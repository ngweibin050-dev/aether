"""Replay saved reference runs offline: the same reading (Muse Spark's agreed parts, in pixels) and the same engineer's
completion go through the CURRENT rebuild and drawing check, so a change to the rebuild is measured on real
readings without new API calls (and without the run-to-run variance of the reading).

    python -m tests.replay_rebuild                        # every saved run that has a replay.json
    python -m tests.replay_rebuild patent_US929594_fig1   # one input

Prints per run: recall, precision for parts and frames, and precision per part kind (worst first)."""
import base64
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import vision  # noqa: E402
from engine import interpret, rebuild  # noqa: E402
from tests.run_reference import INPUTS, OUT  # noqa: E402


def replay(name, run_dir):
    rp = json.loads((run_dir / "replay.json").read_text(encoding="utf-8"))
    src = ROOT / "tests" / INPUTS[name][0]
    im = vision.load_image("data:x;base64," + base64.b64encode(src.read_bytes()).decode(), 1024)
    W, H = im.size
    from engine import circles
    parts = interpret.parts_from_read(rp["read_parts_px"], W, H, rp["mm_per_px"], ink=circles.ink_mask(im)[0])
    specs, rep = rebuild.rebuild(parts, rp["drawing_mm"], rp.get("completion"), frame_cell_mm=rp["mm_per_px"])
    sil = rep.pop("_silhouette")
    check, _ = interpret.drawing_check(im, sil, rp["mm_per_px"])
    return {"run": run_dir.name, "parts": len(parts), "recall": check["drawing_lines_on_built_parts_pct"],
            "precision": check["outline_on_ink_pct"], "by_kind": check.get("outline_on_ink_by_kind_pct", {}),
            "gear_pairs": len(rep.get("gear_pairs") or [])}


def main(names):
    for name in names:
        runs = sorted((OUT / name).glob("run*/replay.json"), key=lambda f: int(f.parent.name[3:]))
        if not runs:
            continue
        rows = [replay(name, f.parent) for f in runs]
        print(f"\n{name}: {len(rows)} saved readings replayed")
        for r in rows:
            kinds = ", ".join(f"{k} {v['pct']}% ({v['px']} px)" for k, v in sorted(r["by_kind"].items(), key=lambda kv: kv[1]["pct"] or 0))
            print(f"  {r['run']}: parts {r['parts']}, recall {r['recall']}%, precision parts {r['precision']['parts']}% "
                  f"frames {r['precision']['frames']}%, gear pairs {r['gear_pairs']}\n      by kind: {kinds}")
        mean = lambda xs: round(statistics.mean([x for x in xs if x is not None]), 1) if any(x is not None for x in xs) else None
        print(f"  MEAN recall {mean([r['recall'] for r in rows])}%, precision parts {mean([r['precision']['parts'] for r in rows])}%, "
              f"frames {mean([r['precision']['frames'] for r in rows])}%")
        agg = {}
        for r in rows:
            for k, v in r["by_kind"].items():
                a = agg.setdefault(k, [0, 0])
                a[0] += v["on_ink"]
                a[1] += v["px"]
        print("  by kind over all runs (worst first): " + ", ".join(
            f"{k} {100 * a[0] / a[1]:.1f}% of {a[1]} px" for k, a in sorted(agg.items(), key=lambda kv: kv[1][0] / max(kv[1][1], 1))))


if __name__ == "__main__":
    main(sys.argv[1:] or [n for n, v in INPUTS.items() if v[3] and not n.startswith("heldout_")])
