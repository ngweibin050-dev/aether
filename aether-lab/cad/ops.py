"""The fixed set of feature operations a document may name (OPS). Each takes (params, inputs, doc) where params are
resolved numbers / lists / enum strings and inputs are [(shape, info)] of the features it depends on; returns
(shape, info). info["valid"] is the kernel's verdict on the result; a False makes the recompute fail explicitly.

All geometry is built here by OpenCascade from those numbers. There is no operation that takes text to execute.
"""
from __future__ import annotations

import math

import numpy as np
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Vec

from . import kernel as K


def _valid(shape):
    return bool(BRepCheck_Analyzer(shape).IsValid())


# ------------------------------------------------------------------------------------------------ body
def op_section_sketch(p, inputs, doc):
    """Half-section keypoint sketch at station x (cad.kernel.section_keypoints) -> its planar B-spline edge.
    The envelope (end views, blended by w_front) shapes the flank; every keypoint is a parameter."""
    env_f = np.asarray(p["env_front"], float).copy()
    env_r = np.asarray(p["env_rear"], float).copy()
    env_f[:, 0] *= p.get("scale", 1.0)                     # envelope heights are stored at the reference scale
    env_r[:, 0] *= p.get("scale", 1.0)
    zz = np.linspace(0, max(env_f[:, 0].max(), env_r[:, 0].max()), 400)
    ee = p["w_front"] * np.interp(zz, env_f[:, 0], env_f[:, 1]) + (1 - p["w_front"]) * np.interp(zz, env_r[:, 0], env_r[:, 1])
    k = {key: p[key] for key in ("x", "z_bot", "z_top", "y_max", "z_max", "y_sh", "z_sh", "y_re", "z_re", "r_low", "glass_bulge")}
    k["crown_exp"] = p.get("crown_exp", 2.0)
    if p.get("env_cap") is not None:
        cap = np.asarray(p["env_cap"], float).copy()
        k["cap"] = (cap[:, 0] * p.get("scale", 1.0), cap[:, 1] * p.get("scale", 1.0) * p.get("cap_tol", 1.0))
    pts = K.section_keypoints(k, zz, ee)
    edge = K.half_section_edge(p["x"], pts)
    return edge, {"valid": True, "points_yz": [[round(a, 4), round(b, 4)] for a, b in pts], "x": p["x"]}


def op_skin_sections(p, inputs, doc):
    """Body solid by skinning the station half-sections (cad.kernel.skin_body_v3)."""
    st = [(info["x"], [tuple(q) for q in info["points_yz"]]) for _, info in inputs]
    sol, info = K.skin_body_v3(st, what="body skin")
    info["valid"] = _valid(sol)
    if not info["valid"]:
        from .validate import failing_subshapes
        info["why"] = failing_subshapes(sol)
    return sol, info


def op_wheel_well_cut(p, inputs, doc):
    """Wheel opening + wheel well: a cylinder about the axle (axis Y) of radius r_arch, from y_inner outwards on BOTH
    sides (the well's inner wall is the plane y = +-y_inner), subtracted from the body."""
    body = inputs[0][0]
    x, z, r, yi = p["x"], p["z"], p["r_arch"], p["y_inner"]
    big = 4000.0
    tools = []
    for sgn in (1, -1):
        y0 = yi if sgn > 0 else -yi - big
        tools.append(K.cylinder((x, y0, z), (0, 1, 0), r, big))
    tool = K.compound(tools)
    res, inf = K.boolean("cut", body, tool, "wheel well cut")
    s = K.solids(res)
    if len(s) != 1:
        raise K.KernelError(f"wheel well cut left {len(s)} solids (expected 1)")
    return s[0], {"valid": _valid(s[0]), **inf}


