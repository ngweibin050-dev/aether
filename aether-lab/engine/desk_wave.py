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


def pupil_gs(v, inband, iters=200, rng=None, scale=None):
    """Phase-only panel by band-limited phase retrieval ("pupil Gerchberg-Saxton").

    Only the part of the eye box the (tracked) pupil can occupy has to be right; the rest of the eye box is free.
    A phase-only panel has N real unknowns; the pupil band asks for 2 * N * (band / eye box) real numbers, so for a
    4 mm pupil band in a 10.7 mm eye box (37 %) there are ~1.35x more unknowns than conditions and a near-exact
    solution exists. Iterate: panel -> eye plane (FFT), put the wanted field back inside the band (best common
    scale) and leave the outside free, back to the panel, keep only the phase.
    v: wanted complex panel field (SLM plane, lens removed); inband: boolean mask on the FFT grid (fftshifted).
    scale: fixed amplitude of the target in the band (panel pixels have |w| = 1). One scale for the whole panel
    keeps every column and subframe at the right brightness (one shared backlight); the surplus light is sent
    out of the band. None = best scale per call (only for single-point checks).
    Returns the phase-only field and the relative error inside the band."""
    T = np.fft.fftshift(np.fft.fft(np.fft.ifftshift(v)))
    tn = float(np.vdot(T[inband], T[inband]).real) or 1e-30
    w = np.exp(1j * np.angle(v + 1e-30 * (rng or np.random.default_rng(0)).random(v.shape)))
    err = 1.0
    for it in range(iters):
        U = np.fft.fftshift(np.fft.fft(np.fft.ifftshift(w)))
        a = np.vdot(T[inband], U[inband]) / tn          # best complex scale of the target
        if scale is not None:
            a = scale * a / max(abs(a), 1e-30)          # keep its phase (free), fix its size
        err = float(np.linalg.norm(U[inband] - a * T[inband]) / max(np.linalg.norm(a * T[inband]), 1e-30))
        U[inband] = a * T[inband]
        w = np.exp(1j * np.angle(np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(U)))))
    return w, err


def column_fields(D, theta, I, F, d_c, pitch, lam=530e-9, k=3, encode="none", rng=None,
                  pupil=4e-3, eye_box=None, diffuse=True, band_mm=None, pupil_y=0.0, gs_scale=None):
    """Eye-plane fields of one panel column, one per sparse subframe (k of them), after the panel encoding.

    encode: "none" (complex modulation), "double_phase", "phase" (kinoform) or "pupil_gs" (phase-only, solved for
    the pupil band only: needs the eye-tracked pupil position pupil_y). Returns (yy, dy, [U_g], info)."""
    rng = rng or np.random.default_rng(0)
    if encode == "auto":
        encode = "none"
    kk = 2 * np.pi / lam
    e = eye_box or lam * d_c / pitch                       # eye box height = lambda d / p
    if encode == "double_phase":
        e = e / 2                                          # the double-phase copy sits half an eye box away
    y = D * np.tan(theta)
    L = d_c - D * np.cos(theta)
    s_c = y * d_c / np.maximum(D, 1e-6)
    half = np.maximum(0.5 * e * np.abs(L) / np.maximum(D, 1e-6), pitch)
    s_lo, s_hi = float((s_c - half).min()) - 4 * pitch, float((s_c + half).max()) + 4 * pitch
    N = int(2 ** np.ceil(np.log2(max(1024, (s_hi - s_lo) / pitch))))
    s0 = (s_lo + s_hi) / 2 - N / 2 * pitch
    s = s0 + np.arange(N) * pitch
    dy = lam * d_c / (N * pitch)
    yy = (np.arange(N) - N / 2) * dy
    band = (band_mm * 1e-3 if band_mm else pupil + 0.6e-3) / 2   # pupil + 0.3 mm tracking margin each side
    inband = np.abs(yy - pupil_y) <= band
    rows = np.arange(len(D))
    out, errs, band_E = [], [], []
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
            # soft sub-hologram edge (Tukey, outer 30 %): hard edges throw encoding noise across the eye box
            r = np.abs(ss - s_c[i]) / half[i]
            w = w * np.where(r < 0.7, 1.0, 0.5 * (1 + np.cos(np.pi * np.clip((r - 0.7) / 0.3, 0, 1))))
            u[a0:a1] += np.sqrt(I[i] / (a1 - a0)) * (np.exp(2j * np.pi * rng.random()) if diffuse else 1) * w
        if not np.any(u):
            continue
        # backlight converging to the eye (field lens): the SLM shows v = u / lens. Fresnel to the eye:
        # U(y) ~ e^{ik y^2/2d} FT{u e^{ik s^2/2d}} = e^{ik y^2/2d} FT{v}
        v = u * np.exp(1j * kk * s ** 2 / (2 * d_c))
        if encode == "double_phase":
            v = np.exp(1j * double_phase(v))
        elif encode == "phase":
            v = np.exp(1j * np.angle(v))
        elif encode == "pupil_gs":
            v, err = pupil_gs(v, inband, scale=gs_scale)   # own seed: diffuse phases stay identical to "none"
            errs.append(err)
        f = yy / (lam * d_c)
        Ue = np.fft.fftshift(np.fft.fft(np.fft.ifftshift(v)))
        Ue = Ue * np.exp(-2j * np.pi * f * (s0 + N / 2 * pitch)) * np.exp(1j * kk * yy ** 2 / (2 * d_c))
        if encode == "pupil_gs" and gs_scale:
            Ue = Ue / gs_scale                         # back to the units of "none" (same backlight for all)
        out.append(Ue)
        band_E.append(float(np.sum(np.abs(Ue[inband]) ** 2)) / N ** 2)
    info = {"band_error": float(np.mean(errs)) if errs else None, "N": N, "band_energy_per_N2": band_E}
    return yy, dy, out, info


