"""Is an upload a multi-view sheet (side, top and end views of one object)? Pure numpy + Pillow, measured on the ink.

Used only to ROUTE an upload (vision.upload_kind). It finds the separate drawings on the sheet and checks that their
sizes agree as one object's views: a side view and a plan view share the object's length. It builds no geometry:
three-view sheets are reconstructed as parametric CAD by the cad/ package (OpenCascade B-rep), never as a mesh here.
"""
import io

import numpy as np
from PIL import Image


def gray(raw, max_side=1000):
    im = Image.open(io.BytesIO(raw))
    if im.mode in ("P", "LA", "RGBA"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    im = im.convert("L")
    s = max_side / max(im.size)
    if s < 1:
        im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
    return np.asarray(im, float)


def ink(g):
    hist = np.bincount(np.clip(g, 0, 255).astype(int).ravel(), minlength=256).astype(float)
    p = hist / hist.sum()
    w, mu = np.cumsum(p), np.cumsum(p * np.arange(256))
    t = int(np.argmax((mu[-1] * w - mu) ** 2 / np.maximum(w * (1 - w), 1e-12)))
    m = g <= t
    if np.concatenate([m[0], m[-1], m[:, 0], m[:, -1]]).mean() > 0.5:
        m = ~m
    return m


def _drop_long_rows(m, frac=0.35):
    """Erase straight horizontal runs longer than frac of the width (ground lines that would join two views)."""
    m = m.copy()
    W = m.shape[1]
    for y in np.nonzero(m.sum(1) >= frac * W)[0]:
        d = np.diff(np.r_[0, m[y].astype(int), 0])
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            if b - a >= frac * W:
                m[max(0, y - 1):y + 2, a:b] = False
    return m


def _label(c):
    """4-connected components of a small boolean grid -> [(cells, (y0, x0, y1, x1), touches_edge)]."""
    H, W = c.shape
    seen = np.zeros_like(c)
    out = []
    for y, x in zip(*np.nonzero(c)):
        if seen[y, x]:
            continue
        stack, cells = [(y, x)], []
        seen[y, x] = True
        while stack:
            a, b = stack.pop()
            cells.append((a, b))
            for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q, r = a + da, b + db
                if 0 <= q < H and 0 <= r < W and c[q, r] and not seen[q, r]:
                    seen[q, r] = True
                    stack.append((q, r))
        ys, xs = zip(*cells)
        edge = min(ys) == 0 or min(xs) == 0 or max(ys) == H - 1 or max(xs) == W - 1
        out.append((len(cells), (min(ys), min(xs), max(ys) + 1, max(xs) + 1), edge))
    return out


def panels(g, coarse=200):
    """Boxes (x0, y0, x1, y1, px) of the separate drawings: ink without ground lines, blurred on a coarse grid, connected
    blobs; blobs touching the sheet edge (scan noise) and blobs much smaller than the biggest (text) are dropped."""
    m = _drop_long_rows(ink(g))
    H, W = m.shape
    f = max(1, int(np.ceil(max(H, W) / coarse)))
    h, w = H // f, W // f
    c = m[:h * f, :w * f].reshape(h, f, w, f).mean((1, 3)) > 0.02
    d = c.copy()                                     # one-cell dilation closes hairline gaps inside one view
    d[1:] |= c[:-1]
    d[:-1] |= c[1:]
    d[:, 1:] |= c[:, :-1]
    d[:, :-1] |= c[:, 1:]
    comps = [x for x in _label(d) if not x[2]]
    if not comps:
        return []
    big = max(n for n, _, _ in comps)
    return [(x0 * f, y0 * f, x1 * f, y1 * f) for n, (y0, x0, y1, x1), _ in comps if n >= 0.08 * big]


def multi_view(raw, max_side=1000):
    """(is_multi_view, evidence). A multi-view sheet has >= 3 separate drawings, and two of them (a side view and a plan
    view) have the same length within 15 %; the views stacked under / beside them are the end views."""
    g = gray(raw, max_side)
    boxes = panels(g)
    ev = {"views_found": len(boxes)}
    if len(boxes) < 3:
        return False, ev
    widths = [b[2] - b[0] for b in boxes]
    best = min((abs(widths[i] - widths[j]) / max(widths[i], widths[j]), i, j)
               for i in range(len(boxes)) for j in range(i + 1, len(boxes)))
    ev["length_disagreement_pct"] = round(100 * best[0], 1)
    return best[0] <= 0.15, ev
