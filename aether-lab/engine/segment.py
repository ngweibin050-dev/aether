"""Split a solid rebuilt from a drawing into the parts the drawing shows, the way a modeller builds it up.

A modeller does not make a car as one lump: bonnet, roof, doors, windows, bumpers, intakes, lamps and wheels are
separate shapes. The drawing already says where they are: inside every view the lines enclose closed regions
(a window, a door skin, an intake). So:

1. regions(): per view, the drawn lines cut the silhouette into closed regions; tiny ones (hatching, mesh grilles,
   text) are merged into their neighbours, and every pixel (lines too) gets the region it belongs to.
2. assign(): every surface triangle faces mostly one way. Side-facing triangles take their region from the side
   view, upward ones from the top view, the two ends from the front / rear views, downward ones are the underbody.
   Left and right are kept apart (a left door and a right door are two parts).
3. A few rounds of majority voting between neighbouring triangles straighten the seams.
4. split(): one mesh per (view, region, side).
5. seams(): each region's outline is traced, simplified and smoothed into a continuous curve and laid on the
   surface - clean panel lines instead of pixel steps.
"""
import numpy as np
from PIL import Image

from . import hull, outline


def _shift_max(L):
    """For each pixel, the largest label among its 4 neighbours (and itself)."""
    out = L.copy()
    out[1:] = np.maximum(out[1:], L[:-1])
    out[:-1] = np.maximum(out[:-1], L[1:])
    out[:, 1:] = np.maximum(out[:, 1:], L[:, :-1])
    out[:, :-1] = np.maximum(out[:, :-1], L[:, 1:])
    return out


def _components(m):
    """4-connected components of a boolean image -> label image (0 = background, 1..n)."""
    return hull.label4(m)


def regions(mask, ink, min_frac=0.004, max_side=360):
    """Closed regions the drawn lines cut the silhouette into. Returns a label image the size of mask: -1 outside,
    0..k-1 region ids (ordered by area, largest first). Works on a copy scaled to max_side for speed."""
    h, w = mask.shape
    s = min(1.0, max_side / max(h, w))
    hs, ws = max(2, round(h * s)), max(2, round(w * s))
    m = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).resize((ws, hs), Image.NEAREST)) > 127
    k = np.asarray(Image.fromarray(ink.astype(np.uint8) * 255).resize((ws, hs), Image.BOX)) > 60
    free = m & ~k
    lab, n = _components(free)
    area = np.bincount(lab.ravel(), minlength=n + 1)
    keep = np.nonzero(area >= max(min_frac * m.sum(), 6))[0]
    keep = keep[keep > 0]
    # relabel kept regions 1..K by area, drop the rest, then grow the kept ones over lines and small regions
    order = keep[np.argsort(-area[keep])]
    remap = np.zeros(n + 1, int)
    remap[order] = np.arange(1, len(order) + 1)
    L = remap[lab]
    if not len(order):
        L = m.astype(int)
    for _ in range(max(hs, ws)):
        empty = m & (L == 0)
        if not empty.any():
            break
        grow = _shift_max(L)
        L = np.where(empty, grow, L)
    L = np.where(m, L - 1, -1)
    full = np.asarray(Image.fromarray((L + 1).astype(np.uint16)).resize((w, h), Image.NEAREST)).astype(int) - 1
    return np.where(mask, np.maximum(full, 0), -1)


def _lookup(L, rows, cols, reach=8):
    """Region id at view pixels (rows, cols). A surface point that lands just outside the drawn silhouette (-1; at fine
    voxel sizes the smoothed surface sits a pixel or two outside it) takes the nearest region within `reach` px, else
    the main region 0 - never -1, which no part code can hold."""
    h, w = L.shape
    r = np.clip(np.round(rows).astype(int), 0, h - 1)
    c = np.clip(np.round(cols).astype(int), 0, w - 1)
    out = L[r, c]
    if (out < 0).any():
        G = L.copy()
        for _ in range(reach):
            G = np.where(G < 0, _shift_max(G), G)
        out = np.where(out < 0, np.maximum(G[r, c], 0), out)
    return out


