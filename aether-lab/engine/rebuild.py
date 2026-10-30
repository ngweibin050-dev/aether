"""One drawing view -> a real 3D mechanism (not a relief).

A single orthographic view gives two coordinates of every part; the third (depth, thickness, axis direction) is
lost. An engineer recovers it from what each part IS. This module does the same, with explicit rules:

- gear      -> involute spur gear; teeth = the count Muse Spark read, checked against the FFT of the traced outline;
               module from the tip radius, snapped to the ISO 54 series; face width b = 8 m (4..25 mm);
               axis = the drawing normal. Gears whose centres sit at m (z1 + z2) / 2 mesh: same layer, centre
               distance snapped exactly, teeth phased so a tooth enters a gap.
- small round (r < 8 mm or pin/bolt/axle) -> pin / shaft seen end-on: cylinder along the normal, through the stack.
- shaft/rod drawn long -> cylinder along its long axis, diameter = traced width.
- wheel/pulley -> traced outline (keeps its spokes and holes) extruded 0.3 r.
- link/lever/arm/crank -> traced outline extruded as a plate, 0.25 x width (3..8 mm).
- spring -> helical coil along its long axis; piston/cylinder -> tube along its long axis.
- frame/plate/housing -> back plate behind the stack + front plate in front (hidden by default so you can look in)
  + four standoffs.
Layers: parts that mesh share a layer; parts whose outlines overlap and do not mesh go to different layers
(greedy graph colouring); layers stack towards the viewer. Coordinates: drawing frame, mm, x right, y up,
z = towards the viewer. The caller rotates the group so the drawing stands upright on the desk.
"""
import re

import numpy as np
from PIL import Image, ImageDraw

from . import geometry

KINDS = {                                  # checked in this order, whole words only ("frame" is not "ram")
    "gear": ("gear", "gears", "pinion", "sprocket", "cog", "rack"),
    "spring": ("spring", "springs"),
    "link": ("link", "links", "lever", "arm", "crank", "beam", "bar", "rocker", "connecting", "linkage"),
    "piston": ("piston", "cylinder", "ram", "plunger"),
    "frame": ("frame", "plate", "housing", "base", "body", "bracket", "support", "casing", "chassis"),
    "wheel": ("wheel", "wheels", "pulley", "disc", "disk", "flywheel", "cam"),
    "shaft": ("shaft", "axle", "rod", "pin", "bolt", "screw", "spindle"),
}


def kind_of(p):
    """Spark's type decides; the label is only a fallback (a "connecting rod" labelled part of type link is a link)."""
    for text in (str(p.get("kind", "")), str(p.get("label", ""))):
        words = set(re.findall(r"[a-z]+", text.lower()))
        for k, ws in KINDS.items():
            if words & set(ws):
                return k
    return "plate" if p.get("elongation", 9) > 1.4 or not p.get("radius_mm") else "wheel"


def _teeth(p):
    """Teeth count: Spark's count if the outline's FFT agrees (or has no clear peak), else the FFT."""
    seen = p.get("teeth_seen")
    fft, strength = p.get("teeth_fft"), p.get("teeth_fft_strength_pct", 0) / 100
    seen = int(seen) if isinstance(seen, (int, float)) and seen >= 6 else None
    if seen and (not fft or strength < 0.01 or abs(fft - seen) <= 0.15 * seen):
        return seen, "read by Muse Spark" + (" (FFT agrees)" if fft and abs(fft - seen) <= 0.15 * seen and strength >= 0.01 else "")
    if fft and strength >= 0.01:
        return int(fft), "FFT of the traced outline" + (f" (Spark said {seen})" if seen else "")
    if seen:
        return seen, "read by Muse Spark"
    tip = p.get("tip_radius_mm") or p.get("radius_mm") or p.get("length_mm", 40) / 2
    m = geometry.snap_module(max(0.5, tip / 11))
    return max(10, int(round(2 * tip / m - 2))), "assumed (no teeth visible)"


