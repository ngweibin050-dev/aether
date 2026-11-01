"""Object-specific interpretation for a vehicle three-view (first domain implementation).

Input: cad.observations output (pixels) + decisions (scale, which end view is the front, AI hypotheses).
Output: model-frame curves (mm) and the derived quantities the planner turns into parameters, each with its
provenance class. Nothing here builds geometry.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

MEASURED, DERIVED, INFERRED, ASSUMED, UNRESOLVED, USER = (
    "measured", "derived", "inferred", "assumed", "unresolved", "user_confirmed")


def _clean(a):
    a = np.asarray(a, float)
    idx = np.arange(len(a))
    ok = np.isfinite(a)
    return np.interp(idx, idx[ok], a[ok]) if ok.any() else a


def smooth_curve(x, y, sigma, what):
    """Noise-aware smoothing spline through a measured profile: sigma = the measurement noise (mm) of one sample
    (half a pixel of the view's scale). Keeps the drawn shape (residual ~ sigma) and removes pixel staircases, which an
    interpolating NURBS would otherwise turn into ripples. Returns (y_smooth, stats)."""
    from scipy.interpolate import make_smoothing_spline
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    o = np.argsort(x)
    xs, ys = x[o], y[o]
    keep = np.r_[True, np.diff(xs) > 1e-9]
    xs, ys = xs[keep], ys[keep]
    # lam chosen so the RMS residual is about sigma (bisection on log lam)
    lo, hi = -6.0, 12.0
    best = None
    for _ in range(40):
        mid = (lo + hi) / 2
        sp = make_smoothing_spline(xs, ys, lam=10 ** mid)
        r = float(np.sqrt(np.mean((sp(xs) - ys) ** 2)))
        best = (sp, r)
        if r > sigma:
            hi = mid
        else:
            lo = mid
    sp, r = best
    out = sp(x)
    return out, {"curve": what, "rms_residual_mm": round(r, 3), "max_residual_mm": round(float(np.max(np.abs(sp(xs) - ys))), 3),
                 "noise_sigma_mm": round(sigma, 3), "method": "penalised cubic smoothing spline, RMS residual = sigma"}


def frames(obs, decisions):
    """Per-view affine transforms px -> mm, from the assumed / confirmed length and the fitted scale ratios."""
    L_px = obs["fit"]["length_side_px"]
    L_mm = float(decisions["overall_length_mm"]["value"])
    s_side = L_mm / L_px
    per_view = decisions.get("end_view_scale", {"value": "per_view"})["value"] == "per_view"
    s_top = s_side * obs["fit"]["ratio_side_over_top"]
    s_end = s_side * (obs["fit"]["ratio_side_over_end"] if per_view else 1.0)
    side = obs["views"]["side"]
    top = obs["views"]["top"]
    nose_left = decisions["nose_left"]["value"]
    front_key = decisions["front_view"]["value"]
    rear_key = "end_a" if front_key == "end_b" else "end_b"
    sx0, sx1 = side["extent"][0], side["extent"][2]
    tx0, tx1 = top["extent"][0], top["extent"][2]
    return {
        "side": {"s": s_side, "u0": sx0 if nose_left else sx1, "dir": 1 if nose_left else -1, "v_ground": side["ground_v"]},
        "top": {"s": s_top, "u0": tx0 if nose_left else tx1, "dir": 1 if nose_left else -1, "v_c": obs["top"]["v_c"]},
        "front": {"s": s_end, "key": front_key, "u_c": obs["ends"][front_key]["u_c"], "v_ground": obs["ends"][front_key]["ground_v"], "ysign": 1},
        "rear": {"s": s_end, "key": rear_key, "u_c": obs["ends"][rear_key]["u_c"], "v_ground": obs["ends"][rear_key]["ground_v"], "ysign": -1},
        "scale_mode": "per_view" if per_view else "single",
    }


def side_xz(F, u, v):
    f = F["side"]
    return f["dir"] * (np.asarray(u, float) - f["u0"]) * f["s"], (f["v_ground"] - np.asarray(v, float)) * f["s"]


def top_xy(F, u, v):
    f = F["top"]
    return f["dir"] * (np.asarray(u, float) - f["u0"]) * f["s"], (f["v_c"] - np.asarray(v, float)) * f["s"]


def end_yz(F, which, u, v):
    f = F[which]
    return f["ysign"] * (np.asarray(u, float) - f["u_c"]) * f["s"], (f["v_ground"] - np.asarray(v, float)) * f["s"]


def curves(obs, F):
    """Model-frame curves: ztop(x), zbot(x) (side), ybody(x) (plan), envelopes (end views), wheels."""
    zt = np.array(obs["side"]["ztop_v"], float)
    zb = np.array(obs["side"]["zbot_v"], float)
    x, ztop = side_xz(F, zt[:, 0], _clean(zt[:, 1]))
    _, zbot_raw = side_xz(F, zb[:, 0], _clean(zb[:, 1]))
    order = np.argsort(x)
    x, ztop, zbot_raw = x[order], ztop[order], zbot_raw[order]
    wheels = []
    for w in obs["side"]["wheels"]:
        cx, cz = side_xz(F, w["cx"], w["cy"])
        s = F["side"]["s"]
        r_ground = (F["side"]["v_ground"] - 1 - w["cy"]) * s          # the drawn tyre stands on the ground line
        wheels.append({"x": float(cx), "z_centre_drawn": float(cz), "r_tyre": max(w["r"] * s, r_ground),
                       "r_tyre_circle": w["r"] * s, "r_tyre_to_ground": r_ground,
                       "r_arch": (w["arch"]["r"] * s) if w.get("arch") else None,
                       "rings": [r * s for r in w["rings"]], "spoke_arms": w["spokes"],
                       "spoke_strength": w["spoke_strength"], "px": w})
    wheels.sort(key=lambda w: w["x"])
    # lower profile: inside the wheel columns the silhouette bottom is the tyre, not the body: the body's lower edge
    # there is unseen; it is bridged straight between the arch edges (assumption, recorded by the planner)
    zbot = zbot_raw.copy()
    bridged = []
    for w in wheels:
        ra = w["r_arch"] or 1.08 * w["r_tyre"]
        m = np.abs(x - w["x"]) <= ra
        if m.any():
            idx = np.nonzero(m)[0]
            a, b = max(idx[0] - 1, 0), min(idx[-1] + 1, len(x) - 1)
            zbot[m] = np.interp(x[m], [x[a], x[b]], [zbot_raw[a], zbot_raw[b]])
            bridged.append([float(x[a]), float(x[b])])
    hp = np.array(obs["top"]["half_px"], float)
    xt, _ = top_xy(F, hp[:, 0], np.zeros(len(hp)))
    yb = hp[:, 1] * F["top"]["s"]
    o = np.argsort(xt)
    xt, yb = xt[o], yb[o]
    fits = []
    ss, st_ = F["side"]["s"], F["top"]["s"]
    ztop_raw = ztop.copy()
    ztop, f1 = smooth_curve(x, ztop, 0.5 * ss, "ztop (side upper silhouette)")
    zbot, f2 = smooth_curve(x, zbot, 0.5 * ss, "zbot (side lower edge, bridged under the wheels)")
    yb_raw = yb.copy()
    yb, f3 = smooth_curve(xt, yb, 0.5 * st_, "ybody (plan half-width, mirrors removed)")
    fits += [f1, f2, f3]
    env = {}
    for which in ("front", "rear"):
        e = obs["ends"][F[which]["key"]]
        hw = np.array(e["half_width_px"], float)
        _, z = end_yz(F, which, np.zeros(len(hw)), hw[:, 0])
        w = hw[:, 1] * F[which]["s"]
        o = np.argsort(z)
        z, w = z[o], w[o]
        z_body_bottom = float(end_yz(F, which, 0, e["body_bottom_v"])[1]) if e["body_bottom_v"] else 0.0
        keep = z >= z_body_bottom
        ws, fe = smooth_curve(z[keep], w[keep], 0.5 * F[which]["s"], f"envelope {which} view (half-width vs height)")
        fits.append(fe)
        env[which] = {"z": z[keep], "w": ws, "w_raw": w[keep], "w_norm": ws / max(ws.max(), 1e-9),
                      "z_body_bottom": z_body_bottom, "mirror": e["mirror"], "tyres": e["tyres"]}
    return {"x": x, "ztop": ztop, "ztop_raw": ztop_raw, "zbot": zbot, "zbot_raw": zbot_raw, "bridged": bridged,
            "xt": xt, "ybody": yb, "ybody_raw": yb_raw, "env": env, "wheels": wheels, "fits": fits}


def stations(C, n_min=18, max_dev_mm=None, min_gap_frac=0.02):
    """Station x positions: mandatory structural stations + curvature-adaptive refinement until the straight line
    between neighbours stays within max_dev_mm of every profile (ztop, zbot, ybody)."""
    x, L = C["x"], float(C["x"][-1] - C["x"][0])
    max_dev_mm = max_dev_mm or 0.004 * L
    x0, x1 = float(x[0]) + 0.004 * L, float(x[-1]) - 0.004 * L
    mand = {"nose": x0, "tail": x1}
    for i, w in enumerate(C["wheels"]):
        ra = w["r_arch"] or 1.08 * w["r_tyre"]
        tag = "front" if i == 0 else "rear"
        mand[f"{tag}_arch_front_edge"] = w["x"] - ra
        mand[f"{tag}_axle"] = w["x"]
        mand[f"{tag}_arch_rear_edge"] = w["x"] + ra
    zt = C["ztop"]
    mand["roof_peak"] = float(x[int(np.argmax(zt))])
    yb = np.interp(x, C["xt"], C["ybody"])
    prof = [zt, C["zbot"], yb]
    S = sorted(set(round(v, 3) for v in mand.values() if x0 <= v <= x1))
    for _ in range(60):
        worst = None
        for a, b in zip(S, S[1:]):
            m = (x > a) & (x < b)
            if not m.any():
                continue
            for p in prof:
                pa, pb = np.interp(a, x, p), np.interp(b, x, p)
                lin = pa + (pb - pa) * (x[m] - a) / (b - a)
                d = np.abs(p[m] - lin)
                if d.max() > max_dev_mm and (worst is None or d.max() > worst[0]):
                    worst = (d.max(), float(x[m][np.argmax(d)]))
        if worst is None:
            break
        xn = worst[1]
        if min(abs(xn - s) for s in S) < min_gap_frac * L:
            # too close to an existing station: put it in the middle of the widest gap instead (keeps spacing sane)
            gaps = [(b - a, (a + b) / 2) for a, b in zip(S, S[1:])]
            g, xn = max(gaps)
            if g < 2 * min_gap_frac * L:
                break
        S = sorted(S + [round(xn, 3)])
    while len(S) < n_min:
        g, xn = max((b - a, (a + b) / 2) for a, b in zip(S, S[1:]))
        S = sorted(S + [round(xn, 3)])
    names = {}
    for k, v in mand.items():
        names[round(v, 3)] = k
    return [{"x": s, "role": names.get(s, "adaptive")} for s in S]


def blend_weight(x, x_front_axle, x_rear_axle):
    """Front-envelope weight: 1 ahead of the front axle, 0 behind the rear axle, smoothstep between (inferred)."""
    t = np.clip((x - x_front_axle) / max(x_rear_axle - x_front_axle, 1e-9), 0, 1)
    return float(1 - (3 * t * t - 2 * t ** 3))


GREENHOUSE_TOP = ("roof", "windscreen", "rear_window", "pillar")


def labelled(obs, labels, view, kinds, accepted_only=True):
    """Regions of a view whose S3 label is in kinds (accepted labels only, unless accepted_only is False)."""
    out = []
    for i, rg in enumerate(obs["regions"][view]):
        lab = labels.get(view, {}).get(i) or labels.get(view, {}).get(str(i))
        if not lab or lab.get("kind") not in kinds:
            continue
        if accepted_only and lab.get("status") != "accepted":
            continue
        out.append(rg)
    return out


def greenhouse(obs, labels, F, C):
    """Greenhouse (cabin) curves from labelled regions, all measured on the ink:
    plan view: y_roof(x) = half-width of the roof + windscreen (+ pillars, rear glass) outline; y_belt(x) = outer edge of
    the side glass seen from above (the beltline width: the glass leans in, the tumblehome is visible in plan);
    side view: z_belt(x) = lower edge of the side windows; z_glass(x) = upper edge (the roof rail).
    Returns None if the needed regions are not labelled (then the body has no separate greenhouse: recorded)."""
    top = labelled(obs, labels, "top", GREENHOUSE_TOP)
    glass_top = labelled(obs, labels, "top", ("side_window",))
    glass_side = labelled(obs, labels, "side", ("side_window",))
    if not top or not glass_side:
        return None
    vc = F["top"]["v_c"]
    cols = {}
    for rg in top:
        for u, (v0, v1) in rg["cols"].items():
            u = int(u)
            h = max(abs(vc - v0), abs(v1 - vc))
            cols[u] = max(cols.get(u, 0.0), h)
    u = np.array(sorted(cols))
    xr, _ = top_xy(F, u, np.zeros(len(u)))
    yr = np.array([cols[k] for k in u]) * F["top"]["s"]
    o = np.argsort(xr)
    xr, yr = xr[o], yr[o]
    # the drawn lines BETWEEN the windscreen, pillar and roof regions belong to neither: close those narrow dips
    # (grey closing over 5 % of the length) so the outline is the greenhouse's outer edge
    wclose = max(5, int(0.05 * len(yr)) | 1)
    yr = ndi.grey_closing(yr, size=wclose)
    gcols = {}
    for rg in glass_top:
        for uu, (v0, v1) in rg["cols"].items():
            uu = int(uu)
            h = max(abs(vc - v0), abs(v1 - vc))
            gcols[uu] = max(gcols.get(uu, 0.0), h)
    gu = np.array(sorted(gcols)) if gcols else np.zeros(0)
    xg, _ = top_xy(F, gu, np.zeros(len(gu)))
    yg = np.array([gcols[k] for k in gu]) * F["top"]["s"] if len(gu) else np.zeros(0)
    o = np.argsort(xg)
    xg, yg = xg[o], yg[o]
    lo, hi = {}, {}
    for rg in glass_side:
        for uu, (v0, v1) in rg["cols"].items():
            uu = int(uu)
            lo[uu] = max(lo.get(uu, -1), v1)                 # image y down: the lower edge is the larger v
            hi[uu] = min(hi.get(uu, 10 ** 9), v0)
    su = np.array(sorted(lo))
    xs, zb = side_xz(F, su, np.array([lo[k] for k in su]))
    _, zg = side_xz(F, su, np.array([hi[k] for k in su]))
    o = np.argsort(xs)
    xs, zb, zg = xs[o], zb[o], zg[o]
    fits = []
    yr_s, f = smooth_curve(xr, yr, 0.5 * F["top"]["s"], "greenhouse half-width in plan (roof + windscreen outline)")
    fits.append(f)
    if len(xg) > 8:
        yg_s, f = smooth_curve(xg, yg, 0.5 * F["top"]["s"], "beltline half-width in plan (side glass outer edge)")
        fits.append(f)
    else:
        yg_s = yg
    # the beltline is drawn as one straight line under both side windows; anything above it (the mirror cutting into
    # the window's lower corner, the gap between the two windows) is not beltline: robust straight-line fit
    keep = np.ones(len(xs), bool)
    for _ in range(6):
        A = np.c_[xs[keep], np.ones(keep.sum())]
        coef, *_ = np.linalg.lstsq(A, zb[keep], rcond=None)
        res = zb - (coef[0] * xs + coef[1])
        sig = max(float(np.std(res[keep])), 0.5 * F["side"]["s"])
        new = res < 2.0 * sig                                   # only points ABOVE the line can be non-beltline
        if (new == keep).all():
            break
        keep = new
    zb_s = coef[0] * xs + coef[1]
    fits.append({"curve": "beltline height (side glass lower edge)", "method": "robust straight-line fit (points above "
                 "the line rejected: mirror cut-out, window gap)", "slope": round(float(coef[0]), 4),
                 "rms_residual_mm": round(float(np.sqrt(np.mean(res[keep] ** 2))), 3),
                 "rejected_columns": int((~keep).sum()), "used_columns": int(keep.sum())})
    belt_line = [float(coef[0]), float(coef[1])]
    zg_s, f = smooth_curve(xs, zg, 0.5 * F["side"]["s"], "roof-rail height (side glass upper edge)")
    fits.append(f)
    return {"x_roof": xr, "y_roof": yr_s, "y_roof_raw": yr, "x_glass_plan": xg, "y_belt_plan": yg_s,
            "x_glass_side": xs, "z_belt": zb_s, "z_glass_top": zg_s, "fits": fits, "belt_line": belt_line,
            "x_range": [float(xr.min()), float(xr.max())],
            "regions": {"top": [r["id"] for r in top], "glass_top": [r["id"] for r in glass_top],
                        "glass_side": [r["id"] for r in glass_side]}}


DEFAULT_SHAPE = {   # used only when no accepted Muse Wonder hypothesis exists (provenance "assumed")
    "front_deck": {"crown_frac": 0.06, "deck_drop_frac": 0.14, "sill_radius_frac": 0.10, "glass_bulge_frac": 0.0},
    "cabin": {"crown_frac": 0.05, "deck_drop_frac": 0.12, "sill_radius_frac": 0.10, "glass_bulge_frac": 0.04},
    "rear_deck": {"crown_frac": 0.05, "deck_drop_frac": 0.12, "sill_radius_frac": 0.10, "glass_bulge_frac": 0.0},
}


def env_blend(C, w_front):
    ef, er = C["env"]["front"], C["env"]["rear"]
    zz = np.linspace(0, max(ef["z"].max(), er["z"].max()), 400)
    wf = np.interp(zz, ef["z"], ef["w_norm"])
    wr = np.interp(zz, er["z"], er["w_norm"])
    return zz, w_front * wf + (1 - w_front) * wr


def z_max_global(C):
    """Height of the top of the body's widest band (end views; the plateau where the envelope >= 98.5 %)."""
    out = {}
    for k in ("front", "rear"):
        e = C["env"][k]
        z = e["z"][e["w_norm"] >= 0.985]
        out[k] = float(z.max()) if len(z) else float(e["z"][np.argmax(e["w_norm"])])
    return out


def cabin_weight(C, G, x):
    """1 where the greenhouse exists (plan outline present and the roof above the beltline), 0 on the decks;
    smoothstep over the first / last 15 % of the greenhouse height."""
    if G is None or not (G["x_range"][0] <= x <= G["x_range"][1]):
        return 0.0
    zt = float(np.interp(x, C["x"], C["ztop"]))
    zb = G["belt_line"][0] * x + G["belt_line"][1]
    h_max = max(float(np.max(C["ztop"])) - (G["belt_line"][0] * float(C["x"][np.argmax(C["ztop"])]) + G["belt_line"][1]), 1.0)
    t = np.clip((zt - zb) / (0.25 * h_max), 0, 1)
    return float(3 * t * t - 2 * t ** 3)


def station_keypoints(C, G, x, shape, zmax_g, x_front_axle, x_rear_axle):
    """All keypoints of one station + where each came from. shape: {group: fractions} (Muse Wonder or default)."""
    zt = float(np.interp(x, C["x"], C["ztop"]))
    zb = float(np.interp(x, C["x"], C["zbot"]))
    ym = float(np.interp(x, C["xt"], C["ybody"]))
    H = zt - zb
    w_front = blend_weight(x, x_front_axle, x_rear_axle)
    zz, ee = env_blend(C, w_front)
    wc = cabin_weight(C, G, x)
    group = "cabin" if wc > 0.5 else ("front_deck" if G is None or x < (G["x_range"][0] + G["x_range"][1]) / 2 else "rear_deck")
    deck_group = "front_deck" if G is None or x < (G["x_range"][0] + G["x_range"][1]) / 2 else "rear_deck"
    sd, sc = shape[deck_group], shape["cabin"]
    zm_g = w_front * zmax_g["front"] + (1 - w_front) * zmax_g["rear"]
    # deck keypoints (no greenhouse): shoulder = deck edge, roof edge = a point on the crowned deck
    z_sh_d = zt - sd["deck_drop_frac"] * H
    e_at = lambda z: float(np.interp(z, zz, ee))
    zm_d = min(zm_g, z_sh_d - 0.2 * (z_sh_d - zb))
    y_sh_d = min(ym, ym * e_at(z_sh_d) / max(e_at(zm_d), 1e-6))
    f = 0.55
    y_re_d, z_re_d = f * y_sh_d, zt - (zt - z_sh_d) * f * f
    kp = {"deck": {"z_sh": z_sh_d, "y_sh": y_sh_d, "z_re": z_re_d, "y_re": y_re_d, "z_max": zm_d, "bulge": 0.0}}
    src = {"z_top": "measured (side upper silhouette)", "z_bot": "measured (side lower edge; bridged under wheels: assumed)",
           "y_max": "measured (plan half-width)"}
    if wc > 0:
        Ltot = float(C["x"][-1] - C["x"][0])
        def outside_w(a, b):
            """0 inside the measured range [a, b], rising smoothly to 1 at 6 % of the length outside it."""
            d = max(a - x, x - b, 0.0) / (0.06 * Ltot)
            t = min(d, 1.0)
            return 3 * t * t - 2 * t ** 3
        z_sh_c = G["belt_line"][0] * x + G["belt_line"][1]
        xs = G["x_glass_side"]
        ws = outside_w(xs.min(), xs.max())
        z_glass = float(np.interp(x, xs, G["z_glass_top"]))            # clamped at the ends of the measured range
        z_re_c = (1 - ws) * z_glass + ws * (zt - sc["crown_frac"] * H)
        y_re_c = float(np.interp(x, G["x_roof"], G["y_roof"]))
        xg = G["x_glass_plan"]
        wp = outside_w(xg.min(), xg.max()) if len(xg) else 1.0
        y_belt = float(np.interp(x, xg, G["y_belt_plan"])) if len(xg) else y_sh_d
        y_sh_c = max((1 - wp) * y_belt + wp * y_sh_d, y_re_c + 5.0)
        ysrc = ("measured (plan: side glass outer edge)" if wp == 0 else
                f"measured plan side-glass edge blended into the deck shoulder (weight {wp:.2f}, inferred)")
        zm_c = min(zm_g, z_sh_c - 0.2 * (z_sh_c - zb))
        kp["cabin"] = {"z_sh": z_sh_c, "y_sh": y_sh_c, "z_re": z_re_c, "y_re": y_re_c, "z_max": zm_c,
                       "bulge": sc["glass_bulge_frac"]}
        src.update({"z_sh": "measured (side: beltline fit)", "y_sh": ysrc,
                    "z_re": "measured (side: glass upper edge)" if ws == 0 else
                            f"side glass upper edge blended into the crown (weight {ws:.2f}, inferred)",
                    "y_re": "measured (plan: greenhouse outline)"})
    else:
        src.update({"z_sh": "inferred (deck edge: deck_drop_frac)", "y_sh": "inferred (end-view envelope at the deck edge)",
                    "z_re": "inferred (crown)", "y_re": "inferred (crown)"})
    mix = lambda key: wc * kp["cabin"][key] + (1 - wc) * kp["deck"][key] if wc > 0 else kp["deck"][key]
    k = {"x": float(x), "z_top": zt, "z_bot": zb, "y_max": ym, "z_max": mix("z_max"), "z_sh": mix("z_sh"),
         "y_sh": mix("y_sh"), "z_re": mix("z_re"), "y_re": mix("y_re"), "glass_bulge": mix("bulge"),
         "r_low": float(np.clip(shape[group]["sill_radius_frac"] * H, 5.0, 0.3 * H)), "w_front": w_front,
         "cabin_weight": wc, "group": group}
    # keep the sketch constraints satisfiable; every clamp is recorded
    clamps = []
    def fix(key, val, why):
        if abs(k[key] - val) > 1e-6:
            clamps.append({"key": key, "from": round(k[key], 2), "to": round(val, 2), "why": why})
            k[key] = val
    fix("z_max", max(k["z_max"], k["z_bot"] + k["r_low"] + 2.0) if k["z_max"] < k["z_bot"] + k["r_low"] + 2.0 else k["z_max"], "above the sill")
    fix("z_sh", max(k["z_sh"], k["z_max"] + 1.0), "shoulder above the widest point")
    fix("z_re", min(max(k["z_re"], k["z_sh"] + 1.0), k["z_top"] - 0.5), "roof edge between shoulder and top")
    fix("z_sh", min(k["z_sh"], k["z_re"] - 0.5), "shoulder below the roof edge")
    fix("y_sh", min(k["y_sh"], k["y_max"]), "shoulder not wider than the body")
    fix("y_re", min(max(k["y_re"], 1.0), k["y_sh"] - 0.5), "roof edge inside the shoulder")
    k["clamps"] = clamps
    k["sources"] = src
    return k


FIELD_KEYS = ("z_top", "z_bot", "y_max", "z_max", "y_sh", "z_sh", "y_re", "z_re", "glass_bulge", "r_low", "w_front",
              "cabin_weight")
FIELD_CLASS = {"z_top": "measured", "z_bot": "measured", "y_max": "measured", "z_max": "derived", "y_sh": "derived",
               "z_sh": "derived", "y_re": "derived", "z_re": "derived", "glass_bulge": "inferred", "r_low": "inferred",
               "w_front": "inferred", "cabin_weight": "derived"}


def keypoint_fields(C, G, shape, n=240):
    """Every section keypoint as a smooth field along x (dense grid, then a smoothing spline per field). Deck and cabin
    definitions meet continuously: on the decks the roof-edge width is the deck-edge width times a factor that equals
    the MEASURED plan greenhouse width at the cabin boundary (so the two definitions agree where they meet).
    Returns {"x": grid, key: values, "_notes": [...]}."""
    x0, x1 = float(C["x"][0]) + 0.004 * (C["x"][-1] - C["x"][0]), float(C["x"][-1]) - 0.004 * (C["x"][-1] - C["x"][0])
    xs = np.linspace(x0, x1, n)
    zg = z_max_global(C)
    xa, xr = C["wheels"][0]["x"], C["wheels"][1]["x"]
    raw = [station_keypoints(C, G, x, shape, zg, xa, xr) for x in xs]
    notes = []
    if G is not None:
        # continuity factor for the deck roof-edge width at each cabin boundary
        for side, xb in (("front", G["x_range"][0]), ("rear", G["x_range"][1])):
            i = int(np.argmin(np.abs(xs - xb)))
            k = raw[i]
            yr = float(np.interp(xb, G["x_roof"], G["y_roof"]))
            f = float(np.clip(yr / max(k["y_sh"], 1e-6), 0.2, 0.95))
            notes.append({"deck_roof_edge_factor": side, "value": round(f, 3),
                          "why": "makes the deck's inferred roof-edge width equal the measured plan greenhouse width "
                                 "at the cabin boundary"})
            for kk, x in zip(raw, xs):
                if (side == "front" and x < xb) or (side == "rear" and x > xb):
                    zt, zsh = kk["z_top"], kk["z_sh"]
                    kk["y_re"] = f * kk["y_sh"]
                    kk["z_re"] = zt - (zt - zsh) * f * f
            # inside the cabin's plan range the roof-edge width is the measured plan outline everywhere
        for kk, x in zip(raw, xs):
            if G["x_range"][0] <= x <= G["x_range"][1]:
                kk["y_re"] = float(np.interp(x, G["x_roof"], G["y_roof"]))
    out = {"x": xs}
    for key in FIELD_KEYS:
        v = np.array([k[key] for k in raw], float)
        if key in ("z_top", "z_bot", "y_max", "w_front", "cabin_weight"):
            out[key] = v                                           # already smooth (measured curves / smoothstep)
        else:
            span = max(float(np.ptp(v)), 1e-6)
            out[key], f = smooth_curve(xs, v, 0.015 * span + 0.5, f"field {key}")   # derived fields: 1.5 % of their range
            notes.append(f)
    # re-impose the sketch constraints after smoothing (recorded): project every station's heights into the feasible
    # chain z_bot + r_low < z_max < z_sh < z_re < z_top (each clamped into the band its neighbours leave) and the
    # widths into 0 < y_re < y_sh <= y_max
    fixes = 0
    for i in range(n):
        zb, zt, ym = out["z_bot"][i], out["z_top"][i], out["y_max"][i]
        H = zt - zb
        rl = float(np.clip(out["r_low"][i], 2.0, 0.3 * H))
        e = max(0.06 * H, 1.0)                    # keypoints at least 6 % of the section height apart (no collapse)
        zm = float(np.clip(out["z_max"][i], zb + rl + e, zt - 3 * e))
        zsh = float(np.clip(out["z_sh"][i], zm + e, zt - 2 * e))
        zre = float(np.clip(out["z_re"][i], zsh + e, zt - e))
        ysh = float(min(out["y_sh"][i], ym))
        yre = float(np.clip(out["y_re"][i], 1.0, ysh - 0.5))
        out["glass_bulge"][i] = float(max(out["glass_bulge"][i], 0.0) * out["cabin_weight"][i])   # glass only where a cabin is
        ysh = min(ysh, ym - 0.04 * ym) if zsh - zm < 2 * e else ysh                            # a real shoulder curve
        yre = float(np.clip(yre, 1.0, ysh - 0.05 * ysh))
        new = (rl, zm, zsh, zre, ysh, yre)
        old = (out["r_low"][i], out["z_max"][i], out["z_sh"][i], out["z_re"][i], out["y_sh"][i], out["y_re"][i])
        if any(abs(a - b) > 1e-6 for a, b in zip(new, old)):
            fixes += 1
        out["r_low"][i], out["z_max"][i], out["z_sh"][i], out["z_re"][i], out["y_sh"][i], out["y_re"][i] = new
    notes.append({"constraint_fixes_after_smoothing": fixes, "of_samples": n})
    out["_notes"] = notes
    return out


def keypoints_at(fields, x):
    k = {key: float(np.interp(x, fields["x"], fields[key])) for key in FIELD_KEYS}
    k["x"] = float(x)
    return k


def crown_exponent(C, G, F):
    """Roof crown shape z = z_top - (z_top - z_re) * (y / y_re)^p: p fitted so the crown matches the end views'
    top envelope (the drawn roof is flat and wide: p > 2). Returns (p, evidence)."""
    if G is None:
        return 2.0, "no greenhouse: parabolic crown (assumed)"
    i = int(np.argmax(C["ztop"]))
    x = float(C["x"][i])
    zt = float(C["ztop"][i])
    xs = G["x_glass_side"]
    zre = float(np.interp(x, xs, G["z_glass_top"]))
    yre = float(np.interp(x, G["x_roof"], G["y_roof"]))
    ps = []
    for which in ("front", "rear"):
        e = C["env"][which]
        for dz in np.linspace(0.15, 0.85, 8) * (zt - zre):
            w = float(np.interp(zt - dz, e["z"], e["w"]))
            r = min(w / max(yre, 1e-6), 0.999)
            if 0.05 < r < 0.999:
                ps.append(np.log(dz / (zt - zre)) / np.log(r))
    if not ps:
        return 2.0, "no usable envelope rows: parabolic crown (assumed)"
    p = float(np.clip(np.median(ps), 1.5, 6.0))
    return p, f"median of {len(ps)} end-view envelope rows between the roof edge and the top (front + rear views)"


# kind -> (operation, view it is built from, material or default depth). Each region is built from the view that sees it
# face-on; a kind accepted in other views too is evidence only there (listed, not built twice).
REGION_RULES = {
    "side_window": ("imprint", "side", "glass"), "windscreen": ("imprint", "top", "glass"),
    "rear_window": ("imprint", "top", "glass"), "door": ("imprint", "side", "panel"),
    "headlight": ("imprint", "front", "light"), "tail_light": ("imprint", "rear", "light"),
    "air_intake": ("pocket", "side", 60.0), "grille_mesh": ("pocket", "top", 25.0), "louvre": ("pocket", "top", 25.0),
    "licence_plate": ("pocket", "rear", 15.0),
}


def region_to_model(F, view, poly_px):
    P = np.asarray(poly_px, float)
    if view == "side":
        a, b = side_xz(F, P[:, 0], P[:, 1])
    elif view == "top":
        a, b = top_xy(F, P[:, 0], P[:, 1])
    else:
        a, b = end_yz(F, view, P[:, 0], P[:, 1])
    return np.c_[a, b]
