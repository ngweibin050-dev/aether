"""Speckle: why laser holograms look grainy, and the sparse point-group fix (Physics v11).

Theorem S1 (v11): one coherent frame of a diffuse surface gives speckle contrast
C = std(I)/mean(I) close to the fully developed value. Averaging N independent random-phase frames
gives C ~ C1 / sqrt(N) (needs ~64 frames for 4 %).
Sparse point groups (v11, Takaki-style): split the surface into a k x k lattice of interleaved
groups; points shown in the same sub-frame sit >= k resolution cells apart, so their blur spots
barely overlap and do not interfere. k^2 sub-frames, each almost speckle-free.
"""
import numpy as np

from . import optics


def test_patch(size=1.2e-3, z=0.03, cell=None, grid=None):
    """A flat, evenly lit square: the hardest case for speckle. Points on the resolution lattice."""
    cell = cell or grid.pitch * 2
    xs = np.arange(-size / 2, size / 2 + 1e-12, cell)
    X, Y = np.meshgrid(xs, xs)
    pts = np.stack([X.ravel(), Y.ravel(), np.full(X.size, z)], 1)
    ij = np.stack([np.round((X.ravel() + size / 2) / cell), np.round((Y.ravel() + size / 2) / cell)], 1).astype(int)
    return pts, ij


def contrast(I, mask):
    v = I[mask]
    return float(v.std() / v.mean())


def compare(grid, k=3, z=0.03, size=1.0e-3, eye_dist=0.2, pupil=2e-3, seed=0):
    """Contrast seen by an eye (pupil at eye_dist) for: 1 frame, k^2 random frames, k x k sparse groups.

    The eye's blur spot at the object is lambda (eye_dist - z) / pupil. Points are spaced 2 pixels,
    several per blur spot, so a single frame shows full speckle; the groups put k-cell gaps between
    points shown together.
    """
    rng = np.random.default_rng(seed)
    cell = 2 * grid.pitch
    pts, ij = test_patch(size, z, cell, grid)
    rc = grid.to_index(0, 0)
    half = int(size / 2 / grid.pitch * 0.7)
    mask = np.zeros((grid.n, grid.n), bool)
    mask[rc[0] - half:rc[0] + half, rc[1] - half:rc[1] + half] = True

    def frame(sel):
        u = optics.wrp_hologram(pts[sel], grid, rng=rng)
        return optics.eye_view(optics.phase_only(u), grid, (0, 0), eye_dist, z, pupil)

    everything = np.ones(len(pts), bool)
    n = k * k
    one = frame(everything)
    rand = sum(frame(everything) for _ in range(n)) / n
    groups = np.zeros_like(one)
    for a in range(k):
        for b in range(k):
            groups += frame((ij[:, 0] % k == a) & (ij[:, 1] % k == b))
    groups /= n
    spot = grid.wavelength * (eye_dist - z) / pupil
    return {
        "k": k, "frames": n, "eye_blur_spot_um": round(spot * 1e6, 1), "point_spacing_um": round(cell * 1e6, 1),
        "one_frame": contrast(one, mask), "random_avg": contrast(rand, mask), "sparse_groups": contrast(groups, mask),
        "random_expected": contrast(one, mask) / np.sqrt(n),
        "_img": {"one": one * mask, "random": rand * mask, "groups": groups * mask},
    }