def op_cut_cylinders_x(p, inputs, doc):
    """Holes along X (e.g. exhaust openings in the tail): cylinders at (y, z) radius r from x0 to x1, subtracted."""
    body = inputs[0][0]
    tools = [K.cylinder((p["x0"], y, z), (1, 0, 0), r, p["x1"] - p["x0"]) for (y, z, r) in p["holes"]]
    res, inf = K.boolean("cut", body, K.compound(tools), "cylinder holes")
    s = K.solids(res)
    if len(s) != 1:
        raise K.KernelError(f"holes left {len(s)} solids")
    return s[0], {"valid": _valid(s[0]), **inf}


# ------------------------------------------------------------------------------------------------ wheels
def _tyre_profile(r_out, r_bead, width, bulge, n=40):
    # r_bead is kept clear of the rim lip by the caller (no tyre/rim overlap)
    """Closed tyre cross-section (radius, axial offset): tread flat-ish with shoulders, sidewalls bulging outward,
    beads at r_bead. Points ordered around the section."""
    h = width / 2
    pts = []
    # tread: from left shoulder to right shoulder (slight crown)
    rs = 0.12 * (r_out - r_bead)                                   # shoulder radius
    for t in np.linspace(-1, 1, 9):
        a = t * (h - rs)
        pts.append((r_out - 0.01 * (r_out - r_bead) * t * t, a))
    # right shoulder arc
    for ang in np.linspace(0, math.pi / 2, 5)[1:]:
        pts.append((r_out - rs + rs * math.cos(ang), (h - rs) + rs * math.sin(ang)))
    # right sidewall (bulged) down to the bead
    for t in np.linspace(0, 1, 10)[1:]:
        r = (r_out - rs) - t * (r_out - rs - r_bead)
        a = h + bulge * h * math.sin(math.pi * t) - 0.06 * h * t
        pts.append((r, a))
    # bead seat across the rim (closing the section inside)
    for t in np.linspace(1, -1, 7)[1:-1]:
        pts.append((r_bead, t * 0.94 * h))
    # left sidewall back up
    for t in np.linspace(1, 0, 10)[:-1]:
        r = (r_out - rs) - t * (r_out - rs - r_bead)
        a = -(h + bulge * h * math.sin(math.pi * t) - 0.06 * h * t)
        pts.append((r, a))
    for ang in np.linspace(math.pi / 2, 0, 5)[:-1]:
        pts.append((r_out - rs + rs * math.cos(ang), -((h - rs) + rs * math.sin(ang))))
    return pts


def op_tyre(p, inputs, doc):
    """Tyre: a smooth closed cross-section (tread, shoulders, bulged sidewalls, bead) revolved 360 deg about the
    axle (axis Y through the wheel centre)."""
    prof = _tyre_profile(p["r_out"], p["r_bead"], p["width"], p.get("sidewall_bulge", 0.08))
    sol = K.revolve_spline_profile_y(prof, (p["x"], p["y"], p["z"]), what="tyre")
    return sol, {"valid": _valid(sol), "construction": "closed B-spline section revolved about the axle"}


