"""Synthetic side-view drawing: frame, two meshing gears (z 30 / 18, m 3), a pin, a link, a spring."""
import numpy as np
from PIL import Image, ImageDraw

from engine import geometry as g

def drawing():
    W, H = 900, 600
    S = 2.0                 # px per mm
    objs = []
    def blank(): return Image.new("1", (W, H))
    def add(label, typ, im, teeth=None):
        m = np.array(im)
        ys, xs = np.nonzero(m)
        objs.append({"mask": m, "label": label, "box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                     "confidence": 0.9, "spark": {"type": typ, **({"teeth": teeth} if teeth else {})}})
    # frame: a rectangle outline plate with a window, drawn as line art (strokes)
    im = blank(); d = ImageDraw.Draw(im)
    d.rectangle([60, 60, 840, 540], outline=1, width=6)
    add("frame", "frame", im)
    c1 = (330, 300); c2 = (330 + 3 * (30 + 18) / 2 * S, 300)
    for (c, z, lab, ph) in ((c1, 30, "gear", 0), (c2, 18, "gear", 0)):
        P, _ = g.gear_profile(z, 3, 20, ph)
        im = blank(); d = ImageDraw.Draw(im)
        d.polygon([(c[0] + x * S, c[1] - y * S) for x, y in P], fill=1)
        d.ellipse([c[0] - 10 * S, c[1] - 10 * S, c[0] + 10 * S, c[1] + 10 * S], fill=0)
        add(lab, "gear", im, teeth=z)
    im = blank(); d = ImageDraw.Draw(im); d.ellipse([c1[0] - 5 * S, c1[1] - 5 * S, c1[0] + 5 * S, c1[1] + 5 * S], fill=1)
    add("pin", "pin", im)
    im = blank(); d = ImageDraw.Draw(im); d.line([(c2[0], c2[1]), (760, 150)], fill=1, width=int(12 * S))
    add("link", "link", im)
    im = blank(); d = ImageDraw.Draw(im); d.rectangle([120, 470, 330, 500], fill=1)
    add("spring", "spring", im)
    img = Image.new("RGB", (W, H), "white")
    return img, objs, 1 / S
