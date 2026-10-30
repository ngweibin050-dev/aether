"""Photo of a real part -> SAM 3.1 cut-out -> silhouette measurements for Muse Spark.

SAM 3.1 runs on the Meta Model API (POST /v1/responses, model "sam-3.1", streamed). It returns, per object,
a box and a mask over that box; the mask is decoded with Meta's meta-sam-parser package.
The measurements (size, roundness, centre hole, number of lobes such as gear teeth or fan blades) are what
Muse Spark uses, together with the cut-out image, to rebuild the part from the parametric library.
"""
import base64
import io
import json
import os
import urllib.request

import numpy as np
from PIL import Image, ImageDraw

API = os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")
SAM_MODEL = os.environ.get("META_SAM_MODEL", "sam-3.1")
MAX_SIDE = 768                     # SAM masks are decoded in pure Python, so keep photos small


def load_image(data_url, max_side=MAX_SIDE):
    raw = base64.b64decode(data_url.split(",", 1)[-1])
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    s = max_side / max(im.size)
    if s < 1:
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    return im


def _data_url(im, fmt="PNG"):
    buf = io.BytesIO()
    im.save(buf, fmt)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


def _sse_text(resp):
    """Collect the output text of a streamed Responses call."""
    out = []
    for line in resp:
        line = line.decode("utf-8", "ignore").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            ev = json.loads(data)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "response.output_text.delta":
            out.append(ev.get("delta", ""))
        elif ev.get("type") in ("response.failed", "error"):
            raise RuntimeError(f"SAM 3.1: {json.dumps(ev)[:300]}")
    return "".join(out)


