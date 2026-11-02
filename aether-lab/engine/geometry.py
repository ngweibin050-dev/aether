"""Scene geometry helpers (mm): transforms, bounds and surface sampling over the triangles DERIVED from validated
OpenCascade B-rep (cad/ worker). Nothing here builds or modifies geometry: the authoritative model is the CAD
document in the worker; these triangles exist only for the viewport, cutaway, bounds, physics and optics.

Each part: {"id", "name", "type": "cad" | "group", "params": {...}, "position": [x,y,z], "rotation": [rx,ry,rz] (deg),
            "scale": [sx,sy,sz], "parent": id|None, "visible": bool, "brightness": 0..1}
`world_mesh` applies the transform chain.
"""
import numpy as np

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


PART_TYPES = ("group", "cad")


class NotCadGeometry(ValueError):
    """A scene part that is not a tessellation of a validated B-rep (or a group)."""


def local_mesh(part, cache=None):
    """The display / physics triangles of one part, in its local frame. Only two part types exist:
    "cad" = the tessellation of a validated OpenCascade B-rep produced by the CAD worker (cad/tessellate.py);
    "group" = no geometry. Anything else (the removed primitive / traced / imported mesh types) is refused."""
    if part["type"] == "cad":
        return np.asarray(part["params"]["vertices"], float).reshape(-1, 3), \
            np.asarray(part["params"]["faces"], int).reshape(-1, 3)
    if part["type"] == "group":
        return np.zeros((0, 3)), np.zeros((0, 3), int)
    raise NotCadGeometry(f"part type {part['type']!r} is not CAD geometry; only B-rep tessellations ('cad') and groups "
                         "exist in the scene")


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