def _raster(polys, at, cell=1.0, lo=None, shape=None):
    im = Image.new("1", shape[::-1])
    d = ImageDraw.Draw(im)
    for poly in polys:
        d.polygon([((x + at[0] - lo[0]) / cell, (shape[0] - 1) - (y + at[1] - lo[1]) / cell) for x, y in poly["outer"]], fill=1)
        for h in poly.get("holes", []):
            d.polygon([((x + at[0] - lo[0]) / cell, (shape[0] - 1) - (y + at[1] - lo[1]) / cell) for x, y in h], fill=0)
    return np.array(im)


def mesh_phase(phi1_deg, z1, z2, theta12_deg):
    """Phase (deg) of gear 2 so its teeth enter gear 1's gaps. theta12 = direction gear1 -> gear2."""
    phi1, th = np.radians(phi1_deg), np.radians(theta12_deg)
    d1 = (th - phi1) % (2 * np.pi / z1)
    return float(np.degrees(th + np.pi + np.pi / z2 + d1 * z1 / z2))


def rebuild(parts, drawing_mm):
    """parts: from vision.blueprint_parts (with _poly). Returns (specs for build_assembly, report)."""
    P = []
    for p in parts:
        k = kind_of(p)
        r = p.get("radius_mm") or 0
        if k in ("shaft", "wheel", "plate") and p.get("elongation", 9) < 1.4 and 0 < r < 8:
            k = "pin"
        if k == "shaft" and p.get("elongation", 9) < 1.6:
            k = "pin"
        P.append({**p, "k": k, "at": list(p["centre_mm"]), "polys": p.get("_poly") or []})
    report = {"parts": [], "gear_pairs": [], "notes": []}

    # ---- gears: teeth, module, meshing pairs (snap centre distance), phases
    gears = [g for g in P if g["k"] == "gear"]
    for g in gears:
        g["z"], g["z_src"] = _teeth(g)
        tip = g.get("tip_radius_mm") or g.get("radius_mm") or g["length_mm"] / 2
        g["m"] = geometry.snap_module(2 * tip / (g["z"] + 2))
        g["phase"] = 0.0
    pairs = []
    for i, a in enumerate(gears):
        for b in gears[i + 1:]:
            c = float(np.hypot(b["at"][0] - a["at"][0], b["at"][1] - a["at"][1]))
            m = geometry.snap_module(2 * c / (a["z"] + b["z"])) if c > 0 else a["m"]
            ideal = m * (a["z"] + b["z"]) / 2
            if c > 0 and abs(c - ideal) <= 0.2 * ideal and abs(np.log(m / a["m"])) < 0.5 and abs(np.log(m / b["m"])) < 0.5:
                pairs.append((a, b, m))
    # one module per meshing train; place each gear from the biggest one outward (breadth first)
    done = set()
    for start in sorted(gears, key=lambda g: -g["z"]):
        if id(start) in done:
            continue
        done.add(id(start))
        queue = [start]
        while queue:
            a = queue.pop(0)
            for x, y, m in pairs:
                if a not in (x, y):
                    continue
                b = y if a is x else x
                if id(b) in done:
                    continue
                a["m"] = b["m"] = m
                th = np.degrees(np.arctan2(b["at"][1] - a["at"][1], b["at"][0] - a["at"][0]))
                dist = m * (a["z"] + b["z"]) / 2
                b["at"] = [a["at"][0] + dist * np.cos(np.radians(th)), a["at"][1] + dist * np.sin(np.radians(th))]
                b["phase"] = mesh_phase(a["phase"], a["z"], b["z"], th) % 360
                b["mesh_with"] = a
                done.add(id(b))
                queue.append(b)
                chk = geometry.gear_mesh_check(a["z"], b["z"], m, dist)
                report["gear_pairs"].append({"a": a["n"], "b": b["n"], "module_mm": m, "teeth": [a["z"], b["z"]],
                                             "centre_distance_mm": round(dist, 2), "contact_ratio": chk["contact_ratio"]})

    # ---- thickness of every flat part
    for q in P:
        if q["k"] == "gear":
            q["t"] = float(np.clip(8 * q["m"], 4, 25))
        elif q["k"] == "wheel":
            q["t"] = float(np.clip(0.3 * (q.get("radius_mm") or q["length_mm"] / 2), 5, 20))
        elif q["k"] in ("link", "plate"):
            q["t"] = float(np.clip(0.25 * q["width_mm"], 3, 8))
        elif q["k"] in ("shaft", "spring", "piston"):
            q["t"] = float(max(2.0, q["width_mm"]))
        else:
            q["t"] = 0.0

    # ---- layers: meshing gears together, overlapping parts apart (greedy colouring), biggest first
    layered = [q for q in P if q["k"] not in ("frame", "pin")]
    lo = np.array([-drawing_mm[0] / 2 - 20, -drawing_mm[1] / 2 - 20])
    shape = (int(drawing_mm[1] + 40) + 1, int(drawing_mm[0] + 40) + 1)
    masks = {id(q): _raster(q["polys"], q["at"], 1.0, lo, shape) for q in layered if q["polys"]}
    group = {id(q): id(q) for q in layered}

    def root(i):
        while group[i] != i:
            i = group[i]
        return i

    for a, b, _ in pairs:
        group[root(id(b))] = root(id(a))
    members = {}
    for q in layered:
        members.setdefault(root(id(q)), []).append(q)
    groups = sorted(members.values(), key=lambda g: -sum(float(masks[id(q)].sum()) if id(q) in masks else 0 for q in g))
    layer_of = {}
    layers = []                                  # [[group, ...]]
    for g in groups:
        gm = np.zeros(shape, bool)
        for q in g:
            if id(q) in masks:
                gm |= masks[id(q)]
        for li, L in enumerate(layers):
            if not (L["mask"] & gm).sum() > 2:
                L["mask"] |= gm
                L["parts"] += g
                break
        else:
            layers.append({"mask": gm, "parts": list(g)})
            li = len(layers) - 1
        for q in g:
            layer_of[id(q)] = li
    gap = 1.0
    z = 0.0
    for L in layers:
        L["t"] = max(q["t"] for q in L["parts"])
        L["z"] = z + L["t"] / 2
        z += L["t"] + gap
    stack = max(z - gap, 4.0)

    # ---- specs
    specs = []

    def name(q):
        return f"{q['label']} {q['n']}"

    for q in P:
        k, (x, y) = q["k"], q["at"]
        zc = layers[layer_of[id(q)]]["z"] if id(q) in layer_of else stack / 2
        eng = {"kind": k, "from_drawing": q["label"], "dims": {}, "joints": []}
        if k == "gear":
            spec = {"type": "gear", "params": {"teeth": q["z"], "module": q["m"], "thickness": q["t"], "phase": round(q["phase"], 3),
                                                "bore": round(0.25 * q["m"] * q["z"] / 2, 2)},
                    "position": [x, y, zc]}
            eng["dims"] = {"teeth": [q["z"], q["z_src"]], "module_mm": [q["m"], "tip radius / (z + 2), snapped to ISO 54"],
                           "pitch_diameter_mm": [round(q["m"] * q["z"], 2), "m z"],
                           "face_width_mm": [q["t"], "assumed: 8 x module"]}
            if q.get("mesh_with") is not None:
                eng["joints"].append({"type": "gear_mesh", "with": name(q["mesh_with"])})
        elif k == "pin":
            r = max(1.0, q.get("radius_mm") or q["width_mm"] / 2)
            spec = {"type": "cylinder", "params": {"radius": round(r, 2), "height": round(stack + 16, 1)}, "position": [x, y, stack / 2]}
            eng["dims"] = {"diameter_mm": [round(2 * r, 2), "traced"], "length_mm": [round(stack + 16, 1), "assumed: through the stack and both plates"]}
        elif k in ("shaft", "spring", "piston"):
            a = q["angle_deg"]
            L = q["length_mm"]
            w = q["width_mm"]
            rot = [0, 90, a]                     # local z (axis) -> in-plane direction at angle a
            if k == "shaft":
                spec = {"type": "cylinder", "params": {"radius": round(w / 2, 2), "height": round(L, 1)}}
            elif k == "spring":
                turns = max(4, int(round(L / max(w * 0.45, 1))))
                spec = {"type": "coil", "params": {"radius": round(w / 2 * 0.85, 2), "wire": round(max(0.6, w * 0.08), 2),
                                                     "turns": turns, "pitch": round(L / turns, 2)}}
            else:
                spec = {"type": "tube", "params": {"outer": round(w / 2, 2), "inner": round(w / 2 * 0.85, 2), "height": round(L, 1)}}
            spec.update({"position": [x, y, zc], "rotation": rot})
            eng["dims"] = {"length_mm": [round(L, 1), "traced"], "diameter_mm": [round(w, 1), "traced"]}
        elif k == "frame":
            continue                             # built below, around the stack
        else:                                    # wheel, link, plate: the traced outline with its real holes
            spec = {"type": "outline", "params": {"polygons": q["polys"], "thickness": round(q["t"], 1)}, "position": [x, y, zc]}
            eng["dims"] = {"thickness_mm": [round(q["t"], 1), "assumed from its size"],
                           "outline": ["traced", f"{q['length_mm']} x {q['width_mm']} mm"]}
        spec.update({"name": name(q), "eng": eng})
        specs.append(spec)
        report["parts"].append({"n": q["n"], "label": q["label"], "built_as": k + (f" z={q['z']} m={q['m']}" if k == "gear" else ""),
                                "layer": layer_of.get(id(q))})

    # pins through gears / wheels -> coaxial (fixed) joints
    for s in specs:
        if s["eng"]["kind"] != "pin":
            continue
        for t in specs:
            if t["eng"]["kind"] in ("gear", "wheel", "link", "plate") and \
                    np.hypot(t["position"][0] - s["position"][0], t["position"][1] - s["position"][1]) < 3:
                s["eng"]["joints"].append({"type": "coaxial", "with": t["name"]})
                t["eng"]["joints"].append({"type": "coaxial", "with": s["name"]})
                if t["type"] == "gear":                  # the bore fits the pin
                    t["params"]["bore"] = s["params"]["radius"]

    frames = [q for q in P if q["k"] == "frame"]
    for q in frames:
        t = float(np.clip(0.03 * max(q["length_mm"], q["width_mm"]), 3, 8))
        for side, zf, vis in (("back", -t / 2 - gap - 2, True), ("front", stack + gap + 2 + t / 2, False)):
            specs.append({"name": f"{q['label']} {q['n']} {side}", "type": "outline", "visible": vis,
                          "params": {"polygons": q["polys"], "thickness": round(t, 1)}, "position": [q["at"][0], q["at"][1], zf],
                          "eng": {"kind": "frame", "from_drawing": q["label"], "joints": [],
                                  "dims": {"thickness_mm": [round(t, 1), "assumed"], "outline": ["traced", ""]}}})
        # four standoffs between the plates, inside the outline near its corners
        pts = np.array([pt for poly in q["polys"] for pt in poly["outer"]])
        if len(pts):
            from .outline import _inside
            lo2, hi2 = pts.min(0), pts.max(0)
            for fx, fy in ((0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)):
                c = lo2 + (hi2 - lo2) * [fx, fy]
                if any(_inside(c, np.array(poly["outer"])) and not any(_inside(c, np.array(h)) for h in poly.get("holes", []))
                       for poly in q["polys"]):
                    specs.append({"name": f"standoff {q['n']}-{int(fx * 10)}{int(fy * 10)}", "type": "cylinder",
                                  "params": {"radius": 3.0, "height": round(stack + 2 * gap + 4, 1)},
                                  "position": [float(c[0] + q["at"][0]), float(c[1] + q["at"][1]), stack / 2],
                                  "eng": {"kind": "standoff", "joints": [], "dims": {"diameter_mm": [6.0, "assumed"]}}})
        report["parts"].append({"n": q["n"], "label": q["label"], "built_as": "frame: back + front plate + standoffs"})
    report["layers"] = len(layers)
    report["stack_depth_mm"] = round(stack, 1)
    if frames:
        report["notes"].append("The front frame plate is hidden so you can see the mechanism; show it in the outliner.")
    return specs, report
