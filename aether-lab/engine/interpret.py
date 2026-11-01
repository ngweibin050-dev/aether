"""Engineer's interpretation: a drawing READ (part types, boxes, axis ends, teeth) -> clean standard parts.

Tracing the pixels of a dense or hand-drawn sheet (vision.blueprint_parts) copies its hatching, labels and
overlaps into the solids, and the result is a blob. An engineer reading such a sheet does not copy strokes: they
recognise "a gear about this big here, a lever from this pivot to that one, a cylinder along this axis" and draw
clean standard parts. This module does the same with Muse Spark's reading of the drawing, then hands the parts to
rebuild.rebuild (gear module and meshing, layers, machine depth, hubs, housing) like traced parts.

Per part, from its box (and, for long parts, the two axis ends Spark gives):
  gear              -> involute gear, tip radius = half the box's smaller side
  wheel/pulley/...  -> rim + hub + 5 spokes
  link/arm/lever    -> forged link: a stadium between the two ends with a bore at each end
  piston/cylinder   -> barrel along its axis (rebuild makes the tube)
  shaft/rod/spring  -> along its axis
  frame/housing     -> rounded rectangle (the housing walls follow it); plate/base -> rectangle
Every size is the box measured at the drawing's scale; everything else is a stated assumption.
"""
import numpy as np


def _circle(cx, cy, r, n=48, cw=False):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    if cw:
        t = t[::-1]
    return [[float(cx + r * np.cos(a)), float(cy + r * np.sin(a))] for a in t]


def _round_rect(w, h, r, n=8):
    r = min(r, w / 2, h / 2)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, -h / 2 + r, -np.pi / 2), (w / 2 - r, h / 2 - r, 0),
                       (-w / 2 + r, h / 2 - r, np.pi / 2), (-w / 2 + r, -h / 2 + r, np.pi)):
        for a in np.linspace(a0, a0 + np.pi / 2, n):
            pts.append([float(cx + r * np.cos(a)), float(cy + r * np.sin(a))])
    return pts


def _stadium(L, w, angle_deg, n=16):
    """Link outline: two half circles of radius w/2 whose centres are L apart, rotated; bores at both ends."""
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    R = w / 2
    h = max(L / 2, 0.0)
    pts = []
    for t in np.linspace(-np.pi / 2, np.pi / 2, n):
        pts.append([h + R * np.cos(t), R * np.sin(t)])
    for t in np.linspace(np.pi / 2, 3 * np.pi / 2, n):
        pts.append([-h + R * np.cos(t), R * np.sin(t)])
    rot = lambda P: [[float(x * c - y * s), float(x * s + y * c)] for x, y in P]
    holes = [rot(_circle(x, 0, 0.42 * R, 24, cw=True)) for x in (-h, h)]
    return {"outer": rot(pts), "holes": holes}


def _rotated_rect(L, w, angle_deg):
    """The outline of a cylinder of length L and diameter w lying at angle_deg in the drawing plane: what rebuild
    actually builds for a shaft, piston or spring (not the reader's upright box around it)."""
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    return [[float(x * c - y * s), float(x * s + y * c)] for x, y in ((L / 2, -w / 2), (L / 2, w / 2), (-L / 2, w / 2), (-L / 2, -w / 2))]


def _disc(r, bore=0.2):
    """A wheel or pulley as drawn in a side view: a disc with its bore. Spokes are not invented: a reading gives the
    wheel's box, not its spokes (spokes drawn from a template put outlines where the drawing has none)."""
    return {"outer": _circle(0, 0, r, 72), "holes": [_circle(0, 0, bore * r, 24, cw=True)]}


