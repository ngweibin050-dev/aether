"""AETHER Lab tools: the actions the Muse Spark agent (and the UI) can take.

Every tool is a pure function of (state, args) -> result, so the same code runs on
this computer or on Modal. Units the agent sees are friendly: mm, cm, um, nm.
Images go to the UI only; the agent gets numbers.
"""
import base64
import copy
import hashlib
import io
import json

import numpy as np
from PIL import Image

from . import eye, film, measure, optics, scene

DISPLAYS = {
    # small lab phase modulator: what the full wave simulation runs on
    "lab_slm": {"pitch_um": 8.0, "wavelength_nm": 532.0, "samples": 1024},
    # AETHER Desk (pre-event physics study v13): 1D hologram, eye-tracked
    "aether_desk": {"vertical_pitch_um": 45.0, "column_width_um": 150.0,
                    "view_distance_cm": 70.0, "wavelength_nm": 530.0},
}

DEFAULT_STATE = {
    "objects": [{"type": "gear", "teeth": 12, "radius_mm": 1.5,
                 "rotate_deg": [0, 0, 0], "position_mm": [0, 0, 50]}],
    "display": copy.deepcopy(DISPLAYS["lab_slm"]),
    "desk": copy.deepcopy(DISPLAYS["aether_desk"]),
}

_cache = {}


# ---------- helpers ----------

def _grid(state):
    d = state["display"]
    return optics.Grid(int(d["samples"]), d["pitch_um"] * 1e-6, d["wavelength_nm"] * 1e-9)


def _points(state):
    pts = []
    for o in state["objects"]:
        pts.append(scene.build({
            "type": o.get("type", "gear"),
            "teeth": int(o.get("teeth", 12)),
            "radius": o.get("radius_mm", 1.5) * 1e-3,
            "rotate": o.get("rotate_deg", [0, 0, 0]),
            "position": [v * 1e-3 for v in o.get("position_mm", [0, 0, 50])],
        }))
    return np.vstack(pts)


def _key(state):
    return hashlib.sha1(json.dumps([state["objects"], state["display"]],
                                   sort_keys=True).encode()).hexdigest()


