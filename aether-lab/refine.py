"""Refining an existing model: parts are placed ON the model by where they go, never by guessed coordinates.

A part spec may carry `attach`:
  {"side": "front" | "rear" | "left" | "right" | "top" | "bottom", "u": 0..1, "v": 0..1, "proud_mm": ..., "spin_deg": ...}
    u, v: where on that side, as fractions of the model's extent seen from that side
      front / rear: u = the model's left (0) -> right (1), v = bottom (0) -> top (1)
      left / right: u = rear (0) -> front (1),            v = bottom (0) -> top (1)
      top / bottom: u = rear (0) -> front (1),            v = left (0) -> right (1)
    A ray is cast from outside the model straight at that side; the part sits where it hits the real surface, with its
    local z along the surface normal (a box's h, a cylinder's height = its thickness out of the surface) and its local
    x along u. proud_mm: how far its outer face stands above the surface (default 60 % of its thickness; 0 = flush,
    negative = sunk in).
  {"side": "inside", "u": rear->front, "v": left->right, "w": bottom->top}: a point inside the model's box (cabin,
    engine bay); it is checked to really be inside the body.
The model's front is known (a CAD vehicle faces -x, see cad/vehicle.frames; other models face -y), so "rear lights"
can never land on the nose.

checks(): every part added in this turn is tested against the model: floating (not touching anything), sticking out
of the model's box, overlapping another new part, or duplicating something the model already has (a "window" box on
a body that has a glass region)."""
import numpy as np

from engine import geometry, lab, snap

SIDES = ("front", "rear", "left", "right", "top", "bottom")
# a part named like these duplicates a body region whose name contains the key (a "headlight" box over the body's
# "headlight" region); a body with ONE shared lamp region ("light", older models) has no region for a red tail light
# apart from yellow headlights, so a lamp part there is not a duplicate
DUPLICATE_WORDS = {"glass": ("window", "windshield", "windscreen", "glass"),
                   "head": ("headlight", "head light", "headlamp"),
                   "tail": ("taillight", "tail light", "rear light", "tail lamp")}


def model_mesh(state, model, exclude=()):
    """All triangles of the model in its own frame (mm): V, F, and the id of the part each triangle belongs to."""
    Vs, Fs, owner, n = [], [], [], 0
    for p, V, F, _ in snap.model_meshes(state, model):
        if p["id"] in exclude:
            continue
        Vs.append(V)
        Fs.append(F + n)
        owner += [p["id"]] * len(F)
        n += len(V)
    if not Vs:
        return np.zeros((0, 3)), np.zeros((0, 3), int), []
    return np.vstack(Vs), np.vstack(Fs), owner


def raycast(V, F, origin, direction):
    """Nearest hit of a ray on the triangles (Moller-Trumbore, vectorised): (t, point, unit normal facing the ray,
    triangle index) or None."""
    if not len(F):
        return None
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    o = np.asarray(origin, float)
    A, B, C = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    e1, e2 = B - A, C - A
    h = np.cross(d, e2)
    a = np.einsum("ij,ij->i", e1, h)
    ok = np.abs(a) > 1e-12
    f = np.zeros_like(a)
    f[ok] = 1.0 / a[ok]
    s = o - A
    u = f * np.einsum("ij,ij->i", s, h)
    q = np.cross(s, e1)
    v = f * (q @ d)
    t = f * np.einsum("ij,ij->i", e2, q)
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6)
    if not hit.any():
        return None
    i = np.flatnonzero(hit)[np.argmin(t[hit])]
    n = np.cross(e1[i], e2[i])
    n /= np.linalg.norm(n)
    if n @ d > 0:
        n = -n
    return float(t[i]), o + t[i] * d, n, int(i)


def side_frame(front):
    """Per side: outward normal, the u direction and the v direction (all unit vectors in the model frame)."""
    s = snap.sides(front)
    up = s["top"]
    return {"front": (s["front"], s["right"], up), "rear": (s["rear"], s["right"], up),
            "left": (s["left"], s["front"], up), "right": (s["right"], s["front"], up),
            "top": (up, s["front"], s["right"]), "bottom": (-up, s["front"], s["right"])}