def fit_box_to_ink(box, ink, reach=None, min_cover=0.5):
    """Move each side of an upright box (px) onto the drawn line next to it, if there is one: the reader's boxes are
    rough, the drawing's lines are exact. A side moves by up to `reach` px to the offset where the most of that side
    lies on ink, and only if at least min_cover of it does (a real line, not hatching crossing it); otherwise it stays.
    Returns (box, sides moved)."""
    H, W = ink.shape
    x1, y1, x2, y2 = (float(v) for v in box)
    w, h = x2 - x1, y2 - y1
    reach = reach or int(np.clip(0.12 * min(w, h), 3, 14))
    out, moved = [x1, y1, x2, y2], 0

    def cover(vertical, at, lo, hi):
        at = int(round(at))
        lo, hi = int(lo + 0.1 * (hi - lo)), int(hi - 0.1 * (hi - lo))          # the middle 80 %: corners round off
        if vertical:
            if not 0 <= at < W or hi <= lo:
                return 0.0
            return float(ink[max(lo, 0):min(hi, H), at].mean()) if min(hi, H) > max(lo, 0) else 0.0
        if not 0 <= at < H or hi <= lo:
            return 0.0
        return float(ink[at, max(lo, 0):min(hi, W)].mean()) if min(hi, W) > max(lo, 0) else 0.0
    for i, (vertical, lo, hi) in enumerate(((True, y1, y2), (False, x1, x2), (True, y1, y2), (False, x1, x2))):
        best = max(range(-reach, reach + 1), key=lambda d: (cover(vertical, out[i] + d, lo, hi), -abs(d)))
        if cover(vertical, out[i] + best, lo, hi) >= min_cover and best:
            out[i] += best
            moved += 1
    if out[2] - out[0] < 0.5 * w or out[3] - out[1] < 0.5 * h:                    # never collapse a part
        return [x1, y1, x2, y2], 0
    return out, moved


def fit_width_to_ink(a, b, ink, w0, min_cover=0.45):
    """Width (px) of a long part between axis ends a, b (px) from the drawing: the half-width d at which BOTH lines
    parallel to the axis at +d and -d lie on ink over the middle 70 % of the length (the part's two drawn sides).
    Searched from 0.4 to 1.8 x the estimated width w0; None if no such pair of lines exists (keep the estimate)."""
    H, W = ink.shape
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = float(np.linalg.norm(b - a))
    if L < 8:
        return None
    u = (b - a) / L
    nrm = np.array([-u[1], u[0]])
    t = np.linspace(0.15, 0.85, max(12, int(0.7 * L / 2)))
    axis = a[None] + t[:, None] * (b - a)[None]

    def cov(off):
        P = np.round(axis + off * nrm).astype(int)
        ok = (P[:, 0] >= 0) & (P[:, 0] < W) & (P[:, 1] >= 0) & (P[:, 1] < H)
        if ok.mean() < 0.8:
            return 0.0
        hit = np.zeros(len(P), bool)
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):        # 1 px tolerance for a slanted line
            Q = P + [dx, dy]
            okq = ok & (Q[:, 0] >= 0) & (Q[:, 0] < W) & (Q[:, 1] >= 0) & (Q[:, 1] < H)
            hit[okq] |= ink[Q[okq, 1], Q[okq, 0]]
        return float(hit.mean())
    best = None
    for d in np.arange(max(2.0, 0.2 * w0), 0.9 * w0 + 1, 1.0):
        c = min(cov(d), cov(-d))
        if c >= min_cover and (best is None or c > best[0] + 0.02):
            best = (c, d)
    return None if best is None else 2 * best[1]


def _spoked(r, spokes=5):
    hub, rim = 0.28 * r, 0.80 * r
    holes = []
    gap = 2 * np.pi / spokes
    half_spoke = np.arctan2(0.09 * r, rim)            # spoke width ~0.18 r
    for k in range(spokes):
        a0, a1 = k * gap + half_spoke + np.pi / 2, (k + 1) * gap - half_spoke + np.pi / 2
        inner = [[hub * np.cos(t), hub * np.sin(t)] for t in np.linspace(a0, a1, 6)]
        outer = [[rim * np.cos(t), rim * np.sin(t)] for t in np.linspace(a1, a0, 12)]
        holes.append([[float(x), float(y)] for x, y in (inner + outer)][::-1])
    return {"outer": _circle(0, 0, r, 72), "holes": holes}


