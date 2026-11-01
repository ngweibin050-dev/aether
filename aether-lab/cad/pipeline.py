"""Three-view sheet -> validated parametric CAD: the whole pipeline, in five stages.

1. drawing interpretation (cad/observations.py, CV on the ink)            -> measured observations
2. AI stages S1-S8 (cad/ai.py: Muse Spark, Muse Wonder, SAM 3.1)        -> typed, gated, stored hypotheses
3. object-specific interpretation (cad/vehicle.py) + planning (planner)  -> the .aethercad document
4. CAD construction (cad/document.py recompute over cad/ops.py)          -> OpenCascade B-rep
5. validation + export (validate, STEP round trip, GLB, reprojection)   -> report

`build()` is used by the worker and the tests. With ai_mode="replay" the stored model answers in a previous
document are reused (no network), which is how recompute stays deterministic.
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
from PIL import Image

from . import ai as AI
from . import observations as O
from . import planner as PL
from . import reproject as RP
from . import tessellate as T
from . import validate as Vd
from . import vehicle as Vh
from .document import Document
from .ops import OPS


def _crops(path, obs, scale=2):
    im = Image.open(path).convert("RGB")
    out, off = {}, {}
    for role, v in obs["views"].items():
        x0, y0, x1, y1 = v["extent"]
        x0, y0 = max(0, x0 - 4), max(0, y0 - 4)
        x1, y1 = min(im.width - 1, x1 + 4), min(im.height - 1, y1 + 4)
        out[role] = im.crop((x0, y0, x1 + 1, y1 + 1)).resize(((x1 - x0 + 1) * scale, (y1 - y0 + 1) * scale), Image.LANCZOS)
        off[role] = (x0, y0, scale)
    return out, off


# ------------------------------------------------------------------------------------------------ validation
def assembly_validation(doc, interference=True):
    """Every component solid (cad/validate.check_solid) + pairwise interference between components whose boxes
    overlap. Contacts (shared surfaces, common volume < 1 mm^3) are reported as contacts; volumes above that are
    interferences unless the joint between the two says the overlap is intended (an embedded stalk)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    comps = [c for c in doc.data["components"] if not c.get("group")]
    res = {"components": {}, "interference": [], "all_valid": True}
    shapes = {}
    for c in comps:
        shp = doc.shapes.get(c["output"])
        if shp is None:
            res["components"][c["id"]] = {"valid": False, "why": "no geometry (feature failed)"}
            res["all_valid"] = False
            continue
        r = Vd.check_solid(shp, c["id"], argument_analysis=c["kind"] == "body_shell")
        res["components"][c["id"]] = r
        res["all_valid"] &= r["valid"]
        shapes[c["id"]] = (shp, r["bbox_mm"])
    if interference:
        intended = {(j["a"], j["b"]) for j in doc.data["joints"] if j.get("type") == "fixed" and "stalk" in j.get("note", "")}
        ids = list(shapes)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                A, B = shapes[a][1], shapes[b][1]
                if any(A[k] > B[k + 3] + 0.5 or B[k] > A[k + 3] + 0.5 for k in range(3)):
                    continue
                op = BRepAlgoAPI_Common(shapes[a][0], shapes[b][0])
                op.SetFuzzyValue(1e-5)
                op.Build()
                if not op.IsDone():
                    res["interference"].append({"a": a, "b": b, "status": "check failed"})
                    continue
                v = Vd.mass(op.Shape())["volume_mm3"] if not op.Shape().IsNull() else 0.0
                if v < 1.0:
                    status = "clear" if v <= 1e-6 else "contact"
                elif (a, b) in intended or (b, a) in intended or ("body" in (a, b) and any(x.startswith("mirror") for x in (a, b))):
                    status = "intended (embedded joint)"
                else:
                    status = "INTERFERENCE"
                    res["all_valid"] = False
                res["interference"].append({"a": a, "b": b, "common_volume_mm3": round(v, 2), "status": status})
    return res


