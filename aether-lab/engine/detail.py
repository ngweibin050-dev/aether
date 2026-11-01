"""Modeller's finishing pass on parts rebuilt from a drawing: what a part IS decides its material and its depth.

A three-view hull only knows the outer silhouette, so every part sits flush on it. A modeller knows that an air
intake is a pocket, a window sits a little inside the body and is glass, a headlight is a lens under a cover. Once
a part has a name (Muse Spark reads the numbered drawing), this pass:

- gives it a material (paint, glass, dark trim, lens, tyre rubber...);
- pushes it into the body where that kind of part is recessed: the boundary stays on its neighbours (no holes, no
  gaps), the inside sinks smoothly to the depth, along the surface normal.

The depths are typical proportions for the kind of part (a guess from what the part is, not a measurement from the
drawing); the report says so.
"""
import numpy as np

# (kind, words that name it, depth as a fraction of the body length, depth cap as a fraction of the part's own size)
KINDS = [
    ("intake", ("intake", "vent", "duct", "scoop", "inlet", "outlet", "grille", "grill", "louver", "louvre",
                "diffuser", "exhaust", "radiator"), 0.022, 0.30),
    ("glass", ("window", "glass", "windscreen", "windshield", "screen", "quarter light", "backlight"), 0.004, 0.06),
    ("lamp", ("light", "lamp", "headlight", "taillight", "indicator", "drl"), 0.006, 0.12),
    ("trim", ("skirt", "sill", "splitter", "spoiler", "wing", "mirror", "pillar", "trim", "lip", "bumper insert",
              "wheel", "arch", "underbody", "floor"), 0.0, 0.0),
]
MATERIAL = {"intake": "#20262e", "glass": "#1d3448", "lamp": "#e9f3ff", "trim": "#3a4350"}
LAMP_REAR = "#d4384a"


def kind_of(name):
    n = (name or "").lower()
    for kind, words, _, _ in KINDS:
        if any(w in n for w in words):
            return kind
    return "paint"


def colour(kind, name, paint):
    if kind == "lamp" and any(w in (name or "").lower() for w in ("tail", "rear", "brake")):
        return LAMP_REAR
    return MATERIAL.get(kind, paint)


def _normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], n)
    return N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)


def _edge_distance(V, F, iters=200):
    """Distance along the surface from the part's open boundary (its seam with the neighbours), per vertex."""
    E = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), 1)
    u, cnt = np.unique(E, axis=0, return_counts=True)
    d = np.full(len(V), np.inf)
    d[np.unique(u[cnt == 1])] = 0
    if not np.isfinite(d).any():
        return np.full(len(V), np.inf)
    a, b = u[:, 0], u[:, 1]
    w = np.linalg.norm(V[a] - V[b], axis=1)
    for _ in range(iters):
        nd = d.copy()
        np.minimum.at(nd, a, d[b] + w)
        np.minimum.at(nd, b, d[a] + w)
        if np.array_equal(nd, d):
            break
        d = nd
    return d


def recess(V, F, kind, length_mm, body_centre=(0, 0, 0)):
    """Sink a part into the body by its kind's depth. Returns (V, depth_mm)."""
    spec = next((k for k in KINDS if k[0] == kind), None)
    if spec is None or spec[2] <= 0 or len(F) < 8:
        return V, 0.0
    size = np.ptp(V, 0)
    small = np.sort(size)[1]                                   # the part's width across its face
    depth = min(spec[2] * length_mm, spec[3] * small)
    if depth < 0.05:
        return V, 0.0
    N = _normals(V, F)
    if ((V - np.asarray(body_centre)) * N).sum() < 0:          # make the normals point out of the body
        N = -N
    d = _edge_distance(V, F)
    ramp = max(min(depth * 1.2, 0.3 * small), 1e-6)
    t = np.clip(np.where(np.isfinite(d), d, ramp) / ramp, 0, 1)
    prof = t * t * (3 - 2 * t)                                 # smoothstep: flush at the seam, full depth inside
    return V - N * (depth * prof)[:, None], round(float(depth), 2)