TYPE = {"gear": "gear", "gears": "gear", "pinion": "gear", "sprocket": "gear", "cog": "gear",
        "wheel": "wheel", "pulley": "wheel", "flywheel": "wheel", "disc": "wheel", "disk": "wheel", "cam": "wheel",
        "link": "link", "lever": "link", "arm": "link", "crank": "link", "rocker": "link", "beam": "link", "bar": "link",
        "piston": "piston", "cylinder": "piston", "ram": "piston", "plunger": "piston",
        "shaft": "shaft", "rod": "shaft", "axle": "shaft", "spindle": "shaft", "screw": "shaft",
        "pin": "pin", "bolt": "pin",
        "spring": "spring",
        "frame": "frame", "housing": "frame", "casing": "frame", "body": "frame", "chassis": "frame", "support": "frame",
        "plate": "plate", "base": "plate", "bracket": "plate"}


def kind(t, label=""):
    for w in (str(t).lower().split() + str(label).lower().split()):
        w = w.strip(",.;:()")
        if w in TYPE:
            return TYPE[w]
    return "plate"


FIT_KINDS = ("plate", "frame", "shaft", "piston")      # drawn as upright rectangles when no axis ends are read
EDGE_ON = 1.15                                         # box side ratio from which an unmeasured round part is seen edge-on


