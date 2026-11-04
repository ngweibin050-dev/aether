"""Why not just ask Muse Spark? The same three-view car drawing, two ways, scored the same way.

    python -m tests.baseline_spark            # 3 plain Muse Spark answers (costs Meta API calls) + AETHER's model
    python -m tests.baseline_spark --score    # only re-score the saved answers (no API)

A. AETHER: the CAD car its pipeline built from the sheet (output/projects/cad-car: the B-rep body, wheels, mirrors).
B. Plain Muse Spark (muse-spark-1.3), no tools: the sheet and one request ("build this car as parametric parts"),
   with the same part vocabulary and frame AETHER's create_model gives it. 3 answers (seeds 1-3).

Both are scored against the DRAWING itself, not against each other: the silhouette of each view (side, top, end) as
cad/observations.py reads it from the ink, and the model's silhouette in the same view, each scaled to the drawing's
view box (the sheet has no dimension, so size is not scored, shape is). Mirror images are tried for both alike.
  - silhouette IoU per view (1 = the same outline)
  - proportion error: |W/L - W0/L0| / (W0/L0) and the same for H/L (L length, W width, H height), mean, %
  - parts built / parts in the answer (a part the geometry engine rejects is not built)
Results: output/baseline/results.json and the table printed (pasted into docs/EVIDENCE.md)."""
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "baseline"
SHEET = ROOT / "output" / "cad" / "current" / "sheet.png"
VIEWS = (("side", (0, 2)), ("top", (0, 1)), ("end_a", (1, 2)))      # view -> model axes (horizontal, vertical)


def drawing_masks():
    from cad import observations as O
    obs, aux = O.observe(str(SHEET))
    out = {}
    for v, _ in VIEWS:
        x0, y0, x1, y1 = obs["views"][v]["box"]
        m = np.asarray(aux["sils"][v])[y0:y1 + 1, x0:x1 + 1]
        ys, xs = np.nonzero(m)
        out[v] = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return out


def model_masks(meshes, shapes):
    """Silhouettes of triangles [(V, F)] (model frame: x length, y width, z up) at the drawing views' pixel sizes."""
    allV = np.vstack([V for V, _ in meshes])
    out = {}
    for v, (a, b) in VIEWS:
        h, w = shapes[v]
        lo, hi = allV[:, [a, b]].min(0), allV[:, [a, b]].max(0)
        im = Image.new("1", (w, h))
        dr = ImageDraw.Draw(im)
        for V, F in meshes:
            P = V[:, [a, b]]
            px = (P[:, 0] - lo[0]) / max(hi[0] - lo[0], 1e-9) * (w - 1)
            py = (hi[1] - P[:, 1]) / max(hi[1] - lo[1], 1e-9) * (h - 1)     # image rows go down, z / y up
            for t in F:
                dr.polygon([(px[i], py[i]) for i in t], fill=1)
        out[v] = np.asarray(im, bool)
    ext = allV.max(0) - allV.min(0)
    return out, ext


def iou(a, b):
    best = 0.0
    for fx in (False, True):
        for fy in (False, True):
            m = b[:, ::-1] if fx else b
            m = m[::-1, :] if fy else m
            best = max(best, float((a & m).sum() / max((a | m).sum(), 1)))
    return best


def score(meshes, dm):
    mm, ext = model_masks(meshes, {k: v.shape for k, v in dm.items()})
    L0 = dm["side"].shape[1]
    W0, H0 = dm["top"].shape[0] * dm["side"].shape[1] / dm["top"].shape[1], dm["side"].shape[0]
    L, W, H = ext
    prop = (abs(W / L - W0 / L0) / (W0 / L0) + abs(H / L - H0 / L0) / (H0 / L0)) / 2
    return {"iou": {v: round(iou(dm[v], mm[v]), 3) for v, _ in VIEWS}, "proportion_error_pct": round(100 * prop, 1),
            "size_mm": [round(float(x)) for x in ext]}


