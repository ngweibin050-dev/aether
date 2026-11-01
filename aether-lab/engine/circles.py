"""Find every round part a drawing shows, by measurement: gears, wheels, pulleys, bearings, pivots, pins.

A reader (Muse Spark) lists what it recognises, but on a dense sheet it names the big parts and skips the many small
round ones, and its boxes are rough. Round parts are the one thing a drawing states exactly: an engineer finds each
circle, its centre and its radius, with a compass. This module does that on the ink:

- gradient Hough: every edge pixel votes for centres along its gradient (both sides, a thin line has two edges), for
  each radius; peaks are candidate circles;
- each candidate is checked on the ink itself: the share of a ring at that radius that is drawn (support) must be
  high, so arcs of hatching or text do not pass;
- concentric circles (a bore, a hub, a rim, a pitch circle) are ONE part: the outermost ring is the part, the inner
  rings are its bore and hub;
- teeth: the ink just inside the outer ring, sampled around it, alternates regularly for a gear; its dominant
  frequency is the tooth count.

Numpy + Pillow only. Everything returned is measured on the drawing; nothing is guessed."""
import numpy as np
from PIL import Image


def ink_mask(im):
    g = np.asarray(im.convert("L"), float)
    hist = np.bincount(g.astype(int).ravel(), minlength=256).astype(float)
    p = hist / hist.sum()
    w, mu = np.cumsum(p), np.cumsum(p * np.arange(256))
    t = int(np.argmax((mu[-1] * w - mu) ** 2 / np.maximum(w * (1 - w), 1e-12)))
    return g <= t, g


def _blur(a, r=1):
    for ax in (0, 1):
        a = sum(np.roll(a, k, ax) for k in range(-r, r + 1)) / (2 * r + 1)
    return a


def ring_support(ink, cx, cy, r, tol=1.5, n=None):
    """Share of the ring (cx, cy, r) that has ink within +-tol px, and the per-angle hits."""
    n = n or max(48, int(2 * np.pi * r / 1.5))
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    H, W = ink.shape
    hit = np.zeros(n, bool)
    for dr in np.arange(-tol, tol + 0.01, 0.75):
        x = np.round(cx + (r + dr) * np.cos(t)).astype(int)
        y = np.round(cy + (r + dr) * np.sin(t)).astype(int)
        ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
        hit[ok] |= ink[y[ok], x[ok]]
    return float(hit.mean()), hit


def count_teeth(ink, cx, cy, r):
    """Tooth count of a gear whose tip circle is r: ink along a ring slightly inside the tip alternates once per
    tooth. Returns (teeth or None, strength 0-1)."""
    best = (None, 0.0)
    for f in (0.93, 0.90, 0.96):
        n = 1024
        t = np.linspace(0, 2 * np.pi, n, endpoint=False)
        H, W = ink.shape
        x = np.clip(np.round(cx + f * r * np.cos(t)).astype(int), 0, W - 1)
        y = np.clip(np.round(cy + f * r * np.sin(t)).astype(int), 0, H - 1)
        s = ink[y, x].astype(float)
        if s.std() < 0.2:
            continue
        S = np.abs(np.fft.rfft(s - s.mean()))
        lo, hi = 8, min(200, int(2 * np.pi * r / 3))         # a tooth is at least ~3 px wide
        if hi <= lo:
            continue
        k = lo + int(np.argmax(S[lo:hi]))
        strength = float(S[k] / (S[1:hi].sum() + 1e-9) * 6)
        if strength > best[1]:
            best = (k, min(strength, 1.0))
    return best if best[1] > 0.6 and r >= 14 else (None, best[1])