def parts_from_read(read_parts, W, H, mm_per_px, ink=None):
    """read_parts: Spark's parts with box [x1, y1, x2, y2] in px (image y down), optional ends [[x, y], [x, y]] px
    and teeth. Returns parts in the format of vision.blueprint_parts (mm, y up, centred on the image).
    ink (bool array, the drawing's ink at W x H): upright rectangular parts get their sides moved onto the drawn lines
    (fit_box_to_ink); round parts were already snapped to measured circles."""
    out = []
    for n, it in enumerate(read_parts, 1):
        bx = it.get("box")
        if not bx:
            continue
        x1, y1, x2, y2 = (float(v) for v in bx)
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        k = kind(it.get("type", ""), it.get("label", ""))
        # a gear or wheel no measured circle confirms, in a box that is not square, is seen edge-on (a side view or a
        # section): its outline is that rectangle, and its axis lies in the drawing plane along the box's short side
        edge_on = k in ("gear", "wheel") and not it.get("measured") and \
            max(x2 - x1, y2 - y1) >= EDGE_ON * min(x2 - x1, y2 - y1)
        fitted = 0
        if ink is not None and (k in FIT_KINDS or edge_on) and not it.get("ends") and x2 - x1 > 4 and y2 - y1 > 4:
            (x1, y1, x2, y2), fitted = fit_box_to_ink([x1, y1, x2, y2], ink)
        w, h = (x2 - x1) * mm_per_px, (y2 - y1) * mm_per_px
        if w < 2 or h < 2:
            continue
        cx, cy = ((x1 + x2) / 2 - W / 2) * mm_per_px, (H / 2 - (y1 + y2) / 2) * mm_per_px
        ends = it.get("ends")
        if isinstance(ends, list) and len(ends) == 2 and all(isinstance(e, list) and len(e) == 2 for e in ends):
            (ax, ay), (bx_, by) = [((float(e[0]) - W / 2) * mm_per_px, (H / 2 - float(e[1])) * mm_per_px) for e in ends]
            L = float(np.hypot(bx_ - ax, by - ay))
            ang = float(np.degrees(np.arctan2(by - ay, bx_ - ax)))
            cx, cy = (ax + bx_) / 2, (ay + by) / 2
            # thickness across the axis: the box area spread along the axis, within sane limits ...
            thick = float(np.clip(w * h / max(L, 1e-6) * 0.35, 0.06 * L, 0.35 * L)) if L > 0 else min(w, h)
            ends_src = "axis ends read by Muse Spark"
            thick_est, width_src = thick, "estimated from the box"
            # ... or, better, the distance between the part's two drawn sides along that axis
            if ink is not None and k in ("link", "shaft", "piston", "spring") and L > 0:
                wpx = fit_width_to_ink(ends[0], ends[1], ink, thick / mm_per_px)
                if wpx:
                    thick = float(wpx * mm_per_px)
                    width_src = "two drawn sides"
                    fitted += 2
        else:
            L, ang = max(w, h), (0.0 if w >= h else 90.0)
            thick = min(w, h)
            thick_est, width_src = thick, "the box's short side"
            ends_src = "axis assumed along the box's long side"
        p = {"n": n, "label": str(it.get("label") or k), "kind": k, "confidence": it.get("confidence", 1.0),
             "centre_mm": [round(cx, 2), round(cy, 2)], "length_mm": round(max(L, thick), 1),
             "width_mm": round(min(L, thick) if L else thick, 1), "angle_deg": round(ang, 1),
             "elongation": round(max(L, thick) / max(min(L, thick), 1e-6), 2), "interpreted": True, "axis_source": ends_src,
             "width_source": width_src, "width_estimate_mm": round(min(L, thick_est) if L else thick_est, 1)}
        for f in ("measured", "read_from"):
            if it.get(f):
                p[f] = it[f]
        if fitted:
            p["fitted_to_ink"] = f"{fitted} side(s) moved onto the drawn lines"
        if edge_on:
            dia, face = max(w, h), min(w, h)
            p.update({"edge_on": True, "radius_mm": round(dia / 2, 2), "tip_radius_mm": round(dia / 2, 2),
                      "face_mm": round(face, 2), "axis_deg": 0.0 if w < h else 90.0, "length_mm": round(dia, 1),
                      "width_mm": round(face, 1), "angle_deg": 0.0, "elongation": round(dia / max(face, 1e-6), 2),
                      "view_note": "seen edge-on: no measured circle and a non-square box; axis in the drawing plane"})
            p["_poly"] = [{"outer": _round_rect(w, h, 0.0), "holes": []}]
        elif k in ("gear", "wheel", "pin") or (k in ("plate", "shaft") and p["elongation"] < 1.3):
            r = min(w, h) / 2
            p.update({"radius_mm": round(r, 2), "tip_radius_mm": round(r, 2), "length_mm": round(2 * r, 1),
                      "width_mm": round(2 * r, 1), "elongation": 1.0})
            if isinstance(it.get("teeth"), (int, float)):
                p["teeth_seen"] = int(it["teeth"])
            p["_poly"] = [_disc(r)] if k == "wheel" else [{"outer": _circle(0, 0, r), "holes": []}]
        elif k == "link":
            p["_poly"] = [_stadium(max(L - thick, 0.0), thick, ang)]
        elif k == "frame":
            p["_poly"] = [{"outer": _round_rect(w, h, 0.08 * min(w, h)), "holes": []}]
            p.update({"length_mm": round(max(w, h), 1), "width_mm": round(min(w, h), 1), "angle_deg": 0.0})
        elif k == "plate":
            p["_poly"] = [{"outer": _round_rect(w, h, 0.05 * min(w, h)), "holes": []}]
            p.update({"length_mm": round(max(w, h), 1), "width_mm": round(min(w, h), 1)})
        else:                                          # piston, shaft, spring: rebuild builds L x width along the angle
            p["_poly"] = [{"outer": _rotated_rect(p["length_mm"], p["width_mm"], p["angle_deg"]), "holes": []}]
        out.append(p)
    return out