def segment(im, prompt):
    """SAM 3.1 concept segmentation. Returns a list of {id, box [x1,y1,x2,y2], confidence, mask (H x W bool, full frame)}."""
    from meta_sam_parser import CompletedOutcome, decode_mask_to_raster, image_segmentation_format
    key = os.environ.get("META_API")
    if not key:
        raise RuntimeError("META_API is not set in .env")
    body = {"model": SAM_MODEL, "stream": True, "metadata": {"include_confidence": "true"},
            "input": [{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": _data_url(im, "JPEG")}]}]}
    req = urllib.request.Request(API + "/responses", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "Accept": "text/event-stream"})
    with urllib.request.urlopen(req, timeout=120) as r:
        text = _sse_text(r)
    parser = image_segmentation_format().create_parser()
    parser.push(text if text.endswith("\n") else text + "\n")
    result = parser.finish(CompletedOutcome()).result
    objs = {}
    for rec in result.records:
        if rec.kind == "box":
            o = objs.setdefault(rec.object_id, {"id": rec.object_id})
            o["box"] = [int(rec.left), int(rec.top), int(rec.right), int(rec.bottom)]
            o["confidence"] = rec.confidence
        elif rec.kind == "mask":
            o = objs.setdefault(rec.object_id, {"id": rec.object_id})
            m = np.frombuffer(decode_mask_to_raster(rec.mask), np.uint8).reshape(rec.mask.height, rec.mask.width).astype(bool)
            b = rec.bounds
            full = np.zeros((im.height, im.width), bool)
            bw, bh = int(b.right - b.left), int(b.bottom - b.top)
            if (m.shape[1], m.shape[0]) != (bw, bh):           # mask at another resolution: stretch it over its box
                m = np.array(Image.fromarray(m).resize((max(bw, 1), max(bh, 1)), Image.NEAREST))
            y0, x0 = int(b.top), int(b.left)
            h, w = min(m.shape[0], im.height - y0), min(m.shape[1], im.width - x0)
            full[y0:y0 + h, x0:x0 + w] = m[:h, :w]
            o["mask"] = full
            o.setdefault("box", [x0, y0, x0 + bw, y0 + bh])
            if o.get("confidence") is None:
                o["confidence"] = rec.confidence
    return [o for o in objs.values() if "mask" in o and o["mask"].any()]


def radial(mask, bins=720):
    """Outer radius r(theta) around the centroid (pixels) and its strongest harmonic.
    Teeth / lobes = the dominant FFT harmonic of r(theta) (robust on outlines and line art, unlike counting
    crossings of the median). Returns teeth, its strength (harmonic amplitude / mean radius), tip and root radius."""
    ys, xs = np.nonzero(mask)
    cx, cy = xs.mean(), ys.mean()
    ang = np.arctan2(ys - cy, xs - cx)
    rad = np.hypot(ys - cy, xs - cx)
    idx = ((ang + np.pi) / (2 * np.pi) * bins).astype(int) % bins
    r = np.zeros(bins)
    np.maximum.at(r, idx, rad)
    empty = r == 0
    if empty.any() and (~empty).any():
        r[empty] = np.interp(np.nonzero(empty)[0], np.nonzero(~empty)[0], r[~empty], period=bins)
    spec = np.abs(np.fft.rfft(r - r.mean())) / bins * 2
    k = 6 + int(np.argmax(spec[6:min(len(spec), 160)])) if len(spec) > 8 else 0
    return {"teeth": k, "strength": float(spec[k] / max(r.mean(), 1e-6)) if k else 0.0,
            "tip_px": float(np.percentile(r, 97)), "root_px": float(np.percentile(r, 3)), "centre_px": (cx, cy)}


def rectify_round(mask):
    """A round part photographed at an angle is an ellipse. Its second moments give the ellipse axes; stretching
    the minor axis back to the major one (an affine approximation of the homography for a flat round part)
    returns the front-on silhouette. Returns (mask, tilt_deg)."""
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return mask, 0.0
    cx, cy = xs.mean(), ys.mean()
    C = np.cov(np.c_[xs - cx, ys - cy].T)
    w, v = np.linalg.eigh(C)
    ratio = float(np.sqrt(max(w[0], 1e-9) / max(w[1], 1e-9)))
    if ratio > 0.97 or ratio < 0.3:                     # already round, or not a round part
        return mask, 0.0
    minor = v[:, 0]
    # x' = c + (I + (1/ratio - 1) n n^T)(x - c): stretch along the minor axis
    S = np.eye(2) + (1 / ratio - 1) * np.outer(minor, minor)
    Si = np.linalg.inv(S)
    H, W = mask.shape
    grow = 1 / ratio
    Ho, Wo = int(H * grow) + 2, int(W * grow) + 2
    yo, xo = np.mgrid[0:Ho, 0:Wo]
    oc = np.array([Wo / 2, Ho / 2])
    src = (np.stack([xo.ravel() - oc[0], yo.ravel() - oc[1]], 1) @ Si.T) + [cx, cy]
    sx, sy = np.round(src[:, 0]).astype(int), np.round(src[:, 1]).astype(int)
    ok = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
    out = np.zeros(Ho * Wo, bool)
    out[ok] = mask[sy[ok], sx[ok]]
    return out.reshape(Ho, Wo), round(float(np.degrees(np.arccos(ratio))), 1)


def measure(mask, size_mm):
    """Silhouette numbers in mm (the longest side of the object = size_mm)."""
    ys, xs = np.nonzero(mask)
    x1, x2, y1, y2 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    w, h = x2 - x1, y2 - y1
    mm = size_mm / max(w, h)
    cx, cy = xs.mean(), ys.mean()
    area = len(xs)
    # boundary pixels -> perimeter estimate and radial profile around the centroid
    m = mask[y1:y2, x1:x2]
    pad = np.pad(m, 1)
    edge = m & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
    ey, ex = np.nonzero(edge)
    perim = max(len(ey), 1) * 0.95
    circ = float(min(1.0, 4 * np.pi * area / perim ** 2))
    ang = np.arctan2(ey + y1 - cy, ex + x1 - cx)
    rad = np.hypot(ey + y1 - cy, ex + x1 - cx)
    bins = 180
    idx = ((ang + np.pi) / (2 * np.pi) * bins).astype(int) % bins
    outer = np.zeros(bins)
    np.maximum.at(outer, idx, rad)
    outer[outer == 0] = np.median(outer[outer > 0]) if (outer > 0).any() else 0
    sm = np.convolve(np.r_[outer[-2:], outer, outer[:2]], np.ones(5) / 5, "valid")
    rr = radial(mask)
    lobes = rr["teeth"] if rr["strength"] > 0.01 else 0
    # a hole in the middle: the centroid itself is background
    hole = not mask[int(round(cy)), int(round(cx))]
    inner = 0.0
    if hole:
        r = 1
        while r < max(w, h) and not mask[int(np.clip(cy, 0, mask.shape[0] - 1)), int(np.clip(cx + r, 0, mask.shape[1] - 1))]:
            r += 1
        inner = r * mm
    return {"width_mm": round(w * mm, 1), "height_mm": round(h * mm, 1), "aspect": round(w / h, 2),
            "fill_of_box_pct": round(100 * area / (w * h), 1), "circularity": round(circ, 2),
            "outer_radius_mm": round(float(np.median(outer)) * mm, 1), "outer_radius_max_mm": round(float(outer.max()) * mm, 1),
            "radius_ripple_pct": round(100 * float(np.std(sm) / max(np.mean(sm), 1e-6)), 1),
            "lobes_around_centre": lobes, "lobe_strength_pct": round(100 * rr["strength"], 2), "centre_hole": hole,
            "centre_hole_radius_mm": round(inner, 1), "mm_per_pixel": round(mm, 3)}


def cutout(im, mask, box):
    """The object on a transparent background, cropped to its box."""
    rgba = np.dstack([np.asarray(im), (mask * 255).astype(np.uint8)])
    x1, y1, x2, y2 = box
    return Image.fromarray(rgba[y1:y2, x1:x2], "RGBA")


def overlay(im, objs, pick):
    """The photo with every SAM 3.1 mask tinted (the chosen one in cyan) and its box."""
    a = np.asarray(im).astype(np.float32)
    for o in objs:
        col = np.array([56, 217, 255] if o is pick else [255, 190, 90], np.float32)
        m = o["mask"]
        a[m] = 0.55 * a[m] + 0.45 * col
    out = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    d.rectangle(pick["box"], outline=(56, 217, 255), width=3)
    return out


def photo_part(data_url, prompt, size_mm=80.0):
    """Run SAM 3.1 on the photo and describe the best match. Returns (info, images, cutout data URL)."""
    im = load_image(data_url)
    objs = segment(im, prompt)
    if not objs:
        return {"error": f"SAM 3.1 found no '{prompt}' in the photo. Try a plainer background or another noun."}, {}, None
    pick = max(objs, key=lambda o: (o.get("confidence") or 0) * 0.3 + o["mask"].mean())
    flat, tilt = rectify_round(pick["mask"])            # a round part seen at an angle -> front-on silhouette
    info = {"object": prompt, "found": len(objs), "confidence": pick.get("confidence"),
            "photo_px": [im.width, im.height], "box_px": pick["box"], **measure(flat, float(size_mm)),
            "tilt_corrected_deg": tilt, "size_source": f"assumed (longest side set to {size_mm} mm)"}
    cut = cutout(im, pick["mask"], pick["box"])
    images = {"sam_overlay": _data_url(overlay(im, objs, pick), "JPEG"), "sam_cutout": _data_url(cut)}
    flat = Image.new("RGB", cut.size, (255, 255, 255))
    flat.paste(cut, mask=cut.split()[3])
    return info, images, _data_url(flat, "JPEG")             # the model gets the cut-out on white


# ---------------- blueprints: many parts in one drawing ----------------

COLORS = [(56, 217, 255), (255, 190, 90), (255, 90, 200), (120, 255, 160), (160, 140, 255), (255, 110, 110)]


def _iou(a, b):
    inter = np.logical_and(a, b).sum()
    return inter / max(1, np.logical_or(a, b).sum())


def _shape(mask, mm, centre):
    """Where a part sits in the drawing and its shape: centre (mm, y up), long axis length/width/angle (PCA),
    and for round parts the radius, teeth (lobes) and centre hole."""
    ys, xs = np.nonzero(mask)
    cx, cy = xs.mean(), ys.mean()
    X = np.c_[xs - cx, cy - ys] * mm
    w, v = np.linalg.eigh(np.cov(X.T) + 1e-9 * np.eye(2))
    ax = v[:, 1]
    proj, perp = X @ ax, X @ v[:, 0]
    length, width = float(np.ptp(proj)), float(np.ptp(perp))
    angle = float(np.degrees(np.arctan2(ax[1], ax[0]))) % 180
    out = {"centre_mm": [round((cx - centre[0]) * mm, 1), round((centre[1] - cy) * mm, 1)],
           "length_mm": round(length, 1), "width_mm": round(width, 1), "angle_deg": round(angle),
           "elongation": round(length / max(width, 1e-6), 2)}
    if out["elongation"] < 1.4:                    # roundish: measure it like a gear or wheel
        m = measure(mask, max(np.ptp(xs), np.ptp(ys)) * mm)
        out.update({"radius_mm": m["outer_radius_mm"], "lobes": m["lobes_around_centre"],
                    "centre_hole_radius_mm": m["centre_hole_radius_mm"] if m["centre_hole"] else 0})
    return out


def mask_profile(mask, mm, centre, max_cells=96):
    """The mask as a cut-out for geometry.profile: filled cells (row runs) on a grid of at most max_cells per side,
    plus where its box centre sits in the drawing (mm, y up)."""
    ys, xs = np.nonzero(mask)
    x1, x2, y1, y2 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    step = max(1.0, max(x2 - x1, y2 - y1) / max_cells)
    cols, rows = max(1, round((x2 - x1) / step)), max(1, round((y2 - y1) / step))
    g = np.asarray(Image.fromarray((mask[y1:y2, x1:x2] * 255).astype(np.uint8)).resize((cols, rows), Image.BOX)) > 110
    runs = []
    for r in range(rows):
        row = np.r_[0, g[r].astype(np.int8), 0]
        d = np.diff(row)
        runs += [[r, int(a), int(b)] for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0])]
    cell = (x2 - x1) * mm / cols
    return {"runs": runs, "rows": rows, "cols": cols, "cell": round(cell, 3),
            "at_mm": [round(((x1 + x2) / 2 - centre[0]) * mm, 1), round((centre[1] - (y1 + y2) / 2) * mm, 1)]}


