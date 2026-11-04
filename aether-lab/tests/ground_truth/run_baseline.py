"""BASELINE: Muse Wonder writes the program ONCE from the same drawing and instructions (codegen.one_shot: no plan,
no gates, no critic, no second round). Run in the CAD worker's Python:
    cad-worker/.venv/Scripts/python tests/ground_truth/run_baseline.py [part ...]  -> tests/ground_truth/<part>/baseline/"""
import concurrent.futures as cf
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LAB)
for p in (os.path.join(LAB, ".env"), os.path.join(os.path.dirname(LAB), ".env")):
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
from cad import codegen as G  # noqa: E402

from run_aether import REQUEST  # noqa: E402  (the same sentence the full loop gets)


def one(name):
    d = os.path.join(HERE, name)
    r = G.one_shot(os.path.join(d, "drawing.png"), os.path.join(d, "baseline"), request=REQUEST,
                   log=lambda m: print(name, m, flush=True))
    json.dump(r, open(os.path.join(d, "baseline", "result.json"), "w", encoding="utf-8"), indent=1, default=str)
    return name, r.get("error"), len(r.get("parts") or []), r.get("seconds")


if __name__ == "__main__":
    names = sys.argv[1:] or ["pillow_block", "flanged_hub", "gusset_bracket"]
    with cf.ThreadPoolExecutor(len(names)) as ex:
        for res in ex.map(one, names):
            print("DONE", res, flush=True)
