"""One drawing view -> a real 3D mechanism (not a relief).

A single orthographic view gives two coordinates of every part; the third (depth, thickness, axis direction) is
lost. An engineer recovers it from what each part IS. This module does the same, with explicit rules:

- gear      -> involute spur gear; teeth = the count Muse Spark read, checked against the FFT of the traced outline;
               module from the tip radius, snapped to the ISO 54 series; face width b = 8 m (4..25 mm);
               axis = the drawing normal. Gears whose centres sit at m (z1 + z2) / 2 mesh: same layer, centre
               distance snapped exactly, teeth phased so a tooth enters a gap.
- small round (r < 8 mm or pin/bolt/axle) -> pin / shaft seen end-on: cylinder along the normal, through the stack.
- shaft/rod drawn long -> cylinder along its long axis, diameter = traced width.
- wheel/pulley -> traced outline (keeps its spokes and holes) made solid with rounded rim (inflate), 0.35 r thick, + hub.
- link/lever/arm/crank -> traced outline inflated to a forged arm, 0.5 x width thick, fully rounded edges.
- spring -> helical coil along its long axis; piston/cylinder -> tube along its long axis.
- frame/plate/housing -> a housing: back plate + walls along its outer contour through the machine depth + front plate
  (hidden by default so you can look in). Machine depth = 0.45 x the smaller drawing side (assumed), layers spread
  through it; gears and wheels get hubs.

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


MIN_TEETH = 12          # fewer than ~12 involute teeth is not a working gear (undercut below 17 without shift)


def _teeth(p):
    """Teeth count: Spark's count if the outline's FFT agrees (or has no clear peak), else the FFT. A count below
    MIN_TEETH means the drawing was too fine or too messy to count (spokes or hatching counted instead), so the
    count is then assumed from the size at a typical module (tip radius / 15)."""
    seen = p.get("teeth_seen")
    fft, strength = p.get("teeth_fft"), p.get("teeth_fft_strength_pct", 0) / 100
    seen = int(seen) if isinstance(seen, (int, float)) and seen >= MIN_TEETH else None
    if fft and fft < MIN_TEETH:
        fft = None
    if seen and (not fft or strength < 0.01 or abs(fft - seen) <= 0.15 * seen):
        return seen, "read by Muse Spark" + (" (FFT agrees)" if fft and abs(fft - seen) <= 0.15 * seen and strength >= 0.01 else "")
    if fft and strength >= 0.01:
        return int(fft), "FFT of the traced outline" + (f" (Spark said {seen})" if seen else "")
    if seen:
        return seen, "read by Muse Spark"
    tip = p.get("tip_radius_mm") or p.get("radius_mm") or p.get("length_mm", 40) / 2
    m = geometry.snap_module(max(0.5, tip / 15))
    return max(MIN_TEETH, int(round(2 * tip / m - 2))), "assumed from the size (teeth too fine or unclear to count)"


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


def rebuild(parts, drawing_mm, completion=None, frame_cell_mm=1.0):
    """parts: from vision.blueprint_parts (with _poly). Returns (specs for build_assembly, report).
    completion: Muse Spark's engineering completion of the views the drawing does not show (see agent
    ._spark_complete): machine depth, each part's depth position and thickness, and hidden parts a working machine
    needs (shafts through gears, bearings, spacers, feet). Where it is given it replaces the default rules."""
    comp = completion or {}
    cpart = {int(c["n"]): c for c in comp.get("parts", []) if isinstance(c, dict) and str(c.get("n", "")).isdigit()}
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
    # the machine itself (not the sheet with its margins and title block): the extent of everything read
    ext = np.array([[q["at"][0] - q["length_mm"] / 2, q["at"][1] - q["length_mm"] / 2,
                     q["at"][0] + q["length_mm"] / 2, q["at"][1] + q["length_mm"] / 2] for q in P]) if P else np.zeros((1, 4))
    mach_w = float(min(ext[:, 2].max() - ext[:, 0].min(), drawing_mm[0]))
    mach_h = float(min(ext[:, 3].max() - ext[:, 1].min(), drawing_mm[1]))
    # a plate, block or bracket much smaller than the machine is a part of the mechanism (a slide block, a bearing
    # bracket), not part of the frame: it gets its own layer and thickness instead of running through the depth
    for q in P:
        if q["k"] == "frame" and not re.search(r"housing|casing|frame|body|chassis|base|bed", (q.get("label", "") + " " + str(q.get("kind", ""))).lower()) \
                and q["length_mm"] * q["width_mm"] < 0.12 * mach_w * mach_h:
            q["k"] = "plate"

    # ---- gears: teeth, module, meshing pairs (snap centre distance), phases
    gears = [g for g in P if g["k"] == "gear"]
    for g in gears:
        g["z"], g["z_src"] = _teeth(g)
        tip = g.get("tip_radius_mm") or g.get("radius_mm") or g["length_mm"] / 2
        g["m"], g["m_src"] = geometry.module_for(2 * tip / (g["z"] + 2))     # keeps the drawn size unless ISO 54 is within 3 %
        g["phase"] = 0.0
    pairs = []
    flat = [g for g in gears if not g.get("edge_on")]       # edge-on gears do not mesh in the drawing plane
    for i, a in enumerate(flat):
        for b in flat[i + 1:]:
            c = float(np.hypot(b["at"][0] - a["at"][0], b["at"][1] - a["at"][1]))
            m, m_src = geometry.module_for(2 * c / (a["z"] + b["z"])) if c > 0 else (a["m"], a["m_src"])
            ideal = m * (a["z"] + b["z"]) / 2
            if c > 0 and abs(c - ideal) <= 0.2 * ideal and abs(np.log(m / a["m"])) < 0.5 and abs(np.log(m / b["m"])) < 0.5:
                pairs.append((a, b, m, m_src))
    # one module per meshing train; place each gear from the biggest one outward (breadth first)
    done = set()
    for start in sorted(gears, key=lambda g: -g["z"]):
        if id(start) in done:
            continue
        done.add(id(start))
        queue = [start]
        while queue:
            a = queue.pop(0)
            for x, y, m, m_src in pairs:
                if a not in (x, y):
                    continue
                b = y if a is x else x
                if id(b) in done:
                    continue
                a["m"] = b["m"] = m
                a["m_src"] = b["m_src"] = "meshing pair: centre distance x 2 / (z1 + z2), " + m_src
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
        if q.get("edge_on"):
            q["t"] = float(2 * q["radius_mm"])                # axis in the drawing plane: it spans its diameter in depth
        elif q["k"] == "gear":
            q["t"] = float(np.clip(8 * q["m"], 4, 25))
        elif q["k"] == "wheel":
            q["t"] = float(np.clip(0.35 * (q.get("radius_mm") or q["length_mm"] / 2), 6, 30))
        elif q["k"] == "link":
            q["t"] = float(np.clip(0.5 * q["width_mm"], 5, 20))       # forged arm: about half as thick as wide
        elif q["k"] == "plate":
            q["t"] = float(np.clip(0.3 * min(q["length_mm"], q["width_mm"]), 5, 25))
        elif q["k"] in ("shaft", "spring", "piston"):
            q["t"] = float(max(2.0, q["width_mm"]))
        else:
            q["t"] = 0.0

    for q in P:                                  # Spark's thickness, where it gave one (within sane limits)
        t = (cpart.get(int(q.get("n", 0))) or {}).get("thickness_mm")
        if isinstance(t, (int, float)) and t > 0 and q["k"] not in ("frame", "pin") and not q.get("edge_on"):
            q["t"] = float(np.clip(t, 1.0, 400.0))
            q["t_src"] = "Muse Spark (engineer's completion)"

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

    for a, b, _, _ in pairs:
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
    # machine depth: one view does not show it. Real machines of this kind (gearboxes, presses, engines drawn in side
    # view) are roughly half as deep as they are tall; use that, never less than the parts themselves need, and
    # spread the layers through it (space between layers = bearings, spacers, clearance), so the result has a
    # real third dimension instead of a 2.5D stack.
    for L in layers:
        L["t"] = max(q["t"] for q in L["parts"])
    need = sum(L["t"] for L in layers) + 1.0 * max(len(layers) - 1, 0)
    Wd, Hd = mach_w, mach_h
    depth = float(max(need, np.clip(0.45 * min(Wd, Hd), 30, 300)))
    gap = max(1.0, (depth - sum(L["t"] for L in layers)) / (len(layers) + 1)) if layers else 1.0
    z = gap
    for L in layers:
        L["z"] = z + L["t"] / 2
        z += L["t"] + gap
    stack = max(depth, 4.0)
    report["machine_depth_mm"] = [round(stack, 1), f"assumed: 0.45 x the machine's smaller side ({min(Wd, Hd):.0f} mm); "
                                  "one view does not show depth"]
    D = comp.get("machine_depth_mm")
    if isinstance(D, (int, float)) and D > 0:
        stack = float(max(D, need))
        report["machine_depth_mm"] = [round(stack, 1), "Muse Spark (engineer's completion of the unseen views)"]
    for q in P:                                  # Spark's depth position (centre, mm from the back), clamped inside
        z = (cpart.get(int(q.get("n", 0))) or {}).get("z_mm")
        if isinstance(z, (int, float)) and q["k"] not in ("frame", "pin"):
            q["z_over"] = float(np.clip(z, q["t"] / 2, max(stack - q["t"] / 2, q["t"] / 2)))

    # ---- specs
    specs = []

    def name(q):
        return f"{q['label']} {q['n']}"

    for q in P:
        k, (x, y) = q["k"], q["at"]
        zc = q["z_over"] if "z_over" in q else layers[layer_of[id(q)]]["z"] if id(q) in layer_of else stack / 2
        eng = {"kind": k, "from_drawing": q["label"], "dims": {}, "joints": []}
        if k == "gear":
            spec = {"type": "gear", "params": {"teeth": q["z"], "module": q["m"], "thickness": q["t"], "phase": round(q["phase"], 3),
                                                "bore": round(0.25 * q["m"] * q["z"] / 2, 2)},
                    "position": [x, y, zc]}
            eng["dims"] = {"teeth": [q["z"], q["z_src"]], "module_mm": [q["m"], q.get("m_src", "tip radius / (z + 2)")],
                           "pitch_diameter_mm": [round(q["m"] * q["z"], 2), "m z"],
                           "face_width_mm": [q["t"], "assumed: 8 x module"]}
            if q.get("mesh_with") is not None:
                eng["joints"].append({"type": "gear_mesh", "with": name(q["mesh_with"])})
            if q.get("edge_on"):                 # seen edge-on: face width = the drawn short side, axis in the plane
                spec["params"]["thickness"] = round(float(q["face_mm"]), 1)
                spec["rotation"] = [0, 90, q["axis_deg"]]
                eng["edge_on"] = True
                eng["dims"]["face_width_mm"] = [round(float(q["face_mm"]), 1), "drawn: the gear is seen edge-on"]
                eng["dims"]["axis"] = ["in the drawing plane", q["view_note"]]
        elif k == "wheel" and q.get("edge_on"):  # a disc seen edge-on: diameter = long side, width = short side
            spec = {"type": "cylinder", "params": {"radius": round(float(q["radius_mm"]), 2), "height": round(float(q["face_mm"]), 1)},
                    "position": [x, y, zc], "rotation": [0, 90, q["axis_deg"]]}
            eng["edge_on"] = True
            eng["dims"] = {"diameter_mm": [round(2 * float(q["radius_mm"]), 1), "drawn (long side)"],
                           "width_mm": [round(float(q["face_mm"]), 1), "drawn (short side)"],
                           "axis": ["in the drawing plane", q["view_note"]]}
        elif k == "pin":
            r = max(1.0, q.get("radius_mm") or q["width_mm"] / 2)
            # a pin through a link / disc is that part's pivot: as long as the part plus a collar each side. Only a pin
            # nothing carries runs through the whole stack into both frame plates.
            host = None
            ring = [(x + 1.6 * r * np.cos(a), y + 1.6 * r * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False)]
            pts = [(int(round(shape[0] - 1 - (py - lo[1]))), int(round(px - lo[0]))) for px, py in ring]   # around the bore
            pts = [(a, b) for a, b in pts if 0 <= a < shape[0] and 0 <= b < shape[1]]
            for h in P:
                if id(h) in masks and pts and sum(masks[id(h)][a, b] for a, b in pts) >= 5 and (host is None or h["t"] > host["t"]):
                    host = h
            if host is not None and "measured" in q:
                hz = host["z_over"] if "z_over" in host else layers[layer_of[id(host)]]["z"]
                ln = host["t"] + 2 * max(2.0, 0.6 * r)
                spec = {"type": "cylinder", "params": {"radius": round(r, 2), "height": round(ln, 1)}, "position": [x, y, hz]}
                eng["dims"] = {"diameter_mm": [round(2 * r, 2), q.get("measured", "traced")],
                               "length_mm": [round(ln, 1), f"pivot of {name(host)}: its thickness + a collar each side"]}
                eng["joints"].append({"type": "pivot", "with": name(host)})
            elif "measured" in q:
                # a boss nothing read carries: a stud from the back wall out to the layer of the nearest part
                near = [h for h in P if id(h) in layer_of]
                h = min(near, key=lambda h: np.hypot(h["at"][0] - x, h["at"][1] - y)) if near else None
                zt = (h["z_over"] if "z_over" in h else layers[layer_of[id(h)]]["z"]) + h["t"] / 2 if h else min(stack, 4 * r + 6)
                zt = float(np.clip(zt, 4.0, stack))
                spec = {"type": "cylinder", "params": {"radius": round(r, 2), "height": round(zt + 2, 1)}, "position": [x, y, zt / 2 - 1]}
                eng["dims"] = {"diameter_mm": [round(2 * r, 2), q["measured"]],
                               "length_mm": [round(zt + 2, 1), "assumed: a stud from the back wall to the nearest part's layer"]}
            else:
                spec = {"type": "cylinder", "params": {"radius": round(r, 2), "height": round(stack + 16, 1)}, "position": [x, y, stack / 2]}
                eng["dims"] = {"diameter_mm": [round(2 * r, 2), q.get("measured", "traced")],
                               "length_mm": [round(stack + 16, 1), "assumed: through the stack and both plates"]}
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
        else:                                    # wheel, link, plate: the clean profile with its holes, extruded
            # an exact extrusion of the profile (lines, arcs; vectorised when traced), not the voxelised rounded
            # solid of `inflate`, whose rim was a smoothed voxel staircase
            spec = {"type": "outline", "params": {"polygons": q["polys"], "thickness": round(q["t"], 1)},
                    "position": [x, y, zc]}
            eng["dims"] = {"thickness_mm": [round(q["t"], 1), "assumed from its size"],
                           "outline": ["read by Muse Spark" if q.get("interpreted") else "traced",
                                       f"{q['length_mm']} x {q['width_mm']} mm"]}
        spec.update({"name": name(q), "eng": eng})
        specs.append(spec)
        report["parts"].append({"n": q["n"], "label": q["label"], "built_as": k + (f" z={q['z']} m={q['m']}" if k == "gear" else ""),
                                "layer": layer_of.get(id(q))})

    # hidden parts the engineer adds (the drawing does not show them, a working machine needs them)
    added = []
    for a in (comp.get("added") or [])[:16]:
        try:
            lab_ = str(a.get("label") or a.get("type") or "part")[:40]
            z0, z1 = sorted((float(a.get("z_from_mm", 0)), float(a.get("z_to_mm", stack))))
            z0, z1 = max(z0, -10.0), min(z1, stack + 10.0)
            if z1 - z0 < 0.5:
                continue
            eng = {"kind": "added", "from_drawing": None, "joints": [], "reason": str(a.get("reason") or "")[:160],
                   "dims": {"added_by": ["Muse Spark", "not in the drawing: needed for the machine to work"]}}
            if a.get("type") in ("shaft", "pin", "axle", "spacer", "bearing", "bushing") and a.get("at_mm"):
                x, y = (float(v) for v in a["at_mm"][:2])
                r = float(np.clip(float(a.get("radius_mm", 4)), 0.5, 200))
                spec = {"type": "cylinder", "params": {"radius": round(r, 2), "height": round(z1 - z0, 1)},
                        "position": [x, y, (z0 + z1) / 2]}
                if a.get("type") in ("bearing", "bushing", "spacer"):
                    spec = {"type": "tube", "params": {"outer": round(r, 2), "inner": round(r * 0.55, 2), "height": round(z1 - z0, 1)},
                            "position": [x, y, (z0 + z1) / 2]}
            elif a.get("box_mm"):
                x0_, y0_, x1_, y1_ = (float(v) for v in a["box_mm"][:4])
                w, h = abs(x1_ - x0_), abs(y1_ - y0_)
                if w < 0.5 or h < 0.5:
                    continue
                spec = {"type": "box", "params": {"w": round(w, 1), "d": round(h, 1), "h": round(z1 - z0, 1)},
                        "position": [(x0_ + x1_) / 2, (y0_ + y1_) / 2, (z0 + z1) / 2], "brightness": 0.6}
            else:
                continue
            spec.update({"name": lab_ + " (added)", "eng": eng})
            specs.append(spec)
            added.append({"part": lab_, "reason": eng["reason"]} if eng["reason"] else lab_)
        except (TypeError, ValueError):
            continue
    if added:
        report["added_by_engineer"] = added

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

    # hubs: a gear or wheel sits on its shaft through a hub longer than the rim (keyed / pressed bore)
    for t in [t for t in specs if t["eng"]["kind"] in ("gear", "wheel") and not t["eng"].get("edge_on")]:
        if t["type"] == "gear":
            pr = t["params"]["module"] * t["params"]["teeth"] / 2
            bore = t["params"].get("bore") or 0.25 * pr
            face = t["params"]["thickness"]
        else:
            pts = np.array([pt for poly in t["params"]["polygons"] for pt in poly["outer"]])
            pr = float(np.ptp(pts, axis=0).max()) / 2 if len(pts) else 10
            bore, face = 0.2 * pr, t["params"]["thickness"]
        hr = float(np.clip(1.8 * bore, bore + 2, 0.45 * pr))
        hl = round(face + min(gap, face), 1)
        specs.append({"name": f"{t['name']} hub", "type": "tube", "params": {"outer": round(hr, 2), "inner": round(bore, 2), "height": hl},
                      "position": list(t["position"]),
                      "eng": {"kind": "hub", "from_drawing": t["eng"].get("from_drawing"), "joints": [{"type": "coaxial", "with": t["name"]}],
                              "dims": {"hub_diameter_mm": [round(2 * hr, 1), "assumed: 1.8 x bore"], "hub_length_mm": [hl, "assumed: face + clearance"]}}})
        t["eng"]["joints"].append({"type": "coaxial", "with": f"{t['name']} hub"})

    frames = sorted([q for q in P if q["k"] == "frame"], key=lambda q: -q["length_mm"] * q["width_mm"])
    from . import outline as ol
    # frames and the silhouette are rastered at frame_cell_mm per cell: the drawing's own pixel (the agent passes its
    # scale) keeps a vectorised frame outline within 1.5 drawing px of its trace; 1 mm cells were ~4 px
    fc = float(frame_cell_mm)
    lo2 = np.array([-drawing_mm[0] / 2 - 20, -drawing_mm[1] / 2 - 20])
    shp = (int((drawing_mm[1] + 40) / fc) + 1, int((drawing_mm[0] + 40) / fc) + 1)
    to_drawing = (-lo2[0] / fc, shp[0] - 1 + lo2[1] / fc)

    # Where the mechanism is, seen in the drawing: every non-frame part's silhouette (gears at their real tip circle,
    # pins at their radius). A frame body runs through the whole machine depth, so wherever it overlaps this
    # silhouette it would cut straight through a part. Frames are therefore built only OUTSIDE it, with clearance.
    others = [q for q in P if q["k"] != "frame"]
    occ = np.zeros(shp, bool)
    rings = {"parts": [], "frames": []}       # the same outlines as polygons (drawing mm), for the precision check
    shift = lambda ring, at: [[float(x + at[0]), float(y + at[1])] for x, y in ring]
    for q in others:
        if q["k"] == "gear" and not q.get("edge_on"):
            ra = q["m"] * (q["z"] + 2) / 2
            ring = [[ra * np.cos(t), ra * np.sin(t)] for t in np.linspace(0, 2 * np.pi, 128, endpoint=False)]
            occ |= _raster([{"outer": ring}], q["at"], fc, lo2, shp)
            rings["parts"].append({"kind": q["k"], "ring": shift(ring, q["at"])})
        elif q["k"] == "pin":
            r = max(1.0, q.get("radius_mm") or q["width_mm"] / 2)
            ring = [[r * np.cos(t), r * np.sin(t)] for t in np.linspace(0, 2 * np.pi, 48, endpoint=False)]
            occ |= _raster([{"outer": ring}], q["at"], fc, lo2, shp)
            rings["parts"].append({"kind": q["k"], "ring": shift(ring, q["at"])})
        elif q["polys"]:
            occ |= _raster([{"outer": pl["outer"], "holes": []} for pl in q["polys"]], q["at"], fc, lo2, shp)
            rings["parts"] += [{"kind": q["k"], "ring": shift(pl["outer"], q["at"])} for pl in q["polys"]]
    keep_out = occ.copy()
    for _ in range(int(round(3 / fc))):                  # 3 mm running clearance around every part
        g = keep_out.copy()
        g[1:, :] |= keep_out[:-1, :]
        g[:-1, :] |= keep_out[1:, :]
        g[:, 1:] |= keep_out[:, :-1]
        g[:, :-1] |= keep_out[:, 1:]
        keep_out = g

    def erode(m, n):                                     # n in mm
        for _ in range(int(round(n / fc))):
            e = m.copy()
            e[1:, :] &= m[:-1, :]
            e[:-1, :] &= m[1:, :]
            e[:, 1:] &= m[:, :-1]
            e[:, :-1] &= m[:, 1:]
            m = e
        return m

    frame_mask = np.zeros(shp, bool)
    vec = {}                                             # vectorised frame outlines: largest deviation from the trace
    centres = [q["at"] for q in others]
    for fi, q in enumerate(frames):
        t = float(np.clip(0.03 * max(q["length_mm"], q["width_mm"]), 3, 8))
        solid = ol.fill_holes(_raster([{"outer": pl["outer"], "holes": []} for pl in q["polys"]], q["at"], fc, lo2, shp))
        if solid.sum() * fc * fc <= 50:
            continue
        # does this frame surround the mechanism (a housing) or only sit beside / under it (a base, a bracket)?
        inside = [solid[int(round(shp[0] - 1 - (c[1] - lo2[1]) / fc)), int(round((c[0] - lo2[0]) / fc))]
                  for c in centres if 0 <= (c[0] - lo2[0]) / fc < shp[1] and 0 <= shp[0] - 1 - (c[1] - lo2[1]) / fc < shp[0]]
        encloses = bool(inside) and float(np.mean(inside)) >= 0.6
        eps = max(1.5, 0.01 * max(q["length_mm"], q["width_mm"])) / fc   # cells
        min_cells = max(30, int(30 / (fc * fc)))
        dims = {"thickness_mm": [round(t, 1), "assumed"], "outline": ["traced" if not q.get("interpreted") else "read by Muse Spark", ""]}
        if fi == 0 and encloses:
            # housing: back plate behind the stack, walls along the outer contour through the depth, hidden front
            # plate. The mechanism sits INSIDE it; the walls stay clear of every part.
            for side, zf, vis in (("back", -t / 2 - 2, True), ("front", stack + 2 + t / 2, False)):
                specs.append({"name": f"{q['label']} {q['n']} {side}", "type": "outline", "visible": vis,
                              "params": {"polygons": q["polys"], "thickness": round(t, 1)}, "position": [q["at"][0], q["at"][1], zf],
                              "eng": {"kind": "frame", "from_drawing": q["label"], "joints": [], "dims": dims}})
            body = solid & ~erode(solid, max(3.0, t)) & ~keep_out
            built = "frame: housing around the mechanism (back plate + walls through the depth + hidden front plate)"
        elif re.search(r"base|bed|foot|feet|plinth", q.get("label", "").lower()):
            # base: a solid bed through the machine depth, cut back wherever a part passes in front of it in the
            # drawing, so nothing runs through a part (a machine bed with clearance pockets)
            body = solid & ~keep_out
            built = "frame: base block through the depth, cut clear of every part"
        else:
            # any other frame member (an arch, a column, a side frame): a cast frame is two side plates, one behind
            # and one in front of the mechanism, joined by the housing - not a solid block the depth of the machine
            body = solid & ~keep_out & ~frame_mask
            polys = ol.mask_polygons(body, fc, to_drawing, eps_px=min(eps, 1.0), min_area_px=min_cells, stats=vec) if body.sum() > min_cells else []
            if polys:
                frame_mask |= body
                rings["frames"] += [{"kind": "frame", "ring": [[float(x), float(y)] for x, y in pl["outer"]]} for pl in polys]
                for side, zf, vis in (("back", -t / 2 - 2, True), ("front", stack + 2 + t / 2, False)):
                    specs.append({"name": f"{q['label']} {q['n']} {side} plate", "type": "outline", "visible": vis, "brightness": 0.3,
                                  "params": {"polygons": polys, "thickness": round(t, 1)}, "position": [0.0, 0.0, zf],
                                  "eng": {"kind": "frame", "from_drawing": q["label"], "joints": [], "dims": dims}})
            report["parts"].append({"n": q["n"], "label": q["label"],
                                    "built_as": "frame: side plates behind and in front of the mechanism (front one hidden)"})
            continue
        body &= ~frame_mask
        polys = ol.mask_polygons(body, fc, to_drawing, eps_px=min(eps, 1.0), min_area_px=min_cells, stats=vec) if body.sum() > min_cells else []
        if polys:
            frame_mask |= body
            rings["frames"] += [{"kind": "frame", "ring": [[float(x), float(y)] for x, y in pl["outer"]]} for pl in polys]
            specs.append({"name": f"{q['label']} {q['n']} {'walls' if 'housing' in built else 'block'}", "type": "outline",
                          "brightness": 0.3, "params": {"polygons": polys, "thickness": round(stack + 2 * gap + 4, 1)},
                          "position": [0.0, 0.0, stack / 2],
                          "eng": {"kind": "frame", "from_drawing": q["label"], "joints": [],
                                  "dims": {"wall_mm": [round(max(3.0, t), 1), "assumed"],
                                           "depth_mm": [round(stack, 1), "assumed: machine depth"],
                                           "clearance_mm": [3, "kept around every part"]}}})
        report["parts"].append({"n": q["n"], "label": q["label"], "built_as": built})
    # proof, not a promise: how much frame body still overlaps any part's silhouette (should be 0)
    report["checks"] = {"frame_part_overlap_mm2": int(round((frame_mask & occ).sum() * fc * fc)),
                        "frame_outline_max_dev_mm": round(float(vec.get("max_dev_px", 0.0)) * fc, 3)}
    report["_silhouette"] = {"parts": occ, "frames": frame_mask, "margin_mm": int(round(20 / fc)),   # cells (not sent)
                             "rings_mm": rings}
    report["layers"] = len(layers)
    report["stack_depth_mm"] = round(stack, 1)
    if any("housing" in p["built_as"] for p in report["parts"] if p["built_as"].startswith("frame")):
        report["notes"].append("The front frame plate is hidden so you can see the mechanism; show it in the outliner.")
    return specs, report
