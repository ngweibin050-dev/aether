"""Three-view drawing -> 3D solid (visual hull). Pure numpy + Pillow.

An engineering drawing in orthographic projection shows the same part from the front (x across, z up),
the top (x across, y away from the viewer) and the right side (y across, z up). Each view is a silhouette, so
the part lies inside the extrusion of every silhouette along its viewing axis. The intersection of the three
extrusions is the largest solid that matches all three views: the visual hull.

What it cannot recover: a pocket or blind hole that no view sees through (the hull fills it), and hidden
(dashed) lines are not read. Through-holes along a viewing axis are kept only when that view shows the hole as
an enclosed white region AND the drawing is a filled silhouette; line drawings are filled solid first, so their
holes are lost. The result is labelled with exactly this caveat.
"""
import base64
import io
from collections import deque

import numpy as np
from PIL import Image

from . import outline


def _image(src):
    if isinstance(src, Image.Image):
        return src
    if isinstance(src, str) and src.startswith("data:"):
        src = base64.b64decode(src.split(",", 1)[1])
    return Image.open(io.BytesIO(src))


def _largest(mask):
    """Largest 4-connected component (drops dimension text, arrows and title blocks)."""
    seen = np.zeros_like(mask)
    best, best_n = None, 0
    H, W = mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        comp, q = [], deque([(y0, x0)])
        seen[y0, x0] = True
        while q:
            y, x = q.popleft()
            comp.append((y, x))
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    q.append((yy, xx))
        if len(comp) > best_n:
            best, best_n = comp, len(comp)
    out = np.zeros_like(mask)
    if best:
        ys, xs = zip(*best)
        out[list(ys), list(xs)] = True
    return out


def silhouette(src, max_side=256):
    """Dark ink / filled part on a light background -> cropped boolean silhouette (row 0 = top of the image)."""
    im = _image(src).convert("L")
    im.thumbnail((max_side, max_side))
    g = np.asarray(im, float)
    # Otsu threshold
    hist = np.bincount(g.astype(int).ravel(), minlength=256).astype(float)
    p = hist / hist.sum()
    w = np.cumsum(p)
    mu = np.cumsum(p * np.arange(256))
    between = (mu[-1] * w - mu) ** 2 / np.maximum(w * (1 - w), 1e-12)
    ink = g < int(np.argmax(between))
    border = np.concatenate([ink[0], ink[-1], ink[:, 0], ink[:, -1]])
    if border.mean() > 0.5:                    # light part on a dark background
        ink = ~ink
    line_art = ink.mean() < 0.15
    m = _largest(outline.fill_holes(ink) if line_art else ink)
    if line_art:
        m = outline.fill_holes(m)
    ys, xs = np.nonzero(m)
    if not len(ys):
        raise ValueError("no part found in a view (expect dark lines or a dark filled shape on white)")
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1], line_art


def _resample(mask, rows, cols):
    im = Image.fromarray(mask.astype(np.uint8) * 255).resize((cols, rows), Image.NEAREST)
    return np.asarray(im) > 127


def carve(front, top, side, width_mm, voxels=96):
    """Visual hull on a voxel grid. front: (z, x) image rows top->bottom; top: (y, x) with y away from the viewer
    at the top of the image (third-angle layout); side: right view (z, y).

    The front view fixes the x and z size (its aspect ratio + width_mm). The top view's depth (y) is taken from
    its own aspect ratio against the shared x width; the side view is stretched to that y and the front z.
    Returns (occupancy[x, y, z], mm per voxel, report)."""
    fh, fw = front.shape
    th, tw = top.shape
    sh, sw = side.shape
    mm_px = width_mm / fw
    W, Hz = width_mm, fh * mm_px
    Dy = th * width_mm / tw                    # top view: rows are depth
    side_depth = sw * Hz / sh                  # what the side view says the depth is
    step = max(W, Dy, Hz) / voxels
    nx, ny, nz = (max(2, int(round(v / step))) for v in (W, Dy, Hz))
    F = _resample(front, nz, nx)[::-1].T       # [x, z], z up
    T = _resample(top, ny, nx)[::-1].T         # [x, y], y away (image top = far)
    S = _resample(side, nz, ny)[::-1].T        # [y, z]
    occ = F[:, None, :] & T[:, :, None] & S[None, :, :]
    report = {"size_mm": [round(W, 1), round(Dy, 1), round(Hz, 1)],
              "depth_mismatch_pct": round(100 * abs(side_depth - Dy) / max(Dy, 1e-9), 1),
              "voxel_mm": round(step, 2), "grid": [nx, ny, nz],
              "filled_pct_of_box": round(100 * occ.mean(), 1)}
    return occ, step, report


