"""Do AETHER's downloads open outside AETHER, with the right size? (independent check, no API)

    python -m tests.check_exports                 # writes the files + manifest, then loads them with trimesh
                                                  # in the isolated env output/.venv-eval (pip install trimesh lxml networkx)

1. Here: the GLB, STL and 3MF that the app's Export / the assistant's export_model produce (engine/export.py), for
   three models, at their real size: the CAD car (cad-car project), the drawing press rebuilt from US 929,594 (the recorded demo run) and a
   bracket of standard parts (ISO 4017 bolt, 6204 bearing). Our own numbers go in a manifest: triangles, size (mm).
2. In the isolated environment: tests/check_exports_load.py opens every file with trimesh alone (not our code) and
   compares triangles and size with the manifest. Results: output/exports_check/results.json.
STEP is checked by the CAD pipeline's own round trip (re-read in a fresh OpenCascade process: docs/archive/CAD_RESULTS.md)."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "exports_check"
EVAL_PY = ROOT / "output" / ".venv-eval" / "Scripts" / "python.exe"


def models():
    import assistant as A
    from engine import lab
    st = json.loads((ROOT / "output" / "projects" / "cad-car" / "project.json").read_text(encoding="utf-8"))["state"]
    lab.fold_cad_leaves(st)
    car = next(r for r in A.roots(st) if (r.get("eng") or {}).get("cad_document"))
    keep = {p["id"] for p in lab.subtree(st, car["id"]) if p["type"] == "group" or (p.get("eng") or {}).get("cad_document")}
    yield "cad_car", {**st, "parts": [p for p in st["parts"] if p["id"] in keep]}
    rec = json.loads((ROOT / "output" / "recorded" / "D.json").read_text(encoding="utf-8"))["state"]
    yield "drawing_press", rec
    st = lab.default_state()
    st["parts"] = []
    lab.build_assembly(st, "bracket", [
        {"name": "plate", "type": "rbox", "params": {"w": 100, "d": 60, "h": 10, "r": 1.5}},
        {"name": "bolt M8x30", "type": "hex_bolt", "params": {"size": "M8", "length": 30}, "position": [30, 0, 30]},
        {"name": "bearing 6204", "type": "ball_bearing", "params": {"designation": "6204"}, "position": [-20, 0, 20]}])
    yield "bracket", st


def main():
    from engine import export as ex
    from engine import geometry
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    import assistant as A
    for name, st in models():
        st = A._real_size(st)                        # what export_model writes: real size, not the desk's display size
        ms = [(V, F) for p, V, F in geometry.scene_meshes(st["parts"]) if p["type"] != "group" and len(F)]
        allV = np.vstack([V for V, _ in ms])
        manifest[name] = {"triangles": int(sum(len(F) for _, F in ms)), "parts": len(ms),
                          "size_mm": [round(float(x), 2) for x in allV.max(0) - allV.min(0)], "files": {}}
        for fmt, fn in (("glb", ex.glb), ("stl", ex.stl), ("3mf", ex.three_mf)):
            f = OUT / f"{name}.{fmt}"
            f.write_bytes(fn(st))
            manifest[name]["files"][fmt] = f.name
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    if not EVAL_PY.exists():
        print(f"no isolated env at {EVAL_PY}: python -m venv output/.venv-eval; pip install trimesh lxml networkx")
        return
    r = subprocess.run([str(EVAL_PY), "-I", str(ROOT / "tests" / "check_exports_load.py"), str(OUT)],
                       capture_output=True, text=True)
    print(r.stdout or r.stderr)


if __name__ == "__main__":
    main()
