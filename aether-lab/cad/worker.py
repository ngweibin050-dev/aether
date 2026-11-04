"""AETHER CAD worker: a long-lived process in the isolated Python 3.12 CAD environment (OpenCascade via OCP).

Protocol: one JSON request per line on stdin -> one JSON response per line on stdout:
  {"id": n, "cmd": "...", "args": {...}}  ->  {"id": n, "ok": true, "result": {...}} | {"id": n, "ok": false, "error": "..."}
Log lines go to stderr. The worker keeps the open document and its B-rep cache in memory, so a parameter edit only
rebuilds the features that depend on it.

Commands
  ping                                       -> versions
  build {sheet, out_dir, decisions?, ai_mode?, stored_from?}
                                             -> full pipeline (stages 1-5); document saved as out_dir/model.aethercad
  open {path, out_dir}                       -> load a document, recompute it with REPLAYED model answers
  document {}                                -> feature tree, parameters (value + provenance), components, status
  set_param {id, value?, clear_override?}    -> transactional edit + recompute + validation (rolled back on failure)
  meshes {}                                  -> per component: vertices, faces, normals (from the B-rep), edges
  export {kind: step|glb|aethercad|report}   -> writes the file in out_dir and returns its path (STEP only if valid)
  finalize {}                                -> validation with interference, STEP round trip, GLB, reprojection
"""
from __future__ import annotations

import json
import os
import sys
import re
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

STATE = {"doc": None, "res": None, "out_dir": None, "sheet": None}


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def cmd_ping(a):
    import OCP
    import cadquery
    return {"python": sys.version.split()[0], "cadquery": cadquery.__version__, "ocp": getattr(OCP, "__version__", "?"),
            "pid": os.getpid()}


def _save(doc, out_dir):
    from OCP.BRepTools import BRepTools
    os.makedirs(f"{out_dir}/brep", exist_ok=True)
    doc.save(f"{out_dir}/model.aethercad")
    for c in doc.data["components"]:
        if not c.get("group") and c["output"] in doc.shapes:
            BRepTools.Write_s(doc.shapes[c["output"]], f"{out_dir}/brep/{c['id']}.brep")


def cmd_build(a):
    from cad import pipeline as P
    stored = None
    if a.get("stored_from"):
        with open(a["stored_from"], encoding="utf-8") as f:
            stored = json.load(f).get("hypotheses")
    out = a["out_dir"]
    doc, res = P.build(a["sheet"], out, decisions=a.get("decisions"), ai_mode=a.get("ai_mode", "live"), stored=stored, log=_log,
                       defer_detail=bool(a.get("defer_detail")))
    STATE.update(doc=doc, res=res, out_dir=out, sheet=a["sheet"])
    fin = a.get("finalize", "full")
    rep = None
    if fin == "now":                                   # synchronous, everything included (the tests use this)
        rep = P.finalize(doc, res, out, log=_log, ai_mode=a.get("ai_mode", "live"))
    elif fin == "defer":                               # fast path: model + meshes now, validation right after
        rep = P.finalize(doc, res, out, log=_log, ai_mode=a.get("ai_mode", "live"),
                         s8=a.get("s8", True), skip_step_roundtrip=True)
    _save(doc, out)
    return {"status": doc.data["status"], "maturity": doc.data["maturity"], "out_dir": out,
            "report": _brief(rep) if rep else None, "seconds": res["seconds"],
            "finalize": fin, "step_roundtrip": ("full" if fin == "now" else "deferred")}