def _smooth_normals(V, F, n_iter):
    """Face normals averaged over a wide neighbourhood (vertex normals smoothed n_iter times over the mesh): which
    view a triangle belongs to is decided by the broad direction the surface faces, so the border between 'seen
    from the side' and 'seen from above' is a smooth curve, not a flicker of stripes on a sloped surface."""
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.stack([sum(np.bincount(F[:, k], fn[:, d], minlength=len(V)) for k in range(3)) for d in range(3)], 1)
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    E = np.concatenate([E, E[:, ::-1]])
    deg = np.maximum(np.bincount(E[:, 0], minlength=len(V)), 1)[:, None]
    for _ in range(n_iter):
        vn = vn / (np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12)
        vn = 0.5 * vn + 0.5 * np.stack([np.bincount(E[:, 0], vn[E[:, 1], d], minlength=len(V)) for d in range(3)], 1) / deg
    n = vn[F].sum(1)
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)


def assign(V, F, maps, centre, step, grid, smooth_n=40):
    """Triangle -> (view, region, side) keys. maps: {"side": (L, flip), "top": (L, flip), "end_min": (L, flip) or
    None, "end_max": ...}; L in the view's own pixels; grid = (nx, ny, nz) voxel counts."""
    nx, ny, nz = grid
    T = V[F]
    c = T.mean(1)
    n = _smooth_normals(V, F, smooth_n)
    vox = (c + centre) / step                                    # voxel units, voxel i spans [i, i + 1]
    ax = np.argmax(np.abs(n), 1)
    # keys as integer codes: view * 1e6 + region * 10 + side  (view 0 side, 1 top, 2 under, 3 end_min, 4 end_max)
    L, flip = maps["side"]
    h, w = L.shape
    cols = vox[:, 0] * w / nx
    side_r = _lookup(L, (nz - vox[:, 2]) * h / nz, w - 1 - cols if flip else cols)
    L, flip = maps["top"]
    h, w = L.shape
    cols = vox[:, 0] * w / nx
    top_r = _lookup(L, (ny - vox[:, 1]) * h / ny, w - 1 - cols if flip else cols)
    code = np.where(ax == 1, side_r * 10 + np.where(n[:, 1] > 0, 1, 2),
           np.where((ax == 2) & (n[:, 2] > 0), 1_000_000 + top_r * 10,
           np.where(ax == 2, 2_000_000, np.where(n[:, 0] < 0, 3_000_000, 4_000_000))))
    for end, base in (("end_min", 3_000_000), ("end_max", 4_000_000)):
        if maps.get(end) is None:
            continue
        L, flip = maps[end]
        h, w = L.shape
        sel = code == base
        cols = vox[sel, 1] * w / ny
        code[sel] = base + 10 * _lookup(L, (nz - vox[sel, 2]) * h / nz, w - 1 - cols if flip else cols)
    return code


NAMES = {0: "side", 1: "top", 2: "under", 3: "end_min", 4: "end_max"}


def decode(c):
    c = int(c)
    return NAMES[c // 1_000_000], (c % 1_000_000) // 10, {1: "L", 2: "R"}.get(c % 10, "")


def _neighbours(F):
    """For every triangle, the (up to 3) triangles sharing an edge with it; -1 where none."""
    E = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), 1)
    tri = np.tile(np.arange(len(F)), 3)
    slot = np.repeat(np.arange(3), len(F))
    order = np.lexsort((E[:, 1], E[:, 0]))
    E, tri, slot = E[order], tri[order], slot[order]
    same = (E[1:] == E[:-1]).all(1)
    nb = -np.ones((len(F), 3), int)
    a, b = np.nonzero(same)[0], np.nonzero(same)[0] + 1
    nb[tri[a], slot[a]] = tri[b]
    nb[tri[b], slot[b]] = tri[a]
    return nb


def smooth_labels(F, code, rounds=4):
    """Majority vote among edge-neighbouring triangles: a triangle whose neighbours agree (2 or 3 of them) on
    another part joins it. Removes single-triangle islands and stair-stepped seams."""
    nb = _neighbours(F)
    lab = code.copy()
    for _ in range(rounds):
        L = np.where(nb >= 0, lab[np.maximum(nb, 0)], -1)
        a, b, c = L[:, 0], L[:, 1], L[:, 2]
        maj = np.where((a == b) & (a >= 0), a, np.where((a == c) & (a >= 0), a, np.where((b == c) & (b >= 0), b, lab)))
        lab = maj
    return lab


