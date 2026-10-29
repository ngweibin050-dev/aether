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
