"""Snapshots of ONE model, in its own frame (mm), for Muse Spark to look at (the refine self-check) and for the Explain
player (the steps show the real model, never an invented picture).

A painter's-algorithm rasteriser on the CPU: every triangle of the model's parts, far to near, flat-shaded with the
part's colour and its CAD regions' colours (glass, lights ...) exactly as the viewport shows them. Orthographic
cameras named relative to the model's FRONT (a CAD vehicle faces -x; other models face -y, Blender's front view).
Parts can be highlighted (the others greyed) and moved by explode offsets."""
import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from engine import geometry

REGION_DEFAULT = {"glass": "#1d2b3a", "light": "#dfe7ef"}     # as the viewport (Viewport.jsx) and the CAD document
BG = (12, 15, 22)
UP = np.array([0.0, 0.0, 1.0])


def front_axis(model):
    """Unit vector of the model's front in its own frame."""
    f = (model.get("eng") or {}).get("front")
    if f:
        return np.asarray(f, float)
    return np.array([-1.0, 0, 0]) if (model.get("eng") or {}).get("cad_document") else np.array([0.0, -1, 0])


def sides(front):
    """Outward unit normals of the model's six sides: front, rear, left, right (the model's own left and right, as
    seen by someone sitting in it facing the front), top, bottom."""
    f = np.asarray(front, float)
    left = np.cross(UP, f)
    return {"front": f, "rear": -f, "left": left, "right": -left, "top": UP, "bottom": -UP}


def view_dir(name, front):
    s = sides(front)
    if name in s:
        return s[name]
    d = {"iso": s["front"] * 0.75 + s["left"] * 0.75 + UP * 0.65,
         "iso_rear": s["rear"] * 0.75 + s["right"] * 0.75 + UP * 0.65,
         "iso_right": s["front"] * 0.75 + s["right"] * 0.75 + UP * 0.65,
         "iso_low": s["front"] * 0.8 + s["left"] * 0.8 + UP * 0.2}.get(name)
    if d is None:
        raise ValueError(f"unknown view '{name}'")
    return d / np.linalg.norm(d)


def _hex(c, default="#b9c2cc"):
    c = c or default
    try:
        return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], float)
    except (ValueError, IndexError, TypeError):
        return np.array([185, 194, 204], float)


def model_meshes(state, model, offsets=None, include_hidden=False):
    """(part, V (model frame mm), F, per-triangle RGB 0..255) for every visible part under the model."""
    from engine import lab
    by = {p["id"]: p for p in state["parts"]}
    M = geometry.world_matrix(model, by)
    # the model frame keeps the desk's orientation (z up): only the model's position and display scale are taken
    # out, not its rotation (a drawn machine stands up by a 90 deg turn of its group; its "top" is the desk's top)
    t, scale = M[:3, 3], float(np.linalg.norm(M[:3, 0])) or 1.0
    out = []
    for p in lab.subtree(state, model["id"]):
        if p["type"] == "group" or not (include_hidden or _shown(p, by)):
            continue
        V, F = geometry.world_mesh(p, by)
        if not len(V) or not len(F):
            continue
        V = (V - t) / scale
        if offsets and p["id"] in offsets:
            V = V + np.asarray(offsets[p["id"]], float)
        base = _hex(p.get("color"))
        col = np.tile(base, (len(F), 1))
        prm = p.get("params") or {}
        if prm.get("regions") and prm.get("region_names"):
            r = np.asarray(prm["regions"], int)
            if len(r) == len(F):
                for k, nm in enumerate(prm["region_names"], 1):
                    c = (p.get("region_colors") or {}).get(nm) or REGION_DEFAULT.get(nm) or (
                        REGION_DEFAULT["light"] if ("light" in nm or "lamp" in nm) else None)
                    if c:
                        col[r == k] = _hex(c)
        out.append((p, V, np.asarray(F, int), col))
    return out


def model_rotation(state, model):
    """The rotation of the model's group on the desk: a point of the model frame (model_meshes) is R.T @ it in the
    group's own frame, where its parts' positions are."""
    M = geometry.world_matrix(model, {p["id"]: p for p in state["parts"]})
    R = M[:3, :3]
    return R / (np.linalg.norm(R[:, 0]) or 1.0)


def _shown(p, by):
    q = p
    seen = set()
    while q is not None and q["id"] not in seen:
        if q.get("visible", True) is False:
            return False
        seen.add(q["id"])
        q = by.get(q.get("parent"))
    return True


