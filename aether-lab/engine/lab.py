"""AETHER 2.0 lab tools: actions the Muse Spark agent, the laptop UI and the hand UI all share.

State is a plain dict (JSON), so the same tool runs locally or on Modal. Scene units: mm.
The hologram panel is the plane z = 0; parts float in front of it (z > 0).

Two scales:
- Desk scale: the real AETHER Desk (598 x 336 mm panel, eye 700 mm away). Window Law, occlusion,
  hand conflicts and the eye-model sharpness are computed at this scale.
- Lab scale: the full wave simulation runs on a small phase hologram (default 1024 x 8 um = 8.2 mm).
  The scene is shrunk uniformly to fit it (the factor is reported), because a desk-size hologram
  has ~3e7 pixels.
"""
import base64
import copy
import hashlib
import io
import json
import uuid

import numpy as np
from PIL import Image

from . import backend, cutaway, eye, film, geometry, optics, retina, speckle, window

DISPLAYS = {
    "lab_slm": {"pitch_um": 8.0, "wavelength_nm": 532.0, "samples": 1024, "distance_mm": 50.0},
    "aether_desk": {"panel_w_mm": 598.0, "panel_h_mm": 336.0, "vertical_pitch_um": 45.0,
                    "column_width_um": 150.0, "view_distance_mm": 700.0, "wavelength_nm": 530.0},
}


def _part(type_, params=None, name=None, position=(0, 0, 60), rotation=(0, 0, 0), scale=(1, 1, 1),
          parent=None, brightness=1.0):
    return {"id": uuid.uuid4().hex[:8], "name": name or type_, "type": type_, "params": params or {},
            "position": list(position), "rotation": list(rotation), "scale": list(scale),
            "parent": parent, "visible": True, "brightness": brightness}


def default_state():
    g = _part("gear", {"teeth": 16, "radius": 30, "thickness": 8}, "Drive gear", (0, 0, 60), (25, 30, 0))
    return {
        "parts": [g], "selected": g["id"], "version": 1,
        "display": copy.deepcopy(DISPLAYS["lab_slm"]), "desk": copy.deepcopy(DISPLAYS["aether_desk"]),
        "eye": [0.0, -450.0, 540.0], "hands": [], "points": 3000, "method": "layers",      # seated, 70 cm from the panel centre, looking down 50 deg
        "view": copy.deepcopy(cutaway.DEFAULT_VIEW),
    }


DEFAULT_STATE = default_state()
_cache = {}

# ---------------- helpers ----------------


def _bump(state):
    state["version"] = state.get("version", 0) + 1


def _find(state, pid):
    for p in state["parts"]:
        if p["id"] == pid or p["name"].lower() == str(pid).lower():
            return p
    raise ValueError(f"no part '{pid}'")


def _grid(state):
    d = state["display"]
    return optics.Grid(int(d["samples"]), d["pitch_um"] * 1e-6, d["wavelength_nm"] * 1e-9)


def _scene_key(state):
    return hashlib.sha1(json.dumps([state["parts"], state["display"], state["eye"], state["points"],
                                    state.get("method"), cutaway.view_of(state)], sort_keys=True).encode()).hexdigest()


def _samples(state):
    """Surface points (desk scale, mm) of the design as shown (exploded, isolated, cut), with hidden
    surfaces removed as seen from the eye. X-ray keeps the hidden ones: the object becomes see-through."""
    k = "pts" + _scene_key(state)
    if k not in _cache:
        P, N, owner = geometry.sample_surface(cutaway.view_parts(state), int(state["points"]))
        keep = cutaway.section_mask(P, state)
        P, owner = P[keep], owner[keep]
        if not len(P):
            vis = np.zeros(0, bool)
        elif cutaway.view_of(state)["xray"]:
            vis = np.ones(len(P), bool)
        else:
            vis = window.visible_from(P, state["eye"])
        _cache[k] = (P, owner, vis)
    return _cache[k]


def _lab_points(state):
    """Shrink the visible scene into the lab hologram's field. Returns metres + scale factor."""
    P, owner, vis = _samples(state)
    P = P[vis]
    if len(P) == 0:
        raise ValueError("scene is empty")
    g = _grid(state)
    lo, hi = P.min(0), P.max(0)
    c = (lo + hi) / 2
    extent = float(max(hi[0] - lo[0], hi[1] - lo[1], 1e-6))
    s = 0.55 * g.size * 1e3 / extent            # mm -> lab mm
    lab = (P - c) * s
    lab[:, 2] += state["display"]["distance_mm"]
    lab[:, 2] = np.maximum(lab[:, 2], 1.0)
    return lab * 1e-3, s, c


def _hologram(state):
    k = "holo" + _scene_key(state)
    if k not in _cache:
        pts, s, c = _lab_points(state)
        g = _grid(state)
        f = {"wrp": optics.wrp_hologram, "points": optics.point_hologram, "layers": optics.layer_hologram}[state.get("method", "wrp")]
        ph = backend.to_numpy(optics.phase_only(f(pts, g)))
        for key in [x for x in _cache if x.startswith("holo")]:
            del _cache[key]
        _cache[k] = (ph, pts, s, c)
    return _cache[k]


def _lab_z(state, z_mm):
    """Scene depth (mm, desk scale) -> lab propagation distance (m)."""
    _, _, s, c = _hologram(state)
    return (state["display"]["distance_mm"] + (z_mm - c[2]) * s) * 1e-3