def _hologram(state, method="points"):
    k = _key(state) + method
    if k not in _cache:
        g = _grid(state)
        pts = _points(state)
        u = optics.point_hologram(pts, g) if method == "points" else optics.layer_hologram(pts, g)
        _cache.clear()
        _cache[k] = optics.phase_only(u)
    return _cache[k]


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
    v = v[n // 4:3 * n // 4, n // 4:3 * n // 4]       # zoom so fringes are visible
    buf = io.BytesIO()
    Image.fromarray(v).resize((size, size), Image.NEAREST).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _depth_range(state):
    z = _points(state)[:, 2]
    return float(z.min() * 1e3), float(z.max() * 1e3)


# ---------- tools ----------

def set_scene(state, objects):
    state["objects"] = objects
    lo, hi = _depth_range(state)
    return {"objects": len(objects), "depth_range_mm": [round(lo, 2), round(hi, 2)]}


def move_object(state, index=0, position_mm=None, rotate_deg=None, teeth=None, radius_mm=None):
    o = state["objects"][index]
    if position_mm is not None:
        o["position_mm"] = position_mm
    if rotate_deg is not None:
        o["rotate_deg"] = rotate_deg
    if teeth is not None:
        o["teeth"] = int(teeth)
    if radius_mm is not None:
        o["radius_mm"] = radius_mm
    lo, hi = _depth_range(state)
    return {"object": o, "depth_range_mm": [round(lo, 2), round(hi, 2)]}


def set_display(state, preset=None, pitch_um=None, wavelength_nm=None, samples=None,
                column_width_um=None, vertical_pitch_um=None, view_distance_cm=None):
    if preset == "lab_slm":
        state["display"] = copy.deepcopy(DISPLAYS["lab_slm"])
    if preset == "aether_desk":
        state["desk"] = copy.deepcopy(DISPLAYS["aether_desk"])
    d, k = state["display"], state["desk"]
    if pitch_um:
        d["pitch_um"] = float(pitch_um)
    if wavelength_nm:
        d["wavelength_nm"] = float(wavelength_nm)
        k["wavelength_nm"] = float(wavelength_nm)
    if samples:
        d["samples"] = int(min(2048, max(256, samples)))
    if column_width_um:
        k["column_width_um"] = float(column_width_um)
    if vertical_pitch_um:
        k["vertical_pitch_um"] = float(vertical_pitch_um)
    if view_distance_cm:
        k["view_distance_cm"] = float(view_distance_cm)
    g = _grid(state)
    return {"lab_slm": d, "aether_desk": k,
            "hologram_size_mm": round(g.size * 1e3, 2),
            "max_bend_deg": round(float(np.degrees(g.max_angle)), 3)}


def make_hologram(state, method="points"):
    ph = _hologram(state, method)
    g = _grid(state)
    pts = _points(state)
    return {"points": int(len(pts)), "method": method,
            "hologram_px": g.n, "pitch_um": g.pitch * 1e6,
            "_images": {"hologram": _phase_png(ph)}}


def propagate(state, z_mm):
    g = _grid(state)
    ph = _hologram(state)
    i = optics.reconstruct(ph, z_mm * 1e-3, g)
    pts = _points(state)
    near = np.abs(pts[:, 2] * 1e3 - z_mm) < 0.25
    return {"z_mm": z_mm, "points_in_focus_pct": round(100 * float(near.mean()), 1),
            "_images": {"reconstruction": _png(i, crop=0.6)}}


def focus_sweep(state, z_start_mm=None, z_end_mm=None, steps=9):
    g = _grid(state)
    ph = _hologram(state)
    lo, hi = _depth_range(state)
    pad = max(0.5, 0.2 * (hi - lo))
    z0 = lo - pad if z_start_mm is None else z_start_mm
    z1 = hi + pad if z_end_mm is None else z_end_mm
    steps = int(min(15, max(3, steps)))
    zs = np.linspace(z0, z1, steps)
    stack = optics.focus_sweep(ph, zs * 1e-3, g)
    pts = _points(state)
    idx = [g.to_index(p[0], p[1]) for p in pts]
    peaks = np.array([[measure.peak_near(s, rc, 1) for rc in idx] for s in stack])
    best = zs[np.argmax(peaks, axis=0)]
    err = np.abs(best - pts[:, 2] * 1e3)
    sharp = (peaks / peaks.max(axis=0) > 0.5).mean(axis=1)
    return {
        "depths_mm": [round(float(z), 2) for z in zs],
        "share_of_object_sharp_pct": [round(100 * float(s), 1) for s in sharp],
        "median_depth_error_mm": round(float(np.median(err)), 3),
        "_images": {"sweep": [_png(s, crop=0.6, size=384) for s in stack]},
    }


def desk_check(state, heights_cm=(-10, -5, 5, 10, 15), column_width_um=None,
               view_distance_cm=None):
    k = state["desk"]
    w = (column_width_um or k["column_width_um"]) * 1e-6
    d = (view_distance_cm or k["view_distance_cm"]) * 1e-2
    rows = []
    for h in heights_cm:
        r = eye.desk_sharpness(h * 1e-2, d, w, k["wavelength_nm"] * 1e-9)
        rows.append({"height_cm": h, "sharpness_vs_full_hologram_pct": round(100 * r["relative"], 1),
                     "focus_error_dioptre": round(r["focus_error_D"], 3)})
    return {"column_width_um": w * 1e6, "view_distance_cm": d * 100,
            "eye_box_mm": round(eye.eye_box(k["vertical_pitch_um"] * 1e-6, d) * 1e3, 1),
            "rows": rows,
            "note": "Eye model simulation (4 mm pupil, 15 cycles/degree). Not a measurement."}


def search_column_width(state, height_cm=10, min_sharpness_pct=80, view_distance_cm=None):
    k = state["desk"]
    d = (view_distance_cm or k["view_distance_cm"]) * 1e-2
    lam = k["wavelength_nm"] * 1e-9

    def ok(w):
        return 100 * eye.desk_sharpness(height_cm * 1e-2, d, w * 1e-6, lam)["relative"] >= min_sharpness_pct

    tried = []
    lo, hi = 20.0, 1000.0
    if not ok(lo):
        return {"result": "not reachable", "reason": f"even {lo} um columns stay below "
                f"{min_sharpness_pct}% at {height_cm} cm: the limit is the 1D design itself, not pixel size"}
    for _ in range(7):
        mid = (lo + hi) / 2
        good = ok(mid)
        tried.append({"column_width_um": round(mid, 1), "passes": good})
        lo, hi = (mid, hi) if good else (lo, mid)
    return {"largest_column_width_um": round(lo, 1), "height_cm": height_cm,
            "min_sharpness_pct": min_sharpness_pct, "tried": tried}


def measure_speckle(state, frames=16):
    """Speckle of an evenly lit diffuse patch: one frame vs the average of `frames` frames."""
    g = optics.Grid(256, 8e-6, state["display"]["wavelength_nm"] * 1e-9)
    xs = np.arange(-40, 41) * g.pitch
    X, Y = np.meshgrid(xs, xs)
    pts = np.stack([X.ravel(), Y.ravel(), np.full(X.size, 0.03)], 1)
    rc = g.to_index(0, 0)
    mask = np.zeros((g.n, g.n), bool)
    mask[rc[0] - 30:rc[0] + 30, rc[1] - 30:rc[1] + 30] = True
    frames = int(min(32, max(1, frames)))
    acc = np.zeros((g.n, g.n))
    one = None
    for f in range(frames):
        ph = optics.phase_only(optics.layer_hologram(pts, g, 1, rng=np.random.default_rng(f)))
        i = optics.reconstruct(ph, 0.03, g)
        # blur to the spacing of the points, like an eye that cannot resolve finer detail
        k = np.ones(3) / 3
        i = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 1, i)
        i = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 0, i)
        one = i if one is None else one
        acc += i
    c1 = measure.speckle_contrast(one, mask)
    cn = measure.speckle_contrast(acc / frames, mask)
    return {"contrast_one_frame": round(c1, 3), "frames": frames,
            "contrast_averaged": round(cn, 3), "expected_1_over_sqrt_n": round(c1 / np.sqrt(frames), 3),
            "visible_threshold": "about 0.03-0.04 (literature, still image)",
            "_images": {"one_frame": _png(one * mask), "averaged": _png(acc * mask)}}