def smooth_seams(V, F, lab, iters=25, rate=0.5, fixed=None, fixed_limit=0.0, min_edge=0.0):
    """Straighten the seams between parts. A seam found per triangle runs along triangle edges and zig-zags (the
    'pixelated' edge of a window or an intake). Every vertex on a seam with exactly two seam neighbours slides
    toward the middle of them, again and again (1-D smoothing along the seam); junctions where three parts meet
    and the ends stay put. The moves are along the surface and at most about one edge long, so the shape is kept.
    fixed: vertices that must not move at all (on a drawn view's outline: on a decimated mesh one edge is ~1 mm, so
    a seam vertex sliding along the silhouette moved it; NASA X-3 front view 99.2 % -> 97.9 %) - or, with
    fixed_limit > 0, may move at most that far (mm) instead of not at all. min_edge: a seam edge shorter than that
    is first pulled to its midpoint (each end moves <= min_edge / 2): decimation leaves sliver triangles where a seam
    runs back and forth, 0.35-0.6 px edges turning +64 / -124 / +103 deg, which the smoothing cannot reach."""
    nb = _neighbours(F)
    f = np.repeat(np.arange(len(F)), 3)
    k = np.tile(np.arange(3), len(F))
    g = nb.ravel()
    sel = (g >= 0) & (f < g) & (lab[f] != lab[np.maximum(g, 0)])
    a = F[f[sel], k[sel]]
    b = F[f[sel], (k[sel] + 1) % 3]
    if not len(a):
        return V
    if min_edge > 0:
        V = V.copy()
        for _ in range(2):
            short = np.linalg.norm(V[a] - V[b], axis=1) < min_edge
            for i, j in zip(a[short], b[short]):
                V[i] = V[j] = (V[i] + V[j]) / 2
    deg = np.bincount(np.r_[a, b], minlength=len(V))
    # vertices touching three or more parts are corners of the layout: fixed
    vl = np.full((len(V), 3), -1)
    for c in range(3):
        np.maximum.at(vl[:, 0], F[:, c], lab)
    lo = np.full(len(V), np.iinfo(np.int64).max)
    for c in range(3):
        np.minimum.at(lo, F[:, c], lab)
    mid = np.zeros(len(V), bool)
    for c in range(3):
        mid[F[:, c][(lab != lo[F[:, c]]) & (lab != vl[F[:, c], 0])]] = True
    move = (deg == 2) & ~mid
    if fixed is not None and fixed_limit <= 0:
        move &= ~fixed
    edge = np.linalg.norm(V[F[:, 0]] - V[F[:, 1]], axis=1).mean()
    V0 = V.copy()
    V = V.copy()
    for _ in range(iters):
        s = np.zeros_like(V)
        for d in range(3):
            s[:, d] = np.bincount(a, V[b, d], minlength=len(V)) + np.bincount(b, V[a, d], minlength=len(V))
        avg = s / np.maximum(deg, 1)[:, None]
        V[move] += rate * (avg[move] - V[move])
        D = V - V0                                               # never more than about one edge from home
        n = np.linalg.norm(D, axis=1, keepdims=True)
        lim = np.full((len(V), 1), edge)
        if fixed is not None and fixed_limit > 0:
            lim[fixed] = fixed_limit
        V = np.where(n > lim, V0 + D * lim / np.maximum(n, 1e-12), V)
    return V


def split(V, F, code, min_faces=40, fixed=None, fixed_limit=0.0, seam_iters=25, seam_min_edge=0.0):
    """One (V, F) per part code; parts with fewer than min_faces triangles join their most common neighbour."""
    keys, inv = np.unique(code, return_inverse=True)
    counts = np.bincount(inv)
    small = counts < min_faces
    if small.any() and (~small).any():
        # vertex -> a large key using it; small faces take it
        owner = -np.ones(len(V), int)
        big = ~small[inv]
        owner[F[big].ravel()] = np.repeat(inv[big], 3)
        for t in np.nonzero(~big)[0]:
            o = owner[F[t]]
            o = o[o >= 0]
            if len(o):
                inv[t] = np.bincount(o).argmax()
    V = smooth_seams(V, F, inv, iters=seam_iters, fixed=fixed, fixed_limit=fixed_limit, min_edge=seam_min_edge)
    out = {}
    for k in np.unique(inv):
        sel = F[inv == k]
        used, local = np.unique(sel, return_inverse=True)
        out[decode(keys[k])] = (V[used], local.reshape(-1, 3), used)
    return out


