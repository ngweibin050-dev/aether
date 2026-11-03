"""Mechanical assembly -> exact OpenCascade B-rep: one solid per scene part, built from the part's own parameters.

The machine rebuilt from a drawing (engine/rebuild.py) is a list of parametric parts. This module turns each one into
the solid it describes, never from its display mesh:

- cylinder / tube / cone / sphere / torus / box: OpenCascade primitives (exact circles, planes, cones);
- gear: involute spur gear; each flank is a B-spline interpolated through the involute of the base circle, tip and
  root are circular arcs, the bore is a true circle;
- coil: a circular wire swept along a true helix;
- outline (a part traced from the drawing): its polygon extruded; a ring of points that fits a circle within 2 % of
  its radius is replaced by that exact circle (bores, wheels, bosses), the rest stays the traced polygon;
- pipe / profile / nozzle / blade ring: sweep, fused blocks, revolution, fused blades.
A part type that has no exact B-rep (an inflated sketch, an imported triangle mesh) is reported as not built; it is
never approximated silently.

Then, on the world-placed solids: BRepCheck validity and mass properties per part (validate.check_solid), contact and
interference for every pair whose boxes touch (BRepExtrema distance, Boolean common volume), and the assembly mates,
each one measured: Coaxial (axis angle and offset), Concentric pin-in-bore (clearance), Gear mesh (centre distance
against m (z1 + z2) / 2, contact ratio), Planar face-to-face contact.
"""
from __future__ import annotations

import math
import time

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (BRepBuilderAPI_GTransform, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform)
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder,
                             BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol, BRepPrimAPI_MakeSphere,
                             BRepPrimAPI_MakeTorus)
from OCP.GC import GC_MakeArcOfCircle
from OCP.GeomAPI import GeomAPI_Interpolate
from OCP.GProp import GProp_GProps
from OCP.ShapeFix import ShapeFix_Shape
from OCP.TColgp import TColgp_HArray1OfPnt
from OCP.TopoDS import TopoDS, TopoDS_Shape
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_GTrsf, gp_Mat, gp_Pnt, gp_Trsf, gp_Vec, gp_XYZ

from engine import geometry as G

from . import validate as Vd

CIRCLE_FIT = 0.02            # a traced ring is an exact circle when every point is within 2 % of the fitted radius
CONTACT_MM = 0.02            # two solids closer than this touch
INTERFERE_MM3 = 1e-3         # common volume above this is interference
AXIS_DEG = 0.5               # axes within this angle are parallel
AXIS_MM = 0.05               # ... and coaxial when their lines are this close

# subassemblies of the STEP / tree, by the engineering kind the rebuild gave each part
GROUPS = [("frame", "Frame & plates", ("frame", "plate", "block", "base", "housing")),
          ("shafts", "Shafts, pins & bolts", ("shaft", "pin", "bolt", "axle")),
          ("gears", "Gear train", ("gear", "pinion", "rack", "wheel", "hub", "pulley")),
          ("linkage", "Linkage", ("link", "crank", "lever", "rod", "piston", "cam", "slider")),
          ("springs", "Springs", ("spring", "coil")),
          ("inferred", "Inferred by Muse Wonder (not on the drawing)", ("added",)),
          ("other", "Other parts", ())]


# ------------------------------------------------------------------------------------------------ local builders
def _P(x, y, z=0.0):
    return gp_Pnt(float(x), float(y), float(z))


def _ax(z0=0.0):
    return gp_Ax2(gp_Pnt(0, 0, float(z0)), gp_Dir(0, 0, 1))


def _fit_circle(P):
    """Algebraic circle fit of a closed ring (n, 2) -> (cx, cy, r) if every point is within CIRCLE_FIT r and the
    points go all the way round, else None."""
    P = np.asarray(P, float)
    if len(P) < 8:
        return None
    A = np.c_[2 * P, np.ones(len(P))]
    b = (P ** 2).sum(1)
    (cx, cy, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    r = math.sqrt(max(c + cx * cx + cy * cy, 0.0))
    if r <= 1e-6:
        return None
    d = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    if np.max(np.abs(d - r)) > CIRCLE_FIT * r:
        return None
    ang = np.sort(np.arctan2(P[:, 1] - cy, P[:, 0] - cx))
    gaps = np.diff(np.r_[ang, ang[0] + 2 * np.pi])
    if gaps.max() > np.pi / 3:                     # an arc, not a full ring
        return None
    return float(cx), float(cy), float(r)


def _ring_wire(ring, z, rec):
    """A closed planar wire at height z: the exact circle when the ring is one, else the traced polygon."""
    fit = _fit_circle(ring)
    if fit:
        cx, cy, r = fit
        rec["circles"].append({"centre": [cx, cy], "radius": r})
        e = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(_P(cx, cy, z), gp_Dir(0, 0, 1)), r)).Edge()
        return BRepBuilderAPI_MakeWire(e).Wire(), fit
    pts = np.asarray(ring, float)
    keep = [pts[0]]
    for q in pts[1:]:
        if np.hypot(*(q - keep[-1])) > 1e-4:
            keep.append(q)
    if np.hypot(*(keep[-1] - keep[0])) <= 1e-4:
        keep.pop()
    poly = BRepBuilderAPI_MakePolygon()
    for x, y in keep:
        poly.Add(_P(x, y, z))
    poly.Close()
    rec["polygon_edges"] += len(keep)
    return poly.Wire(), None


def _prism(outer_wire, hole_wires, thickness):
    """Planar face (outer + holes) at z = -t/2 extruded by t, fixed (wire orientation) by ShapeFix."""
    mf = BRepBuilderAPI_MakeFace(outer_wire, True)
    for h in hole_wires:
        mf.Add(TopoDS.Wire_s(h.Reversed()))
    fix = ShapeFix_Shape(mf.Face())
    fix.Perform()
    face = fix.Shape()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, float(thickness))).Shape()


