"""Detail parts that look like what they are, for refining a model: a seat has a cushion, a raked backrest, bolsters and
a headrest; a steering wheel a rim, spokes, hub and column; edges are rounded. A plain box added to a smooth CAD
body reads as a toy block stuck on it; these match the body's finish. All in mm, one mesh each (one colour).

Local frames (what attach / slots rely on): seat, dashboard, engine, interior_mirror: x = the direction the car
faces, y = left, z = up, origin at the centre of the bounding box. steering_wheel: z = the wheel's axis (towards the
driver), x = up the wheel. rbox / exhaust_tip / handle / plate on a surface: z = out of the surface.
"""
import numpy as np


def _rot(axis, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _merge(items):
    Vs, Fs, n = [], [], 0
    for V, F in items:
        Vs.append(np.asarray(V, float))
        Fs.append(np.asarray(F, int) + n)
        n += len(V)
    V = np.vstack(Vs)
    V -= (V.min(0) + V.max(0)) / 2                       # origin at the centre of the bounding box
    return V, np.vstack(Fs)


def _at(mesh, pos=(0, 0, 0), R=None):
    V, F = mesh
    if R is not None:
        V = V @ np.asarray(R).T
    return V + np.asarray(pos, float), F


def rbox(w=10, d=10, h=10, r=None, k=4):
    """A box with rounded edges and corners (radius r, default 18 % of the smallest side): flat faces, round rims."""
    H = np.array([w, d, h], float) / 2
    r = float(min(r if r is not None else 0.18 * 2 * H.min(), 0.98 * H.min()))
    core = H - r
    th = np.radians(np.linspace(0, 45, k + 1)[1:])

    def axis(i):
        z = core[i] + r * np.tan(th)
        return np.concatenate([-z[::-1], [-core[i], core[i]] if core[i] > 1e-9 else [0.0], z])
    ax = [axis(i) for i in range(3)]
    pts, quads = [], []
    for i in range(3):                                   # the six faces: axis i fixed at -H / +H
        j, l = [a for a in range(3) if a != i]
        A, B = np.meshgrid(ax[j], ax[l], indexing="ij")
        for sgn in (-1, 1):
            P = np.zeros(A.shape + (3,))
            P[..., i] = sgn * H[i]
            P[..., j], P[..., l] = A, B
            base = sum(len(p) for p in pts)
            pts.append(P.reshape(-1, 3))
            nj, nl = A.shape
            idx = base + np.arange(nj * nl).reshape(nj, nl)
            q = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], -1).reshape(-1, 4)
            if ((j, l, i) in ((0, 1, 2), (1, 2, 0), (2, 0, 1))) != (sgn > 0):
                q = q[:, ::-1]
            quads.append(q)
    P = np.vstack(pts)
    Q = np.vstack(quads)
    C = np.clip(P, -core, core)
    D = P - C
    n = np.linalg.norm(D, axis=1, keepdims=True)
    V = C + r * D / np.maximum(n, 1e-12)
    uniq, inv = np.unique(np.round(V, 6), axis=0, return_inverse=True)
    Q = inv.ravel()[Q]
    F = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    return uniq, F


