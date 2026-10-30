"""True-scale wave simulation of the AETHER Desk (1D holographic panel), as the eye sees it.

Why: the lab hologram (8.2 mm SLM, scene shrunk ~40x) is not wave-equivalent to the desk - the wavelength does not
shrink with the scene - and it is a full-parallax hologram while the desk is 1D. This module simulates the desk
panel at its real size and pitch, column by column:

Vertical (coherent, the holographic direction; v7 / v13):
  1. Every visible scene point (rendered from the eye, Window Law applied) gets a sub-hologram on the panel: the
     converging (or, behind the panel, diverging) cylindrical wave aimed at the eye box (SeeReal-style eye-tracked
     window), random diffuse phase, amplitude normalised so its energy matches the rendered brightness.
  2. Sparse point groups (v11): k subframes, each lighting every k-th row only; the eye averages them.
  3. Panel modulation, sampled at the real vertical pitch (45 um, projected by the panel tilt); the backlight
     converges to the eye (field lens). encode="none" (default): ideal complex modulation (amplitude + phase, e.g.
     two stacked LC layers). encode="double_phase" (Hsueh & Sawchuk 1978: alternating pixels phi +- arccos(A/Amax))
     or "phase" (kinoform) model a single phase-only panel. Measured in this model (tests/notes): with a 10.7 mm
     eye box and a 4 mm pupil there is no guard band, and both phase-only encodings put a haze of 0.4-1.7x the
     image brightness into the pupil. Phase-only encoding for the desk is an open engineering problem; these two
     modes are experimental and not yet validated.
  4. Fresnel propagation panel -> eye plane at the real distance (single FFT; output grid = the eye box), pupil
     chord, eye lens focused at F, Fourier transform to retinal angle.
Horizontal (incoherent columns, v12): each column's light keeps the panel's curvature 1/d (geometric defocus when
  the eye focuses elsewhere) plus the column width blur w/d. The 4 mm circular pupil is integrated exactly as
  incoherent vertical chords (Parseval: the vertical marginal of the 2D PSF is the sum over chords).
Approximations (stated): each image column uses one panel plane perpendicular to its mean ray at the median panel
  distance, with the pitch projected by the panel tilt; horizontal diffraction of the pupil is not added;
  diffraction-limited eye; 530 nm.
"""
import numpy as np

from . import retina

ARCMIN = np.pi / 180 / 60


def double_phase(u):
    """Complex field -> phase-only samples (double-phase, alternating pixels along the last axis)."""
    u = np.asarray(u)
    A = np.abs(u)
    a = A / max(float(A.max()), 1e-30)
    ph = np.angle(u)
    d = np.arccos(np.clip(a, 0, 1))
    out = ph + d
    idx = np.arange(u.shape[-1]) % 2 == 1
    out[..., idx] = (ph - d)[..., idx]
    return out


def _chords(n=8):
    """Gauss-Legendre chord positions x/R and weights for integrating over a circular pupil."""
    x, w = np.polynomial.legendre.leggauss(n)
    return x, w


