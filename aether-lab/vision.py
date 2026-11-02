"""SAM 3.1 segmentation and 2D image evidence (no geometry is built here).

SAM 3.1 runs on the Meta Model API (POST /v1/responses, model "sam-3.1", streamed). It returns, per object,
a box and a mask over that box; the mask is decoded with Meta's meta-sam-parser package.
The measurements (size, roundness, centre hole, number of lobes such as gear teeth or fan blades) are 2D evidence
only. The former mask -> profile / outline extrusion paths (blueprint_parts, mask_profile) were removed in Phase A;
the part-photo and machine-drawing CAD builders (Phase C / D) will turn this evidence into typed CAD sketches.
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


KINDS = ("machine", "three_view", "part")


def upload_kind(data_url, views_side=1000):
    """What an upload is, measured on the image (no AI, no comma in a prompt):
    - "three_view": a sheet with three or more separate views of one object whose lengths agree (side and plan view;
      engine/views.py). It is rebuilt as parametric CAD (cad/ package, OpenCascade B-rep);
    - "machine": any other line drawing (one view of a machine);
    - "part": a photo (smooth shading, few sharp edges): SAM 3.1 cuts out one part.
    Line drawing = dense sharp edges: >= 6 % of pixels have a grey-level step > 25 per pixel (drawings measured
    0.195-0.199, the sample phone photo 0.007). Returns (kind, evidence)."""
    from engine import views
    raw = base64.b64decode(data_url.split(",", 1)[-1])
    im = Image.open(io.BytesIO(raw)).convert("L")
    im.thumbnail((512, 512))
    g = np.asarray(im, float)
    gy, gx = np.gradient(g)
    edge = float((np.hypot(gx, gy) > 25).mean())
    ev = {"edge_density": round(edge, 3)}
    if edge < 0.06:
        return "part", ev
    multi, vev = views.multi_view(raw, views_side)
    ev.update({k: (float(v) if isinstance(v, (np.floating,)) else v) for k, v in vev.items()})
    return ("three_view" if multi else "machine"), ev


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