def op_rim(p, inputs, doc):
    """Rim: barrel (revolved profile: outer lips at r_lip, barrel at r_barrel, wheel face disc) + `spokes` Y-spokes
    (one spoke sketch = trunk from the hub splitting into two arms to the lip, extruded through the face thickness,
    polar-patterned) + hub with centre bore and `lugs` lug holes on the pitch circle (polar pattern). Face plane on
    the OUTER side (outer_sign = +1 for +Y wheels)."""
    x, y, z = p["x"], p["y"], p["z"]
    s = 1.0 if p["outer_sign"] >= 0 else -1.0
    w, rl, rb, rh = p["width"], p["r_lip"], p["r_barrel"], p["r_hub"]
    face_t = p["face_thickness"]
    h = w / 2
    lip = 0.06 * rl
    # barrel profile in (r, a); a measured along +Y from the wheel centre; outer face at a = s*h
    prof = [(rb, -h), (rl, -h), (rl, -h + lip), (rb + 0.5 * lip, -h + 1.5 * lip), (rb + 0.5 * lip, h - 1.5 * lip),
            (rl, h - lip), (rl, h), (rb, h), (rb - 0.4 * lip, h - lip), (rb - 0.4 * lip, -h + lip)]
    barrel = K.revolve_profile_y(prof, (x, y, z), what="rim barrel")
    # hub disc on the outer side
    a_face = s * (h - face_t / 2 - lip)
    hub = K.cylinder((x, y + a_face - face_t / 2, z), (0, 1, 0), rh, face_t)
    # one Y spoke in the wheel's face plane (local polar coords: angle 0 = +Z)
    n_sp = int(p["spokes"])
    wt = p["spoke_width"]
    r0, r_split = 0.85 * rh, rh + 0.45 * (rb - rh)
    split = math.radians(p["split_deg"])

    def pt(r, ang, off=0.0):
        # point at radius r, angle ang (from +Z, rotating about Y), offset 'off' perpendicular (in the face plane)
        ux, uz = math.sin(ang), math.cos(ang)
        return (x + r * ux + off * uz, z + r * uz - off * ux)
    trunk = [pt(r0, 0, -wt / 2), pt(r_split, 0, -wt / 2), pt(rb - 0.2 * lip, -split, -0.4 * wt),
             pt(rb - 0.2 * lip, -split, 0.4 * wt), pt(r_split + 0.6 * wt, 0, 0.0),
             pt(rb - 0.2 * lip, split, -0.4 * wt), pt(rb - 0.2 * lip, split, 0.4 * wt), pt(r_split, 0, wt / 2),
             pt(r0, 0, wt / 2)]
    y0 = y + a_face - face_t / 2
    spoke = K.prism_y(trunk, y0, y0 + face_t, "spoke")
    shapes = [spoke]
    for i in range(1, n_sp):
        shapes.append(K.transformed(spoke, rotate=(((x, y, z), (0, 1, 0)), 360.0 * i / n_sp)))
    body, _ = K.boolean("fuse", barrel, hub, "rim hub")
    for sp in shapes:
        body, _ = K.boolean("fuse", body, sp, "rim spoke")
    # centre bore + lug holes (polar pattern)
    holes = [K.cylinder((x, y - w, z), (0, 1, 0), p["r_bore"], 2 * w)]
    for i in range(int(p["lugs"])):
        a = 2 * math.pi * i / p["lugs"]
        holes.append(K.cylinder((x + p["r_pcd"] * math.sin(a), y - w, z + p["r_pcd"] * math.cos(a)), (0, 1, 0), p["r_lug"], 2 * w))
    body, _ = K.boolean("cut", body, K.compound(holes), "rim bores")
    s1 = K.solids(body)
    if len(s1) != 1:
        raise K.KernelError(f"rim: expected 1 solid, got {len(s1)}")
    return s1[0], {"valid": _valid(s1[0]), "construction": "revolved barrel + hub + Y-spoke sketch extruded x polar "
                   f"pattern {n_sp} + bore + {int(p['lugs'])} lug holes (polar pattern)"}


# ------------------------------------------------------------------------------------------------ small components
def op_mirror_housing(p, inputs, doc):
    """Exterior mirror: housing = loft of three rounded sections along +Y (inner, middle, outer), sized by the plan
    view (x range, outer reach) and the end views (z range); stalk = cylinder from the body side to the housing."""
    x0, x1, z0, z1 = p["x0"], p["x1"], p["z0"], p["z1"]
    yi, yo = p["y_in"], p["y_out"]
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    ax, az = (x1 - x0) / 2, (z1 - z0) / 2
    wires = []
    for t, sc in ((0.0, 0.82), (0.55, 1.0), (1.0, 0.88)):
        yy = yi + p["stalk"] + t * (yo - yi - p["stalk"])
        pts = []
        for ang in np.linspace(0, 2 * math.pi, 28, endpoint=False):
            # superellipse (rounded rectangle) section, slightly egg-shaped (blunt front)
            c, s_ = math.cos(ang), math.sin(ang)
            e = 2.0 / 3.2
            px = cx + sc * ax * math.copysign(abs(c) ** e, c)
            pz = cz + sc * az * math.copysign(abs(s_) ** e, s_)
            pts.append((px, yy, pz))
        wires.append(K._wire_from_curve(K._interp_closed(pts)))
    housing = K.loft(wires, what="mirror housing")
    rs = min(0.18 * (z1 - z0), 0.12 * (x1 - x0))
    stalk = K.cylinder((cx + 0.25 * ax, yi - p["embed"], cz - 0.2 * az), (0, 1, 0), rs, p["stalk"] + p["embed"] + 2.0)
    m, _ = K.boolean("fuse", housing, stalk, "mirror")
    s1 = K.solids(m)
    if len(s1) != 1:
        raise K.KernelError(f"mirror: expected 1 solid, got {len(s1)}")
    return s1[0], {"valid": _valid(s1[0]), "construction": "3-section loft housing + cylinder stalk, fused"}