def find(im, r_min=None, r_max=None, max_n=80, min_support=0.85, min_contrast=0.35):
    """Circles drawn on the sheet: [{cx, cy, r (px, image y down), support, rings: [r...], bore_r, teeth}]
    largest first."""
    ink, g = ink_mask(im)
    H, W = ink.shape
    r_min = r_min or max(6, int(0.006 * max(W, H)))
    r_max = r_max or int(0.22 * min(W, H))
    gs = _blur(g, 1)
    gx = np.zeros_like(gs); gy = np.zeros_like(gs)
    gx[:, 1:-1] = gs[:, 2:] - gs[:, :-2]
    gy[1:-1, :] = gs[2:, :] - gs[:-2, :]
    mag = np.hypot(gx, gy)
    ys, xs = np.nonzero(mag > max(10.0, np.percentile(mag, 75)))   # faint (light blue) lines count too
    if len(xs) > 250000:
        k = np.random.default_rng(0).choice(len(xs), 250000, replace=False)
        ys, xs = ys[k], xs[k]
    ux, uy = gx[ys, xs] / mag[ys, xs], gy[ys, xs] / mag[ys, xs]
    radii = np.unique(np.round(np.geomspace(r_min, r_max, 64)).astype(int))
    cs = 2                                                 # accumulator cell (px)
    Wa, Ha = W // cs + 1, H // cs + 1
    cands = []
    for r in radii:
        acc = np.zeros(Wa * Ha)
        for sgn in (1, -1):
            cx = np.round((xs + sgn * r * ux) / cs).astype(int)
            cy = np.round((ys + sgn * r * uy) / cs).astype(int)
            ok = (cx >= 0) & (cx < Wa) & (cy >= 0) & (cy < Ha)
            acc += np.bincount(cy[ok] * Wa + cx[ok], minlength=Wa * Ha)
        acc = _blur(acc.reshape(Ha, Wa), 1) * 9
        need = 0.9 * 2 * np.pi * r * 0.5                   # a full ring gives ~2 votes per px of circumference
        mx = acc == np.maximum.reduce([np.roll(np.roll(acc, a, 0), b, 1) for a in (-2, -1, 0, 1, 2) for b in (-2, -1, 0, 1, 2)])
        py, px = np.nonzero(mx & (acc > need))
        sc = acc[py, px] / (2 * np.pi * r)
        for i in np.argsort(-sc)[:40]:                     # the best peaks of every radius, so big rings compete
            cands.append((float(sc[i]), int(px[i]) * cs, int(py[i]) * cs, int(r)))
    cands.sort(reverse=True)
    rings, seen = [], []
    for score, x, y, r in cands:
        if any(abs(a - x) < 0.1 * max(r, c) + 2 and abs(b - y) < 0.1 * max(r, c) + 2 and abs(c - r) < 0.05 * max(r, c) + 1
               for a, b, c in seen):
            continue
        seen.append((x, y, r))
        if ring_support(ink, x, y, r, tol=1.5)[0] < 0.4:
            continue
        best = None                                        # refine the centre and radius on the ink
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for rr in (r * 0.97, r, r * 1.03):
                    s, _ = ring_support(ink, x + dx, y + dy, rr, tol=1.0)
                    if best is None or s > best[0]:
                        best = (s, x + dx, y + dy, rr)
        s, x, y, r = best
        if s < min_support:
            continue
        # a drawn ring, not a patch of hatching: the ink must stand out from just inside OR just outside it (a hub or
        # a rim may sit right next to it on the other side)
        d = max(3.0, 0.15 * r)
        side = min(ring_support(ink, x, y, r - d, tol=1.0)[0], ring_support(ink, x, y, r + d, tol=1.0)[0])
        if s - side < min_contrast:
            continue
        if any(abs(q["cx"] - x) < 0.15 * max(r, q["r"]) + 2 and abs(q["cy"] - y) < 0.15 * max(r, q["r"]) + 2 and
               abs(q["r"] - r) < 0.12 * max(r, q["r"]) + 2 for q in rings):
            continue
        rings.append({"cx": float(x), "cy": float(y), "r": float(r), "support": round(s, 2), "contrast": round(s - side, 2)})
    # concentric rings -> one part (the outermost ring), inner rings are its hub / bore
    rings.sort(key=lambda q: -q["r"])
    parts = []
    for q in rings:
        host = next((p for p in parts if np.hypot(p["cx"] - q["cx"], p["cy"] - q["cy"]) < 0.2 * p["r"] + 2 and q["r"] < p["r"]), None)
        if host:
            host["rings"].append(round(q["r"], 1))
            continue
        parts.append({**q, "rings": [round(q["r"], 1)]})
    for p in parts:
        p["bore_r"] = round(min(p["rings"]), 1) if len(p["rings"]) > 1 else None
        p["teeth"], p["teeth_strength"] = count_teeth(ink, p["cx"], p["cy"], p["r"])
        if p["teeth"] is None and len(p["rings"]) == 1:
            # a gear drawn by its tip outline: teeth show just outside a ring at the root circle
            t2, s2 = count_teeth(ink, p["cx"], p["cy"], p["r"] * 1.08)
            if t2:
                p["teeth"], p["teeth_strength"] = t2, s2
    return parts[:max_n]


def kind_of(c, scale_px):
    """What a round thing on a drawing is, from what it measurably is. scale_px = the drawing's size (max side)."""
    if c.get("teeth"):
        return "gear"
    rel = c["r"] / scale_px
    if rel < 0.018:
        return "pin"
    if len(c["rings"]) >= 3 or rel > 0.06:
        return "wheel"
    return "bearing" if c.get("bore_r") else "pin"


def as_read_parts(circles, W, H):
    """Circles in the format of Muse Spark's reading (boxes in px), so they join the same pipeline."""
    out = []
    s = max(W, H)
    for c in circles:
        k = kind_of(c, s)
        r = c["r"]
        it = {"label": {"gear": "gear", "wheel": "wheel / pulley", "bearing": "bearing boss", "pin": "pivot pin"}[k],
              "type": {"bearing": "wheel"}.get(k, k), "box": [c["cx"] - r, c["cy"] - r, c["cx"] + r, c["cy"] + r],
              "source": "measured circle", "support": c["support"]}
        if c.get("teeth"):
            it["teeth"] = int(c["teeth"])
        out.append(it)
    return out


def overlay(im, circles):
    from PIL import ImageDraw
    ov = im.convert("RGB").copy()
    d = ImageDraw.Draw(ov)
    for c in circles:
        for r in c["rings"]:
            d.ellipse([c["cx"] - r, c["cy"] - r, c["cx"] + r, c["cy"] + r], outline=(255, 120, 0), width=2)
        if c.get("teeth"):
            d.text((c["cx"] + 3, c["cy"] + 3), f"{c['teeth']}T", fill=(200, 0, 0))
    return ov
