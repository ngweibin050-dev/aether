"""Software rendering of tessellated B-rep (preview images and orthographic projections). numpy + PIL only."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw


def _raster(P2, F, depth, shade, W, H, colours=None, bg=(250, 250, 252)):
    """z-buffered flat triangles. P2 (n,2) pixel coords, depth (n,) larger = nearer, shade (m,) 0..1 per triangle."""
    img = np.zeros((H, W, 3), float) + np.array(bg, float)
    zb = np.full((H, W), -np.inf)
    for t in range(len(F)):
        a, b, c = F[t]
        xs = P2[[a, b, c], 0]
        ys = P2[[a, b, c], 1]
        x0, x1 = max(int(np.floor(xs.min())), 0), min(int(np.ceil(xs.max())), W - 1)
        y0, y1 = max(int(np.floor(ys.min())), 0), min(int(np.ceil(ys.max())), H - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = P2[a], P2[b], P2[c]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if not inside.any():
            continue
        z = l1 * depth[a] + l2 * depth[b] + l3 * depth[c]
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        win = inside & (z > sub)
        sub[win] = z[win]
        col = np.array(colours[t] if colours is not None else (180, 190, 205), float)
        img[y0:y1 + 1, x0:x1 + 1][win] = col * (0.35 + 0.65 * shade[t])
    return img.clip(0, 255).astype(np.uint8), np.isfinite(zb)


def shaded(parts, view_dir=(-1.0, -1.4, 0.9), up=(0, 0, 1), W=1100, H=650, margin=0.06, edges=None, ss=2):
    """parts: [(V, F, rgb)] in mm. Orthographic shaded view from view_dir (camera looks along -view_dir).
    Painter's algorithm (triangles sorted far to near, filled by PIL), supersampled ss x. edges: optional (n,6)
    segments drawn on top (B-rep edges)."""
    d = np.asarray(view_dir, float)
    d /= np.linalg.norm(d)
    upv = np.asarray(up, float)
    if abs(np.dot(upv, d)) > 0.999:
        upv = np.array([0, 1.0, 0])
    r = np.cross(upv, d)
    r /= np.linalg.norm(r)
    u = np.cross(d, r)
    allV = np.vstack([p[0] for p in parts])
    P = np.c_[allV @ r, allV @ u]
    lo, hi = P.min(0), P.max(0)
    s = (1 - 2 * margin) * min(W / max(hi[0] - lo[0], 1e-9), H / max(hi[1] - lo[1], 1e-9)) * ss
    off = np.array([W, H]) * ss / 2 - s * (lo + hi) / 2
    light = np.array([0.35, -0.45, 0.82]) + 0.6 * d
    light /= np.linalg.norm(light)
    polys, depth, cols = [], [], []
    for V, F, rgb in parts:
        if not len(F):
            continue
        T = V[F]
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        facing = n @ d
        shade = 0.25 + 0.55 * np.clip(n @ light, 0, 1) + 0.2 * np.clip(facing, 0, 1)
        P2 = np.stack([T @ r, T @ u], -1) * s + off
        P2[..., 1] = H * ss - P2[..., 1]
        polys.append(P2)
        depth.append((T @ d).mean(1))
        cols.append(np.clip(np.asarray(rgb, float)[None] * shade[:, None], 0, 255))
    P2 = np.concatenate(polys)
    D = np.concatenate(depth)
    Cc = np.concatenate(cols).astype(int)
    im = Image.new("RGB", (W * ss, H * ss), (246, 247, 250))
    dr = ImageDraw.Draw(im)
    for k in np.argsort(D):
        dr.polygon([tuple(p) for p in P2[k]], fill=tuple(Cc[k]))
    if edges is not None and len(edges):
        E = np.asarray(edges, float)
        a = np.c_[E[:, :3] @ r, E[:, :3] @ u] * s + off
        b = np.c_[E[:, 3:] @ r, E[:, 3:] @ u] * s + off
        da = E[:, :3] @ d
        for k in range(len(E)):
            dr.line([(a[k, 0], H * ss - a[k, 1]), (b[k, 0], H * ss - b[k, 1])], fill=(30, 40, 55), width=ss)
    return im.resize((W, H), Image.LANCZOS)


def ortho_mask(V, F, to_px, W, H):
    """Filled silhouette of triangles projected with to_px(V) -> (n,2) pixel coords, on a W x H canvas (4x AA)."""
    k = 4
    im = Image.new("L", (W * k, H * k), 0)
    d = ImageDraw.Draw(im)
    P = to_px(V) * k
    for a, b, c in F:
        d.polygon([tuple(P[a]), tuple(P[b]), tuple(P[c])], fill=255)
    return np.asarray(im.resize((W, H), Image.BOX)) >= 128