def _fuse(shapes):
    shapes = [s for s in shapes if s is not None and not s.IsNull()]
    if not shapes:
        return None
    out = shapes[0]
    for s in shapes[1:]:
        f = BRepAlgoAPI_Fuse(out, s)
        f.Build()
        out = f.Shape()
    return out


def b_cylinder(rec, radius=5, height=10, **_):
    rec["exact"] = "cylinder"
    return BRepPrimAPI_MakeCylinder(_ax(-height / 2), float(radius), float(height)).Shape()


def b_tube(rec, outer=5, inner=3, height=10, **_):
    rec["exact"] = "annulus prism (two exact circles)"
    o = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(_ax(-height / 2), float(outer))).Edge()).Wire()
    i = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(_ax(-height / 2), float(inner))).Edge()).Wire()
    rec["circles"] += [{"centre": [0, 0], "radius": float(outer)}, {"centre": [0, 0], "radius": float(inner), "hole": True}]
    return _prism(o, [i], height)


def b_box(rec, w=10, d=10, h=10, **_):
    rec["exact"] = "box"
    return BRepPrimAPI_MakeBox(_P(-w / 2, -d / 2, -h / 2), float(w), float(d), float(h)).Shape()


def b_cone(rec, r_bottom=5, r_top=0.01, height=10, **_):
    rec["exact"] = "cone"
    return BRepPrimAPI_MakeCone(_ax(-height / 2), float(r_bottom), float(max(r_top, 0.0)), float(height)).Shape()


def b_sphere(rec, radius=5, **_):
    rec["exact"] = "sphere"
    return BRepPrimAPI_MakeSphere(float(radius)).Shape()


def b_torus(rec, radius=10, tube_radius=2, **_):
    rec["exact"] = "torus"
    return BRepPrimAPI_MakeTorus(_ax(), float(radius), float(tube_radius)).Shape()


def _bspline(pts):
    arr = TColgp_HArray1OfPnt(1, len(pts))
    for i, p in enumerate(pts, 1):
        arr.SetValue(i, p)
    it = GeomAPI_Interpolate(arr, False, 1e-7)
    it.Perform()
    return BRepBuilderAPI_MakeEdge(it.Curve()).Edge()


def _arc(a, m, b):
    return BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(a, m, b).Value()).Edge()


def b_gear(rec, teeth=12, radius=None, thickness=5, module=None, pressure_angle=20.0, bore=None, phase=0.0, **_):
    """Involute spur gear (same tooth definition as engine.geometry.gear_profile): B-spline flanks on the involute,
    arc tips and roots, radial flank below the base circle, exact bore."""
    z = max(6, int(round(teeth)))
    m = float(module) if module is not None else 2 * float(radius if radius is not None else 15) / (z + 2)
    al = math.radians(pressure_angle)
    r = m * z / 2
    rb, ra, rf = r * math.cos(al), r + m, r - 1.25 * m
    inv = lambda a: math.tan(a) - a
    half = lambda R: math.pi / (2 * z) + inv(al) - inv(math.acos(min(1.0, rb / R)))
    z0 = -float(thickness) / 2
    R0 = max(rb, rf)
    Rs = np.linspace(R0, ra, 12)
    pol = lambda R, t: _P(R * math.cos(t), R * math.sin(t), z0)
    h0, ht = half(R0), half(ra)
    wire = BRepBuilderAPI_MakeWire()
    for k in range(z):
        c = math.radians(phase) + 2 * math.pi * k / z
        right = [pol(R, c - half(R)) for R in Rs]
        left = [pol(R, c + half(R)) for R in Rs[::-1]]
        if rf < rb:
            wire.Add(BRepBuilderAPI_MakeEdge(pol(rf, c - h0), right[0]).Edge())
        wire.Add(_bspline(right))
        wire.Add(_arc(right[-1], pol(ra, c), left[0]))
        wire.Add(_bspline(left))
        start = pol(rf, c + h0) if rf < rb else left[-1]
        if rf < rb:
            wire.Add(BRepBuilderAPI_MakeEdge(left[-1], start).Edge())
        cn = c + 2 * math.pi / z
        nxt = pol(rf, cn - h0) if rf < rb else pol(R0, cn - half(R0))
        wire.Add(_arc(start, pol(rf, c + math.pi / z), nxt))
    if not wire.IsDone():
        raise RuntimeError("gear outline wire did not close")
    bore = rf * 0.35 if bore is None else float(bore)
    holes = []
    if bore > 0:
        bore = min(bore, 0.8 * rf)
        holes = [BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(_ax(z0), bore)).Edge()).Wire()]
        rec["circles"].append({"centre": [0, 0], "radius": bore, "hole": True})
    rec["exact"] = f"involute spur gear z={z} m={m:g} (B-spline flanks, arc tips / roots)"
    rec["gear"] = {"teeth": z, "module": m, "pitch_radius": r, "tip_radius": ra, "root_radius": rf, "base_radius": rb,
                   "pressure_angle": pressure_angle, "face_width": float(thickness)}
    return _prism(wire.Wire(), holes, thickness)


def b_coil(rec, radius=10, wire=1.2, turns=6, pitch=3, **_):
    import cadquery as cq
    h = float(turns) * float(pitch)
    hel = cq.Wire.makeHelix(float(pitch), h, float(radius), center=cq.Vector(0, 0, -h / 2))
    prof = cq.Wire.makeCircle(float(wire), hel.startPoint(), hel.tangentAt(0))
    rec["exact"] = f"circle swept along a helix ({turns:g} turns, pitch {pitch:g} mm)"
    return cq.Solid.sweep(prof, [], hel, isFrenet=True).wrapped


def b_pipe(rec, points, radius=2, **_):
    import cadquery as cq
    P = [cq.Vector(*map(float, p)) for p in points]
    path = cq.Wire.makePolygon(P)
    prof = cq.Wire.makeCircle(float(radius), P[0], P[1] - P[0])
    rec["exact"] = "circle swept along the polyline (round transitions)"
    return cq.Solid.sweep(prof, [], path, transition="round").wrapped