def column_retina(D, theta, I, F, d_c, pitch, lam=530e-9, k=3, encode="auto", rng=None,
                  pupil=4e-3, eye_box=None, fine=None, x_rel=0.0, diffuse=True):
    """Vertical retinal intensity of one panel column for one pupil chord.

    D, theta, I: distance (m), vertical angle (rad) and brightness of the column's visible points.
    F: eye focus (m); d_c: panel distance for this column (m); pitch: projected vertical pitch (m).
    x_rel: chord position across the pupil (-1..1). Returns (theta_grid, intensity), intensity averaged over the
    k sparse subframes."""
    rng = rng or np.random.default_rng(0)
    if encode == "auto":
        encode = "none"
    kk = 2 * np.pi / lam
    e = eye_box or lam * d_c / pitch                       # eye box height = lambda d / p
    if encode == "double_phase":
        # the double-phase copy sits half an eye box away: aim the sub-holograms at the central half only,
        # so the copy falls outside the pupil (the known price of double-phase: half the eye box)
        e = e / 2
    y = D * np.tan(theta)                                  # transverse position of each point
    L = d_c - D * np.cos(theta)                            # its distance in front of (+) or behind (-) the panel
    s_c = y * d_c / np.maximum(D, 1e-6)                    # where the eye -> point line meets the panel
    half = np.maximum(0.5 * e * np.abs(L) / np.maximum(D, 1e-6), pitch)
    s_lo, s_hi = float((s_c - half).min()) - 4 * pitch, float((s_c + half).max()) + 4 * pitch
    N = int(2 ** np.ceil(np.log2(max(1024, (s_hi - s_lo) / pitch))))
    s0 = (s_lo + s_hi) / 2 - N / 2 * pitch
    s = s0 + np.arange(N) * pitch
    dy = lam * d_c / (N * pitch)                           # eye-plane sample step (single-FFT Fresnel)
    yy = (np.arange(N) - N / 2) * dy
    R = pupil / 2
    hh = R * np.sqrt(max(0.0, 1 - x_rel ** 2))
    inp = np.abs(yy) <= hh
    M = fine or 8192
    acc = None
    rows = np.arange(len(D))
    for g in range(k):
        u = np.zeros(N, complex)
        for i in rows[rows % k == g]:
            if I[i] <= 0:
                continue
            a0 = int(np.floor((s_c[i] - half[i] - s0) / pitch))
            a1 = int(np.ceil((s_c[i] + half[i] - s0) / pitch)) + 1
            a0, a1 = max(a0, 0), min(a1, N)
            if a1 <= a0:
                continue
            ss = s[a0:a1]
            if abs(L[i]) < pitch * pitch / lam:             # on the panel plane: the pixel itself is the point
                j = int(np.clip(round((s_c[i] - s0) / pitch), 0, N - 1))
                u[j] += np.sqrt(I[i]) * (np.exp(2j * np.pi * rng.random()) if diffuse else 1)
                continue
            w = np.exp(-1j * kk * (ss - y[i]) ** 2 / (2 * L[i]))     # converging (L > 0) or diverging (L < 0)
            # soft sub-hologram edge (Tukey, outer 15 % each side - outside the pupil's part of the eye box):
            # hard edges would throw encoding noise across the whole eye box
            r = np.abs(ss - s_c[i]) / half[i]
            w = w * np.where(r < 0.7, 1.0, 0.5 * (1 + np.cos(np.pi * np.clip((r - 0.7) / 0.3, 0, 1))))
            u[a0:a1] += np.sqrt(I[i] / (a1 - a0)) * (np.exp(2j * np.pi * rng.random()) if diffuse else 1) * w
        if not np.any(u):
            continue
        # the panel is lit by a backlight converging to the eye (field lens, as in SeeReal-type displays), so the
        # SLM itself only has to encode u / lens; whatever the encoding throws away (zero order, double-phase copy)
        # focuses to points in the eye plane instead of flooding the pupil
        # v = u / lens is what the SLM itself shows (the lens is real glass, not pixels: sampling it on the 45 um
        # grid would alias). Fresnel to the eye: U(y) ~ e^{ik y^2/2d} FT{u e^{ik s^2/2d}} = e^{ik y^2/2d} FT{v}.
        v = u * np.exp(1j * kk * s ** 2 / (2 * d_c))
        if encode == "double_phase":
            v = np.exp(1j * double_phase(v))
        elif encode == "phase":
            v = np.exp(1j * np.angle(v))
        f = yy / (lam * d_c)
        Ue = np.fft.fftshift(np.fft.fft(np.fft.ifftshift(v)))
        Ue = Ue * np.exp(-2j * np.pi * f * (s0 + N / 2 * pitch)) * np.exp(1j * kk * yy ** 2 / (2 * d_c))
        # pupil chord, eye lens focused at F, then angle spectrum on the retina
        P = np.where(inp, Ue * np.exp(-1j * kk * yy ** 2 / (2 * F)), 0)
        Pc = P[inp]
        G = np.fft.fftshift(np.fft.fft(Pc, M))
        Ig = np.abs(G) ** 2
        acc = Ig if acc is None else acc + Ig
    th = -np.fft.fftshift(np.fft.fftfreq(M, d=dy)) * lam   # retinal angle of each sample (image is inverted)
    if acc is None:
        return th, np.zeros(M)
    return th, acc / k


