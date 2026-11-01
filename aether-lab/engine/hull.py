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


def _largest(mask):
    """Largest 4-connected component (drops dimension text, arrows and title blocks)."""
    lab, n = label4(mask)
    if not n:
        return np.zeros_like(mask)
    area = np.bincount(lab.ravel(), minlength=n + 1)
    area[0] = 0
    return lab == area.argmax()


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


def surface(occ, step, origin=None, smooth=6):
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
    for _ in range(smooth):
        for lam in (0.5, -0.53):
            avg = np.zeros_like(V)
            np.add.at(avg, ii, V[jj])
            V = V + lam * (avg / deg[:, None] - V)
    V = (V - 1) * step                             # undo the pad, to mm
    if origin is None:
        V -= (V.min(0) + V.max(0)) / 2
    else:
        V += np.asarray(origin, float)
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


def _blur(f, passes=2):
    """Separable [1 2 1]/4 blur, repeated: softens the voxel staircase before the surface is taken."""
    f = f.astype(float)
    for _ in range(passes):
        for ax in range(3):
            f = (np.roll(f, 1, ax) + 2 * f + np.roll(f, -1, ax)) / 4
    return f


def taubin(V, F, n=8, lam=0.5, mu=-0.53):
    """Taubin smoothing (shrink-free): removes small ripples, keeps the shape and volume."""
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    E = np.concatenate([E, E[:, ::-1]])
    i, j = E[:, 0], E[:, 1]
    deg = np.maximum(np.bincount(i, minlength=len(V)), 1).astype(float)
    for _ in range(n):
        for k in (lam, mu):
            avg = np.stack([np.bincount(i, V[j, d], minlength=len(V)) for d in range(3)], 1) / deg[:, None]
            V = V + k * (avg - V)
    return V


def _blur32(f, passes=2, xp=np):
    """_blur in float32 without np.roll copies (same [1 2 1]/4 kernel; the 3-cell zero padding makes the wrap-around
    of the old version a no-op): ~4 bytes per cell instead of ~40, so a 1-px-per-voxel field fits in memory."""
    f = xp.asarray(f, dtype=xp.float32).copy()
    for _ in range(passes):
        for ax in range(3):
            g = f * xp.float32(2)
            sl = [slice(None)] * 3
            sl_a, sl_b = list(sl), list(sl)
            sl_a[ax], sl_b[ax] = slice(1, None), slice(None, -1)
            g[tuple(sl_a)] += f[tuple(sl_b)]
            g[tuple(sl_b)] += f[tuple(sl_a)]
            g *= xp.float32(0.25)
            f = g
    return f


def surface_nets(occ, step, blur=2, iso=0.5, smooth=8, return_centre=False, constrain=None, xp=np):
    """smooth_surface, memory-frugal: the same surface nets (one vertex per crossed cell at the mean of its edge
    crossings, one quad per crossed grid edge) but corners are read only for the cells the surface crosses and quads
    find their cells by sorted cell number, so no dense 8-corner or index array exists (a 1400 x 480 x 280 grid needs
    ~2 GB instead of ~10). constrain(V_voxel, V_new) -> V may hold vertices after every smoothing step (silhouettes).
    xp: numpy, or cupy on a GPU (Modal): the same code; V and F come back as numpy."""
    f = _blur32(xp.pad(xp.asarray(occ, dtype=xp.float32), 3), blur, xp)
    nx, ny, nz = f.shape
    inside = f > iso
    del_any = xp.zeros((nx - 1, ny - 1, nz - 1), bool)
    del_all = xp.ones((nx - 1, ny - 1, nz - 1), bool)
    offs = np.array([(i, j, k) for i in (0, 1) for j in (0, 1) for k in (0, 1)])
    for i, j, k in offs:
        s = inside[i:nx - 1 + i, j:ny - 1 + j, k:nz - 1 + k]
        del_any |= s
        del_all &= s
    active = del_any & ~del_all
    del del_any, del_all
    cells = xp.argwhere(active).astype(xp.int32)
    lin = xp.ravel_multi_index(cells.T, active.shape)            # sorted (argwhere is in C order)
    del active
    edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if np.abs(offs[a] - offs[b]).sum() == 1]
    Cc = xp.stack([f[cells[:, 0] + int(i), cells[:, 1] + int(j), cells[:, 2] + int(k)] for i, j, k in offs], -1)
    acc = xp.zeros((len(cells), 3))
    cnt = xp.zeros(len(cells))
    offs_x = xp.asarray(offs)
    for a, b in edges:
        va, vb = Cc[:, a], Cc[:, b]
        m = (va > iso) != (vb > iso)
        t = xp.where(m, (iso - va) / xp.where(m, vb - va, 1), 0)
        p = offs_x[a] + t[:, None] * (offs_x[b] - offs_x[a])
        acc[m] += p[m]
        cnt[m] += 1
    del Cc
    V = cells + acc / xp.maximum(cnt, 1)[:, None]
    shp = (nx - 1, ny - 1, nz - 1)
    quads = []
    for ax in range(3):
        u, v = [a for a in range(3) if a != ax]
        e = np.zeros(3, int)
        e[ax] = 1
        cross = xp.argwhere(inside[:nx - e[0], :ny - e[1], :nz - e[2]] != inside[e[0]:, e[1]:, e[2]:])
        ok = (cross[:, u] >= 1) & (cross[:, v] >= 1) & (cross[:, u] < shp[u]) & (cross[:, v] < shp[v]) & (cross[:, ax] < shp[ax])
        cross = cross[ok]
        flip = inside[tuple(cross.T)]
        q = []
        for du, dv in ((-1, -1), (0, -1), (0, 0), (-1, 0)):
            c = cross.copy()
            c[:, u] += du
            c[:, v] += dv
            key = xp.ravel_multi_index(c.T, shp)
            pos = xp.searchsorted(lin, key)
            pos = xp.minimum(pos, len(lin) - 1)
            q.append(xp.where(lin[pos] == key, pos, -1))
        q = xp.stack(q, 1)
        right = (u, v, ax) in ((0, 1, 2), (1, 2, 0), (2, 0, 1))
        rev = flip != right
        q[rev] = q[rev][:, ::-1]
        quads.append(q[(q >= 0).all(1)])
    del inside, f
    Q = xp.concatenate(quads)
    F = xp.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    if xp is not np:                       # smoothing and the rest on the CPU: the mesh is small now
        V, F = V.get(), F.get()
    if smooth:
        if constrain is None:
            V = taubin(V, F, smooth)
        else:
            for _ in range(smooth):
                V = constrain(V, taubin(V, F, 1))
    V = (V - 3 + 0.5) * step                 # voxel i spans [i, i + 1] * step
    c = (V.min(0) + V.max(0)) / 2
    V -= c
    return (V, F, c) if return_centre else (V, F)


