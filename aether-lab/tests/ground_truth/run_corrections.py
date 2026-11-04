"""An engineer's correction: the full loop's INFERRED parameters set to the part's real values (what calipers on the
real part would give), the same program re-run (codegen.rerun: no model call). -> tests/ground_truth/<part>/corrected/
    cad-worker/.venv/Scripts/python tests/ground_truth/run_corrections.py"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from cad import codegen as G  # noqa: E402

FIX = {
    "pillow_block": {"base_thickness": 14, "bolt_hole_diameter": 12, "bolt_hole_end_offset": 15, "bore_diameter": 30,
                     "bore_centre_height": 42, "cap_outer_radius": 28, "housing_depth": 40, "pedestal_width": 70},
    "flanged_hub": {"flange_thickness": 12, "hub_diameter": 60, "hub_protrusion": 50, "central_bore_diameter": 25,
                    "bolt_hole_diameter": 10, "bolt_pcd": 90},
    "gusset_bracket": {"plate_thickness": 8, "hole_diameter": 9, "hole_spacing": 60, "hole_offset_x": 20},
}

if __name__ == "__main__":
    out = {}
    for part, ovr in FIX.items():
        d = os.path.join(HERE, part)
        have = json.load(open(os.path.join(d, "aether", "params.json"), encoding="utf-8"))
        ovr = {k: float(v) for k, v in ovr.items() if k in have}
        t = time.time()
        r = G.rerun(os.path.join(d, "aether"), os.path.join(d, "corrected"), ovr, log=lambda m: None)
        out[part] = {"overrides": ovr, "was": {k: have[k]["value"] for k in ovr}, "error": r.get("error"),
                     "seconds": round(time.time() - t, 1)}
        print(part, out[part], flush=True)
    json.dump(out, open(os.path.join(HERE, "corrections_run.json"), "w"), indent=1)