def b_outline(rec, polygons, thickness=5.0, **_):
    t = float(thickness)
    solids = []
    for poly in polygons:
        ow, ofit = _ring_wire(poly["outer"], -t / 2, rec)
        hw = []
        for h in poly.get("holes") or []:
            w, fit = _ring_wire(h, -t / 2, rec)
            if fit:
                rec["circles"][-1]["hole"] = True
            hw.append(w)
        solids.append(_prism(ow, hw, t))
    rec["exact"] = (f"traced outline extruded {t:g} mm: {len(rec['circles'])} exact circle(s), "
                    f"{rec['polygon_edges']} traced polygon edge(s)")
    return _fuse(solids)


def b_profile(rec, runs, cell=1.0, thickness=5.0, rows=0, cols=0, **_):
    V, F = G.profile(runs, cell, thickness, rows, cols)
    boxes = []
    for i in range(0, len(V), 8):
        lo, hi = V[i:i + 8].min(0), V[i:i + 8].max(0)
        boxes.append(BRepPrimAPI_MakeBox(_P(*lo), *map(float, hi - lo)).Shape())
    rec["exact"] = f"{len(boxes)} fused blocks"
    return _fuse(boxes)


def b_nozzle(rec, throat=10, exit=30, length=60, chamber=18, chamber_length=30, **_):
    zs = np.linspace(0, 1, 16)
    bell = [[throat + (exit - throat) * (1 - (1 - s) ** 2), -chamber_length - 8 - s * length] for s in zs]
    prof = [[chamber, 0], [chamber, -chamber_length + 4], [throat * 1.15, -chamber_length - 4]] + bell
    pts = [[0, prof[0][1]]] + prof + [[0, prof[-1][1]]]
    poly = BRepBuilderAPI_MakePolygon()
    for rr, zz in pts:
        poly.Add(_P(rr, 0, zz))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    rec["exact"] = "profile revolved about its axis (solid of revolution)"
    return BRepPrimAPI_MakeRevol(face, gp_Ax1(_P(0, 0, 0), gp_Dir(0, 0, 1)), 2 * math.pi).Shape()


def b_blade_ring(rec, count=12, inner=8, outer=20, thickness=1.0, height=6, twist=25, **_):
    blades = []
    for k in range(int(count)):
        b = BRepPrimAPI_MakeBox(_P(inner, -thickness / 2, -height / 2), float(outer - inner), float(thickness), float(height)).Shape()
        M = np.eye(4)
        M[:3, :3] = G._rot([0, 0, 360 * k / count]) @ G._rot([twist, 0, 0])
        M[:3, 3] = 0
        blades.append(_apply(b, M))
    rec["exact"] = f"{int(count)} fused blades"
    return _fuse(blades)


BUILDERS = {"cylinder": b_cylinder, "tube": b_tube, "box": b_box, "cone": b_cone, "sphere": b_sphere, "torus": b_torus,
            "gear": b_gear, "coil": b_coil, "pipe": b_pipe, "outline": b_outline, "profile": b_profile,
            "nozzle": b_nozzle, "blade_ring": b_blade_ring}
NO_BREP = {"inflate": "an inflated sketch is a triangle surface, it has no exact B-rep",
           "mesh": "an imported triangle mesh has no exact B-rep",
           "cad": "already a B-rep of the three-view CAD document (exported from there)"}


# ------------------------------------------------------------------------------------------------ placement
def _apply(shape, M):
    """Shape moved by the 4x4 matrix M: an exact rigid (or uniformly scaled) transform when M allows it, else a
    general affine one (non-uniform scale: surfaces become B-splines)."""
    L = M[:3, :3]
    s = np.cbrt(abs(np.linalg.det(L))) or 1.0
    R = L / s
    if np.allclose(R.T @ R, np.eye(3), atol=1e-9):
        t = gp_Trsf()
        t.SetValues(*[float(v) for v in np.c_[L, M[:3, 3]].ravel()])
        return BRepBuilderAPI_Transform(shape, t, True).Shape()
    g = gp_GTrsf()
    g.SetVectorialPart(gp_Mat(*[float(v) for v in L.ravel()]))
    g.SetTranslationPart(gp_XYZ(*map(float, M[:3, 3])))
    return BRepBuilderAPI_GTransform(shape, g, True).Shape()


def _group_of(part):
    kind = ((part.get("eng") or {}).get("kind") or part["type"]).lower()
    if (part.get("eng") or {}).get("reason") or kind == "added":
        return "inferred"
    for gid, _, kinds in GROUPS:
        if kind in kinds or any(k in kind for k in kinds):
            return gid
    t = part["type"]
    return {"gear": "gears", "coil": "springs", "cylinder": "shafts"}.get(t, "other")


# ------------------------------------------------------------------------------------------------ build
def build(parts, log=print):
    """parts: the scene's parts (engine format). Returns (shapes {id: world TopoDS_Shape}, local {id: shape in the
    part's own frame, unscaled}, records {id: build record})."""
    by_id = {p["id"]: p for p in parts}
    shapes, local, records = {}, {}, {}
    for p in parts:
        if p["type"] == "group":
            continue
        rec = {"id": p["id"], "name": p["name"], "type": p["type"], "group": _group_of(p), "circles": [],
               "polygon_edges": 0, "eng": p.get("eng") or {},
               "params": {k: v for k, v in (p.get("params") or {}).items() if isinstance(v, (int, float))}}
        records[p["id"]] = rec
        if p["type"] in NO_BREP or p["type"] not in BUILDERS:
            rec.update(built=False, reason=NO_BREP.get(p["type"], f"no B-rep builder for part type {p['type']!r}"))
            continue
        t0 = time.time()
        try:
            loc = BUILDERS[p["type"]](rec, **(p.get("params") or {}))
            if loc is None or loc.IsNull():
                raise RuntimeError("empty shape")
            M = G.world_matrix(p, by_id)
            par = by_id.get(p.get("parent"))
            ds = float(np.cbrt(abs(np.linalg.det(G.world_matrix(par, by_id)[:3, :3])))) if par else 1.0
            M[:3, :] /= ds or 1.0              # the display scale of the whole machine is not part of the model
            rec["display_scale"] = round(ds, 9)
            local[p["id"]] = loc
            shapes[p["id"]] = _apply(loc, M)
            rec.update(built=True, seconds=round(time.time() - t0, 3), matrix=M.round(6).tolist())
        except Exception as e:                                  # reported, never replaced by an approximation
            rec.update(built=False, reason=f"{type(e).__name__}: {e}"[:300])
            log(f"[assembly] {p['name']}: {rec['reason']}")
    return shapes, local, records