def _validate_fast(doc):
    """Validation used inside recompute (all components, no pairwise interference: that runs once at the end)."""
    return assembly_validation(doc, interference=False)


# ------------------------------------------------------------------------------------------------ S5 scoring
def _score_shape(C, G, shape, obs, aux, F):
    """Build the body only for one shape hypothesis and score its front/rear reprojection (body rows only: above the
    tyres, mirror rows excluded) -> mean IoU."""
    from . import kernel as K
    FD = Vh.keypoint_fields(C, G, shape)
    st = Vh.stations(C)
    xs = sorted(set([s["x"] for s in st] + ([G["x_range"][0], G["x_range"][1]] if G else [])))
    secs = []
    p_exp, _ = Vh.crown_exponent(C, G, F)
    zc = np.linspace(min(C["env"]["front"]["z"].min(), C["env"]["rear"]["z"].min()),
                     max(C["env"]["front"]["z"].max(), C["env"]["rear"]["z"].max()), 300)
    cap = np.maximum(np.interp(zc, C["env"]["front"]["z"], C["env"]["front"]["w"]), np.interp(zc, C["env"]["rear"]["z"], C["env"]["rear"]["w"]))
    for x in xs:
        k = Vh.keypoints_at(FD, x)
        k["crown_exp"], k["cap"] = p_exp, (zc, cap)
        zz, ee = Vh.env_blend(C, k["w_front"])
        secs.append((x, K.section_keypoints(k, zz, ee)))
    body, _ = K.skin_body_v3(secs)
    V, Fc, _, _ = T.mesh(body, 3.0, 0.3)
    H, W = aux["gray"].shape
    out = {}
    for view in ("front", "rear"):
        role = F[view]["key"]
        mod = RP.model_mask([(V, Fc)], F, view, (H, W))
        drw = aux["sils"][role].copy()
        e = obs["ends"][role]
        keep = np.zeros_like(drw)
        x0, y0, x1, y1 = obs["views"][role]["box"]
        keep[y0:(e["body_bottom_v"] or y1) + 1, x0:x1 + 1] = True
        if e["mirror"]:
            keep[e["mirror"]["v0"] - 2:e["mirror"]["v1"] + 3] = False
        out[view] = RP.compare(mod, drw, F[view]["s"], keep)["iou"]
    return float(np.mean(list(out.values()))), out