def surface(occ, step):
    """Boundary faces of the voxel solid -> watertight triangle mesh (mm, centred), then Taubin smoothing so the
    voxel staircase does not read as detail."""
    o = np.pad(occ, 1)
    quads = []
    # (axis, direction): face between voxel i (filled) and i+dir (empty)
    for ax in range(3):
        for sgn in (1, -1):
            nb = np.roll(o, -sgn, axis=ax)
            idx = np.argwhere(o & ~nb)
            if not len(idx):
                continue
            base = idx.astype(float)
            base[:, ax] += 0.5 + 0.5 * sgn          # the face plane
            u, v = [a for a in range(3) if a != ax]
            c = []
            for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1)):
                p = base.copy()
                p[:, u] += du
                p[:, v] += dv
                c.append(p)
            q = np.stack(c, 1)                       # (n, 4, 3)
            # outward winding: (u, v, ax) right-handed when sgn > 0
            right = (u, v, ax) in ((0, 1, 2), (1, 2, 0), (2, 0, 1))
            if right != (sgn > 0):
                q = q[:, ::-1]
            quads.append(q)
    q = np.concatenate(quads)
    pts = q.reshape(-1, 3)
    uniq, inv = np.unique(np.round(pts * 2).astype(np.int64), axis=0, return_inverse=True)
    V = uniq / 2.0
    Q = inv.reshape(-1, 4)
    F = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    # Taubin (lambda/mu) smoothing keeps volume better than plain Laplacian
    nbrs = [[] for _ in range(len(V))]
    for a, b in np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]):
        nbrs[a].append(b)
    ii = np.repeat(np.arange(len(V)), [len(n) for n in nbrs])
    jj = np.concatenate([np.asarray(n, int) for n in nbrs])
    deg = np.bincount(ii, minlength=len(V)).astype(float)
    for _ in range(6):
        for lam in (0.5, -0.53):
            avg = np.zeros_like(V)
            np.add.at(avg, ii, V[jj])
            V = V + lam * (avg / deg[:, None] - V)
    V = (V - 1) * step                             # undo the pad, to mm
    V -= (V.min(0) + V.max(0)) / 2
    return V, F


def three_view(front, top, side, width_mm=80.0, voxels=96):
    """Images (data URLs / bytes / PIL) of the front, top and right-side views -> (V, F, report)."""
    (f, la1), (t, la2), (s, la3) = silhouette(front), silhouette(top), silhouette(side)
    occ, step, rep = carve(f, t, s, float(width_mm), int(voxels))
    if not occ.any():
        raise ValueError("the three views do not overlap: check the order (front, top, right side)")
    V, F = surface(occ, step)
    rep["line_art_filled"] = bool(la1 or la2 or la3)
    rep["note"] = ("Visual hull: the largest solid whose front, top and side silhouettes match the drawing. Hidden "
                   "pockets and blind holes are filled; dashed hidden lines are not read"
                   + ("; line drawings were filled solid, so their through-holes are lost" if rep["line_art_filled"] else "")
                   + ". Width is " + ("given" if width_mm else "assumed") + f" ({width_mm} mm).")
    if rep["depth_mismatch_pct"] > 10:
        rep["warning"] = (f"top and side views disagree on depth by {rep['depth_mismatch_pct']}%: views may be in the "
                          "wrong order or drawn at different scales")
    return V, F, rep