PIN_KINDS = ("pin", "bolt", "shaft", "axle")
PLATE_TYPES = ("outline", "box")
BORE_CLEARANCE_MM = 0.1      # bore = pin diameter + 0.1 mm (a free running clearance), stated on every bore


def _is_pin(rec):
    if rec["type"] != "cylinder":
        return False
    kind = (rec["eng"].get("kind") or "").lower()
    name = rec["name"].lower()
    return kind in PIN_KINDS or any(k in name for k in PIN_KINDS)


def _half_t(rec):
    p = rec["params"]
    return float(p.get("thickness", p.get("h", 0))) / 2


def cut_bores(shapes, local, records, log=print):
    """Where a pin, bolt or shaft passes through a plate (pin axis parallel to the plate's normal, solids overlapping),
    the plate gets the bore the pin needs: a cylinder of the pin's own length and diameter + BORE_CLEARANCE_MM, cut
    from the plate in the plate's own frame. The drawing shows the pin passing through; the hole itself is hidden in the
    section, so every bore is recorded as an INFERRED feature naming the pin that implies it."""
    boxes = {i: _bbox(s) for i, s in shapes.items()}
    pins = [i for i in shapes if _is_pin(records[i])]
    plates = [i for i in shapes if records[i]["type"] in PLATE_TYPES]
    n = 0
    for j in plates:
        Mj = np.asarray(records[j]["matrix"])
        nj = Mj[:3, 2] / np.linalg.norm(Mj[:3, 2])
        Mj_inv = np.linalg.inv(Mj)
        loc = local[j]
        v0 = None
        for i in pins:
            A, B = boxes[i], boxes[j]
            if np.any(A[:3] > B[3:]) or np.any(B[:3] > A[3:]):
                continue
            Mp = np.asarray(records[i]["matrix"])
            dp = Mp[:3, 2] / np.linalg.norm(Mp[:3, 2])
            if abs(float(dp @ nj)) < math.cos(math.radians(AXIS_DEG)):
                continue
            prm = records[i]["params"]
            r = float(prm.get("radius", 0)) + BORE_CLEARANCE_MM / 2
            h = float(prm.get("height", 0))
            if r <= BORE_CLEARANCE_MM or h <= 0:
                continue
            T = Mj_inv @ Mp                                   # pin frame -> plate frame
            tool = _apply(BRepPrimAPI_MakeCylinder(_ax(-h / 2), r, h).Shape(), T)
            if v0 is None:
                v0 = _volume(loc)
            cut = BRepAlgoAPI_Cut()
            cut.SetRunParallel(True)
            _args(cut, loc, tool)
            cut.Build()
            if not cut.IsDone():
                continue
            res = cut.Shape()
            v1 = _volume(res)
            if v0 - v1 <= 1e-6:
                continue                                      # the pin does not reach into this plate
            o, d = T[:3, 3], T[:3, 2] / np.linalg.norm(T[:3, 2])
            c = o - (o[2] / d[2]) * d if abs(d[2]) > 1e-9 else o
            through = bool(v0 - v1 >= 0.97 * math.pi * r * r * 2 * _half_t(records[j]))
            records[j]["circles"].append({"centre": [float(c[0]), float(c[1])], "radius": r, "hole": True, "bore_for": i})
            records[j].setdefault("features", []).append({
                "op": "bore", "for": records[i]["name"], "diameter_mm": round(2 * r, 3), "through": through,
                "removed_mm3": round(v0 - v1, 3),
                "provenance": f"inferred: {records[i]['name']} passes through here; bore = pin diameter + {BORE_CLEARANCE_MM} mm"})
            loc, v0 = res, v1
            n += 1
        if loc is not local[j]:
            local[j] = loc
            shapes[j] = _apply(loc, Mj)
            records[j]["exact"] += f" + {len(records[j]['features'])} inferred bore(s)"
    return n


def _args(op, a, b):
    from OCP.TopTools import TopTools_ListOfShape
    la, lb = TopTools_ListOfShape(), TopTools_ListOfShape()
    la.Append(a)
    lb.Append(b)
    op.SetArguments(la)
    op.SetTools(lb)


def why_interfering(p, records):
    """A plain cause for an interference, from what the two parts are (shown next to the volume)."""
    a, b = records[p["a"]], records[p["b"]]
    if a["eng"].get("reason") or b["eng"].get("reason"):
        x = a if a["eng"].get("reason") else b
        return f"involves {x['name']}, inferred by Muse Wonder: its guessed size / place conflicts with a drawn part"
    ka, kb = (a["eng"].get("kind") or a["type"]), (b["eng"].get("kind") or b["type"])
    if ka == kb == "frame":
        return "frame walls overlap where they meet"
    if a["type"] in AXIAL and b["type"] in AXIAL:
        _, da, _ = _axis(a)
        _, db, _ = _axis(b)
        if abs(float(da @ db)) >= math.cos(math.radians(AXIS_DEG)):
            return "parallel round parts overlap: read too close together or too large on the drawing"
        return "round parts cross each other"
    return "drawn parts overlap in depth: the single view does not say which is in front"


def _bbox(shape):
    return np.array(Vd.bbox(shape))


def _volume(shape):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    return float(g.Mass())


def _axis(rec):
    M = np.asarray(rec["matrix"])
    d = M[:3, 2] / max(np.linalg.norm(M[:3, 2]), 1e-12)
    return M[:3, 3], d, M


def _line_dist(o1, d1, o2):
    v = o2 - o1
    return float(np.linalg.norm(v - (v @ d1) * d1))