def seat(width=500, depth=540, height=900, recline_deg=16):
    """A car seat facing +x: pedestal, cushion with side bolsters, raked backrest with bolsters, headrest."""
    W, D, H = float(width), float(depth), float(height)
    back_R = _rot("y", -recline_deg)
    bx = -0.36 * D
    out = [
        _at(rbox(0.55 * D, 0.62 * W, 0.12 * H, 0.02 * H), (0.02 * D, 0, 0.06 * H)),                          # pedestal
        _at(rbox(0.86 * D, 0.92 * W, 0.15 * H, 0.06 * H), (0.04 * D, 0, 0.19 * H), _rot("y", -5)),         # cushion
        _at(rbox(0.74 * D, 0.13 * W, 0.11 * H, 0.05 * H), (0.06 * D, 0.43 * W, 0.27 * H), _rot("y", -5)),  # bolsters
        _at(rbox(0.74 * D, 0.13 * W, 0.11 * H, 0.05 * H), (0.06 * D, -0.43 * W, 0.27 * H), _rot("y", -5)),
        _at(rbox(0.17 * D, 0.92 * W, 0.56 * H, 0.06 * H), (bx, 0, 0.55 * H), back_R),                         # backrest
        _at(rbox(0.22 * D, 0.13 * W, 0.5 * H, 0.06 * H), (bx + 0.05 * D, 0.43 * W, 0.53 * H), back_R),       # bolsters
        _at(rbox(0.22 * D, 0.13 * W, 0.5 * H, 0.06 * H), (bx + 0.05 * D, -0.43 * W, 0.53 * H), back_R),
        _at(rbox(0.14 * D, 0.52 * W, 0.15 * H, 0.06 * H), (bx - 0.12 * D, 0, 0.93 * H), back_R),            # headrest
    ]
    return _merge(out)


def seat_belt(length=650, width=48, thickness=4):
    """A seat belt strap with its buckle tongue: flat, slightly rounded (lies across the seat diagonally)."""
    L, W, t = float(length), float(width), float(thickness)
    return _merge([_at(rbox(L, W, t, t * 0.45)), _at(rbox(0.09 * L, 1.2 * W, 3 * t, t), (-0.5 * L, 0, 0))])


def torus_(R, r, seg=48, sides=14):
    u = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    v = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    U, Vv = np.meshgrid(u, v, indexing="ij")
    P = np.stack([(R + r * np.cos(Vv)) * np.cos(U), (R + r * np.cos(Vv)) * np.sin(U), r * np.sin(Vv)], -1).reshape(-1, 3)
    i = np.arange(seg)[:, None] * sides + np.arange(sides)[None, :]
    i2 = ((np.arange(seg)[:, None] + 1) % seg) * sides + np.arange(sides)[None, :]
    i3 = ((np.arange(seg)[:, None] + 1) % seg) * sides + (np.arange(sides)[None, :] + 1) % sides
    i4 = np.arange(seg)[:, None] * sides + (np.arange(sides)[None, :] + 1) % sides
    F = np.concatenate([np.stack([i, i2, i3], -1).reshape(-1, 3), np.stack([i, i3, i4], -1).reshape(-1, 3)])
    return P, F


def _cyl(r, h, seg=32):
    t = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    ring = np.c_[r * np.cos(t), r * np.sin(t)]
    V = np.vstack([np.c_[ring, np.full(seg, -h / 2)], np.c_[ring, np.full(seg, h / 2)], [[0, 0, -h / 2], [0, 0, h / 2]]])
    j = np.arange(seg)
    k = (j + 1) % seg
    F = np.concatenate([np.c_[j, k, seg + k], np.c_[j, seg + k, seg + j],
                        np.c_[np.full(seg, 2 * seg), k, j], np.c_[np.full(seg, 2 * seg + 1), seg + j, seg + k]])
    return V, F


def steering_wheel(diameter=370, grip=30):
    """Rim, three spokes, hub with an airbag cover and the column behind it. z = the wheel's axis (towards the driver)."""
    R, g = float(diameter) / 2 - float(grip) / 2, float(grip) / 2
    out = [torus_(R, g), _at(_cyl(0.3 * R, 0.28 * R), (0, 0, 0.04 * R))]
    for a in (90, 210, 330):                                   # spokes: hub to rim, in the wheel's plane
        out.append(_at(rbox(0.75 * R, 0.16 * R, 0.07 * R, 0.03 * R), (0.62 * R * np.cos(np.radians(a)), 0.62 * R * np.sin(np.radians(a)), 0),
                       _rot("z", a)))
    out.append(_at(_cyl(0.11 * R, 1.1 * R), (0, 0, -0.62 * R)))   # column
    return _merge(out)


