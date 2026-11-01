"""Build the static replay site's data (docs/replay/<demo>/) from the server's recorded demo runs (output/recorded/).

    python tools/build_replay.py

For each demo (D, C, G): the model as GLB (engine/export.py), the drawing check image, Muse Spark's reading overlay,
the explanation (steps, part names to highlight, camera, explode) with its labelled Muse Image illustration, the
timed steps (who did what) and the measured numbers of THAT recorded run. No key, no endpoint, no server: the site is
plain files, and every number on it comes from the recorded run (labelled as recorded on the page)."""
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine import export, geometry  # noqa: E402

REC = ROOT / "output" / "recorded"
OUT = ROOT / "docs" / "replay"
DEMOS = {"D": ("Metal drawing press", "US Patent 929,594, Fig. 1 (public domain)", "machine"),
         "C": ("Speed-reduction gearbox", "US Patent 1,770,035, Fig. 1 (public domain; held out before step 3)", "machine"),
         "G": ("Douglas X-3 three-view", "NASA Dryden graphic (public domain)", "three_view")}
WHO = {"read_drawing": "Muse Spark", "complete_views": "Muse Wonder", "Muse Spark": "Muse Spark",
       "explain · Muse Spark": "Muse Spark", "illustration · Muse Image": "Muse Image", "sam_3_1": "SAM 3.1",
       "read_views": "Modal T4 GPU", "desk_score": "Modal T4 GPU", "focus_sweep": "Modal T4 GPU"}
WHAT = {"read_drawing": "read drawing", "complete_views": "complete the unseen views", "Muse Spark": "thinking",
        "rebuild_3d": "rebuild each part in 3D", "measure_circles": "measure circles on the ink",
        "classify_upload": "what the image is", "read_views": "find the views, carve the 3D shape",
        "desk_score": "desk sharpness score", "focus_sweep": "eye focus sweep"}


def _img(data_url, path):
    if not data_url:
        return None
    head, b64 = data_url.split(",", 1)
    ext = "png" if "png" in head else "jpg"
    p = path.with_suffix("." + ext)
    p.write_bytes(base64.b64decode(b64))
    return p.name


def build(k):
    rec = json.loads((REC / f"{k}.json").read_text(encoding="utf-8"))
    title, source, kind = DEMOS[k]
    d = OUT / k
    d.mkdir(parents=True, exist_ok=True)
    st = rec["state"]
    (d / "model.glb").write_bytes(export.glb(st))
    by_id = {p["id"]: p["name"] for p in st["parts"]}
    parts = [p for p in st["parts"] if p["type"] != "group" and p.get("visible", True)]
    lo, hi = geometry.bounds(st["parts"])
    out = {"id": k, "title": title, "source": source, "kind": kind, "recorded_at": rec["recorded_at"],
           "parts": len(parts), "size_mm": [round(float(v), 1) for v in hi - lo],
           "check_image": _img(rec["images"].get("sam_check"), d / "check"),
           "reading_image": _img(rec["images"].get("sam_overlay"), d / "reading"),
           "steps": [{"who": s.get("who") or WHO.get(s["label"], "AETHER engine"), "what": WHAT.get(s["label"], s["label"]),
                      "s": s.get("s")} for s in rec.get("steps") or [] if s.get("s") is not None]}
    for t in rec["trace"]:
        res = t.get("result") or {}
        chk = res.get("check") or {}
        if t["tool"] == "sam_3_1":
            out["metrics"] = {"recall_pct": chk.get("drawing_lines_on_built_parts_pct"),
                              "parts_precision_pct": (chk.get("outline_on_ink_pct") or {}).get("parts"),
                              "staircase_pct": chk.get("staircase_pct"), "scale": res.get("scale_source")}
        if t["tool"] == "read_views":
            out["metrics"] = {"view_match_pct": chk.get("view_match_iou_pct"), "triangles": chk.get("delivered_triangles"),
                              "scale": f"assumed: length {res.get('size_mm', [0])[0]} mm (no scale on the sheet)"}
        if t["tool"] == "desk_score":
            out["desk"] = {"parts_ok": res.get("parts_ok"), "parts": res.get("parts"), "min_sharpness_pct": res.get("min_sharpness_pct")}
    ex = rec.get("explain")
    if ex:
        ill = ex.get("illustration") or {}
        out["explain"] = {"machine": ex.get("machine"), "timing": ex.get("timing"),
                          "scale_known": (ex.get("scale") or {}).get("real_size_known", False),
                          "steps": [{"title": s["title"], "text": s["text"], "camera": s["camera"], "explode": s["explode"],
                                     "parts": [by_id[i] for i in s["parts"] if i in by_id]} for s in ex["steps"]],
                          "illustration": _img(ill.get("data_url"), d / "illustration"),
                          "illustration_label": ill.get("label"), "illustration_s": ill.get("s")}
    (d / "data.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    index = [build(k) for k in DEMOS]
    (OUT / "index.json").write_text(json.dumps([{x: o[x] for x in ("id", "title", "source", "kind", "recorded_at")}
                                                for o in index], indent=1, ensure_ascii=False), encoding="utf-8")
    for o in index:
        size = sum(f.stat().st_size for f in (OUT / o["id"]).iterdir())
        print(o["id"], o["title"], o["recorded_at"], f"{size / 1e6:.2f} MB", o.get("metrics"))
