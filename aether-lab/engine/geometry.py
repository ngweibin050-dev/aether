"""Parametric parts -> triangle meshes (mm). One geometry source for display and physics.

Each part: {"id", "name", "type", "params": {...}, "position": [x,y,z], "rotation": [rx,ry,rz] (deg),
            "scale": [sx,sy,sz], "parent": id|None, "visible": bool, "brightness": 0..1}
Meshes are built in the part's local frame; `world_mesh` applies the transform chain.
"""
import json

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


STANDARD_MODULES = (0.5, 0.6, 0.8, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20)   # ISO 54 series I


def snap_module(m):
    return min(STANDARD_MODULES, key=lambda s: abs(np.log(s / m)))


def gear_profile(teeth=12, module=2.0, pressure_angle=20.0, phase=0.0, flank_pts=7):
    """Involute spur gear outline (standard full-depth teeth, no profile shift), counter-clockwise.

    Pitch radius r = m z / 2, base rb = r cos(alpha), tip ra = r + m, root rf = r - 1.25 m. Flank = involute of the
    base circle; tooth half-angle at radius R: pi/(2z) + inv(alpha) - inv(alpha_R), inv(a) = tan a - a,
    alpha_R = arccos(rb / R). Below the base circle (small tooth counts) the flank continues radially.
    phase (deg): rotation of tooth 0, which is centred on the +x axis at phase 0."""
    z = int(teeth)
    m = float(module)
    al = np.radians(pressure_angle)
    r = m * z / 2
    rb, ra, rf = r * np.cos(al), r + m, r - 1.25 * m

    def inv(a):
        return np.tan(a) - a

    def half(R):
        return np.pi / (2 * z) + inv(al) - inv(np.arccos(np.clip(rb / R, -1, 1)))

    R = np.linspace(max(rb, rf), ra, flank_pts)
    h = half(R)
    pts = []
    for k in range(z):
        c = np.radians(phase) + 2 * np.pi * k / z
        # root -> right flank up -> tip arc -> left flank down
        if rf < rb:
            pts.append((rf, c - h[0]))
        pts += [(Ri, c - hi) for Ri, hi in zip(R, h)]
        pts += [(ra, c + t) for t in np.linspace(-h[-1], h[-1], 4)[1:-1]]
        pts += [(Ri, c + hi) for Ri, hi in zip(R[::-1], h[::-1])]
        if rf < rb:
            pts.append((rf, c + h[0]))
        # root arc to the next tooth
        a0, a1 = c + h[0], c + 2 * np.pi / z - h[0]
        pts += [(rf, t) for t in np.linspace(a0, a1, 5)[1:-1]]
    P = np.array([[Ri * np.cos(t), Ri * np.sin(t)] for Ri, t in pts])
    return P, {"module": m, "teeth": z, "pitch_radius": r, "base_radius": rb, "tip_radius": ra, "root_radius": rf,
               "pressure_angle": pressure_angle}


def gear(teeth=12, radius=None, thickness=5, module=None, pressure_angle=20.0, bore=None, phase=0.0,
         tooth_depth=None, segments=None):
    """Involute spur gear, axis = local z. Give module (mm) or the old tip radius (module = 2 radius / (teeth + 2)).
    tooth_depth / segments are accepted for old designs and ignored (the involute fixes the tooth shape)."""
    z = max(6, int(round(teeth)))
    if module is None:
        module = 2 * float(radius if radius is not None else 15) / (z + 2)
    outer, g = gear_profile(z, module, pressure_angle, phase)
    bore = g["root_radius"] * 0.35 if bore is None else float(bore)
    if bore > 0:
        bore = min(bore, 0.8 * g["root_radius"])
        ang = np.arctan2(outer[:, 1], outer[:, 0])          # star-shaped: bore points at the same angles
        return _extrude(outer, thickness, holes=[np.c_[bore * np.cos(ang), bore * np.sin(ang)]])
    return _extrude(outer, thickness)


def gear_mesh_check(z1, z2, module, centre_distance, pressure_angle=20.0):
    """Two standard spur gears: ideal centre distance a = m (z1 + z2) / 2 and the contact ratio
    eps = (sqrt(ra1^2 - rb1^2) + sqrt(ra2^2 - rb2^2) - a sin(alpha)) / (pi m cos(alpha)); needs eps >= 1.2."""
    al = np.radians(pressure_angle)
    a0 = module * (z1 + z2) / 2
    r1, r2 = module * z1 / 2, module * z2 / 2
    ra1, ra2 = r1 + module, r2 + module
    rb1, rb2 = r1 * np.cos(al), r2 * np.cos(al)
    a = float(centre_distance)
    eps = (np.sqrt(ra1 ** 2 - rb1 ** 2) + np.sqrt(ra2 ** 2 - rb2 ** 2) - a * np.sin(al)) / (np.pi * module * np.cos(al))
    return {"ideal_centre_distance_mm": round(a0, 3), "centre_distance_mm": round(a, 3),
            "error_mm": round(a - a0, 3), "contact_ratio": round(float(eps), 3),
            "ok": bool(abs(a - a0) <= 0.05 * module and eps >= 1.2)}


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


