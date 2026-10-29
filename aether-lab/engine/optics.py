"""Scalar wave optics for AETHER Lab.

Conventions
- Hologram plane at z = 0, light travels towards +z (towards the viewer).
- A scene point at z > 0 floats in front of the hologram (real image),
  z < 0 sits behind it (virtual image).
- All lengths in metres. Arrays live on the GPU when CuPy is available (see backend.py).
"""
from dataclasses import dataclass

import numpy as np

from .backend import xp, to_numpy


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
    """Propagate field u by distance z (band-limited angular spectrum, Matsushima 2009).

    U(z) = F^-1{ F{U(0)} * exp(i 2 pi z sqrt(1/lambda^2 - fx^2 - fy^2)) * W(fx, fy) }
    with W cutting |f| > 1 / (lambda sqrt((2 df z)^2 + 1)) to avoid aliasing of the transfer function.
    """
    u = xp.asarray(u)
    n = u.shape[0]
    if pad:
        big = xp.zeros((2 * n, 2 * n), complex)
        big[n // 2:n // 2 + n, n // 2:n // 2 + n] = u
        u = big
    m = u.shape[0]
    f = xp.fft.fftfreq(m, d=grid.pitch)
    fx, fy = xp.meshgrid(f, f)
    lam = grid.wavelength
    arg = 1 - (lam * fx) ** 2 - (lam * fy) ** 2
    h = xp.exp(1j * grid.k * z * xp.sqrt(xp.maximum(arg, 0)))
    df = 1 / (m * grid.pitch)
    f_lim = 1 / (lam * np.sqrt((2 * df * z) ** 2 + 1))
    h[(arg < 0) | (xp.abs(fx) > f_lim) | (xp.abs(fy) > f_lim)] = 0
    out = xp.fft.ifft2(xp.fft.fft2(u) * h)
    if pad:
        out = out[n // 2:n // 2 + n, n // 2:n // 2 + n]
    return out


def _splat_points(u, points, amps, phases, grid, z_plane):
    """Add exact spherical waves of points onto the plane z = z_plane (windowed, anti-aliased).

    Converging wave for points in front of the plane: a exp(i(phi - k r)) / r, written only where
    the local fringe frequency rho / (lambda r) stays below 1 / (2 p).
    """
    x = (np.arange(grid.n) - grid.n / 2) * grid.pitch
    tan_max = np.tan(grid.max_angle)
    k = grid.k
    for (px, py, pz), a, ph in zip(points, amps, phases):
        dz = pz - z_plane
        if abs(dz) < grid.pitch:
            dz = grid.pitch * np.sign(dz or 1)
        r_max = abs(dz) * tan_max
        c0 = max(0, int(np.floor((px - r_max) / grid.pitch + grid.n / 2)))
        c1 = min(grid.n, int(np.ceil((px + r_max) / grid.pitch + grid.n / 2)) + 1)
        r0 = max(0, int(np.floor((py - r_max) / grid.pitch + grid.n / 2)))
        r1 = min(grid.n, int(np.ceil((py + r_max) / grid.pitch + grid.n / 2)) + 1)
        if c0 >= c1 or r0 >= r1:
            continue
        X, Y = np.meshgrid(x[c0:c1] - px, x[r0:r1] - py)
        rho2 = X ** 2 + Y ** 2
        r = np.sqrt(rho2 + dz ** 2)
        w = a * np.exp(1j * (ph - np.sign(dz) * k * r)) / r
        w[rho2 > r_max ** 2] = 0
        u[r0:r1, c0:c1] += w
    return u


def point_hologram(points, grid, amps=None, phases=None, rng=None):
    """Direct point-source CGH: every point's spherical wave written straight onto the hologram."""
    points = np.asarray(points, float)
    m = len(points)
    amps = np.ones(m) if amps is None else np.asarray(amps, float)
    if phases is None:
        phases = (rng or np.random.default_rng(0)).uniform(0, 2 * np.pi, m)
    u = np.zeros((grid.n, grid.n), complex)
    return _splat_points(u, points, amps, phases, grid, 0.0)


def wrp_hologram(points, grid, amps=None, phases=None, rng=None, slab=1.5e-3, gap=0.2e-3):
    """Wavefront-recording-plane CGH (Shimobaba et al. 2009), multi-plane version.

    Points are cut into depth slabs. Each slab's points are written onto a recording plane just
    in front of the slab (tiny windows, because they are close), then that plane is propagated
    back to the hologram with the angular spectrum method. Exact within scalar diffraction,
    and ~10-100x faster than writing every point onto the hologram directly.
    """
    points = np.asarray(points, float)
    m = len(points)
    if m == 0:
        return xp.zeros((grid.n, grid.n), complex)
    amps = np.ones(m) if amps is None else np.asarray(amps, float)
    if phases is None:
        phases = (rng or np.random.default_rng(0)).uniform(0, 2 * np.pi, m)
    phases = np.asarray(phases, float)
    z = points[:, 2]
    edges = np.arange(z.min(), z.max() + slab, slab)
    total = xp.zeros((grid.n, grid.n), complex)
    for lo in edges:
        sel = (z >= lo) & (z < lo + slab)
        if not sel.any():
            continue
        z_w = lo - gap
        wrp = np.zeros((grid.n, grid.n), complex)
        _splat_points(wrp, points[sel], amps[sel], phases[sel], grid, z_w)
        total += angular_spectrum(wrp, -z_w, grid)
    return total


def layer_hologram(points, grid, n_layers=16, amps=None, rng=None):
    """Fast approximation: bin points into depth layers and back-propagate each layer."""
    points = np.asarray(points, float)
    amps = np.ones(len(points)) if amps is None else np.asarray(amps, float)
    rng = rng or np.random.default_rng(0)
    zs = points[:, 2]
    edges = np.linspace(zs.min(), zs.max() + 1e-12, n_layers + 1)
    u = xp.zeros((grid.n, grid.n), complex)
    for i in range(n_layers):
        sel = (zs >= edges[i]) & (zs < edges[i + 1])
        if not sel.any():
            continue
        layer = np.zeros((grid.n, grid.n), complex)
        for (px, py, _), a in zip(points[sel], amps[sel]):
            r, c = grid.to_index(px, py)
            if 0 <= r < grid.n and 0 <= c < grid.n:
                layer[r, c] += a * np.exp(1j * rng.uniform(0, 2 * np.pi))
        u += angular_spectrum(layer, -zs[sel].mean(), grid)
    return u


def phase_only(u):
    """Encode a complex field as a phase-only hologram (what a phase SLM can show)."""
    return xp.angle(xp.asarray(u))


def reconstruct(phase, z, grid):
    """Intensity on a screen at distance z when the phase hologram is lit by a plane wave."""
    return to_numpy(xp.abs(angular_spectrum(xp.exp(1j * xp.asarray(phase)), z, grid)) ** 2)


def focus_sweep(phase, zs, grid):
    return [reconstruct(phase, z, grid) for z in zs]


def eye_view(phase, grid, eye_xy, eye_dist, focus_z, pupil=4e-3, pad=3):
    """What an eye (or camera) sees: hologram -> eye pupil -> refocus at depth focus_z.

    1. Propagate the hologram field to the eye plane z = eye_dist on a padded grid.
    2. Keep only the light inside a circular pupil centred at eye_xy (this is the Window Law:
       only light that actually enters the pupil can be seen).
    3. Propagate back by -(eye_dist - focus_z): the image the eye forms when focused at focus_z,
       expressed in object-space coordinates.
    """
    n = grid.n
    big = Grid(n * pad, grid.pitch, grid.wavelength)
    u = xp.zeros((big.n, big.n), complex)
    o = (big.n - n) // 2
    u[o:o + n, o:o + n] = xp.exp(1j * xp.asarray(phase))
    e = angular_spectrum(u, eye_dist, big, pad=False)
    x = (xp.arange(big.n) - big.n / 2) * big.pitch
    X, Y = xp.meshgrid(x, x)
    e = e * (((X - eye_xy[0]) ** 2 + (Y - eye_xy[1]) ** 2) <= (pupil / 2) ** 2)
    img = angular_spectrum(e, -(eye_dist - focus_z), big, pad=False)
    return to_numpy(xp.abs(img[o:o + n, o:o + n]) ** 2)
