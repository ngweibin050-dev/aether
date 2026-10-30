"""Wave-optics eye model for judging what a viewer of a holographic display would see.

The eye is a 4 mm pupil + a lens focused at distance F. Light arriving from an image
point has wavefront curvature 1/Dx horizontally and 1/Dy vertically.
- Full 2D hologram: Dx = Dy = D (distance eye -> image point). Natural focus.
- AETHER Desk (1D hologram): vertical curvature is true (1/D) but horizontal light comes
  from the panel plane (1/d), plus a horizontal blur from the column width.
Sharpness = MTF at 15 cycles/degree (fine detail for design work), best eye focus.
Assumptions: diffraction-limited eye, paraxial, pupil fully inside the eye box.
"""
import numpy as np

ARCMIN = np.pi / 180 / 60
PUPIL = 4e-3
N = 512
DTH = 0.125 * ARCMIN       # retinal sampling (rad)
CPD = 15.0                 # cycles per degree used as the sharpness test


def psf(dx_dist, dy_dist, focus, wavelength=530e-9, blur_angle=0.0):
    step = wavelength / (N * DTH)
    x = (np.arange(N) - N / 2) * step
    X, Y = np.meshgrid(x, x)
    pupil = (X ** 2 + Y ** 2 <= (PUPIL / 2) ** 2).astype(float)
    k = 2 * np.pi / wavelength
    w = 0.5 * k * (X ** 2 * (1 / dx_dist - 1 / focus) + Y ** 2 * (1 / dy_dist - 1 / focus))
    e = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(pupil * np.exp(-1j * w))))
    i = np.abs(e) ** 2
    if blur_angle > 0:
        nb = max(1, int(round(blur_angle / DTH)))
        kern = np.ones(nb) / nb
        i = np.apply_along_axis(lambda r: np.convolve(r, kern, "same"), 1, i)
    return i / i.sum()


def mtf(i, cpd=CPD):
    o = np.abs(np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(i))))
    f = np.fft.fftshift(np.fft.fftfreq(N, d=DTH / (np.pi / 180)))
    j = int(np.argmin(np.abs(f - cpd)))
    c = N // 2
    return 0.5 * (float(o[c, j]) + float(o[j, c]))


def best_focus(dx_dist, dy_dist, wavelength=530e-9, blur_angle=0.0, span=0.6, steps=25):
    """Eye refocuses to the sharpest setting. Returns (mtf, focus error in dioptres)."""
    d_mid = 2 / (1 / dx_dist + 1 / dy_dist)
    powers = np.linspace(1 / d_mid - span, 1 / d_mid + span, steps)
    vals = [mtf(psf(dx_dist, dy_dist, 1 / p, wavelength, blur_angle)) for p in powers]
    i = int(np.argmax(vals))
    true_dist = dy_dist  # the true (vertical) depth cue
    return vals[i], float(powers[i] - 1 / true_dist)


def desk_sharpness(height, view_dist=0.7, column_width=150e-6, wavelength=530e-9):
    """How sharp a point `height` metres in front of an AETHER Desk panel looks.

    Returns dict with the 1D-desk MTF, the full-2D-hologram MTF, their ratio and the
    focus error (how far the eye's focus lands from the true depth, in dioptres).
    """
    D = view_dist - height
    ref, _ = best_focus(D, D, wavelength)
    one_d, err = best_focus(view_dist, D, wavelength, column_width / view_dist)
    return {
        "height_m": height,
        "astigmatism_D": abs(1 / D - 1 / view_dist),
        "mtf_1d": one_d,
        "mtf_2d": ref,
        "relative": one_d / ref,
        "focus_error_D": err,
    }


def eye_box(vertical_pitch, view_dist=0.7, wavelength=530e-9):
    """Height of the viewing window a 1D hologram of this pitch can serve: e = lambda d / p."""
    return wavelength * view_dist / vertical_pitch


# ---------------- per-point sharpness for the real (oblique) viewing geometry ----------------

_REL = {}


def _load_table():
    """Precomputed relative_sharpness (0..1.5 D astigmatism, 0.4..1.3' column blur, 530 nm): same function, saved
    once (sharpness_table.json) so a desk_score does not spend ~30 s filling the cache."""
    import json
    import os
    f = os.path.join(os.path.dirname(__file__), "sharpness_table.json")
    if os.path.exists(f):
        try:
            for k, v in json.load(open(f)).items():
                a, b, lam = k.split("|")
                _REL[(float(a), float(b), int(lam))] = float(v)
        except (OSError, ValueError):
            pass


def _rel_key(astig, blur_angle, wavelength):
    return (round(abs(float(astig)), 2), round(float(blur_angle) / ARCMIN, 1), round(float(wavelength) * 1e9))


def relative_sharpness(d, D, column_width=150e-6, wavelength=530e-9):
    """1D desk / full 2D hologram, each at the eye's best focus (the v9 / v13 definition).

    d: eye -> panel along the line of sight through the point (m); D: eye -> point (m). Only the astigmatism
    |1/D - 1/d| and the column blur w/d matter (diffraction-limited eye, best focus), so results are cached on
    0.01 D and 0.1 arcmin steps. Both numbers come from the same psf() at the same wavelength."""
    key = _rel_key(1 / D - 1 / d, column_width / d, wavelength)
    if key not in _REL:
        a, blur, lam = key[0], key[1] * ARCMIN, key[2] * 1e-9
        Dm = 0.6                                     # any distance: only the dioptre difference matters
        dm = 1 / (1 / Dm - a)
        ref = mtf(psf(Dm, Dm, Dm, lam))
        powers = np.linspace(min(1 / dm, 1 / Dm) - 0.05, max(1 / dm, 1 / Dm) + 0.05, 13)
        one = max(mtf(psf(dm, Dm, 1 / p, lam, blur)) for p in powers)
        _REL[key] = min(1.0, one / ref)
    return _REL[key]


_load_table()


def line_of_sight(points_mm, eye_mm):
    """Per point: D = eye -> point and d = eye -> panel (plane z = 0) along the same line, in metres.
    ok is False where that line never reaches the panel (the point is level with or above the eye)."""
    P = np.asarray(points_mm, float).reshape(-1, 3)
    E = np.asarray(eye_mm, float)
    dz = E[2] - P[:, 2]
    ok = dz > 1e-6
    t = np.where(ok, E[2] / np.where(ok, dz, 1), 1)  # E + t (P - E) is on the panel
    D = np.linalg.norm(P - E, axis=1) * 1e-3
    return D, D * t, ok


def point_sharpness(points_mm, eye_mm, column_width=150e-6, wavelength=530e-9):
    """1D-desk sharpness (0..1 of a full 2D hologram) of each point, seen from the real eye position."""
    D, d, ok = line_of_sight(points_mm, eye_mm)
    out = np.zeros(len(D))
    keys = {}
    for i in np.nonzero(ok)[0]:
        k = (round(abs(1 / D[i] - 1 / d[i]), 2), round(d[i], 2))
        if k not in keys:
            keys[k] = relative_sharpness(d[i], D[i], column_width, wavelength)
        out[i] = keys[k]
    return out, ok