def lines_per_part(pieces, n_vertices, seg, centre, step, shape):
    """Give every panel-line segment to the part it lies on (so a part carries its own lines when it is moved,
    exploded or hidden). seg: (n, 2, 3) in mesh mm. Each vertex marks its voxel with its part; the marks are spread
    to empty neighbouring voxels, then every segment midpoint takes the mark of its voxel. The grid is at most ~256
    cells long (a 1-px-per-voxel solid is ~1400): a cell stays below the decimated mesh's ~1 mm edge, and a dense
    int64 grid of 1400 x 480 x 280 rolled 18 times took ~50 s."""
    keys = list(pieces)
    k_ = max(1, int(np.ceil(max(shape) / 256)))
    step, shape = step * k_, [int(np.ceil(n / k_)) for n in shape]
    owner = np.zeros(n_vertices, int)
    for i, k in enumerate(keys):
        owner[pieces[k][2]] = i + 1
    G = np.zeros(tuple(int(n) + 4 for n in shape), np.int32)
    def cell(P):
        return tuple(np.clip(np.floor((P + centre) / step).astype(int) + 2, 0, np.array(G.shape) - 1).T)
    allV = np.zeros((n_vertices, 3))
    for k in keys:
        allV[pieces[k][2]] = pieces[k][0]
    G[cell(allV)] = owner
    for _ in range(3):
        empty = G == 0
        if not empty.any():
            break
        N = G.copy()
        for ax in range(3):
            N = np.maximum(N, np.roll(G, 1, ax))
            N = np.maximum(N, np.roll(G, -1, ax))
        G = np.where(empty, N, G)
    mid = seg.mean(1)
    lab = G[cell(mid)]
    return {k: seg[lab == i + 1] for i, k in enumerate(keys)}


def _resample_closed(P, spacing):
    Pc = np.vstack([P, P[:1]])
    d = np.linalg.norm(np.diff(Pc, axis=0), axis=1)
    t = np.concatenate([[0], np.cumsum(d)])
    n = max(8, int(t[-1] / spacing))
    s = np.linspace(0, t[-1], n, endpoint=False)
    return np.c_[np.interp(s, t, Pc[:, 0]), np.interp(s, t, Pc[:, 1])]


def seam_curves(L, sigma=1.6, max_side=360, min_len=12):
    """The outline of every region of a label image, as smooth closed curves in that image's pixels (x right,
    y down). The regions are made at about max_side pixels (segment.regions), so the outlines are traced there (not
    on the upscaled copy, whose pixel steps are several pixels tall), resampled evenly and smoothed with a Gaussian
    along the curve (sigma in those pixels), then scaled to the full image: continuous lines, no stair steps."""
    h, w = L.shape
    k = min(1.0, max_side / max(h, w))
    hs, ws = max(2, round(h * k)), max(2, round(w * k))
    Ls = np.asarray(Image.fromarray((L + 1).astype(np.uint16)).resize((ws, hs), Image.NEAREST)).astype(int) - 1
    sx, sy = w / ws, h / hs
    step = 0.25
    m_ = int(4 * sigma / step)
    g = np.exp(-0.5 * (np.arange(-m_, m_ + 1) * step / sigma) ** 2)
    g /= g.sum()
    # the outer outline is the silhouette (the body's own edge), not a panel line: points near it are left out (NaN)
    out_ = Ls < 0
    out_ = np.pad(out_, 1, constant_values=True)
    for _ in range(2):
        out_ = out_ | np.roll(out_, 1, 0) | np.roll(out_, -1, 0) | np.roll(out_, 1, 1) | np.roll(out_, -1, 1)
    out_ = out_[1:-1, 1:-1]
    curves = []
    for r in range(Ls.max() + 1):
        m = Ls == r
        if m.sum() < 4:
            continue
        for loop in outline.trace(m):
            if len(loop) < max(4, min_len * k):
                continue
            P = _resample_closed(np.asarray(loop, float), step)
            if len(P) > 2 * len(g):
                P = np.stack([np.convolve(np.r_[P[-m_:, i], P[:, i], P[:m_, i]], g, "valid") for i in (0, 1)], 1)
            P = _resample_closed(P, 1.0 / max(sx, sy))
            edge = out_[np.clip(np.round(P[:, 1]).astype(int), 0, hs - 1), np.clip(np.round(P[:, 0]).astype(int), 0, ws - 1)]
            if edge.all():
                continue
            P = np.c_[(P[:, 0] + 0.5) * sx - 0.5, (P[:, 1] + 0.5) * sy - 0.5]
            P[edge] = np.nan
            curves.append(P)
    return curves




