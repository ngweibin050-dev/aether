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


def _outline_edges(V, F, depth):
    """Index pairs of a mesh's silhouette + open edges seen along `depth` (as view_outline, but vertex ids)."""
    V = np.asarray(V, float)
    F = np.asarray(F, int)
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    front = n[:, depth] > 0.05 * np.linalg.norm(n, axis=1)
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    fid = np.tile(np.arange(len(F)), 3)
    key = np.sort(E, 1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    key, fid = key[order], fid[order]
    out, i = [], 0
    while i < len(key):
        if i + 1 < len(key) and (key[i] == key[i + 1]).all():
            if front[fid[i]] != front[fid[i + 1]]:
                out.append(key[i])
            i += 2
        else:
            out.append(key[i])
            i += 1
    return np.array(out, int).reshape(-1, 2)


def straighten_zigzags(V, pieces, view_of, mm_per_px, limit_mm, fixed=None, fixed_limit_mm=None, rounds=3):
    """Remove pixel zig-zags from every part's outline where the staircase score finds them: the inner vertices of a
    zig-zag run move onto the straight chord between the run's ends (3-D), by at most limit_mm (fixed_limit_mm for
    `fixed` vertices, e.g. on a drawn outline). V is the shared vertex array; pieces[k] = (Vk, Fk, used) with Fk
    indexing Vk = V[used], so a vertex moved here moves in every part that has it (no crack). Returns V."""
    V = np.asarray(V, float).copy()
    for _ in range(rounds):
        moved = 0
        for k, (_, Fk, used) in pieces.items():
            axes, depth = view_of(k)
            E = used[_outline_edges(V[used], Fk, depth)]
            adj = {}
            for a, b in E:
                adj.setdefault(a, []).append(b)
                adj.setdefault(b, []).append(a)
            seen = set()
            for s0 in list(adj):
                for nxt in adj[s0]:
                    if (min(s0, nxt), max(s0, nxt)) in seen:
                        continue
                    chain, prev, cur = [s0, nxt], s0, nxt
                    seen.add((min(s0, nxt), max(s0, nxt)))
                    while len(adj.get(cur, [])) == 2:
                        a, b = adj[cur]
                        nn = b if a == prev else a
                        e = (min(cur, nn), max(cur, nn))
                        if e in seen:
                            break
                        seen.add(e)
                        prev, cur = cur, nn
                        chain.append(cur)
                    if len(chain) < 4:
                        continue
                    ids = np.array(chain)
                    P = V[ids][:, list(axes)] / mm_per_px
                    d = np.diff(P, axis=0)
                    ln = np.linalg.norm(d, axis=1)
                    turn = np.degrees(np.arctan2(d[:-1, 0] * d[1:, 1] - d[:-1, 1] * d[1:, 0], (d[:-1] * d[1:]).sum(1)))
                    zig = (ln[:-1] <= 2) & (ln[1:] <= 2) & (np.abs(turn) >= 15)
                    i = 0
                    while i < len(turn):
                        j = i
                        while j < len(turn) and zig[j] and (j == i or turn[j] * turn[j - 1] < 0):
                            j += 1
                        if j - i >= 2:                      # a zig-zag run: vertices i+1 .. j between ends i and j+1
                            A, B = V[ids[i]], V[ids[j + 1]]
                            for m in range(i + 1, j + 1):
                                v = ids[m]
                                t = np.clip(np.dot(V[v] - A, B - A) / max(np.dot(B - A, B - A), 1e-12), 0, 1)
                                D = A + t * (B - A) - V[v]
                                lim = fixed_limit_mm if fixed is not None and fixed[v] and fixed_limit_mm is not None else limit_mm
                                n_ = np.linalg.norm(D)
                                V[v] += D * min(1.0, lim / max(n_, 1e-12))
                                moved += 1
                            i = j
                        else:
                            i += 1
        if not moved:
            break
    return V


def _face_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def folds(V, F):
    """3-D surface quality of a delivered mesh, which the per-view staircase cannot see: a thin rim (a wing's trailing
    edge) whose vertices crossed over shows as a sawtooth of dark facets. folded_edges = edges whose two triangles face
    more than 120 deg apart; flipped_triangles = triangles facing away from the mean of their neighbours (dot < -0.3).
    A clean surface has a few at true knife edges. G's X-3 after seam smoothing: 525 / 191; with keep_unflipped after
    it (sheet.py): 153 / 27."""
    V = np.asarray(V, float)
    F = np.asarray(F, int)
    if not len(F):
        return {"folded_edges": 0, "flipped_triangles": 0}
    nu = _face_normals(V, F)
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    fid = np.tile(np.arange(len(F)), 3)
    key = np.sort(E, 1)
    o = np.lexsort((key[:, 1], key[:, 0]))
    key, fid = key[o], fid[o]
    same = (key[1:] == key[:-1]).all(1)
    a, b = fid[:-1][same], fid[1:][same]
    acc = np.zeros((len(F), 3))
    np.add.at(acc, a, nu[b])
    np.add.at(acc, b, nu[a])
    flip = (nu * acc).sum(1) < -0.3 * np.linalg.norm(acc, axis=1)
    return {"folded_edges": int(((nu[a] * nu[b]).sum(1) < -0.5).sum()), "flipped_triangles": int(flip.sum())}


def roughness(V, F, crease_deg=40.0):
    """Crumple of a delivered mesh's smooth surfaces (a car body that looks like crushed foil): over every edge whose
    two triangles meet at less than crease_deg (real creases and knife edges excluded), the length-weighted RMS of the
    angle between their normals, in degrees, and the share of that edge length bending more than 10 deg. A smooth
    panel scores ~1 deg; a voxel surface held to its voxels several."""
    V, F = _weld(V, F)
    nu = _face_normals(V, F)
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    fid = np.tile(np.arange(len(F)), 3)
    key = np.sort(E, 1)
    o = np.lexsort((key[:, 1], key[:, 0]))
    key, fid = key[o], fid[o]
    same = np.nonzero((key[1:] == key[:-1]).all(1))[0]
    ang = np.degrees(np.arccos(np.clip((nu[fid[same]] * nu[fid[same + 1]]).sum(1), -1, 1)))
    ln = np.linalg.norm(V[key[same, 0]] - V[key[same, 1]], axis=1)
    s = ang < crease_deg
    if not s.any():
        return {"rms_deg": 0.0, "bent_over_10deg_pct": 0.0}
    return {"rms_deg": round(float(np.sqrt((ln[s] * ang[s] ** 2).sum() / ln[s].sum())), 2),
            "bent_over_10deg_pct": round(float(100 * ln[s][ang[s] > 10].sum() / ln[s].sum()), 1)}


def mesh_staircase(V, F, mm_per_px, max_step=6.0):
    """3-D edge quality of a whole delivered mesh: the staircase rule on ALL its silhouette edges (wall rims inside the
    outline too) in each of the three axis views, with steps up to max_step px. part_staircase checks each part only in
    the view it was cut from with 2-px steps; a decimated mesh (G: median edge ~7 px) keeps a voxel step on a swept thin
    edge as a row of ribs a few px apart, seen in a close-up but in neither. G's X-3, top view: 334 px before the
    1-px build, 635 px after it. Returns {"side"|"top"|"front": staircase px}."""
    V, F = _weld(V, F)
    return {nm: staircase(_chains(view_outline(V, F, ax, dp) / float(mm_per_px)), max_step=max_step)[2]
            for nm, ax, dp in (("side", (0, 2), 1), ("top", (0, 1), 2), ("front", (1, 2), 0))}


def _weld(V, F, tol=0.02):
    """One vertex per position (parts are delivered as separate meshes that share their seam vertices' positions)."""
    _, ids, inv = np.unique(np.round(np.asarray(V, float) / tol).astype(np.int64), axis=0, return_index=True,
                            return_inverse=True)
    return np.asarray(V, float)[ids], inv.reshape(-1)[np.asarray(F, int)]


def keep_unflipped(V0, V1, F, rounds=20):
    """V1 = V0 after a smoothing / straightening step; every triangle that step turned by more than 90 deg gets its
    vertices back from V0 (rounds times, as a put-back vertex can turn a neighbour). Returns (V, vertices put back)."""
    V0 = np.asarray(V0, float)
    V = np.asarray(V1, float).copy()
    F = np.asarray(F, int)
    n0 = np.cross(V0[F[:, 1]] - V0[F[:, 0]], V0[F[:, 2]] - V0[F[:, 0]])
    back = np.zeros(len(V), bool)
    for _ in range(rounds):
        n1 = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
        bad = (n0 * n1).sum(1) < 0
        ids = np.unique(F[bad])
        ids = ids[~back[ids] | (np.abs(V[ids] - V0[ids]).max(1) > 0)]
        if not len(ids):
            break
        V[ids] = V0[ids]
        back[ids] = True
    return V, int(back.sum())


def part_staircase(V, F, mm_per_px, axes=(0, 1), depth=2):
    """Staircase score of one part's outline in a view (V in mm; mm_per_px of that drawing)."""
    S = view_outline(V, F, axes, depth) / float(mm_per_px)
    return staircase(_chains(S))
