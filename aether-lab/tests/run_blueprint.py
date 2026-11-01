"""Live blueprint -> 3D test (needs META_API in .env). Run from C:\\Aether\\aether-lab:
   python tests\\run_blueprint.py tests\\blueprint_example2.jpg
Writes output\\blueprint_test.json (scene + report). Never prints keys."""
import base64, json, os, sys, time, pathlib
os.environ.setdefault("AETHER_COMPUTE", "local")   # test the engine on this PC (Modal may still run an older deploy)
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # loads .env, does not start the HTTP server
from engine import lab
import agent

from engine import rebuild
_orig, CAP = rebuild.rebuild, {}
def _cap(parts, drawing_mm):                       # keep the traced parts, so the rebuild can be re-run offline
    CAP["parts"], CAP["drawing_mm"] = parts, drawing_mm
    return _orig(parts, drawing_mm)
rebuild.rebuild = _cap

img = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tests" / "blueprint_example2.jpg")
url = "data:image/jpeg;base64," + base64.b64encode(img.read_bytes()).decode()
st = lab.default_state()
steps = []
t = time.time()
reply, trace, images, hist = agent.photo_to_design(st, [], url, "gear, wheel, link, frame, shaft, piston", 300,
                                                   str(ROOT / "output"), lambda e: steps.append(e))
sc = lab.desk_score(st)
out = {"seconds": round(time.time() - t, 1), "reply": reply,
       "trace": [{"tool": x.get("tool"), "result": {k: v for k, v in (x.get("result") or {}).items() if k != "_images"}}
                 for x in trace],
       "desk_score": {k: sc.get(k) for k in ("pass", "min_sharpness_pct", "size_mm", "depth_ratio", "relief_warning", "hints")},
       "parts": [{"name": p["name"], "type": p["type"], "eng_kind": (p.get("eng") or {}).get("kind")} for p in st["parts"]],
       "state": st}
(ROOT / "output" / "blueprint_parts.json").write_text(json.dumps(CAP, default=str), encoding="utf-8")
(ROOT / "output" / "blueprint_test.json").write_text(json.dumps(out, default=str), encoding="utf-8")
print("done", out["seconds"], "s;", len(st["parts"]), "parts; desk", out["desk_score"])