def segment_boxes(im, items):
    """SAM 3.1 with box prompts: one exact mask per box (16 objects per request). items: [{box: [x1,y1,x2,y2] px, ...}]."""
    from concurrent.futures import ThreadPoolExecutor
    from meta_sam_parser import FramePrompt, PromptBox, PromptObject, build_object_prompt
    W, H = im.size
    objs = []
    for i, it in enumerate(items, 1):
        x1, y1, x2, y2 = (int(round(v)) for v in it["box"])
        x1, x2 = sorted((min(max(x1, 0), W - 1), min(max(x2, 1), W)))
        y1, y2 = sorted((min(max(y1, 0), H - 1), min(max(y2, 1), H)))
        if x2 - x1 >= 4 and y2 - y1 >= 4:
            objs.append(PromptObject(id=i, prompts=[FramePrompt(frame=0, box=PromptBox(x1, y1, x2, y2))]))
    chunks = [objs[i:i + 16] for i in range(0, len(objs), 16)]
    with ThreadPoolExecutor(max(1, len(chunks))) as ex:
        res = list(ex.map(lambda c: segment(im, build_object_prompt(size=(W, H), objects=c)), chunks))
    out = []
    for r in res:
        for o in r:
            it = items[int(o["id"]) - 1]
            out.append({**o, "label": it.get("label") or it.get("type") or "part", "spark": it})
    return out