def thin(m):
    """Zhang-Suen thinning: the drawn ink lines -> one-pixel centre lines (pure numpy)."""
    I = np.pad(np.asarray(m, bool), 1).astype(np.uint8)
    while True:
        changed = False
        for step in (0, 1):
            P = [I[:-2, 1:-1], I[:-2, 2:], I[1:-1, 2:], I[2:, 2:], I[2:, 1:-1], I[2:, :-2], I[1:-1, :-2], I[:-2, :-2]]
            B = sum(p.astype(int) for p in P)
            A = sum(((P[k] == 0) & (P[(k + 1) % 8] == 1)).astype(int) for k in range(8))
            if step == 0:
                c = (P[0] * P[2] * P[4] == 0) & (P[2] * P[4] * P[6] == 0)
            else:
                c = (P[0] * P[2] * P[6] == 0) & (P[0] * P[4] * P[6] == 0)
            kill = (I[1:-1, 1:-1] == 1) & (B >= 2) & (B <= 6) & (A == 1) & c
            if kill.any():
                I[1:-1, 1:-1][kill] = 0
                changed = True
        if not changed:
            return I[1:-1, 1:-1].astype(bool)


_N8 = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]


def skeleton_paths(sk):
    """One-pixel centre lines -> polylines (x, y) running between ends and junctions (and closed loops). A pixel
    is an end or a junction by its crossing number (how many separate line arms leave it), so the diagonal steps
    of a slanted line do not count as junctions."""
    I = np.pad(sk, 1).astype(np.uint8)
    P = [I[:-2, 1:-1], I[:-2, 2:], I[1:-1, 2:], I[2:, 2:], I[2:, 1:-1], I[2:, :-2], I[1:-1, :-2], I[:-2, :-2]]
    A = sum(((P[k] == 0) & (P[(k + 1) % 8] == 1)).astype(int) for k in range(8))
    pts = set(zip(*np.nonzero(sk)))
    node = {p for p in pts if A[p] != 2}
    nb = {p: [(p[0] + dy, p[1] + dx) for dy, dx in _N8 if (p[0] + dy, p[1] + dx) in pts] for p in pts}
    seen = set()
    paths = []

    def walk(a, b):
        path, prev, cur = [a, b], a, b
        while cur not in node:
            seen.add(cur)
            c = [q for q in nb[cur] if q != prev and q not in seen and q != path[0] or (q in node and q != prev and q != a)]
            if not c:
                if path[0] in nb[cur] and len(path) > 2:
                    path.append(path[0])                     # closed loop
                break
            c.sort(key=lambda q: (q not in node, abs(q[0] - cur[0]) + abs(q[1] - cur[1])))
            prev, cur = cur, c[0]
            path.append(cur)
        return path

    for a in node:
        for b in nb[a]:
            if b in seen or (b in node and b < a):
                continue
            paths.append(walk(a, b))
    for a in pts:                                            # closed loops with no end or junction
        if a not in seen and a not in node:
            nxt = [q for q in nb[a] if q not in seen]
            if nxt:
                seen.add(a)
                paths.append(walk(a, nxt[0]))
    return [np.array([(x, y) for y, x in p], float) for p in paths if len(p) > 1]