def profile(runs, cell=1.0, thickness=5.0, rows=0, cols=0):
    """A flat cut-out (e.g. a part traced from a drawing) extruded to `thickness`, centred.
    runs: [[row, col0, col1], ...] filled cells of a rows x cols grid (col1 exclusive), cell = mm per cell,
    row 0 at the top. Runs that repeat on the next row are merged into one block."""
    blocks = []                  # [row0, row1, c0, c1]
    open_ = {}
    for r, c0, c1 in sorted((int(a), int(b), int(c)) for a, b, c in runs):
        k = (c0, c1)
        if k in open_ and open_[k][1] == r:
            open_[k][1] = r + 1
        else:
            if k in open_:
                blocks.append(open_[k])
            open_[k] = [r, r + 1, c0, c1]
    blocks += list(open_.values())
    rows = rows or max((b[1] for b in blocks), default=1)
    cols = cols or max((b[3] for b in blocks), default=1)
    Vs, Fs = [], []
    for i, (r0, r1, c0, c1) in enumerate(blocks):
        V, F = box((c1 - c0) * cell, (r1 - r0) * cell, thickness)
        V[:, 0] += ((c0 + c1) / 2 - cols / 2) * cell
        V[:, 1] += (rows / 2 - (r0 + r1) / 2) * cell
        Vs.append(V)
        Fs.append(F + 8 * i)
    if not Vs:
        return box(cell, cell, thickness)
    return np.vstack(Vs), np.vstack(Fs)


def outline(polygons, thickness=5.0):
    """Closed solid of traced outlines (with real holes) extruded to `thickness`, centred on z = 0.
    polygons: [{"outer": [[x, y], ...], "holes": [[[x, y], ...], ...]}, ...] in mm (y up)."""
    from . import outline as ol
    Vs, Fs, off = [], [], 0
    for p in polygons:
        V, F = ol.extrude(p["outer"], p.get("holes") or [], thickness)
        Vs.append(V)
        Fs.append(F + off)
        off += len(V)
    if not Vs:
        return box(1, 1, thickness)
    return np.vstack(Vs), np.vstack(Fs)


BUILDERS = {"box": box, "profile": profile, "outline": outline, "cylinder": cylinder, "tube": tube, "cone": cone, "sphere": sphere,
            "torus": torus, "gear": gear, "nozzle": nozzle, "blade_ring": blade_ring,
            "pipe": pipe, "coil": coil}

PARAM_HELP = {
    "box": "w, d, h", "cylinder": "radius, height", "tube": "outer, inner, height",
    "cone": "r_bottom, r_top, height", "sphere": "radius", "torus": "radius, tube_radius",
    "gear": "teeth, module (mm; or radius = tip radius), thickness, bore, phase (deg)", "nozzle": "throat, exit, length, chamber, chamber_length",
    "blade_ring": "count, inner, outer, thickness, height, twist", "pipe": "points [[x,y,z],...], radius",
    "coil": "radius, wire, turns, pitch",
    "outline": "polygons [{outer: [[x,y],...], holes: [...]}], thickness",
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
    key = (part["type"], json.dumps(part.get("params", {}), sort_keys=True))
    if key not in _MESH:
        if len(_MESH) > 512:
            _MESH.clear()
        _MESH[key] = fn(**part.get("params", {}))
    V, F = _MESH[key]
    return V.copy(), F


_MESH = {}            # built meshes by (type, params): traced outlines and gears are costly to rebuild


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


def sample_surface(parts, n_points=4000, seed=0, xp=np):
    """Area-weighted random points on all visible parts. Returns points (N,3), normals (N,3), part index.
    xp=cupy draws the samples on the GPU (the triangle list is small; the samples are not)."""
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
    T, N, O, W = np.vstack(tris).astype(np.float32), np.vstack(norms).astype(np.float32), np.concatenate(owner), np.concatenate(weight)
    if xp is not np:
        T, N, O, W, rng = xp.asarray(T), xp.asarray(N), xp.asarray(O), xp.asarray(W), xp.random.default_rng(seed)
    c = xp.cumsum(W)                                    # area-weighted pick (searchsorted: ~10x faster than choice(p=))
    idx = xp.minimum(xp.searchsorted(c, rng.random(n_points) * c[-1], side="right"), len(T) - 1)
    u, v = rng.random(n_points, dtype=xp.float32), rng.random(n_points, dtype=xp.float32)
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