FRAMEISH = ("frame", "plate", "housing", "base", "body", "bracket", "support", "casing", "chassis")


def _frameish(o):
    t = (str(o.get("label", "")) + " " + str((o.get("spark") or {}).get("type", ""))).lower()
    return any(k in t for k in FRAMEISH)


def clean_masks(objs):
    """Line art -> solid regions, and a frame no longer swallows the parts drawn inside it.
    1. A mask that is mostly strokes (it fills < 60 % of its own filled outline) is hole-filled.
    2. A frame-like part that contains another mask (|A and B| / |B| > 0.8) has that part cut out of it."""
    from engine.outline import fill_holes
    for o in objs:
        m = o["mask"]
        f = fill_holes(m)
        if m.sum() < 0.6 * f.sum():
            o["mask"] = f
            o["filled_from_line_art"] = True
    for a in objs:
        if not _frameish(a):
            continue
        for b in objs:
            if b is a:
                continue
            inter = np.logical_and(a["mask"], b["mask"]).sum()
            if inter > 0.8 * max(1, b["mask"].sum()):
                a["mask"] = a["mask"] & ~b["mask"]
                a.setdefault("cut_out", []).append(b.get("label", "part"))
    return objs


def blueprint_parts(data_url, prompts, size_mm=200.0, max_parts=24, boxes=None, mm_per_px=None, scale_source=None, objs=None):
    """A drawing of a whole machine. With boxes (parts Muse Spark listed after reading the drawing) SAM 3.1 traces
    each box; without, SAM 3.1 searches once per part type (one concept per request, in parallel). Overlapping masks
    are merged, line art is filled, frames lose the parts drawn inside them, and every part gets its position, shape
    and clean outline polygons in mm. Scale: mm_per_px when a dimension was read from the drawing, otherwise the
    longest side of the drawing = size_mm (an assumption, reported as such)."""
    from concurrent.futures import ThreadPoolExecutor
    from engine import outline
    im = data_url if isinstance(data_url, Image.Image) else load_image(data_url, 1024)
    if objs is not None:                              # already segmented (tests, or a cached SAM result)
        pass
    elif boxes:
        objs = segment_boxes(im, boxes)
    else:
        with ThreadPoolExecutor(len(prompts)) as ex:
            found = list(ex.map(lambda p: (p, segment(im, p)), prompts))
        objs = [{**o, "label": p} for p, os_ in found for o in os_]
    objs.sort(key=lambda o: -((o.get("confidence") or 0.5) * o["mask"].sum() ** 0.5))
    keep = []
    for o in objs:
        if all(_iou(o["mask"], k["mask"]) < 0.6 for k in keep):
            keep.append(o)
        if len(keep) >= max_parts:
            break
    if not keep:
        return {"error": f"SAM 3.1 found none of {prompts} in the drawing."}, {}
    keep = [o for o in clean_masks(keep) if o["mask"].sum() >= 20]
    if mm_per_px:
        mm = float(mm_per_px)
        source = scale_source or "read from a dimension on the drawing"
    else:
        mm = float(size_mm) / max(im.size)
        source = scale_source or f"assumed: longest side of the drawing = {size_mm} mm"
    centre = (im.width / 2, im.height / 2)
    parts = []
    for i, o in enumerate(keep, 1):
        sp = o.get("spark") or {}
        sh = _shape(o["mask"], mm, centre)
        ys, xs = np.nonzero(o["mask"])
        c_px = (xs.mean(), ys.mean())
        rr = radial(o["mask"]) if sh.get("elongation", 9) < 1.4 else None
        parts.append({"n": i, "label": o["label"], "confidence": None if o.get("confidence") is None else round(o["confidence"], 2),
                      **sh, **({"kind": sp["type"]} if sp.get("type") else {}), **({"teeth_seen": sp["teeth"]} if sp.get("teeth") else {}),
                      **({"teeth_fft": rr["teeth"], "teeth_fft_strength_pct": round(100 * rr["strength"], 2),
                          "tip_radius_mm": round(rr["tip_px"] * mm, 2), "root_radius_mm": round(rr["root_px"] * mm, 2)} if rr else {}),
                      **({"cut_out": o["cut_out"]} if o.get("cut_out") else {}),
                      **({"filled_from_line_art": True} if o.get("filled_from_line_art") else {}),
                      "_poly": outline.mask_polygons(o["mask"], mm, c_px, eps_px=0.8)})
    a = np.asarray(im).astype(np.float32)
    labels = sorted({o["label"] for o in keep})
    for o in keep:
        col = np.array(COLORS[labels.index(o["label"]) % len(COLORS)], np.float32)
        a[o["mask"]] = 0.45 * a[o["mask"]] + 0.55 * col
    out = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    for o, p in zip(keep, parts):
        x1, y1, x2, y2 = o["box"]
        d.rectangle([x1, y1, x2, y2], outline=COLORS[labels.index(o["label"]) % len(COLORS)], width=2)
        d.text((x1 + 3, y1 + 2), str(p["n"]), fill=(0, 0, 0))
    counts = {l: sum(1 for p in parts if p["label"] == l) for l in labels}
    info = {"mode": "blueprint", "read_by": "Muse Spark + SAM 3.1 boxes" if boxes else "SAM 3.1 concepts", "prompts": prompts,
            "found": counts, "parts": parts, "drawing_mm": [round(im.width * mm, 1), round(im.height * mm, 1)],
            "mm_per_px": round(mm, 4), "scale_source": source, "photo_px": [im.width, im.height]}
    return info, {"sam_overlay": _data_url(out, "JPEG"), "sam_cutout": None}