def dashboard(width=1300, depth=420, height=300):
    """A dashboard across the cabin (x = the car's front; the occupants sit at -x): rounded top sloping down towards
    them, an instrument binnacle on the driver's side (left, +y) and a centre stack."""
    W, D, H = float(width), float(depth), float(height)
    out = [
        _at(rbox(D, W, 0.55 * H, 0.18 * H), (0, 0, 0.0)),
        _at(rbox(0.7 * D, 0.96 * W, 0.4 * H, 0.15 * H), (-0.12 * D, 0, 0.32 * H), _rot("y", 12)),
        _at(rbox(0.3 * D, 0.26 * W, 0.3 * H, 0.12 * H), (-0.3 * D, 0.25 * W, 0.48 * H), _rot("y", 20)),   # binnacle
        _at(rbox(0.5 * D, 0.16 * W, 0.9 * H, 0.08 * H), (-0.3 * D, 0, -0.25 * H)),                          # centre stack
    ]
    return _merge(out)


def engine(length=700, width=650, height=520):
    """A V engine seen as an engine: block and sump, two valve covers on the banks, intake plenum on top, front pulleys
    and belt. x = along the crankshaft."""
    L, W, H = float(length), float(width), float(height)
    out = [
        _at(rbox(0.9 * L, 0.5 * W, 0.45 * H, 0.05 * H), (0, 0, -0.18 * H)),                         # block
        _at(rbox(0.8 * L, 0.42 * W, 0.16 * H, 0.04 * H), (0, 0, -0.45 * H)),                        # sump
        _at(rbox(0.86 * L, 0.24 * W, 0.17 * H, 0.06 * H), (0, 0.32 * W, 0.15 * H), _rot("x", 32)),   # valve covers
        _at(rbox(0.86 * L, 0.24 * W, 0.17 * H, 0.06 * H), (0, -0.32 * W, 0.15 * H), _rot("x", -32)),
        _at(rbox(0.7 * L, 0.3 * W, 0.2 * H, 0.08 * H), (0, 0, 0.3 * H)),                             # intake plenum
    ]
    for y, z, r in ((0.0, -0.25 * H, 0.13 * H), (0.22 * W, 0.0, 0.08 * H), (-0.22 * W, 0.0, 0.08 * H)):
        out.append(_at(_cyl(r, 0.06 * L), (0.48 * L, y, z), _rot("y", 90)))                        # pulleys
    return _merge(out)


def exhaust_tip(diameter=90, length=160, wall=4):
    """A round tailpipe tip, hollow, with a rolled lip. z = along the pipe (out of the surface it comes through)."""
    r, L, t = float(diameter) / 2, float(length), float(wall)
    prof = [[r - t, -L / 2], [r - t, L / 2 - t], [r - t * 0.2, L / 2], [r + t * 0.6, L / 2 - t * 0.5], [r, L / 2 - 2 * t],
            [r, -L / 2], [r - t, -L / 2]]
    seg = 40
    tt = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    P = np.asarray(prof, float)
    m = len(P)
    V = np.stack([np.outer(P[:, 0], np.cos(tt)), np.outer(P[:, 0], np.sin(tt)), np.repeat(P[:, 1:2], seg, 1)], -1).reshape(-1, 3)
    F = []
    for i in range(m - 1):
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg
            F += [[a, b, b + seg], [a, b + seg, a + seg]]
    return V, np.asarray(F)


def interior_mirror(width=250, height=70, depth=40):
    """The rear-view mirror inside the windscreen: a rounded mirror body on a stem to the roof (stem up, +z)."""
    W, H, D = float(width), float(height), float(depth)
    return _merge([_at(rbox(D, W, H, 0.4 * H)), _at(_cyl(0.12 * H, 0.9 * H), (0.1 * D, 0, 0.9 * H))])