def op_exhaust_tip(p, inputs, doc):
    """Exhaust tip: a tube along X (outer radius r, wall t) from x0 (inside the tail) to x1 (protrusion)."""
    y, z, r, t = p["y"], p["z"], p["r"], p["wall"]
    L = p["x1"] - p["x0"]
    outer = K.cylinder((p["x0"], y, z), (1, 0, 0), r, L)
    inner = K.cylinder((p["x0"] - 1, y, z), (1, 0, 0), r - t, L + 2)
    res, _ = K.boolean("cut", outer, inner, "exhaust bore")
    s1 = K.one_solid(res, "exhaust tip")
    return s1, {"valid": _valid(s1), "construction": "cylinder - bore (tube)"}


def op_mirror_copy(p, inputs, doc):
    """The input solid mirrored at the symmetry plane Y = 0 (left-hand part from the right-hand one)."""
    from OCP.TopoDS import TopoDS
    s = K.transformed(inputs[0][0], mirror_y=True)
    s = K.one_solid(s, "mirror copy")
    return s, {"valid": _valid(s), "construction": "mirror of " + str(p.get("of", "input")) + " at Y = 0"}


OPS = {"section_sketch": op_section_sketch, "skin_sections": op_skin_sections, "wheel_well_cut": op_wheel_well_cut,
       "cut_cylinders_x": op_cut_cylinders_x, "tyre": op_tyre, "rim": op_rim, "mirror_housing": op_mirror_housing,
       "exhaust_tip": op_exhaust_tip, "mirror_copy": op_mirror_copy}


# ------------------------------------------------------------------------------------------------ region features
_AXIS = {"side": 1, "top": 2, "front": 0, "rear": 0}


def _poly3d(view, poly2d, depth):
    """Region polygon in its view plane (model coords: side (x, z), top (x, y), front/rear (y, z)) placed at the
    given coordinate along the view axis."""
    if view == "side":
        return [(a, depth, b) for a, b in poly2d]
    if view == "top":
        return [(a, b, depth) for a, b in poly2d]
    return [(depth, a, b) for a, b in poly2d]


