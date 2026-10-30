"""What the viewer's eye actually sees on an AETHER Desk (desk scale, 70 cm), from the theory folder.

Pipeline (each step is a model from C:\\Aether\\theory):
1. View from the eye (H1 Window Law, Physics Record §8.1): render the design from the eye position
   (pinhole), with depth. Pixels whose eye->point ray misses the panel get no light.
2. Focus (v9 / v13 wave-optics eye): a 4 mm pupil, lens focused at F. A point at distance D from the
   eye on a 1D desk has vertical wavefront curvature 1/D (true hologram) and horizontal curvature
   1/d (it leaves the panel column at distance d), plus the column-width blur. Full 2D hologram:
   both 1/D. Ordinary 3D screen: both 1/d. The retinal PSF is the |FFT|^2 of the pupil function.
   The scene is cut into depth layers in dioptres; each layer is blurred by its own PSF and the
   layers add in intensity (diffuse scene, as in v9).
3. Speckle (v11 / v12): a coherent single frame has contrast ~0.3; sparse point groups (k
   subframes, vertical only on a 1D desk because adjacent columns are mutually incoherent, v12)
   bring it down. The speckle texture is computed with the v11 eye model (pupil + 1' pooling) on a
   uniform patch and applied multiplicatively, so its statistics match the theory numbers.
4. Full colour: three lasers (638 / 520 / 450 nm, common RGB laser diodes) shown in sequence. Each
   colour gets its own pupil PSF (diffraction and defocus phase scale with wavelength) and its own,
   independent speckle pattern; the eye adds the three. Part colours (reflectance per channel) come
   from the part's "color", or a material guess from its name.
5. The eye's longitudinal chromatic aberration (colour mode): the chromatic-eye model of Thibos et al. 1992
   (Appl. Opt. 31, 3594), R(lambda) = 1.68524 - 633.46 / (lambda_nm - 214.102) dioptres. The eye focuses the green
   laser; red and blue are defocused by R(lambda) - R(520). It affects a real object in the same way.
6. Sharpness is reported against a full 2D hologram at the SAME eye focus (same render, same PSF code, same
   wavelength), so a full 2D hologram scores exactly 100 %. Natural depth-of-field blur is not counted as a loss.
Not modelled: the eye's other aberrations, real accommodation behaviour.
"""
import re

import numpy as np

from . import backend, cutaway, geometry

ARCMIN = np.pi / 180 / 60
PUPIL = 4e-3
LAM = 530e-9
LASERS = (638e-9, 520e-9, 450e-9)                           # R, G, B laser diodes
DOF = 0.25                                                  # eye depth of field, dioptres (Hoffman, v10)


def chromatic_D(lam):
    """Thibos et al. 1992 chromatic eye: refraction (D) at wavelength lam (m)."""
    return 1.68524 - 633.46 / (lam * 1e9 - 214.102)

# material guesses from a part's name (linear reflectance per R, G, B)
MATERIALS = [
    (("coil", "winding", "copper", "wire"), "#c8763e"),
    (("magnet",), "#3a3f4a"),
    (("brass", "bush"), "#c9a44a"),
    (("bearing", "shaft", "axle", "pin", "bolt", "screw", "steel", "spring"), "#b8bfc8"),
    (("fan", "blade", "impeller", "propeller", "plastic", "cover", "cap"), "#2e6fd8"),
    (("pcb", "board", "circuit"), "#1f7a4a"),
    (("rubber", "tyre", "tire", "belt", "seal", "gasket"), "#2a2a2e"),
    (("stator", "lamination", "core"), "#6e7682"),
    (("rotor",), "#8a929c"),
    (("housing", "case", "frame", "body", "shell"), "#c4cbd4"),
    (("gear", "pinion", "wheel", "sprocket"), "#d0a35c"),
    (("glass", "lens", "window"), "#a7d8e8"),
]


def hex_color(c):
    c = str(c).strip()
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", c):
        return "#" + c.lstrip("#").lower()
    raise ValueError(f"colour must be a hex like #b87333, got {c}")


def part_rgb(part):
    """Linear RGB reflectance of a part (0..1)."""
    c = part.get("color")
    if not c:
        name = (part.get("name", "") + " " + part.get("type", "")).lower()
        c = next((col for keys, col in MATERIALS if any(k in name for k in keys)), "#b9c2cc")
    v = np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)]) / 255.0
    return v ** 2.2


# ---------------- 1. view from the eye ----------------


def camera(eye, target):
    E = np.asarray(eye, float)
    f = np.asarray(target, float) - E
    f /= np.linalg.norm(f)
    up = np.array([0, 0, 1.0]) if abs(f[2]) < 0.97 else np.array([0, 1.0, 0])
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return E, f, r, u


