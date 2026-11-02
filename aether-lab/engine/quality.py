"""Edge quality of a built model: no pixel staircase may reach the delivered mesh.

staircase score = share of a part's outline length that runs in pixel steps: at least 3 consecutive outline edges,
each at most 2 drawing pixels long, alternating between two near-perpendicular directions (H, V, H, V ...). An outline
of straight lines, circular arcs or smooth curves scores 0 %; a traced pixel mask or a voxel surface does not.

The outline of a part in a view = its silhouette edges there (an edge between a triangle facing the viewer and one
facing away) plus its open edges, projected into the drawing's pixels."""
import numpy as np


def view_outline(V, F, axes=(0, 1), depth=2):
    """Silhouette + open edges of a mesh seen along `depth`, as 2-D segments (n, 2, 2) in the mesh's units."""
    V = np.asarray(V, float)
    F = np.asarray(F, int)
    if not len(F):
        return np.zeros((0, 2, 2))
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    # facing the viewer = clearly (a side wall, normal ~ 0 along depth, is not; else top and bottom both qualify)
    front = n[:, depth] > 0.05 * np.linalg.norm(n, axis=1)
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    fid = np.tile(np.arange(len(F)), 3)
    key = np.sort(E, 1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    key, fid, E = key[order], fid[order], E[order]
    same = (key[1:] == key[:-1]).all(1)
    keep = []
    i = 0
    while i < len(key):                                     # each undirected edge: its 1 or 2 faces
        if i + 1 < len(key) and same[i]:
            if front[fid[i]] != front[fid[i + 1]]:
                keep.append(i)
            i += 2
        else:
            keep.append(i)                                  # open edge
            i += 1
    S = V[E[keep]][:, :, list(axes)]
    # one copy of each projected segment, none of zero length (a wall's vertical edges project to points)
    S = S[np.linalg.norm(S[:, 1] - S[:, 0], axis=1) > 1e-9]
    k = np.round(np.sort(S.reshape(-1, 4).reshape(-1, 2, 2), axis=1).reshape(-1, 4), 6)
    _, first = np.unique(k, axis=0, return_index=True)
    return S[np.sort(first)]


def _chains(S, tol=1e-6):
    """Segments -> polylines (point sequences) by joining shared end points."""
    if not len(S):
        return []
    P = np.round(S.reshape(-1, 2) / tol).astype(np.int64)
    _, ids = np.unique(P, axis=0, return_inverse=True)
    ids = ids.reshape(-1, 2)
    pts = {}
    for (a, b), seg in zip(ids, S):
        pts[a], pts[b] = seg[0], seg[1]
    adj = {}
    for a, b in ids:
        if a != b:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    seen, out = set(), []
    for start in [k for k, v in adj.items() if len(v) != 2] + list(adj):
        for nxt in adj.get(start, []):
            if (min(start, nxt), max(start, nxt)) in seen:
                continue
            line = [start]
            prev, cur = start, nxt
            seen.add((min(prev, cur), max(prev, cur)))
            line.append(cur)
            while len(adj.get(cur, [])) == 2:
                a, b = adj[cur]
                nn = b if a == prev else a
                e = (min(cur, nn), max(cur, nn))
                if e in seen:
                    break
                seen.add(e)
                prev, cur = cur, nn
                line.append(cur)
            out.append(np.array([pts[k] for k in line]))
    return out


def staircase(polylines, max_step=2.0, min_turn_deg=15.0, min_run=3):
    """(score %, outline length, staircase length) of polylines given in drawing pixels. A staircase is a zig-zag of
    short edges: at least min_run consecutive turns, between edges of at most max_step px, that each turn by at least
    min_turn_deg and alternate left / right. A straight edge does not turn, an arc or a spline turns one way, a pixel
    trace (marching squares: 0 / 45 deg half-pixel edges) or a voxel surface's silhouette zig-zags."""
    total = steps = 0.0
    for L in polylines:
        if len(L) < 3:
            if len(L) == 2:
                total += float(np.linalg.norm(L[1] - L[0]))
            continue
        d = np.diff(L, axis=0)
        ln = np.linalg.norm(d, axis=1)
        keep = ln > 1e-9
        d, ln = d[keep], ln[keep]
        total += ln.sum()
        if len(d) < 3:
            continue
        turn = np.degrees(np.arctan2(d[:-1, 0] * d[1:, 1] - d[:-1, 1] * d[1:, 0], (d[:-1] * d[1:]).sum(1)))
        zig = (ln[:-1] <= max_step) & (ln[1:] <= max_step) & (np.abs(turn) >= min_turn_deg)
        alt = np.r_[False, (turn[1:] * turn[:-1] < 0)]          # turn i reverses turn i-1
        flag = np.zeros(len(d), bool)
        run = 0
        for i in range(len(turn)):
            if zig[i] and (run == 0 or alt[i]):
                run += 1
                if run >= min_run:
                    flag[i - run + 1:i + 2] = True
            else:
                run = 1 if zig[i] else 0
        steps += ln[flag].sum()
    return (round(100 * steps / total, 2) if total else 0.0), round(total, 1), round(steps, 1)


def part_staircase(V, F, mm_per_px, axes=(0, 1), depth=2):
    """Staircase score of one part's outline in a view (V in mm; mm_per_px of that drawing)."""
    S = view_outline(V, F, axes, depth) / float(mm_per_px)
    return staircase(_chains(S))