def euler_zyx(R):
    """Degrees (rx, ry, rz) with R = Rz @ Ry @ Rx (geometry._rot, three.js order ZYX)."""
    ry = -np.arcsin(np.clip(R[2, 0], -1, 1))
    if abs(np.cos(ry)) > 1e-6:
        rx = np.arctan2(R[2, 1], R[2, 2])
        rz = np.arctan2(R[1, 0], R[0, 0])
    else:
        rx, rz = np.arctan2(-R[1, 2], R[1, 1]), 0.0
    return [float(np.degrees(rx)), float(np.degrees(ry)), float(np.degrees(rz))]


def _local_extent(spec):
    """The part's own mesh (no transform) -> (zmin, zmax) along its local z and its size."""
    p = {"type": spec["type"], "params": spec.get("params") or {}, "position": [0, 0, 0], "rotation": [0, 0, 0],
         "scale": spec.get("scale") or [1, 1, 1]}
    V, _ = geometry.local_mesh(p)
    if not len(V):
        return -0.5, 0.5, np.ones(3)
    V = V * np.asarray(p["scale"], float)
    return float(V[:, 2].min()), float(V[:, 2].max()), V.max(0) - V.min(0)


def place(state, model, spec, mesh=None):
    """position + rotation (model frame) for a spec with `attach`. Raises ValueError with a plain reason."""
    at = spec["attach"]
    side = str(at.get("side", "")).lower()
    V, F, _ = mesh if mesh is not None else model_mesh(state, model)
    if not len(V):
        raise ValueError("the model has no surface to attach to")
    lo, hi = V.min(0), V.max(0)
    front = snap.front_axis(model)
    fr = side_frame(front)
    u = float(np.clip(at.get("u", 0.5), 0, 1))
    v = float(np.clip(at.get("v", 0.5), 0, 1))
    if side == "inside":
        s = snap.sides(front)
        w = float(np.clip(at.get("w", 0.5), 0, 1))
        P = lo + (hi - lo) * 0.5
        for axis, frac in ((s["front"], u), (s["right"], v), (s["top"], w)):
            ax = np.abs(axis)
            # along this axis: frac 0 at the negative end of the named direction (rear / left / bottom), 1 at its end
            a0, a1 = (lo @ ax, hi @ ax) if axis @ ax > 0 else (hi @ ax, lo @ ax)
            P = P - (P @ ax) * ax + (a0 + (a1 - a0) * frac) * ax
        hits = sum(1 for dd in (np.array([0, 0, 1.0]), np.array([0, 0, -1.0])) if raycast(V, F, P, dd))
        R = _frame_rotation(np.array([0, 0, 1.0]), s["front"], float(at.get("spin_deg", 0)))
        rot = euler_zyx(R) if spec.get("rotation") is None else spec["rotation"]
        return [float(c) for c in P], rot, {"side": "inside", "enclosed": hits == 2}
    if side not in fr:
        raise ValueError(f"attach.side must be one of {SIDES + ('inside',)}")
    n, du, dv = fr[side]
    c = (lo + hi) / 2
    # the point on the side's projection: u across du, v across dv (fractions of the box seen from that side)
    P = c.copy()
    for d, frac in ((du, u), (dv, v)):
        ax = np.abs(d)
        a0, a1 = (lo @ ax, hi @ ax) if d @ ax > 0 else (hi @ ax, lo @ ax)
        P = P - (P @ ax) * ax + (a0 + (a1 - a0) * frac) * ax
    reach = float(np.linalg.norm(hi - lo)) + 100.0
    hit = raycast(V, F, P + n * reach, -n)
    if hit is None:
        raise ValueError(f"no surface of the model at {side} u={u:.2f} v={v:.2f} (the ray missed it): pick u / v nearer "
                         "the middle of that side")
    _, X, N, _ = hit
    zmin, zmax, _ = _local_extent(spec)
    thick = zmax - zmin
    proud = float(at["proud_mm"]) if at.get("proud_mm") is not None else 0.6 * thick
    pos = X + N * (proud - zmax)                          # outer face (local zmax) `proud` above the surface
    if spec["type"] == "exhaust_tip":                    # a tailpipe points straight out of that end, not along a sloped skin
        pos = X + np.asarray(n, float) * (proud - zmax)
        R = _frame_rotation(n, du, float(at.get("spin_deg", 0)))
    else:
        R = _frame_rotation(N, du, float(at.get("spin_deg", 0)))
    return [float(c) for c in pos], euler_zyx(R), {"side": side, "surface_point": [round(float(c), 1) for c in X],
                                                    "surface_normal": [round(float(c), 3) for c in N],
                                                    "proud_mm": round(proud, 2)}


