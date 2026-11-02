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
  import_step {path, out_dir, name?}         -> external STEP -> validated B-rep solids as a "step_import" document

Failure integrity: build and import_step work in a staging folder; the open document (and out_dir) are replaced only
when the new document recomputed and validated. Worker-side failures preserve the last document. A subsequent server-side
scene-import failure can still leave document and scene out of sync; see the Phase 0/A report.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
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


def _swap_in(staging, out):
    """Make the staging folder the document folder (only after a valid build)."""
    old = out + ".previous"
    shutil.rmtree(old, ignore_errors=True)
    if os.path.exists(out):
        os.replace(out, old)
    try:
        os.replace(staging, out)
    except Exception:
        if os.path.exists(old) and not os.path.exists(out):
            os.replace(old, out)
        raise
    shutil.rmtree(old, ignore_errors=True)


def _staging(out):
    st = out + ".staging"
    shutil.rmtree(st, ignore_errors=True)
    os.makedirs(st)
    return st


def _unresolved_view_status(doc):
    front = doc.data.get("decisions", {}).get("front_view", {})
    if isinstance(front, dict) and front.get("provenance") == "unresolved":
        return {"state": "invalid", "error": "Front/rear view interpretation is unresolved; confirm the front view before building"}
    return None


def cmd_build(a):
    from cad import pipeline as P
    stored = None
    if a.get("stored_from"):
        with open(a["stored_from"], encoding="utf-8") as f:
            stored = json.load(f).get("hypotheses")
    out = os.path.abspath(a["out_dir"])
    st = _staging(out)
    sheet = os.path.join(st, "sheet" + os.path.splitext(a["sheet"])[1])
    shutil.copyfile(a["sheet"], sheet)
    doc, res = P.build(sheet, st, decisions=a.get("decisions"), ai_mode=a.get("ai_mode", "live"), stored=stored, log=_log)
    if doc.data["status"].get("state") != "ok":            # the last valid document stays open, nothing is swapped in
        doc.save(f"{st}/failed.aethercad")
        return {"status": doc.data["status"], "maturity": doc.data["maturity"], "kept_previous_document": True,
                "failed_document": f"{st}/failed.aethercad", "seconds": res["seconds"]}
    # Valid topology does not resolve failed drawing interpretation. Never publish
    # the pipeline's placeholder front/rear choice as a successful reconstruction.
    if status := _unresolved_view_status(doc):
        return {"status": status, "maturity": doc.data["maturity"], "kept_previous_document": True, "seconds": res["seconds"]}
    rep = P.finalize(doc, res, st, log=_log, ai_mode=a.get("ai_mode", "live")) if a.get("finalize", True) else None
    if rep and (not rep.get("validation", {}).get("all_valid") or not rep.get("step_roundtrip", {}).get("all_pass")):
        return {"status": {"state": "invalid", "error": "Full validation or STEP round-trip failed"},
                "maturity": doc.data["maturity"], "kept_previous_document": True,
                "report": _brief(rep), "seconds": res["seconds"]}
    _save(doc, st)
    _swap_in(st, out)
    STATE.update(doc=doc, res=res, out_dir=out, sheet=os.path.join(out, os.path.basename(sheet)))
    return {"status": doc.data["status"], "maturity": doc.data["maturity"], "out_dir": out,
            "report": _brief(rep) if rep else None, "seconds": res["seconds"]}