# ------------------------------------------------------------------------------------------------ standard parts
# Sizes from the standards, by designation (the AI says "M8 x 30", not a guessed shape):
# ISO 4017 hex bolt / ISO 4032 nut (s = across flats, k / m = head / nut height), ISO 7089 washer, ISO 15 / DIN 625
# deep-groove ball bearings of the 62 series (d x D x B).
ISO_METRIC = {  # M: (pitch, s across flats, k head height, m nut height, washer d1, d2, h)
    3: (0.5, 5.5, 2.0, 2.4, 3.2, 7, 0.5), 4: (0.7, 7, 2.8, 3.2, 4.3, 9, 0.8), 5: (0.8, 8, 3.5, 4.7, 5.3, 10, 1.0),
    6: (1.0, 10, 4.0, 5.2, 6.4, 12, 1.6), 8: (1.25, 13, 5.3, 6.8, 8.4, 16, 1.6), 10: (1.5, 16, 6.4, 8.4, 10.5, 20, 2.0),
    12: (1.75, 18, 7.5, 10.8, 13, 24, 2.5), 16: (2.0, 24, 10, 14.8, 17, 30, 3.0), 20: (2.5, 30, 12.5, 18, 21, 37, 3.0),
    24: (3.0, 36, 15, 21.5, 25, 44, 4.0)}
BEARING_62 = {"6200": (10, 30, 9), "6201": (12, 32, 10), "6202": (15, 35, 11), "6203": (17, 40, 12), "6204": (20, 47, 14),
              "6205": (25, 52, 15), "6206": (30, 62, 16), "6207": (35, 72, 17), "6208": (40, 80, 18), "6210": (50, 90, 20)}


def _metric(size):
    m = int(round(float(str(size).upper().lstrip("M") or 8)))
    if m not in ISO_METRIC:
        raise ValueError(f"metric size M{m} not in the table: one of {['M%d' % k for k in ISO_METRIC]}")
    return m, ISO_METRIC[m]


def _hex_prism(s, h, seg_chamfer=True):
    """A hexagon s across flats, h high (z from 0 to h), as a 6-sided lathe would not do: real flats."""
    r = s / np.sqrt(3)
    t = np.radians(np.arange(6) * 60 + 30)
    ring = np.c_[r * np.cos(t), r * np.sin(t)]
    V = np.vstack([np.c_[ring, np.zeros(6)], np.c_[ring, np.full(6, h)], [[0, 0, 0], [0, 0, h]]])
    j = np.arange(6)
    k = (j + 1) % 6
    F = np.concatenate([np.c_[j, k, 6 + k], np.c_[j, 6 + k, 6 + j], np.c_[np.full(6, 12), k, j], np.c_[np.full(6, 13), 6 + j, 6 + k]])
    return V, F


def _threaded(d, L, pitch, seg=28):
    """A shank of diameter d, length L along -z from 0, with the thread shown as grooves one pitch apart."""
    z = [0.0]
    while z[-1] - pitch > -L:
        z += [z[-1] - 0.5 * pitch, z[-1] - pitch]
    z.append(-L)
    prof = [[d / 2 if i % 2 == 0 else d / 2 - 0.3 * pitch, zz] for i, zz in enumerate(z)]
    prof[-1][0] = d / 2 - 0.4 * pitch                         # chamfered end
    return _lathe_closed(prof[::-1], seg)


def _lathe_closed(prof, seg=28):
    P = np.asarray(prof, float)
    m = len(P)
    t = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    V = np.stack([np.outer(P[:, 0], np.cos(t)), np.outer(P[:, 0], np.sin(t)), np.repeat(P[:, 1:2], seg, 1)], -1).reshape(-1, 3)
    F = []
    for i in range(m - 1):
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg
            F += [[a, b, b + seg], [a, b + seg, a + seg]]
    V = np.vstack([V, [[0, 0, P[0, 1]], [0, 0, P[-1, 1]]]])
    c0, c1 = len(V) - 2, len(V) - 1
    F += [[c0, (j + 1) % seg, j] for j in range(seg)] + [[c1, (m - 1) * seg + j, (m - 1) * seg + (j + 1) % seg] for j in range(seg)]
    return V, np.asarray(F)


