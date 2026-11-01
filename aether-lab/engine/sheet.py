"""One sheet with several orthographic views (a car blueprint: side, front, rear, top) -> the views, matched.

1. ink(): Otsu threshold; halftone / scan noise at the paper edge is dropped later because it touches the border.
2. panels(): ink blurred on a coarse grid, connected blobs = views. Blobs touching the sheet edge, and blobs much
   smaller than the biggest (text, logos, dimension numbers), are dropped.
3. view_mask(): per view, the long straight ground line (a row of ink longer than 85% of the view) is removed
   first - otherwise filling the outline would also fill the air under the car between the wheels - then small
   gaps are closed and the outline is filled solid.
4. match(): every assignment of views to side (z, x), top (y, x) and front (z, y) is scored by how well their sizes
   agree when drawn at one scale (side width = top width, side height = front height, top height = front width).
   This works for any layout (third angle, first angle, car sheets) without being told which view is which.
5. Then hull.carve() intersects the three extrusions; flips of the top / front view are tried and the orientation
   that keeps the most volume wins (a wrong flip cuts the solid away).
"""
import itertools

import numpy as np
from PIL import Image

from . import hull, outline


def _gray(src, max_side):
    im = hull._image(src)
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
    from the fuselage (hull._largest dropped it). A separate outline is kept if it is at least min_frac of the main
    area (text, arrows, dimension numbers are smaller), lies inside the main outline's box grown by `margin`, and does
    not touch the edge of the view's crop (a neighbouring view reaching into this crop always does: NASA's X-3 front
    view fin reaches into the top view's box)."""
    lab_, n = hull.label4(mask)
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


def carve_best(side, top, front, length_mm, voxels):
    """hull.carve(front=side view, top=top view, side=front view) with the flip that keeps the most volume."""
    best = None
    for ft in (False, True):          # top view mirrored along the length
        for ff in (False, True):      # front view mirrored across the width
            T = top[:, ::-1] if ft else top
            F = front[:, ::-1] if ff else front
            occ, step, rep = hull.carve(side, T, F, length_mm, voxels)
            if best is None or occ.sum() > best[0].sum():
                best = (occ, step, rep, ft, ff)
    return best