def _smooth_open(P, sigma, spacing=0.5):
    d = np.linalg.norm(np.diff(P, axis=0), axis=1)
    t = np.concatenate([[0], np.cumsum(d)])
    if t[-1] <= 0:
        return P
    s = np.linspace(0, t[-1], max(2, int(t[-1] / spacing) + 1))
    Q = np.c_[np.interp(s, t, P[:, 0]), np.interp(s, t, P[:, 1])]
    m = int(3 * sigma / spacing)
    if m < 1 or len(Q) < 3:
        return Q
    g = np.exp(-0.5 * (np.arange(-m, m + 1) * spacing / sigma) ** 2)
    g /= g.sum()
    closed = np.linalg.norm(Q[0] - Q[-1]) < 1.5
    if closed:
        R = np.stack([np.convolve(np.r_[Q[-m - 1:-1, i], Q[:, i], Q[1:m + 1, i]], g, "valid") for i in (0, 1)], 1)
    else:                                            # ends stay put (lines meet other lines there)
        R = np.stack([np.convolve(np.r_[2 * Q[0, i] - Q[m:0:-1, i], Q[:, i], 2 * Q[-1, i] - Q[-2:-m - 2:-1, i]], g, "valid")
                      for i in (0, 1)], 1)
    k = max(1, int(1.0 / spacing))
    return np.vstack([R[::k], R[-1:]])


def _box_mean(m, r):
    S = np.pad(np.asarray(m, float), ((r + 1, r), (r + 1, r))).cumsum(0).cumsum(1)
    k = 2 * r + 1
    return (S[k:, k:] - S[:-k, k:] - S[k:, :-k] + S[:-k, :-k]) / (k * k)


def ink_curves(ink, mask, sigma=2.5, min_frac=0.02, edge_px=4, exclude=None, dense=0.18):
    """The drawn lines themselves as smooth curves (x right, y down, pixels): centre lines of the ink, split at
    junctions, short bits (hatching, mesh grilles, text) dropped, each smoothed with a Gaussian along its length.
    Points on the silhouette edge are NaN (the body's own edge, not a panel line). Each curve ends with a NaN row,
    so a consumer treating curves as closed never joins its two ends."""
    sk = thin(ink & mask)
    for _ in range(3):                               # prune spurs: short branches off a line (ink bumps, line ends)
        spur = 0
        for P in skeleton_paths(sk):
            if len(P) > 1 and len(P) < 10:
                ends = [tuple(P[0].astype(int)), tuple(P[-1].astype(int))]
                deg = [int(sk[max(y - 1, 0):y + 2, max(x - 1, 0):x + 2].sum()) - 1 for x, y in ends]
                if min(deg) <= 1 and max(deg) >= 3:  # one free end, one junction: a spur
                    keep = 1 if deg[0] >= 3 else 0
                    for x, y in P.astype(int)[(1 if keep == 0 else 0):(len(P) - 1 if keep == 1 else len(P))]:
                        sk[y, x] = False
                    spur += 1
        if not spur:
            break
        sk = thin(sk)
    inner = mask.copy()
    for _ in range(edge_px):
        inner = inner & np.roll(inner, 1, 0) & np.roll(inner, -1, 0) & np.roll(inner, 1, 1) & np.roll(inner, -1, 1)
    # hatching and mesh grilles (ink everywhere) are a texture, not panel lines; nor is anything in `exclude`
    r = max(4, round(0.012 * max(mask.shape)))
    inner = inner & (_box_mean(sk, r) < dense)             # centre-line pixels per area: high only in hatching
    if exclude is not None:
        inner = inner & ~exclude
    min_len = min_frac * max(mask.shape)
    out = []
    for P in skeleton_paths(sk):
        if np.linalg.norm(np.diff(P, axis=0), axis=1).sum() < min_len:
            continue
        Q = _smooth_open(P, sigma)
        yi = np.clip(np.round(Q[:, 1]).astype(int), 0, mask.shape[0] - 1)
        xi = np.clip(np.round(Q[:, 0]).astype(int), 0, mask.shape[1] - 1)
        Q[~inner[yi, xi]] = np.nan
        ok = ~np.isnan(Q[:, 0])                     # pieces left between masked stretches: keep only long ones
        edges = np.flatnonzero(np.diff(np.r_[0, ok.astype(int), 0]))
        for a, b in zip(edges[::2], edges[1::2]):
            if b - a < 0.5 * min_len:
                Q[a:b] = np.nan
        if np.isnan(Q).all():
            continue
        out.append(np.vstack([Q, [np.nan, np.nan]]))
    return out