def drawing_check(im, silhouette, mm_per_px):
    """Put what was BUILT back on the drawing, so a person can judge it at a glance instead of trusting it.
    im: the drawing (PIL); silhouette: rebuild's report["_silhouette"] (1 mm grid, drawing frame, y up).
    Returns (check, overlay image): the share of the drawing's lines that lie on a built part, and the drawing
    faded with every built part in cyan and every frame body in amber. Lines nothing was built for stay dark:
    those are parts the model left out (or text, dimensions and hatching, which are not parts)."""
    from PIL import Image
    W, H = im.size
    m = int(silhouette["margin_mm"])
    def to_px(mask):
        crop = mask[m:mask.shape[0] - m, m:mask.shape[1] - m]
        return np.asarray(Image.fromarray(crop.astype(np.uint8) * 255).resize((W, H), Image.NEAREST)) > 127
    parts, frames = to_px(silhouette["parts"]), to_px(silhouette["frames"])
    g = np.asarray(im.convert("L"), float)
    hist = np.bincount(g.astype(int).ravel(), minlength=256).astype(float)
    p = hist / hist.sum()
    w, mu = np.cumsum(p), np.cumsum(p * np.arange(256))
    ink = g <= int(np.argmax((mu[-1] * w - mu) ** 2 / np.maximum(w * (1 - w), 1e-12)))
    near = parts | frames
    for _ in range(3):                                   # a line just on a part's edge counts as that part's line
        n2 = near.copy()
        n2[1:, :] |= near[:-1, :]; n2[:-1, :] |= near[1:, :]; n2[:, 1:] |= near[:, :-1]; n2[:, :-1] |= near[:, 1:]
        near = n2
    # only the machine's own area counts: title blocks, watermarks and banners outside it are not parts
    ys, xs = np.nonzero(near)
    if len(ys):
        py, px = int(0.06 * H), int(0.06 * W)
        area = np.zeros_like(ink)
        area[max(0, ys.min() - py):ys.max() + py, max(0, xs.min() - px):xs.max() + px] = True
        ink &= area
    covered = float((ink & near).sum() / max(ink.sum(), 1))
    edge = lambda m: m & ~(np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1))
    def thick(m, n=1):
        for _ in range(n):
            m = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
        return m
    # precision: the other direction. Recall (above) counts drawn lines that lie on something built, and one big
    # housing covering the sheet would score high. Precision counts the built outlines (front view, 1 px edges) that
    # lie within 2 px (square) of any ink of the drawing: an outline drawn where the drawing has no line is invented.
    # Hatching and text count as ink here too, so precision is an upper bound where they are dense.
    ink_all = g <= int(np.argmax((mu[-1] * w - mu) ** 2 / np.maximum(w * (1 - w), 1e-12)))
    near_ink = ink_all.copy()
    for _ in range(2):
        n2 = near_ink.copy()
        n2[1:, :] |= near_ink[:-1, :]; n2[:-1, :] |= near_ink[1:, :]; n2[:, 1:] |= near_ink[:, :-1]; n2[:, :-1] |= near_ink[:, 1:]
        n2[1:, 1:] |= near_ink[:-1, :-1]; n2[:-1, :-1] |= near_ink[1:, 1:]; n2[1:, :-1] |= near_ink[:-1, 1:]; n2[:-1, 1:] |= near_ink[1:, :-1]
        near_ink = n2

    def outline_px(rings):
        """Built outlines drawn 1 px wide at the drawing's own resolution, from the rebuild's polygons (drawing mm,
        origin at the image centre, y up), so the 1 mm grid of the silhouette masks adds no stair steps."""
        from PIL import ImageDraw
        o = Image.new("1", (W, H))
        d = ImageDraw.Draw(o)
        for ring in rings:
            ring = ring["ring"] if isinstance(ring, dict) else ring
            pts = [(x / mm_per_px + W / 2, H / 2 - y / mm_per_px) for x, y in ring]
            if len(pts) > 1:
                d.line(pts + [pts[0]], fill=1, width=1)
        return np.asarray(o)

    def prec(e):
        e = e.copy()
        e[0, :] = e[-1, :] = e[:, 0] = e[:, -1] = False              # the image border is not an outline
        n = int(e.sum())
        return (round(100 * float((e & near_ink).sum()) / n, 1) if n else None), n
    rings = silhouette.get("rings_mm")
    # OFFICIAL precision: the OUTER edge of the built silhouette (all parts merged; frames separately), as the check
    # image draws it. Each part's own outline (rings) also counts edges lying inside other parts, which on a dense
    # section land on some line easily (B run 7: 61 % of those pixels, 74 % on ink, vs 61 % on the outer edge), so it
    # read 69 % where the outer edge reads 56 %. The stricter outer edge is reported; the per-kind numbers below use
    # each part's own outline and are a diagnostic only.
    p_parts, n_parts = prec(edge(parts))
    p_frames, n_frames = prec(edge(frames))
    by_kind = {}                                   # which kinds of part are drawn where the drawing has no line
    for k in sorted({r["kind"] for r in (rings or {}).get("parts", []) + (rings or {}).get("frames", []) if isinstance(r, dict)}):
        e = outline_px([r for r in rings["parts"] + rings["frames"] if isinstance(r, dict) and r["kind"] == k]).copy()
        e[0, :] = e[-1, :] = e[:, 0] = e[:, -1] = False
        n = int(e.sum())
        if n:
            on = int((e & near_ink).sum())
            by_kind[k] = {"pct": round(100 * on / n, 1), "on_ink": on, "px": n}
    a = 255 - 0.5 * (255 - np.asarray(im.convert("L"), float)[..., None].repeat(3, 2))   # faded grey drawing
    a[ink & ~near] = 0.4 * a[ink & ~near] + 0.6 * np.array([230, 60, 80])                # drawn, not built
    a[parts] = 0.78 * a[parts] + 0.22 * np.array([40, 200, 255])                         # built: light fill...
    a[frames] = 0.75 * a[frames] + 0.25 * np.array([255, 180, 60])
    a[thick(edge(frames))] = [235, 150, 30]
    a[thick(edge(parts))] = [0, 150, 230]                                                # ...and a clear outline
    check = {"drawing_lines_on_built_parts_pct": round(100 * covered, 1),
             "recall_note": "share of the drawing's lines (inside the machine's area) that lie on a built part or frame",
             "outline_on_ink_pct": {"parts": p_parts, "frames": p_frames},
             "outline_px": {"parts": n_parts, "frames": n_frames},
             "outline_on_ink_by_kind_pct": by_kind,
             "by_kind_note": "diagnostic: each part's own outline, including edges inside other parts (more lenient than the "
                             "official outer-edge precision)",
             "precision_note": "share of the OUTER edge of the built silhouette (front view; parts merged, frames separate) "
                               "within 2 px of the drawing's ink: an outline where the drawing has no line was invented. "
                               "Hatching and text count as ink, so this is an upper bound",
             "note": "Blue outline = built part, amber = frame body, red = lines in the drawing that no built part covers "
                     "(missed parts, or text / dimensions / hatching). Front view only: depth is not checked here."}
    return check, Image.fromarray(a.clip(0, 255).astype(np.uint8))


