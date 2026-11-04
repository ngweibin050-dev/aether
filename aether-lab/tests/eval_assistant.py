"""Live evaluation of the assistant (assistant.py) on the messages real users send. Each case sets up a scene, sends one
message through the real Muse Spark tool loop, and checks what the assistant DID (tools called, what changed in the
scene, the extras it returned), not how it worded the reply.

    python tests/eval_assistant.py            # all cases
    python tests/eval_assistant.py window     # cases whose name contains "window"

Writes output/eval_assistant.json. Needs META_API (live calls) and, for export / drawing, the CAD worker."""
import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server  # noqa: E402,F401  (loads .env)
import assistant as A  # noqa: E402
from engine import export, lab  # noqa: E402

OUT = ROOT / "output" / "eval"
OUT.mkdir(parents=True, exist_ok=True)


def car_scene():
    """A simple car: body (a CAD-style part whose triangles carry a 'glass' region), four wheels."""
    st = lab.default_state()
    st["parts"] = []
    g = lab._part("group", {}, "Sports car", (0, 0, 0))
    g["eng"] = {"kind": "cad assembly", "cad_document": "eval-car"}
    st["parts"].append(g)
    import numpy as np
    from engine import geometry
    V, F = geometry.box(200, 80, 50)
    body = lab._part("cad", {"vertices": V.ravel().tolist(), "faces": F.ravel().tolist(), "regions": [1, 1] + [0] * 10,
                             "region_names": ["glass"]}, "body", (0, 0, 45), parent=g["id"])
    body["color"] = "#c4cbd4"
    body["eng"] = {"kind": "body_shell", "cad_document": "eval-car"}
    st["parts"].append(body)
    for i, (x, y) in enumerate(((-70, -45), (70, -45), (-70, 45), (70, 45))):
        w = lab._part("cylinder", {"radius": 20, "height": 12}, f"wheel {i + 1}", (x, y, 20), (90, 0, 0), parent=g["id"])
        st["parts"].append(w)
    st["selected"] = None
    A.arrange(st)
    return st


def machine_scene():
    rec = json.loads((ROOT / "output" / "recorded" / "D.json").read_text(encoding="utf-8"))
    st = copy.deepcopy(rec["state"])
    st["selected"] = None
    return st


def two_models():
    st = car_scene()
    lab.add_part(st, "gear", {"teeth": 20, "module": 2, "thickness": 8}, "Drive gear", (0, 0, 0))
    st["selected"] = None
    A.arrange(st)
    return st


def glb_file():
    st = lab.default_state()
    f = OUT / "small_gear.glb"
    f.write_bytes(export.glb(st))
    return {"name": f.name, "kind": "mesh", "path": str(f), "bytes": f.stat().st_size}


def ctx(attachments=()):
    files = list(attachments)
    return {"out_dir": str(OUT), "exports_dir": str(OUT / "exports"), "cad_brep_dir": str(ROOT / "output" / "cad" / "current" / "brep"),
            "files": files, "attachments": files, "data_url": server._data_url, "on_step": lambda e: None, "have": {}}


def tools(trace):
    return [t["tool"] for t in trace]


def names(st):
    return {p["name"] for p in st["parts"]}


