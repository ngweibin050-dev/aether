"""Edge quality of the machine models, replayed from saved readings (no API calls): every delivered part's outline in
the front view, scored for pixel staircases (engine/quality.py), per part kind.

    python -m tests.edge_quality                         # D, C, B: the latest saved run of each
    python -m tests.edge_quality patent_US929594_fig1"""
import base64
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import vision  # noqa: E402
from engine import circles, geometry, interpret, lab, quality, rebuild  # noqa: E402
from tests.run_reference import INPUTS, OUT  # noqa: E402

MACHINES = ["patent_US929594_fig1", "heldout_US1770035_fig1", "patent_US1699653_fig1"]          # D, C, B


def build(name, run_dir):
    """The saved reading -> the current rebuild -> parts in the drawing frame (no rotation), and the drawing scale."""
    rp = json.loads((run_dir / "replay.json").read_text(encoding="utf-8"))
    im = vision.load_image("data:x;base64," + base64.b64encode((ROOT / "tests" / INPUTS[name][0]).read_bytes()).decode(), 1024)
    W, H = im.size
    parts = interpret.parts_from_read(rp["read_parts_px"], W, H, rp["mm_per_px"], ink=circles.ink_mask(im)[0])
    specs, rep = rebuild.rebuild(parts, rp["drawing_mm"], rp.get("completion"), frame_cell_mm=rp["mm_per_px"])
    st = lab.default_state()
    lab.clear_scene(st)                   # a scene with only this design
    lab.build_assembly(st, "replay", specs, position=[0, 0, 0], rotation=[0, 0, 0])
    return st, rp["mm_per_px"], im, rep


def report(name):
    runs = sorted((OUT / name).glob("run*/replay.json"), key=lambda f: int(f.parent.name[3:]))
    if not runs:
        return None
    st, mmpx, im, rep = build(name, runs[-1].parent)
    by = {}
    worst = []
    for p, V, F in geometry.scene_meshes(st["parts"]):
        if p["type"] == "group" or not len(F):
            continue
        k = (p.get("eng") or {}).get("kind", p["type"])
        score, length, steps = quality.part_staircase(V, F, mmpx)
        b = by.setdefault(k, {"parts": 0, "with_steps": 0, "length_px": 0.0, "steps_px": 0.0})
        b["parts"] += 1
        b["with_steps"] += score > 0
        b["length_px"] += length
        b["steps_px"] += steps
        if score > 0:
            worst.append((score, p["name"], p["type"]))
    total_len = sum(b["length_px"] for b in by.values())
    total_steps = sum(b["steps_px"] for b in by.values())
    print(f"\n{name} ({runs[-1].parent.name}): staircase {100 * total_steps / max(total_len, 1):.2f} % of {total_len:,.0f} px outline; "
          f"parts with steps: {sum(b['with_steps'] for b in by.values())} of {sum(b['parts'] for b in by.values())}; "
          f"vectorised frame outline max deviation from its trace {rep['checks'].get('frame_outline_max_dev_mm', 0) / mmpx:.2f} px")
    for k, b in sorted(by.items(), key=lambda kv: -kv[1]["steps_px"]):
        print(f"   {k:8s} {b['parts']:3d} parts, {b['with_steps']:3d} with steps, staircase {100 * b['steps_px'] / max(b['length_px'], 1):6.2f} %")
    for s, n, t in sorted(worst, reverse=True)[:5]:
        print(f"      worst: {n} ({t}) {s} %")
    return by


if __name__ == "__main__":
    for n in sys.argv[1:] or MACHINES:
        report(n)