# ------------------------------------------------------------------------------------------------ build
def build(sheet, out_dir, decisions=None, ai_mode="live", stored=None, log=print, run_s5=True):
    """sheet: path of the drawing. decisions: user decisions (overall_length_mm, end_view_scale). stored: a list of
    stored AI records (hypotheses) to replay. Returns (Document, report dict)."""
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    timings = {}
    rep = {"pipeline": [], "sheet": os.path.basename(sheet)}

    def stage(name, t):
        timings[name] = round(time.time() - t, 2)
        log(f"[{timings[name]:7.2f} s] {name}")

    # 1. drawing interpretation
    t = time.time()
    obs, aux = O.observe(sheet)
    stage("observe (CV on the ink)", t)
    crops, offsets = _crops(sheet, obs)
    store = list(stored or [])
    ai = AI.AI(store, ai_mode, log=lambda e: log(f"    {e.get('who', '')} {e['stage']} {e['key']} {e['state']}"
                                                + (f" {e.get('s')} s" if e.get('s') else "") + (f" ({e.get('error')})" if e.get("error") else "")))
    decisions = dict(decisions or {})
    decisions.setdefault("overall_length_mm", {"value": 4500.0, "provenance": "assumed",
                                               "note": "placeholder: the sheet states no dimension (user default)"})
    decisions.setdefault("end_view_scale", {"value": "per_view", "provenance": "user_confirmed",
                                            "note": "end views fitted at their own scale (user default)"})

    # 2. AI stages: S1 view roles
    t = time.time()
    s1, s1_ev = AI.s1_view_roles(ai, crops, O.nose_left_cv(obs))
    if s1:
        decisions.update({k: v for k, v in s1.items() if k != "object"})
        decisions["object"] = s1["object"]
    else:
        decisions.setdefault("front_view", {"value": "end_b", "provenance": "unresolved",
                                            "note": "S1 failed its gate; needs confirmation: " + str(s1_ev.get("gate"))})
        decisions.setdefault("nose_left", {"value": O.nose_left_cv(obs), "provenance": "inferred", "by": "CV only"})
    stage("S1 view roles (Muse Spark x2 + CV gate)", t)
    rep["S1"] = {"decision": s1, "evidence": s1_ev}
    F = Vh.frames(obs, decisions)
    crops["end_front"], crops["end_rear"] = crops[F["front"]["key"]], crops[F["rear"]["key"]]
    offsets["end_front"], offsets["end_rear"] = offsets[F["front"]["key"]], offsets[F["rear"]["key"]]

    # S2 SAM 3.1 checks
    t = time.time()
    s2 = AI.s2_sam_checks(ai, crops, offsets, aux["ink"], obs["side"]["wheels"])
    stage("S2 SAM 3.1 segmentation checks", t)

    # S3 region labels
    t = time.time()
    labels, s3_err = {}, {}
    for role in ("side", "top", "end_a", "end_b"):
        regs = obs["regions"][role]
        ov = O.region_overlay(aux["gray"], aux["region_labels"][role], obs["views"][role]["extent"], regs)
        ov.save(f"{out_dir}/regions_{role}.png")
        name = {"end_a": "end A", "end_b": "end B"}.get(role, role)
        lab, err = AI.s3_region_labels(ai, name, ov, len(regs), decisions.get("object", "car"))
        labels[role] = lab
        if err:
            s3_err[role] = err
    stage("S3 region labels (Muse Spark + Muse Wonder)", t)
    rep["S3"] = {"labels": labels, "errors": s3_err,
                 "counts": {r: {s: sum(1 for l in v.values() if l["status"] == s) for s in ("accepted", "ambiguous", "unconfirmed", "unlabelled")}
                            for r, v in labels.items()}}

    # 3. vehicle interpretation
    t = time.time()
    C = Vh.curves(obs, F)
    G = Vh.greenhouse(obs, labels, F, C)
    rear_key = F["rear"]["key"]
    near = [tuple(r["centroid"]) for i, r in enumerate(obs["regions"][rear_key])
            if (labels[rear_key].get(i) or {}).get("kind") == "exhaust" and labels[rear_key][i]["status"] == "accepted"]
    tips = O.exhaust_tips(aux["gray"], aux["ink"], obs["views"][rear_key]["extent"], obs["ends"][rear_key]["u_c"], near) if near else []
    lc = [O.lug_count(aux["ink"], w) for w in obs["side"]["wheels"]]
    lugs = {"count": lc[0][0] if lc and lc[0][0] and all(c[0] == lc[0][0] for c in lc) else None,
            "evidence": [f"side: angular FFT around the hub: {c[0]} (strength {c[1]:.2f})" for c in lc]}
    # drawn regions that become features (accepted labels only; REGION_RULES picks the view that sees each face-on)
    region_feats, region_skipped = [], []
    role_of = {"side": "side", "top": "top", "front": F["front"]["key"], "rear": F["rear"]["key"]}
    for kind, (op, view, val) in Vh.REGION_RULES.items():
        role = role_of[view]
        for i, rg in enumerate(obs["regions"][role]):
            lab = labels[role].get(i)
            if not lab or lab.get("kind") != kind:
                continue
            if lab["status"] != "accepted":
                region_skipped.append({"region": rg["id"], "kind": kind, "why": f"label {lab['status']}"})
                continue
            poly = O.region_polygon(aux["region_labels"][role], obs["views"][role]["extent"], i)
            if poly is None or len(poly) < 4:
                region_skipped.append({"region": rg["id"], "kind": kind, "why": "too small to outline"})
                continue
            region_feats.append({"kind": kind, "op": op, "view": view, "value": val, "region_id": rg["id"],
                                 "label": lab["status"], "poly_model": Vh.region_to_model(F, view, poly).round(3).tolist()})
    stage("vehicle interpretation (curves, greenhouse, tips, lugs, region features)", t)
    rep["regions"] = {"built": [{k: r[k] for k in ("region_id", "kind", "op", "view")} for r in region_feats],
                      "skipped": region_skipped}

    # S5 section hypotheses: >= 2 Muse Wonder samples + the default, each built and scored by reprojection
    t = time.time()
    cands = [{"name": "default (assumed)", "shape": Vh.DEFAULT_SHAPE, "source": "assumed"}]
    table = "station table (x, z_top, z_bot, y_max, cabin):\n" + "\n".join(
        f"{x:.0f}, {np.interp(x, C['x'], C['ztop']):.0f}, {np.interp(x, C['x'], C['zbot']):.0f}, "
        f"{np.interp(x, C['xt'], C['ybody']):.0f}, {'yes' if Vh.cabin_weight(C, G, x) > 0.5 else 'no'}"
        for x in np.linspace(C["x"][0], C["x"][-1], 16))
    s5 = AI.s5_section_hypotheses(ai, crops, table) if run_s5 else []
    for smp in s5:
        if "answer" not in smp:
            continue
        sh = json.loads(json.dumps(Vh.DEFAULT_SHAPE))
        for g in smp["answer"]["groups"]:
            sh[g["group"]] = {k: float(g[k]) for k in ("crown_frac", "deck_drop_frac", "sill_radius_frac", "glass_bulge_frac")}
        cands.append({"name": f"Muse Wonder seed {smp['seed']}", "shape": sh, "source": "inferred",
                      "model": smp.get("model"), "fallback": smp.get("fallback"), "reasoning": smp["answer"]["reasoning"]})
    for c in cands:
        try:
            c["score_mean_iou"], c["score_views"] = _score_shape(C, G, c["shape"], obs, aux, F)
        except Exception as e:
            c["score_mean_iou"], c["error"] = -1.0, f"{type(e).__name__}: {e}"[:300]
    best = max(cands, key=lambda c: c["score_mean_iou"])
    stage("S5 section hypotheses (Muse Wonder) built + scored", t)
    rep["S5"] = {"candidates": [{k: v for k, v in c.items() if k != "shape"} | {"shape": c["shape"]} for c in cands],
                 "chosen": best["name"], "rule": "highest mean front/rear body IoU (reprojection), not model confidence"}

    # S6 / S7 (recorded; S7 never decides)
    t = time.time()
    s6, s6_model = AI.s6_transitions(ai, crops)
    s7, s7_model = AI.s7_ambiguities(ai, crops, [
        ("brake_disc", "Inside each rim a ring at ~0.6 of the tyre radius is drawn: brake disc, or the rim's inner step?"),
        ("end_view_scale", "The end views are ~4.4 % shorter than the side view: drawn at another scale, or a drawing error?"),
        ("intake_depth", "How deep is the side air intake behind the door?")])
    stage("S6 transitions + S7 ambiguities (Muse Wonder)", t)

    # 4. plan + CAD construction
    t = time.time()
    decisions["section_shape"] = {"value": best["name"], "provenance": best["source"]}
    data = PL.plan_vehicle(obs, labels, decisions, best["shape"], F, C, G, tips, lugs, s2=s2, s6=s6, s7=s7,
                           region_feats=region_feats)
    data["hypotheses"] = store
    data["pipeline_report"] = {k: rep[k] for k in ("S1", "S3", "S5", "regions")}
    doc = Document(data, OPS)
    stage("plan (typed document)", t)
    t = time.time()
    st = doc.recompute(validate=_validate_fast)
    stage(f"recompute ({len(doc.data['features'])} features) -> {st['state']}", t)
    rep["recompute"] = st
    return doc, {"report": rep, "timings": timings, "obs": obs, "aux": aux, "F": F, "C": C, "G": G,
                 "seconds": round(time.time() - t0, 1)}


