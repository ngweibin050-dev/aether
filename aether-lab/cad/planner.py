"""Deterministic CAD planner for a vehicle three-view: observations + accepted AI labels + decisions + hypotheses ->
an .aethercad document (parameters with relations and provenance, observations, datums, features, components,
joints, assumptions). No geometry is built here; no model output is executed: every number it writes comes from
the measured observations, a recorded decision, or a schema-checked hypothesis.

Scale: every mm value is (measured px) x (mm per px). The mm per px follows from overall_length, which is ASSUMED
(4500 mm placeholder) until the user confirms a real dimension. Observations are stored at the reference scale
(REF_L); every derived parameter carries a `scaled` / `sample` relation on overall_length, so editing the length
rescales the whole model consistently.
"""
from __future__ import annotations

import numpy as np

from . import vehicle as Vh
from .document import Document

REF_L = 4500.0


def _P(doc, pid, value=None, rel=None, prov="derived", unit="mm", note=None, evidence=None, rng=None):
    p = {"provenance": prov, "unit": unit}
    if rel is not None:
        p["rel"] = rel
    else:
        p["value"] = value
    if note:
        p["note"] = note
    if evidence:
        p["evidence"] = evidence
    if rng:
        p["range"] = rng
    doc["parameters"][pid] = p


def scaled(v):
    return {"kind": "scaled", "ref": float(v), "by": "overall_length", "by_ref": REF_L}


def sample(obs_id, at):
    return {"kind": "sample", "obs": obs_id, "at": at, "by": "overall_length", "by_ref": REF_L}


def _ref(pid):
    return {"$p": pid}