def view(state, focus_z_mm=None, n=240, eye=None, k=3, encode="none", chords=6, seed=0, rendered=None):
    """Retinal image of the design on the real-size AETHER Desk (vertical wave optics, horizontal geometric).
    Returns the image (n x n), the eye focus and the settings."""
    R = rendered or retina.render(state, n=n, eye=eye)
    I, D, d, win, dth = R["I"], R["D"], R["d"], R["window"], R["dth"]
    n = R["n"]
    E, T = R["eye"], R["target"]
    if focus_z_mm is None:
        focus_z_mm = float(T[2])
    t = (E[2] - focus_z_mm) / max(E[2] - T[2], 1e-6)
    F = float(np.linalg.norm(T - E) * t) * 1e-3
    k_ = state["desk"]
    lam = k_["wavelength_nm"] * 1e-9
    p = k_["vertical_pitch_um"] * 1e-6
    w = k_["column_width_um"] * 1e-6
    # panel tilt seen along the view: projected pitch p cos(angle between the view ray and the panel normal)
    view_dir = (T - E) / np.linalg.norm(T - E)
    cos_t = abs(float(view_dir[2]))
    p_eff = p * cos_t
    rng = np.random.default_rng(seed)
    out = np.zeros((n, n))
    theta_rows = (n / 2 - np.arange(n) - 0.5) * dth
    xs, ws = _chords(chords)
    valid = np.isfinite(D) & (I > 0) & win
    for j in range(n):
        sel = valid[:, j]
        if not sel.any():
            continue
        Dj, thj, Ij, dj = D[sel, j], theta_rows[sel], I[sel, j], d[sel, j]
        d_c = float(np.median(dj))
        for xr, wt in zip(xs, ws):
            th, Ig = column_retina(Dj, thj, Ij, F, d_c, p_eff, lam, k, encode, rng, x_rel=float(xr))
            # bin the fine retinal profile onto the image rows (each image pixel integrates its angle range)
            idx = np.floor(n / 2 - th / dth).astype(int)
            ok = (idx >= 0) & (idx < n)
            col = np.bincount(idx[ok], weights=Ig[ok], minlength=n)[:n] * wt
            # horizontal: geometric defocus of the panel curvature for this chord, per row (its own panel distance)
            shift = float(xr) * 2e-3 * (1 / F - 1 / d_c) / dth
            j2 = j + shift
            j0 = int(np.floor(j2))
            fr = j2 - j0
            if 0 <= j0 < n:
                out[:, j0] += (1 - fr) * col
            if 0 <= j0 + 1 < n:
                out[:, j0 + 1] += fr * col
    # column width blur (w / d) along x
    nb = max(1, int(round(w / float(np.nanmedian(d[valid])) / dth))) if valid.any() else 1
    if nb > 1:
        ker = np.ones(nb) / nb
        out = np.apply_along_axis(lambda r: np.convolve(r, ker, "same"), 1, out)
    return {"image": out, "focus_m": F, "focus_z_mm": focus_z_mm, "encode": encode, "k": k,
            "pitch_projected_um": round(p_eff * 1e6, 1), "eye_box_mm": round(lam * float(np.nanmedian(d[valid])) / p_eff * 1e3, 1) if valid.any() else None}


def point_psf(D, d, F, pitch=45e-6, lam=530e-9, encode="none", chords=8, dth=0.125 * ARCMIN, size=512):
    """Vertical retinal line-spread of a single point at D (m) on a 1D panel at d, eye focused at F, by the wave
    simulation above. Used to check it against the analytic eye model (eye.psf vertical marginal)."""
    xs, ws = _chords(chords)
    prof = np.zeros(size)
    for xr, wt in zip(xs, ws):
        th, Ig = column_retina(np.array([D]), np.array([0.0]), np.array([1.0]), F, d, pitch, lam, 1, encode,
                               np.random.default_rng(1), x_rel=float(xr), fine=16384)
        idx = np.floor(size / 2 - th / dth).astype(int)
        ok = (idx >= 0) & (idx < size)
        prof += np.bincount(idx[ok], weights=Ig[ok], minlength=size)[:size] * wt
    return prof / prof.sum()


def mtf_1d(profile, dth, cpd=15.0):
    o = np.abs(np.fft.fft(np.fft.ifftshift(profile)))
    f = np.fft.fftfreq(len(profile), d=dth / (np.pi / 180))
    return float(o[int(np.argmin(np.abs(f - cpd)))] / o[0])