def render(state, n=640, eye=None, light=(-0.35, -0.55, 0.76), samples=None):
    """Pinhole view of the design from the eye. Returns intensity, distance (m), panel distance (m),
    window mask, angular pixel size (rad) and the camera."""
    parts = cutaway.view_parts(state)
    E = np.asarray(eye if eye is not None else state["eye"], float)
    lo, hi = geometry.bounds([p for p in parts if p.get("visible", True)])
    T = (lo + hi) / 2
    E, f, r, u = camera(E, T)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]) - E
    depth = corners @ f
    ang = np.max(np.abs(np.stack([corners @ r, corners @ u], 1)) / depth[:, None])
    fov = 2 * ang * 1.18 + 1e-4
    dth = fov / n
    # dense surface samples splatted into a z-buffer (a few per visible pixel; holes are filled below)
    m = samples or int(4.5 * n * n)
    xp = backend.xp                                         # the whole splat runs on the GPU when there is one
    P, N, owner = geometry.sample_surface(parts, m, seed=1, xp=xp)
    keep = xp.asarray(cutaway.section_mask(backend.to_numpy(P), state)) if cutaway.view_of(state).get("section") else None
    if keep is not None:
        P, N, owner = P[keep], N[keep], owner[keep]
    meshes = geometry.scene_meshes(parts)
    bright = xp.asarray(np.array([p.get("brightness", 1.0) for p, _, _ in meshes], np.float32))[owner] if len(owner) else xp.zeros(0)
    alb = xp.asarray(np.array([part_rgb(p) for p, _, _ in meshes], np.float32))[owner] if len(owner) else xp.zeros((0, 3))
    E, f, r, u = (xp.asarray(a, dtype=xp.float32) for a in (E, f, r, u))
    V = P - E
    z = V @ f
    x = (V @ r) / z
    y = (V @ u) / z
    ix = xp.floor(x / dth + n / 2).astype(xp.int64)
    iy = xp.floor(n / 2 - y / dth).astype(xp.int64)
    ok = (ix >= 0) & (ix < n) & (iy >= 0) & (iy < n) & (z > 0)
    ix, iy, z, P, N, bright, alb = ix[ok], iy[ok], z[ok], P[ok], N[ok], bright[ok], alb[ok]
    key = iy * n + ix
    zbuf = xp.full(n * n, xp.inf, dtype=xp.float32)
    backend.scatter_min(zbuf, key, z)
    # occlusion from the 3x3 neighbourhood too, so sparse samples of a back surface cannot leak
    # through gaps in a front surface (same fix as window.visible_from)
    zb = zbuf.reshape(n, n)
    zp = xp.pad(zb, 1, constant_values=xp.inf)
    zmin = xp.stack([zp[a:a + n, b:b + n] for a in range(3) for b in range(3)]).min(0).ravel()
    tol = 0.8 + 2.5 * dth * z                                   # mm: ~2 pixels of slope
    front = z <= xp.minimum(zbuf[key] + 0.6, zmin[key] + tol)
    # Lambert shading, two-sided normals (cut faces and inner walls are lit too), plus a soft rim
    L = xp.asarray(np.asarray(light, np.float32) / np.linalg.norm(light))
    view = -V[ok] / xp.linalg.norm(V[ok], axis=1)[:, None]
    nd = xp.abs(N @ L)
    rim = (1 - xp.abs(xp.sum(N * view, 1))) ** 2
    half = (L + view) / xp.linalg.norm(L + view, axis=1)[:, None]
    spec = xp.abs(xp.sum(N * half, 1)) ** 40
    shade = (0.08 + 0.62 * nd ** 1.2 + 0.25 * rim + 0.35 * spec) * bright
    kf = key[front]
    acc = xp.zeros(n * n)
    cnt = xp.zeros(n * n)
    backend.scatter_add(acc, kf, shade[front].astype(xp.float64))
    backend.scatter_add(cnt, kf, xp.ones(kf.shape[0]))
    A = xp.zeros((3, n * n))
    for c in range(3):
        backend.scatter_add(A[c], kf, alb[front, c].astype(xp.float64))
    # back to the CPU: the rest is per-pixel (small)
    acc, cnt, A, zbuf = (backend.to_numpy(a) for a in (acc, cnt, A, zbuf))
    E, f, r, u = (backend.to_numpy(a).astype(float) for a in (E, f, r, u))
    I = np.where(cnt > 0, acc / np.maximum(cnt, 1), 0.0)
    A = (A.T / np.maximum(cnt, 1)[:, None]).reshape(n, n, 3)
    zbuf = zbuf.astype(float)
    Z = np.where(np.isfinite(zbuf), zbuf, np.nan)
    # fill single-pixel holes left by random sampling (3x3 neighbourhood mean)
    I, Z = I.reshape(n, n), Z.reshape(n, n)
    hole = (cnt.reshape(n, n) == 0)
    if hole.any():
        pad_i = np.pad(I, 1)
        pad_z = np.pad(np.nan_to_num(Z, nan=0), 1)
        pad_c = np.pad((~hole).astype(float), 1)
        si = sum(pad_i[a:a + n, b:b + n] for a in range(3) for b in range(3))
        sz = sum(pad_z[a:a + n, b:b + n] for a in range(3) for b in range(3))
        sc = sum(pad_c[a:a + n, b:b + n] for a in range(3) for b in range(3))
        fill = hole & (sc >= 3)
        I[fill] = si[fill] / sc[fill]
        Z[fill] = sz[fill] / sc[fill]
        pad_a = np.pad(A, ((1, 1), (1, 1), (0, 0)))
        sa = sum(pad_a[a:a + n, b:b + n] for a in range(3) for b in range(3))
        A[fill] = sa[fill] / sc[fill][:, None]
    # per pixel: distance from the eye to the surface (D) and to the panel along the same ray (d)
    jj, ii = np.meshgrid(np.arange(n), np.arange(n))
    ray = (f[None, None] + ((jj + 0.5 - n / 2) * dth)[..., None] * r + ((n / 2 - ii - 0.5) * dth)[..., None] * u)
    ray /= np.linalg.norm(ray, axis=2, keepdims=True)
    cos = ray @ f
    D = Z / cos * 1e-3                                  # m
    t = -E[2] / np.minimum(ray[..., 2], -1e-9)          # ray length to the panel plane z = 0
    hit = E[None, None] + t[..., None] * ray
    k = state["desk"]
    win = (np.abs(hit[..., 0]) <= k["panel_w_mm"] / 2) & (np.abs(hit[..., 1]) <= k["panel_h_mm"] / 2) & (ray[..., 2] < 0)
    d = t * 1e-3
    return {"I": I, "A": A, "D": D, "d": d, "window": win, "dth": dth, "n": n, "eye": E, "target": T}