def chord_retina(yy, dy, fields, F, lam=530e-9, pupil=4e-3, x_rel=0.0, fine=None, pupil_y=0.0):
    """Retinal intensity (vertical) for one chord of the round pupil, averaged over the subframe fields."""
    kk = 2 * np.pi / lam
    hh = pupil / 2 * np.sqrt(max(0.0, 1 - x_rel ** 2))
    inp = np.abs(yy - pupil_y) <= hh
    M = fine or 8192
    acc = np.zeros(M)
    for Ue in fields:
        P = Ue[inp] * np.exp(-1j * kk * (yy[inp] - pupil_y) ** 2 / (2 * F))
        acc += np.abs(np.fft.fftshift(np.fft.fft(P, M))) ** 2
    th = -np.fft.fftshift(np.fft.fftfreq(M, d=dy)) * lam
    return th, acc / max(len(fields), 1)


def column_retina(D, theta, I, F, d_c, pitch, lam=530e-9, k=3, encode="auto", rng=None,
                  pupil=4e-3, eye_box=None, fine=None, x_rel=0.0, diffuse=True):
    """One column, one pupil chord (kept for point_psf and older callers)."""
    yy, dy, fields, _ = column_fields(D, theta, I, F, d_c, pitch, lam, k, encode, rng, pupil, eye_box, diffuse)
    return chord_retina(yy, dy, fields, F, lam, pupil, x_rel, fine)


def view(state, focus_z_mm=None, n=240, eye=None, k=3, encode="none", chords=6, seed=0, rendered=None, eta=0.05):
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
    band_err = []
    gs_scale = None
    if encode == "pupil_gs":
        # pass 1: how much in-band light each column needs (complex fields); one panel-wide scale so the column
        # that needs the most gets eta of its own power into the band
        need = []
        for j in range(n):
            sel = valid[:, j]
            if sel.any():
                _, _, _, inf = column_fields(D[sel, j], theta_rows[sel], I[sel, j], F, float(np.median(d[sel, j])),
                                             p_eff, lam, k, "none", np.random.default_rng(seed + j))
                need += inf["band_energy_per_N2"]
        gs_scale = float(np.sqrt(eta / max(max(need), 1e-30))) if need else None
    for j in range(n):
        sel = valid[:, j]
        if not sel.any():
            continue
        Dj, thj, Ij, dj = D[sel, j], theta_rows[sel], I[sel, j], d[sel, j]
        d_c = float(np.median(dj))
        yy, dyy, fields, info = column_fields(Dj, thj, Ij, F, d_c, p_eff, lam, k, encode,
                                              np.random.default_rng(seed + j), gs_scale=gs_scale)
        if info["band_error"] is not None:
            band_err.append(info["band_error"])
        for xr, wt in zip(xs, ws):
            th, Ig = chord_retina(yy, dyy, fields, F, lam, x_rel=float(xr))
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
            "pupil_band_error": round(float(np.mean(band_err)), 4) if band_err else None,
            "pupil_band_efficiency": eta if encode == "pupil_gs" else None,
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
