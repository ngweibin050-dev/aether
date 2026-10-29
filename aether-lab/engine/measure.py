"""Numbers read off a reconstruction: point sharpness, depth of best focus, speckle."""
import numpy as np


def peak_near(intensity, rc, radius=2):
    r, c = rc
    win = intensity[max(0, r - radius):r + radius + 1, max(0, c - radius):c + radius + 1]
    return float(win.max()) if win.size else 0.0


def energy_near(intensity, rc, radius=2):
    r, c = rc
    win = intensity[max(0, r - radius):r + radius + 1, max(0, c - radius):c + radius + 1]
    return float(win.sum() / intensity.sum())


def best_depth(stack, zs, rc, radius=2):
    """Depth at which the light around pixel rc is brightest (= where that point is in focus)."""
    vals = [peak_near(i, rc, radius) for i in stack]
    return float(zs[int(np.argmax(vals))]), vals


def speckle_contrast(intensity, mask=None):
    """C = std / mean over a region that should be evenly bright. 0 = smooth, 1 = full speckle."""
    v = intensity[mask] if mask is not None else intensity.ravel()
    return float(v.std() / v.mean())