def plan_vehicle(obs, labels, decisions, shape, F, C, G, tips, lugs, s2=None, s6=None, s7=None, provenance_notes=None,
                 region_feats=None):
    """Returns the document dict (validated by Document on load)."""
    title = f"{decisions.get('object', 'car')} — three-view CAD reconstruction"
    doc = Document.new(obs["source"], title)
    doc["decisions"] = decisions
    A = doc["assumptions"]

    def assume(aid, text, cls, affects, editable):
        A.append({"id": aid, "text": text, "class": cls, "affects": affects, "editable_via": editable})

    # ---------------------------------------------------------------- global
    _P(doc, "overall_length", value=float(decisions["overall_length_mm"]["value"]),
       prov=decisions["overall_length_mm"]["provenance"], note=decisions["overall_length_mm"].get("note"),
       rng=[500.0, 20000.0])
    _P(doc, "scale_mm_per_px_side", rel=scaled(F["side"]["s"]), note="overall_length / side-view length (px)",
       evidence=[f"side length {obs['fit']['length_side_px']} px"])
    _P(doc, "end_view_scale_ratio", value=float(F["front"]["s"] / F["side"]["s"]), prov="derived", unit="1",
       note=f"end views drawn at a {'separate (fitted)' if F['scale_mode'] == 'per_view' else 'common'} scale",
       evidence=[f"height side {obs['fit']['height_side_px']} px vs end views {obs['fit']['height_end_px']} px"])
    assume("A-01", "Real size: the sheet has no dimension; overall length is a placeholder until confirmed.",
           decisions["overall_length_mm"]["provenance"], ["every mm value"], ["overall_length"])
    assume("A-02", f"End views are drawn at {F['front']['s'] / F['side']['s']:.4f} x the side view's scale (fitted from the "
                   "heights; confirmed by the plan vs end-view widths agreeing within 0.5 %).", "derived",
           ["front/rear envelopes", "track", "tyre widths", "exhaust and mirror heights"], ["decision end_view_scale"])

    # ---------------------------------------------------------------- wheels / datums
    wf, wr = C["wheels"][0], C["wheels"][1]
    _P(doc, "front_axle_x", rel=scaled(wf["x"]), evidence=["side: wheel circle centre", f"px {wf['px']['cx']:.1f}"])
    _P(doc, "wheelbase", rel=scaled(wr["x"] - wf["x"]), evidence=["side: wheel circle centres"])
    _P(doc, "rear_axle_x", rel={"kind": "linear", "terms": [["front_axle_x", 1.0], ["wheelbase", 1.0]], "const": 0.0})
    tail_ref = float(C["x"][-1])
    _P(doc, "rear_overhang", rel=scaled(tail_ref - wr["x"]), evidence=["side: tail end to rear wheel centre"])
    for tag, w in (("f", wf), ("r", wr)):
        _P(doc, f"wheel_z_{tag}", rel=scaled(w["z_centre_drawn"]), evidence=["side: wheel circle centre height above ground"])
        _P(doc, f"r_tyre_{tag}", rel=scaled(w["r_tyre"]),
           evidence=[f"side: tyre circle r {w['px']['r']:.1f} px; centre to ground line {w['r_tyre_to_ground'] / F['side']['s']:.1f} px "
                     "(the drawn tyre stands on the ground line: the larger is used)"])
        rim = [r for r in w["rings"] if 0.6 * w["r_tyre"] <= r <= 0.88 * w["r_tyre"]]
        r_rim = max(rim) if rim else 0.76 * w["r_tyre"]
        _P(doc, f"r_rim_{tag}", rel=scaled(r_rim), prov="derived" if rim else "assumed",
           evidence=["side: inner ring of the wheel (rim lip)" if rim else "no rim ring measured: 0.76 x tyre radius"])
        _P(doc, f"r_arch_{tag}", rel=scaled(w["r_arch"] or 1.08 * w["r_tyre"]), prov="derived" if w["r_arch"] else "assumed",
           evidence=[f"side: arch line ring r {w['px']['arch']['r']:.1f} px, support {w['px']['arch']['support']}"] if w["r_arch"] else None)
        hubs = [r for r in w["rings"] if 0.25 * w["r_tyre"] <= r <= 0.45 * w["r_tyre"]]
        _P(doc, f"r_hub_{tag}", rel=scaled(min(hubs) if hubs else 0.32 * w["r_tyre"]), prov="derived" if hubs else "assumed",
           evidence=["side: innermost wheel ring"] if hubs else None)
    for tag, which in (("f", "front"), ("r", "rear")):
        e = obs["ends"][F[which]["key"]]
        t = e["tyres"]
        if t:
            width = ((t["left"][1] - t["left"][0]) + (t["right"][1] - t["right"][0])) / 2 * F[which]["s"]
            track = ((t["right"][0] + t["right"][1]) / 2 - (t["left"][0] + t["left"][1]) / 2) * F[which]["s"]
            ev = [f"{which} view: tyre side faces at {t['left']} / {t['right']} px"]
            prov = "derived"
        else:
            width, track, ev, prov = 0.13 * REF_L / 4.5, 0.36 * REF_L, None, "assumed"
        _P(doc, f"tyre_width_{tag}", rel=scaled(width), prov=prov, evidence=ev)
        _P(doc, f"track_{tag}", rel=scaled(track), prov=prov, evidence=ev)
    _P(doc, "well_clearance", value=25.0, prov="assumed", note="gap between the tyre's inner face and the wheel-well wall",
       rng=[0.0, 200.0])
    for tag in ("f", "r"):
        _P(doc, f"well_y_inner_{tag}", rel={"kind": "linear", "terms": [[f"track_{tag}", 0.5], [f"tyre_width_{tag}", -0.5],
                                                                         ["well_clearance", -1.0]], "const": 0.0})
    assume("A-03", "Wheel wells: a cylinder of the measured arch radius about each axle, from the tyre's inner face minus a "
                   "25 mm clearance outwards (well depth is not drawn).", "assumed", ["wheel well cuts"], ["well_clearance"])
    doc["datums"] = {
        "PLANE_SYM": {"type": "plane", "origin": [0, 0, 0], "normal": [0, 1, 0], "note": "symmetry plane"},
        "PLANE_GROUND": {"type": "plane", "origin": [0, 0, 0], "normal": [0, 0, 1], "note": "ground line"},
        "AXIS_FRONT": {"type": "axis", "origin": [_ref("front_axle_x"), 0, _ref("wheel_z_f")], "dir": [0, 1, 0]},
        "AXIS_REAR": {"type": "axis", "origin": [_ref("rear_axle_x"), 0, _ref("wheel_z_r")], "dir": [0, 1, 0]},
    }

    # ---------------------------------------------------------------- body observations (reference scale)
    FD = Vh.keypoint_fields(C, G, shape)
    for key in Vh.FIELD_KEYS:
        doc["observations"][f"obs.field.{key}"] = {
            "kind": "keypoint_field", "class": Vh.FIELD_CLASS[key], "data": np.c_[FD["x"], FD[key]].round(4).tolist(),
            "note": "section keypoint along x at the reference scale (cad/vehicle.keypoint_fields)"}
    for which in ("front", "rear"):
        e = C["env"][which]
        doc["observations"][f"obs.env.{which}"] = {"kind": "envelope", "class": "measured",
                                                   "data": np.c_[e["z"], e["w_norm"]].round(5).tolist(),
                                                   "view": F[which]["key"], "note": "normalised half-width vs height"}
    zc = np.linspace(min(C["env"]["front"]["z"].min(), C["env"]["rear"]["z"].min()),
                     max(C["env"]["front"]["z"].max(), C["env"]["rear"]["z"].max()), 300)
    cap = np.maximum(np.interp(zc, C["env"]["front"]["z"], C["env"]["front"]["w"]), np.interp(zc, C["env"]["rear"]["z"], C["env"]["rear"]["w"]))
    doc["observations"]["obs.env.cap"] = {"kind": "envelope_cap", "class": "measured", "data": np.c_[zc, cap].round(3).tolist(),
                                          "note": "max over the front and rear views of the end-view half-width (mm, reference "
                                                  "scale): no section may be wider at that height (hard drawing constraint)"}
    p_exp, p_ev = Vh.crown_exponent(C, G, F)
    _P(doc, "roof_crown_exp", value=round(p_exp, 3), prov="derived", unit="1", evidence=[p_ev], rng=[1.2, 10.0])
    _P(doc, "env_cap_tol", value=1.0, prov="assumed", unit="1", note="1.0 = sections exactly within the end-view silhouette",
       rng=[0.9, 1.2])
    for nm, xs_, ys_ in (("ztop", C["x"], C["ztop"]), ("zbot", C["x"], C["zbot"]), ("ybody", C["xt"], C["ybody"])):
        doc["observations"][f"obs.curve.{nm}"] = {"kind": "profile", "class": "measured",
                                                 "data": np.c_[xs_, ys_].round(3).tolist()}
    doc["observations"]["obs.fits"] = {"kind": "fit_report", "class": "derived", "data": C["fits"] + (G["fits"] if G else []) + FD["_notes"]}
    doc["observations"]["obs.regions"] = {"kind": "regions", "class": "measured", "data": {
        v: [{k: r[k] for k in ("id", "area_px", "bbox", "centroid")} | {"label": labels.get(v, {}).get(i)}
            for i, r in enumerate(obs["regions"][v])] for v in obs["regions"]}}
    doc["observations"]["obs.views"] = {"kind": "views", "class": "measured", "data": {
        "views": obs["views"], "fit": obs["fit"], "frames": {k: v for k, v in F.items()}}}
    if G is not None:
        doc["observations"]["obs.greenhouse"] = {"kind": "greenhouse", "class": "measured", "data": {
            "regions": G["regions"], "x_range": G["x_range"], "belt_line": G["belt_line"]}}
    assume("A-04", "Cross-section shape between the measured extremes: the end views give only the MAXIMUM envelope, so the "
                   "flank shape at each station is that envelope blended front -> rear (smoothstep between the axles).",
           "inferred", ["every section flank"], ["station overrides", "S5 hypotheses"])
    assume("A-05", "Lower body edge under the wheels is not visible; it is bridged straight between the arch edges.",
           "assumed", ["z_bot inside the wheel columns"], ["station z_bot overrides"])
    assume("A-06", "Deck shapes (bonnet, engine deck) and crowns are shape fractions from Muse Wonder (or defaults if it "
                   "gave none) between measured extremes.", "inferred", ["deck edge, crown"], ["S5 hypotheses", "station overrides"])
    assume("A-11", f"Roof crown shape: exponent {p_exp:.2f} fitted to the end views' top envelope ({p_ev}).", "derived",
           ["roof crown"], ["roof_crown_exp"])
    assume("A-12", "Hard constraint from the end views: no section is wider at any height than the drawn end-view silhouette "
                   "(max of front and rear).", "measured", ["every section"], ["env_cap_tol"])
    assume("A-07", "The interior is not modelled: the body is the closed exterior envelope (styling solid), not panels.",
           "assumed", ["body"], [])

    # ---------------------------------------------------------------- stations
    st = Vh.stations(C)
    xs = sorted(set([s["x"] for s in st] + ([G["x_range"][0], G["x_range"][1]] if G else [])))
    roles = {round(s["x"], 3): s["role"] for s in st}
    xf, xr_, xt = wf["x"], wr["x"], tail_ref
    feats = doc["features"]
    sec_ids = []
    for i, x in enumerate(xs):
        sid = f"st{i:02d}"
        _P(doc, f"{sid}.x_ref", rel=scaled(x), note=f"station position in the drawing ({roles.get(round(x, 3), 'boundary')})")
        if x <= xf:
            rel = {"kind": "linear", "terms": [["front_axle_x", x / xf]], "const": 0.0}
            seg = "front overhang"
        elif x <= xr_:
            rel = {"kind": "linear", "terms": [["front_axle_x", 1.0], ["wheelbase", (x - xf) / (xr_ - xf)]], "const": 0.0}
            seg = "wheelbase"
        else:
            rel = {"kind": "linear", "terms": [["rear_axle_x", 1.0], ["rear_overhang", (x - xr_) / (xt - xr_)]], "const": 0.0}
            seg = "rear overhang"
        _P(doc, f"{sid}.x", rel=rel, note=f"placed on the {seg} (moves with the axle datums)")
        params = {"x": _ref(f"{sid}.x"), "env_front": {"$obs": "obs.env.front"}, "env_rear": {"$obs": "obs.env.rear"},
                  "scale": _ref(f"{sid}._scale"), "crown_exp": _ref("roof_crown_exp"), "env_cap": {"$obs": "obs.env.cap"},
                  "cap_tol": _ref("env_cap_tol")}
        _P(doc, f"{sid}._scale", rel={"kind": "scaled", "ref": 1.0, "by": "overall_length", "by_ref": REF_L}, unit="1",
           note="model scale relative to the reference (scales the envelope heights)")
        scale_confirmed = decisions["overall_length_mm"].get("provenance") == "user_confirmed"
        for key in ("z_top", "z_bot", "y_max", "z_max", "y_sh", "z_sh", "y_re", "z_re", "r_low", "glass_bulge", "w_front"):
            cls = Vh.FIELD_CLASS[key]
            if cls == "measured" and not scale_confirmed:
                cls = "derived"           # measured in px on the drawing; in mm only via the (assumed) scale
            unit = "1" if key in ("glass_bulge", "w_front") else "mm"
            if unit == "1":
                v = float(np.interp(x, FD["x"], FD[key]))
                _P(doc, f"{sid}.{key}", value=round(v, 5), prov=cls, unit="1")
            else:
                _P(doc, f"{sid}.{key}", rel=sample(f"obs.field.{key}", f"{sid}.x_ref"), prov=cls)
            params[key] = _ref(f"{sid}.{key}")
        feats.append({"id": f"section.{sid}", "op": "section_sketch", "params": params, "inputs": [],
                      "label": f"Section sketch {sid} ({roles.get(round(x, 3), 'boundary')}, x_ref {x:.0f} mm)",
                      "component": "body"})
        sec_ids.append(f"section.{sid}")
    feats.append({"id": "body.skin", "op": "skin_sections", "params": {}, "inputs": sec_ids,
                  "label": f"Body skin: NURBS surface through {len(sec_ids)} sections, mirrored, end caps", "component": "body"})
    last = "body.skin"
    for tag, nm in (("f", "front"), ("r", "rear")):
        fid = f"body.well_{tag}"
        feats.append({"id": fid, "op": "wheel_well_cut", "inputs": [last], "component": "body",
                      "label": f"{nm.capitalize()} wheel openings + wells (both sides)",
                      "params": {"x": _ref("front_axle_x" if tag == "f" else "rear_axle_x"), "z": _ref(f"wheel_z_{tag}"),
                                 "r_arch": _ref(f"r_arch_{tag}"), "y_inner": _ref(f"well_y_inner_{tag}")}})
        last = fid

    # exhaust openings in the tail + tips
    if tips:
        holes, hparams = [], []
        e = obs["ends"][F["rear"]["key"]]
        for j, tp in enumerate(tips):
            for side, u in (("L", tp["u"][0]), ("R", tp["u"][1])):
                y, z = Vh.end_yz(F, "rear", u, tp["v"])
                tid = f"exhaust{j}{side}"
                _P(doc, f"{tid}.y", rel=scaled(float(y)), evidence=[f"rear view: circle centre u {u:.1f} px"])
                _P(doc, f"{tid}.z", rel=scaled(float(z)), evidence=[f"rear view: circle centre v {tp['v']:.1f} px"])
                hparams.append(tid)
        r_ex = float(np.mean([t["r"] for t in tips]) * F["rear"]["s"])
        for j, tp in enumerate(tips):
            _P(doc, f"exhaust{j}.r", rel=scaled(tp["r"] * F["rear"]["s"]), evidence=[f"rear view: circle r {tp['r']:.1f} px, pair symmetry {tp['pair_symmetry_px']} px"])
        _P(doc, "exhaust_protrusion", value=20.0, prov="assumed", rng=[0.0, 300.0])
        _P(doc, "exhaust_depth", value=120.0, prov="assumed", rng=[10.0, 1000.0])
        _P(doc, "exhaust_wall", value=2.5, prov="assumed", rng=[0.5, 20.0])
        _P(doc, "tail_x", rel={"kind": "linear", "terms": [["rear_axle_x", 1.0], ["rear_overhang", 1.0]], "const": 0.0})
        _P(doc, "exhaust_x0", rel={"kind": "linear", "terms": [["tail_x", 1.0], ["exhaust_depth", -1.0]], "const": 0.0})
        _P(doc, "exhaust_x1", rel={"kind": "linear", "terms": [["tail_x", 1.0], ["exhaust_protrusion", 1.0]], "const": 0.0})
        assume("A-08", "Exhaust tips: positions and radii measured in the rear view; how far they protrude (20 mm), how "
                       "deep they go into the tail (120 mm) and the wall (2.5 mm) are assumed.", "assumed",
               ["exhaust tips"], ["exhaust_protrusion", "exhaust_depth", "exhaust_wall"])
        feats.append({"id": "body.exhaust_openings", "op": "cut_cylinders_x", "inputs": [last], "component": "body",
                      "label": f"{len(hparams)} exhaust openings in the tail",
                      "params": {"x0": _ref("exhaust_x0"), "x1": {"$p": "exhaust_x1"},
                                 "holes": [[_ref(f"{t}.y"), _ref(f"{t}.z"), _ref(f"exhaust{t[7]}.r")] for t in hparams]}})
        last = "body.exhaust_openings"
    # ---------------------------------------------------------------- drawn regions -> pockets, then imprints
    groups = {}
    for rf in region_feats or []:
        groups.setdefault((rf["op"], rf["kind"], rf["view"]), []).append(rf)
    order = sorted(groups, key=lambda k: (0 if k[0] == "pocket" else 1, k[1]))
    _P(doc, "region_scale", rel={"kind": "scaled", "ref": 1.0, "by": "overall_length", "by_ref": REF_L}, unit="1",
       note="region outlines are stored at the reference scale")
    for op, kind, view in order:
        items = groups[(op, kind, view)]
        oid = f"obs.region.{kind}.{view}"
        doc["observations"][oid] = {"kind": "region_outlines", "class": "measured", "view": view,
                                    "regions": [it["region_id"] for it in items],
                                    "label_status": [it["label"] for it in items],
                                    "data": [it["poly_model"] for it in items],
                                    "note": f"outlines of the regions labelled '{kind}' (S3) in the {view} view, model "
                                            "coordinates of that view's plane at the reference scale"}
        fid = f"body.{op}_{kind}_{view}"
        params = {"view": view, "polygons": {"$obs": oid}, "scale": _ref("region_scale"), "name": f"{kind} ({view})"}
        if op == "pocket":
            pid = f"depth_{kind}"
            if pid not in doc["parameters"]:
                _P(doc, pid, value=float(items[0]["value"]), prov="assumed", rng=[1.0, 400.0],
                   note=f"depth of the {kind} recess (not drawn)")
            params["depth"] = _ref(pid)
            label = f"Pocket: {kind.replace('_', ' ')} ({len(items)} region(s), {view} view, assumed depth)"
        else:
            params["material"] = items[0]["value"]
            label = f"Imprint: {kind.replace('_', ' ')} outline ({len(items)} region(s), {view} view)"
        feats.append({"id": fid, "op": f"{op}_projection", "inputs": [last], "params": params, "component": "body",
                      "label": label, "region": {"kind": kind, "view": view, "material": params.get("material")}})
        last = fid
    if region_feats:
        assume("A-13", "Drawn regions become features of the body: windows / windscreen / door / lights are IMPRINTED "
                       "(the outline splits the surface; no depth is invented); intakes, grilles, louvres and the plate are "
                       "POCKETS whose depths are assumed (not drawn). Each is built from the view that sees it face-on.",
               "assumed", ["region features"], ["depth_*"])
    body_out = last
    comps = [{"id": "body", "name": "Body shell", "kind": "body_shell", "role": "body", "output": body_out,
              "material": "paint", "colour": "#b9c3cf", "parent": None}]
    if tips:
        for t in hparams:
            j = t[7]
            fid = f"{t}.tip"
            feats.append({"id": fid, "op": "exhaust_tip", "inputs": [], "component": t,
                          "label": f"Exhaust tip {t[7:]}", "params": {"y": _ref(f"{t}.y"), "z": _ref(f"{t}.z"),
                                                                    "r": _ref(f"exhaust{j}.r"), "wall": _ref("exhaust_wall"),
                                                                    "x0": _ref("exhaust_x0"), "x1": _ref("exhaust_x1")}})
            comps.append({"id": t, "name": f"Exhaust tip {t[7:]}", "kind": "exhaust_tip", "role": "body", "output": fid,
                          "material": "metal", "colour": "#8d939b", "parent": None})
            doc["joints"].append({"id": f"j.{t}", "type": "fixed", "a": "body", "b": t, "note": "through the tail opening"})

    # ---------------------------------------------------------------- wheels (right side built, left side mirrored)
    _P(doc, "tyre_bead_gap", value=12.0, prov="assumed", note="radial gap tyre bead -> rim lip (the tyre section's spline "
       "corner must stay clear of the lip)", rng=[0.0, 50.0])
    _P(doc, "spokes", value=int(round(wf["spoke_arms"] / 2)), prov="derived", unit="count",
       evidence=[f"side: angular FFT of the spoke ink = {wf['spoke_arms']} arms (front), {wr['spoke_arms']} (rear); drawn as pairs (Y-spokes)"])
    _P(doc, "spoke_split_deg", value=13.0, prov="inferred", unit="deg", note="half-angle between the two arms of a Y spoke")
    _P(doc, "lugs", value=int(lugs["count"]) if lugs.get("count") else 5, prov="derived" if lugs.get("count") else "assumed",
       unit="count", evidence=lugs.get("evidence"))
    assume("A-09", "Wheel detail depth (face thickness, spoke width, barrel radius, bore, lug size) is not drawn; values are "
                   "proportions of the measured radii.", "assumed", ["rims"], ["rim parameters"])
    for tag, axle in (("f", "front_axle_x"), ("r", "rear_axle_x")):
        _P(doc, f"wheel_y_{tag}", rel={"kind": "linear", "terms": [[f"track_{tag}", 0.5]], "const": 0.0})
        _P(doc, f"r_bead_{tag}", rel={"kind": "linear", "terms": [[f"r_rim_{tag}", 1.0], ["tyre_bead_gap", 1.0]], "const": 0.0},
           prov="assumed", note="the tyre's inner surface just clears the rim lip (no overlap)")
        for key, frac, base in (("r_barrel", 0.9, "r_rim"), ("face_t", 0.16, "tyre_width"), ("spoke_w", 0.12, "r_rim"),
                                ("r_bore", 0.22, "r_hub"), ("r_pcd", 0.62, "r_hub"), ("r_lug", 0.1, "r_hub")):
            _P(doc, f"{key}_{tag}", rel={"kind": "linear", "terms": [[f"{base}_{tag}", frac]], "const": 0.0}, prov="assumed",
               note=f"{frac} x {base}")
        tyre = f"wheel_{tag}r.tyre"
        rim = f"wheel_{tag}r.rim"
        feats.append({"id": tyre, "op": "tyre", "inputs": [], "component": f"tyre_{tag}r", "label": f"Tyre {tag.upper()}R (revolve)",
                      "params": {"x": _ref(axle), "y": _ref(f"wheel_y_{tag}"), "z": _ref(f"wheel_z_{tag}"),
                                 "r_out": _ref(f"r_tyre_{tag}"), "r_bead": _ref(f"r_bead_{tag}"), "width": _ref(f"tyre_width_{tag}"),
                                 "sidewall_bulge": 0.08}})
        feats.append({"id": rim, "op": "rim", "inputs": [], "component": f"rim_{tag}r", "label": f"Rim {tag.upper()}R (revolve + Y-spokes x pattern)",
                      "params": {"x": _ref(axle), "y": _ref(f"wheel_y_{tag}"), "z": _ref(f"wheel_z_{tag}"), "outer_sign": 1,
                                 "width": _ref(f"tyre_width_{tag}"), "r_lip": _ref(f"r_rim_{tag}"), "r_barrel": _ref(f"r_barrel_{tag}"),
                                 "r_hub": _ref(f"r_hub_{tag}"), "face_thickness": _ref(f"face_t_{tag}"), "spokes": _ref("spokes"),
                                 "spoke_width": _ref(f"spoke_w_{tag}"), "split_deg": _ref("spoke_split_deg"),
                                 "r_bore": _ref(f"r_bore_{tag}"), "r_pcd": _ref(f"r_pcd_{tag}"), "r_lug": _ref(f"r_lug_{tag}"),
                                 "lugs": _ref("lugs")}})
        for part, fid in (("tyre", tyre), ("rim", rim)):
            lid = fid.replace(f"{tag}r.", f"{tag}l.")
            feats.append({"id": lid, "op": "mirror_copy", "inputs": [fid], "params": {"of": fid}, "component": f"{part}_{tag}l",
                          "label": f"{part.capitalize()} {tag.upper()}L (mirror of {tag.upper()}R at the symmetry plane)"})
        for side in ("r", "l"):
            comps.append({"id": f"wheel_{tag}{side}", "name": f"Wheel {'front' if tag == 'f' else 'rear'} {'right' if side == 'r' else 'left'}",
                          "kind": "wheel_assembly", "role": "assembly", "output": f"wheel_{tag}{side}.rim", "parent": None, "group": True})
            comps.append({"id": f"tyre_{tag}{side}", "name": "Tyre", "kind": "tyre", "role": "body", "output": f"wheel_{tag}{side}.tyre",
                          "material": "rubber", "colour": "#2b2e33", "parent": f"wheel_{tag}{side}"})
            comps.append({"id": f"rim_{tag}{side}", "name": "Rim", "kind": "rim", "role": "body", "output": f"wheel_{tag}{side}.rim",
                          "material": "metal", "colour": "#c7ccd3", "parent": f"wheel_{tag}{side}"})
            doc["joints"].append({"id": f"j.wheel_{tag}{side}", "type": "revolute", "a": "body", "b": f"wheel_{tag}{side}",
                                  "axis": "AXIS_FRONT" if tag == "f" else "AXIS_REAR", "dof": 1})

    # ---------------------------------------------------------------- mirrors
    mp, me = obs["top"].get("mirror"), obs["ends"][F["front"]["key"]].get("mirror")
    if mp and me:
        x0, _ = Vh.top_xy(F, mp["u0"], 0)
        x1, _ = Vh.top_xy(F, mp["u1"], 0)
        x0, x1 = sorted((float(x0), float(x1)))
        _, z1 = Vh.end_yz(F, "front", 0, me["v0"])
        _, z0 = Vh.end_yz(F, "front", 0, me["v1"])
        y_out = mp["half_out_px"] * F["top"]["s"]
        y_in = float(np.interp((x0 + x1) / 2, FD["x"], FD["y_sh"]))
        for k, v, ev in (("mirror.x0", x0, "plan: mirror head start"), ("mirror.x1", x1, "plan: mirror head end"),
                         ("mirror.z0", float(z0), "front view: mirror head bottom"), ("mirror.z1", float(z1), "front view: mirror head top"),
                         ("mirror.y_out", y_out, "plan: mirror outer reach"), ("mirror.y_in", y_in, "body shoulder width at the mirror (derived)")):
            _P(doc, k, rel=scaled(v), evidence=[ev])
        _P(doc, "mirror.stalk", rel={"kind": "linear", "terms": [["mirror.y_out", 0.3], ["mirror.y_in", -0.3]], "const": 0.0},
           prov="inferred", note="stalk length: 30 % of the reach beyond the body")
        _P(doc, "mirror.embed", value=15.0, prov="assumed", note="stalk embedded into the door")
        feats.append({"id": "mirror_r.housing", "op": "mirror_housing", "inputs": [], "component": "mirror_r",
                      "label": "Mirror R: 3-section loft housing + stalk",
                      "params": {k: _ref(f"mirror.{k}") for k in ("x0", "x1", "z0", "z1", "y_out", "y_in", "stalk", "embed")}})
        feats.append({"id": "mirror_l.housing", "op": "mirror_copy", "inputs": ["mirror_r.housing"], "params": {"of": "mirror_r.housing"},
                      "component": "mirror_l", "label": "Mirror L (mirror of R)"})
        for side in ("r", "l"):
            comps.append({"id": f"mirror_{side}", "name": f"Mirror {'right' if side == 'r' else 'left'}", "kind": "mirror", "role": "body",
                          "output": f"mirror_{side}.housing", "material": "paint", "colour": "#b9c3cf", "parent": None})
            doc["joints"].append({"id": f"j.mirror_{side}", "type": "fixed", "a": "body", "b": f"mirror_{side}", "note": "stalk into the door"})
        assume("A-10", "Mirror head shape between the measured box (plan x-range and reach, front-view height) is a rounded "
                       "3-section loft; stalk position and diameter are inferred.", "inferred", ["mirrors"], ["mirror.*"])

    doc["components"] = comps
    doc["ai"] = {"S2_sam": s2, "S6_transitions": s6, "S7_ambiguities": s7}
    doc["shape_hypothesis"] = shape
    return doc
