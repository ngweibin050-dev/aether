"""Finding the separate views on a sheet and matching them (side / top / front), for classifying an upload.

vision.upload_kind uses this to tell a three-view sheet (sent to the OpenCascade CAD pipeline, cad/) from a single
machine drawing. No solid is made here.

1. ink(): Otsu threshold.
2. panels(): ink blurred on a coarse grid, connected blobs = views; blobs touching the sheet edge, and blobs much
   smaller than the biggest (text, logos, dimension numbers), are dropped.
3. view_mask(): per view, the ground line is removed, small gaps are closed and the outline is filled solid.
4. match(): every assignment of views to side / top / front is scored by how well their sizes agree at one scale.
"""
import base64
import io
import itertools

import numpy as np
from PIL import Image

from . import outline


def _image(src):
    if isinstance(src, Image.Image):
        return src
    if isinstance(src, str) and src.startswith("data:"):
        src = base64.b64decode(src.split(",", 1)[1])
    return Image.open(io.BytesIO(src))


def label4(m):
    """4-connected components of a boolean image -> (label image 0 = background / 1..n, n), numbered in the raster
    order of each component's first pixel. Works on horizontal runs, not pixels: runs that overlap in neighbouring
    rows are joined (union-find), so a 1400 x 300 view takes milliseconds (the pixel-wise version took ~10 s)."""
    m = np.asarray(m, bool)
    H, W = m.shape
    d = np.diff(np.pad(m, ((0, 0), (1, 1))).astype(np.int8), axis=1)
    rs, cs = np.nonzero(d == 1)
    re_, ce = np.nonzero(d == -1)                          # same rows, same order as the starts
    n_runs = len(rs)
    lab = np.zeros((H, W), np.int32)
    if not n_runs:
        return lab, 0
    parent = list(range(n_runs))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    row_start = np.searchsorted(rs, np.arange(H + 1))
    for y in range(1, H):
        a0, a1, b0, b1 = row_start[y - 1], row_start[y], row_start[y], row_start[y + 1]
        i, j = a0, b0
        while i < a1 and j < b1:                          # two pointers over the runs of rows y-1 and y
            if cs[i] < ce[j] and cs[j] < ce[i]:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
            if ce[i] < ce[j]:
                i += 1
            else:
                j += 1
    roots = np.array([find(i) for i in range(n_runs)])
    first = {}
    ids = np.empty(n_runs, np.int32)
    for i, r in enumerate(roots):                          # runs come in raster order: first seen = first pixel
        ids[i] = first.setdefault(r, len(first) + 1)
    for i in range(n_runs):
        lab[rs[i], cs[i]:ce[i]] = ids[i]
    return lab, len(first)


