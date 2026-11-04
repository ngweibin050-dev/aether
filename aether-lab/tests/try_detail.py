"""Experiment: drive AETHER like a user does, through the chat API, and record what the AI does.

    python -m tests.try_detail <sheet.png> <out_dir>

1. upload the sheet, "Create a 3D model of this car from the drawing."
2. the user's own request: "make the car model more detailed ... a lot a lot ..."
Writes <out_dir>/turns.json (every tool call, its arguments and result, the reply) and copies each program model's
GLB per version, for review renders."""
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests import e2e_story as E  # noqa: E402

DETAIL = ("make the car model more detailed, like the internal car seats, seat belts, engine, car window, front mirror, "
          "back mirror, side mirror, car light, car plate, car door, car door knob and so on, a lot a lot, with suitable "
          "color and depth, like car light can be yellow")


def main(sheet, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    E.SLUG, E.PORT = "_try-detail", 8780
    E.BASE = f"http://127.0.0.1:{E.PORT}"
    E.OUT, E.CAD = out, ROOT / "output" / "cad" / "try_detail"
    shutil.rmtree(ROOT / "output" / "projects" / E.SLUG, ignore_errors=True)
    import projects
    from engine import lab
    st = lab.default_state()
    st["parts"] = []
    projects.create(E.SLUG, st)
    if projects.CURRENT["slug"] != E.SLUG:
        shutil.move(str(ROOT / "output" / "projects" / projects.CURRENT["slug"]), str(ROOT / "output" / "projects" / E.SLUG))
    srv = E.start_server()
    turns = []
    try:
        up = E.http("/api/files", raw=Path(sheet).read_bytes(), headers={"X-Filename": "car_sheet.png"})
        for text, att in (("Create a 3D model of this car from the drawing.", [up.get("name") or "car_sheet.png"]),
                          (DETAIL, [])):
            t0 = time.time()
            r = E.chat(text, att)
            st = E.http("/api/state")["state"]
            progs = [(p["name"], (p.get("eng") or {}).get("version"), (p.get("eng") or {}).get("glb"))
                     for p in st["parts"] if not p.get("parent") and (p.get("eng") or {}).get("kind") == "cad program"]
            for name, v, glb in progs:
                if glb and Path(glb).exists():
                    shutil.copy2(glb, out / f"turn{len(turns) + 1}_v{v}.glb")
            turns.append({"request": text, "seconds": round(time.time() - t0, 1), "reply": r.get("reply"),
                          "calls": [{"tool": t["tool"], "args": t.get("args"),
                                     "result": json.dumps(t.get("result"), default=str)[:3000]} for t in r.get("trace") or []],
                          "program_models": progs, "parts_in_scene": len(st["parts"])})
            print(f"turn {len(turns)}: {[c['tool'] for c in turns[-1]['calls']]} {turns[-1]['seconds']} s", flush=True)
            json.dump(turns, open(out / "turns.json", "w", encoding="utf-8"), indent=1, default=str)
    finally:
        E.stop_server(srv)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