def export_film(state, dpi=2400, film_mm=15, wall_distance_m=2.0, wavelength_nm=650, out_dir="."):
    t = film.target_image(256)
    h = film.binary_fourier_hologram(t)
    pitch = 25.4e-3 / dpi
    info = film.export_png(h, f"{out_dir}/aether_film_{dpi}dpi.png", dpi, film_mm)
    wall = film.predicted_wall(h)
    c = wall.shape[0] // 2
    wall[c - 1:c + 2, c - 1:c + 2] = 0
    info.update({"pattern_width_on_wall_cm": round(100 * film.wall_size(pitch, wavelength_nm * 1e-9,
                                                                       wall_distance_m), 1),
                 "laser": f"red {wavelength_nm:.0f} nm, Class 2 (<1 mW)",
                 "_images": {"predicted_wall": _png(wall), "film_tile": _png(h, gamma=1)}})
    return info


TOOLS = {f.__name__: f for f in (set_scene, move_object, set_display, make_hologram, propagate,
                                  focus_sweep, desk_check, search_column_width, measure_speckle,
                                  export_film)}


def run(state, name, args):
    if name not in TOOLS:
        return {"error": f"unknown tool {name}"}
    try:
        return TOOLS[name](state, **(args or {}))
    except Exception as e:  # report to the agent instead of crashing the session
        return {"error": f"{type(e).__name__}: {e}"}


def for_agent(result):
    """Strip images: the agent reasons over numbers only."""
    return {k: v for k, v in result.items() if not k.startswith("_")}