def smooth_surface(occ, step, blur=2, iso=0.5, smooth=8, return_centre=False):
    """Surface nets on the blurred occupancy: one vertex per cell the surface crosses (the mean of its edge
    crossings), one quad per crossed grid edge. Smooth where the hull is smooth, no staircase. -> (V mm centred, F)."""
    f = _blur(np.pad(occ, 3), blur)
    nx, ny, nz = f.shape
    inside = f > iso
    # 8 corners of every cell
    offs = np.array([(i, j, k) for i in (0, 1) for j in (0, 1) for k in (0, 1)])
    C = np.stack([f[i:nx - 1 + i, j:ny - 1 + j, k:nz - 1 + k] for i, j, k in offs], -1)
    S = C > iso
    active = S.any(-1) & ~S.all(-1)
    idx = -np.ones(active.shape, int)
    cells = np.argwhere(active)
    idx[tuple(cells.T)] = np.arange(len(cells))
    # the 12 cell edges as corner index pairs
    edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if np.abs(offs[a] - offs[b]).sum() == 1]
    acc = np.zeros((len(cells), 3))
    cnt = np.zeros(len(cells))
    Cc = C[tuple(cells.T)]
    for a, b in edges:
        va, vb = Cc[:, a], Cc[:, b]
        m = (va > iso) != (vb > iso)
        t = np.where(m, (iso - va) / np.where(m, vb - va, 1), 0)
        p = offs[a] + t[:, None] * (offs[b] - offs[a])
        acc[m] += p[m]
        cnt[m] += 1
    V = cells + acc / np.maximum(cnt, 1)[:, None]
    quads = []
    for ax in range(3):
        u, v = [a for a in range(3) if a != ax]
        e = np.zeros(3, int)
        e[ax] = 1
        a0 = inside[:nx - e[0], :ny - e[1], :nz - e[2]]
        a1 = inside[e[0]:, e[1]:, e[2]:]
        cross = np.argwhere(a0 != a1)
        # keep edges whose four neighbour cells exist
        ok = (cross[:, u] >= 1) & (cross[:, v] >= 1) & (cross[:, u] < active.shape[u]) & (cross[:, v] < active.shape[v]) & (cross[:, ax] < active.shape[ax])
        cross = cross[ok]
        flip = a0[tuple(cross.T)]
        q = []
        for du, dv in ((-1, -1), (0, -1), (0, 0), (-1, 0)):
            c = cross.copy()
            c[:, u] += du
            c[:, v] += dv
            q.append(idx[tuple(c.T)])
        q = np.stack(q, 1)
        right = (u, v, ax) in ((0, 1, 2), (1, 2, 0), (2, 0, 1))
        rev = flip != right
        q[rev] = q[rev][:, ::-1]
        quads.append(q[(q >= 0).all(1)])
    Q = np.concatenate(quads)
    F = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    if smooth:
        V = taubin(V, F, smooth)
    V = (V - 3 + 0.5) * step                 # voxel i spans [i, i + 1] * step
    c = (V.min(0) + V.max(0)) / 2
    V -= c
    return (V, F, c) if return_centre else (V, F)