def aether_model():
    from engine import lab, snap
    import assistant as A
    st = json.loads((ROOT / "output" / "projects" / "cad-car" / "project.json").read_text(encoding="utf-8"))["state"]
    lab.fold_cad_leaves(st)
    m = next(r for r in A.roots(st) if (r.get("eng") or {}).get("cad_document"))
    return [(V, F) for p, V, F, _ in snap.model_meshes(st, m) if (p.get("eng") or {}).get("cad_document")]


ASK = """This sheet is a three-view drawing of a sports car (side, top and the two end views). Build it as a 3D model
made of parametric parts, as accurately as you can match the drawing's outline in every view.
Frame: millimetres, x = the car's length (front at -x), y = its width, z = up, the wheels standing on z = 0.
Part types and their params (use exactly these names): {types}.
Each part: {{"name", "type", "params", "position": [x, y, z] (its centre), "rotation": [rx, ry, rz] degrees}}.
Answer with JSON only: {{"name": "...", "parts": [...]}}"""


def ask_spark(seed):
    import agent
    from engine import geometry
    from server import _data_url  # noqa: F401  (loads .env)
    import base64
    url = "data:image/png;base64," + base64.b64encode(SHEET.read_bytes()).decode()
    content = [{"type": "text", "text": ASK.format(types="; ".join(f"{k}({v})" for k, v in geometry.PARAM_HELP.items()))},
               {"type": "image_url", "image_url": {"url": url}}]
    t0 = time.time()
    obj, meta = agent._spark_json(content, name="car", seed=seed, timeout=240, effort="low")
    return obj, round(time.time() - t0, 1)


def build(answer):
    from engine import lab
    st = lab.default_state()
    st["parts"] = []
    ok, bad = [], []
    for p in answer.get("parts") or []:
        try:
            lab.add_part(st, p["type"], p.get("params") or {}, p.get("name"), p.get("position") or [0, 0, 0],
                         p.get("rotation") or [0, 0, 0])
            ok.append(p.get("name"))
        except Exception as e:                       # noqa: BLE001 - a part the engine rejects is counted, not fixed
            bad.append(f"{p.get('name')}: {type(e).__name__}: {str(e)[:80]}")
    from engine import geometry
    return [(V, F) for p, V, F in geometry.scene_meshes(st["parts"]) if len(F)], ok, bad


def main(score_only=False):
    OUT.mkdir(parents=True, exist_ok=True)
    dm = drawing_masks()
    res = {"sheet": SHEET.name, "aether": score(aether_model(), dm), "spark": []}
    for seed in (1, 2, 3):
        f = OUT / f"spark_seed{seed}.json"
        if not f.exists() and not score_only:
            try:
                ans, s = ask_spark(seed)
                f.write_text(json.dumps({"answer": ans, "seconds": s}, indent=1), encoding="utf-8")
            except Exception as e:                   # noqa: BLE001
                res["spark"].append({"seed": seed, "error": f"{type(e).__name__}: {str(e)[:200]}"})
                continue
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        meshes, ok, bad = build(d["answer"])
        row = {"seed": seed, "seconds": d["seconds"], "parts": len(ok) + len(bad), "built": len(ok), "rejected": bad[:5]}
        row.update(score(meshes, dm) if meshes else {"iou": None})
        res["spark"].append(row)
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("| model | IoU side | IoU top | IoU end | proportion error % | parts built |")
    print("|---|---|---|---|---|---|")
    a = res["aether"]
    print(f"| AETHER (CAD pipeline) | {a['iou']['side']} | {a['iou']['top']} | {a['iou']['end_a']} | {a['proportion_error_pct']} | B-rep solids |")
    for r in res["spark"]:
        if r.get("iou"):
            print(f"| plain Muse Spark, seed {r['seed']} | {r['iou']['side']} | {r['iou']['top']} | {r['iou']['end_a']} | "
                  f"{r['proportion_error_pct']} | {r['built']}/{r['parts']} |")
        else:
            print(f"| plain Muse Spark, seed {r['seed']} | - | - | - | - | {r.get('error') or 'nothing built'} |")


if __name__ == "__main__":
    main("--score" in sys.argv)
