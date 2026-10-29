"""Parametric parts -> triangle meshes (mm). One geometry source for display and physics.

Each part: {"id", "name", "type", "params": {...}, "position": [x,y,z], "rotation": [rx,ry,rz] (deg),
            "scale": [sx,sy,sz], "parent": id|None, "visible": bool, "brightness": 0..1}
Meshes are built in the part's local frame; `world_mesh` applies the transform chain.
"""
import numpy as np

# ---------------- primitive builders (local frame, z = axis of revolution) ----------------


def _lathe(profile, segments=48, closed_top=True, closed_bottom=True):
    """Revolve (r, z) profile points around the z axis."""
    prof = np.asarray(profile, float)
    m = len(prof)
    t = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    V = np.stack([np.outer(prof[:, 0], c), np.outer(prof[:, 0], s),
                  np.repeat(prof[:, 1:2], segments, 1)], -1).reshape(-1, 3)
    F = []
    for i in range(m - 1):
        for j in range(segments):
            a, b = i * segments + j, i * segments + (j + 1) % segments
            c2, d = a + segments, b + segments
            F += [[a, b, d], [a, d, c2]]
    V = list(V)
    if closed_bottom and prof[0, 0] > 0:
        ci = len(V)
        V.append([0, 0, prof[0, 1]])
        F += [[ci, (j + 1) % segments, j] for j in range(segments)]
    if closed_top and prof[-1, 0] > 0:
        ci = len(V)
        V.append([0, 0, prof[-1, 1]])
        base = (m - 1) * segments
        F += [[ci, base + j, base + (j + 1) % segments] for j in range(segments)]
    return np.asarray(V, float), np.asarray(F, int)


def _extrude(outer, height, holes=()):
    """Extrude a closed 2D polygon (with optional circular hole polygons) along z, centred."""
    outer = np.asarray(outer, float)
    n = len(outer)
    h2 = height / 2
    V = [np.c_[outer, np.full(n, -h2)], np.c_[outer, np.full(n, h2)]]
    F = []
    for j in range(n):  # side walls
        a, b = j, (j + 1) % n
        F += [[a, b, n + b], [a, n + b, n + a]]
    off = 2 * n
    if holes:
        hole = np.asarray(holes[0], float)
        assert len(hole) == n, "hole must have the same sample count as outer"
        V += [np.c_[hole, np.full(n, -h2)], np.c_[hole, np.full(n, h2)]]
        for j in range(n):
            a, b = j, (j + 1) % n
            F += [[off + a, off + n + b, off + b], [off + a, off + n + a, off + n + b]]  # bore wall
            F += [[a, off + b, b], [a, off + a, off + b]]                                # bottom ring
            F += [[n + a, n + b, off + n + b], [n + a, off + n + b, off + n + a]]        # top ring
    else:
        V += [np.array([[0, 0, -h2], [0, 0, h2]])]
        F += [[off, (j + 1) % n, j] for j in range(n)]
        F += [[off + 1, n + j, n + (j + 1) % n] for j in range(n)]
    return np.vstack([np.atleast_2d(v) for v in V]), np.asarray(F, int)


