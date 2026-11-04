"""CAD quality benchmark: the same objects through cad/codegen.py after every change to the loop, scored the same way.

    python -m tests.cad_quality_bench run <case> [rounds]    # one case (costs Meta API calls; ~15-35 min)
    python -m tests.cad_quality_bench summary                # docs/CAD_QUALITY.md from the saved runs

Cases (no object has construction code):
  car       the closed-car four-view sheet (third-party: kept out of the repository; the case is skipped without it)
  roadster  the CC0 roadster four-view sheet (tests/inputs/heldout/CC0_Cobra_four_view.png)
  clamp     a description only
  engine    a description only (a machine, many internal parts)
  press     a 1909 patent figure: ONE sectional view of an undocumented machine (evidence-driven reconstruction)
Per case: the kept round's critic scores (0-10, Muse Spark reviewing real renders), the quality gates (floating,
stickers, box-like share, wrong overlaps, planned-but-missing), silhouette IoU per view (drawings only), parts, time."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "cad_bench"
CASES = {
    "car": {"sheet": ROOT / "output" / "cad" / "current" / "sheet.png", "request": ""},
    "roadster": {"sheet": ROOT / "tests" / "inputs" / "heldout" / "CC0_Cobra_four_view.png", "request": ""},
    "clamp": {"sheet": None, "request": "a mechanical clamp with an adjustable screw and two gripping jaws"},
    "press": {"sheet": ROOT / "tests" / "inputs" / "US929594_fig1.png",
              "request": "reconstruct this machine from its patent drawing (one sectional side view; hidden geometry must be "
                         "inferred and listed as unknown)"},
    "engine": {"sheet": None, "request": "a single-cylinder four-stroke motorcycle engine: crankcase, finned cylinder, "
                                         "cylinder head with valve cover, spark plug, carburettor with air filter, exhaust "
                                         "header, clutch cover, mounting lugs; shown complete from outside"},
}


def run(case, rounds=5):
    for line in open(ROOT.parent / ".env", encoding="utf-8"):
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))
    from cad import codegen as G
    c = CASES[case]
    if c["sheet"] and not Path(c["sheet"]).exists():
        print(f"{case}: its sheet is not in this copy; skipped")
        return
    out = OUT / case / time.strftime("%Y%m%d-%H%M")
    r = G.build(str(c["sheet"]) if c["sheet"] else None, str(out), request=c["request"], rounds=rounds)
    print(json.dumps({k: v for k, v in (r.get("best") or {}).items() if k != "parts"}, indent=1, default=str))


def summary():
    L = ["# CAD quality benchmark", "",
         "`python -m tests.cad_quality_bench`: the same objects through the AI-written CAD loop (`cad/codegen.py`). The "
         "critic is Muse Spark reviewing real renders against `prompts/cad_critic.md` (0-10; an AI judgement, not a "
         "measurement). The gates and IoU are computed by code.", "",
         "| case | run | rounds | kept | critic overall | fidelity / assembly / surfaces / detail / materials / integrity | "
         "gates | IoU side / top / ends | parts | min |", "|---|---|---|---|---|---|---|---|---|---|"]
    for case in CASES:
        for d in sorted((OUT / case).glob("*")) if (OUT / case).exists() else []:
            f = d / "report.json"
            if not f.exists():
                continue
            r = json.loads(f.read_text(encoding="utf-8"))
            b = r.get("best") or {}
            sc = b.get("critic_scores") or {}
            iou = b.get("iou") or {}
            L.append(f"| {case} | {d.name} | {len(r.get('rounds') or [])} | {b.get('round', '-')} | {b.get('critic', '-')} | "
                     + " / ".join(str(sc.get(k, '-')) for k in ("fidelity", "assembly", "surfaces", "detail", "materials", "integrity"))
                     + f" | {b.get('gates', '-')} | "
                     + (" / ".join(str(iou.get(k)) for k in ("side", "top", "end_a", "end_b")) if iou else "-")
                     + f" | {len(b.get('parts') or [])} | {round((r.get('seconds') or 0) / 60, 1)} |")
    (ROOT / "docs" / "CAD_QUALITY.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 5)
    else:
        summary()