def cmd_step_roundtrip(a):
    """The deferred STEP round trip, run on demand (export / maturity promotion). Writes model.step + brep/ and the
    comparison into the current out_dir; returns the round-trip result and updates the document's validation."""
    from cad import export as EX
    from cad import pipeline as P
    doc = _need()
    if doc.data["status"].get("state") != "ok" or doc.stale:
        raise RuntimeError("STEP round trip blocked: the document is not in a valid, recomputed state")
    val = P.assembly_validation(doc, interference=True)
    if not val["all_valid"]:
        raise RuntimeError("STEP round trip blocked: " + json.dumps(
            [k for k, v in val["components"].items() if not v.get("valid")]
            + [i for i in val["interference"] if i.get("status") == "INTERFERENCE"])[:400])
    comps = P.components_for_export(doc)
    out = STATE["out_dir"]
    os.makedirs(os.path.join(out, "brep"), exist_ok=True)
    rt = EX.roundtrip([c for c in comps if not c.get("group")], os.path.join(out, "model.step"),
                      os.path.join(out, "brep"))
    doc.data["validation"] = {**doc.data.get("validation", {}),
                              "summary": {**doc.data.get("validation", {}).get("summary", {}),
                                          "step_roundtrip_pass": rt["all_pass"],
                                          "step_roundtrip_deferred": False}}
    if rt["all_pass"] and doc.data["validation"]["summary"].get("reprojection_iou") and \
            all(v >= 0.9 for v in doc.data["validation"]["summary"]["reprojection_iou"].values()):
        doc.data["maturity"] = "drawing_consistent"
    _save(doc, out)
    return {"step_roundtrip": {"all_pass": rt["all_pass"], "components": {k: {"pass": v.get("pass")}
                                                                          for k, v in rt["components"].items()}},
            "maturity": doc.data["maturity"]}


def cmd_open(a):
    """Open a saved document: the observations / views are re-measured from its source sheet (needed for
    reprojection) and the features recompute from the document itself; no model is called."""
    from cad import observations as O
    from cad import vehicle as Vh
    from cad.document import Document
    from cad.ops import OPS
    with open(a["path"], encoding="utf-8") as f:
        data = json.load(f)
    doc = Document(data, OPS)
    st = doc.recompute(validate=_fast_validate)
    res = None
    if a.get("sheet"):
        obs, aux = O.observe(a["sheet"])
        F = Vh.frames(obs, doc.data["decisions"])
        res = {"obs": obs, "aux": aux, "F": F}
    STATE.update(doc=doc, res=res, out_dir=a.get("out_dir") or os.path.dirname(a["path"]), sheet=a.get("sheet"))
    return {"status": st}


def _fast_validate(doc):
    from cad import pipeline as P
    return P.assembly_validation(doc, interference=False)


def _need():
    if STATE["doc"] is None:
        raise RuntimeError("no document open: build or open one first")
    return STATE["doc"]


def cmd_document(a):
    doc = _need()
    d = doc.data
    PV = doc.param_values()
    params = []
    for pid, p in d["parameters"].items():
        params.append({"id": pid, "value": PV[pid], "unit": p.get("unit"), "provenance": p["provenance"],
                       "kind": "override" if "override" in p else ("relation:" + p["rel"]["kind"]) if "rel" in p else "value",
                       "note": p.get("note"), "evidence": p.get("evidence"), "range": p.get("range")})
    feats = [{"id": f["id"], "op": f["op"], "label": f.get("label"), "status": f.get("status"), "error": f.get("error"),
              "inputs": f.get("inputs", []), "component": f.get("component"),
              "params": sorted({v["$p"] for v in _refs(f.get("params", {}))})} for f in d["features"]]
    return {"title": d["title"], "document_id": d["document_id"], "maturity": d["maturity"], "status": d["status"],
            "stale": doc.stale, "components": d["components"], "joints": d["joints"], "features": feats,
            "parameters": params, "assumptions": d["assumptions"], "decisions": d["decisions"],
            "history": d["history"][-30:], "validation": d.get("validation")}


def _refs(v):
    if isinstance(v, dict):
        if set(v) == {"$p"}:
            yield v
            return
        for x in v.values():
            yield from _refs(x)
    elif isinstance(v, list):
        for x in v:
            yield from _refs(x)


def cmd_set_param(a):
    doc = _need()
    t = time.time()
    st = doc.set_param(a["id"], a.get("value"), clear_override=a.get("clear_override", False), validate=_fast_validate,
                       note=a.get("note"))
    if st["state"] == "ok":
        _save(doc, STATE["out_dir"])
    return {"status": st, "seconds": round(time.time() - t, 2), "document_status": doc.data["status"]}


def cmd_program_build(a):
    """AI-written CAD program (cad/codegen.py): from a drawing, a description, or a change to an existing program.
    The result is a new program version in its own folder; a failed build leaves every earlier version untouched."""
    from cad import codegen as G
    rep = G.build(a.get("sheet"), a["out_dir"], request=a.get("request") or "", rounds=int(a.get("rounds", 4)),
                  base_program=a.get("base_program"), base_length_mm=a.get("base_length_mm"), log=_log)
    out = {k: rep.get(k) for k in ("seconds", "best", "edit")}
    out["rounds"] = [{k: r.get(k) for k in ("round", "error", "iou", "mean_iou", "invalid", "object", "model_s", "run_s")}
                     | {"parts": len(r.get("parts") or [])} for r in rep["rounds"]]
    if rep.get("best"):
        out["meshes"] = cmd_program_meshes({"report": os.path.join(a["out_dir"], "report.json")})["meshes"]
    return out