# ---------------- 2. retinal PSF (v9 eye) ----------------


def psf(Dx, Dy, F, dth, size, lam=LAM, col_blur=0.0, xp=np):
    """Retinal PSF on the image grid (angular step dth, `size` pixels square), v9 model.
    xp = numpy, or cupy on a GPU (same code)."""
    m = max(1, int(np.ceil(dth / (0.3 * ARCMIN))))          # compute finer if the image pixels are coarse
    dp = dth / m
    nf = size * m
    step = lam / (nf * dp)
    x = (xp.arange(nf) - nf / 2) * step
    X, Y = xp.meshgrid(x, x)
    P = (X ** 2 + Y ** 2 <= (PUPIL / 2) ** 2).astype(float)
    k = 2 * np.pi / lam
    W = 0.5 * k * (X ** 2 * (1 / Dx - 1 / F) + Y ** 2 * (1 / Dy - 1 / F))
    e = xp.fft.fftshift(xp.fft.fft2(xp.fft.ifftshift(P * xp.exp(-1j * W))))
    i = xp.abs(e) ** 2
    if col_blur > 0:                                        # horizontal box blur of the panel column
        nb = max(1, int(round(col_blur / dp)))
        c = xp.cumsum(xp.pad(i, ((0, 0), (nb // 2 + 1, nb - nb // 2 - 1))), axis=1)   # running mean, "same" size
        i = (c[:, nb:] - c[:, :-nb])[:, :nf] / nb
    if m > 1:
        i = i.reshape(size, m, size, m).sum((1, 3))
    return i / i.sum()


def mtf15(p, dth):
    p = backend.to_numpy(p)
    o = np.abs(np.fft.fft2(np.fft.ifftshift(p)))
    f = np.fft.fftfreq(p.shape[0], d=dth / (np.pi / 180))
    j = int(np.argmin(np.abs(f - 15.0)))
    return 0.5 * (float(o[0, j]) + float(o[j, 0]))


# ---------------- 3. speckle texture (v11 / v12 eye model) ----------------

_speckle_cache = {}


def speckle_texture(display, k, seed=0, lam=LAM):
    """Multiplicative speckle texture (mean 1) at 0.125'/px on a 512 tile, and its contrast."""
    LAM = lam
    key = (display, k, seed, lam)
    if key in _speckle_cache:
        return _speckle_cache[key]
    rng = np.random.default_rng(seed)
    n, dth = 512, 0.125
    f = np.fft.fftfreq(n, d=dth * ARCMIN)
    FX, FY = np.meshgrid(f, f)
    xs = (np.arange(n) - n / 2) * dth
    X, Y = np.meshgrid(xs, xs)
    cell = LAM / (2 * PUPIL) / ARCMIN                       # Nyquist cell, arcmin
    I = np.zeros((n, n))
    if display == "desk1d":
        # vertical: coherent, pupil height; horizontal: columns mutually incoherent (v12)
        Py = (np.abs(np.fft.fftfreq(n, d=dth * ARCMIN) * LAM) <= PUPIL / 2).astype(complex)
        st = k * cell
        for oy in range(k):
            u = np.zeros((n, n), complex)
            rows = ((np.arange(-n / 2 * dth, n / 2 * dth, st) + oy * cell) / dth + n / 2).round().astype(int) % n
            u[rows, :] = np.exp(2j * np.pi * rng.random((len(rows), n)))
            I += np.abs(np.fft.ifft(np.fft.fft(u, axis=0) * Py[:, None], axis=0)) ** 2
        # horizontal resolution of the column (incoherent) - smooth along x at the eye's 0.46' limit
    else:
        P = ((FX * LAM) ** 2 + (FY * LAM) ** 2 <= (PUPIL / 2) ** 2).astype(complex)
        st = k * cell
        for ox in range(k):
            for oy in range(k):
                u = np.zeros((n, n), complex)
                rows = ((np.arange(-n / 2 * dth, n / 2 * dth, st) + oy * cell) / dth + n / 2).round().astype(int) % n
                cols = ((np.arange(-n / 2 * dth, n / 2 * dth, st) + ox * cell) / dth + n / 2).round().astype(int) % n
                u[np.ix_(rows, cols)] = np.exp(2j * np.pi * rng.random((len(rows), len(cols))))
                I += np.abs(np.fft.ifft2(np.fft.fft2(u) * P)) ** 2
    s = 1.0 / 2.355                                         # 1' FWHM pooling (v11)
    G = np.exp(-(X ** 2 + Y ** 2) / (2 * s ** 2))
    G /= G.sum()
    I = np.real(np.fft.ifft2(np.fft.fft2(I) * np.fft.fft2(np.fft.ifftshift(G))))
    I /= I.mean()
    c = float(I[128:384, 128:384].std())
    _speckle_cache[key] = (I, c)
    return I, c


def _apply_texture(img, tex, dth):
    """Resample the 0.125' texture onto the image grid (nearest, tiled) and multiply."""
    n = img.shape[0]
    step = dth / ARCMIN / 0.125
    idx = (np.arange(n) * step).astype(int) % tex.shape[0]
    return img * tex[np.ix_(idx, idx)]


# ---------------- the retina image ----------------


def retina(state, focus_z_mm=None, display="desk1d", k=3, speckle=True, n=840, eye=None, rendered=None, color=False):
    """Retinal image for an eye focused at scene height focus_z_mm (mm above the panel).
    color=False: one 530 nm laser (n x n). color=True: R/G/B lasers (n x n x 3), each with its own PSF and speckle."""
    R = rendered or render(state, n=n, eye=eye)
    I, D, d, win, dth = R["I"], R["D"], R["d"], R["window"], R["dth"]
    n = R["n"]
    E = R["eye"]
    valid = np.isfinite(D) & (I > 0)
    lit = np.where(win, I, 0.0)                              # Window Law: no light outside the panel cone
    if focus_z_mm is None:
        focus_z_mm = float(R["target"][2])
    # eye focus distance: from the eye to the focus height along the view direction to the target
    T = R["target"]
    v = T - E
    t = (E[2] - focus_z_mm) / max(E[2] - T[2], 1e-6)
    F = float(np.linalg.norm(v) * t) * 1e-3
    col = state["desk"]["column_width_um"] * 1e-6
    # depth layers in dioptres (0.02 D, finer than the eye's ±0.25 D depth of field)
    P_D = np.where(valid, 1 / np.where(valid, D, 1), 0)
    q = np.round(P_D / 0.02).astype(int)
    size = 96 if n >= 96 else n
    xp = backend.xp
    lit_x, valid_x, q_x = xp.asarray(lit), xp.asarray(valid), xp.asarray(q)
    channels = [(lam, R["A"][..., c]) for c, lam in enumerate(LASERS)] if color else [(LAM, None)]
    outs, rows, cs = [], [], []
    for ci, (lam, alb) in enumerate(channels):
        src = lit_x if alb is None else lit_x * xp.asarray(alb)
        out = xp.zeros((n, n))
        # longitudinal chromatic aberration (colour mode): the eye focuses green, other lasers are defocused
        Fl = F if not color else 1 / (1 / F - (chromatic_D(lam) - chromatic_D(LASERS[1])))
        for level in np.unique(q[valid]):
            mask = valid & (q == level)
            mask_x = valid_x & (q_x == int(level))
            layer = xp.where(mask_x, src, 0.0)
            if not bool(layer.any()):
                continue
            Dl = 1 / (level * 0.02)
            dl = float(np.median(d[mask]))
            if display == "desk1d":
                p = psf(dl, Dl, Fl, dth, size, lam=lam, col_blur=col / dl, xp=xp)
            elif display == "full2d":
                p = psf(Dl, Dl, Fl, dth, size, lam=lam, xp=xp)
            else:                                            # ordinary 3D screen: light from the panel
                p = psf(dl, dl, Fl, dth, size, lam=lam, xp=xp)
            kern = xp.zeros((n, n))
            h = size // 2
            kern[:size, :size] = p
            kern = xp.roll(kern, (-h, -h), (0, 1))
            out += xp.fft.irfft2(xp.fft.rfft2(layer) * xp.fft.rfft2(kern), s=(n, n))
            if ci == (1 if color else 0):                    # sharpness from the green channel
                ref = mtf15(p, dth) if display == "full2d" else mtf15(psf(Dl, Dl, Fl, dth, size, lam=lam, xp=xp), dth)
                rows.append((float(mask.sum()), mtf15(p, dth), ref, abs(1 / Dl - 1 / F) <= DOF))
        out = np.maximum(backend.to_numpy(out), 0)
        if speckle and display != "screen3d":
            tex, c = speckle_texture(display, k, seed=ci, lam=lam)   # each laser: an independent pattern
            out = _apply_texture(out, tex, dth)
            cs.append(c)
        outs.append(out)
    img = outs[0] if not color else np.stack(outs, -1)
    if color and cs:
        # three independent patterns add in the eye: luminance contrast = sqrt(sum (w_i c_i)^2) for a white surface
        c = float(np.sqrt(sum((w * x) ** 2 for w, x in zip((0.2126, 0.7152, 0.0722), cs))))
    else:
        c = cs[0] if cs else 0.0
    R_ = np.array(rows, float) if rows else np.zeros((1, 4))
    w, m, m2, dof = R_[:, 0], R_[:, 1], R_[:, 2], R_[:, 3] > 0
    sharp = float((w * m).sum() / max((w * m2).sum(), 1e-12))
    in_f = float((w * m)[dof].sum() / max((w * m2)[dof].sum(), 1e-12)) if dof.any() else float("nan")
    share = float(w[dof].sum() / max(w.sum(), 1e-12))
    blocked = float(((~win) & valid).sum() / max(valid.sum(), 1))
    return {"image": img, "focus_m": F, "focus_z_mm": focus_z_mm, "speckle_contrast": c,
            "lasers_nm": [round(l * 1e9) for l, _ in channels],
            "sharpness_vs_2d": sharp, "in_focus_vs_2d": in_f, "in_focus_share": share, "outside_window": blocked, "arcmin_per_px": dth / ARCMIN}


def to_rgb_color(img, gamma=1 / 2.2):
    """R/G/B laser image -> sRGB. The three lasers are taken as the display primaries (their real gamut is wider)."""
    Y = img @ np.array([0.2126, 0.7152, 0.0722])
    hi = np.percentile(Y[Y > 0], 99.5) if (Y > 0).any() else 1.0
    v = np.clip(img / (hi * 1.4), 0, 1) ** gamma
    return (v * 255).astype(np.uint8)


def to_rgb(img, wavelength_nm=530, gamma=0.9):
    """Monochrome laser light shown in its own colour (530 nm green by default)."""
    hi = np.percentile(img[img > 0], 99.8) if (img > 0).any() else 1.0
    v = np.clip(img / hi, 0, 1) ** gamma
    tint = {530: (0.42, 1.0, 0.62), 532: (0.42, 1.0, 0.62), 635: (1.0, 0.32, 0.25), 460: (0.35, 0.55, 1.0)}
    c = tint.get(int(round(wavelength_nm)), (0.42, 1.0, 0.62))
    rgb = np.stack([v * c[0], v * c[1], v * c[2]], -1)
    rgb = rgb + 0.18 * v[..., None] ** 3                     # bright parts whiten a little, like a real laser image
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