AXIAL = ("cylinder", "tube", "gear", "coil", "cone", "torus")


def _envelope(rec, shape):
    """An exact solid that contains the part, for fast conservative tests (B-spline surfaces are slow for BRepExtrema
    and Booleans): a swept coil is enclosed by the annular tube its wire sweeps, a gear by its tip cylinder.
    None = use the part itself."""
    if "matrix" not in rec:
        return None
    if rec.get("gear"):
        g = rec["gear"]
        h = g["face_width"]
        return _apply(BRepPrimAPI_MakeCylinder(_ax(-h / 2), g["tip_radius"], h).Shape(), np.asarray(rec["matrix"]))
    if rec["type"] != "coil":
        return None
    p = rec["params"]
    R, w, h = float(p.get("radius", 10)), float(p.get("wire", 1.2)), float(p.get("turns", 6)) * float(p.get("pitch", 3))
    o = BRepPrimAPI_MakeCylinder(_ax(-h / 2 - w), R + w, h + 2 * w).Shape()
    if R - w > 1e-3:
        o = BRepAlgoAPI_Cut(o, BRepPrimAPI_MakeCylinder(_ax(-h / 2 - w), R - w, h + 2 * w).Shape()).Shape()
    return _apply(o, np.asarray(rec["matrix"]))


def _dist(a, b):
    ds = BRepExtrema_DistShapeShape()
    ds.SetMultiThread(True)
    ds.LoadS1(a)
    ds.LoadS2(b)
    ds.Perform()
    return float(ds.Value()) if ds.IsDone() else float("nan")


def contacts(shapes, records, log=print):
    """Every pair whose boxes (grown by CONTACT_MM) overlap: Boolean common volume (interference), else the exact
    minimum distance (contact / clear). A part with an envelope is first tested through it: envelope clear => part
    clear (the envelope contains the part), so the slow exact distance runs only where the envelope touches."""
    ids = list(shapes)
    boxes = {i: _bbox(shapes[i]) for i in ids}
    env = {i: _envelope(records[i], shapes[i]) for i in ids}
    out = []
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            i, j = ids[a], ids[b]
            A, B = boxes[i], boxes[j]
            if np.any(A[:3] > B[3:] + CONTACT_MM) or np.any(B[:3] > A[3:] + CONTACT_MM):
                continue
            t0 = time.time()
            ea = env[i] if env[i] is not None else shapes[i]
            eb = env[j] if env[j] is not None else shapes[j]
            vol = None
            if env[i] is not None or env[j] is not None:       # envelopes do not overlap => the parts do not either
                c = BRepAlgoAPI_Common(ea, eb)
                c.SetRunParallel(True)
                c.Build()
                if c.IsDone() and _volume(c.Shape()) <= INTERFERE_MM3:
                    vol = 0.0
            if vol is None:
                c = BRepAlgoAPI_Common()
                c.SetRunParallel(True)
                _args(c, shapes[i], shapes[j])
                c.Build()
                vol = _volume(c.Shape()) if c.IsDone() else float("nan")
            method = "Boolean common"
            if vol > INTERFERE_MM3:
                dist = 0.0
            else:
                dist = None
                if env[i] is not None or env[j] is not None:
                    d0 = _dist(ea, eb)
                    if d0 > CONTACT_MM:
                        dist, method = d0, "envelope distance (lower bound)"
                if dist is None:
                    dist, method = _dist(shapes[i], shapes[j]), "exact distance"
            status = "interference" if vol > INTERFERE_MM3 else ("contact" if dist <= CONTACT_MM else "clear")
            out.append({"a": i, "b": j, "distance_mm": round(dist, 4), "common_mm3": round(vol, 3), "status": status,
                        "method": method, "ms": round(1000 * (time.time() - t0))})
    return out


def _scale(rec):
    """The part's uniform world scale (a machine fitted to the desk display is scaled as a whole)."""
    return float(np.linalg.norm(np.asarray(rec["matrix"])[:3, 0])) or 1.0


