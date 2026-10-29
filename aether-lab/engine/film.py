"""Printable binary hologram for the real-light check (laser pointer + printed film).

A Fourier hologram: lit by a narrow laser beam, its picture appears on a far wall.
The tile repeats across the film so the 2-3 mm laser spot always covers whole tiles;
repeating only samples the picture, it does not move it.
Black film = blocks light (0), clear film = passes light (1).
"""
import numpy as np
from PIL import Image, ImageDraw


def target_image(n=256, kind="gear", teeth=12):
    """Picture to show on the wall, placed off-centre so it clears the bright central spot."""
    img = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(img)
    cx, cy, r = int(n * 0.70), int(n * 0.30), int(n * 0.14)
    if kind == "gear":
        pts = []
        for i in range(teeth * 4):
            a = 2 * np.pi * i / (teeth * 4)
            rr = r if (i % 4) in (0, 1) else int(r * 0.78)
            pts.append((cx + rr * np.cos(a), cy + rr * np.sin(a)))
        d.polygon(pts, fill=255)
        hr = int(r * 0.28)
        d.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=0)
    else:
        d.text((cx - r, cy - 6), kind[:8], fill=255)
    return np.asarray(img, float) / 255


def binary_fourier_hologram(target, iterations=40, seed=0):
    """Iterative binary amplitude hologram whose far field matches `target`."""
    rng = np.random.default_rng(seed)
    n = target.shape[0]
    sig = target > 0
    field = target * np.exp(1j * rng.uniform(0, 2 * np.pi, target.shape))
    for _ in range(iterations):
        h = np.real(np.fft.ifft2(np.fft.ifftshift(field)))
        h = (h > np.median(h)).astype(float)    # half the film clear
        far = np.fft.fftshift(np.fft.fft2(h))
        ph = np.exp(1j * np.angle(far))
        amp = np.abs(far)
        scale = amp[sig].mean() / max(target[sig].mean(), 1e-9)
        new_amp = np.where(sig, target * scale, amp)   # free outside the picture
        field = new_amp * ph
    return h


def predicted_wall(h):
    """Brightness pattern on the far wall (includes the bright centre and the mirror twin)."""
    return np.abs(np.fft.fftshift(np.fft.fft2(h))) ** 2


def wall_size(pitch, wavelength, distance):
    """Width of the whole pattern on the wall: lambda * L / p."""
    return wavelength * distance / pitch


def export_png(h, path, dpi=2400, film_mm=15):
    """Tile the hologram over a film_mm square and save at exact printer resolution."""
    n = h.shape[0]
    pitch_mm = 25.4 / dpi
    total = int(round(film_mm / pitch_mm))
    reps = int(np.ceil(total / n))
    tiled = np.tile(h, (reps, reps))[:total, :total]
    border = int(round(2 / pitch_mm))           # 2 mm black frame to hold the film
    out = np.zeros((total + 2 * border, total + 2 * border), np.uint8)
    out[border:border + total, border:border + total] = (tiled * 255).astype(np.uint8)
    Image.fromarray(out, "L").convert("1").save(path, dpi=(dpi, dpi))
    return {"path": str(path), "dpi": dpi, "pixel_um": pitch_mm * 1000,
            "tile_mm": n * pitch_mm, "film_mm": film_mm}
