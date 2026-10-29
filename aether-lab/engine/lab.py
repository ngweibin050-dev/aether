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

from . import backend, eye, film, geometry, optics, speckle, window

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
        "eye": [0.0, 0.0, 700.0], "hands": [], "points": 3000, "method": "wrp",
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
                                    state.get("method")], sort_keys=True).encode()).hexdigest()


def _samples(state):
    """Surface points (desk scale, mm) with hidden surfaces removed as seen from the eye."""
    k = "pts" + _scene_key(state)
    if k not in _cache:
        P, N, owner = geometry.sample_surface(state["parts"], int(state["points"]))
        vis = window.visible_from(P, state["eye"]) if len(P) else np.zeros(0, bool)
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
    lo, hi = geometry.bounds([p for p in state["parts"] if p.get("visible", True)])
    return float(lo[2]), float(hi[2])


def _clean(v):
    return [float(x) for x in v]

# ---------------- scene tools ----------------


def add_part(state, type, params=None, name=None, position=(0, 0, 60), rotation=(0, 0, 0),
             scale=(1, 1, 1), parent=None, brightness=1.0):
    if type not in geometry.BUILDERS and type not in ("group", "mesh"):
        raise ValueError(f"unknown part type {type}; use one of {sorted(geometry.BUILDERS)}")
    if parent:
        parent = _find(state, parent)["id"]
    p = _part(type, params, name, _clean(position), _clean(rotation), _clean(scale), parent, brightness)
    geometry.local_mesh(p)          # validate parameters now
    state["parts"].append(p)
    state["selected"] = p["id"]
    _bump(state)
    return {"id": p["id"], "name": p["name"], "parts": len(state["parts"])}


def update_part(state, id, position=None, rotation=None, scale=None, params=None, name=None,
                visible=None, brightness=None, parent="__keep__"):
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


def build_assembly(state, name, parts, position=(0, 0, 70), replace=True):
    """Text-to-CAD: the agent designs an assembly as a list of parametric parts (local to the group)."""
    if replace:
        state["parts"] = []
    group = _part("group", {}, name, _clean(position))
    state["parts"].append(group)
    made = []
    ids = {}
    for spec in parts:
        parent = ids.get(spec.get("parent"), group["id"])
        p = _part(spec["type"], spec.get("params", {}), spec.get("name"), _clean(spec.get("position", [0, 0, 0])),
                  _clean(spec.get("rotation", [0, 0, 0])), _clean(spec.get("scale", [1, 1, 1])), parent,
                  spec.get("brightness", 1.0))
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
            "note": "Parametric approximation built from primitives, not manufacturer CAD data."}


def list_parts(state):
    return {"parts": [{"id": p["id"], "name": p["name"], "type": p["type"], "params": p["params"]
                       if p["type"] != "mesh" else {"faces": len(p["params"]["faces"]) // 3},
                       "position": p["position"], "rotation": p["rotation"], "parent": p.get("parent")}
                      for p in state["parts"]]}


def import_mesh(state, name, vertices, faces, target_faces=4000, position=(0, 0, 60), size_mm=80):
    """Inject an external mesh (e.g. from a GLB or a 3D-generation API): decimate + normalise size."""
    V = np.asarray(vertices, float).reshape(-1, 3)
    F = np.asarray(faces, int).reshape(-1, 3)
    before = len(F)
    V, F = geometry.decimate(V, F, int(target_faces))
    V = V - (V.min(0) + V.max(0)) / 2
    V *= size_mm / max(float(np.ptp(V, axis=0).max()), 1e-9)
    p = _part("mesh", {"vertices": np.round(V, 4).ravel().tolist(), "faces": F.ravel().tolist()},
              name, _clean(position))
    state["parts"].append(p)
    state["selected"] = p["id"]
    _bump(state)
    return {"id": p["id"], "faces_before": before, "faces_after": int(len(F))}


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
        state["eye"][2] = float(view_distance_mm)
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


def set_hands(state, points):
    state["hands"] = [_clean(p) for p in points]
    return {"hand_points": len(state["hands"])}

# ---------------- physics tools ----------------


def make_hologram(state):
    ph, pts, s, c = _hologram(state)
    g = _grid(state)
    return {"points_used": int(len(pts)), "method": state.get("method", "wrp"), "hologram_px": g.n,
            "pitch_um": g.pitch * 1e6, "lab_scale": round(s, 4), "compute": backend.name(),
            "_images": {"hologram": _phase_png(ph)}}


def propagate(state, z_mm=None):
    """Light at scene depth z_mm (default: middle of the object)."""
    lo, hi = _depth_range(state)
    z_mm = (lo + hi) / 2 if z_mm is None else float(z_mm)
    ph, pts, s, c = _hologram(state)
    i = optics.reconstruct(ph, _lab_z(state, z_mm), _grid(state))
    return {"z_mm": round(z_mm, 2), "_images": {"reconstruction": _png(i, crop=0.6)}}


def focus_sweep(state, steps=9):
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


def eye_view(state, eye_x_mm=0.0, eye_y_mm=0.0, focus_z_mm=None):
    """What an eye sees through its pupil (lab scale): parallax, Window Law and focus in one image."""
    ph, pts, s, c = _hologram(state)
    g = _grid(state)
    lo, hi = _depth_range(state)
    focus = (lo + hi) / 2 if focus_z_mm is None else float(focus_z_mm)
    L = (state["display"]["distance_mm"] + 150) * 1e-3          # lab eye 15 cm beyond the object
    ex, ey = eye_x_mm * s * 1e-3, eye_y_mm * s * 1e-3
    img = optics.eye_view(ph, g, (ex, ey), L, _lab_z(state, focus), pupil=min(4e-3, g.size / 2))
    return {"eye_mm": [eye_x_mm, eye_y_mm], "focus_z_mm": round(focus, 1),
            "_images": {"eye": _png(img, crop=0.6)}}


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
    parts = [p for p in state["parts"] if p.get("visible", True)]
    meshes = geometry.scene_meshes(state["parts"])
    rows = []
    for i, (p, V, F) in enumerate(meshes):
        sel = owner == i
        if sel.any():
            rows.append({"part": p["name"], "visible_pct": round(100 * float(ok[sel].mean()), 1)})
    lo, hi = _depth_range(state)
    return {"eye_mm": E, "visible_pct": round(100 * float(ok.mean()), 1) if len(ok) else 0,
            "parts": rows, "height_range_mm": [round(lo, 1), round(hi, 1)],
            "sharp_zone_mm": [-100, 100], "outside_sharp_zone": bool(hi > 100 or lo < -100),
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


def meshes(state):
    """Local meshes for the UI (one geometry source: this file)."""
    out = {}
    for p in state["parts"]:
        V, F = geometry.local_mesh(p)
        if len(V):
            out[p["id"]] = {"v": np.round(V, 3).astype(np.float32).ravel().tolist(), "f": F.ravel().tolist()}
    return out


TOOLS = {f.__name__: f for f in (add_part, update_part, delete_part, clear_scene, build_assembly, list_parts,
                                  import_mesh, set_display, set_eye, set_hands, make_hologram, propagate,
                                  focus_sweep, eye_view, window_check, hand_check, desk_check,
                                  search_column_width, speckle_compare, export_film)}
HEAVY = {"make_hologram", "propagate", "focus_sweep", "eye_view", "desk_check", "search_column_width",
         "speckle_compare"}


def run(state, name, args):
    if name not in TOOLS:
        return {"error": f"unknown tool {name}"}
    try:
        return TOOLS[name](state, **(args or {}))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def for_agent(result):
    return {k: v for k, v in result.items() if not k.startswith("_")}
