"""Drawing interpretation, stage 1: a multi-view sheet -> measured observations (no geometry is built here).

Everything returned is measured on the ink of the sheet, in sheet pixels, together with the model-frame transform
of its view. Nothing here decides what a component IS (that is the AI stages + the planner) and nothing here builds
a solid. Visual-hull carving is not used: the filled silhouettes below are evidence for curves and for the
reprojection check, never a body.

Model frame (mm): X along the object from its front end (nose) towards the rear, Y lateral (Y = 0 = symmetry plane,
+Y = the side the side view shows; it does not matter for a symmetric object), Z up from the ground line.

Per view the transform is affine and axis-aligned (orthographic sheet):
  side:  x = s_side * (u - u0) * dir,  z = s_side * (v_ground - v)
  top:   x = s_top  * (u - u0) * dir,  y = s_top  * (v_c - v)
  front/rear: y = s_end * (u - u_c) * (+1 front / -1 rear),  z = s_end * (v_ground - v)
The scales are fitted from shared quantities (length side <-> top, height side <-> end views); residuals are kept.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from engine import circles as _circles
from engine import outline as _outline

INK_LEVEL = None          # None: Otsu


# ----------------------------------------------------------------------------------------------- image helpers
def load(path):
    raw = open(path, "rb").read()
    im = Image.open(path)
    if im.mode in ("P", "LA", "RGBA"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    g = np.asarray(im.convert("L"), float)
    return g, {"file": str(path).split("/")[-1], "sha256": hashlib.sha256(raw).hexdigest(), "size_px": [g.shape[1], g.shape[0]]}


def otsu(g):
    hist = np.bincount(np.clip(g, 0, 255).astype(int).ravel(), minlength=256).astype(float)
    p = hist / hist.sum()
    w, mu = np.cumsum(p), np.cumsum(p * np.arange(256))
    return int(np.argmax((mu[-1] * w - mu) ** 2 / np.maximum(w * (1 - w), 1e-12)))


def ink_of(g):
    return g <= (INK_LEVEL or otsu(g))


def _long_rows(ink, frac):
    """Rows holding a straight horizontal run >= frac of the image width (ground lines)."""
    out = []
    W = ink.shape[1]
    for y in range(ink.shape[0]):
        r = ink[y]
        if r.sum() < frac * W:
            continue
        d = np.diff(np.r_[0, r.astype(int), 0])
        a, b = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        if len(a) and (b - a).max() >= frac * W:
            i = int(np.argmax(b - a))
            out.append((y, int(a[i]), int(b[i])))
    return out


# ----------------------------------------------------------------------------------------------- views
def find_views(g, ink):
    """Separate drawings on the sheet. Ground lines (long straight rows) are removed first so two views standing on
    one line stay apart; paper noise at the sheet border (blobs touching the edge) is dropped. Returns a list of
    {box: [x0, y0, x1, y1], ground_v: row or None} ordered top-to-bottom, left-to-right."""
    H, W = ink.shape
    grounds = _long_rows(ink, 0.35)

    def _label(gr):
        m = ink.copy()
        for y, a, b in gr:
            m[max(0, y - 1):y + 2, a:b] = False
        m = ndi.binary_opening(m, np.ones((2, 2)))           # stipple noise
        lab, n = ndi.label(ndi.binary_dilation(m, np.ones((15, 15))))
        return m, lab, n

    m, lab, n = _label(grounds)
    # a ground line lies UNDER a view; a long straight row running through a view's own height is one of its edges (the
    # straight body sides of a plan view): keep it as ink, or removing it cuts that view into pieces
    sl = ndi.find_objects(lab)
    inner = [(y, a, b) for y, a, b in grounds
             if any(s is not None and s[0].start + 12 < y < s[0].stop - 13 and s[1].start < b and a < s[1].stop for s in sl)]
    if inner:
        grounds = [g_ for g_ in grounds if g_ not in inner]
        m, lab, n = _label(grounds)
    out = []
    areas = ndi.sum(m, lab, range(1, n + 1))
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if ys.min() == 0 or xs.min() == 0 or ys.max() == H - 1 or xs.max() == W - 1:
            continue                                           # border noise
        if areas[k - 1] < 0.08 * areas.max():
            continue
        sub = m & (lab == k)
        yy, xx = np.nonzero(sub)
        box = [int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())]
        gv = None                                              # the ground line just under this view, if any
        for y, a, b in grounds:
            if box[3] - 3 <= y <= box[3] + 12 and a <= box[0] + 5 and b >= box[2] - 5:
                gv = y if gv is None else min(gv, y)
        out.append({"box": box, "ground_v": gv, "ink_px": int(sub.sum())})
    # a drawing that lies wholly inside another view's box (a cockpit drawn with a gap to the plan view's outline) is
    # part of that view, not a view of its own
    inside = lambda p, q: q["box"][0] <= p["box"][0] and q["box"][1] <= p["box"][1] and p["box"][2] <= q["box"][2] and p["box"][3] <= q["box"][3]
    for p in sorted(out, key=lambda v: v["ink_px"]):
        host = next((q for q in out if q is not p and inside(p, q)), None)
        if host:
            host["ink_px"] += p["ink_px"]
            out.remove(p)
    out.sort(key=lambda v: (round(v["box"][1] / 40), v["box"][0]))
    return out


def silhouette(ink, box, ground_v=None, close=2):
    """Filled outline of one view (ground line removed, enclosed areas filled). Bool array the size of the sheet."""
    x0, y0, x1, y1 = box
    if ground_v is not None:
        y1 = max(y1, min(ground_v + 1, ink.shape[0] - 1))       # include the ground rows: a tyre's bottom lies on them
    m = np.zeros_like(ink)
    sub = ink[y0:y1 + 1, x0:x1 + 1].copy()
    if ground_v is not None and y0 <= ground_v <= y1 + 2:
        gy = ground_v - y0
        band = sub[max(0, gy - 1):gy + 2].copy()
        sub[max(0, gy - 1):gy + 2] = False
        # keep the ground line where the object stands on it: between two strokes that reach the ground (a tyre's
        # sides in an end view, the tangent of a tyre circle in a side view), at most 20 % of the view wide apart
        above = ink[max(0, ground_v - 5):max(0, ground_v - 1), x0:x1 + 1].any(0) if ground_v - 1 > 0 else np.zeros(x1 - x0 + 1, bool)
        cols = np.nonzero(above)[0]
        W_ = x1 - x0 + 1
        if len(cols):
            runs_ = np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1)
            for a_, b_ in zip(runs_[:-1], runs_[1:]):
                if b_[0] - a_[-1] <= 0.2 * W_:
                    sub[max(0, gy - 1):gy + 2, a_[0]:b_[-1] + 1] = band[:, a_[0]:b_[-1] + 1]
            for r_ in runs_:
                sub[max(0, gy - 1):gy + 2, r_[0]:r_[-1] + 1] = band[:, r_[0]:r_[-1] + 1]
    P = 2 * close + 2                                          # pad: closing must not erode the crop's own edges
    sub = np.pad(sub, P)
    sub = ndi.binary_closing(sub, np.ones((2 * close + 1, 2 * close + 1)))
    filled = ndi.binary_fill_holes(sub)[P:-P, P:-P]
    if ground_v is not None and y0 <= ground_v <= y1:
        filled[ground_v - y0:] = False                         # the ground line is not part of the object
    lab, n = ndi.label(filled)
    if n:
        a = ndi.sum(filled, lab, range(1, n + 1))
        keep = [i + 1 for i in range(n) if a[i] >= 0.002 * a.max()]
        filled = np.isin(lab, keep)
    m[y0:y1 + 1, x0:x1 + 1] = filled
    return m


def ground_row(ink, box, ground_v):
    """The ground line row; if the sheet draws none (a plan view) None."""
    return ground_v


def view_extent(sil):
    ys, xs = np.nonzero(sil)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def classify_views(views, sils):
    """CV evidence for the view roles: a side view and a plan view share the object's length; the two remaining
    views (end views) share each other's size. Returns (roles {index: role}, evidence); front/rear of the end views
    and the nose direction are NOT decided here (AI stage S1 + confirmation)."""
    ext = [view_extent(s) for s in sils]
    dims = [(e[2] - e[0] + 1, e[3] - e[1] + 1) for e in ext]
    n = len(views)
    best = None
    for s in range(n):
        for t in range(n):
            if t == s:
                continue
            rest = [i for i in range(n) if i not in (s, t)]
            if len(rest) != 2:
                continue
            e_len = abs(dims[s][0] - dims[t][0]) / max(dims[s][0], dims[t][0])
            e_end = abs(dims[rest[0]][1] - dims[rest[1]][1]) / max(dims[rest[0]][1], dims[rest[1]][1])
            ground = 0 if views[s]["ground_v"] is not None else 0.05
            plan = 0 if views[t]["ground_v"] is None else 0.05
            aspect = 0 if dims[s][0] / dims[s][1] > dims[t][0] / dims[t][1] else 0.05
            e = e_len + e_end + ground + plan + aspect
            if best is None or e < best[0]:
                best = (e, s, t, rest)
    if best is None:
        raise ValueError(f"need 4 views (side, plan, two end views); found {n}")
    e, s, t, rest = best
    roles = {s: "side", t: "top", rest[0]: "end_a", rest[1]: "end_b"}
    ev = {"length_side_vs_top_px": [dims[s][0], dims[t][0]], "score": round(e, 4),
          "rule": "side and plan share the length; the side view stands on a ground line; the plan view does not; "
                  "end views share each other's height. Front/rear of the end views: not decided by CV."}
    return roles, ev


# ----------------------------------------------------------------------------------------------- profiles
def column_profiles(sil, x0, x1):
    top = np.full(x1 - x0 + 1, np.nan)
    bot = np.full(x1 - x0 + 1, np.nan)
    for i, x in enumerate(range(x0, x1 + 1)):
        ys = np.nonzero(sil[:, x])[0]
        if len(ys):
            top[i], bot[i] = ys.min(), ys.max()
    return top, bot


def row_profiles(sil, y0, y1):
    left = np.full(y1 - y0 + 1, np.nan)
    right = np.full(y1 - y0 + 1, np.nan)
    for i, y in enumerate(range(y0, y1 + 1)):
        xs = np.nonzero(sil[y])[0]
        if len(xs):
            left[i], right[i] = xs.min(), xs.max()
    return left, right


def _runs(row):
    d = np.diff(np.r_[0, row.astype(int), 0])
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1))


def wheels_side(ink, sil, ext, ground_v):
    """Wheel circles of the side view, measured: Hough circles (engine/circles.find) on the view crop, keeping the
    biggest circles that stand on the ground line; their concentric rings (rim lip, inner rim, hub) are kept too."""
    x0, y0, x1, y1 = ext
    crop = Image.fromarray(((~ink[y0:ground_v + 2, x0:x1 + 1]) * 255).astype(np.uint8)).convert("RGB")
    h = ground_v - y0
    found = _circles.find(crop, r_min=max(6, int(0.12 * h)), r_max=int(0.45 * h))
    out = []
    for c in sorted(found, key=lambda c: -c["r"]):
        cy = c["cy"] + y0
        if abs(cy + c["r"] - ground_v) <= max(4, 0.08 * c["r"]) and c["support"] >= 0.8:
            out.append({"cx": float(c["cx"] + x0), "cy": float(cy), "r": float(c["r"]),
                        "rings": [float(r) for r in c.get("rings", [c["r"]])], "support": float(c["support"])})
    out = sorted(out[:2], key=lambda w: w["cx"])
    return out


def arch_radius(ink, wheel, ground_v, search=(1.03, 1.45)):
    """The wheel-arch line around a tyre: the radius (centre = the wheel's) whose upper half-ring above the body's
    lower edge is best covered by ink. Measured; None if no ring above 50 % support exists."""
    cx, cy, r = wheel["cx"], wheel["cy"], wheel["r"]
    best = None
    for R in np.arange(search[0] * r, search[1] * r, 0.5):
        t = np.linspace(np.radians(200), np.radians(340), 140)        # upper arc only (image y down)
        hit = 0
        for dr in (-1, -0.5, 0, 0.5, 1):
            x = np.round(cx + (R + dr) * np.cos(t)).astype(int)
            y = np.round(cy + (R + dr) * np.sin(t)).astype(int)
            hit = np.maximum(hit, ink[y, x])
        s = float(np.mean(hit))
        if best is None or s > best[0] + 1e-9:
            best = (s, float(R))
    return {"r": best[1], "support": round(best[0], 3)} if best and best[0] >= 0.5 else None


def spoke_count(ink, wheel):
    """Spoke arms of a wheel: ink sampled on rings between the hub and the rim lip alternates once per arm; the
    dominant angular frequency (FFT) over several radii is the arm count. Returns (arms, strength)."""
    cx, cy = wheel["cx"], wheel["cy"]
    rings = sorted(wheel["rings"])
    lip = max(r for r in rings if r < wheel["r"] * 0.95) if any(r < wheel["r"] * 0.95 for r in rings) else 0.8 * wheel["r"]
    spec = np.zeros(257)
    for f in np.linspace(0.45, 0.85, 9):
        n = 512
        t = np.linspace(0, 2 * np.pi, n, endpoint=False)
        x = np.round(cx + f * lip * np.cos(t)).astype(int)
        y = np.round(cy + f * lip * np.sin(t)).astype(int)
        s = ink[y, x].astype(float)
        spec += np.abs(np.fft.rfft(s - s.mean()))
    k = int(np.argmax(spec[3:25])) + 3
    return k, float(spec[k] / max(spec[3:25].sum(), 1e-9))


# ----------------------------------------------------------------------------------------------- main entry
def observe(path):
    """The sheet -> observations dict (JSON-serialisable). Raises ValueError if it is not a 4-view sheet."""
    g, src = load(path)
    ink = ink_of(g)
    views = find_views(g, ink)
    sils = [silhouette(ink, v["box"], v["ground_v"]) for v in views]
    roles, role_ev = classify_views(views, sils)
    V = {}
    for i, v in enumerate(views):
        r = roles.get(i)
        if r:
            V[r] = {**v, "extent": view_extent(sils[i]), "_sil": sils[i]}
    side, top, ea, eb = V["side"], V["top"], V["end_a"], V["end_b"]

    # ---- the end views' ground: a shared ground line, or the bottom of their silhouettes
    for e in (ea, eb):
        if e["ground_v"] is None:
            e["ground_v"] = e["extent"][3] + 1
    gs = side["ground_v"] if side["ground_v"] is not None else side["extent"][3] + 1
    side["ground_v"] = gs

    # ---- side view: wheels, profiles
    sx0, sy0, sx1, sy1 = side["extent"]
    wl = wheels_side(ink, side["_sil"], side["extent"], gs)
    ztop_px, zbot_px = column_profiles(side["_sil"], sx0, sx1)
    for w in wl:
        a = arch_radius(ink, w, gs)
        w["arch"] = a
        w["spokes"], w["spoke_strength"] = spoke_count(ink, w)

    # ---- plan view: centreline, half-width (mirrors detected as narrow protrusions and taken out)
    tx0, ty0, tx1, ty1 = top["extent"]
    t_top, t_bot = column_profiles(top["_sil"], tx0, tx1)
    vc = float(np.nanmedian((t_top + t_bot) / 2))
    half = np.nanmax(np.c_[vc - t_top, t_bot - vc], axis=1)
    half_l, half_r = vc - t_top, t_bot - vc
    base = ndi.median_filter(np.nan_to_num(half, nan=0), size=max(9, int(0.09 * len(half))) | 1)
    bump = half - base
    mir_cols = np.nonzero(bump > 0.035 * np.nanmax(half))[0]
    mirror_plan = None
    if len(mir_cols):
        grp = np.split(mir_cols, np.nonzero(np.diff(mir_cols) > 3)[0] + 1)
        grp = max(grp, key=len)
        a, b = int(grp[0]), int(grp[-1])
        pad = max(4, int(1.0 * (b - a + 1)))                     # the stalk widens the body next to the head
        a2, b2 = max(0, a - pad), min(len(half) - 1, b + pad)
        mirror_plan = {"u0": tx0 + a, "u1": tx0 + b, "half_out_px": float(np.nanmax(half[a:b + 1])),
                       "half_base_px": float(np.nanmedian(base[a:b + 1]))}
        for arr in (half, half_l, half_r):
            idx = np.arange(len(arr))
            ok = (idx < a2) | (idx > b2)
            arr[~ok] = np.interp(idx[~ok], idx[ok], arr[ok])
    sym = float(np.nanmax(np.abs(half_l - half_r)))

    # ---- scales: side length = plan length (fit s_top), end-view height = side height (fit s_end)
    L_side = sx1 - sx0 + 1
    L_top = tx1 - tx0 + 1
    H_side = gs - sy0
    H_a, H_b = ea["ground_v"] - ea["extent"][1], eb["ground_v"] - eb["extent"][1]
    r_top = L_side / L_top
    r_end = H_side / ((H_a + H_b) / 2)

    # ---- end views: centre, tyre faces, envelope (mirror rows out), body bottom
    ends = {}
    for key, e in (("end_a", ea), ("end_b", eb)):
        ex0, ey0, ex1, ey1 = e["extent"]
        ga = e["ground_v"]
        rows = range(ey0, ga)
        left, right = row_profiles(e["_sil"], ey0, ga - 1)
        # tyres: the lowest rows split into two runs
        # tyres: vertical lines that run down to the ground through the lowest rows (the tyres' side faces); the two
        # outermost on each side bound each tyre
        band = ink[ga - 14:ga - 2, ex0:ex1 + 1].all(0)
        cols = [ex0 + (a + b) / 2 for a, b in _runs(band)]
        grp = []                                                   # a doubled line (2 strokes < 8 px apart) is one edge
        for c in cols:
            if grp and c - grp[-1][-1] < 8:
                grp[-1].append(c)
            else:
                grp.append([c])
        cols = [float(np.mean(g_)) for g_ in grp]
        tyres, uc_t = None, None
        if len(cols) >= 4:
            tyres = {"left": [cols[0], cols[1]], "right": [cols[-2], cols[-1]],
                     "evidence": "vertical ink lines reaching the ground line in the lowest 12 rows"}
            uc_t = (cols[0] + cols[-1]) / 2
        # body bottom: lowest row whose silhouette is one connected run across the centre
        uc = uc_t if uc_t is not None else (ex0 + ex1) / 2
        bottom_v = None
        for y in range(ga - 1, ey0, -1):
            if e["_sil"][y, int(round(uc))]:
                bottom_v = y
                break
        width = right - left
        med = ndi.median_filter(np.nan_to_num(width, nan=0), size=max(9, int(0.35 * len(width))) | 1)
        mir_rows = np.nonzero(width - med > 0.06 * np.nanmax(width))[0]
        mirror_end = None
        hw = np.maximum(uc - left, right - uc)
        if len(mir_rows):
            grp = max(np.split(mir_rows, np.nonzero(np.diff(mir_rows) > 2)[0] + 1), key=len)
            a, b = int(grp[0]), int(grp[-1])
            mirror_end = {"v0": ey0 + a, "v1": ey0 + b, "half_out_px": float(np.nanmax(hw[a:b + 1]))}
            pad = 2
            idx = np.arange(len(hw))
            ok = (idx < a - pad) | (idx > b + pad)
            hw = np.where(ok, hw, np.interp(idx, idx[ok], hw[ok]))
        ends[key] = {"extent": e["extent"], "ground_v": int(ga), "u_c": float(uc), "tyres": tyres,
                     "body_bottom_v": bottom_v, "half_width_px": [[int(ey0 + i), float(h)] for i, h in enumerate(hw)],
                     "mirror": mirror_end}

    regs, labs = {}, {}
    for role, v in V.items():
        regs[role], labs[role] = regions(ink, v["_sil"], v["extent"], role)
    obs = {"source": src, "role_evidence": role_ev, "regions": regs,
           "views": {k: {"box": v["box"], "extent": v["extent"], "ground_v": v["ground_v"]} for k, v in V.items()},
           "side": {"ztop_v": [[int(sx0 + i), float(t)] for i, t in enumerate(ztop_px)],
                    "zbot_v": [[int(sx0 + i), float(t)] for i, t in enumerate(zbot_px)],
                    "wheels": wl},
           "top": {"v_c": vc, "half_px": [[int(tx0 + i), float(h)] for i, h in enumerate(half)],
                   "symmetry_max_dev_px": round(sym, 2), "mirror": mirror_plan},
           "ends": ends,
           "fit": {"length_side_px": L_side, "length_top_px": L_top, "height_side_px": H_side,
                   "height_end_px": [H_a, H_b], "ratio_side_over_top": round(r_top, 4),
                   "ratio_side_over_end": round(r_end, 4)}}
    return obs, {"ink": ink, "sils": {k: v["_sil"] for k, v in V.items()}, "gray": g, "region_labels": labs}


def nose_left_cv(obs):
    """CV evidence for the nose direction in the side view: the nose end is the lower end of the top profile."""
    zt = np.array([t for _, t in obs["side"]["ztop_v"]])
    k = max(2, int(0.1 * len(zt)))
    return bool(np.nanmean(zt[:k]) > np.nanmean(zt[-k:]))


# ----------------------------------------------------------------------------------------------- closed regions
def regions(ink, sil, extent, view, min_px=40, max_n=48):
    """Closed areas the drawn lines cut a view's silhouette into (windows, panels, lights, intakes ...), measured.
    Each region: id "<view>.r<k>" (k by area, largest first), area, bbox, centroid, and its per-column extent
    (u -> [v_min, v_max]) and per-row extent (v -> [u_min, u_max]) in sheet px. Labels are NOT decided here."""
    x0, y0, x1, y1 = extent
    m = sil[y0:y1 + 1, x0:x1 + 1]
    k = ink[y0:y1 + 1, x0:x1 + 1]
    free = m & ~ndi.binary_dilation(k, iterations=1)
    lab, n = ndi.label(free)
    if not n:
        return [], np.full(m.shape, -1)
    area = ndi.sum(free, lab, range(1, n + 1))
    order = [int(i) for i in np.argsort(-area) if area[i] >= min_px][:max_n]
    out = []
    L = np.full(m.shape, -1, int)
    for r, i in enumerate(order):
        mk = lab == i + 1
        mk = ndi.binary_dilation(mk, iterations=1) & m          # give the 1 px the line removal took back
        L[mk & (L < 0)] = r
        ys, xs = np.nonzero(mk)
        cols = {}
        for u in np.unique(xs):
            vv = ys[xs == u]
            cols[int(u + x0)] = [int(vv.min() + y0), int(vv.max() + y0)]
        rows = {}
        for v in np.unique(ys):
            uu = xs[ys == v]
            rows[int(v + y0)] = [int(uu.min() + x0), int(uu.max() + x0)]
        out.append({"id": f"{view}.r{r:02d}", "area_px": int(mk.sum()),
                    "bbox": [int(xs.min() + x0), int(ys.min() + y0), int(xs.max() + x0), int(ys.max() + y0)],
                    "centroid": [round(float(xs.mean() + x0), 1), round(float(ys.mean() + y0), 1)],
                    "cols": cols, "rows": rows})
    return out, L


def region_overlay(gray, L, extent, regs, scale=2):
    """The view with every region tinted and numbered (what Muse Spark / Muse Wonder are shown)."""
    from PIL import ImageDraw
    x0, y0, x1, y1 = extent
    g = gray[y0:y1 + 1, x0:x1 + 1]
    rgb = np.repeat(g[..., None], 3, 2).astype(float)
    rng = np.random.default_rng(7)
    cols = rng.integers(70, 230, (len(regs), 3))
    for r in range(len(regs)):
        mk = L == r
        rgb[mk] = 0.45 * rgb[mk] + 0.55 * cols[r]
    im = Image.fromarray(rgb.clip(0, 255).astype(np.uint8)).resize(((x1 - x0 + 1) * scale, (y1 - y0 + 1) * scale), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for r, rg in enumerate(regs):
        cx, cy = (rg["centroid"][0] - x0) * scale, (rg["centroid"][1] - y0) * scale
        d.rectangle([cx - 8, cy - 7, cx + 10, cy + 8], fill=(255, 255, 255))
        d.text((cx - 6, cy - 6), str(r), fill=(0, 0, 0))
    return im


def exhaust_tips(gray, ink, rear_extent, u_c, near_px, r_range=(5.0, 13.0), min_support=0.95):
    """Exhaust tips in the rear view, measured: Hough circles (engine/circles.find) of tip size near the regions the
    AI labelled 'exhaust' (near_px = their centroids), non-maximum-suppressed, then kept only as LEFT/RIGHT MIRROR
    PAIRS about the view's centreline (|u_l + u_r - 2 u_c| <= 3 px, |v_l - v_r| <= 3 px). Returns tips (sheet px)."""
    x0, y0, x1, y1 = rear_extent
    crop = Image.fromarray(((~ink[y0:y1 + 1, x0:x1 + 1]) * 255).astype(np.uint8)).convert("RGB")
    found = _circles.find(crop, r_min=int(r_range[0]) - 1, r_max=int(r_range[1]) + 2)
    cand = []
    for c in found:
        u, v, r = c["cx"] + x0, c["cy"] + y0, c["r"]
        if not (r_range[0] <= r <= r_range[1]) or c["support"] < min_support:
            continue
        if near_px and min(np.hypot(u - a, v - b) for a, b in near_px) > 40:
            continue
        cand.append((c["support"] * r, u, v, r))
    keep = []
    for sc, u, v, r in sorted(cand, reverse=True):
        if all(np.hypot(u - k[0], v - k[1]) > 0.9 * max(r, k[2]) for k in keep):
            keep.append((u, v, r))
    tips = []
    used = set()
    for i, (u, v, r) in enumerate(keep):
        if i in used or u > u_c:
            continue
        for j, (u2, v2, r2) in enumerate(keep):
            if j != i and j not in used and u2 > u_c and abs(u + u2 - 2 * u_c) <= 3 and abs(v - v2) <= 3:
                used |= {i, j}
                tips.append({"u": [u, u2], "v": (v + v2) / 2, "r": (r + r2) / 2,
                             "pair_symmetry_px": round(abs(u + u2 - 2 * u_c), 2)})
                break
    return tips


def lug_count(ink, wheel, k_range=(3, 8)):
    """Lug nuts: ink on rings around the hub alternates once per nut; dominant angular frequency over radii between
    35 % and 75 % of the innermost ring (the hub). Returns (count, strength) or (None, 0) if no clear peak."""
    cx, cy = wheel["cx"], wheel["cy"]
    hub = min(wheel["rings"]) if len(wheel["rings"]) > 1 else 0.35 * wheel["r"]
    spec = np.zeros(129)
    for f in np.linspace(0.35, 0.75, 7):
        t = np.linspace(0, 2 * np.pi, 256, endpoint=False)
        x = np.round(cx + f * hub * np.cos(t)).astype(int)
        y = np.round(cy + f * hub * np.sin(t)).astype(int)
        s = ink[y, x].astype(float)
        spec += np.abs(np.fft.rfft(s - s.mean()))
    lo, hi = k_range
    k = int(np.argmax(spec[lo:hi + 1])) + lo
    strength = float(spec[k] / max(spec[1:20].sum(), 1e-9))
    return (k, strength) if strength >= 0.12 else (None, strength)


def region_polygon(L, extent, index, eps=0.6, max_pts=60):
    """Outline of one region (marching squares on its mask, Ramer-Douglas-Peucker), sheet px, counter-clockwise
    in image coordinates. None if the region is too small to outline."""
    from engine import outline as _ol
    x0, y0, _, _ = extent
    m = L == index
    if m.sum() < 12:
        return None
    m = ndi.binary_opening(m, np.ones((2, 2))) | (m & ndi.binary_erosion(m))
    loops = _ol.trace(m)
    if not loops:
        return None
    P = max(loops, key=lambda q: abs(_ol.area(q)))
    P = _ol.simplify(P, eps)
    while len(P) > max_pts:
        eps *= 1.4
        P = _ol.simplify(max(loops, key=lambda q: abs(_ol.area(q))), eps)
    return [[float(x + x0), float(y + y0)] for x, y in P]
