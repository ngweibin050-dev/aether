"""Run the full AETHER loop (Modal CPU, 3 rounds) on each ground-truth drawing, in parallel; AETHER gets only the
drawing and one neutral sentence. -> tests/ground_truth/<part>/aether/ (program, plan, params, report, kept B-rep)."""
import concurrent.futures as cf
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
try:
    import cad_remote  # noqa: E402
except ImportError:          # the CAD worker's Python (baseline) only needs REQUEST
    cad_remote = None

REQUEST = "Rebuild this part from its engineering drawing as editable CAD. Units are mm."


def one(name):
    d = os.path.join(HERE, name)
    t = time.time()
    r = cad_remote.build(os.path.join(d, "aether"), sheet=os.path.join(d, "drawing.png"), request=REQUEST, rounds=3,
                         on_progress=lambda m: print(f"[{name} {time.time() - t:5.0f}s] {str(m)[:150]}", flush=True))
    return name, {"seconds": round(time.time() - t), "error": r.get("error"), "rounds": r.get("rounds")}


if __name__ == "__main__":
    names = sys.argv[1:] or ["pillow_block", "flanged_hub", "gusset_bracket"]
    assert cad_remote.available(), "deploy modal_cad.py first"
    with cf.ThreadPoolExecutor(len(names)) as ex:
        for name, res in ex.map(one, names):
            print("DONE", name, json.dumps(res, default=str)[:600], flush=True)
