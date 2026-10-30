"""Mask -> clean outline polygons -> closed solids (pure numpy, no CAD kernel needed).

1. trace(): marching squares on the mask gives closed sub-pixel loops (filled cells 4-connected).
2. simplify(): Ramer-Douglas-Peucker removes the staircase (tolerance in pixels).
3. nest(): even nesting depth = outer boundary, odd = hole; each hole goes to the smallest outer that contains it.
4. triangulate(): ear clipping, holes joined to the outer ring by bridges (Eberly, "Triangulation by Ear Clipping").
5. extrude(): top + bottom caps and side walls only on the real boundary, so the solid is closed (watertight), its
   holes are real holes and it has no internal faces (the old row-of-boxes profile had hundreds).
"""
import numpy as np

# marching-squares segments per case (corners TL, TR, BR, BL -> bits 8, 4, 2, 1); edges T, R, B, L.
# Saddles (5, 10) are split so filled cells only join along edges (4-connectivity).
_CASES = {1: [("L", "B")], 2: [("B", "R")], 3: [("L", "R")], 4: [("T", "R")], 5: [("T", "R"), ("L", "B")],
          6: [("T", "B")], 7: [("T", "L")], 8: [("T", "L")], 9: [("T", "B")], 10: [("T", "L"), ("B", "R")],
          11: [("T", "R")], 12: [("L", "R")], 13: [("R", "B")], 14: [("L", "B")]}
# edge midpoints in doubled integer coordinates (row, col) relative to the cell's top-left corner
_EDGE = {"T": (0, 1), "R": (1, 2), "B": (2, 1), "L": (1, 0)}


def trace(mask):
    """Closed loops (lists of (x, y) pixel coordinates, y down) around the filled region of a boolean mask."""
    B = np.pad(np.asarray(mask, bool), 1).astype(np.int8)
    case = B[:-1, :-1] * 8 + B[:-1, 1:] * 4 + B[1:, 1:] * 2 + B[1:, :-1]
    adj = {}
    for c, segs in _CASES.items():
        ii, jj = np.nonzero(case == c)
        for a, b in segs:
            pa = np.stack([2 * ii + _EDGE[a][0], 2 * jj + _EDGE[a][1]], 1)
            pb = np.stack([2 * ii + _EDGE[b][0], 2 * jj + _EDGE[b][1]], 1)
            for p, q in zip(map(tuple, pa), map(tuple, pb)):
                adj.setdefault(p, []).append(q)
                adj.setdefault(q, []).append(p)
    loops, seen = [], set()
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [q for q in adj[cur] if q != prev]
            if not nxt:
                break
            q = nxt[0]
            if q == start:
                break
            if q in seen:
                break
            seen.add(q)
            loop.append(q)
            prev, cur = cur, q
        if len(loop) >= 4:
            # doubled (row, col) of the padded grid -> pixel (x, y) of the original mask (pixel centres at integers)
            loops.append(np.array([[c / 2 - 1, r / 2 - 1] for r, c in loop], float))
    return loops


def simplify(P, eps=0.7):
    """Ramer-Douglas-Peucker on a closed loop (iterative)."""
    P = np.asarray(P, float)
    n = len(P)
    if n < 5:
        return P
    # split the loop at its two farthest-apart points so both halves are open chains
    i0 = 0
    i1 = int(np.argmax(np.linalg.norm(P - P[0], axis=1)))
    keep = np.zeros(n, bool)
    keep[[i0, i1]] = True
    stack = [(i0, i1), (i1, n)]
    Q = np.vstack([P, P[:1]])
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        seg = Q[b] - Q[a]
        L = np.linalg.norm(seg)
        mid = Q[a + 1:b]
        if L < 1e-12:
            dist = np.linalg.norm(mid - Q[a], axis=1)
        else:
            dist = np.abs(seg[0] * (mid[:, 1] - Q[a, 1]) - seg[1] * (mid[:, 0] - Q[a, 0])) / L
        k = int(np.argmax(dist))
        if dist[k] > eps:
            m = a + 1 + k
            keep[m % n] = True
            stack += [(a, m), (m, b)]
    return P[keep]