MATERIALS = {"glass": "#1d2b3a", "light": "#dfe7ef", "panel": None}


def _pip(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-30) + x1:
            inside = not inside
    return inside


def face_materials(doc, shape):
    """Material per face of the final body, by a GEOMETRIC rule (never a face index): a face whose centre projects
    inside an imprinted region's outline in that region's view, and faces that view, takes the region's material."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    PV = doc.param_values()
    imps = []
    for f in doc.data["features"]:
        if f["op"] == "imprint_projection" and MATERIALS.get(f["params"].get("material")):
            sc = PV.get("region_scale", 1.0)
            polys = [[[c * sc for c in q] for q in poly] for poly in doc.data["observations"][f["params"]["polygons"]["$obs"]]["data"]]
            imps.append((f["params"]["view"], polys, f["params"]["material"]))
    out = []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        face = TopoDS.Face_s(ex.Current())
        g = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, g)
        c = g.CentreOfMass()
        P = np.array([c.X(), c.Y(), c.Z()])
        sas = ShapeAnalysis_Surface(BRep_Tool.Surface_s(face))
        uv = sas.ValueOfUV(c, 1e-6)
        pr = BRepLProp_SLProps(BRepAdaptor_Surface(face), uv.X(), uv.Y(), 1, 1e-6)
        n = np.array([pr.Normal().X(), pr.Normal().Y(), pr.Normal().Z()]) if pr.IsNormalDefined() else np.zeros(3)
        if face.Orientation() == TopAbs_REVERSED:
            n = -n
        mat = None
        for view, polys, m in imps:
            q, facing = {"side": ((P[0], P[2]), abs(n[1]) > 0.25), "top": ((P[0], P[1]), n[2] > 0.25),
                         "front": ((P[1], P[2]), n[0] < -0.25), "rear": ((P[1], P[2]), n[0] > 0.25)}[view]
            if facing and any(_pip(q, poly) for poly in polys):
                mat = m
                break
        out.append(mat)
        ex.Next()
    return out


def components_for_export(doc):
    out = []
    for c in doc.data["components"]:
        e = {"id": c["id"], "name": c["name"], "parent": c.get("parent"), "group": c.get("group", False),
             "colour": c.get("colour"), "material": c.get("material"),
             "extras": {"component_id": c["id"], "kind": c["kind"],
                        "features": [f["id"] for f in doc.data["features"] if f.get("component") == c["id"]][:60]}}
        if not c.get("group"):
            e["shape"] = doc.shapes[c["output"]]
            if c["kind"] == "body_shell":
                fm = face_materials(doc, e["shape"])
                if any(fm):
                    e["face_materials"] = fm
                    e["extras"]["face_materials"] = {m: sum(1 for x in fm if x == m) for m in set(fm) if m}
        out.append(e)
    return out


def finalize(doc, res, out_dir, log=print, s8=True, ai_mode="replay"):
    """Validation (with interference), STEP export + fresh-process round trip, GLB, three-view reprojection, S8
    advisory check, report. Returns the report dict (also written to out_dir/report.json)."""
    rep = {"title": doc.data["title"], "maturity": doc.data["maturity"]}
    if doc.data["status"].get("state") != "ok":
        rep["recompute_failed"] = doc.data["status"]
        rep["exports"] = {"blocked": "the document did not recompute: nothing is exported"}
        with open(f"{out_dir}/report.json", "w") as f:
            json.dump(rep, f, indent=1, default=str)
        log("recompute failed: " + json.dumps(doc.data["status"], default=str)[:400])
        return rep
    t = time.time()
    val = assembly_validation(doc, interference=True)
    rep["validation"] = val
    log(f"[{time.time() - t:7.2f} s] assembly validation: all_valid={val['all_valid']}")
    comps = components_for_export(doc)
    solids = [c for c in comps if not c.get("group")]
    from . import export as EX
    rep["exports"] = {}
    if val["all_valid"]:
        t = time.time()
        os.makedirs(f"{out_dir}/brep", exist_ok=True)
        rt = EX.roundtrip(solids, f"{out_dir}/model.step", f"{out_dir}/brep")
        rep["step_roundtrip"] = rt
        rep["exports"]["step"] = "model.step"
        log(f"[{time.time() - t:7.2f} s] STEP export + round trip: all_pass={rt['all_pass']}")
    else:
        rep["step_roundtrip"] = {"skipped": "STEP export is blocked: the model is not valid"}
    t = time.time()
    extras = {"authoritative": "model.aethercad (feature history) + model.step (B-rep)", "maturity": doc.data["maturity"],
              "units_source": "mm (GLB stores metres, Y up)"}
    with open(f"{out_dir}/model.glb", "wb") as f:
        f.write(EX.glb(comps, extras))
    rep["exports"]["glb"] = "model.glb"
    log(f"[{time.time() - t:7.2f} s] GLB (tessellated from the B-rep)")
    t = time.time()
    meshes = []
    for c in solids:
        V, F, _, _ = T.mesh(c["shape"], 0.5, 0.2)
        meshes.append((V.astype(float), F))
    rp = RP.evaluate(meshes, res["obs"], res["aux"], res["F"], out_dir)
    rep["reprojection"] = rp
    rep["reprojection_note"] = ("Silhouette agreement is necessary, not sufficient: the cross-sections between the end views, "
                                "the wheel-well depth and the deck crowns are inferred and are not tested by these numbers.")
    log(f"[{time.time() - t:7.2f} s] reprojection: " + ", ".join(f"{k} IoU {v['iou']}" for k, v in rp.items()))
    if s8:
        try:
            store = doc.data["hypotheses"]
            ai = AI.AI(store, ai_mode)
            ims = {k: Image.open(f"{out_dir}/{v['image']}") for k, v in rp.items()}
            import hashlib
            key = hashlib.sha1(json.dumps({k: v["iou"] for k, v in rp.items()}, sort_keys=True).encode()
                               + b"".join(open(f"{out_dir}/{v['image']}", "rb").read() for v in rp.values())).hexdigest()[:16]
            rep["S8_verification"] = AI.s8_verify(ai, ims, key)        # keyed by the images: never a stale verdict
        except Exception as e:
            rep["S8_verification"] = {"error": f"{type(e).__name__}: {e}"[:200]}
    # provenance summary
    cls = {}
    for p in doc.data["parameters"].values():
        cls[p["provenance"]] = cls.get(p["provenance"], 0) + 1
    rep["provenance_counts"] = cls
    rep["assumptions"] = doc.data["assumptions"]
    rep["maturity_reached"] = ("drawing_consistent" if val["all_valid"] and rep.get("step_roundtrip", {}).get("all_pass")
                               and all(v["iou"] >= 0.9 for v in rp.values()) else
                               "geometrically_valid" if val["all_valid"] else "draft_inference")
    doc.data["maturity"] = rep["maturity_reached"]
    doc.data["validation"] = {"summary": {"all_valid": val["all_valid"],
                                          "step_roundtrip_pass": rep.get("step_roundtrip", {}).get("all_pass"),
                                          "reprojection_iou": {k: v["iou"] for k, v in rp.items()}},
                              "interference": val["interference"]}
    with open(f"{out_dir}/report.json", "w") as f:
        json.dump(rep, f, indent=1, default=str)
    return rep