def hex_bolt(size="M8", length=30):
    """ISO 4017 hex head bolt (fully threaded), by designation: M8 x 30. z = its axis, the head on top."""
    m, (pitch, s, k, *_r) = _metric(size)
    return _merge([_hex_prism(s, k), _threaded(m, float(length), pitch)])


def hex_nut(size="M8"):
    """ISO 4032 hex nut with its bore."""
    m, (pitch, s, k, mh, *_r) = _metric(size)
    r = s / np.sqrt(3)
    t = np.radians(np.arange(6) * 60 + 30)
    seg = 24
    th = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    # outer hexagon resampled to the bore's segment count, so the faces pair up
    ang = (th - np.radians(30)) % np.radians(60) - np.radians(30)
    rr = (s / 2) / np.cos(ang)
    outer = np.c_[rr * np.cos(th), rr * np.sin(th)]
    inner = np.c_[m / 2 * np.cos(th), m / 2 * np.sin(th)]
    from engine.geometry import _extrude
    return _merge([_extrude(outer, mh, holes=[inner])])


def washer(size="M8"):
    """ISO 7089 plain washer."""
    m, (*_a, d1, d2, h) = _metric(size)
    from engine.geometry import tube
    return _merge([tube(outer=d2 / 2, inner=d1 / 2, height=h)])


def ball_bearing(designation="6204"):
    """Deep-groove ball bearing of the 62 series (ISO 15): inner and outer rings and the two shields that cover the balls."""
    if str(designation) not in BEARING_62:
        raise ValueError(f"bearing {designation} not in the table: one of {sorted(BEARING_62)}")
    d, D, B = BEARING_62[str(designation)]
    from engine.geometry import tube
    t = (D - d) / 2
    out = [tube(outer=D / 2, inner=D / 2 - 0.28 * t, height=B), tube(outer=d / 2 + 0.28 * t, inner=d / 2, height=B),
           tube(outer=D / 2 - 0.3 * t, inner=d / 2 + 0.3 * t, height=0.12 * B)]
    out = [_at(out[0]), _at(out[1]), _at(out[2], (0, 0, 0.42 * B)), _at(out[2], (0, 0, -0.42 * B))]
    return _merge(out)


BUILDERS = {"hex_bolt": hex_bolt, "hex_nut": hex_nut, "washer": washer, "ball_bearing": ball_bearing,
            "rbox": rbox, "seat": seat, "seat_belt": seat_belt, "steering_wheel": steering_wheel, "dashboard": dashboard,
            "engine": engine, "exhaust_tip": exhaust_tip, "interior_mirror": interior_mirror}

PARAM_HELP = {
    "hex_bolt": "size ('M3'..'M24'), length mm: ISO 4017 hex bolt, sized from the standard",
    "hex_nut": "size ('M3'..'M24'): ISO 4032 hex nut", "washer": "size ('M3'..'M24'): ISO 7089 washer",
    "ball_bearing": "designation ('6200'..'6210'): 62-series deep-groove ball bearing (d x D x B from ISO 15)",
    "rbox": "w, d, h, r (edge radius): a box with rounded edges - use it instead of box for any panel, plate, handle, trim",
    "seat": "width, depth, height, recline_deg: a car / chair seat (cushion, bolsters, raked back, headrest), facing +x",
    "seat_belt": "length, width, thickness: a belt strap with its tongue",
    "steering_wheel": "diameter, grip: rim, spokes, hub, column (axis z)",
    "dashboard": "width, depth, height: dashboard with binnacle and centre stack",
    "engine": "length, width, height: V engine (block, valve covers, plenum, pulleys)",
    "exhaust_tip": "diameter, length, wall: hollow tailpipe tip (axis z)",
    "interior_mirror": "width, height, depth: rear-view mirror on its stem",
}