def box(w=10, d=10, h=10):
    x, y, z = w / 2, d / 2, h / 2
    V = np.array([[-x, -y, -z], [x, -y, -z], [x, y, -z], [-x, y, -z],
                  [-x, -y, z], [x, -y, z], [x, y, z], [-x, y, z]], float)
    F = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                  [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    return V, F


def cylinder(radius=5, height=10, segments=48):
    return _lathe([[radius, -height / 2], [radius, height / 2]], segments)


def tube(outer=5, inner=3, height=10, segments=48):
    t = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    return _extrude(np.c_[outer * np.cos(t), outer * np.sin(t)], height,
                    holes=[np.c_[inner * np.cos(t), inner * np.sin(t)]])


def cone(r_bottom=5, r_top=0.01, height=10, segments=48):
    return _lathe([[r_bottom, -height / 2], [max(r_top, 1e-3), height / 2]], segments)


def sphere(radius=5, segments=32):
    a = np.linspace(-np.pi / 2, np.pi / 2, segments // 2 + 1)[1:-1]
    prof = [[1e-3, -radius]] + [[radius * np.cos(x), radius * np.sin(x)] for x in a] + [[1e-3, radius]]
    return _lathe(prof, segments)


def torus(radius=10, tube_radius=2, segments=48, sides=16):
    u = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    v = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    U, Vv = np.meshgrid(u, v, indexing="ij")
    X = (radius + tube_radius * np.cos(Vv)) * np.cos(U)
    Y = (radius + tube_radius * np.cos(Vv)) * np.sin(U)
    Z = tube_radius * np.sin(Vv)
    V = np.stack([X, Y, Z], -1).reshape(-1, 3)
    F = []
    for i in range(segments):
        for j in range(sides):
            a = i * sides + j
            b = ((i + 1) % segments) * sides + j
            c = ((i + 1) % segments) * sides + (j + 1) % sides
            d = i * sides + (j + 1) % sides
            F += [[a, b, c], [a, c, d]]
    return V, np.asarray(F, int)


def gear(teeth=12, radius=15, thickness=5, tooth_depth=None, bore=None, segments=None):
    tooth_depth = tooth_depth or radius * 0.15
    bore = radius * 0.3 if bore is None else bore
    n = segments or max(96, teeth * 12)
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    tooth = np.clip(np.cos(teeth * t) * 3, -1, 1) * 0.5 + 0.5
    r = radius - tooth_depth + tooth_depth * tooth
    outer = np.c_[r * np.cos(t), r * np.sin(t)]
    if bore > 0:
        return _extrude(outer, thickness, holes=[np.c_[bore * np.cos(t), bore * np.sin(t)]])
    return _extrude(outer, thickness)


def nozzle(throat=10, exit=30, length=60, chamber=18, chamber_length=30, segments=48):
    """Rocket-style combustion chamber + converging/diverging bell (z from chamber top down)."""
    zs = np.linspace(0, 1, 16)
    bell = [[throat + (exit - throat) * (1 - (1 - s) ** 2), -chamber_length - 8 - s * length] for s in zs]
    prof = [[chamber, 0], [chamber, -chamber_length + 4], [throat * 1.15, -chamber_length - 4]] + bell
    prof = np.asarray(prof[::-1], float)
    return _lathe(prof, segments, closed_top=True, closed_bottom=False)


def blade_ring(count=12, inner=8, outer=20, thickness=1.0, height=6, twist=25):
    Vs, Fs, off = [], [], 0
    for k in range(count):
        V, F = box(outer - inner, thickness, height)
        V = V + [(outer + inner) / 2, 0, 0]
        V = V @ _rot([twist, 0, 0]).T
        V = V @ _rot([0, 0, 360 * k / count]).T
        Vs.append(V)
        Fs.append(F + off)
        off += len(V)
    return np.vstack(Vs), np.vstack(Fs)


def pipe(points, radius=2, segments=16):
    """Tube swept along a polyline of 3D points (mm)."""
    P = np.asarray(points, float)
    Vs, Fs, off = [], [], 0
    for a, b in zip(P[:-1], P[1:]):
        L = np.linalg.norm(b - a)
        if L < 1e-6:
            continue
        V, F = _lathe([[radius, 0], [radius, L]], segments, False, False)
        d = (b - a) / L
        V = V @ _align_z(d).T + a
        Vs.append(V)
        Fs.append(F + off)
        off += len(V)
    return np.vstack(Vs), np.vstack(Fs)


def coil(radius=10, wire=1.2, turns=6, pitch=3, segments=12):
    """Helical coil (motor winding / spring)."""
    t = np.linspace(0, 2 * np.pi * turns, int(turns * 24))
    pts = np.c_[radius * np.cos(t), radius * np.sin(t), (t / (2 * np.pi) - turns / 2) * pitch]
    return pipe(pts, wire, segments)


BUILDERS = {"box": box, "cylinder": cylinder, "tube": tube, "cone": cone, "sphere": sphere,
            "torus": torus, "gear": gear, "nozzle": nozzle, "blade_ring": blade_ring,
            "pipe": pipe, "coil": coil}

PARAM_HELP = {
    "box": "w, d, h", "cylinder": "radius, height", "tube": "outer, inner, height",
    "cone": "r_bottom, r_top, height", "sphere": "radius", "torus": "radius, tube_radius",
    "gear": "teeth, radius, thickness, bore", "nozzle": "throat, exit, length, chamber, chamber_length",
    "blade_ring": "count, inner, outer, thickness, height, twist", "pipe": "points [[x,y,z],...], radius",
    "coil": "radius, wire, turns, pitch",
}

# ---------------- transforms ----------------


def _rot(deg):
    rx, ry, rz = np.radians(deg)
    Rx = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
    Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Rz = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx       # matches three.js Euler order "ZYX"


def _align_z(d):
    """Rotation taking +z to unit vector d."""
    z = np.array([0, 0, 1.0])
    v = np.cross(z, d)
    c = float(np.dot(z, d))
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1, -1, -1.0])
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def matrix(part):
    M = np.eye(4)
    M[:3, :3] = _rot(part.get("rotation", [0, 0, 0])) @ np.diag(part.get("scale", [1, 1, 1]))
    M[:3, 3] = part.get("position", [0, 0, 0])
    return M