def _frame_rotation(z, xref, spin_deg=0.0):
    z = np.asarray(z, float) / np.linalg.norm(z)
    x = np.asarray(xref, float) - (np.asarray(xref, float) @ z) * z
    if np.linalg.norm(x) < 1e-6:
        x = np.cross(z, [0, 1.0, 0]) if abs(z[1]) < 0.9 else np.cross(z, [1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    if spin_deg:
        a = np.radians(spin_deg)
        x, y = np.cos(a) * x + np.sin(a) * y, -np.sin(a) * x + np.cos(a) * y
    return np.stack([x, y, z], 1)


def checks(state, model, new_ids, inside=()):
    """Problems with the parts just added (model frame, mm): floating, outside, overlapping, duplicate. Parts placed
    inside the body (`inside`) are not expected to touch it."""
    from scipy.spatial import cKDTree
    new_ids = set(new_ids)
    if not new_ids:
        return []
    meshes = snap.model_meshes(state, model, include_hidden=True)
    old = [(p, V) for p, V, _, _ in meshes if p["id"] not in new_ids]
    new = [(p, V) for p, V, _, _ in meshes if p["id"] in new_ids]
    if not old or not new:
        return []
    OV = np.vstack([V for _, V in old])
    lo, hi = OV.min(0), OV.max(0)
    diag = float(np.linalg.norm(hi - lo))
    tree = cKDTree(OV[:: max(1, len(OV) // 60000)])
    regions = set()
    for p, _ in old:
        regions |= set(((p.get("params") or {}).get("region_names")) or [])
    issues = []
    boxes = []
    for p, V in new:
        plo, phi = V.min(0), V.max(0)
        boxes.append((p, plo, phi))
        size = float(np.linalg.norm(phi - plo))
        dmin = float(tree.query(V[:: max(1, len(V) // 400)])[0].min())
        if p["id"] not in inside and dmin > max(0.02 * diag, 0.6 * size, 2.0):
            issues.append({"part": p["name"], "problem": "floating", "detail": f"{dmin:.0f} mm from the model's surface"})
        out = np.maximum(lo - plo, 0) + np.maximum(phi - hi, 0)
        if float(out.max()) > 0.04 * diag:
            issues.append({"part": p["name"], "problem": "outside", "detail": f"sticks {out.max():.0f} mm out of the model's box"})
        nm = p["name"].lower()
        for reg, words in DUPLICATE_WORDS.items():
            if any(reg in r for r in regions) and any(w in nm for w in words):
                issues.append({"part": p["name"], "problem": "duplicate",
                               "detail": f"the body already has {sorted(r for r in regions if reg in r)} region(s) for this: colour them with modify(region=...) "
                                         "or add a cad_feature instead of a separate part"})
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            inter = np.prod(np.maximum(0, np.minimum(a[2], b[2]) - np.maximum(a[1], b[1])))
            va, vb = (np.prod(np.maximum(x[2] - x[1], 1e-6)) for x in (a, b))
            if inter > 0.5 * min(va, vb) and min(va, vb) > 0.3 * max(va, vb):
                issues.append({"part": a[0]["name"], "problem": "overlap", "detail": f"mostly inside '{b[0]['name']}'"})
    return issues


def look(state, model, views=("iso", "front", "rear", "left"), highlight=None, size=340, section=False):
    """A labelled multi-view image of the model (data URL) for Muse Spark to check its own work. True depth (no x-ray:
    a part inside the body stays hidden, as it really is); section=True adds a view cut open lengthwise down the middle,
    where parts placed inside can be judged."""
    from PIL import Image
    ms = snap.model_meshes(state, model)
    f = snap.front_axis(model)
    ims = [snap.render(ms, v, f, size, highlight, label=v.replace("_", " "), xray=False, dim=False) for v in views]
    if section and ms:
        V = np.vstack([Vm for _, Vm, _, _ in ms])
        ax = snap.sides(f)["left"]
        mid = float(((V.min(0) + V.max(0)) / 2) @ ax)
        lo, hi = V.min(0), V.max(0)
        roof = (np.array([0, 0, 1.0]), float(lo[2] + 0.55 * (hi[2] - lo[2])))
        ims.append(snap.render(ms, "top", f, size, highlight, label="roof cut away (inside, from above)", xray=False,
                               dim=False, clip=roof))
        ims.append(snap.render(ms, "left", f, size, highlight, label="left half cut away (inside, from the side)",
                               xray=False, dim=False, clip=(ax, mid)))
    cols = 2
    rows = (len(ims) + cols - 1) // cols
    out = Image.new("RGB", (cols * size, rows * size), snap.BG)
    for i, im in enumerate(ims):
        out.paste(im, ((i % cols) * size, (i // cols) * size))
    return snap.png_data_url(out, "JPEG")


# ------------------------------------------------------------------------------------------------ vehicles: where things go
# For a vehicle the AI names WHERE a part goes ("driver_seat") instead of guessing fractions of the bounding box (seats
# came out one behind the other, the engine against a door). The places are measured on the model itself: the cabin
# from its glass region (or between the axles), the floor and roof by rays, the wheels from its wheel parts.
SLOTS = ("driver_seat", "passenger_seat", "driver_belt", "passenger_belt", "dashboard", "steering_wheel",
         "rear_view_mirror", "engine_bay", "center_console")


def _count_hits(V, F, P, d):
    """How many triangles each ray P[i] + t d (t > 0) crosses (parity: inside a closed body = odd)."""
    d = np.asarray(d, float) / np.linalg.norm(d)
    A, B, C = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    e1, e2 = B - A, C - A
    h = np.cross(d, e2)
    a = np.einsum("ij,ij->i", e1, h)
    ok = np.abs(a) > 1e-12
    f = np.where(ok, 1.0 / np.where(ok, a, 1), 0)
    out = np.zeros(len(P), int)
    for i, o in enumerate(np.asarray(P, float)):
        s = o - A
        u = f * np.einsum("ij,ij->i", s, h)
        m = ok & (u >= 0) & (u <= 1)
        if not m.any():
            continue
        q = np.cross(s[m], e1[m])
        v = f[m] * (q @ d)
        t = f[m] * np.einsum("ij,ij->i", e2[m], q)
        out[i] = int(((v >= 0) & (u[m] + v <= 1) & (t > 1e-6)).sum())
    return out


def inside_share(V, F, pts):
    """Share of the points enclosed by the mesh (V, F). A point is inside when the body is around it: rays up, down,
    left and right (model y) hit it, at least three of the four. Not ray parity: a drawn body can have a gap (an open
    floor between the wheel wells), which flips parity but not enclosure."""
    pts = np.asarray(pts, float)
    if not len(pts):
        return 1.0
    T = V[F]
    tl, th = T.min(1), T.max(1)
    lo, hi = pts.min(0), pts.max(0)
    votes = np.zeros(len(pts), int)
    for d, a, b in (((0, 0, 1), 0, 1), ((0, 0, -1), 0, 1), ((0, 1, 0), 0, 2), ((0, -1, 0), 0, 2)):
        near = (th[:, a] >= lo[a]) & (tl[:, a] <= hi[a]) & (th[:, b] >= lo[b]) & (tl[:, b] <= hi[b])
        votes += _count_hits(V, F[near], pts, d) > 0
    return float((votes >= 3).mean())


def _is_wheel(p):
    k = ((p.get("eng") or {}).get("kind") or "") + " " + p.get("name", "").lower()
    return any(w in k for w in ("tyre", "tire", "wheel", "rim"))


def body_mesh(state, model):
    """The vehicle's body (the CAD body shell, else everything but wheels): V, F (model frame) and per-triangle
    region names."""
    ms = snap.model_meshes(state, model)
    body = [x for x in ms if (x[0].get("eng") or {}).get("kind") == "body_shell"]
    if not body:
        body = [x for x in ms if not _is_wheel(x[0])]
    Vs, Fs, R, n = [], [], [], 0
    for p, V, F, _ in body:
        Vs.append(V)
        Fs.append(F + n)
        n += len(V)
        names = (p.get("params") or {}).get("region_names") or []
        reg = (p.get("params") or {}).get("regions") or []
        R += [names[r - 1] if 0 < r <= len(names) else None for r in reg] if len(reg) == len(F) else [None] * len(F)
    if not Vs:
        return np.zeros((0, 3)), np.zeros((0, 3), int), []
    return np.vstack(Vs), np.vstack(Fs), R


def vehicle(state, model):
    """Measured places of a vehicle (model frame, mm), or None when the model is not one (no wheels)."""
    f = np.asarray(snap.front_axis(model), float)
    sd = snap.sides(f)
    left, up = np.asarray(sd["left"], float), np.array([0, 0, 1.0])
    ms = snap.model_meshes(state, model)
    wheels = [V for p, V, _, _ in ms if _is_wheel(p)]
    V, F, R = body_mesh(state, model)
    if len(wheels) < 2 or not len(F):
        return None
    lo, hi = V.min(0), V.max(0)
    sv = V @ f
    s0, s1 = float(sv.min()), float(sv.max())
    k = float(np.clip((s1 - s0) / 4500.0, 0.01, 4.0))    # the fixed mm below are for a 4.5 m car: scaled to this one
    wc = np.array([(W.min(0) + W.max(0)) / 2 for W in wheels])
    rw = float(np.median([(W.max(0) - W.min(0))[2] / 2 for W in wheels]))
    s_fa, s_ra = float((wc @ f).max()), float((wc @ f).min())
    glass = [i for i, r in enumerate(R) if r and "glass" in r]
    if glass:
        G = V[F[glass]].reshape(-1, 3)
        g0, g1 = float((G @ f).min()), float((G @ f).max())
        belt = float(G[:, 2].min())
    else:
        g0, g1 = s_ra + 0.3 * (s_fa - s_ra), s_ra + 0.8 * (s_fa - s_ra)
        belt = lo[2] + 0.55 * (hi[2] - lo[2])
    Lc = g1 - g0
    mid = (lo + hi) / 2
    centre = lambda s: mid + f * (s - float(mid @ f))
    reach = float(np.linalg.norm(hi - lo)) + 100

    def ray_z(s, from_top):
        P = centre(s).copy()
        P[2] = hi[2] + 50 * k if from_top else lo[2] - 50 * k
        h = raycast(V, F, P, (0, 0, -1) if from_top else (0, 0, 1))
        return None if h is None else float(h[1][2])
    sm = g0 + 0.45 * Lc
    # the floor: rays up from under the cabin at a few places; a hit above the beltline went through a gap in the
    # floor (a drawn body can be open underneath) and is not the floor
    fl = []
    for ss in (g0 + 0.3 * Lc, sm, g0 + 0.6 * Lc):
        for off in (-0.3, 0.0, 0.3):
            P = centre(ss) + left * off * float((hi - lo) @ np.abs(left))
            P[2] = lo[2] - 50 * k
            h = raycast(V, F, P, (0, 0, 1))
            if h is not None and h[1][2] < belt:
                fl.append(float(h[1][2]))
    floor = (float(np.median(fl)) if fl else lo[2] + 0.6 * rw) + 40 * k
    roof = ray_z(sm, True)
    roof = (roof if roof is not None else hi[2]) - 50 * k
    Pm = centre(sm)
    Pm[2] = floor + 0.35 * (roof - floor)
    h = raycast(V, F, Pm + left * reach, -left)
    half = (abs(float((h[1] - Pm) @ left)) if h else 0.45 * float((hi - lo) @ np.abs(left))) - 60 * k
    mid_engine = (g0 - s0) > (s1 - g1)
    bay = (s0 + 0.1 * (s1 - s0), g0 - 60 * k) if mid_engine else (g1 + 60 * k, s1 - 0.1 * (s1 - s0))
    deck = ray_z((bay[0] + bay[1]) / 2, True)
    return {"front": f, "left": left, "up": up, "centre": centre, "cabin": (g0, g1), "floor": floor, "roof": roof,
            "belt": belt, "half_width": half, "mid_engine": bool(mid_engine), "bay": bay,
            "deck": (deck if deck is not None else belt) - 50 * k, "wheel_radius": rw, "k": k, "axles": (s_ra, s_fa), "V": V, "F": F}


def _height(kind, prm):
    V, _ = geometry.local_mesh({"type": kind, "params": prm})
    return float(V[:, 2].max() - V[:, 2].min()) if len(V) else 100.0


def slot(state, model, name, spec, veh=None):
    """position, rotation matrix, params (sized to the car where the AI gave none) and info for attach {"slot": name}.
    Left-hand drive: the driver sits on the model's left."""
    veh = veh or vehicle(state, model)
    if veh is None:
        raise ValueError("slots are for vehicles (a model with wheels): use attach side 'inside' with u / v / w")
    f, left, up = veh["front"], veh["left"], veh["up"]
    g0, g1 = veh["cabin"]
    Lc = g1 - g0
    fl, rf, half = veh["floor"], veh["roof"], veh["half_width"]
    Hc = rf - fl
    k = veh.get("k", 1.0)                                  # sizes below are for a 4.5 m car, scaled to this one
    seat_w = float(np.clip(0.8 * half, 380 * k, 560 * k))
    seat_d = float(np.clip(0.3 * Lc, 420 * k, 600 * k))
    seat_h = float(np.clip(0.92 * Hc, 450 * k, 1000 * k))
    side = 1.0 if name.startswith("driver") else -1.0
    y = side * 0.52 * half
    s_seat, s_dash = g0 + 0.40 * Lc, g0 + 0.78 * Lc
    upright = _frame_rotation(up, f)                         # local x = the car's front, z = up
    kind = spec["type"]
    prm = dict(spec.get("params") or {})
    if name in ("driver_seat", "passenger_seat"):
        if kind == "seat":
            prm = {"width": seat_w, "depth": seat_d, "height": seat_h, **prm}
        P = veh["centre"](s_seat) + left * y
        P[2] = fl + _height(kind, prm) / 2
        return P, upright, prm, {"slot": name}
    if name in ("driver_belt", "passenger_belt"):
        # diagonally across the front of that seat's backrest: outer shoulder to inner hip
        a = veh["centre"](s_seat - 0.22 * seat_d) + left * (y + side * 0.36 * seat_w)
        a[2] = fl + 0.8 * seat_h
        b = veh["centre"](s_seat - 0.1 * seat_d) + left * (y - side * 0.32 * seat_w)
        b[2] = fl + 0.3 * seat_h
        x = (a - b) / np.linalg.norm(a - b)
        if kind == "seat_belt":
            prm = {"length": float(np.linalg.norm(a - b)), "width": 48 * k, "thickness": 4 * k, **prm}
        z = f - (f @ x) * x                                  # the strap's flat face towards the car's front
        R = _frame_rotation(z / np.linalg.norm(z), x)
        return (a + b) / 2 + f * 0.12 * seat_d, R, prm, {"slot": name}
    if name == "dashboard":
        if kind == "dashboard":
            prm = {"width": float(np.clip(1.85 * half, 900 * k, 1700 * k)), "depth": float(np.clip(0.2 * Lc, 300 * k, 520 * k)),
                   "height": float(np.clip(0.3 * Hc, 220 * k, 360 * k)), **prm}
        P = veh["centre"](s_dash)
        P[2] = fl + 0.5 * Hc
        return P, upright, prm, {"slot": name}
    if name == "steering_wheel":
        if kind == "steering_wheel":
            prm = {"diameter": float(np.clip(0.72 * seat_w, 330 * k, 380 * k)), "grip": 30 * k, **prm}
        axis = -f + 0.5 * up
        P = veh["centre"](s_dash - 0.14 * Lc) + left * (0.52 * half)
        P[2] = fl + 0.6 * Hc
        return P, _frame_rotation(axis / np.linalg.norm(axis), up), prm, {"slot": name}
    if name == "rear_view_mirror":
        if kind == "interior_mirror":
            prm = {"width": 240 * k, "height": 65 * k, "depth": 40 * k, **prm}
        P = veh["centre"](g0 + 0.66 * Lc)
        P[2] = rf - 90 * k
        return P, upright, prm, {"slot": name}
    if name == "center_console":
        P = veh["centre"](s_seat + 0.15 * Lc)
        P[2] = fl + 0.18 * Hc
        return P, upright, prm, {"slot": name}
    if name == "engine_bay":
        b0, b1 = veh["bay"]
        L = abs(b1 - b0)
        if kind == "engine":
            prm = {"length": float(np.clip(0.7 * L, 400 * k, 900 * k)), "width": float(np.clip(1.1 * half, 450 * k, 800 * k)),
                   "height": float(np.clip(0.75 * (veh["deck"] - fl), 300 * k, 650 * k)), **prm}
        P = veh["centre"]((b0 + b1) / 2)
        P[2] = fl + _height(kind, prm) / 2 + 30 * k
        return P, upright, prm, {"slot": name, "engine": "behind the cabin (mid-engine)" if veh["mid_engine"]
                                 else "in front of the cabin"}
    raise ValueError(f"unknown slot '{name}': one of {SLOTS}")


def slot_for(name, kind=None):
    """The slot a vehicle interior part's name means (None: no slot): 'driver seat' -> driver_seat; a passenger part
    by 'passenger' / 'right' (left-hand drive: the driver sits on the left)."""
    nm = f"{name} {kind or ''}".lower().replace("_", " ")
    pas = any(w in nm for w in ("passenger", "right"))
    if "belt" in nm:
        return "passenger_belt" if pas else "driver_belt"
    if "seat" in nm:
        return "passenger_seat" if pas else "driver_seat"
    if "steering" in nm:
        return "steering_wheel"
    if "dash" in nm:
        return "dashboard"
    if "mirror" in nm and any(w in nm for w in ("interior", "rear view", "rear-view", "rearview", "inside")):
        return "rear_view_mirror"
    if "engine" in nm or "motor" in nm:
        return "engine_bay"
    if "console" in nm:
        return "center_console"
    return None


def fit_inside(state, model, part, veh=None, tries=6):
    """An inside part that pokes through the body (an engine against a door showed outside) is shrunk about its
    centre until it is inside. Returns (share of it inside, scale factor applied)."""
    V, F = (veh["V"], veh["F"]) if veh else body_mesh(state, model)[:2]
    k, share = 1.0, 1.0
    for _ in range(tries):
        Vp = next((Vm for p, Vm, _, _ in snap.model_meshes(state, model) if p["id"] == part["id"]), None)
        if Vp is None:
            break
        share = inside_share(V, F, Vp[:: max(1, len(Vp) // 90)])
        if share >= 0.97:
            break
        part["scale"] = [float(c) * 0.85 for c in part.get("scale", [1, 1, 1])]
        k *= 0.85
    return share, k


# ------------------------------------------------------------------------------------------------ surface details
# A lamp, window, plate or grille is part of the body's SURFACE: on a CAD body it is a region (recolour) or a CAD
# feature. Where neither is possible it is a panel that follows the body's curvature exactly (rays onto the real
# surface), never a flat block standing on a curved bonnet.
SURFACE_WORDS = ("light", "lamp", "window", "windshield", "windscreen", "glass", "grille", "grill", "plate", "intake",
                 "vent", "badge", "logo", "stripe", "door line", "panel line", "decal")


def is_surface_detail(name):
    nm = name.lower()
    return any(w in nm for w in SURFACE_WORDS) and not any(w in nm for w in ("mirror", "interior", "dash", "inside"))


def surface_patch(state, model, side, u, v, width, height, shape="rect", proud=2.0, bulge=0.0, mesh=None, n=18):
    """A panel on the model's surface: the outline (centre u, v on that side as attach; width x height mm) is cast
    onto the real surface on an n x n grid; the outer face stands `proud` mm above it (+ `bulge` mm domed in the
    middle: a lamp lens), the inner face 1 mm inside. Returns V, F in the model frame (a closed mesh)."""
    V, F, _ = mesh if mesh is not None else model_mesh(state, model)
    lo, hi = V.min(0), V.max(0)
    fr = side_frame(snap.front_axis(model))
    if side not in fr:
        raise ValueError(f"surface details go on one of {SIDES}")
    nrm, du, dv = (np.asarray(x, float) for x in fr[side])
    P = (lo + hi) / 2
    for d, frac in ((du, u), (dv, v)):
        ax = np.abs(d)
        a0, a1 = (lo @ ax, hi @ ax) if d @ ax > 0 else (hi @ ax, lo @ ax)
        P = P - (P @ ax) * ax + (a0 + (a1 - a0) * float(np.clip(frac, 0, 1))) * ax
    a = np.linspace(-1, 1, n)
    A, B = np.meshgrid(a, a, indexing="ij")
    if shape == "ellipse":                                   # square grid -> disc, the boundary on the ellipse
        A, B = A * np.sqrt(1 - B ** 2 / 2), B * np.sqrt(1 - A ** 2 / 2)
    Q = P[None, None, :] + A[..., None] * (width / 2) * du + B[..., None] * (height / 2) * dv
    reach = float(np.linalg.norm(hi - lo)) + 100
    T = V[F]                                                 # only triangles under the outline can be hit
    tu, tv = T @ du, T @ dv
    pu, pv = Q.reshape(-1, 3) @ du, Q.reshape(-1, 3) @ dv
    near = (tu.max(1) >= pu.min()) & (tu.min(1) <= pu.max()) & (tv.max(1) >= pv.min()) & (tv.min(1) <= pv.max())
    Fn = F[near]
    X, N = np.zeros(Q.shape), np.zeros(Q.shape)
    for i in range(n):
        for j in range(n):
            h = raycast(V, Fn, Q[i, j] + nrm * reach, -nrm)
            if h is None:
                raise ValueError(f"the outline at {side} u={u:.2f} v={v:.2f} ({width:.0f} x {height:.0f} mm) runs off the "
                                 "model's surface: make it smaller or move it towards the middle of that side")
            X[i, j], N[i, j] = h[1], h[2]
    r2 = np.clip(A ** 2 + B ** 2, 0, 1)
    out = X + N * (proud + bulge * (1 - r2))[..., None]
    inn = X - N * 1.0
    idx = np.arange(n * n).reshape(n, n)
    q = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], -1).reshape(-1, 4)
    top = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
    t = np.vstack([out.reshape(-1, 3), inn.reshape(-1, 3)])[top]
    if np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]).sum(0) @ nrm < 0:
        top = top[:, ::-1]                                   # the outer face faces away from the body
    Ft = [top, top[:, ::-1] + n * n]
    ring = np.concatenate([idx[:, 0], idx[-1, 1:], idx[::-1, -1][1:], idx[0, ::-1][1:-1]])
    rim = []
    for k in range(len(ring)):                               # the rim: outer edge to inner edge
        a_, b_ = ring[k], ring[(k + 1) % len(ring)]
        rim += [[a_, b_ + n * n, b_], [a_, a_ + n * n, b_ + n * n]]
    rim = np.asarray(rim)
    c = np.vstack([out.reshape(-1, 3), inn.reshape(-1, 3)])
    mid = c.mean(0)
    tri = c[rim]
    nr = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    if (np.einsum("ij,ij->i", nr, tri.mean(1) - mid) < 0).mean() > 0.5:
        rim = rim[:, ::-1]
    return c, np.vstack(Ft + [rim])