CASES = [
    # (name, scene, message, attachments, check(state_before, state_after, reply, trace, extras) -> list of failures)
    ("knowledge: what is a 3D model", car_scene, "what is 3d model?", (),
     lambda b, a, r, t, x: (["changed the scene"] if x["changes"] else []) + (["no answer"] if len(r or "") < 40 else [])),
    ("maths: 45+64", car_scene, "what is 45+64", (),
     lambda b, a, r, t, x: (["no calculate"] if "calculate" not in tools(t) else []) + (["109 missing"] if "109" not in (r or "") else [])
     + (["changed the scene"] if x["changes"] else [])),
    ("learn the machine", machine_scene, "help me learn this machine", (),
     lambda b, a, r, t, x: (["no explain_machine"] if "explain_machine" not in tools(t) else []) + (["no explain payload"] if not x.get("explain") else [])
     + (["changed the scene"] if x["changes"] else [])),
    ("explain (explain panel)", machine_scene, "explain the machine", (),
     lambda b, a, r, t, x: ["no explain_machine"] if "explain_machine" not in tools(t) else []),
    ("angry: window blue (English)", car_scene, "I am fucking angry now, u stupid ai, just make the car window to become blue color lah", (),
     lambda b, a, r, t, x: (["window not blue"] if not any((p.get("region_colors") or {}).get("glass") for p in a["parts"]) else [])
     + (["removed or added parts"] if names(b) != names(a) else [])
     + (["other colours changed"] if any(p.get("color") != q.get("color") for p, q in zip(b["parts"], a["parts"])) else [])),
    ("window blue (Chinese)", car_scene, "把车窗变成蓝色", (),
     lambda b, a, r, t, x: ["window not blue"] if not any((p.get("region_colors") or {}).get("glass") for p in a["parts"]) else []),
    ("refine: more detailed car", car_scene, "can separate single body to more detailed, like car windows, car doors, seats inside, steering wheel, front and back bonnet", (),
     lambda b, a, r, t, x: (["car removed"] if "Sports car" not in names(a) else [])
     + (["the car was rebuilt (its group is gone)"] if not ({p["id"] for p in b["parts"] if p["name"] == "Sports car"}
                                                            & {p["id"] for p in a["parts"]}) else [])
     + (["used create_model while refining"] if "create_model" in tools(t) else [])
     + (["nothing added to the car"] if len(lab.subtree(a, next(p for p in a["parts"] if p["name"] == "Sports car")["id"])) <= 6 else [])),
    ("add a GLB beside the car", car_scene, "put this glb beside the car", ("glb",),
     lambda b, a, r, t, x: (["car removed"] if "Sports car" not in names(a) else []) + (["no import"] if "import_file" not in tools(t) else [])
     + (["not 2 models"] if len(A.roots(a)) != 2 else [])),
    ("remove the model (ambiguous)", two_models, "remove the model", (),
     lambda b, a, r, t, x: (["removed without asking"] if len(A.roots(a)) < len(A.roots(b)) else []) + (["no question"] if not x.get("question") else [])),
    ("remove a named model", two_models, "delete the drive gear", (),
     lambda b, a, r, t, x: (["gear still there"] if "Drive gear" in names(a) else []) + (["car removed"] if "Sports car" not in names(a) else [])),
    ("export GLB to chat", car_scene, "export this model now in aether desk to glb and send in this chatbox for me to download", (),
     lambda b, a, r, t, x: ["no glb download"] if not any(d["name"].endswith(".glb") for d in x["downloads"]) else []),
    ("blueprint from the model", machine_scene, "make reliable blueprint from the 3d model in the aether desk now", (),
     lambda b, a, r, t, x: ["no drawing PDF"] if not any(d["name"].endswith(".pdf") for d in x["downloads"]) else []),
    ("web search", car_scene, "what is the latest stable version of OpenCascade OCCT?", (),
     lambda b, a, r, t, x: (["no web_search"] if "web_search" not in tools(t) else []) + (["no sources"] if not x["sources"] else [])),
    ("make it bigger (selection)", car_scene, "make the car bigger", (),
     lambda b, a, r, t, x: ["car not scaled"] if next(p for p in a["parts"] if p["name"] == "Sports car")["scale"] ==
     next(p for p in b["parts"] if p["name"] == "Sports car")["scale"] else []),
    ("create beside existing", car_scene, "make a simple robot arm", (),
     lambda b, a, r, t, x: (["car removed"] if "Sports car" not in names(a) else []) + (["not 2 models"] if len(A.roots(a)) != 2 else [])),
    ("Malay: hide wheels", car_scene, "tolong sorokkan semua roda", (),
     lambda b, a, r, t, x: ["wheels visible"] if any(p["visible"] for p in a["parts"] if p["name"].startswith("wheel")) else []),
]


def main(filt=None):
    results = []
    for name, scene, msg, att, check in CASES:
        if filt and filt.lower() not in name.lower():
            continue
        A.steps.reset()
        st = scene()
        before = copy.deepcopy(st)
        files = [glb_file()] if "glb" in att else []
        t0 = time.time()
        try:
            reply, trace, images, hist, extras = A.turn(st, [], msg, ctx(files))
            fails = check(before, st, reply, trace, extras)
            err = None
        except Exception as e:
            reply, trace, extras, fails, err = "", [], {}, [f"{type(e).__name__}: {e}"], str(e)
        dt = round(time.time() - t0, 1)
        ok = not fails
        print(f"{'PASS' if ok else 'FAIL'}  {dt:6.1f} s  {name:34s} tools={tools(trace)}  {'' if ok else fails}", flush=True)
        results.append({"case": name, "message": msg, "pass": ok, "fails": fails, "seconds": dt, "tools": tools(trace),
                        "changes": extras.get("changes"), "question": extras.get("question"), "reply": (reply or "")[:600],
                        "error": err})
    n = sum(r["pass"] for r in results)
    print(f"\n{n}/{len(results)} pass")
    f = ROOT / "output" / "eval_assistant.json"         # merged by case: running one case keeps the others' latest result
    old = {r["case"]: r for r in (json.loads(f.read_text(encoding="utf-8")) if f.exists() else [])}
    old.update({r["case"]: r for r in results})
    f.write_text(json.dumps(list(old.values()), indent=1, ensure_ascii=False), encoding="utf-8")
    return results


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