ROUND = ("gear", "wheel", "pin")


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    A = (a[2] - a[0]) * (a[3] - a[1])
    B = (b[2] - b[0]) * (b[3] - b[1])
    return i / max(A + B - i, 1e-9), i / max(min(A, B), 1e-9), min(A, B) / max(A, B, 1e-9)


def merge_reads(reads, W, H):
    """Several readings of one sheet (the whole sheet + close-up tiles), boxes already in full-image px -> one parts
    list without duplicates. reads: [(parts, source)], whole sheet first. A part is the same as one already kept when
    the boxes overlap (IoU >= 0.45, or one sits inside the other and they are of similar size) and they are the same
    kind; the kept one takes over ends / teeth it lacked. Big parts trust the whole-sheet reading, small ones the
    close-up."""
    kept = []
    big = 0.06 * W * H
    for parts, src in reads:
        for it in parts:
            b = [float(v) for v in it["box"]]
            k = kind(it.get("type", ""), it.get("label", ""))
            area = (b[2] - b[0]) * (b[3] - b[1])
            dup = None
            for q in kept:
                if q["_k"] != k and not ({q["_k"], k} <= {"plate", "frame"}):
                    continue
                iou, inside, ratio = _iou(b, q["box"])
                if iou >= 0.45 or (inside >= 0.8 and ratio >= 0.45):
                    dup = q
                    break
            if dup is None:
                kept.append({**it, "box": b, "_k": k, "read_from": src})
                continue
            if src != "whole sheet" and area < big and dup["read_from"] == "whole sheet":
                for f in ("ends", "teeth"):         # the close-up is the better reading of a small part
                    if f not in it and f in dup:
                        it = {**it, f: dup[f]}
                dup.clear()
                dup.update({**it, "box": b, "_k": k, "read_from": src})
            else:
                for f in ("ends", "teeth"):
                    if f in it and f not in dup:
                        dup[f] = it[f]
    for q in kept:
        q.pop("_k", None)
    return kept