def area(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _inside(pt, P):
    x, y = pt
    xs, ys = P[:, 0], P[:, 1]
    xn, yn = np.roll(xs, -1), np.roll(ys, -1)
    c = ((ys > y) != (yn > y)) & (x < (xn - xs) * (y - ys) / np.where(yn == ys, 1e-12, yn - ys) + xs)
    return bool(c.sum() % 2)


def nest(loops, min_area=4.0):
    """[(outer, [holes])], outers counter-clockwise and holes clockwise (in a y-up frame)."""
    loops = [L for L in loops if abs(area(L)) >= min_area]
    loops.sort(key=lambda L: -abs(area(L)))
    depth, parent = [], []
    for i, L in enumerate(loops):
        cont = [j for j in range(i) if _inside(L[0], loops[j])]
        depth.append(len(cont))
        parent.append(cont[-1] if cont else None)    # the smallest container (sorted by area)
    out = {}
    for i, L in enumerate(loops):
        if depth[i] % 2 == 0:
            out[i] = (L if area(L) > 0 else L[::-1], [])
    for i, L in enumerate(loops):
        if depth[i] % 2 == 1 and parent[i] in out:
            out[parent[i]][1].append(L if area(L) < 0 else L[::-1])
    return list(out.values())


def _seg_cross(p, q, A, B):
    """Does segment p-q properly cross any segment A[i]-B[i]?"""
    d1 = (B[:, 0] - A[:, 0]) * (p[1] - A[:, 1]) - (B[:, 1] - A[:, 1]) * (p[0] - A[:, 0])
    d2 = (B[:, 0] - A[:, 0]) * (q[1] - A[:, 1]) - (B[:, 1] - A[:, 1]) * (q[0] - A[:, 0])
    d3 = (q[0] - p[0]) * (A[:, 1] - p[1]) - (q[1] - p[1]) * (A[:, 0] - p[0])
    d4 = (q[0] - p[0]) * (B[:, 1] - p[1]) - (q[1] - p[1]) * (B[:, 0] - p[0])
    return bool(np.any((d1 * d2 < -1e-12) & (d3 * d4 < -1e-12)))


def _bridge(outer, holes):
    """Join holes to the outer ring with zero-width bridges -> one simple ring."""
    ring = [np.asarray(p, float) for p in outer]
    for h in sorted(holes, key=lambda H: -np.max(H[:, 0])):
        k = int(np.argmax(h[:, 0]))
        M = h[k]
        R = np.array(ring)
        others = [H for H in holes if H is not h]
        edges_a = [R, *others, h]
        edges_b = [np.roll(R, -1, 0), *[np.roll(H, -1, 0) for H in others], np.roll(h, -1, 0)]
        A, Bn = np.vstack(edges_a), np.vstack(edges_b)
        best = None
        for i in np.argsort(np.linalg.norm(R - M, axis=1)):
            V = R[i]
            ok = ~(np.all(np.isclose(A, V), 1) | np.all(np.isclose(Bn, V), 1) |
                   np.all(np.isclose(A, M), 1) | np.all(np.isclose(Bn, M), 1))
            if not _seg_cross(M, V, A[ok], Bn[ok]):
                best = int(i)
                break
        if best is None:
            best = int(np.argmin(np.linalg.norm(R - M, axis=1)))
        hk = [h[(k + j) % len(h)] for j in range(len(h))] + [M]
        ring = ring[:best + 1] + hk + ring[best:]
    return np.array(ring)


def triangulate(outer, holes=()):
    """Ear clipping of a polygon with holes. Returns (points (N, 2), triangles (M, 3)) indexing points."""
    P = _bridge(np.asarray(outer, float), [np.asarray(h, float) for h in holes]) if len(holes) else np.asarray(outer, float)
    idx = list(range(len(P)))
    tris = []

    def convex(a, b, c):
        return (P[b, 0] - P[a, 0]) * (P[c, 1] - P[a, 1]) - (P[b, 1] - P[a, 1]) * (P[c, 0] - P[a, 0]) > 1e-12

    guard = 0
    while len(idx) > 3 and guard < 4 * len(P) * len(P):
        n = len(idx)
        clipped = False
        for t in range(n):
            a, b, c = idx[t - 1], idx[t], idx[(t + 1) % n]
            if not convex(a, b, c):
                continue
            rest = np.array([i for i in idx if i not in (a, b, c)])
            if len(rest):
                Q = P[rest]
                Q = Q[~(np.all(np.isclose(Q, P[a]), 1) | np.all(np.isclose(Q, P[b]), 1) | np.all(np.isclose(Q, P[c]), 1))]
                if len(Q):
                    v0, v1, v2 = P[a], P[b], P[c]
                    d1 = (Q[:, 0] - v1[0]) * (v0[1] - v1[1]) - (v0[0] - v1[0]) * (Q[:, 1] - v1[1])
                    d2 = (Q[:, 0] - v2[0]) * (v1[1] - v2[1]) - (v1[0] - v2[0]) * (Q[:, 1] - v2[1])
                    d3 = (Q[:, 0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (Q[:, 1] - v0[1])
                    if np.any((d1 <= 0) & (d2 <= 0) & (d3 <= 0)) or np.any((d1 >= 0) & (d2 >= 0) & (d3 >= 0)):
                        continue
            tris.append((a, b, c))
            idx.pop(t)
            clipped = True
            break
        guard += 1
        if not clipped:                     # degenerate leftovers (collinear bridge points): drop one vertex
            idx.pop(0)
    if len(idx) == 3 and convex(*idx):
        tris.append(tuple(idx))
    return P, np.array(tris, int).reshape(-1, 3)


def extrude(outer, holes=(), thickness=5.0):
    """Closed prism of a polygon with holes, centred on z = 0. Returns V (N, 3), F (M, 3), outward normals."""
    P, T = triangulate(outer, holes)
    h2 = thickness / 2
    n = len(P)
    V = [np.c_[P, np.full(n, -h2)], np.c_[P, np.full(n, h2)]]
    F = [T[:, ::-1], T + n]                                   # bottom faces down, top faces up
    off = 2 * n
    for ring in [np.asarray(outer, float), *[np.asarray(h, float) for h in holes]]:
        m = len(ring)
        V += [np.c_[ring, np.full(m, -h2)], np.c_[ring, np.full(m, h2)]]
        j = np.arange(m)
        a, b = off + j, off + (j + 1) % m
        F += [np.stack([a, b, b + m], 1), np.stack([a, b + m, a + m], 1)]
        off += 2 * m
    return np.vstack(V), np.vstack(F).astype(int)


def mask_polygons(mask, mm_per_px, origin_px, eps_px=0.7, min_area_px=12):
    """A mask -> outline polygons in mm (x right, y up) relative to origin_px, ready for geometry.outline."""
    out = []
    for o, hs in nest([simplify(L, eps_px) for L in trace(mask)], min_area_px):
        def to_mm(L):
            return [[round((x - origin_px[0]) * mm_per_px, 3), round((origin_px[1] - y) * mm_per_px, 3)] for x, y in L]
        # y flips (image y down -> mm y up), which reverses orientation: re-orient after the flip
        oo = np.array(to_mm(o))
        if area(oo) < 0:
            oo = oo[::-1]
        hh = []
        for h in hs:
            a = np.array(to_mm(h))
            hh.append((a if area(a) < 0 else a[::-1]).tolist())
        out.append({"outer": oo.tolist(), "holes": hh})
    return out


def fill_holes(mask):
    """Fill enclosed background (binary hole filling, flood from the border) - pure numpy."""
    m = np.asarray(mask, bool)
    bg = ~np.pad(m, 1)
    reach = np.zeros_like(bg)
    reach[0, :] = reach[-1, :] = reach[:, 0] = reach[:, -1] = True
    reach &= bg
    while True:
        grow = reach.copy()
        grow[1:, :] |= reach[:-1, :]
        grow[:-1, :] |= reach[1:, :]
        grow[:, 1:] |= reach[:, :-1]
        grow[:, :-1] |= reach[:, 1:]
        grow &= bg
        if (grow == reach).all():
            break
        reach = grow
    return ~reach[1:-1, 1:-1]