def mates(shapes, records, pairs, parts):
    """Mates, each measured on the solids. Every length is compared in the parts' own millimetres (model mm): the
    display scale of the whole machine is divided out. The joints the rebuild declared are checked by their type
    (pivot = the pin sits in a bore of the part, gear_mesh = centre distance and contact ratio, coaxial = shared
    axis); then mates found on the solids that nobody declared."""
    by_name = {r["name"]: i for i, r in records.items()}
    built = {i: r for i, r in records.items() if r.get("built")}
    touching = {(p["a"], p["b"]) for p in pairs if p["status"] != "clear"} | \
               {(p["b"], p["a"]) for p in pairs if p["status"] != "clear"}
    out, seen = [], set()
    cos_tol = math.cos(math.radians(AXIS_DEG))

    def add(kind, a, b, **m):
        key = (kind, *sorted((a, b)))
        if key in seen:
            return False
        seen.add(key)
        out.append({"type": kind, "a": a, "b": b, **m})
        return True

    def coax(a, b):
        oa, da, _ = _axis(built[a])
        ob, db, _ = _axis(built[b])
        ang = math.degrees(math.acos(min(1.0, abs(float(da @ db)))))
        return ang, _line_dist(oa, da, ob) / _scale(built[a])

    def pin_radius(i):
        prm = parts[i].get("params") or {}
        return float(prm.get("radius") or prm.get("outer") or 0)

    def pin_in_hole(i, j):
        """The pin i in an exact circular hole of part j (bore, gear bore, tube bore): (mate fields) or None."""
        oi, di, _ = _axis(built[i])
        _, dj, Mj = _axis(built[j])
        if abs(float(di @ dj)) < cos_tol:
            return None
        k = _scale(built[i])
        pin_r = pin_radius(i)
        for c in built[j]["circles"]:
            if not c.get("hole"):
                continue
            centre = Mj[:3, :3] @ np.array([c["centre"][0], c["centre"][1], 0.0]) + Mj[:3, 3]
            off = _line_dist(oi, di, centre) / k
            hole_r = c["radius"] * _scale(built[j]) / k
            if off <= max(AXIS_MM, 0.1 * hole_r) and 0.6 * hole_r <= pin_r <= hole_r * 1.02:
                return dict(clearance_mm=round(hole_r - pin_r, 4), offset_mm=round(off, 4),
                            satisfied=off <= AXIS_MM and hole_r >= pin_r - 1e-6,
                            check=f"axis offset {off:.3f} mm, bore \u00d8{2 * hole_r:.3f} / pin \u00d8{2 * pin_r:.3f} mm "
                                  f"({'clearance' if hole_r >= pin_r else 'interference'} {abs(hole_r - pin_r):.3f} mm)")
        return None

    def gear_pair(i, j):
        gi, gj = built[i]["gear"], built[j]["gear"]
        oa, da, _ = _axis(built[i])
        ob, db, _ = _axis(built[j])
        if abs(float(da @ db)) < cos_tol:
            return None, "axes not parallel"
        if abs(gi["module"] - gj["module"]) > 1e-6:
            return None, f"modules differ ({gi['module']:g} / {gj['module']:g} mm): these teeth cannot mesh"
        cd = _line_dist(oa, da, ob) / _scale(built[i])
        ideal = gi["module"] * (gi["teeth"] + gj["teeth"]) / 2
        chk = G.gear_mesh_check(gi["teeth"], gj["teeth"], gi["module"], cd, gi["pressure_angle"])
        return dict(ratio=f"{gi['teeth']}:{gj['teeth']}", centre_distance_mm=chk["centre_distance_mm"],
                    ideal_mm=chk["ideal_centre_distance_mm"], contact_ratio=chk["contact_ratio"], satisfied=chk["ok"],
                    check=f"centre distance {cd:.3f} mm vs m(z1+z2)/2 = {ideal:.3f} mm (\u00b1 {0.05 * gi['module']:.3f}), "
                          f"contact ratio {chk['contact_ratio']} (\u2265 1.2)"), None

    # 1. the joints the rebuild declared, by type
    for i, r in built.items():
        for jt in (r["eng"].get("joints") or []):
            other = by_name.get(jt.get("with"))
            if other is None or other not in built or other == i:
                continue
            kind = (jt.get("type") or "coaxial").lower()
            if kind == "gear_mesh":
                if not (built[i].get("gear") and built[other].get("gear")):
                    add("Gear mesh", i, other, source="declared by the rebuild", satisfied=False,
                        check="declared, but one of the two parts is not a gear")
                    continue
                m, why = gear_pair(i, other)
                add("Gear mesh", i, other, source="declared by the rebuild",
                    **(m or dict(satisfied=False, check=f"declared, but {why}")))
            elif kind == "pivot":
                pin, host = (i, other) if built[i]["type"] in ("cylinder", "tube") else (other, i)
                m = pin_in_hole(pin, host) if built[pin]["type"] in ("cylinder", "tube") else None
                if m:
                    add("Concentric (pin in bore)", pin, host, source="declared by the rebuild", **m)
                else:
                    ang, off = coax(pin, host)
                    add("Concentric (pin in bore)", pin, host, source="declared by the rebuild", satisfied=False,
                        check=(f"declared pivot, but the pin is {ang:.0f}\u00b0 to the part's axis" if ang > AXIS_DEG else
                               "declared pivot, but the pin does not reach the part in depth: no bore around it"))
            else:
                ang, off = coax(i, other)
                add("Coaxial", i, other, source="declared by the rebuild", angle_deg=round(ang, 4), offset_mm=round(off, 4),
                    satisfied=ang <= AXIS_DEG and off <= AXIS_MM,
                    check=f"axis angle {ang:.3f}\u00b0 (\u2264 {AXIS_DEG}\u00b0), axis offset {off:.3f} mm (\u2264 {AXIS_MM} mm)")
    # 2. gear meshes nobody declared: parallel gears whose centre distance is near m (z1 + z2) / 2
    gears = [i for i, r in built.items() if r.get("gear")]
    for x in range(len(gears)):
        for y in range(x + 1, len(gears)):
            m, _ = gear_pair(gears[x], gears[y])
            if m and abs(m["centre_distance_mm"] - m["ideal_mm"]) <= 0.25 * m["ideal_mm"]:
                add("Gear mesh", gears[x], gears[y], source="found on the solids", **m)
    # 3. pins in bores nobody declared (the inferred bores, gear and tube bores)
    for i, r in built.items():
        if r["type"] not in ("cylinder", "tube"):
            continue
        for j in built:
            if j == i or ((i, j) not in touching and not _near(shapes[i], shapes[j])):
                continue
            m = pin_in_hole(i, j)
            if m:
                add("Concentric (pin in bore)", i, j, source="found on the solids", **m)
    # 4. coaxial round parts that touch (a shaft through a hub, a gear on its shaft)
    for (i, j) in touching:
        if i > j or i not in built or j not in built:
            continue
        if built[i]["type"] not in AXIAL or built[j]["type"] not in AXIAL:
            continue
        ang, off = coax(i, j)
        if ang <= AXIS_DEG and off <= AXIS_MM:
            add("Coaxial", i, j, source="found on the solids", angle_deg=round(ang, 4), offset_mm=round(off, 4),
                satisfied=True, check=f"axis angle {ang:.3f}\u00b0, axis offset {off:.3f} mm")
    # 5. planar face-to-face contact between parts extruded along the same axis (stacked plates)
    for p in pairs:
        if p["status"] != "contact":
            continue
        i, j = p["a"], p["b"]
        _, di, Mi = _axis(built[i])
        _, dj, Mj = _axis(built[j])
        if abs(float(di @ dj)) < cos_tol:
            continue
        ti, tj = _half_thickness(parts[i]), _half_thickness(parts[j])
        if ti is None or tj is None:
            continue
        gap = abs(float((Mj[:3, 3] - Mi[:3, 3]) @ di)) / _scale(built[i]) - (ti + tj)
        if abs(gap) <= CONTACT_MM:
            add("Mate (face to face)", i, j, source="found on the solids", gap_mm=round(gap, 4), satisfied=True,
                check=f"faces {abs(gap):.4f} mm apart (\u2264 {CONTACT_MM} mm), normals parallel")
    return out