def cmd_import_step(a):
    """An external STEP file -> a "step_import" document: one external_brep feature + component per solid. Every solid
    must pass cad/validate.check_solid; otherwise nothing is opened. No feature history is invented."""
    import hashlib
    from OCP.BRepTools import BRepTools
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from cad import validate as Vd
    from cad.document import Document
    from cad.ops import OPS
    src = a["path"]
    with open(src, "rb") as f:
        src_hash = hashlib.sha256(f.read()).hexdigest()
    r = STEPControl_Reader()
    if r.ReadFile(str(src)) != IFSelect_RetDone:
        raise RuntimeError("STEP import failed: the file could not be read as STEP")
    r.TransferRoots()
    shape = r.OneShape()
    solids = []
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        solids.append(ex.Current())
        ex.Next()
    if not solids:
        raise RuntimeError("STEP import failed: the file contains no solid (surfaces / meshes are not accepted)")
    checks = [Vd.check_solid(s_, f"solid_{i + 1}", argument_analysis=False) for i, s_ in enumerate(solids)]
    bad = [c["name"] for c in checks if not c["valid"]]
    if bad:
        raise RuntimeError(f"STEP import failed: invalid B-rep solid(s) {bad}; nothing was imported")
    out = os.path.abspath(a["out_dir"])
    st = _staging(out)
    os.makedirs(f"{st}/external", exist_ok=True)
    shutil.copyfile(src, f"{st}/source.step")
    name = (a.get("name") or "Imported STEP")[:80]
    data = Document.new({"file": os.path.basename(src), "sha256": src_hash, "format": "STEP"}, name, route="step_import")
    data["maturity"] = "geometrically_valid"
    data["assumptions"].append({"id": "external_geometry", "provenance": "external_reference",
                                "text": "Geometry imported from an external STEP file: genuine B-rep, but no AETHER feature "
                                        "history, parameters or design intent are known for it."})
    for i, s_ in enumerate(solids):
        fn = f"external/solid_{i + 1}.brep"
        BRepTools.Write_s(s_, f"{st}/{fn}")
        with open(f"{st}/{fn}", "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        fid = f"ext_{i + 1}"
        data["features"].append({"id": fid, "op": "external_brep", "label": f"External B-rep solid {i + 1} (imported STEP)",
                                 "params": {"brep_file": fn, "sha256": h}, "inputs": [], "component": f"solid_{i + 1}",
                                 "provenance": "external_reference"})
        data["components"].append({"id": f"solid_{i + 1}", "name": f"{name} solid {i + 1}", "kind": "external_brep",
                                   "output": fid, "colour": "#b9c2cc", "provenance": "external_reference"})
    doc = Document(data, OPS)
    doc.base_dir = st
    stt = doc.recompute(validate=_fast_validate)
    if stt["state"] != "ok":
        raise RuntimeError(f"STEP import failed: {stt.get('error') or stt}")
    doc.data["validation"] = {"import": checks}
    doc.save(f"{st}/model.aethercad")
    _swap_in(st, out)
    doc.base_dir = out
    STATE.update(doc=doc, res=None, out_dir=out, sheet=None)
    return {"status": doc.data["status"], "solids": len(solids), "source_sha256": src_hash, "route": "step_import",
            "checks": [{k: c.get(k) for k in ("name", "valid", "volume_mm3", "bbox_mm", "faces")} for c in checks]}


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
    doc.base_dir = os.path.dirname(os.path.abspath(a["path"]))
    if status := _unresolved_view_status(doc):
        return {"status": status, "kept_previous_document": True}
    st = doc.recompute(validate=_fast_validate)
    if st["state"] != "ok":                                # keep the last valid document open
        return {"status": st, "kept_previous_document": True}
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
    return {"title": d["title"], "document_id": d["document_id"], "route": d.get("route", "three_view"),
            "source": d.get("source"), "maturity": d["maturity"], "status": d["status"],
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


def cmd_meshes(a):
    from cad import tessellate as T
    doc = _need()
    out = {}
    for c in doc.data["components"]:
        if c.get("group") or c["output"] not in doc.shapes:
            continue
        shp = doc.shapes[c["output"]]
        lin = a.get("linear", 1.0 if c["kind"] == "body_shell" else 0.4)
        V, F, N, _ = T.mesh(shp, lin, a.get("angular", 0.25))
        E = T.edges(shp)
        out[c["id"]] = {"name": c["name"], "kind": c["kind"], "parent": c.get("parent"), "colour": c.get("colour"),
                        "material": c.get("material"), "v": V.round(3).ravel().tolist(), "f": F.ravel().tolist(),
                        "n": N.round(4).ravel().tolist(), "l": E.round(3).ravel().tolist()}
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


CMDS = {"ping": cmd_ping, "build": cmd_build, "open": cmd_open, "document": cmd_document, "set_param": cmd_set_param,
        "meshes": cmd_meshes, "export": cmd_export, "finalize": cmd_finalize, "import_step": cmd_import_step}


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