def _png(a, size=512, gamma=0.5, crop=None):
    a = np.asarray(a, float)
    if crop:
        n = a.shape[0]
        c0 = int(n * (1 - crop) / 2)
        a = a[c0:n - c0, c0:n - c0]
    hi = np.percentile(a, 99.7) or 1.0
    v = (np.clip(a / hi, 0, 1) ** gamma * 255).astype(np.uint8)
    im = Image.fromarray(v).resize((size, size), Image.BILINEAR)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _phase_png(ph, size=512):
    v = ((ph + np.pi) / (2 * np.pi) * 255).astype(np.uint8)
    n = v.shape[0]
    v = v[n // 4:3 * n // 4, n // 4:3 * n // 4]
    buf = io.BytesIO()
    Image.fromarray(v).resize((size, size), Image.NEAREST).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _depth_range(state):
    lo, hi = geometry.bounds([p for p in cutaway.view_parts(state) if p.get("visible", True)])
    v = cutaway.view_of(state)
    if v["section"] == "z":             # the cut removes depth too
        lo[2], hi[2] = (max(lo[2], v["section_mm"]), hi[2]) if v["section_flip"] else (lo[2], min(hi[2], v["section_mm"]))
    return float(lo[2]), float(hi[2])


def _clean(v):
    return [float(x) for x in v]

# ---------------- scene tools ----------------


def add_part(state, type, params=None, name=None, position=(0, 0, 60), rotation=(0, 0, 0),
             scale=(1, 1, 1), parent=None, brightness=1.0, color=None):
    if type not in geometry.BUILDERS and type not in ("group", "mesh"):
        raise ValueError(f"unknown part type {type}; use one of {sorted(geometry.BUILDERS)}")
    if parent:
        parent = _find(state, parent)["id"]
    p = _part(type, params, name, _clean(position), _clean(rotation), _clean(scale), parent, brightness)
    if color:
        p["color"] = retina.hex_color(color)
    geometry.local_mesh(p)          # validate parameters now
    state["parts"].append(p)
    state["selected"] = p["id"]
    _bump(state)
    return {"id": p["id"], "name": p["name"], "parts": len(state["parts"])}


def update_part(state, id, position=None, rotation=None, scale=None, params=None, name=None,
                visible=None, brightness=None, parent="__keep__", color=None):
    p = _find(state, id)
    if position is not None:
        p["position"] = _clean(position)
    if rotation is not None:
        p["rotation"] = _clean(rotation)
    if scale is not None:
        p["scale"] = _clean(scale)
    if params:
        new = {**p["params"], **params}
        geometry.local_mesh({**p, "params": new})
        p["params"] = new
    if name:
        p["name"] = name
    if visible is not None:
        p["visible"] = bool(visible)
    if brightness is not None:
        p["brightness"] = float(brightness)
    if color:
        p["color"] = retina.hex_color(color)
    if parent != "__keep__":
        p["parent"] = _find(state, parent)["id"] if parent else None
    _bump(state)
    return {"id": p["id"], "name": p["name"], "position": p["position"], "rotation": p["rotation"]}


def delete_part(state, id):
    p = _find(state, id)
    drop = {p["id"]}
    changed = True
    while changed:
        changed = False
        for q in state["parts"]:
            if q.get("parent") in drop and q["id"] not in drop:
                drop.add(q["id"])
                changed = True
    state["parts"] = [q for q in state["parts"] if q["id"] not in drop]
    state["selected"] = None
    _bump(state)
    return {"deleted": len(drop), "parts": len(state["parts"])}


def clear_scene(state):
    state["parts"] = []
    state["selected"] = None
    _bump(state)
    return {"parts": 0}


def build_assembly(state, name, parts, position=(0, 0, 70), replace=True, rotation=(0, 0, 0), scale=1.0):
    """Text-to-CAD: the agent designs an assembly as a list of parametric parts (local to the group)."""
    if replace:
        state["parts"] = []
    s_ = float(scale)
    group = _part("group", {}, name, _clean(position), _clean(rotation), [s_, s_, s_])
    state["parts"].append(group)
    made = []
    ids = {}
    for spec in parts:
        parent = ids.get(spec.get("parent"), group["id"])
        p = _part(spec["type"], spec.get("params", {}), spec.get("name"), _clean(spec.get("position", [0, 0, 0])),
                  _clean(spec.get("rotation", [0, 0, 0])), _clean(spec.get("scale", [1, 1, 1])), parent,
                  spec.get("brightness", 1.0))
        if spec.get("color"):
            p["color"] = retina.hex_color(spec["color"])
        if spec.get("eng"):
            p["eng"] = spec["eng"]
        if spec.get("visible") is False:
            p["visible"] = False
        try:
            geometry.local_mesh(p)
        except Exception as e:
            made.append({"name": p["name"], "error": str(e)})
            continue
        state["parts"].append(p)
        ids[p["name"]] = p["id"]
        made.append({"name": p["name"], "type": p["type"]})
    state["selected"] = group["id"]
    _bump(state)
    lo, hi = geometry.bounds(state["parts"])
    return {"assembly": name, "parts": made, "size_mm": _clean(np.round(hi - lo, 1)),
            "note": "Rebuilt from one drawing view: outlines and positions traced, depth rebuilt from what each part is "
                    "(see each part's eng.dims for what was read and what was assumed)."
            if any(sp.get("eng") for sp in parts) else
            "Parametric approximation built from primitives, not manufacturer CAD data."}


def turn_gear(state, id, degrees=15.0):
    """Turn one gear (or the shaft it sits on) and let the whole train follow: meshing gears turn by
    -degrees * z1 / z2 (opposite direction), coaxial parts (gears on the same pin) turn by the same angle.
    Joints come from the drawing rebuild (eng.joints) or from gears whose pitch circles touch."""
    start = _find(state, id)
    by_name = {p["name"]: p for p in state["parts"]}
    gears = [p for p in state["parts"] if p["type"] == "gear"]

    def links(p):
        out = []
        for j in (p.get("eng") or {}).get("joints", []):
            q = by_name.get(j["with"])
            if q is not None:
                out.append((j["type"], q))
        for q in state["parts"]:                       # joints declared on the other side
            for j in (q.get("eng") or {}).get("joints", []):
                if j["with"] == p["name"]:
                    out.append((j["type"], q))
        if p["type"] == "gear" and not out:             # hand-built gears: mesh if pitch circles touch
            for q in gears:
                if q is p or q.get("parent") != p.get("parent"):
                    continue
                m1 = p["params"].get("module") or 2 * p["params"].get("radius", 15) / (p["params"]["teeth"] + 2)
                m2 = q["params"].get("module") or 2 * q["params"].get("radius", 15) / (q["params"]["teeth"] + 2)
                a = (m1 * p["params"]["teeth"] + m2 * q["params"]["teeth"]) / 2
                dist = float(np.linalg.norm(np.subtract(p["position"], q["position"])))
                if abs(dist - a) < 0.1 * a and abs(m1 - m2) < 0.05 * m1:
                    out.append(("gear_mesh", q))
        return out

    turned = {start["id"]: float(degrees)}
    queue = [start]
    while queue:
        p = queue.pop(0)
        for kind, q in links(p):
            if q["id"] in turned:
                continue
            if kind == "gear_mesh" and p["type"] == "gear" and q["type"] == "gear":
                turned[q["id"]] = -turned[p["id"]] * p["params"]["teeth"] / q["params"]["teeth"]
            elif kind == "coaxial":
                turned[q["id"]] = turned[p["id"]]
            else:
                continue
            queue.append(q)
    out = []
    for pid, deg in turned.items():
        q = next(x for x in state["parts"] if x["id"] == pid)
        if q["type"] == "gear":
            q["params"]["phase"] = round((q["params"].get("phase", 0.0) + deg) % 360, 4)
        out.append({"part": q["name"], "turned_deg": round(deg, 2)})
    _bump(state)
    return {"turned": out, "note": "meshing gears: angle x (-z1/z2); same pin: same angle"}


def list_parts(state):
    return {"parts": [{"id": p["id"], "name": p["name"], "type": p["type"], "params": p["params"]
                       if p["type"] != "mesh" else {"faces": len(p["params"]["faces"]) // 3},
                       "position": p["position"], "rotation": p["rotation"], "parent": p.get("parent")}
                      for p in state["parts"]]}


def import_mesh(state, name, vertices, faces, target_faces=4000, position=(0, 0, 60), size_mm=80):
    """Inject an external mesh (GLB, STL/OBJ from CAD, or a 3D-generation API): decimate + centre.
    size_mm > 0 rescales the longest side to that size; size_mm = 0 keeps real CAD units (mm)."""
    V = np.asarray(vertices, float).reshape(-1, 3)
    F = np.asarray(faces, int).reshape(-1, 3)
    before = len(F)
    V, F = geometry.decimate(V, F, int(target_faces))
    V = V - (V.min(0) + V.max(0)) / 2
    if size_mm and float(size_mm) > 0:
        V *= float(size_mm) / max(float(np.ptp(V, axis=0).max()), 1e-9)
    p = _part("mesh", {"vertices": np.round(V, 4).ravel().tolist(), "faces": F.ravel().tolist()},
              name, _clean(position))
    state["parts"].append(p)
    state["selected"] = p["id"]
    _bump(state)
    return {"id": p["id"], "faces_before": before, "faces_after": int(len(F))}


def import_three_view(state, front, top, side, width_mm=80.0, name="three-view part", position=None, voxels=96):
    """Front + top + right-side drawing images (data URLs) -> visual-hull solid at real size (hull.py).
    The front view's width is width_mm; every other size follows from the drawing's own proportions."""
    from . import hull
    V, F, rep = hull.three_view(front, top, side, width_mm, voxels)
    if position is None:                     # stand it on the panel, inside the sharp zone
        position = (0, 0, float(V[:, 2].max()) + 2)
    res = import_mesh(state, name, V.ravel().tolist(), F.ravel().tolist(), 6000, position, 0)
    p = next(x for x in state["parts"] if x["id"] == res["id"])
    p["eng"] = {"kind": "three-view hull", "from_drawing": True,
                "dims": {"width (x)": [rep["size_mm"][0], "given" if width_mm else "assumed"],
                         "depth (y)": [rep["size_mm"][1], "top view proportion"],
                         "height (z)": [rep["size_mm"][2], "front view proportion"]}, "joints": []}
    return {**res, **rep}


def set_display(state, preset=None, pitch_um=None, wavelength_nm=None, samples=None, distance_mm=None,
                column_width_um=None, vertical_pitch_um=None, view_distance_mm=None, points=None, method=None):
    if preset in DISPLAYS:
        state["display" if preset == "lab_slm" else "desk"] = copy.deepcopy(DISPLAYS[preset])
    d, k = state["display"], state["desk"]
    if pitch_um:
        d["pitch_um"] = float(pitch_um)
    if wavelength_nm:
        d["wavelength_nm"] = k["wavelength_nm"] = float(wavelength_nm)
    if samples:
        d["samples"] = int(min(2048, max(256, samples)))
    if distance_mm:
        d["distance_mm"] = float(distance_mm)
    if column_width_um:
        k["column_width_um"] = float(column_width_um)
    if vertical_pitch_um:
        k["vertical_pitch_um"] = float(vertical_pitch_um)
    if view_distance_mm:
        k["view_distance_mm"] = float(view_distance_mm)
        E = np.asarray(state["eye"], float)                  # keep the viewing direction, change the distance
        n = np.linalg.norm(E)
        state["eye"] = _clean(E / n * float(view_distance_mm)) if n > 1 else [0.0, 0.0, float(view_distance_mm)]
    if points:
        state["points"] = int(min(20000, max(300, points)))
    if method in ("wrp", "points", "layers"):
        state["method"] = method
    g = _grid(state)
    return {"lab_slm": d, "aether_desk": k, "points": state["points"], "method": state["method"],
            "hologram_size_mm": round(g.size * 1e3, 2), "max_bend_deg": round(float(np.degrees(g.max_angle)), 3)}


def set_eye(state, x_mm=0.0, y_mm=0.0, z_mm=None):
    state["eye"] = [float(x_mm), float(y_mm), float(z_mm or state["eye"][2])]
    return {"eye_mm": state["eye"]}


def set_view(state, explode=None, section=None, section_mm=None, section_flip=None, isolate=None, xray=None):
    """How to look inside: exploded view, section cut, isolate parts, X-ray. Applies to the 3D view
    AND to the hologram (the hologram is computed from the design as shown)."""
    v = cutaway.view_of(state)
    if explode is not None:
        v["explode"] = float(min(1.0, max(0.0, explode)))
    if section is not None:
        v["section"] = section if section in cutaway.AXES else None
    if section_mm is not None:
        v["section_mm"] = float(section_mm)
    if section_flip is not None:
        v["section_flip"] = bool(section_flip)
    if isolate is not None:
        v["isolate"] = [_find(state, i)["id"] for i in isolate]
    if xray is not None:
        v["xray"] = bool(xray)
    state["view"] = v
    shown = [p for p in cutaway.view_parts(state) if p.get("visible", True) and p["type"] != "group"]
    return {"view": v, "parts_shown": len(shown),
            "hologram_note": "The next hologram is computed from this view: cut faces, exploded spacing and "
                             "X-ray (no hidden-surface removal) all change the light field."}


def set_hands(state, points):
    state["hands"] = [_clean(p) for p in points]
    return {"hand_points": len(state["hands"])}

# ---------------- physics tools ----------------


def _view_hologram(state):
    """Lab phase holograms of the design as the viewer sees it (rendered view -> layers -> sparse groups)."""
    k = "vholo" + _scene_key(state)
    if k not in _cache:
        g = _grid(state)
        R = _render(state, list(state["eye"]))
        I, D = R["I"], R["D"]
        I = np.where(R["window"], I, 0)                      # Window Law: only what the panel can show
        ok = np.isfinite(D) & (I > 0)
        if not ok.any():
            raise ValueError("nothing visible from the eye")
        rr, cc = np.where(ok)
        r0, r1, c0, c1 = rr.min(), rr.max() + 1, cc.min(), cc.max() + 1
        I, D = I[r0:r1, c0:c1], D[r0:r1, c0:c1]
        span = int(0.55 * g.n)                               # the view fills 55 % of the hologram field
        h, w = I.shape
        f = span / max(h, w)
        nh, nw = max(1, int(h * f)), max(1, int(w * f))
        Ii = np.asarray(Image.fromarray(I.astype(np.float32)).resize((nw, nh), Image.BILINEAR))
        Dn = np.nan_to_num(D, nan=0).astype(np.float32)
        Di = np.asarray(Image.fromarray(Dn).resize((nw, nh), Image.NEAREST))
        big_I = np.zeros((g.n, g.n))
        big_D = np.full((g.n, g.n), np.nan)
        y0, x0 = (g.n - nh) // 2, (g.n - nw) // 2
        big_I[y0:y0 + nh, x0:x0 + nw] = Ii
        big_D[y0:y0 + nh, x0:x0 + nw] = np.where(Di > 0, Di, np.nan)
        # lab depth: same scale along and across (scene mm -> lab mm), object centred at distance_mm
        mm_per_px = R["dth"] * float(np.nanmedian(D)) * 1e3 / f
        s = g.pitch * 1e3 / mm_per_px                        # lab mm per scene mm
        Dmid = float(np.nanmedian(big_D))
        Zlab = (state["display"]["distance_mm"] + (Dmid - big_D) * 1e3 * s) * 1e-3
        # depth layers by the eye's tolerance (0.02 D steps of the real desk depth, as in retina), 4..24 layers
        Dv = big_D[np.isfinite(big_D) & (big_D > 0)]
        span_D = float(1 / Dv.min() - 1 / Dv.max()) if len(Dv) else 0.0
        phases = optics.image_hologram(big_I, Zlab, g, k=2, n_layers=int(np.clip(np.ceil(span_D / 0.02), 4, 24)))
        for old in [x for x in _cache if x.startswith("vholo")]:
            del _cache[old]
        _cache[k] = (phases, s, Dmid, int((big_I > 0).sum()))
    return _cache[k]


def make_hologram(state):
    """Lab phase hologram (8 um phase SLM) of the design as the viewer sees it, plus its reconstruction."""
    g = _grid(state)
    phases, s, Dmid, npx = _view_hologram(state)
    z = state["display"]["distance_mm"] * 1e-3
    rec = optics.reconstruct_groups(phases, z, g)
    return {"lit_pixels": npx, "points_used": npx, "method": "rendered view -> depth layers (0.02 D) -> 2x2 sparse groups",
            "scale_note": "small lab-SLM demo, scene shrunk to fit 8 mm; not wave-equivalent to the desk (use desk_wave_view)",
            "subframes": len(phases), "hologram_px": g.n, "pitch_um": g.pitch * 1e6, "lab_scale": round(s, 4),
            "compute": backend.name(),
            "_images": {"hologram": _phase_png(phases[0]), "reconstruction": _png(rec, crop=0.62, gamma=0.8)}}


def propagate(state, z_mm=None):
    """Lab reconstruction at scene height z_mm (default: middle of the object), all subframes averaged."""
    lo, hi = _depth_range(state)
    z_mm = (lo + hi) / 2 if z_mm is None else float(z_mm)
    g = _grid(state)
    phases, s, Dmid, _ = _view_hologram(state)
    E = np.asarray(state["eye"], float)
    lo_, hi_ = geometry.bounds([p for p in cutaway.view_parts(state) if p.get("visible", True)])
    T = (lo_ + hi_) / 2
    t = (E[2] - z_mm) / max(E[2] - T[2], 1e-6)
    Dz = float(np.linalg.norm(T - E) * t) * 1e-3              # eye -> that height along the view
    zlab = (state["display"]["distance_mm"] + (Dmid - Dz) * 1e3 * s) * 1e-3
    rec = optics.reconstruct_groups(phases, zlab, g)
    return {"z_mm": round(z_mm, 2), "_images": {"reconstruction": _png(rec, crop=0.62, gamma=0.8)}}


def _lab_sweep(state, steps=9):
    ph, pts, s, c = _hologram(state)
    g = _grid(state)
    lo, hi = _depth_range(state)
    steps = int(min(15, max(3, steps)))
    zs = np.linspace(lo, hi, steps)
    stack = [optics.reconstruct(ph, _lab_z(state, z), g) for z in zs]
    # share of object points whose light is brightest near each depth
    idx = [g.to_index(p[0], p[1]) for p in pts]
    peaks = np.array([[st[min(max(r, 0), g.n - 1), min(max(cc, 0), g.n - 1)] for r, cc in idx] for st in stack])
    sharp = (peaks / np.maximum(peaks.max(axis=0), 1e-30) > 0.5).mean(axis=1)
    return {"depths_mm": [round(float(z), 1) for z in zs],
            "share_sharp_pct": [round(100 * float(v), 1) for v in sharp],
            "_images": {"sweep": [_png(st, crop=0.6, size=384) for st in stack]}}


def lab_eye_view(state, eye_x_mm=0.0, eye_y_mm=0.0, focus_z_mm=None):
    """Lab-scale check: an eye's pupil looking at the small phase-SLM hologram (true wave propagation)."""
    ph, pts, s, c = _hologram(state)
    g = _grid(state)
    lo, hi = _depth_range(state)
    focus = (lo + hi) / 2 if focus_z_mm is None else float(focus_z_mm)
    L = (state["display"]["distance_mm"] + 150) * 1e-3          # lab eye 15 cm beyond the object
    ex, ey = eye_x_mm * s * 1e-3, eye_y_mm * s * 1e-3
    img = optics.eye_view(ph, g, (ex, ey), L, _lab_z(state, focus), pupil=min(4e-3, g.size / 2))
    return {"eye_mm": [eye_x_mm, eye_y_mm], "focus_z_mm": round(focus, 1),
            "_images": {"eye": _png(img, crop=0.6)}}


# ---------------- what the viewer sees on the AETHER Desk (retina model, theory v9/v11/v12/v13) ----------------

DISPLAY_NAMES = {"desk1d": "AETHER Desk (1D hologram)", "full2d": "full 2D hologram", "screen3d": "ordinary 3D screen"}


def _render(state, eye_xyz):
    key = "ret" + _scene_key(state) + json.dumps(eye_xyz)
    if key not in _cache:
        for old in [x for x in _cache if x.startswith("ret")]:
            del _cache[old]
        _cache[key] = retina.render(state, n=720, eye=eye_xyz)
    return _cache[key]


def _eye_pos(state, eye_x_mm=None, eye_y_mm=None):
    E = list(state["eye"])
    if eye_x_mm is not None:
        E[0] = float(eye_x_mm)
    if eye_y_mm is not None:
        E[1] = float(eye_y_mm)
    return E


def _rgb_png(img, wavelength_nm):
    buf = io.BytesIO()
    Image.fromarray(retina.to_rgb(img, wavelength_nm) if img.ndim == 2 else retina.to_rgb_color(img)).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


IPD_MM = 63.0                                               # adult interpupillary distance (mean)


def _shift_eye(state, E, which):
    """Left / right eye: half the IPD along the viewer's horizontal (perpendicular to the view, in the desk plane)."""
    if which not in ("left", "right"):
        return E
    lo, hi = geometry.bounds([p for p in cutaway.view_parts(state) if p.get("visible", True)])
    f = (lo + hi) / 2 - np.asarray(E, float)
    r = np.cross(f, [0, 0, 1.0])
    r = r / max(np.linalg.norm(r), 1e-9)
    return _clean(np.asarray(E, float) + (1 if which == "right" else -1) * IPD_MM / 2 * r)


def eye_view(state, focus_z_mm=None, display="desk1d", eye_x_mm=None, eye_y_mm=None, speckle=True, k=3, color=True,
             which_eye="centre"):
    """What the viewer's eye sees on the desk, focused at focus_z_mm (height above the panel).
    Wave-optics eye (4 mm pupil) with the 1D-desk wavefronts, Window Law and sparse-group speckle.
    which_eye: centre, left, right (+-31.5 mm), or both (a side-by-side stereo pair: the desk serves each eye its own
    view, which is where binocular depth comes from)."""
    if which_eye == "both":
        L = eye_view(state, focus_z_mm, display, eye_x_mm, eye_y_mm, speckle, k, color, "left")
        Rr = eye_view(state, focus_z_mm, display, eye_x_mm, eye_y_mm, speckle, k, color, "right")
        a = np.asarray(Image.open(io.BytesIO(base64.b64decode(L["_images"]["eye"].split(",", 1)[1]))).convert("RGB"))
        b = np.asarray(Image.open(io.BytesIO(base64.b64decode(Rr["_images"]["eye"].split(",", 1)[1]))).convert("RGB"))
        buf = io.BytesIO()
        Image.fromarray(np.hstack([a, np.zeros((a.shape[0], 8, 3), np.uint8), b])).save(buf, "PNG")
        out = {**L, "which_eye": "both (left | right)", "eye_mm": [L["eye_mm"], Rr["eye_mm"]]}
        out["_images"] = {"eye": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}
        return out
    E = _shift_eye(state, _eye_pos(state, eye_x_mm, eye_y_mm), which_eye)
    R = _render(state, E)
    r = retina.retina(state, focus_z_mm, display, int(k), bool(speckle), rendered=R, color=bool(color))
    return {"display": DISPLAY_NAMES.get(display, display), "eye_mm": E, "focus_z_mm": round(r["focus_z_mm"], 1),
            "lasers_nm": r["lasers_nm"],
            "sharpness_vs_full_2d_pct": round(100 * r["sharpness_vs_2d"], 1),
            "in_focus_vs_full_2d_pct": None if r["in_focus_vs_2d"] != r["in_focus_vs_2d"] else round(100 * r["in_focus_vs_2d"], 1),
            "in_focus_area_pct": round(100 * r["in_focus_share"], 1),
            "sharpness_note": "1D desk vs a full 2D hologram at the same eye focus (100 % = as sharp as a full 2D "
                              "hologram; depth-of-field blur that a real object also has is not counted)",
            "speckle_contrast_pct": round(100 * r["speckle_contrast"], 1),
            "parts_outside_window_pct": round(100 * r["outside_window"], 1),
            "arcmin_per_pixel": round(r["arcmin_per_px"], 2),
            "model": "v9/v13 wave-optics eye, 4 mm pupil, per laser wavelength; v11/v12 speckle; simulation, not a measurement",
            "_images": {"eye": _rgb_png(r["image"], state["desk"]["wavelength_nm"])}}


def desk_wave_view(state, focus_z_mm=None, k=3, encode="none", n=240):
    """True-scale wave simulation of the AETHER Desk (engine/desk_wave.py): the panel's own sub-holograms at 45 um
    pitch, propagated 700 mm to the eye, with incoherent 150 um columns. Also returns the eye-model image of the same
    render for comparison."""
    from . import desk_wave
    E = _eye_pos(state)
    R = _render(state, E)
    w = desk_wave.view(state, focus_z_mm, rendered=R, k=int(k), encode=encode)
    m = retina.retina(state, focus_z_mm, "desk1d", int(k), False, rendered=R, color=False)
    return {"focus_z_mm": round(w["focus_z_mm"], 1), "encode": w["encode"], "subframes": w["k"],
            "projected_pitch_um": w["pitch_projected_um"], "eye_box_mm": w["eye_box_mm"],
            "model": "true-scale 1D wave simulation of the desk panel (vertical: coherent sub-holograms at the real pitch "
                     "and distance; horizontal: incoherent columns). Simulation, not a measurement.",
            "_images": {"wave": _rgb_png(w["image"], 530), "eye_model": _rgb_png(m["image"], 530)}}


def focus_sweep(state, steps=7, display="desk1d", speckle=True, k=3, color=True):
    """The viewer's eye refocusing from the bottom to the top of the design (desk scale)."""
    E = _eye_pos(state)
    R = _render(state, E)
    lo, hi = _depth_range(state)
    steps = int(min(11, max(3, steps)))
    zs = np.linspace(lo, hi, steps)
    imgs, sharp, inf = [], [], []
    for z in zs:
        r = retina.retina(state, float(z), display, int(k), bool(speckle), rendered=R, color=bool(color))
        imgs.append(_rgb_png(r["image"], state["desk"]["wavelength_nm"]))
        sharp.append(round(100 * r["sharpness_vs_2d"], 1))
        inf.append(round(100 * r["in_focus_share"], 1))
    return {"display": DISPLAY_NAMES.get(display, display), "depths_mm": [round(float(z), 1) for z in zs],
            "share_sharp_pct": sharp, "in_focus_area_pct": inf, "lasers_nm": r["lasers_nm"], "speckle_contrast_pct": round(100 * r["speckle_contrast"], 1),
            "parts_outside_window_pct": round(100 * r["outside_window"], 1), "sharpness_note": "share_sharp_pct = 1D desk vs a full 2D hologram at the same eye focus (100 % = as sharp as full "
                              "2D; normal depth-of-field blur is not counted); in_focus_area_pct = share of the visible "
                              "design within the eye's +-0.25 D depth of field at that focus",
            "_images": {"sweep": imgs}}


def lab_focus_sweep(state, steps=9):
    """Lab-scale check: reconstruct the small phase-SLM hologram at several depths (true propagation)."""
    return _lab_sweep(state, steps)


def window_check(state, eye_x_mm=None, eye_y_mm=None):
    """Window Law at desk scale: which parts can the eye actually see through the panel?"""
    P, owner, vis = _samples(state)
    E = list(state["eye"])
    if eye_x_mm is not None:
        E[0] = float(eye_x_mm)
    if eye_y_mm is not None:
        E[1] = float(eye_y_mm)
    k = state["desk"]
    ok = window.window_mask(P, E, k["panel_w_mm"], k["panel_h_mm"])
    vp = cutaway.view_parts(state)
    parts = [p for p in vp if p.get("visible", True)]
    meshes = geometry.scene_meshes(vp)
    rows = []
    for i, (p, V, F) in enumerate(meshes):
        sel = owner == i
        if sel.any():
            rows.append({"part": p["name"], "visible_pct": round(100 * float(ok[sel].mean()), 1)})
    lo, hi = _depth_range(state)
    zone = sharp_zone(state)
    return {"eye_mm": E, "visible_pct": round(100 * float(ok.mean()), 1) if len(ok) else 0,
            "parts": rows, "height_range_mm": [round(lo, 1), round(hi, 1)],
            "sharp_zone_mm": list(zone), "outside_sharp_zone": bool(hi > zone[1] or lo < zone[0]),
            "_mask": ok.tolist(), "_parts_count": len(parts)}


def hand_check(state, hand_radius_mm=9.0):
    if not state["hands"]:
        return {"hand_points": 0, "note": "no hand tracked"}
    P, owner, vis = _samples(state)
    nat, con = window.hand_check(P[vis], state["eye"], state["hands"], hand_radius_mm)
    return {"hand_points": len(state["hands"]), "naturally_hidden_pct": round(100 * float(nat.mean()), 1),
            "depth_conflict_pct": round(100 * float(con.mean()), 1),
            "advice": "Grab from the front or the sides; a hand behind the object erases the parts in front of it."
            if con.any() else "Hand position is safe: no depth conflicts.",
            "_conflict_points": np.round(P[vis][con], 1).tolist()[:400]}


def desk_check(state, heights_cm=(-10, -5, 5, 10, 15), column_width_um=None, view_distance_cm=None):
    k = state["desk"]
    w = (column_width_um or k["column_width_um"]) * 1e-6
    d = (view_distance_cm * 10 if view_distance_cm else k["view_distance_mm"]) * 1e-3
    rows = []
    for h in heights_cm:
        r = eye.desk_sharpness(h * 1e-2, d, w, k["wavelength_nm"] * 1e-9)
        rows.append({"height_cm": h, "sharpness_vs_full_hologram_pct": round(100 * r["relative"], 1),
                     "focus_error_dioptre": round(r["focus_error_D"], 3)})
    lo, hi = _depth_range(state) if state["parts"] else (0, 0)
    return {"column_width_um": w * 1e6, "view_distance_cm": d * 100,
            "eye_box_mm": round(eye.eye_box(k["vertical_pitch_um"] * 1e-6, d) * 1e3, 1), "rows": rows,
            "scene_height_range_cm": [round(lo / 10, 1), round(hi / 10, 1)],
            "note": "Eye model simulation (4 mm pupil, 15 cycles/degree). Not a measurement."}


def search_column_width(state, height_cm=10, min_sharpness_pct=80, view_distance_cm=None):
    k = state["desk"]
    d = (view_distance_cm * 10 if view_distance_cm else k["view_distance_mm"]) * 1e-3
    lam = k["wavelength_nm"] * 1e-9

    def ok(w):
        return 100 * eye.desk_sharpness(height_cm * 1e-2, d, w * 1e-6, lam)["relative"] >= min_sharpness_pct

    tried = []
    lo, hi = 20.0, 1000.0
    if not ok(lo):
        return {"result": "not reachable", "reason": f"even {lo} um columns stay below {min_sharpness_pct}% "
                f"at {height_cm} cm: the limit is the 1D design itself, not pixel size"}
    for _ in range(7):
        mid = (lo + hi) / 2
        good = ok(mid)
        tried.append({"column_width_um": round(mid, 1), "passes": good})
        lo, hi = (mid, hi) if good else (lo, mid)
    return {"largest_column_width_um": round(lo, 1), "height_cm": height_cm,
            "min_sharpness_pct": min_sharpness_pct, "tried": tried}


def _sharpness(state, P):
    """1D-desk sharpness (% of a full 2D hologram) of points P (mm) seen from the real eye position (oblique)."""
    k = state["desk"]
    v, ok = eye.point_sharpness(P, state["eye"], k["column_width_um"] * 1e-6, k["wavelength_nm"] * 1e-9)
    return 100 * v, ok


def sharp_zone(state, target_pct=80, xy_mm=(0.0, 0.0)):
    """Heights (mm) above/below the panel point xy_mm between which the desk stays >= target_pct sharp,
    found by bisection along the panel normal with the real eye position (replaces the fixed +-100 mm)."""
    def good(h):
        return _sharpness(state, [[xy_mm[0], xy_mm[1], h]])[0][0] >= target_pct

    out = []
    for sign in (1, -1):
        lo, hi = 0.0, 300.0 * sign
        if sign > 0:
            hi = min(hi, state["eye"][2] - 50)
        if good(hi):
            out.append(hi)
            continue
        for _ in range(9):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if good(mid) else (lo, mid)
        out.append(lo)
    return round(out[1], 1), round(out[0], 1)


def desk_score(state, target_pct=80, min_visible_pct=95):
    """One score the agent can optimise: is every part sharp on the AETHER Desk and inside the window?
    Per part: its height range, its worst and its area-weighted sharpness (v9 / v13 eye model, best focus, along the
    real line of sight from the seated eye - the eye looks down at the desk, so a point's distance from the panel
    along that line is longer than its height) and the share of it the eye sees through the panel.
    Fast (no images), so it can run every round of a design loop."""
    vp = cutaway.view_parts(state)
    meshes = [(i, p, V) for i, (p, V, F) in enumerate(geometry.scene_meshes(vp)) if len(V)]
    if not meshes:
        return {"error": "scene is empty"}
    vis = {r["part"]: r["visible_pct"] for r in window_check(state)["parts"]}
    S, owner, _ = _samples(state)
    s_sharp, _ = _sharpness(state, S)
    rows, fails = [], 0
    for i, p, V in meshes:
        lo, hi = float(V[:, 2].min()), float(V[:, 2].max())
        sv, ok = _sharpness(state, V)
        sv = np.where(ok, sv, 0)
        j = int(np.argmin(sv))
        sh = round(float(sv[j]), 1)
        sel = owner == i
        mean = round(float(s_sharp[sel].mean()), 1) if sel.any() else sh
        v = vis.get(p["name"], 100.0)
        problems = []
        if sh < target_pct:
            problems.append(f"its point at z = {V[j, 2]:.0f} mm is {sh}% sharp (needs {target_pct}%)")
        if v < min_visible_pct:
            problems.append(f"only {v}% visible through the panel")
        fails += bool(problems)
        rows.append({"part": p["name"], "id": p["id"], "z_mm": [round(lo, 1), round(hi, 1)], "worst_sharpness_pct": sh,
                     "mean_sharpness_pct": mean, "visible_pct": v, "ok": not problems, **({"problems": problems} if problems else {})})
    allV = np.concatenate([V for _, _, V in meshes])
    lo, hi = allV.min(0), allV.max(0)
    size = hi - lo
    zone = sharp_zone(state, target_pct, ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2))
    zmin = min(r["worst_sharpness_pct"] for r in rows)
    hints = []
    if fails:
        if hi[2] > zone[1] or lo[2] < zone[0]:
            room = zone[1] - zone[0]
            if size[2] <= room:
                shift = (zone[0] + zone[1]) / 2 - (lo[2] + hi[2]) / 2 if lo[2] < zone[0] else zone[1] - hi[2]
                hints.append(f"move the whole design by {shift:.0f} mm in z: from this eye the sharp zone is "
                             f"z = {zone[0]:.0f}..{zone[1]:.0f} mm")
            else:
                hints.append(f"the design is {size[2]:.0f} mm tall but the sharp zone is only {room:.0f} mm "
                             f"(z = {zone[0]:.0f}..{zone[1]:.0f}); scale the root group uniformly by about "
                             f"{room / size[2]:.2f} (same factor on x, y and z - never squash one axis)")
        if any(r["visible_pct"] < min_visible_pct for r in rows):
            hints.append("a part sticks out of the window the seated eye sees through (eye at "
                         f"{[round(x) for x in state['eye']]} mm): lower it towards the panel or move it towards the "
                         f"panel centre (panel {state['desk']['panel_w_mm']:.0f} x {state['desk']['panel_h_mm']:.0f} mm)")
    roots = [{"id": p["id"], "name": p["name"], "position": p["position"], "scale": p["scale"]}
             for p in state["parts"] if not p.get("parent")]
    flat = float(size.min() / max(size.max(), 1e-6))
    out = {"pass": fails == 0, "parts_ok": len(rows) - fails, "parts": len(rows), "min_sharpness_pct": zmin,
           "target_pct": target_pct, "design_z_mm": [round(float(lo[2]), 1), round(float(hi[2]), 1)],
           "sharp_zone_mm": list(zone), "size_mm": [round(float(x), 1) for x in size],
           "depth_ratio": round(flat, 2), "rows": rows, "roots": roots, "hints": hints,
           "note": "v9/v13 eye model (4 mm pupil, 15 c/deg, best focus) on the 1D AETHER Desk along the real line of "
                   "sight from the eye; simulation, not a measurement"}
    relief = any(p.get("type") == "profile" for p in state["parts"])
    if relief or flat < 0.06:
        out["relief_warning"] = (f"the design is nearly flat (thinnest side {flat:.0%} of the longest): it is a relief, "
                                 "not a full 3D object; a high score here says nothing about depth")
    return out


def speckle_compare(state, k=3):
    g = optics.Grid(256, state["display"]["pitch_um"] * 1e-6, state["display"]["wavelength_nm"] * 1e-9)
    r = speckle.compare(g, int(min(4, max(2, k))))
    imgs = r.pop("_img")
    out = {a: (round(float(b), 3) if isinstance(b, (float, np.floating)) else b) for a, b in r.items()}
    out["visible_threshold"] = "about 0.03-0.04 for a still image (Verschaffelt 2015)"
    out["_images"] = {"speckle_one": _png(imgs["one"]), "speckle_random": _png(imgs["random"]),
                      "speckle_groups": _png(imgs["groups"])}
    return out


def export_film(state, dpi=2400, film_mm=15, wall_distance_m=2.0, wavelength_nm=650, out_dir="."):
    t = film.target_image(256)
    h = film.binary_fourier_hologram(t)
    pitch = 25.4e-3 / dpi
    info = film.export_png(h, f"{out_dir}/aether_film_{dpi}dpi.png", dpi, film_mm)
    wall = film.predicted_wall(h)
    c = wall.shape[0] // 2
    wall[c - 1:c + 2, c - 1:c + 2] = 0
    info.update({"pattern_width_on_wall_cm": round(100 * film.wall_size(pitch, wavelength_nm * 1e-9, wall_distance_m), 1),
                 "laser": f"red {wavelength_nm:.0f} nm, Class 2 (<1 mW)",
                 "_images": {"predicted_wall": _png(wall), "film_tile": _png(h, gamma=1)}})
    return info


def explode_offsets(state):
    """Per-part offsets at explode = 1 (parent frame, mm); the UI scales them by the explode slider."""
    return cutaway.explode_offsets(state["parts"])


def meshes(state):
    """Local meshes for the UI (one geometry source: this file)."""
    out = {}
    for p in state["parts"]:
        V, F = geometry.local_mesh(p)
        if len(V):
            out[p["id"]] = {"v": np.round(V, 3).astype(np.float32).ravel().tolist(), "f": F.ravel().tolist()}
    return out


TOOLS = {f.__name__: f for f in (add_part, update_part, delete_part, clear_scene, build_assembly, turn_gear, list_parts,
                                  import_mesh, import_three_view, set_display, set_eye, set_view, set_hands, make_hologram, propagate, desk_wave_view,
                                  focus_sweep, eye_view, lab_focus_sweep, lab_eye_view, window_check, hand_check, desk_check,
                                  search_column_width, desk_score, speckle_compare, export_film)}
HEAVY = {"make_hologram", "propagate", "desk_wave_view", "focus_sweep", "eye_view", "lab_focus_sweep", "lab_eye_view", "desk_check", "search_column_width",
         "speckle_compare", "desk_score"}


def run(state, name, args):
    if name not in TOOLS:
        return {"error": f"unknown tool {name}"}
    try:
        return TOOLS[name](state, **(args or {}))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def for_agent(result):
    return {k: v for k, v in result.items() if not k.startswith("_")}