def _confirmed_by_circle(it, circles):
    """A round part (gear, wheel, pin) whose box sits on a circle measured on the ink, of about its size."""
    if kind(it.get("type", ""), it.get("label", "")) not in ROUND:
        return False
    x1, y1, x2, y2 = it["box"]
    cx, cy, r = (x1 + x2) / 2, (y1 + y2) / 2, min(x2 - x1, y2 - y1) / 2
    return any(np.hypot(c["cx"] - cx, c["cy"] - cy) < 0.35 * max(r, c["r"]) + 2 and 0.7 <= c["r"] / max(r, 1e-6) <= 1.4
               for c in circles)


SAME_THING = ({"plate", "frame"}, {"gear", "wheel"})    # kinds two readings may use for one drawn object


def _confirmed_by_lines(it, ink, min_sides=3, min_cover=0.5):
    """A part whose box has at least min_sides of its 4 sides lying on drawn lines (within a few px): the drawing
    itself confirms it is there, as a measured circle does for a round part."""
    if ink is None or kind(it.get("type", ""), it.get("label", "")) in ROUND:
        return False
    x1, y1, x2, y2 = (float(v) for v in it["box"])
    if x2 - x1 < 6 or y2 - y1 < 6:
        return False
    H, W = ink.shape
    reach = int(np.clip(0.12 * min(x2 - x1, y2 - y1), 3, 14))

    def side(vertical, at, lo, hi):
        lo, hi = int(lo + 0.1 * (hi - lo)), int(hi - 0.1 * (hi - lo))
        best = 0.0
        for d in range(-reach, reach + 1):
            c = int(round(at + d))
            if vertical and 0 <= c < W and hi > lo:
                best = max(best, float(ink[max(lo, 0):min(hi, H), c].mean()) if min(hi, H) > max(lo, 0) else 0.0)
            elif not vertical and 0 <= c < H and hi > lo:
                best = max(best, float(ink[c, max(lo, 0):min(hi, W)].mean()) if min(hi, W) > max(lo, 0) else 0.0)
        return best
    covers = [side(True, x1, y1, y2), side(False, y1, x1, x2), side(True, x2, y1, y2), side(False, y2, x1, x2)]
    return sum(c >= min_cover for c in covers) >= min_sides