def render(meshes, view="iso", front=(-1, 0, 0), size=512, highlight=None, label=None, ss=2, tint=None, clip=None,
           xray=True, dim=True):
    """One orthographic view of the meshes -> PIL image. highlight: part ids drawn in colour, the rest greyed.
    tint: {part id: "#rrggbb"} drawn in that colour instead of its own (subsystems of an architecture view).
    clip: (unit axis, value): triangles whose centre lies beyond value along the axis are cut away (a section).
    xray: highlighted parts are drawn over everything (a teaching view); False keeps true depth (a check of where
    parts really are: an interior part drawn on top would look as if it stuck out of the body). dim=False keeps the
    other parts in their own colours (the highlight is then only a tint); a clip never cuts a highlighted part."""
    d = view_dir(view, front)
    fw = -d
    upref = np.asarray(front, float) if abs(d @ UP) > 0.95 else UP
    right = np.cross(fw, upref)
    right /= np.linalg.norm(right)
    upc = np.cross(right, fw)
    light = d * 0.55 + UP * 0.6 + right * 0.35
    light /= np.linalg.norm(light)
    allV = np.vstack([V for _, V, _, _ in meshes]) if meshes else np.zeros((1, 3))
    xs, ys = allV @ right, allV @ upc
    span = max(xs.max() - xs.min(), ys.max() - ys.min(), 1e-6)
    n = size * ss
    k = n * 0.86 / span
    cx, cy = (xs.max() + xs.min()) / 2, (ys.max() + ys.min()) / 2
    polys, depth, cols, ontop = [], [], [], []
    hl = set(highlight or [])
    for p, V, F, col in meshes:
        T = V[F]
        nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        ln = np.linalg.norm(nrm, axis=1)
        ok = ln > 1e-12
        T, nrm, c = T[ok], nrm[ok] / ln[ok, None], col[ok]
        if tint and p["id"] in tint:
            c = np.tile(_hex(tint[p["id"]]), (len(T), 1))
        if clip is not None and not (hl and p["id"] in hl):
            keep = T.mean(1) @ np.asarray(clip[0], float) <= clip[1]
            T, nrm, c = T[keep], nrm[keep], c[keep]
            if not len(T):
                continue
        shade = 0.30 + 0.70 * np.abs(nrm @ light)
        c = c * shade[:, None]
        if hl and p["id"] not in hl:
            if dim:
                c = c * 0.25 + np.array([70, 76, 88]) * 0.75
        elif hl:
            c = np.minimum(255, c * 0.72 + np.array([76, 201, 240]) * 0.28 * (0.6 + 0.4 * shade[:, None]))
        px = (T @ right - cx) * k + n / 2
        py = n / 2 - (T @ upc - cy) * k
        polys.append(np.stack([px, py], -1))
        dep = (T @ d).mean(1)
        if (p.get("eng") or {}).get("kind") == "surface_panel":
            # a panel lying 1-3 mm on the body: its triangles are tiny next to the body's, so sorting by centre puts
            # it behind the surface it sits on. The faces turned to the viewer come forward, the others go back.
            dep = dep + np.where(nrm @ d > 0, 1.0, -1.0) * 0.02 * span
        depth.append(dep)
        cols.append(c)
        ontop.append(np.full(len(T), bool(xray) and bool(hl) and p["id"] in hl))
    img = Image.new("RGB", (n, n), BG)
    if polys:
        P = np.concatenate(polys)
        D = np.concatenate(depth)
        C = np.clip(np.concatenate(cols), 0, 255).astype(np.uint8)
        dr = ImageDraw.Draw(img)
        # far first; highlighted parts after everything else (x-ray: never hidden behind the greyed rest)
        for i in np.lexsort((D, np.concatenate(ontop))):
            q = P[i]
            c = tuple(int(v) for v in C[i])
            dr.polygon([(q[0, 0], q[0, 1]), (q[1, 0], q[1, 1]), (q[2, 0], q[2, 1])], fill=c, outline=c)
    img = img.resize((size, size), Image.LANCZOS)
    if label:
        dr = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except OSError:
            font = ImageFont.load_default()
        dr.text((10, 8), label, fill=(150, 220, 255), font=font)
    return img


def sheet(meshes, views=("iso", "front", "left", "iso_rear"), front=(-1, 0, 0), size=360, highlight=None):
    """Several views side by side (2 columns) as one image, each labelled."""
    ims = [render(meshes, v, front, size, highlight, label=v.replace("_", " ")) for v in views]
    cols = 2 if len(ims) > 1 else 1
    rows = (len(ims) + cols - 1) // cols
    out = Image.new("RGB", (cols * size, rows * size), BG)
    for i, im in enumerate(ims):
        out.paste(im, ((i % cols) * size, (i // cols) * size))
    return out


def png_data_url(img, fmt="PNG"):
    import base64
    b = io.BytesIO()
    img.save(b, fmt, **({"quality": 88} if fmt == "JPEG" else {}))
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(b.getvalue()).decode()