def round_sections(occ, n=2.6, window=9):
    """Real bodies are rounded in cross-section; a visual hull is square there (each view only bounds it). Above the
    middle of the body's height, every station along the length is kept inside a superellipse through the
    station's widest half-width and its top, so the shoulders curve into the roof. Below the middle (wheels, sills)
    nothing changes. The superellipse sizes are smoothed along the length so neighbouring stations do not step."""
    nx, ny, nz = occ.shape
    y = np.abs(np.arange(ny) - (ny - 1) / 2)
    z = np.arange(nz)
    on = occ.any((1, 2))
    W = np.where(on, [np.abs(np.nonzero(occ[i].any(1))[0] - (ny - 1) / 2).max() + 0.5 if on[i] else 0 for i in range(nx)], 0)
    zl = np.array([np.nonzero(occ[i].any(0))[0].min() if on[i] else 0 for i in range(nx)], float)
    zh = np.array([np.nonzero(occ[i].any(0))[0].max() + 0.5 if on[i] else 0 for i in range(nx)], float)
    k = np.ones(window) / window
    sm = lambda a: np.convolve(np.pad(a, window // 2, mode="edge"), k, "valid")
    Ws, zls, zhs = sm(W.astype(float)), sm(zl), sm(zh)
    out = occ.copy()
    for i in np.nonzero(on)[0]:
        zm = (zls[i] + zhs[i]) / 2
        Wi = max(Ws[i], W[i] * 0.98, 1)
        r = (y[:, None] / Wi) ** n + np.clip((z[None, :] - zm) / max(zh[i] - zm, 1), 0, None) ** n
        out[i] &= ~((z[None, :] > zm) & (r > 1))
    # the drawing's outlines are measured, the rounding is a guess: wherever rounding took something away that a
    # view shows (mirrors, wing tips, roof edge), give it back, so every view's outline stays the drawn one
    lost = occ.any(0) & ~out.any(0)                     # front view (y, z): restore along the length
    out |= occ & lost[None]
    lost = occ.any(1) & ~out.any(1)                     # side view (x, z): restore the voxel nearest the centre line
    for i, k in zip(*np.nonzero(lost)):
        js = np.nonzero(occ[i, :, k])[0]
        out[i, js[np.argmin(np.abs(js - (ny - 1) / 2))], k] = True
    lost = occ.any(2) & ~out.any(2)                     # top view (x, y): restore the lowest voxel
    for i, j in zip(*np.nonzero(lost)):
        out[i, j, np.nonzero(occ[i, j])[0].min()] = True
    return out


def _minmax3(m, r, xp, grow):
    """Cube erosion (grow False) or dilation (grow True) of a 3-D bool array by r cells, axis by axis, no wrap."""
    for ax in range(3):
        for _ in range(int(r)):
            a, b = [slice(None)] * 3, [slice(None)] * 3
            a[ax], b[ax] = slice(1, None), slice(None, -1)
            g = m.copy()
            if grow:
                g[tuple(a)] |= m[tuple(b)]
                g[tuple(b)] |= m[tuple(a)]
            else:                            # outside the grid counts as empty
                g[tuple(a)] &= m[tuple(b)]
                g[tuple(b)] &= m[tuple(a)]
                e0, e1 = [slice(None)] * 3, [slice(None)] * 3
                e0[ax], e1[ax] = 0, -1
                g[tuple(e0)] = False
                g[tuple(e1)] = False
            m = g
    return m


def blur_thick(field, core_r=3, reach=1, passes=2, xp=np):
    """The 1-px build's field, blurred (two [1 2 1] passes, as the coarse build) only within `reach` cells of a part at
    least 2 * core_r + 1 cells thick. A thin wing has no core and stays sharp (blur everywhere cost G's top view
    89.5 % of a 2-px wing tip); a car body loses the pixel terraces its outlines leave (car sheet: roughness 9.9 deg
    -> 8.2 deg; coarse build 6.0 deg). Returns (field, near: the cells blurred)."""
    from . import hull
    core = _minmax3(field > 0.5, core_r, xp, False)
    near = _minmax3(core, core_r + reach, xp, True)
    del core
    fb = hull._blur32(field, passes, xp)
    return xp.where(near, fb, field), near


def _cover(mask, rows, cols, aa=0):
    """Area coverage of each grid cell by a high-resolution mask (0..1): the drawn outline at sub-voxel accuracy.
    aa: [1 2 1]/4 passes over the mask first. At 1 px per voxel a cell IS a pixel, so the coverage is 0 or 1 and the
    surface keeps every pixel step as a terrace across the whole body (car sheet: roughness RMS 12.8 deg, 34 % of the
    surface bent > 10 deg); one pass turns each step into a ramp whose 0.5 level runs between the steps, leaves a
    straight edge where it is and keeps a 2-px wing (centre 0.75)."""
    m = mask.astype(np.float32)
    for _ in range(int(aa)):
        m = np.pad(m, 1)
        m = (m[:-2] + 2 * m[1:-1] + m[2:]) / 4
        m = (m[:, :-2] + 2 * m[:, 1:-1] + m[:, 2:]) / 4
    im = Image.fromarray(m, "F").resize((cols, rows), Image.BOX)
    return np.clip(np.asarray(im, np.float32), 0, 1)


def hull_field(side, top, front, ft, ff, shape, n=2.6, window=15):
    """The rounded visual hull as a smooth field on the voxel grid (sampled at voxel centres, > 0.5 inside), not as
    on/off voxels, so the surface taken from it has no voxel terraces.

    1. Each view's outline as area coverage of the grid cells (sub-voxel accurate), extruded across the solid; the
       hull is where all three are inside: H = min(side, top, front).
    2. Rounding (as round_sections, but continuous): above the middle of the body height every station is kept inside
       a superellipse through its half-width (top view) and its top (side view), sizes smoothed along the length.
    3. Wherever the rounding removed something a view shows (mirrors, roof edge, wing tips) it is given back, so
       every view's outline stays the drawn one."""
    nx, ny, nz = shape
    T = top[:, ::-1] if ft else top
    Fr = front[:, ::-1] if ff else front
    Cs = _cover(side, nz, nx)[::-1].T                           # [x, z]
    Ct = _cover(T, ny, nx)[::-1].T                              # [x, y]
    Cf = _cover(Fr, nz, ny)[::-1].T                             # [y, z]
    H = np.minimum(np.minimum(Cs[:, None, :], Ct[:, :, None]), Cf[None, :, :])
    yc_ = np.arange(ny) + 0.5
    zc_ = np.arange(nz) + 0.5
    on = Cs.max(1) > 0.5
    W = Ct.sum(1) / 2                                           # half-width (voxels), sub-voxel
    yc = np.where(Ct.sum(1) > 0, (Ct * yc_).sum(1) / np.maximum(Ct.sum(1), 1e-6), ny / 2)
    a = np.argmax(Cs > 0, 1)
    b = nz - 1 - np.argmax(Cs[:, ::-1] > 0, 1)
    r_ = np.arange(nx)
    zl = a + 1 - Cs[r_, a]
    zh = b + Cs[r_, b]
    k = np.ones(window) / window
    sm = lambda v: np.convolve(np.pad(v, window // 2, mode="edge"), k, "valid")
    Ws, zls, zhs, ycs = sm(W), sm(zl), sm(zh), sm(yc)
    zm = (zls + zhs) / 2
    Wi = np.maximum(np.maximum(Ws, W * 0.98), 1)[:, None, None]
    Hi = np.maximum(zh - zm, 1)[:, None, None]
    dy = np.abs(yc_[None, :, None] - ycs[:, None, None]) / Wi
    dz = np.clip(zc_[None, None, :] - zm[:, None, None], 0, None) / Hi
    r = (dy ** n + dz ** n) ** (1 / n)
    S = np.clip(0.5 + (1 - r) * np.minimum(Wi, Hi), 0, 1)       # ~ signed distance in voxels, like the coverage
    S[~on] = 0
    R = np.minimum(H, S).astype(np.float32)
    # give back what a view shows but the rounding took
    lost = (H.max(0) > 0.5) & (R.max(0) <= 0.5)                 # front view (y, z): along the length
    R = np.maximum(R, np.where(lost[None], H, 0))
    lost = (H.max(1) > 0.5) & (R.max(1) <= 0.5)                 # side view (x, z): a thin web on the centre line
    slab = np.clip(1.5 - np.abs(yc_[None, :] - ycs[:, None]), 0, 1)[:, :, None]
    R = np.maximum(R, np.where(lost[:, None, :], np.minimum(H, slab), 0))
    lost = (H.max(2) > 0.5) & (R.max(2) <= 0.5)                 # top view (x, y): the lowest layer
    zlo = np.argmax(H > 0.5, 2)
    slab = np.clip(1.5 - np.abs(zc_[None, None, :] - (zlo[..., None] + 0.5)), 0, 1)
    R = np.maximum(R, np.where(lost[..., None], np.minimum(H, slab), 0))
    return R.astype(np.float32)


def hull_field_slabs(side, top, front, ft, ff, shape, n=2.6, window=15, slab=64, xp=np, aa=0):
    """hull_field computed slab by slab along the length (identical numbers): its only global input, what the front
    view restores along x, is gathered in a first pass; everything else is local to a station. Peak memory is one
    slab plus the float32 result, so a 1-px-per-voxel grid (1400 x 480 x 280) fits (hull_field needed ~10 GB).
    xp: numpy, or cupy on a GPU (Modal) for the 3-D work; the result is an xp array."""
    nx, ny, nz = shape
    T = top[:, ::-1] if ft else top
    Fr = front[:, ::-1] if ff else front
    Cs = _cover(side, nz, nx, aa)[::-1].T
    Ct = _cover(T, ny, nx, aa)[::-1].T
    Cf = _cover(Fr, nz, ny, aa)[::-1].T
    yc_ = np.arange(ny) + 0.5
    zc_ = np.arange(nz) + 0.5
    on = Cs.max(1) > 0.5
    W = Ct.sum(1) / 2
    yc = np.where(Ct.sum(1) > 0, (Ct * yc_).sum(1) / np.maximum(Ct.sum(1), 1e-6), ny / 2)
    a = np.argmax(Cs > 0, 1)
    b = nz - 1 - np.argmax(Cs[:, ::-1] > 0, 1)
    r_ = np.arange(nx)
    zl = a + 1 - Cs[r_, a]
    zh = b + Cs[r_, b]
    k = np.ones(window) / window
    sm = lambda v: np.convolve(np.pad(v, window // 2, mode="edge"), k, "valid")
    Ws, zls, zhs, ycs = sm(W), sm(zl), sm(zh), sm(yc)
    zm = (zls + zhs) / 2
    Wi_all = np.maximum(np.maximum(Ws, W * 0.98), 1)
    Hi_all = np.maximum(zh - zm, 1)
    Cs, Ct, Cf, yc_, zc_, ycs, zm, on, Wi_all, Hi_all = (xp.asarray(v) for v in (Cs, Ct, Cf, yc_, zc_, ycs, zm, on, Wi_all, Hi_all))

    def core(i0, i1):
        H = xp.minimum(xp.minimum(Cs[i0:i1, None, :], Ct[i0:i1, :, None]), Cf[None, :, :])
        Wi, Hi = Wi_all[i0:i1, None, None], Hi_all[i0:i1, None, None]
        dy = xp.abs(yc_[None, :, None] - ycs[i0:i1, None, None]) / Wi
        dz = xp.clip(zc_[None, None, :] - zm[i0:i1, None, None], 0, None) / Hi
        r = (dy ** n + dz ** n) ** (1 / n)
        S = xp.clip(0.5 + (1 - r) * xp.minimum(Wi, Hi), 0, 1)
        S[~on[i0:i1]] = 0
        return H, xp.minimum(H, S).astype(xp.float32)
    Hmax0 = xp.zeros((ny, nz), xp.float32)
    Rmax0 = xp.zeros((ny, nz), xp.float32)
    for i0 in range(0, nx, slab):
        H, R = core(i0, min(nx, i0 + slab))
        Hmax0 = xp.maximum(Hmax0, H.max(0))
        Rmax0 = xp.maximum(Rmax0, R.max(0))
    lost_f = (Hmax0 > 0.5) & (Rmax0 <= 0.5)
    out = xp.zeros((nx, ny, nz), xp.float32)
    for i0 in range(0, nx, slab):
        i1 = min(nx, i0 + slab)
        H, R = core(i0, i1)
        R = xp.maximum(R, xp.where(lost_f[None], H, 0))                              # front view: along the length
        lost = (H.max(1) > 0.5) & (R.max(1) <= 0.5)                                 # side view: centre-line web
        web = xp.clip(1.5 - xp.abs(yc_[None, :] - ycs[i0:i1, None]), 0, 1)[:, :, None]
        R = xp.maximum(R, xp.where(lost[:, None, :], xp.minimum(H, web), 0))
        lost = (H.max(2) > 0.5) & (R.max(2) <= 0.5)                                 # top view: the lowest layer
        zlo = xp.argmax(H > 0.5, 2)
        low = xp.clip(1.5 - xp.abs(zc_[None, None, :] - (zlo[..., None] + 0.5)), 0, 1)
        out[i0:i1] = xp.maximum(R, xp.where(lost[..., None], xp.minimum(H, low), 0))
    return out


def _circle_fit(x, y):
    """Algebraic least-squares circle (Kasa)."""
    A = np.c_[x, y, np.ones_like(x)]
    b = x ** 2 + y ** 2
    (a, c, d), *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = a / 2, c / 2
    return cx, cy, float(np.sqrt(max(d + cx ** 2 + cy ** 2, 0)))


def wheels(side, front):
    """Wheels of a vehicle: in the side view the lowest parts of the outline are the tyre bottoms (between them
    the sill sits higher); a circle fitted to each tyre's bottom arc gives centre and radius. The front view's
    lowest band gives the tyre's outer and inner edges across the width. All in view pixels; [] if not a vehicle."""
    h, w = side.shape
    bottom = np.array([np.nonzero(side[:, c])[0].max() if side[:, c].any() else -1 for c in range(w)], float)
    ground = bottom.max()
    mid = bottom[int(w * 0.35):int(w * 0.65)]
    sill = np.median(mid[mid >= 0]) if (mid >= 0).any() else ground
    gap = ground - sill
    if gap < 0.02 * h:                       # no wheels standing below the body line
        return []
    low = bottom > sill + 0.35 * gap
    d = np.diff(np.concatenate([[0], low.astype(int), [0]]))
    segs = []
    for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
        if segs and a - segs[-1][1] < 0.04 * w:          # one tyre split by a notch (ground line removed there)
            segs[-1][1] = b
        else:
            segs.append([a, b])
    out = []
    for a, b in segs:
        if b - a < 0.03 * w:
            continue
        xs = np.arange(a, b).astype(float)
        keep = bottom[a:b] > sill + 0.35 * gap
        cx, cy, r = _circle_fit(xs[keep], bottom[a:b][keep])
        r = ground - cy                      # the tyre stands on the ground line
        if not (0.04 * w < r < 0.2 * w):
            continue
        out.append({"cx": cx, "cy": cy, "r": r})
    if len(out) < 2:
        return []
    # across the width: the front view's lowest rows hold only the two tyres
    fh, fw = front.shape
    band = front[int(fh * 0.97):].any(0)
    d = np.diff(np.concatenate([[0], band.astype(int), [0]]))
    runs = [(a, b) for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]) if b - a > 0.03 * fw]
    if len(runs) >= 2:
        (l0, l1), (r0, r1) = runs[0], runs[-1]
        tyre = ((l1 - l0) + (r1 - r0)) / 2
        outer = ((fw / 2 - l0) + (r1 - fw / 2)) / 2
    else:
        tyre, outer = 0.12 * fw, 0.46 * fw
    for wl in out:
        wl.update(outer=float(outer), width=float(tyre))
    return out


def _cast(fb, ax, i, j, from_max):
    """Rays along axis ax through the blurred occupancy fb (padded by 3) at the other two voxel indices (i, j):
    sub-voxel position (voxel units, voxel k spans [k, k + 1]) where the ray first meets the surface (iso 0.5)
    coming from the max (or min) side, and whether it hits at all."""
    col = np.moveaxis(fb, ax, -1)[i + 3, j + 3]                     # the other two axes keep their order
    n = col.shape[1]
    inside = col > 0.5
    hit = inside.any(1)
    if from_max:
        k = n - 1 - np.argmax(inside[:, ::-1], 1)                    # last inside sample
        k2 = np.minimum(k + 1, n - 1)
        va, vb = col[np.arange(len(k)), k], col[np.arange(len(k)), k2]
        t = np.clip((va - 0.5) / np.maximum(va - vb, 1e-6), 0, 1)
        pos = k + t
    else:
        k = np.argmax(inside, 1)
        k2 = np.maximum(k - 1, 0)
        va, vb = col[np.arange(len(k)), k], col[np.arange(len(k)), k2]
        t = np.clip((va - 0.5) / np.maximum(va - vb, 1e-6), 0, 1)
        pos = k - t
    return pos - 3 + 0.5, hit


def _ink_in(g, mask, at, margin=1):
    h, w = mask.shape
    y0, x0 = at
    return ink(g[y0:y0 + h, x0:x0 + w]) & _erode(mask, margin)


def _runs(m):
    e = np.flatnonzero(np.diff(np.r_[0, m.astype(int), 0]))
    return zip(e[::2], e[1::2])


def _close_runs(m, gap, allowed):
    """Fill False runs no longer than gap that have True on both sides (and are allowed)."""
    m = m.copy()
    for a, b in _runs(~m):
        if b - a <= gap and a > 0 and b < len(m) and allowed[a:b].all():
            m[a:b] = True
    return m


def _drop_short(m, n):
    m = m.copy()
    for a, b in _runs(m):
        if b - a < n:
            m[a:b] = False
    return m


def seams_on_surface(fb, grid, curves, view, flip, from_max, lift=0.6, max_jump=3.0, smooth=31):
    """Smooth 2-D curves of one view (pixels, x right / y down, image size (h, w) stored with them) laid onto the
    surface along that view's axis. Returns segments (n, 6) in voxel units."""
    nx, ny, nz = grid
    out = []
    for P, (h, w) in curves:
        gone = np.isnan(P).any(1)
        x, y = np.nan_to_num(P[:, 0]), np.nan_to_num(P[:, 1])
        if flip:
            x = w - 1 - x
        if view == "side":                     # cols -> x, rows -> z, cast along y
            a, b = (x + 0.5) * nx / w, nz - (y + 0.5) * nz / h
            ia, ib = np.clip(a.astype(int), 0, nx - 1), np.clip(b.astype(int), 0, nz - 1)
            pos, hit = _cast(fb, 1, ia, ib, from_max)
            Q = np.c_[a, pos + (lift if from_max else -lift), b]
        elif view == "top":                    # cols -> x, rows -> y (image top = far), cast down along z
            a, b = (x + 0.5) * nx / w, ny - (y + 0.5) * ny / h
            ia, ib = np.clip(a.astype(int), 0, nx - 1), np.clip(b.astype(int), 0, ny - 1)
            pos, hit = _cast(fb, 2, ia, ib, True)
            Q = np.c_[a, b, pos + lift]
        else:                                  # an end view: cols -> y, rows -> z, cast along x
            a, b = (x + 0.5) * ny / w, nz - (y + 0.5) * nz / h
            ia, ib = np.clip(a.astype(int), 0, ny - 1), np.clip(b.astype(int), 0, nz - 1)
            pos, hit = _cast(fb, 0, ia, ib, from_max)
            Q = np.c_[pos + (lift if from_max else -lift), a, b]
        # the depth each point lands at follows the faceted surface; smooth it along the curve (only between
        # neighbours that land on the same stretch of surface) so the line runs evenly over the body
        hit = hit & ~gone
        # a view only places a line reliably where the surface faces that view (else the ray grazes it and the
        # line's depth is a guess): keep points whose surface normal is within ~60 deg of the view axis
        d_ax = {"side": 1, "top": 2}.get(view, 0)
        ijk = np.clip(np.round(Q - 0.5).astype(int) + 3, 0, np.array(fb.shape) - 1)
        # field gradient (points into the body) at these points only: central differences, no full gradient field
        lo_, hi_ = np.maximum(ijk - 1, 0), np.minimum(ijk + 1, np.array(fb.shape) - 1)
        g = np.stack([fb[hi_[:, 0], ijk[:, 1], ijk[:, 2]] - fb[lo_[:, 0], ijk[:, 1], ijk[:, 2]],
                      fb[ijk[:, 0], hi_[:, 1], ijk[:, 2]] - fb[ijk[:, 0], lo_[:, 1], ijk[:, 2]],
                      fb[ijk[:, 0], ijk[:, 1], hi_[:, 2]] - fb[ijk[:, 0], ijk[:, 1], lo_[:, 2]]], -1) / 2
        facing = np.abs(g[:, d_ax]) > 0.6 * (np.linalg.norm(g, axis=1) + 1e-9)
        hit = hit & facing
        d_ax = {"side": 1, "top": 2}.get(view, 0)
        dep = Q[:, d_ax]
        jump = np.abs(np.roll(dep, -1) - dep) > max_jump * 0.5
        if smooth > 1 and len(dep) > smooth:
            num = np.zeros_like(dep)
            den = np.zeros_like(dep)
            h_ = smooth // 2
            for o in range(-h_, h_ + 1):
                # a neighbour counts only if no depth jump lies between it and this point
                blocked = np.zeros(len(dep), bool)
                for q in range(min(o, 0), max(o, 0)):
                    blocked |= np.roll(jump, -q)
                ok_ = np.roll(hit, -o) & ~blocked
                wgt = np.exp(-0.5 * (o / (h_ / 2 + 1e-9)) ** 2) * ok_
                num += wgt * np.roll(dep, -o)
                den += wgt
            Q[:, d_ax] = np.where(den > 0, num / np.maximum(den, 1e-9), dep)
        Q2 = np.roll(Q, -1, 0)
        flat = np.linalg.norm(np.delete(Q2 - Q, d_ax, 1), axis=1)
        steep = np.abs(Q2[:, d_ax] - Q[:, d_ax]) > np.maximum(0.25, 2.5 * flat)   # grazing: depth not reliable
        # the facing / hit tests flicker where a surface is near the limit: fill short gaps inside a line and drop
        # short leftover pieces, so a line is drawn continuous or not at all (no dashes)
        good = hit & ~steep & ~jump
        good = _close_runs(good, 8, ~gone & ~jump)
        good = _drop_short(good, 10)
        ok = good & np.roll(good, -1) & ~jump & (np.linalg.norm(Q2 - Q, axis=1) < max_jump)
        out.append(np.c_[Q[ok], Q2[ok]])
    return np.concatenate(out) if out else np.zeros((0, 6))


def _boundary(m):
    return m & ~_erode(m, 1)


def outline_error(mask, P, mm_per_px):
    """Distance between the drawn outline and the model's outline in that view, in mm: mean and 95th percentile
    over the drawn outline (how far each drawn outline point is from the model's outline)."""
    a = np.argwhere(_boundary(mask)).astype(float)
    b = np.argwhere(_boundary(P)).astype(float)
    if not len(a) or not len(b):
        return None
    d = np.empty(len(a))
    for i in range(0, len(a), 512):
        d[i:i + 512] = np.sqrt(((a[i:i + 512, None, :] - b[None, :, :]) ** 2).sum(-1)).min(1)
    d *= mm_per_px
    return {"mean_mm": round(float(d.mean()), 3), "p95_mm": round(float(np.percentile(d, 95)), 3),
            "max_mm": round(float(d.max()), 3)}


def nose_left(side):
    """A vehicle's nose is the lower end of its side view (bonnet / splitter vs rear deck and wing)."""
    h, w = side.shape
    top = np.array([np.argmax(side[:, c]) if side[:, c].any() else h for c in range(w)])
    k = max(2, int(0.1 * w))
    return top[:k].mean() > top[-k:].mean()          # larger row index = lower


def mesh_view_masks(meshes, frame):
    """The delivered model as each view sees it: every triangle of every mesh [(V, F)] (mm, the hull's centred frame)
    filled into that view's own pixels, with the mapping the panel lines use (voxel = (V + centre) / step; a view
    pixel's centre is voxel (px + 0.5) * cells / px). Returns {"side": mask, "top": mask, "front": mask} in the drawn
    masks' frames (flips undone), for the OFFICIAL view match: what the UI receives, not the voxel field. A pixel is
    covered when its centre lies in (or on) a triangle (the standard rasterisation rule, for every triangle size)."""
    nx, ny, nz = frame["grid"]
    out = {}
    for role, (h, w), flip in (("side", frame["shapes"]["side"], False), ("top", frame["shapes"]["top"], frame["flips"]["top"]),
                               ("front", frame["shapes"]["front"], frame["flips"]["front"])):
        out[role] = np.zeros((h, w), bool)
        for V, F in meshes:
            if not len(F):
                continue
            vox = (np.asarray(V, float) + frame["centre"]) / frame["step"]
            if role == "side":
                X, Y = vox[:, 0] * w / nx - 0.5, (nz - vox[:, 2]) * h / nz - 0.5
            elif role == "top":
                X, Y = vox[:, 0] * w / nx - 0.5, (ny - vox[:, 1]) * h / ny - 0.5
            else:
                X, Y = vox[:, 1] * w / ny - 0.5, (nz - vox[:, 2]) * h / nz - 0.5
            if flip:
                X = w - 1 - X
            P = np.stack([X, Y], -1)[np.asarray(F, int)]
            ext = (P.max(1) - P.min(1)).max(1)
            acc = out[role]
            done = np.zeros(len(P), bool)
            for win in (5, 13, 33):                       # vectorised in windows of win x win pixel centres
                sel = ~done & (ext < win - 1)
                acc |= _fill_small_triangles(P[sel], h, w, win=win)
                done |= sel
            for tri in P[~done]:                           # the few larger ones: same centre rule, one by one
                x0, y0 = np.floor(tri.min(0)).astype(int)
                x1, y1 = np.ceil(tri.max(0)).astype(int) + 1
                x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
                if x1 <= x0 or y1 <= y0:
                    continue
                gx, gy = np.meshgrid(np.arange(x0, x1, dtype=float), np.arange(y0, y1, dtype=float))
                (ax, ay), (bx, by), (cx, cy) = tri
                d1 = (bx - ax) * (gy - ay) - (by - ay) * (gx - ax)
                d2 = (cx - bx) * (gy - by) - (cy - by) * (gx - bx)
                d3 = (ax - cx) * (gy - cy) - (ay - cy) * (gx - cx)
                inside = ((d1 >= 0) & (d2 >= 0) & (d3 >= 0)) | ((d1 <= 0) & (d2 <= 0) & (d3 <= 0))
                acc[y0:y1, x0:x1] |= inside
            out[role] = acc
    return out


def outline_vertices(V, frame, band_px=1):
    """Vertices (mm, the hull's centred frame) whose projection lies within band_px of a drawn view's outline, in any
    view. Nothing may move those (part seams, recesses): a 1-mm move there shifts the silhouette the view match
    measures (NASA X-3 front view 99.2 -> 97.9 % from seam smoothing; a recessed named region 99.1 -> 95.8 %)."""
    return outline_axes(V, frame, band_px).any(1)


def outline_axes(V, frame, band_px=1):
    """(n, 3) bool: the coordinates of each vertex that a drawn outline holds. A vertex within band_px of the side
    view's outline holds x and z (it may still move along y, that view's line of sight), top: x and y, front: y and z."""
    nx, ny, nz = frame["grid"]
    vox = (np.asarray(V, float) + frame["centre"]) / frame["step"]
    out = np.zeros((len(vox), 3), bool)
    held = {"side": [0, 2], "top": [0, 1], "front": [1, 2]}
    for (m, _, flip), role in zip(frame["views"], ("side", "top", "front")):
        h, w = m.shape
        if role == "side":
            X, Y = vox[:, 0] * w / nx - 0.5, (nz - vox[:, 2]) * h / nz - 0.5
        elif role == "top":
            X, Y = vox[:, 0] * w / nx - 0.5, (ny - vox[:, 1]) * h / ny - 0.5
        else:
            X, Y = vox[:, 1] * w / ny - 0.5, (nz - vox[:, 2]) * h / nz - 0.5
        if flip:
            X = w - 1 - X
        band = _dilate(m, band_px) & ~_erode(m, band_px)
        on = band[np.clip(np.round(Y).astype(int), 0, h - 1), np.clip(np.round(X).astype(int), 0, w - 1)]
        out[np.ix_(on, held[role])] = True
    return out


def smooth_off_outline(V, F, frame, n=30, free_px=3.0, band_px=1):
    """Smooth the big surfaces of a three-view solid without moving its silhouettes: Taubin passes in which a vertex on
    a drawn outline keeps the coordinates that outline holds (outline_axes) and moves only along that view's line of
    sight; every other vertex may move up to free_px from where the surface put it. A body built at 1 px per voxel with
    blur 0 (so a 2-px wing survives) keeps its voxel noise otherwise, and decimation turns it into crumples (car sheet:
    roughness RMS 12.7 deg, 35 % of the surface bent > 10 deg). Returns (V, put-back count of keep_unflipped)."""
    from . import hull, quality
    V0 = np.asarray(V, float)
    hold = outline_axes(V0, frame, band_px)
    stats = {"held_any_pct": round(100 * float(hold.any(1).mean()), 1), "held_all3_pct": round(100 * float(hold.all(1).mean()), 1)}
    lim = float(free_px) * float(frame["step"])
    V = V0.copy()
    for _ in range(int(n)):
        V = hull.taubin(V, F, 1)
        V = np.where(hold, V0, V0 + np.clip(V - V0, -lim, lim))
    V, nb = quality.keep_unflipped(V0, V, F)
    return V, dict(stats, put_back=nb, roughness_before=quality.roughness(V0, F))


def silhouette_lock(frame, band_px=1):
    """A constraint for hull.surface_nets' smoothing: a vertex whose projection lies within band_px of a drawn outline
    in a view keeps its two coordinates IN that view's plane (side: x, z; top: x, y; front: y, z) at their surface-net
    values, and may only move along that view's line of sight. Smoothing then rounds the body but cannot pull a thin
    wing or tail tip in from its drawn outline (unconstrained Taubin did: G's top view 89.5 % -> 65.1 %).
    frame: as mesh_view_masks, plus "masks": {"side", "top", "front"} (drawn, the masks' own frames)."""
    nx, ny, nz = frame["grid"]
    bands = {}
    for role, mask in frame["masks"].items():
        m = np.asarray(mask, bool)
        bands[role] = _dilate(m, band_px) & ~_erode(m, band_px)
    state = {}

    def constrain(V_old, V_new):
        if "lock" not in state:                       # first call: V_old is the surface-net placement
            vox = V_old - 2.5                         # surface_nets' cell coordinates -> voxel coordinates
            locks = []
            for role, axes in (("side", (0, 2)), ("top", (0, 1)), ("front", (1, 2))):
                h, w = bands[role].shape
                if role == "side":
                    X, Y = vox[:, 0] * w / nx - 0.5, (nz - vox[:, 2]) * h / nz - 0.5
                elif role == "top":
                    X, Y = vox[:, 0] * w / nx - 0.5, (ny - vox[:, 1]) * h / ny - 0.5
                else:
                    X, Y = vox[:, 1] * w / ny - 0.5, (nz - vox[:, 2]) * h / nz - 0.5
                if role != "side" and frame["flips"][role]:
                    X = w - 1 - X
                c = np.clip(np.round(X).astype(int), 0, w - 1)
                r = np.clip(np.round(Y).astype(int), 0, h - 1)
                locks.append((bands[role][r, c], axes))
            state["lock"], state["V0"] = locks, V_old.copy()
        V = V_new.copy()
        for sel, axes in state["lock"]:
            for a in axes:
                V[sel, a] = state["V0"][sel, a]
        return V
    constrain.locked_share = lambda: (float(np.mean(np.any([s for s, _ in state["lock"]], 0))) if "lock" in state else None)
    return constrain


def _fill_small_triangles(P, h, w, chunk=None, win=5):
    """Pixels whose centre lies in (or on) any of the triangles P (n, 3, 2), all < win - 1 px across: every triangle
    tests the win x win pixel centres from its corner, vectorised - millions of surface-net triangles (win 5) or a
    decimated mesh's ~40k (win 13 / 33) take seconds, not the minutes one call per triangle takes."""
    m = np.zeros((h, w), bool)
    o = np.arange(win)
    chunk = chunk or max(1000, 10_000_000 // (win * win))
    for c0 in range(0, len(P), chunk):
        T = P[c0:c0 + chunk]
        x0 = np.floor(T[:, :, 0].min(1)).astype(int)
        y0 = np.floor(T[:, :, 1].min(1)).astype(int)
        px = np.broadcast_to(x0[:, None, None] + o[None, None, :], (len(T), win, win)) + 0.0
        py = np.broadcast_to(y0[:, None, None] + o[None, :, None], (len(T), win, win)) + 0.0
        (ax, ay), (bx, by), (cx, cy) = [(T[:, i, 0][:, None, None], T[:, i, 1][:, None, None]) for i in range(3)]
        def side_(x1, y1, x2, y2):
            return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
        d1, d2, d3 = side_(ax, ay, bx, by), side_(bx, by, cx, cy), side_(cx, cy, ax, ay)
        eps = 1e-9
        inside = ((d1 >= -eps) & (d2 >= -eps) & (d3 >= -eps)) | ((d1 <= eps) & (d2 <= eps) & (d3 <= eps))
        ok = inside & (px >= 0) & (px < w) & (py >= 0) & (py < h)
        m[py[ok].astype(int), px[ok].astype(int)] = True
    return m


def overlay(g, views, roles, occ, projected=None):
    """Check image: each view's silhouette (light) and the 3D model's projection back into that view (cyan
    outline). Where the model is smaller than the drawing the views disagree. projected: masks already in each view's
    frame (mesh_view_masks: the delivered mesh, the official view match); else the voxel field occ is projected."""
    im = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert("RGB")
    a = np.asarray(im).astype(float)
    proj = {"side": occ.any(1).T[::-1], "top": occ.any(2).T[::-1], "front": occ.any(0).T[::-1]} if projected is None else {}
    iou = {}
    for role, (mask, (y0, x0), flip) in zip(roles, views):
        h, w = mask.shape
        if projected is not None:
            P = projected[role]
        elif role in proj:
            P = proj[role][:, ::-1] if flip else proj[role]
            P = np.asarray(Image.fromarray(P.astype(np.uint8) * 255).resize((w, h), Image.NEAREST)) > 127
        else:
            continue
        iou[role] = round(100 * (P & mask).sum() / max((P | mask).sum(), 1), 1)
        sl = a[y0:y0 + h, x0:x0 + w]
        sl[mask & ~P] = sl[mask & ~P] * 0.4 + np.array([255, 80, 80]) * 0.6        # drawn but not built: red
        sl[P] = sl[P] * 0.55 + np.array([80, 200, 255]) * 0.45                    # built: blue
    return Image.fromarray(a.astype(np.uint8)), iou


def front_rear_candidates(src, max_side=1600):
    """The two same-size end views (front and rear) of a sheet, as [(view index, crop image)], or [] - so that
    something that can recognise a front (Muse Spark) can say which is which before the solid is built."""
    g = _gray(src, max_side)
    views = [v for v in (view_mask(g, b) for b in panels(g)) if v[0] is not None and v[0].sum() > 200]
    if len(views) < 4:
        return []
    s, t, f, rest, err = match([v[0] for v in views])
    fh, fw = views[f][0].shape
    twin = [i for i in rest if abs(views[i][0].shape[0] - fh) < 0.08 * fh and abs(views[i][0].shape[1] - fw) < 0.08 * fw]
    if not twin:
        return []
    out = []
    for i in (f, twin[0]):
        (h, w), (y0, x0) = views[i][0].shape, views[i][1]
        out.append((i, Image.fromarray(np.clip(g[y0:y0 + h, x0:x0 + w], 0, 255).astype(np.uint8))))
    return out


REGION_TINTS = [(255, 99, 71), (65, 105, 225), (50, 180, 90), (230, 160, 30), (170, 80, 200), (0, 170, 190),
                (200, 60, 120), (120, 150, 40), (90, 90, 230), (210, 110, 60)]


def annotate_regions(g, mask, at, L):
    """The view as drawn, each region tinted and numbered (1..k, as Muse Spark is asked to name them)."""
    from PIL import ImageDraw, ImageFont
    h, w = mask.shape
    y0, x0 = at
    base = np.asarray(Image.fromarray(g[y0:y0 + h, x0:x0 + w]).convert("RGB"), float)
    tint = np.zeros_like(base)
    for r in range(L.max() + 1):
        tint[L == r] = REGION_TINTS[r % len(REGION_TINTS)]
    out = np.where((L >= 0)[..., None], base * 0.55 + tint * 0.45, base)
    k = 900 / max(h, w)
    im = Image.fromarray(out.astype(np.uint8)).resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.load_default(size=max(12, round(18 * min(1.0, 900 / max(w * k, 1)))))
    except TypeError:
        font = ImageFont.load_default()
    for r in range(L.max() + 1):
        ys, xs = np.nonzero(L == r)
        if not len(ys):
            continue
        cy, cx = ys.mean(), xs.mean()
        j = np.argmin((ys - cy) ** 2 + (xs - cx) ** 2)        # a point inside the region nearest its centre
        px, py = xs[j] * k, ys[j] * k
        d.text((px, py), str(r + 1), fill=(255, 255, 255), font=font, anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
    return im


def naming_views(src, max_side=1600, front_panel=None):
    """The light first half of sheet_to_solid: the sheet's views found and matched, the closed regions each view's
    lines make, and the views with their regions tinted and numbered for Muse Spark to name ("shown"). It needs no
    solid, so it runs on this computer while the solid is built on Modal, and the numbering is the same on both.
    Raises ValueError if fewer than 3 views are found."""
    from . import segment
    g = _gray(src, max_side)
    views = []
    for b in panels(g):
        m, at = view_mask(g, b)
        if m is not None and m.sum() > 200:
            views.append((m, at))
    if len(views) < 3:
        raise ValueError(f"found {len(views)} separate views on the sheet; a three-view rebuild needs side, front and top")
    s, t, f, rest, err = match([v[0] for v in views])
    side, front = views[s][0], views[f][0]
    nl = nose_left(side)
    fr = None
    twin = [i for i in rest if abs(views[i][0].shape[0] - front.shape[0]) < 0.08 * front.shape[0]
            and abs(views[i][0].shape[1] - front.shape[1]) < 0.08 * front.shape[1]]
    if front_panel is not None and twin:
        other = twin[0]
        fp, rp = (f, other) if front_panel == f else (other, f) if front_panel == other else (None, None)
        if fp is not None:
            fr = {"front": views[fp], "rear": views[rp]}
    regs = {"side": segment.regions(side, _ink_in(g, *views[s])),
            "top": segment.regions(views[t][0], _ink_in(g, *views[t]))}
    end_regs = {role: segment.regions(fr[role][0], _ink_in(g, *fr[role])) for role in ("front", "rear")} if fr else {}
    shown = [("side", annotate_regions(g, side, views[s][1], regs["side"]), int(regs["side"].max()) + 1),
             ("top", annotate_regions(g, views[t][0], views[t][1], regs["top"]), int(regs["top"].max()) + 1)]
    for role, Lr in end_regs.items():
        shown.append((role, annotate_regions(g, *fr[role], Lr), int(Lr.max()) + 1))
    return {"g": g, "views": views, "s": s, "t": t, "f": f, "rest": rest, "err": err, "nl": nl, "fr": fr, "twin": twin,
            "regs": regs, "end_regs": end_regs, "shown": shown}


def sheet_to_solid(src, length_mm=180.0, voxels=220, max_side=1600, front_panel=None, namer=None, px_per_voxel=None,
                   decimate_to=None, smooth_iters=None, smooth_clamp_px=0.7):
    """A multi-view sheet -> (V, F, report, check_image, lines). Raises ValueError if fewer than 3 views are found.
    px_per_voxel: build the solid at that many drawing pixels per voxel (1.0 = the drawing's own resolution: thin wing
    and tail tips survive; on G 99.9 / 99.2 / 99.2 % on the delivered mesh vs 90.8 / 65.1 / 66.9 % at 200 voxels),
    on the GPU when there is one (engine.backend). decimate_to: quadric decimation of the surface to about that many
    triangles (fast-simplification, installed in the Modal image only; skipped and reported where it is missing).
    front_panel: index (in report["used"]) of the view that shows the FRONT of the object, when known (Muse Spark
    tells front from rear); with it the front and rear views' lines are put on the right ends."""
    import time as _time
    _t, tm = _time.time(), {}

    def lap(k):
        nonlocal _t
        tm[k] = round(_time.time() - _t, 2)
        _t = _time.time()
    ctx = naming_views(src, max_side, front_panel)
    lap("views_and_regions_s")
    g, views, s, t, f, rest, err = ctx["g"], ctx["views"], ctx["s"], ctx["t"], ctx["f"], ctx["rest"], ctx["err"]
    side, front, nl, fr, twin = views[s][0], views[f][0], ctx["nl"], ctx["fr"], ctx["twin"]
    regs, end_regs = ctx["regs"], ctx["end_regs"]
    from . import segment
    naming = None
    if namer is not None:                      # Muse Spark names the regions (~20 s) while the hull is carved here
        from concurrent.futures import ThreadPoolExecutor
        pool = ThreadPoolExecutor(1)
        naming = pool.submit(namer, ctx["shown"])
        pool.shutdown(wait=False)
    occ, step, rep, ft, ff = carve_best(side, views[t][0], front, float(length_mm), int(voxels))
    from . import backend
    xp = backend.xp if px_per_voxel else np
    if px_per_voxel:                          # the flips were chosen on the coarse grid; the solid is built finer
        mm_px = float(length_mm) / side.shape[1]
        dims = (float(length_mm), views[t][0].shape[0] * float(length_mm) / views[t][0].shape[1], side.shape[0] * mm_px)
        fine = int(round(max(dims) / (mm_px * float(px_per_voxel))))
        occ, step, rep = hull.carve(side, views[t][0][:, ::-1] if ft else views[t][0], front[:, ::-1] if ff else front,
                                    float(length_mm), fine)
    if not occ.any():
        raise ValueError("the views do not overlap")
    lap("grids_s")
    field = hull_field_slabs(side, views[t][0], front, ft, ff, occ.shape, xp=xp, aa=1 if px_per_voxel else 0)
    if px_per_voxel:                         # thick bodies smoothed like the coarse build, thin parts left sharp
        field, _ = blur_thick(field, xp=xp)
    lap("field_s")
    occ = backend.to_numpy(field > 0.5)
    # blur 0 at the drawing's resolution: two [1 2 1] passes erase a 2-px wing tip (synthetic test: top view
    # 89.2 % with blur 2, 100 % with 0); Taubin smoothing still rounds the voxel steps
    # smoothing may move a vertex at most 0.7 px from where the surface put it (no locking): rounds the voxel steps,
    # 8 Taubin passes at 1 px/voxel (16 cost G's thin front view 0.3 points: 98.7 vs 99.0 %),
    # cannot pull a thin tip in from its drawn outline
    clamp = (lambda V0, V1, _lim=float(smooth_clamp_px): V0 + np.clip(V1 - V0, -_lim, _lim)) if px_per_voxel else None
    state_ = {}
    def held(Vo, Vn):
        state_.setdefault("V0", Vo.copy())
        return clamp(state_["V0"], Vn)
    V, F, centre = hull.surface_nets(field, step, blur=0 if px_per_voxel else 2, smooth=int(smooth_iters or (8 if px_per_voxel else 16)), return_centre=True, xp=xp,
                                     constrain=held if clamp else None)
    lap("surface_s")
    rep["mesh"] = {"surface_triangles": int(len(F)), "px_per_voxel": float(px_per_voxel or step / (float(length_mm) / side.shape[1]))}
    from . import quality
    folds0 = quality.folds(V, F)                                  # 3-D check per stage (quality.folds)
    if decimate_to and len(F) > decimate_to:
        try:
            import fast_simplification
            V, F = fast_simplification.simplify(np.asarray(V, np.float32), np.asarray(F, np.int64),
                                                target_reduction=1 - decimate_to / len(F))
            V, F = np.asarray(V, float), np.asarray(F, np.int64)
            rep["mesh"]["decimated_to"] = int(len(F))
        except ImportError:
            rep["mesh"]["decimated_to"] = None
            rep["mesh"]["note"] = "fast-simplification is not installed here (Modal only): mesh not decimated"
    lap("decimate_s")
    rep["mesh"]["folds"] = {"surface": folds0, "decimated": quality.folds(V, F)}
    if px_per_voxel:                         # the big surfaces smoothed, every drawn silhouette held (smooth_off_outline)
        V, sm = smooth_off_outline(V, F, {"grid": occ.shape, "centre": centre, "step": step, "views": [
            (side, None, False), (views[t][0], None, ft), (front, None, ff)]})
        rep["mesh"]["folds"]["smoothed"] = quality.folds(V, F)
        rep["mesh"]["smoothing"] = dict(sm, roughness_after=quality.roughness(V, F))
    lap("smooth_s")
    L, Dy, Hz = rep["size_mm"]
    # wheels, in mm about the mesh centre (x along the length, z up, y across)
    kx, kz, ky = L / side.shape[1], Hz / side.shape[0], Dy / front.shape[1]
    wh = wheels(hull._largest(side), front)        # tyre arcs on the main outline; parts drawn apart (a rim) do not move it
    wl = [{"x": (w["cx"] + 0.5) * kx - L / 2, "z": Hz / 2 - (w["cy"] + 0.5) * kz, "r": w["r"] * kx,
           "y_outer": w["outer"] * ky, "width": w["width"] * ky} for w in wh]
    maps = {"side": (regs["side"], False), "top": (regs["top"], ft), "end_min": None, "end_max": None}
    ends = {}
    for role, at_nose in (("front", True), ("rear", False)):
        if role not in end_regs:
            continue
        at_min = at_nose == nl
        # seen from -x the object's +y is on the viewer's left, from +x on the right
        fl = ff != (not at_min)
        maps["end_min" if at_min else "end_max"] = (end_regs[role], fl)
        ends[role] = (end_regs[role], fl, at_min)
    # what each region is (door, side window, air intake...): Muse Spark's answer, asked above
    names, end_roles = {}, {}
    for role, (Lr, fl, at_min) in ends.items():
        end_roles["end_min" if at_min else "end_max"] = role
    if naming is not None:
        try:
            names = naming.result() or {}
        except Exception as e:                       # the parts are still built, named by position; the report says why
            names = {}
            end_roles["_naming_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    key = segment.assign(V, F, maps, centre, step, occ.shape)
    key = segment.smooth_labels(F, key, rounds=8)
    # vertices on a drawn view's outline stay where the surface put them while part seams are straightened
    on_outline = outline_vertices(V, {"grid": occ.shape, "centre": centre, "step": step, "views": [
        (side, None, False), (views[t][0], None, ft), (front, None, ff)]})
    pieces = segment.split(V, F, key, fixed=on_outline, fixed_limit=0.7 * float(step) if px_per_voxel else 0.0,
                           seam_min_edge=0.75 * float(step) if px_per_voxel else 0.0)

    def unflip(V_before, pieces, stage):
        """A seam / zig-zag move that turned a triangle over (a thin rim's two faces crossing: a sawtooth of dark
        facets at G's wing tip) is put back; the fold count before and after goes in the report."""
        Vn = np.asarray(V_before, float).copy()
        for pv_, pf_, used_ in pieces.values():
            Vn[used_] = pv_
        rep["mesh"]["folds"][stage] = quality.folds(Vn, F)
        Vn, nb = quality.keep_unflipped(V_before, Vn, F)
        rep["mesh"]["folds"][stage + "_guarded"] = dict(quality.folds(Vn, F), vertices_put_back=nb)
        return Vn, {k_: (Vn[used_], pf_, used_) for k_, (pv_, pf_, used_) in pieces.items()}
    Vs, pieces = unflip(V, pieces, "seams")
    # edge quality: every part's outline in the view it was cut from, in that view's pixels (engine/quality.py)
    view_of = lambda k_: {"side": ((0, 2), 1), "top": ((0, 1), 2), "under": ((0, 1), 2)}.get(k_[0], ((1, 2), 0))
    if px_per_voxel:                          # zig-zags left on part outlines move onto their chords (<= 0.7 px on
        mm_px_ = float(length_mm) / side.shape[1]  # a drawn outline), in the shared vertices so parts stay joined
        Vg = quality.straighten_zigzags(Vs, pieces, view_of, mm_px_, 2 * mm_px_, fixed=on_outline,
                                        fixed_limit_mm=0.7 * mm_px_)
        Vs, pieces = unflip(Vs, {k_: (Vg[used_], pf_, used_) for k_, (pv_, pf_, used_) in pieces.items()}, "zigzags")
    sc, ln_ = [], 0.0
    for k_, (pv_, pf_, _) in pieces.items():
        s_, l_, st_ = quality.part_staircase(pv_, pf_, float(length_mm) / side.shape[1], *view_of(k_))
        sc.append(st_)
        ln_ += l_
    rep["staircase_pct"] = round(100 * sum(sc) / max(ln_, 1e-9), 2)
    rep["staircase_parts_with_steps"] = int(sum(x > 0 for x in sc))
    lap("parts_s")
    # panel lines: the outline of every region, smoothed, laid on the surface
    fb = backend.to_numpy(hull._blur32(xp.pad(field, 3), 1, xp))
    del field
    segs, counts = [], {}
    # panel lines: the drawn lines themselves (ink centre lines, smoothed), not region borders
    yy, xx = np.mgrid[:side.shape[0], :side.shape[1]]
    wheel_px = np.zeros(side.shape, bool)
    for w in wh:                                     # the wheels are their own parts: their spokes are not panel lines
        wheel_px |= (xx - w["cx"]) ** 2 + (yy - w["cy"]) ** 2 < (w["r"] * 1.02) ** 2
    cs = [(c, side.shape) for c in segment.ink_curves(_ink_in(g, side, views[s][1], 0), side, exclude=wheel_px)]
    for fm, nm in ((True, "side L"), (False, "side R")):
        q = seams_on_surface(fb, occ.shape, cs, "side", False, fm)
        segs.append(q)
        counts[nm] = len(q)
    q = seams_on_surface(fb, occ.shape, [(c, views[t][0].shape) for c in segment.ink_curves(_ink_in(g, *views[t], 0), views[t][0])], "top", ft, True)
    segs.append(q)
    counts["top"] = len(q)
    for role, (Lr, fl, at_min) in ends.items():
        m_, at_ = fr[role]
        q = seams_on_surface(fb, occ.shape, [(c, m_.shape) for c in segment.ink_curves(_ink_in(g, m_, at_, 0), m_)], "end", fl, not at_min)
        segs.append(q)
        counts[role] = len(q)
    seg = np.concatenate(segs).reshape(-1, 3) * step - centre
    part_lines = segment.lines_per_part(pieces, len(V), seg.reshape(-1, 2, 3), centre, step, occ.shape)
    pieces = {k: (pv, pf, part_lines[k]) for k, (pv, pf, _) in pieces.items()}
    # precision: outline error per view (mm on the model) and resolution
    proj = {"side": occ.any(1).T[::-1], "top": occ.any(2).T[::-1], "front": occ.any(0).T[::-1]}
    err_mm = {}
    for role, (mask, flip) in {"side": (side, False), "top": (views[t][0], ft), "front": (front, ff)}.items():
        P = proj[role][:, ::-1] if flip else proj[role]
        P = np.asarray(Image.fromarray(P.astype(np.uint8) * 255).resize(mask.shape[::-1], Image.NEAREST)) > 127
        e = outline_error(mask, P, L / side.shape[1])
        if e:
            e["mean_pct_of_length"] = round(100 * e["mean_mm"] / L, 3)
            e["p95_pct_of_length"] = round(100 * e["p95_mm"] / L, 3)
        err_mm[role] = e
    roles = ["side", "top", "front"]
    chk, iou = overlay(g, [(side, views[s][1], False), (views[t][0], views[t][1], ft), (front, views[f][1], ff)], roles, occ)
    edge = np.linalg.norm(V[F[:, 0]] - V[F[:, 1]], axis=1)
    rep.update({"wheels": [{k: round(v, 1) for k, v in w.items()} for w in wl], "views_found": len(views),
                "used": {"side": s, "top": t, "front": f, "unused": rest, "front_or_rear_twin": twin},
                "size_disagreement_pct": round(100 * err, 1), "view_match_iou_pct": iou,
                "precision": {"outline_error_mm": err_mm, "drawing_px_mm": round(L / side.shape[1], 3),
                              "voxel_mm": round(step, 3), "mesh_edge_mm": round(float(np.median(edge)), 3),
                              "faces": int(len(F)), "parts": len(pieces), "panel_line_segments": counts,
                              "lines_note": ("Panel lines are the drawn lines themselves (centre line of the ink, smoothed), "
                                             "laid where they are drawn, each from the view that faces that part of the "
                                             "body; their depth comes from the solid")},
                "region_names": names, "end_roles": {k: v for k, v in end_roles.items() if not k.startswith("_")},
                **({"naming_error": end_roles["_naming_error"]} if "_naming_error" in end_roles else {}),
                "nose": "left of the side view" if nl else "right of the side view",
                "note": ("Visual hull of the side, top and front views: the largest solid whose three silhouettes match "
                         "the drawing, with every line drawn inside the views carried onto its surface. Concave detail "
                         "no view sees (the inside of the air intakes, the cabin) is not recovered; the length is set "
                         "to the requested size, all other sizes come from the drawing's own proportions.")})
    lap("lines_check_s")
    rep["timing"] = {**tm, "on": backend.name()}
    # what the official, mesh-based view match needs (lab.import_sheet measures the delivered parts with it)
    rep["_frame"] = {"grid": occ.shape, "centre": np.asarray(centre, float), "step": float(step),
                     "shapes": {"side": side.shape, "top": views[t][0].shape, "front": front.shape},
                     "flips": {"top": bool(ft), "front": bool(ff)},
                     "views": [(side, views[s][1], False), (views[t][0], views[t][1], ft), (front, views[f][1], ff)],
                     "gray": g}
    return V, F, rep, chk, seg, pieces