def agree(a, b, circles, iou_min=0.4, ink=None):
    """Two independent readings of the same image -> the parts both saw (box IoU >= iou_min, same kind; the box is
    the mean of the two, ends / teeth taken from whichever has them), plus the parts only one saw IF the drawing
    confirms them by measurement: a measured circle for a round part, drawn lines on at least 3 sides of its box for
    any other part (ink given). Returns (kept, dropped): dropped = [{label, type, box, why}] for the log. A reading
    that varies from run to run (26 parts one run, 13 the next) is cut down to what is stable or measured."""
    a, b = list(a or []), list(b or [])
    pairs = []
    for i, p in enumerate(a):
        for j, q in enumerate(b):
            kp, kq = kind(p.get("type", ""), p.get("label", "")), kind(q.get("type", ""), q.get("label", ""))
            # the same object under two names is agreement, not disagreement: on the press (D, run 7) one reading said
            # "54 wheel" and the other "55 large gear" for one box (IoU 0.82), and both were dropped
            if kp != kq and not any({kp, kq} <= s for s in SAME_THING):
                continue
            iou = _iou(p["box"], q["box"])[0]
            if iou >= iou_min:
                pairs.append((iou, i, j))
    used_a, used_b, kept = set(), set(), []
    for iou, i, j in sorted(pairs, reverse=True):
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        p, q = a[i], b[j]
        m = {**q, **p, "box": [(u + v) / 2 for u, v in zip(p["box"], q["box"])], "agreed": f"both readings (box IoU {iou:.2f})"}
        if kind(p.get("type", ""), "") != kind(q.get("type", ""), "") and "gear" in (p.get("type"), q.get("type")):
            m["type"] = "gear"                       # a gear and a wheel for one object: the reading that saw teeth wins
        for f in ("ends", "teeth"):
            if f not in p and f in q:
                m[f] = q[f]
        kept.append(m)
    dropped = []
    for src, rest in (("first", [p for i, p in enumerate(a) if i not in used_a]),
                      ("second", [q for j, q in enumerate(b) if j not in used_b])):
        for it in rest:
            dup = any(_iou(it["box"], k["box"])[0] >= iou_min for k in kept)
            if not dup and _confirmed_by_circle(it, circles):
                kept.append({**it, "agreed": "one reading + a circle measured on the drawing"})
            elif not dup and _confirmed_by_lines(it, ink):
                kept.append({**it, "agreed": "one reading + drawn lines on 3 or 4 sides of its box"})
            else:
                dropped.append({"label": it.get("label"), "type": it.get("type"), "box": [round(float(v), 1) for v in it["box"]],
                                "why": f"only the {src} reading saw it and no measured circle or drawn outline confirms it"})
    return kept, dropped


def snap_circles(parts, circles, W, H, max_added=60):
    """Measured circles (engine/circles.py, px) make the round parts exact and add the ones the reading missed.
    - a round part (gear, wheel, pulley, pin) read near a measured circle of about its size takes the circle's
      centre and radius (an engineer measures a bore with a compass, not by eye);
    - a measured circle inside a round part already kept is its hub or bore, not a new part;
    - any other measured circle is a part the reading missed: a disc / wheel if large, else a pivot pin / boss.
    Returns (parts, {"snapped": n, "added": n})."""
    S = max(W, H)
    used = set()
    snapped = 0
    for it in parts:
        if kind(it.get("type", ""), it.get("label", "")) not in ROUND:
            continue
        x1, y1, x2, y2 = it["box"]
        cx, cy, r = (x1 + x2) / 2, (y1 + y2) / 2, min(x2 - x1, y2 - y1) / 2
        best = None
        for i, c in enumerate(circles):
            if i in used:
                continue
            d = np.hypot(c["cx"] - cx, c["cy"] - cy)
            ratio = c["r"] / max(r, 1e-6)
            if d < 0.35 * max(r, c["r"]) + 2 and 0.7 <= ratio <= 1.4:
                score = d / max(r, 1) + abs(np.log(ratio))
                if best is None or score < best[0]:
                    best = (score, i)
        if best:
            c = circles[best[1]]
            used.add(best[1])
            it["box"] = [c["cx"] - c["r"], c["cy"] - c["r"], c["cx"] + c["r"], c["cy"] + c["r"]]
            it["measured"] = "centre and radius measured on the drawing"
            snapped += 1
    rounds = [it for it in parts if kind(it.get("type", ""), it.get("label", "")) in ROUND]
    from engine import circles as C
    added = 0
    for i, c in enumerate(circles):
        if i in used or added >= max_added:
            continue
        host = False
        for it in rounds:
            x1, y1, x2, y2 = it["box"]
            R = min(x2 - x1, y2 - y1) / 2
            if np.hypot(c["cx"] - (x1 + x2) / 2, c["cy"] - (y1 + y2) / 2) < 0.3 * R + 2 and c["r"] < R:
                host = True
                break
        if host:
            continue
        new = C.as_read_parts([c], W, H)[0]
        if new["type"] == "wheel" and c["r"] < 0.035 * S:
            new.update({"type": "pin", "label": "pivot boss"})
        new["measured"] = "found and measured on the drawing (the reading had missed it)"
        parts.append(new)
        rounds.append(new)
        added += 1
    return parts, {"snapped": snapped, "added": added}
