"""Scalar wave optics for AETHER Lab.

Conventions
- Hologram plane at z = 0, light travels towards +z (towards the viewer).
- A scene point at z > 0 floats in front of the hologram (real image),
  z < 0 sits behind it (virtual image).
- All lengths in metres.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Grid:
    n: int = 512            # samples per side
    pitch: float = 8e-6     # hologram pixel pitch (m)
    wavelength: float = 532e-9

    @property
    def size(self):
        return self.n * self.pitch

    @property
    def k(self):
        return 2 * np.pi / self.wavelength

    @property
    def max_angle(self):
        """Largest angle the hologram can bend light to: sin(theta) = lambda / (2 p)."""
        return float(np.arcsin(min(1.0, self.wavelength / (2 * self.pitch))))

    def coords(self):
        x = (np.arange(self.n) - self.n / 2) * self.pitch
        return np.meshgrid(x, x)

    def to_index(self, x, y):
        """Physical (x, y) -> nearest (row, col)."""
        return (int(round(y / self.pitch + self.n / 2)),
                int(round(x / self.pitch + self.n / 2)))


def angular_spectrum(u, z, grid, pad=True):
    """Propagate field u by distance z (band-limited angular spectrum, Matsushima 2009)."""
    n = grid.n
    if pad:
        big = np.zeros((2 * n, 2 * n), complex)
        big[n // 2:n // 2 + n, n // 2:n // 2 + n] = u
        u = big
    m = u.shape[0]
    f = np.fft.fftfreq(m, d=grid.pitch)
    fx, fy = np.meshgrid(f, f)
    lam = grid.wavelength
    arg = 1 - (lam * fx) ** 2 - (lam * fy) ** 2
    h = np.exp(1j * grid.k * z * np.sqrt(np.maximum(arg, 0)))
    h[arg < 0] = 0
    df = 1 / (m * grid.pitch)
    f_lim = 1 / (lam * np.sqrt((2 * df * z) ** 2 + 1))
    h[(np.abs(fx) > f_lim) | (np.abs(fy) > f_lim)] = 0
    out = np.fft.ifft2(np.fft.fft2(u) * h)
    if pad:
        out = out[n // 2:n // 2 + n, n // 2:n // 2 + n]
    return out


def point_hologram(points, grid, amps=None, phases=None, rng=None):
    """Point-source CGH: complex field on the hologram plane that rebuilds every point.

    points: (M, 3) array of x, y, z. Each point only writes inside the disc where its
    local fringe frequency stays below 1/(2 p); outside it would alias.
    """
    points = np.asarray(points, float)
    m = len(points)
    amps = np.ones(m) if amps is None else np.asarray(amps, float)
    if phases is None:
        rng = rng or np.random.default_rng(0)
        phases = rng.uniform(0, 2 * np.pi, m)
    u = np.zeros((grid.n, grid.n), complex)
    x = (np.arange(grid.n) - grid.n / 2) * grid.pitch
    tan_max = np.tan(grid.max_angle)
    k = grid.k
    for (px, py, pz), a, ph in zip(points, amps, phases):
        if abs(pz) < grid.pitch:
            continue
        r_max = abs(pz) * tan_max
        c0 = max(0, int(np.floor((px - r_max) / grid.pitch + grid.n / 2)))
        c1 = min(grid.n, int(np.ceil((px + r_max) / grid.pitch + grid.n / 2)) + 1)
        r0 = max(0, int(np.floor((py - r_max) / grid.pitch + grid.n / 2)))
        r1 = min(grid.n, int(np.ceil((py + r_max) / grid.pitch + grid.n / 2)) + 1)
        if c0 >= c1 or r0 >= r1:
            continue
        X, Y = np.meshgrid(x[c0:c1] - px, x[r0:r1] - py)
        rho2 = X ** 2 + Y ** 2
        r = np.sqrt(rho2 + pz ** 2)
        # converging wave for a real point (pz > 0), diverging for a virtual one
        w = a * np.exp(1j * (ph - np.sign(pz) * k * r)) / r
        w[rho2 > r_max ** 2] = 0
        u[r0:r1, c0:c1] += w
    return u


def layer_hologram(points, grid, n_layers=16, amps=None, rng=None):
    """Fast approximation: bin points into depth layers and back-propagate each layer."""
    points = np.asarray(points, float)
    amps = np.ones(len(points)) if amps is None else np.asarray(amps, float)
    rng = rng or np.random.default_rng(0)
    zs = points[:, 2]
    edges = np.linspace(zs.min(), zs.max() + 1e-12, n_layers + 1)
    u = np.zeros((grid.n, grid.n), complex)
    for i in range(n_layers):
        sel = (zs >= edges[i]) & (zs < edges[i + 1])
        if not sel.any():
            continue
        layer = np.zeros_like(u)
        for (px, py, _), a in zip(points[sel], amps[sel]):
            r, c = grid.to_index(px, py)
            if 0 <= r < grid.n and 0 <= c < grid.n:
                layer[r, c] += a * np.exp(1j * rng.uniform(0, 2 * np.pi))
        u += angular_spectrum(layer, -zs[sel].mean(), grid)
    return u


def phase_only(u):
    """Encode a complex field as a phase-only hologram (what a phase SLM can show)."""
    return np.angle(u)


def reconstruct(phase, z, grid):
    """Intensity seen on a screen at distance z when the phase hologram is lit by a plane wave."""
    return np.abs(angular_spectrum(np.exp(1j * phase), z, grid)) ** 2


def focus_sweep(phase, zs, grid):
    return [reconstruct(phase, z, grid) for z in zs]