def _gray(src, max_side):
    im = _image(src)
    if im.mode in ("P", "LA", "RGBA"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    im = im.convert("L")
    s = max_side / max(im.size)
    if s < 1:
        im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
    return np.asarray(im, float)


def _otsu(g):
    hist = np.bincount(np.clip(g, 0, 255).astype(int).ravel(), minlength=256).astype(float)
    p = hist / hist.sum()
    w = np.cumsum(p)
    mu = np.cumsum(p * np.arange(256))
    between = (mu[-1] * w - mu) ** 2 / np.maximum(w * (1 - w), 1e-12)
    return int(np.argmax(between))


def ink(g):
    m = g <= _otsu(g)
    if np.concatenate([m[0], m[-1], m[:, 0], m[:, -1]]).mean() > 0.5:
        m = ~m
    return m


def _dilate(m, r):
    out = m.copy()
    for _ in range(r):
        o = out.copy()
        o[1:] |= out[:-1]
        o[:-1] |= out[1:]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


def _erode(m, r):
    return ~_dilate(~m, r)


def _label(m):
    """4-connected components -> list of (count, (y0, x0, y1, x1), touches_border)."""
    H, W = m.shape
    lab = np.zeros(m.shape, int)
    out = []
    for y0, x0 in zip(*np.nonzero(m)):
        if lab[y0, x0]:
            continue
        k = len(out) + 1
        lab[y0, x0] = k
        stack = [(y0, x0)]
        ys, xs = [], []
        while stack:
            y, x = stack.pop()
            ys.append(y)
            xs.append(x)
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = k
                    stack.append((yy, xx))
        b = (min(ys), min(xs), max(ys) + 1, max(xs) + 1)
        out.append((len(ys), b, b[0] == 0 or b[1] == 0 or b[2] == H or b[3] == W))
    return out


def panels(g, coarse=160):
    """Bounding boxes (y0, x0, y1, x1, in g's pixels) of the separate drawings on the sheet.
    First pass: blobs touching the sheet edge are scan noise and straight runs over 20 % of the width are ground
    lines (a car blueprint). If that leaves fewer than three views, the drawing itself may reach the edge (a clean
    line drawing cropped tight, e.g. NASA's X-3 three-view, whose wing tips touch it) and long straight body lines
    (a fuselage) are not ground lines: a second pass pads the sheet with paper and only drops runs over half the
    width (one ground line under two views)."""
    out = _panels(g, coarse, 0.2)
    if len(out) >= 3:
        return out
    p = max(8, int(0.03 * max(g.shape)))
    gp = np.pad(g, p, constant_values=float(np.percentile(g, 99)))
    H, W = g.shape
    out2 = [(max(0, y0 - p), max(0, x0 - p), min(H, y1 - p), min(W, x1 - p)) for y0, x0, y1, x1 in _panels(gp, coarse, 0.5)]
    return out2 if len(out2) > len(out) else out


def _panels(g, coarse, frac):
    m = _drop_long_lines(ink(g), frac)             # a ground line shared by two views would join them
    H, W = m.shape
    f = max(1, int(np.ceil(max(H, W) / coarse)))
    h, w = H // f, W // f
    c = m[:h * f, :w * f].reshape(h, f, w, f).mean((1, 3)) > 0.02
    c = _dilate(c, 1)
    comps = [x for x in _label(c) if not x[2]]
    if not comps:
        return []
    big = max(b[2] - b[0] for _, b, _ in comps) * max(b[3] - b[1] for _, b, _ in comps)
    keep = [b for _, b, _ in comps if (b[2] - b[0]) * (b[3] - b[1]) > 0.08 * big]
    return [(max(0, y0 * f - f), max(0, x0 * f - f), min(H, y1 * f + f), min(W, x1 * f + f)) for y0, x0, y1, x1 in keep]


def _drop_long_lines(m, frac):
    """Erase straight horizontal runs longer than frac of the width (ground lines, frame lines), +-1 row."""
    m = m.copy()
    W = m.shape[1]
    band = m.copy()
    band[1:] |= m[:-1]
    band[:-1] |= m[1:]
    for y in np.nonzero(band.sum(1) >= frac * W)[0]:
        d = np.diff(np.concatenate([[0], band[y].astype(int), [0]]))
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            if b - a >= frac * W:
                m[max(0, y - 1):y + 2, a:b] = False
    return m


def _in_thin_shape(m, y, cols, near=(3, 10), share=0.5):
    """True when the horizontal line at row y is one side of a thin closed shape, not a lone ruled line: in at least
    `share` of its columns another stroke runs 3-10 px above or below it. A wing seen edge-on in a front view is two or
    three such strokes (outline + centre line, NASA's X-2: 3 strokes within 10 px in every column); a ground line has
    nothing beside it except where a wheel stands on it."""
    H = m.shape[0]
    if not len(cols):
        return False
    up = m[max(y - near[1], 0):max(y - near[0] + 1, 0), cols].any(0)
    dn = m[min(y + near[0], H):min(y + near[1] + 1, H), cols].any(0)
    return float(np.mean(up | dn)) >= share


def _drop_ground_line(m):
    """Remove straight horizontal lines spanning most of the view (ground / centre lines). A thin line drawn at an
    angle to the pixel grid, or resampled, wanders between two rows and breaks up, so rows are judged together
    with their neighbours. A row that is one side of a thin closed shape (a wing seen edge-on spans the whole front
    view) is not a ground line (_in_thin_shape)."""
    m0 = m
    m = m.copy()
    W = m.shape[1]
    band = m0.copy()
    band[1:] |= m0[:-1]
    band[:-1] |= m0[1:]
    for y in np.nonzero(band.sum(1) >= 0.8 * W)[0]:
        if _in_thin_shape(m0, y, np.nonzero(band[y])[0]):
            continue
        m[max(0, y - 1):y + 2] = False
    return m


def _drop_ground_under(m, min_frac=0.4, max_thick=5, bottom_frac=0.15):
    """The ground line an object stands on is not part of the object. A straight horizontal ink run in the lowest
    bottom_frac of the view's ink, at least min_frac of the view's width long and at most max_thick px thick, is
    erased, except in the columns where ink rises more than 3 px above it (the wheels standing on it). Shorter than
    _drop_ground_line's 80 %: NASA's X-3 side view draws its ground line over ~70 % of the view, and filled it became
    part of the side silhouette."""
    m = m.copy()
    H, W = m.shape
    ys = np.nonzero(m.any(1))[0]
    if not len(ys):
        return m
    top_ink, bot = ys.min(), ys.max()
    for y in range(bot, max(bot - int(bottom_frac * (bot - top_ink + 1)) - 1, 0), -1):
        band = m[max(y - 1, 0):y + 2].any(0)
        d = np.diff(np.r_[0, band.astype(int), 0])
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            if b - a < min_frac * W:
                continue
            lo, hi = max(y - max_thick // 2 - 1, 0), min(y + max_thick // 2 + 2, H)
            thick = m[max(y - 8, 0):min(y + 9, H), a:b].sum(0)
            if np.mean(thick <= max_thick + 1) < 0.8:             # not thin: a body edge, not a ground line
                continue
            if _in_thin_shape(m, y, np.arange(a, b)):              # one side of a wing seen edge-on
                continue
            # only a line that runs PAST the object's own outline is ground: the object's extent is measured in the band
            # just above the line; a part's own flat bottom edge spans exactly that band and stays
            band_h = max(6, int(0.1 * (bot - top_ink + 1)))
            obj = np.nonzero(m[max(lo - band_h, 0):max(lo - 1, 0)].any(0))[0]
            tol = max(3, int(0.01 * W))
            if not len(obj) or not (a < obj.min() - tol or b > obj.max() + tol):
                continue
            above = m[max(lo - 3, 0):lo, a:b].any(0)               # something stands on it here (a wheel)
            cols = np.arange(a, b)[~above]
            m[lo:hi, cols] = False
    return m


def _body_and_parts(mask, min_frac=0.002, min_px=40, margin=0.15):
    """The view's main outline plus every separate outline that belongs to the same object: a nose wheel drawn apart
    from the fuselage (a largest-component filter drops it). A separate outline is kept if it is at least min_frac of the main
    area (text, arrows, dimension numbers are smaller), lies inside the main outline's box grown by `margin`, and does
    not touch the edge of the view's crop (a neighbouring view reaching into this crop always does: NASA's X-3 front
    view fin reaches into the top view's box)."""
    lab_, n = label4(mask)
    if not n:
        return np.zeros_like(mask)
    area = np.bincount(lab_.ravel(), minlength=n + 1)
    area[0] = 0
    main = int(area.argmax())
    ys, xs = np.nonzero(lab_ == main)
    H, W = mask.shape
    my, mx = margin * (ys.max() - ys.min() + 1), margin * (xs.max() - xs.min() + 1)
    keep = [main]
    for k in np.nonzero(area >= max(min_px, min_frac * area.max()))[0]:
        if k == main:
            continue
        ky, kx = np.nonzero(lab_ == k)
        if ky.min() == 0 or kx.min() == 0 or ky.max() == H - 1 or kx.max() == W - 1:
            continue
        if ky.min() >= ys.min() - my and ky.max() <= ys.max() + my and kx.min() >= xs.min() - mx and kx.max() <= xs.max() + mx:
            keep.append(int(k))
    return np.isin(lab_, keep)


def view_mask(g, box, close=2):
    """One view's ink -> filled silhouette, cropped. Returns (mask, (y0, x0) of the crop in g)."""
    y0, x0, y1, x1 = box
    m = ink(g[y0:y1, x0:x1])
    m = _drop_ground_line(m)
    m = _drop_ground_under(m)
    closed = _dilate(m, close)
    filled = outline.fill_holes(closed)
    filled = _erode(filled, close)
    filled = _body_and_parts(filled)
    ys, xs = np.nonzero(filled)
    if not len(ys):
        return None, (y0, x0)
    return filled[ys.min():ys.max() + 1, xs.min():xs.max() + 1], (y0 + ys.min(), x0 + xs.min())


def match(masks):
    """masks: list of filled silhouettes. -> (side, top, front, rest, error) indices + size disagreement (0..1)."""
    best = None
    n = len(masks)
    for s, t, f in itertools.permutations(range(n), 3):
        (sh, sw), (th, tw), (fh, fw) = masks[s].shape, masks[t].shape, masks[f].shape
        e = (abs(sw - tw) / max(sw, tw) + abs(sh - fh) / max(sh, fh) + abs(th - fw) / max(th, fw)) / 3
        # a car / machine side view is the longest view; prefer it as "side" when sizes tie
        e += 0.001 * (sh / sw)
        if best is None or e < best[-1]:
            best = (s, t, f, [i for i in range(n) if i not in (s, t, f)], e)
    return best
