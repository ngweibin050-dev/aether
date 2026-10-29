"""Geometric laws from the AETHER theory, applied to a scene (all lengths mm, panel at z = 0).

H1 Window Law (Physics Record 8.1): in empty air you see a point P only if the line from your
eye through P, extended back, hits the hologram panel. Light can only come from the panel.

Hand-shadow rule (Physics v13 s.4): light for P travels panel -> P -> pupil. A hand between the
panel and P (behind P, seen from the eye) blocks P's light although P should be in front of the
hand: a depth conflict no software can fix. A hand between P and the eye blocks it naturally.
"""
import numpy as np


def panel_hit(points, eye):
    """Where the line eye -> P meets the panel plane z = 0. Returns (N, 2) and validity mask."""
    P = np.asarray(points, float)
    E = np.asarray(eye, float)
    dz = E[2] - P[:, 2]
    ok = dz > 1e-9                                   # point must be between eye and far side
    t = np.where(ok, E[2] / np.where(ok, dz, 1), 0)  # E + t (P - E) reaches z = 0
    hit = E[:2] + t[:, None] * (P[:, :2] - E[:2])
    return hit, ok


def window_mask(points, eye, panel_w, panel_h, center=(0.0, 0.0)):
    """True where the Window Law lets the eye see P through a panel_w x panel_h panel."""
    hit, ok = panel_hit(points, eye)
    cx, cy = center
    inside = (np.abs(hit[:, 0] - cx) <= panel_w / 2) & (np.abs(hit[:, 1] - cy) <= panel_h / 2)
    return ok & inside


def visible_from(points, eye, res=None):
    """Hidden-surface removal by an angular z-buffer seen from `eye`.

    Points are binned by viewing direction; in each bin only points within one bin-width of the
    nearest depth survive. Bin size adapts to the point density (~2 points per bin).
    """
    P = np.asarray(points, float)
    if len(P) == 0:
        return np.zeros(0, bool)
    E = np.asarray(eye, float)
    d = P - E
    depth = np.linalg.norm(d, axis=1)
    u = d[:, 0] / -d[:, 2]
    v = d[:, 1] / -d[:, 2]
    if res is None:
        span = max(np.ptp(u), np.ptp(v), 1e-9)
        res = span / np.sqrt(len(P) / 2.0)
    iu = np.floor((u - u.min()) / res).astype(np.int64)
    iv = np.floor((v - v.min()) / res).astype(np.int64)
    key = iu * (iv.max() + 1) + iv
    nearest = np.full(key.max() + 1, np.inf)
    np.minimum.at(nearest, key, depth)
    tol = 1.5 * res * depth          # one bin width, in mm at that depth
    return depth <= nearest[key] + tol


def _seg_sphere(a, b, c, r):
    """Does segment a->b (arrays (N,3)) pass within r of centre c?"""
    ab = b - a
    t = np.clip(np.einsum("ij,ij->i", c - a, ab) / np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-12), 0, 1)
    closest = a + t[:, None] * ab
    return np.linalg.norm(closest - c, axis=1) < r


def hand_check(points, eye, hand_points, hand_radius=9.0):
    """Classify object points against a tracked hand (list of joint centres, mm).

    Returns masks: natural (hand in front of P: correct occlusion) and conflict
    (hand behind P blocks its light: P vanishes although it should hide the hand).
    """
    P = np.asarray(points, float)
    E = np.asarray(eye, float)
    hit, ok = panel_hit(P, E)
    src = np.c_[hit, np.zeros(len(P))]
    eyes = np.repeat(E[None], len(P), 0)
    natural = np.zeros(len(P), bool)
    conflict = np.zeros(len(P), bool)
    for h in np.asarray(hand_points, float).reshape(-1, 3):
        hh = np.repeat(h[None], len(P), 0)
        natural |= _seg_sphere(P, eyes, hh, hand_radius)
        conflict |= _seg_sphere(src, P, hh, hand_radius)
    conflict &= ok & ~natural
    return natural, conflict
