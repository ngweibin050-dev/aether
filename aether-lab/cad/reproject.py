"""Three-view reprojection: project the CAD assembly back into each drawing view's own pixel frame and compare.

Projection: orthographic, the inverse of the view transforms in cad/vehicle.frames (same px scale and origin as the
drawing). Geometry: the B-rep tessellated finely (chordal deflection 0.5 mm here; the B-rep is the source).
Per view (never merged into one score):
- silhouette IoU (filled outline of the model vs the drawing's filled outline);
- boundary deviation: distance (px and mm) from every model-outline pixel to the nearest drawing-outline pixel and
  back; mean, 95th percentile, Hausdorff (max);
- normalised contour distance: mean symmetric boundary distance / view diagonal;
- alignment: the integer shift (+-6 px) that maximises IoU (should be ~0: the frames are fixed, a large shift means
  a wrong transform);
- dimensional deviations: model vs drawing extents (length, height, width).
A silhouette match does NOT prove the hidden 3D shape (sections between the end views are inferred).
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

from . import vehicle as Vh


def project(V, F_frames, view):
    """Model points (n,3) mm -> sheet px (n,2) for view in side / top / front / rear."""
    f = F_frames[view]
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    if view == "side":
        return np.c_[f["u0"] + f["dir"] * x / f["s"], f["v_ground"] - z / f["s"]]
    if view == "top":
        return np.c_[f["u0"] + f["dir"] * x / f["s"], f["v_c"] - y / f["s"]]
    return np.c_[f["u_c"] + y / (f["ysign"] * f["s"]), f["v_ground"] - z / f["s"]]


def model_mask(meshes, F_frames, view, shape_hw):
    H, W = shape_hw
    k = 3
    im = Image.new("L", (W * k, H * k), 0)
    d = ImageDraw.Draw(im)
    for V, Fc in meshes:
        P = project(V, F_frames, view) * k
        for a, b, c in Fc:
            d.polygon([tuple(P[a]), tuple(P[b]), tuple(P[c])], fill=255)
    return np.asarray(im.resize((W, H), Image.BOX)) >= 128


def _edge(m):
    return m & ~ndi.binary_erosion(m)


def compare(model, drawing, mm_per_px, region=None):
    """Metrics for one view. region: bool mask restricting the comparison (e.g. the view's box)."""
    if region is not None:
        model, drawing = model & region, drawing & region
    inter, union = (model & drawing).sum(), (model | drawing).sum()
    iou = float(inter / max(union, 1))
    em, ed = _edge(model), _edge(drawing)
    dt_d = ndi.distance_transform_edt(~ed)
    dt_m = ndi.distance_transform_edt(~em)
    a = dt_d[em] if em.any() else np.array([np.inf])
    b = dt_m[ed] if ed.any() else np.array([np.inf])
    both = np.r_[a, b]
    ys, xs = np.nonzero(drawing)
    diag = float(np.hypot(np.ptp(xs) + 1, np.ptp(ys) + 1)) if len(xs) else 1.0
    best = (iou, 0, 0)
    for dy in range(-6, 7, 2):
        for dx in range(-6, 7, 2):
            sh = np.roll(np.roll(model, dy, 0), dx, 1)
            i2 = float((sh & drawing).sum() / max((sh | drawing).sum(), 1))
            if i2 > best[0] + 1e-9:
                best = (i2, dx, dy)
    ext = lambda m: (lambda y, x: [int(x.min()), int(y.min()), int(x.max()), int(y.max())])(*np.nonzero(m)) if m.any() else None
    em_, ed_ = ext(model), ext(drawing)
    dims = None
    if em_ and ed_:
        dims = {"width_px": [em_[2] - em_[0] + 1, ed_[2] - ed_[0] + 1], "height_px": [em_[3] - em_[1] + 1, ed_[3] - ed_[1] + 1],
                "width_dev_mm": round(((em_[2] - em_[0]) - (ed_[2] - ed_[0])) * mm_per_px, 1),
                "height_dev_mm": round(((em_[3] - em_[1]) - (ed_[3] - ed_[1])) * mm_per_px, 1)}
    return {"iou": round(iou, 4),
            "boundary_px": {"model_to_drawing_mean": round(float(a.mean()), 2), "drawing_to_model_mean": round(float(b.mean()), 2),
                            "symmetric_mean": round(float(both.mean()), 2), "p95": round(float(np.percentile(both, 95)), 2),
                            "hausdorff": round(float(both.max()), 2)},
            "boundary_mm": {"symmetric_mean": round(float(both.mean()) * mm_per_px, 1),
                            "p95": round(float(np.percentile(both, 95)) * mm_per_px, 1),
                            "hausdorff": round(float(both.max()) * mm_per_px, 1)},
            "normalised_contour_distance": round(float(both.mean()) / diag, 5),
            "alignment": {"best_shift_px": [best[1], best[2]], "iou_at_best_shift": round(best[0], 4),
                          "note": "shift that maximises IoU within +-6 px (step 2); ~0 means the frames align"},
            "dims": dims, "mm_per_px": round(mm_per_px, 4)}


def overlay(gray, drawing, model, box, scale=2):
    """Drawing grey; drawing outline not covered by the model red; model outside the drawing magenta; model outline
    cyan. Cropped to the view box."""
    x0, y0, x1, y1 = box
    g = gray[y0:y1 + 1, x0:x1 + 1]
    rgb = np.repeat((255 - 0.5 * (255 - g))[..., None], 3, 2)
    d, m = drawing[y0:y1 + 1, x0:x1 + 1], model[y0:y1 + 1, x0:x1 + 1]
    rgb[m & ~d] = 0.4 * rgb[m & ~d] + 0.6 * np.array([230, 60, 220])
    rgb[d & ~m] = 0.4 * rgb[d & ~m] + 0.6 * np.array([235, 60, 60])
    rgb[ndi.binary_dilation(_edge(m))] = [0, 170, 230]
    im = Image.fromarray(rgb.clip(0, 255).astype(np.uint8))
    return im.resize((im.width * scale, im.height * scale), Image.LANCZOS)


VIEW_OF = {"side": "side", "top": "top"}


def evaluate(meshes, obs, aux, F_frames, out_dir=None, tag=""):
    """All four views. meshes: [(V, F)] of every visible component. Returns {view: metrics} (+ images saved)."""
    out = {}
    H, W = aux["gray"].shape
    keys = {"side": "side", "top": "top", "front": F_frames["front"]["key"], "rear": F_frames["rear"]["key"]}
    for view, role in keys.items():
        draw = aux["sils"][role]
        mod = model_mask(meshes, F_frames, view, (H, W))
        x0, y0, x1, y1 = obs["views"][role]["box"]
        pad = 25
        box = [max(0, x0 - pad), max(0, y0 - pad), min(W - 1, x1 + pad), min(H - 1, y1 + pad)]
        region = np.zeros((H, W), bool)
        region[box[1]:box[3] + 1, box[0]:box[2] + 1] = True
        s = F_frames["front"]["s"] if view in ("front", "rear") else F_frames[view]["s"]
        out[view] = compare(mod, draw, s, region)
        if out_dir:
            ov = overlay(aux["gray"], draw, mod, box)
            p = f"{out_dir}/reproject_{view}{tag}.png"
            ov.save(p)
            out[view]["image"] = p.split("/")[-1]
    return out