def cmd_program_meshes(a):
    """Display meshes of a program model's kept parts (tessellated from their B-rep files)."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS_Shape
    from cad import tessellate as T
    rep = json.load(open(a["report"], encoding="utf-8"))
    out = {}
    for p in rep["best"]["parts"]:
        sh = TopoDS_Shape()
        BRepTools.Read_s(sh, p["brep"], BRep_Builder())
        V, F, N, fid = T.mesh(sh, 1.0, 0.25)
        E = T.edges(sh)
        out[p["id"]] = {"name": p["name"], "kind": "program_part", "parent": None, "colour": p["colour"],
                        "material": p["material"], "v": V.round(3).ravel().tolist(), "f": F.ravel().tolist(),
                        "n": N.round(4).ravel().tolist(), "l": E.round(3).ravel().tolist(), "brep": p["brep"]}
    return {"meshes": out}


def cmd_meshes(a):
    from cad import tessellate as T
    doc = _need()
    out = {}
    for c in doc.data["components"]:
        if c.get("group") or c["output"] not in doc.shapes:
            continue
        shp = doc.shapes[c["output"]]
        lin = a.get("linear", 1.5 if c["kind"] == "body_shell" else 0.5)      # display chord error (mm); the B-rep is exact
        V, F, N, fid = T.mesh(shp, lin, a.get("angular", 0.25))
        E = T.edges(shp)
        out[c["id"]] = {"name": c["name"], "kind": c["kind"], "parent": c.get("parent"), "colour": c.get("colour"),
                        "material": c.get("material"), "v": V.round(3).ravel().tolist(), "f": F.ravel().tolist(),
                        "n": N.round(4).ravel().tolist(), "l": E.round(3).ravel().tolist()}
        if c["kind"] == "body_shell":                    # named regions (glass = windows, light = lamps) per triangle
            from cad import pipeline as P
            fm = P.face_materials(doc, shp)
            names = sorted({m for m in fm if m})
            if names:
                idx = {m: k + 1 for k, m in enumerate(names)}
                out[c["id"]]["region_names"] = names
                out[c["id"]]["r"] = [idx.get(fm[int(k)], 0) if fm[int(k)] else 0 for k in fid]
    groups = [{"id": c["id"], "name": c["name"], "kind": c["kind"]} for c in doc.data["components"] if c.get("group")]
    return {"meshes": out, "groups": groups, "stale": doc.stale, "status": doc.data["status"]}


def cmd_export(a):
    from cad import export as EX
    from cad import pipeline as P
    doc = _need()
    out = STATE["out_dir"]
    kind = a["kind"]
    if kind == "aethercad":
        doc.save(f"{out}/model.aethercad")
        return {"path": f"{out}/model.aethercad"}
    if doc.data["status"].get("state") != "ok" or doc.stale:
        raise RuntimeError("export blocked: the document is not in a valid, recomputed state")
    comps = P.components_for_export(doc)
    if kind == "glb":
        with open(f"{out}/model.glb", "wb") as f:
            f.write(EX.glb(comps, {"maturity": doc.data["maturity"]}))
        return {"path": f"{out}/model.glb"}
    if kind == "step":
        val = P.assembly_validation(doc, interference=True)
        if not val["all_valid"]:
            raise RuntimeError("STEP export blocked: " + json.dumps([k for k, v in val["components"].items() if not v.get("valid")]
                                                                      + [i for i in val["interference"] if i.get("status") == "INTERFERENCE"])[:400])
        EX.write_step([c for c in comps if not c.get("group")], f"{out}/model.step")
        return {"path": f"{out}/model.step"}
    if kind == "report":
        return {"path": f"{out}/report.json"}
    raise RuntimeError(f"unknown export kind {kind!r}")


def cmd_finalize(a):
    from cad import pipeline as P
    doc = _need()
    if STATE["res"] is None:
        raise RuntimeError("finalize needs the source sheet (open with sheet=...)")
    rep = P.finalize(doc, STATE["res"], STATE["out_dir"], log=_log, ai_mode=a.get("ai_mode", "replay"))
    _save(doc, STATE["out_dir"])
    return {"report": _brief(rep)}


def _brief(rep):
    if not rep:
        return None
    return {"maturity": rep.get("maturity_reached"), "provenance_counts": rep.get("provenance_counts"),
            "all_valid": rep.get("validation", {}).get("all_valid"),
            "step_all_pass": rep.get("step_roundtrip", {}).get("all_pass"),
            "reprojection_iou": {k: v["iou"] for k, v in (rep.get("reprojection") or {}).items()},
            "recompute_failed": rep.get("recompute_failed")}


ASM = {"shapes": None, "local": None, "report": None, "parts": None, "out_dir": None, "step": None}


def cmd_asm_build(a):
    """The scene's mechanical parts -> B-rep solids (cad/assembly.py): validation, contacts, mates, explode vectors,
    and per part the B-rep tessellation in the part's own frame (what the viewport draws)."""
    from cad import assembly as A
    from cad import tessellate as T
    import hashlib
    import numpy as np
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS_Shape
    parts = a["parts"]
    # cache by what the solids depend on: each part's type, parameters and pose, and the builder's own source
    with open(A.__file__, "rb") as f:
        code = hashlib.sha1(f.read()).hexdigest()
    if ASM.get("code") not in (None, code):              # the builder's source changed while this worker ran
        import importlib
        A = importlib.reload(A)
    ASM["code"] = code
    key = hashlib.sha1(json.dumps([code] + [[p["id"], p["type"], p.get("params"), p.get("position"), p.get("rotation"),
                                             p.get("scale"), p.get("parent"), p.get("eng")] for p in parts],
                                  sort_keys=True, default=str).encode()).hexdigest()[:16]
    cdir = os.path.join(a["out_dir"], "cache", key)
    if os.path.isfile(os.path.join(cdir, "result.json")) and not a.get("force"):
        with open(os.path.join(cdir, "result.json"), encoding="utf-8") as f:
            res = json.load(f)
        shapes = {}
        for i in res["records"]:
            fp = os.path.join(cdir, "brep", i + ".brep")
            if os.path.isfile(fp):
                s = TopoDS_Shape()
                BRepTools.Read_s(s, fp, BRep_Builder())
                shapes[i] = s
        ASM.update(shapes=shapes, local=None, report={k: v for k, v in res.items() if k != "meshes"},
                   parts={p["id"]: p for p in parts}, out_dir=a["out_dir"], step=None)
        res["cached"] = key
        return res
    shapes, local, rep = A.analyse(parts, log=_log)
    meshes = {}
    for i, s in local.items():
        bb = np.array(A.Vd.bbox(s))
        lin = float(np.clip(np.max(bb[3:] - bb[:3]) / 400, 0.01, 0.5))
        ang = 0.2
        r = rep["records"][i]
        if r["type"] == "coil":                         # a helix sweep: chord error relative to the wire, not the coil
            lin, ang = max(lin, 0.15 * float(r["params"].get("wire", 1.0))), 0.45
        V, F, N, _ = T.mesh(s, lin, ang)
        E = T.edges(s, deflection=0.2)
        meshes[i] = {"v": V.round(4).ravel().tolist(), "f": F.ravel().tolist(), "n": N.round(4).ravel().tolist(),
                     "l": E.round(4).ravel().tolist()}
    ASM.update(shapes=shapes, local=local, report=rep, parts={p["id"]: p for p in parts}, out_dir=a["out_dir"], step=None)
    os.makedirs(os.path.join(cdir, "brep"), exist_ok=True)
    with open(os.path.join(a["out_dir"], "assembly_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, default=_default, indent=1)
    for i, s in shapes.items():
        BRepTools.Write_s(s, os.path.join(cdir, "brep", i + ".brep"))
    res = {**rep, "meshes": meshes}
    with open(os.path.join(cdir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, default=_default)
    return {**res, "cached": None}


def cmd_asm_step(a):
    """STEP (AP214) of every VALID solid under its sub-assembly, written now (download right away); the round trip
    (re-read and compared in a fresh process) runs in the background: cmd_asm_step_status reports it. Parts that were
    not built or failed validation are left out and listed."""
    import threading
    from cad import assembly as A
    if ASM["shapes"] is None:
        raise RuntimeError("no B-rep assembly: build it first")
    rec = ASM["report"]["records"]
    comps = {i: {"name": rec[i]["name"], "shape": s, "colour": ASM["parts"][i].get("color")}
             for i, s in ASM["shapes"].items() if rec[i].get("validation", {}).get("valid")}
    left_out = [{"id": i, "name": r["name"], "why": r.get("reason") or "failed B-rep validation"}
                for i, r in rec.items() if i not in comps]
    out = ASM["out_dir"]
    path = os.path.join(out, "assembly.step")
    brep_dir = os.path.join(out, "assembly_brep")
    t = time.time()
    A.write_step_and_breps(comps, ASM["report"]["groups"], path, brep_dir)
    step = {"path": path, "bytes": os.path.getsize(path), "parts": len(comps), "left_out": left_out,
            "write_seconds": round(time.time() - t, 1), "roundtrip": "running", "roundtrip_all_pass": None,
            "missing": [], "components": {}}
    ASM["step"] = step

    def verify():
        t0 = time.time()
        try:
            rt = A.verify_step(path, brep_dir, list(comps))
            step.update(roundtrip="done", roundtrip_all_pass=rt["all_pass"], missing=rt["missing"],
                        seconds=round(time.time() - t0, 1),
                        components={k: {kk: v.get(kk) for kk in ("pass", "volume_rel_diff", "area_rel_diff", "bbox_diff_mm",
                                                                 "tolerance_used_mm", "dist_orig_to_reimport_mm")}
                                    for k, v in rt["components"].items()})
        except Exception as e:
            step.update(roundtrip="failed", roundtrip_all_pass=False, error=f"{type(e).__name__}: {e}"[:400])
    threading.Thread(target=verify, daemon=True).start()
    return step


def cmd_asm_step_status(a):
    return ASM["step"] or {}


def cmd_asm_section(a):
    from cad import assembly as A
    import numpy as np
    if ASM["shapes"] is None:
        raise RuntimeError("no B-rep assembly: build it first")
    k = float(ASM["report"].get("model_scale") or 1.0)          # the viewport cuts in display mm
    cut = A.section(ASM["shapes"], a["axis"], float(a["offset"]) / k, bool(a.get("flip")))
    rec = ASM["report"]["records"]
    out = {}
    for i, c in cut.items():
        M = np.asarray(rec[i]["matrix"])
        Mi = np.linalg.inv(M)
        P = c["cap"] @ Mi[:3, :3].T + Mi[:3, 3]           # back into the part's own frame (explode / transforms apply)
        out[i] = {"name": rec[i]["name"], "area_mm2": c["area_mm2"], "cap": P.round(4).ravel().tolist()}
    return {"axis": a["axis"], "offset": float(a["offset"]), "flip": bool(a.get("flip")), "parts": out}


def _scene_shapes(parts, cad_brep_dir):
    """Scene parts -> exact solids in model mm: parametric parts built by cad/assembly.py, CAD-document parts read from
    their saved .brep (placed like the scene places them, without the display scale). Mesh parts have no B-rep."""
    from cad import assembly as A
    from engine import geometry as G
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS_Shape
    import numpy as np
    shapes, names, left_out = {}, {}, []
    built, _, rec = A.build([p for p in parts if p["type"] != "cad"], log=_log)
    for i, s in built.items():
        shapes[i], names[i] = s, rec[i]["name"]
    for i, r in rec.items():
        if not r.get("built") and r["type"] != "group":
            left_out.append({"name": r["name"], "why": r.get("reason")})
    by = {p["id"]: p for p in parts}
    for p in parts:
        if p["type"] != "cad":
            continue
        cid = (p.get("eng") or {}).get("cad_component")
        f = (p.get("eng") or {}).get("brep") or os.path.join(cad_brep_dir, f"{cid}.brep")   # program parts: own file
        if not cid or not os.path.isfile(f):
            left_out.append({"name": p["name"], "why": "its CAD document's B-rep is not on disk"})
            continue
        s = TopoDS_Shape()
        BRepTools.Read_s(s, f, BRep_Builder())
        M = G.world_matrix(p, by)
        par = by.get(p.get("parent"))
        root = par
        while root is not None and by.get(root.get("parent")) is not None:
            root = by[root["parent"]]
        ds = float(np.cbrt(abs(np.linalg.det(G.world_matrix(root, by)[:3, :3])))) if root else 1.0
        M[:3, :] /= ds or 1.0
        shapes[p["id"]], names[p["id"]] = A._apply(s, M), p["name"]
    return shapes, names, left_out


def cmd_export_parts(a):
    """{parts, kind: step|drawing, path, cad_brep_dir, title} -> a STEP of the parts' exact solids, or a technical
    drawing (cad/drawing.py: SVG + PDF + PNG)."""
    from cad import assembly as A
    shapes, names, left_out = _scene_shapes(a["parts"], a.get("cad_brep_dir") or "")
    if not shapes:
        raise RuntimeError("none of these parts has an exact B-rep (imported meshes cannot be exported as STEP or drawn)")
    if a["kind"] == "step":
        comps = {i: {"name": names[i], "shape": s, "colour": next((p.get("color") for p in a["parts"] if p["id"] == i), None)}
                 for i, s in shapes.items()}
        A.write_step_tree(comps, [{"id": "model", "name": a.get("title") or "model", "parts": list(comps)}], a["path"],
                          title=a.get("title") or "AETHER_MODEL")
        return {"path": a["path"], "solids": len(comps), "left_out": left_out}
    if a["kind"] == "drawing":
        from cad import drawing as D
        notes = [f"{len(left_out)} part(s) without exact B-rep not drawn"] if left_out else []
        r = D.draw(list(shapes.values()), a.get("title") or "AETHER model", a["path"], notes)
        return {**r, "solids": len(shapes), "left_out": left_out}
    raise RuntimeError(f"unknown export kind {a['kind']}")


def cmd_import_step(a):
    """A STEP file -> one CAD part per solid (tessellated from the B-rep it holds), for the scene."""
    from cad import export as EX
    from cad import tessellate as T
    import numpy as np
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    try:
        named = EX.read_step(a["path"])
    except Exception:
        named = {}
    if not named:
        r = STEPControl_Reader()
        if r.ReadFile(a["path"]) != IFSelect_RetDone:
            raise RuntimeError("STEP read failed")
        r.TransferRoots()
        shp = r.OneShape()
        ex = TopExp_Explorer(shp, TopAbs_SOLID)
        k = 0
        while ex.More():
            named[f"solid_{k}"] = ex.Current()
            k += 1
            ex.Next()
    meshes = {}
    for i, (nm, s) in enumerate(named.items()):
        bb = np.array(A_bbox(s))
        lin = float(np.clip(np.max(bb[3:] - bb[:3]) / 300, 0.02, 1.0))
        V, F, N, _ = T.mesh(s, lin, 0.3)
        if not len(F):
            continue
        meshes[f"s{i}"] = {"name": nm, "kind": "imported solid", "parent": None, "colour": None, "material": None,
                           "v": V.round(4).ravel().tolist(), "f": F.ravel().tolist(), "n": N.round(4).ravel().tolist(),
                           "l": T.edges(s).round(4).ravel().tolist()}
    return {"meshes": meshes, "groups": [], "document_id": "step:" + os.path.basename(a["path"])}


def A_bbox(s):
    from cad import validate as Vd
    return Vd.bbox(s)


def cmd_detail(a):
    """The detail pass of a progressive build: a full recompute (the core features come from the cache, only the
    deferred pockets / imprints are built), then saved. Returns which details were built or skipped."""
    from cad import pipeline as P
    doc = _need()
    t = time.time()
    s5 = None
    dfr = (STATE.get("res") or {}).pop("deferred_s5", None)
    if dfr:                                              # the section shape: Muse Wonder's hypotheses vs the default
        try:
            best, cands = dfr["run"]()
            s5 = {"chosen": best["name"], "scores": {c["name"]: c.get("score_mean_iou") for c in cands}}
            gain = best["score_mean_iou"] - next(c["score_mean_iou"] for c in cands if c["source"] == "assumed")
            s5["gain"] = round(gain, 4)
            if best["source"] != "assumed" and gain >= 0.005:      # a re-plan rebuilds everything: only for a real gain
                doc2 = dfr["replan"](best["shape"], best["name"], best["source"])
                st2 = doc2.recompute(validate=_fast_validate, defer_detail=False)
                if st2["state"] == "ok":
                    STATE["doc"] = doc = doc2
                    s5["replanned"] = True
        except Exception as e:
            s5 = {"error": f"{type(e).__name__}: {e}"[:300]}
    st = doc.recompute(validate=_fast_validate)
    if st["state"] == "ok":
        _save(doc, STATE["out_dir"])
    det = [{"id": f["id"], "label": f.get("label"), "status": f.get("status")} for f in doc.data["features"]
           if f["op"] in doc.DETAIL_OPS]
    return {"status": st, "details": det, "section_shape": s5, "seconds": round(time.time() - t, 1)}


def cmd_add_feature(a):
    """Features the assistant adds to the BODY of the open document (refining a model), all in ONE recompute (each
    recompute of a car body costs a minute or two): an imprint (an outline split into the surface, a named region the
    viewer can colour: lamp, plate, door line) or a pocket (a recess `depth_mm` deep: grille, intake, plate recess).
    a["features"]: [{op, view, polygons, region, material?, depth_mm?}]; an outline is a polygon in the view plane in
    model mm (side: (x, z), top: (x, y), front / rear: (y, z)). The features are optional: one that cannot be built
    within the validity rules is skipped (status failed_optional), then taken out of the document and reported, so
    the others still land. They go after the body's current last feature; the body component outputs the last one."""
    doc = _need()
    if a.get("document_id") and a["document_id"] != doc.data["document_id"]:
        raise RuntimeError("that model's CAD document is not the one open in the CAD worker (only the latest CAD model "
                           "can take CAD features); add a part with attach instead")
    body = next((c for c in doc.data["components"] if c["kind"] == "body_shell"), None)
    if body is None:
        raise RuntimeError("this CAD document has no body to add a feature to")
    specs = a.get("features") or [a]
    has_skin = any(f["id"] == "body.skin" for f in doc.data["features"])
    first_last = body["output"]
    i = next(k for k, f in enumerate(doc.data["features"]) if f["id"] == first_last) + 1
    # numbered after the highest one there (one taken out by an undo must not hand its number to a new one)
    n = max([int(m.group(1)) for f in doc.data["features"] if f.get("ai")
             for m in [re.match(r"body\.ai(\d+)_", f["id"])] if m] or [0])
    added = []
    for sp in specs:
        op, view = sp["op"], sp["view"]
        if op not in ("imprint", "pocket"):
            raise ValueError("op must be imprint or pocket")
        if view not in ("side", "top", "front", "rear"):
            raise ValueError("view must be side, top, front or rear")
        polys = [[[float(x), float(y)] for x, y in poly] for poly in sp["polygons"]]
        if not polys or any(len(q) < 3 for q in polys):
            raise ValueError("each outline needs at least 3 points")
        n += 1
        region = str(sp.get("region") or f"detail {n}").strip().lower()[:40]
        oid = f"obs.ai.{n}"
        doc.data["observations"][oid] = {"kind": "region_outlines", "class": "assistant", "view": view, "data": polys,
                                         "note": f"outline drawn by the assistant for '{region}' (refinement), model mm"}
        params = {"view": view, "polygons": {"$obs": oid}, "scale": 1.0, "name": region, "region": region,
                  "defer_si": True}
        if op == "pocket":
            params["depth"] = float(sp.get("depth_mm") or 5.0)
        else:
            params["material"] = sp.get("material") or "panel"
        fid = f"body.ai{n}_{op}"
        feat = {"id": fid, "op": f"{op}_projection", "inputs": [body["output"]] + (["body.skin"] if op == "pocket" and has_skin else []),
                "params": params, "component": "body", "optional": True, "ai": True,
                "label": f"{'Imprint' if op == 'imprint' else 'Pocket'}: {region} (assistant, {view} view)",
                "region": {"kind": region, "view": view, "material": params.get("material")}}
        doc.data["features"].insert(i, feat)
        i += 1
        body["output"] = fid
        added.append((feat, oid))
    t = time.time()
    st = doc.recompute(validate=_fast_validate)
    failed = [(f, o) for f, o in added if f.get("status") != "ok"]
    if failed or st["state"] != "ok":                    # take the ones that did not build out, rebuild without them
        drop = {f["id"] for f, _ in failed} if st["state"] == "ok" else {f["id"] for f, _ in added}
        for f, o in added:
            if f["id"] in drop:
                doc.data["features"].remove(f)
                doc.data["observations"].pop(o, None)
        prev = first_last
        for f, _ in added:                               # re-chain the ones that stay
            if f["id"] not in drop:
                f["inputs"][0] = prev
                prev = f["id"]
        body["output"] = prev
        st = doc.recompute(validate=_fast_validate)
    ok = [f for f, _ in added if f in doc.data["features"]]
    si_s = None
    if ok and st["state"] == "ok":
        # the self-intersection check, once for the whole batch on the finished body; faulty -> the batch is taken out
        from cad.validate import _argument_analysis
        t1 = time.time()
        si = _argument_analysis(doc.shapes[body["output"]])
        si_s = round(time.time() - t1, 1)
        if si["faulty"]:
            for f, o in added:
                if f in doc.data["features"]:
                    doc.data["features"].remove(f)
                    doc.data["observations"].pop(o, None)
                    f["status"], f["error"] = "failed_optional", "self-intersecting body after the batch: " + str(si.get("faults"))[:200]
            body["output"] = first_last
            st = doc.recompute(validate=_fast_validate)
            ok = []
    if ok and st["state"] == "ok":
        _save(doc, STATE["out_dir"])
    return {"ok": bool(ok) and st["state"] == "ok", "seconds": round(time.time() - t, 1), "check_seconds": si_s,
            "added": [{"feature": f["id"], "region": f["params"]["region"], "label": f["label"],
                       **{k: v for k, v in (doc.info.get(f["id"]) or {}).items() if k in ("outline_inset_mm", "depth_mm")}}
                      for f in ok],
            "failed": [{"region": f["params"]["region"], "error": (f.get("error") or st.get("message") or "")[:400]}
                       for f, _ in added if f not in ok]}

def cmd_remove_features(a):
    """Take features the assistant added out of the open document again (an undo in the app), in one recompute: the
    features after them are chained to what came before."""
    doc = _need()
    if a.get("document_id") and a["document_id"] != doc.data["document_id"]:
        return {"ok": False, "skipped": "another CAD document is open now"}
    feats = doc.data["features"]
    gone = [f for f in feats if f["id"] in set(a.get("ids") or []) and f.get("ai")]
    if not gone:
        return {"ok": True, "removed": []}
    sub = {f["id"]: f["inputs"][0] for f in gone}

    def back(x):
        while x in sub:
            x = sub[x]
        return x
    for f in feats:
        if f not in gone and f.get("inputs"):
            f["inputs"] = [back(x) for x in f["inputs"]]
    for c in doc.data["components"]:
        if c.get("output"):
            c["output"] = back(c["output"])
    for f in gone:
        feats.remove(f)
        doc.data["observations"].pop((f["params"].get("polygons") or {}).get("$obs"), None)
    t = time.time()
    st = doc.recompute(validate=_fast_validate)
    if st["state"] == "ok":
        _save(doc, STATE["out_dir"])
    return {"ok": st["state"] == "ok", "removed": [f["id"] for f in gone], "seconds": round(time.time() - t, 1)}


CMDS = {"program_build": cmd_program_build, "program_meshes": cmd_program_meshes, "ping": cmd_ping, "add_feature": cmd_add_feature, "remove_features": cmd_remove_features, "detail": cmd_detail, "export_parts": cmd_export_parts, "import_step": cmd_import_step, "build": cmd_build, "open": cmd_open, "document": cmd_document, "set_param": cmd_set_param,
        "meshes": cmd_meshes, "export": cmd_export, "finalize": cmd_finalize, "asm_build": cmd_asm_build,
        "asm_step": cmd_asm_step, "asm_step_status": cmd_asm_step_status, "asm_section": cmd_asm_section}


def main():
    # the protocol gets a private copy of the real stdout; file descriptor 1 is pointed at stderr, because OpenCascade's
    # C++ code (STEP writer statistics) prints straight to fd 1 and would corrupt the JSON lines
    proto = os.dup(1)
    os.dup2(2, 1)
    out = os.fdopen(proto, "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = CMDS[req["cmd"]](req.get("args") or {})
            msg = {"id": req.get("id"), "ok": True, "result": res}
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            msg = {"id": (req or {}).get("id") if isinstance(locals().get("req"), dict) else None, "ok": False,
                   "error": f"{type(e).__name__}: {e}"[:2000]}
        out.write(json.dumps(msg, default=_default) + "\n")
        out.flush()


def _default(o):
    import numpy as np
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer, np.bool_)):
        return o.item()
    return str(o)


if __name__ == "__main__":
    main()