def _region_prism(view, polys, lo, hi):
    """Prisms of the region polygons along the view axis from lo to hi (model mm)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    out = []
    ax = _AXIS[view]
    v = [0.0, 0.0, 0.0]
    v[ax] = hi - lo
    for poly in polys:
        pts = _poly3d(view, poly, lo)
        face = BRepBuilderAPI_MakeFace(K._poly_wire(pts)).Face()
        mk = BRepPrimAPI_MakePrism(face, gp_Vec(*v))
        mk.Build()
        out.append(mk.Shape())
    return out


def op_imprint_projection(p, inputs, doc):
    """Imprint drawn region outlines (windows, lights, panel lines) onto the body: the region polygon is extruded
    along the view direction; the intersection curves of its SIDE faces with the body (BRepAlgoAPI_Section) are imprinted
    on the body by the general splitter (BRepAlgoAPI_Splitter, solid as argument, edges as tools: faces are split, the
    volume cannot be). The volume must not change and the result must pass the self-intersection check.
    (Splitting the shell and re-sewing it, the first version, produced self-intersecting faces; BRepFeat_SplitShape
    failed where two imprints cross. Both were found by BRepAlgoAPI_Check and replaced.)"""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane
    from cad.validate import bbox, mass, _argument_analysis
    body = inputs[0][0]
    p = {**p, "polygons": [[[c * p.get("scale", 1.0) for c in q] for q in poly] for poly in p["polygons"]]}
    bb = bbox(body)
    ax = _AXIS[p["view"]]
    lo, hi = bb[ax] - 50.0, bb[ax + 3] + 50.0
    mid = (bb[ax] + bb[ax + 3]) / 2
    if p["view"] == "front":
        hi = mid                              # only the half that faces the viewer
    elif p["view"] in ("rear", "top"):
        lo = mid
    sides = []
    for prism in _region_prism(p["view"], p["polygons"], lo, hi):
        ex = TopExp_Explorer(prism, TopAbs_FACE)
        while ex.More():
            f = TopoDS.Face_s(ex.Current())
            ad = BRepAdaptor_Surface(f)
            is_cap = ad.GetType() == GeomAbs_Plane and abs(ad.Plane().Axis().Direction().Coord(ax + 1)) > 0.999
            if not is_cap:                    # the caps (one may lie inside the body) are not cutting tools
                sides.append(f)
            ex.Next()
    sec = BRepAlgoAPI_Section(body, K.compound(sides), False)
    sec.ComputePCurveOn1(True)
    sec.Approximation(True)
    sec.Build()
    if not sec.IsDone():
        raise K.KernelError(f"imprint {p.get('name')}: section failed")
    # imprint the section edges with the general splitter (solid = argument, edges = tools): edges cannot divide a
    # volume, and the general fuse handles crossings with edges imprinted earlier (BRepFeat_SplitShape did not).
    # Tolerance budget: where an outline's prism face grazes the surface, the splitter widens vertex / edge tolerances
    # (4.2 mm measured on the headlights). If the result exceeds TOL_BUDGET, the grazing section edges (the loosest
    # ones) are left out step by step; how many is recorded. If nothing fits the budget the feature fails.
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Splitter
    from OCP.TopTools import TopTools_ListOfShape
    from OCP.BRep import BRep_Tool
    from cad.validate import check_solid
    TOL_BUDGET = float(p.get("tol_budget", 0.2))
    all_edges = []
    ex = TopExp_Explorer(sec.Shape(), TopAbs_EDGE)
    while ex.More():
        e = TopoDS.Edge_s(ex.Current())
        all_edges.append((BRep_Tool.Tolerance_s(e), e))
        ex.Next()
    if not all_edges:
        raise K.KernelError(f"imprint {p.get('name')}: the outline does not cross the body")
    attempt, sol = None, None
    for limit in (None, 0.05, 0.03, 0.02, 0.01):
        use = [e for t, e in all_edges if limit is None or t <= limit]
        if not use:
            break
        edges = TopTools_ListOfShape()
        for e in use:
            edges.Append(e)
        args = TopTools_ListOfShape()
        args.Append(body)
        sp = BRepAlgoAPI_Splitter()
        sp.SetArguments(args)
        sp.SetTools(edges)
        sp.SetFuzzyValue(1e-5)
        sp.Build()
        if not sp.IsDone():
            continue
        cand = K.one_solid(sp.Shape(), f"imprint {p.get('name')}")
        mt = check_solid(cand, argument_analysis=False)["max_tolerance_mm"]
        attempt = {"edge_tolerance_limit_mm": limit, "edges_used": len(use), "edges_left_out": len(all_edges) - len(use),
                   "result_max_tolerance_mm": mt}
        if mt <= max(TOL_BUDGET, check_solid(body, argument_analysis=False)["max_tolerance_mm"]):
            sol = cand
            break
    if sol is None:
        raise K.KernelError(f"imprint {p.get('name')}: no edge set keeps the B-rep tolerance within {TOL_BUDGET} mm "
                            f"(last attempt {attempt})")
    n = attempt["edges_used"]
    v0, v1 = mass(body)["volume_mm3"], mass(sol)["volume_mm3"]
    if abs(v1 - v0) > 1e-6 * abs(v0):
        # split faces can come back with an inconsistent orientation; repair (ShapeFix_Solid + orientation) and re-test
        from OCP.ShapeFix import ShapeFix_Solid
        from OCP.BRepLib import BRepLib
        fx = ShapeFix_Solid(sol)
        fx.Perform()
        sol = K.one_solid(fx.Solid(), f"imprint {p.get('name')}")
        BRepLib.OrientClosedSolid_s(sol)
        v1 = mass(sol)["volume_mm3"]
    if abs(v1 - v0) > 1e-6 * abs(v0):
        raise K.KernelError(f"imprint {p.get('name')}: volume changed by {v1 - v0:.3f} mm^3 (an imprint must not)")
    si = _argument_analysis(sol)
    return sol, {"valid": _valid(sol) and not si["faulty"], "why": si.get("faults"), "edges_imprinted": n,
                 "tolerance_budget": attempt, "region": p.get("name"), "material": p.get("material"),
                 "self_intersection_check": si}


def op_pocket_projection(p, inputs, doc):
    """Pocket (recess) of drawn regions, `depth` mm deep measured along the view direction from the surface that faces
    the viewer: removed = region prism - (clean skin shifted `depth` into the body), cut from the body. The removed
    solid reaches into the air and shares no face with the body (an earlier version that cut "prism ∩ body - shifted"
    shared the body's own surface and self-intersected where imprints had split it; found by BRepAlgoAPI_Check).
    side views: both sides (+Y and -Y); top: from +Z; front: from -X; rear: from +X."""
    from cad.validate import _argument_analysis
    body = inputs[0][0]
    ref = inputs[1][0] if len(inputs) > 1 else body       # depth reference: the clean outer skin (no imprint edges)
    p = {**p, "polygons": [[[c * p.get("scale", 1.0) for c in q] for q in poly] for poly in p["polygons"]]}
    bb = __import__("cad.validate", fromlist=["bbox"]).bbox(body)
    view, d = p["view"], float(p["depth"])
    ax = _AXIS[view]
    prisms = _region_prism(view, p["polygons"], bb[ax] - 50.0, bb[ax + 3] + 50.0)
    prism = prisms[0]
    for q in prisms[1:]:                                   # touching regions (louvre bays) -> ONE tool solid
        prism, _ = K.boolean("fuse", prism, q, "pocket regions")
    dirs = {"side": [(0, 1, 0), (0, -1, 0)], "top": [(0, 0, 1)], "front": [(-1, 0, 0)], "rear": [(1, 0, 0)]}[view]
    res = body
    for dv in dirs:
        # removed = region prism minus the skin shifted INTO the body by `depth` along the view direction. It reaches
        # out into the air, so it shares no face with the body (no coincident-face Boolean); cutting air removes nothing.
        shifted = K.transformed(ref, translate=tuple(-d * c for c in dv))
        tool, _ = K.boolean("cut", prism, shifted, "pocket tool")
        if not K.solids(tool):
            continue
        res, _ = K.boolean("cut", res, tool, f"pocket {p.get('name')}")
    if res is body:
        raise K.KernelError(f"pocket {p.get('name')}: the region does not cut the body")
    s = K.solids(res)
    if len(s) != 1:
        raise K.KernelError(f"pocket {p.get('name')}: left {len(s)} solids")
    si = _argument_analysis(s[0])
    return s[0], {"valid": _valid(s[0]) and not si["faulty"], "why": si.get("faults"), "region": p.get("name"),
                  "depth_mm": d, "self_intersection_check": si}


OPS["imprint_projection"] = op_imprint_projection
OPS["pocket_projection"] = op_pocket_projection