def world_matrix(part, by_id):
    M = matrix(part)
    p = part.get("parent")
    seen = set()
    while p and p in by_id and p not in seen:
        seen.add(p)
        M = matrix(by_id[p]) @ M
        p = by_id[p].get("parent")
    return M


def local_mesh(part, cache=None):
    if part["type"] == "mesh":            # imported (already decimated) mesh
        return np.asarray(part["params"]["vertices"], float).reshape(-1, 3), \
            np.asarray(part["params"]["faces"], int).reshape(-1, 3)
    if part["type"] == "group":
        return np.zeros((0, 3)), np.zeros((0, 3), int)
    fn = BUILDERS[part["type"]]
    return fn(**part.get("params", {}))


def world_mesh(part, by_id):
    V, F = local_mesh(part)
    if len(V) == 0:
        return V, F
    M = world_matrix(part, by_id)
    return V @ M[:3, :3].T + M[:3, 3], F


def scene_meshes(parts):
    by_id = {p["id"]: p for p in parts}
    return [(p, *world_mesh(p, by_id)) for p in parts if p.get("visible", True)]


# ---------------- surface sampling ----------------


def sample_surface(parts, n_points=4000, seed=0):
    """Area-weighted random points on all visible parts. Returns points (N,3), normals (N,3), part index."""
    rng = np.random.default_rng(seed)
    tris, norms, owner, weight = [], [], [], []
    for k, (p, V, F) in enumerate(scene_meshes(parts)):
        if len(F) == 0:
            continue
        T = V[F]
        nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        area = 0.5 * np.linalg.norm(nrm, axis=1)
        ok = area > 1e-12
        tris.append(T[ok])
        norms.append(nrm[ok] / (2 * area[ok, None]))
        owner.append(np.full(ok.sum(), k))
        weight.append(area[ok] * p.get("brightness", 1.0))
    if not tris:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0, int)
    T, N, O, W = np.vstack(tris), np.vstack(norms), np.concatenate(owner), np.concatenate(weight)
    idx = rng.choice(len(T), size=n_points, p=W / W.sum())
    u, v = rng.random(n_points), rng.random(n_points)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    t = T[idx]
    pts = t[:, 0] + u[:, None] * (t[:, 1] - t[:, 0]) + v[:, None] * (t[:, 2] - t[:, 0])
    return pts, N[idx], O[idx]


def bounds(parts):
    ms = [V for _, V, _ in scene_meshes(parts) if len(V)]
    if not ms:
        return np.zeros(3), np.zeros(3)
    allv = np.vstack(ms)
    return allv.min(0), allv.max(0)


def decimate(V, F, target_faces):
    """Vertex-clustering decimation: snap vertices to a grid sized to hit ~target_faces."""
    V, F = np.asarray(V, float), np.asarray(F, int)
    if len(F) <= target_faces:
        return V, F
    lo, hi = V.min(0), V.max(0)
    size = float(np.max(hi - lo)) or 1.0
    cells = max(4, int(np.sqrt(target_faces / 2)))
    for _ in range(8):
        q = np.floor((V - lo) / (size / cells)).astype(np.int64)
        keys, inv = np.unique(q, axis=0, return_inverse=True)
        inv = inv.ravel()
        nv = np.zeros((len(keys), 3))
        np.add.at(nv, inv, V)
        nv /= np.bincount(inv, minlength=len(keys))[:, None]
        nf = inv[F]
        good = (nf[:, 0] != nf[:, 1]) & (nf[:, 1] != nf[:, 2]) & (nf[:, 0] != nf[:, 2])
        nf = nf[good]
        if len(nf) <= target_faces * 1.1:
            return nv, nf
        cells = int(cells * 0.8)
    return nv, nf