def _half_thickness(part):
    prm = part.get("params") or {}
    for k in ("thickness", "height", "h"):
        if k in prm and isinstance(prm[k], (int, float)):
            return float(prm[k]) / 2
    return None


def _near(a, b):
    A, B = _bbox(a), _bbox(b)
    return not (np.any(A[:3] > B[3:] + CONTACT_MM) or np.any(B[:3] > A[3:] + CONTACT_MM))


def explode_vectors(parts, records, found, pairs, gap=8.0, spread=2.6):
    """Exploded view as a CAD tool lays it out (world offsets {id: [x, y, z]} at explode = 1):
    1. layers: the assembly's main axis A is the axis most parts share (the plates' common normal); every part moves
       along A by `spread` x its distance from the assembly's centre along A, so stacked plates, covers and walls open
       up in their own order;
    2. mates: a pin / shaft held in a bore or a coaxial part then slides along that mate's axis, out of the part it is
       mated to, past both parts' extents plus `gap`, on the side it already sits."""
    built = {i: r for i, r in records.items() if r.get("built") and r.get("validation")}
    if not built:
        return {}
    box = {i: np.asarray(r["validation"].get("bbox_mm") or [0] * 6, float) for i, r in built.items()}
    cen = {i: (b[:3] + b[3:]) / 2 for i, b in box.items()}
    lo = np.min([b[:3] for b in box.values()], 0)
    hi = np.max([b[3:] for b in box.values()], 0)
    C = (lo + hi) / 2
    axes = [np.round(np.abs(_axis(r)[1]), 2) for r in built.values()]
    A = max(axes, key=lambda a: sum(np.allclose(a, b, atol=0.02) for b in axes))
    A = A / max(np.linalg.norm(A), 1e-12)
    off = {i: A * float((cen[i] - C) @ A) * spread for i in built}
    # 3. enclosures (a housing / frame wall spanning the whole assembly across A) move clear, down, out of the way
    up = np.array([0.0, 0.0, 1.0]) if abs(A[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    up = up - (up @ A) * A
    up /= np.linalg.norm(up)
    side = np.cross(A, up)
    span = lambda b, v: float(np.abs((b[3:] - b[:3]) * v).sum())
    H = span(np.r_[lo, hi], up)
    for i in built:
        full = np.r_[lo, hi]
        if (span(box[i], up) >= 0.8 * H and span(box[i], side) >= 0.8 * span(full, side)
                and span(box[i], A) >= 0.5 * span(full, A)):        # covers (thin along A) open along A instead
            off[i] = off[i] - up * (H + 2 * gap)
            built[i]["enclosure"] = True
    held = {}
    for m in found:
        if m["type"] in ("Concentric (pin in bore)", "Coaxial") and m["satisfied"]:
            for pin, host in ((m["a"], m["b"]), (m["b"], m["a"])):
                if pin in built and host in built and (_is_pin(built[pin]) or built[pin]["type"] in AXIAL):
                    held.setdefault(pin, []).append(host)
    for pin, hosts in held.items():
        _, d, _ = _axis(built[pin])
        host = max(hosts, key=lambda h: float(np.prod(box[h][3:] - box[h][:3])))
        s = float((cen[pin] - cen[host]) @ d) or float((cen[pin] - C) @ d) or 1.0
        ext = float(np.abs((box[host][3:] - box[host][:3]) * d).sum()) / 2 + float(np.abs((box[pin][3:] - box[pin][:3]) * d).sum()) / 2
        off[pin] = off[host] + np.sign(s) * d * (max(ext - abs(s), 0.0) + gap) + (off[pin] - off[host]) * (1 - abs(float(d @ A)))
    return {i: v.round(3).tolist() for i, v in off.items()}


def section(shapes, axis, offset, flip=False, matrices=None):
    """True B-rep section: each solid cut by the plane {p[axis] = offset}; the side kept is p[axis] <= offset (or >=
    when flip), as in the viewport. Returns {id: {"area_mm2", "cap": [[x, y, z] ...] triangles (world), "edges"}} for
    every part the plane cuts. The caps are the faces of the Boolean result that lie on the plane."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from . import tessellate as T
    k = "xyz".index(axis)
    allb = np.array([_bbox(s) for s in shapes.values()])
    lo, hi = allb[:, :3].min(0) - 10, allb[:, 3:].max(0) + 10
    a, b = lo.copy(), hi.copy()
    if flip:
        a[k] = offset
    else:
        b[k] = offset
    keep = BRepPrimAPI_MakeBox(_P(*a), _P(*b)).Shape()
    out = {}
    for i, s in shapes.items():
        bb = _bbox(s)
        if not (bb[k] < offset < bb[k + 3]):
            continue
        c = BRepAlgoAPI_Common(s, keep)
        c.Build()
        if not c.IsDone():
            continue
        res = c.Shape()
        caps, area = [], 0.0
        ex = TopExp_Explorer(res, TopAbs_FACE)
        while ex.More():
            f = TopoDS.Face_s(ex.Current())
            sa = BRepAdaptor_Surface(f)
            if sa.GetType() == GeomAbs_Plane:
                n = sa.Plane().Axis().Direction()
                o = sa.Plane().Location()
                if abs([n.X(), n.Y(), n.Z()][k]) > 1 - 1e-9 and abs([o.X(), o.Y(), o.Z()][k] - offset) < 1e-6:
                    g = GProp_GProps()
                    BRepGProp.SurfaceProperties_s(f, g)
                    area += float(g.Mass())
                    V, F, _, _ = T.mesh(f, 0.05, 0.2)
                    if len(F):
                        caps.append(V[F].reshape(-1, 3))
            ex.Next()
        if caps:
            out[i] = {"area_mm2": round(area, 3), "cap": np.vstack(caps).round(3)}
    return out


def write_step_tree(components, groups, path, title="AETHER_ASSEMBLY"):
    """AP214 STEP with the assembly tree: top assembly -> one sub-assembly per group -> named, coloured parts.
    components: {id: {"name", "shape", "colour"}}; groups: [{"id", "name", "parts": [ids]}]."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool
    from .export import _rgb
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    name = lambda lab, s: TDataStd_Name.Set_s(lab, TCollection_ExtendedString(s))
    top = st.NewShape()
    name(top, title)
    for g in groups:
        members = [i for i in g["parts"] if i in components]
        if not members:
            continue
        sub = st.NewShape()
        name(sub, g["name"])
        for i in members:
            c = components[i]
            lab = st.AddShape(c["shape"], False)
            name(lab, i)
            r, gg, b = _rgb(c.get("colour"))
            ct.SetColor(lab, Quantity_Color(r, gg, b, Quantity_TOC_RGB), XCAFDoc_ColorSurf)
            comp = st.AddComponent(sub, lab, TopLoc_Location())
            name(comp, c["name"])
        comp = st.AddComponent(top, sub, TopLoc_Location())
        name(comp, g["name"])
    st.UpdateAssemblies()
    Interface_Static.SetCVal_s("write.step.schema", "AP214")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.SetColorMode(True)
    if not w.Transfer(doc, STEPControl_AsIs):
        raise RuntimeError("STEP transfer failed")
    if w.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")
    return str(path)


def write_step_and_breps(components, groups, step_path, brep_dir):
    """The STEP tree, plus each original solid as .brep (OCCT's exact native format) for the round-trip comparison."""
    import os
    from OCP.BRepTools import BRepTools
    write_step_tree(components, groups, step_path)
    os.makedirs(brep_dir, exist_ok=True)
    for i, c in components.items():
        BRepTools.Write_s(c["shape"], os.path.join(brep_dir, i + ".brep"))


def verify_step(step_path, brep_dir, names):
    """Re-read the STEP and compare every part in a FRESH process (no kernel state shared with the writer)."""
    from . import export as EX
    res = EX.fresh_process("assembly", "_roundtrip_child", str(step_path), str(brep_dir), list(names))
    res["all_pass"] = all(r.get("pass") for r in res["components"].values()) and not res["missing"]
    return res


def step_roundtrip(components, groups, step_path, brep_dir):
    write_step_and_breps(components, groups, step_path, brep_dir)
    return verify_step(step_path, brep_dir, list(components))


ROUNDTRIP_SAMPLES = 12       # surface points compared each way per solid, on top of the exact counts / volume / area / box (the car body uses 600)


def _roundtrip_child(step_path, brep_dir, names):
    """Fresh process: read the STEP back, and compare every solid with its original .brep (cad.export.compare_shapes:
    validity, solid / face counts, volume, area, bounding box, sampled distances both ways)."""
    import os
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools
    from . import export as EX
    got = EX.read_step(step_path)
    out, missing = {}, []
    for nm in names:
        if nm not in got:
            missing.append(nm)
            continue
        a = TopoDS_Shape()
        BRepTools.Read_s(a, os.path.join(brep_dir, nm + ".brep"), BRep_Builder())
        out[nm] = EX.compare_shapes(a, got[nm], n=ROUNDTRIP_SAMPLES)
    return {"components": out, "missing": missing, "read_names": sorted(got)}


def analyse(parts, log=print, argument_analysis=False):
    """Build every part, validate each solid, find contacts / interference and mates. Returns (shapes, local, report)."""
    t0 = time.time()
    shapes, local, records = build(parts, log)
    bores = cut_bores(shapes, local, records, log)
    t_build = time.time() - t0
    for i, s in shapes.items():
        try:
            records[i]["validation"] = Vd.check_solid(s, records[i]["name"], argument_analysis=argument_analysis)
        except Exception as e:
            records[i]["validation"] = {"valid": False, "error": f"{type(e).__name__}: {e}"[:300]}
    t_val = time.time() - t0 - t_build
    pairs = contacts(shapes, records, log)
    by_id = {p["id"]: p for p in parts}
    found = mates(shapes, records, pairs, by_id)
    t_all = time.time() - t0
    mated = {(m["a"], m["b"]) for m in found} | {(m["b"], m["a"]) for m in found}
    for p in pairs:
        if p["status"] == "interference":
            p["note"] = ("along a mate (press fit)" if (p["a"], p["b"]) in mated else why_interfering(p, records))
    groups = []
    for gid, name, _ in GROUPS:
        members = [i for i, r in records.items() if r["group"] == gid]
        if members:
            groups.append({"id": gid, "name": name, "parts": members})
    built = [r for r in records.values() if r.get("built")]
    valid = [r for r in built if r.get("validation", {}).get("valid")]
    summary = {"parts": len(records), "built": len(built), "not_built": len(records) - len(built),
               "valid_solids": len(valid), "invalid_solids": len(built) - len(valid),
               "exact_circles": sum(len(r["circles"]) for r in built), "inferred_bores": bores,
               "pairs_checked": len(pairs), "contacts": sum(p["status"] == "contact" for p in pairs),
               "interferences": sum(p["status"] == "interference" for p in pairs),
               "interference_mm3": round(sum(p["common_mm3"] for p in pairs if p["status"] == "interference"), 3),
               "mates": len(found), "mates_satisfied": sum(bool(m["satisfied"]) for m in found),
               "seconds": {"build": round(t_build, 2), "validate": round(t_val, 2), "total": round(t_all, 2)}}
    explode = explode_vectors(parts, records, found, pairs)
    scales = [r["display_scale"] for r in records.values() if "display_scale" in r]
    model_scale = max(set(scales), key=scales.count) if scales else 1.0
    return shapes, local, {"records": records, "pairs": pairs, "mates": found, "groups": groups, "summary": summary,
                           "explode_world": explode, "model_scale": model_scale,
                           "units": "model mm (the machine's own millimetres; the viewport shows it at model_scale)"}
