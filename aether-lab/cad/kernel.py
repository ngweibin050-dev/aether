"""Deterministic OpenCascade feature operations (CAD construction stage).

Every operation is a plain function of typed, already-resolved parameters (numbers, lists of numbers, enum strings)
and of the shapes produced by the features it depends on. There is no path from a model's text to code: the planner
writes a document of operation NAMES (an enum, see OPS) and numbers, and cad/document.py looks the name up here.

Units: mm. Model frame: X from the front end towards the rear, Y lateral (0 = symmetry plane), Z up from the ground.
"""
from __future__ import annotations

import math

import numpy as np
from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire,
                                BRepBuilderAPI_Transform)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.GeomAPI import GeomAPI_Interpolate
from OCP.GeomAbs import GeomAbs_C2
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.TColgp import TColgp_HArray1OfPnt
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Shape


class KernelError(RuntimeError):
    """An operation the kernel could not perform; carries the feature id when raised from a recompute."""


# ------------------------------------------------------------------------------------------------ helpers
def _pnt(p):
    return gp_Pnt(float(p[0]), float(p[1]), float(p[2]))


def solids(shape):
    out = []
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        out.append(TopoDS.Solid_s(ex.Current()))
        ex.Next()
    return out


def one_solid(shape, what):
    s = solids(shape)
    if len(s) != 1:
        raise KernelError(f"{what}: expected 1 solid, got {len(s)}")
    return s[0]


def compound(shapes):
    c = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(c)
    for s in shapes:
        b.Add(c, s)
    return c


def transformed(shape, translate=(0, 0, 0), rotate=None, mirror_y=False):
    t = gp_Trsf()
    if mirror_y:
        t.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)))
        shape = BRepBuilderAPI_Transform(shape, t, True).Shape()
        t = gp_Trsf()
    if rotate:
        axis, deg = rotate
        t.SetRotation(gp_Ax1(gp_Pnt(*axis[0]), gp_Dir(*axis[1])), math.radians(deg))
        shape = BRepBuilderAPI_Transform(shape, t, True).Shape()
        t = gp_Trsf()
    if any(translate):
        t.SetTranslation(gp_Vec(*map(float, translate)))
        shape = BRepBuilderAPI_Transform(shape, t, True).Shape()
    return shape


def _boolean(kind, a, b, what):
    op = {"fuse": BRepAlgoAPI_Fuse, "cut": BRepAlgoAPI_Cut, "common": BRepAlgoAPI_Common}[kind]()
    from OCP.TopTools import TopTools_ListOfShape
    la, lb = TopTools_ListOfShape(), TopTools_ListOfShape()
    la.Append(a)
    lb.Append(b)
    op.SetArguments(la)
    op.SetTools(lb)
    op.SetFuzzyValue(1e-5)
    op.SetRunParallel(True)
    op.Build()
    if not op.IsDone():
        raise KernelError(f"{what}: boolean {kind} failed (not done)")
    r = op.Shape()
    if r.IsNull():
        raise KernelError(f"{what}: boolean {kind} returned a null shape")
    if not BRepCheck_Analyzer(r).IsValid():
        raise KernelError(f"{what}: boolean {kind} produced an invalid shape")
    return r, {"boolean": kind, "result_valid": True}


def _interp_closed(points3d):
    """Periodic interpolating B-spline through 3D points (closed curve, C2)."""
    n = len(points3d)
    arr = TColgp_HArray1OfPnt(1, n)
    for i, p in enumerate(points3d, 1):
        arr.SetValue(i, _pnt(p))
    it = GeomAPI_Interpolate(arr, True, 1e-6)
    it.Perform()
    if not it.IsDone():
        raise KernelError("section curve interpolation failed")
    return it.Curve()


def _interp_open(points3d):
    n = len(points3d)
    arr = TColgp_HArray1OfPnt(1, n)
    for i, p in enumerate(points3d, 1):
        arr.SetValue(i, _pnt(p))
    it = GeomAPI_Interpolate(arr, False, 1e-6)
    it.Perform()
    if not it.IsDone():
        raise KernelError("curve interpolation failed")
    return it.Curve()


def _wire_from_curve(curve):
    e = BRepBuilderAPI_MakeEdge(curve).Edge()
    return BRepBuilderAPI_MakeWire(e).Wire()


def _poly_wire(pts):
    """Closed polyline wire through 3D points."""
    mw = BRepBuilderAPI_MakeWire()
    for a, b in zip(pts, pts[1:] + pts[:1]):
        if np.linalg.norm(np.subtract(a, b)) > 1e-9:
            mw.Add(BRepBuilderAPI_MakeEdge(_pnt(a), _pnt(b)).Edge())
    return mw.Wire()


# ------------------------------------------------------------------------------------------------ body sections
SECTION_COUNTS = {"bottom": 5, "corner_low": 3, "side": 14, "corner_top": 4, "top": 6}


def _envelope_at(env_z, env_w, z):
    return float(np.interp(z, env_z, env_w))


def section_points(x, z_bot, z_top, y_max, env_z, env_wf, env_wr, w_front, crown_frac=0.06, r_low_frac=0.12,
                   r_top_frac=0.22):
    """Half-section (y >= 0) of the body at station x, as an ordered list of (y, z), bottom centre -> top centre,
    with a FIXED number of points per segment (SECTION_COUNTS) so every station has the same topology.

    half-width at height z: y_max * e(z), e = the end views' normalised envelope (front and rear blended by w_front),
    i.e. the plan view gives the station's width and the end views give how that width changes with height.
    crown_frac: how far the top centre rises above the top edge (fraction of the local height);
    r_low_frac / r_top_frac: rounding of the bottom / top edges (fraction of the local height)."""
    H = z_top - z_bot
    if H <= 1e-3 or y_max <= 1e-3:
        raise KernelError(f"station x={x:.1f}: degenerate section (height {H:.3f}, half-width {y_max:.3f})")
    e = lambda z: max(0.05, w_front * _envelope_at(env_z, env_wf, z) + (1 - w_front) * _envelope_at(env_z, env_wr, z))
    rl, rt = r_low_frac * H, r_top_frac * H
    z_edge = z_top - crown_frac * H                       # height of the top edge (where the top meets the side)
    if z_edge - rt <= z_bot + rl:
        rt = rl = 0.45 * (z_edge - z_bot)
    w_low = y_max * e(z_bot + rl)
    w_top = y_max * e(z_edge - rt)
    pts = []
    c = SECTION_COUNTS
    # bottom: centre -> start of the low corner (flat floor)
    for t in np.linspace(0, 1, c["bottom"], endpoint=False):
        pts.append((t * (w_low - rl), z_bot))
    # low corner: quarter ellipse to the side
    for a in np.linspace(-math.pi / 2, 0, c["corner_low"], endpoint=False):
        pts.append((w_low - rl + rl * math.cos(a), z_bot + rl + rl * math.sin(a)))
    # side: follows the envelope
    for z in np.linspace(z_bot + rl, z_edge - rt, c["side"], endpoint=False):
        pts.append((y_max * e(z), z))
    # top corner: from the side into the top surface
    for a in np.linspace(0, math.pi / 2, c["corner_top"], endpoint=False):
        pts.append((w_top - rt + rt * math.cos(a), z_edge - rt + rt * math.sin(a)))
    # top: crowned from the top edge to the centre
    y0 = max(w_top - rt, 1e-3)
    for t in np.linspace(0, 1, c["top"]):
        y = y0 * (1 - t)
        pts.append((y, z_edge + (z_top - z_edge) * (1 - (y / y0) ** 2)))
    return pts


def section_wire(x, half):
    """Closed symmetric section wire in the plane X = x from a half-section (bottom centre -> top centre)."""
    right = [(x, y, z) for y, z in half]
    left = [(x, -y, z) for y, z in reversed(half[1:-1])]
    pts = right + left
    return _wire_from_curve(_interp_closed(pts)), pts


def loft(wires, smooth=False, continuity="C2", what="loft"):
    """Solid through closed section wires. smooth=False (default): the surface INTERPOLATES every section (the
    section curves are exactly on the surface). OCCT's smoothing approximation (smooth=True) segfaults on 40+
    periodic B-spline sections (measured on the car body, OCP 7.8 / CadQuery 2.8), so it is not the default.
    Section compatibility (same start point, same direction, one periodic edge each) is guaranteed by construction,
    so OCCT's own re-ordering is off."""
    ts = BRepOffsetAPI_ThruSections(True, False, 1e-6)
    for w in wires:
        ts.AddWire(w)
    ts.CheckCompatibility(False)
    ts.SetSmoothing(bool(smooth))
    if continuity == "C2":
        ts.SetContinuity(GeomAbs_C2)
    ts.Build()
    if not ts.IsDone():
        raise KernelError(f"{what}: loft failed")
    return one_solid(ts.Shape(), what)


# ------------------------------------------------------------------------------------------------ revolved parts
def revolve_profile_y(profile_rz, centre, angle=360.0, what="revolve"):
    """Revolve a closed (radius, axial) profile about an axis parallel to Y through `centre`.
    profile_rz: list of (r, a) points; r = distance from the axis (in the XZ plane, drawn along +Z), a = offset
    along Y from the centre. Straight segments; arcs come from enough points (the tyre) or from fillets later."""
    cx, cy, cz = centre
    pts = [(cx, cy + a, cz + r) for r, a in profile_rz]
    face = BRepBuilderAPI_MakeFace(_poly_wire(pts)).Face()
    rv = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(cx, cy, cz), gp_Dir(0, 1, 0)), math.radians(angle))
    rv.Build()
    if not rv.IsDone():
        raise KernelError(f"{what}: revolve failed")
    return one_solid(rv.Shape(), what)


def revolve_spline_profile_y(profile_rz, centre, what="revolve"):
    """As revolve_profile_y, but the profile's points are joined by one closed interpolating B-spline (smooth tyre
    sidewalls), so the revolved faces are smooth surfaces of revolution."""
    cx, cy, cz = centre
    pts = [(cx, cy + a, cz + r) for r, a in profile_rz]
    w = _wire_from_curve(_interp_closed(pts))
    face = BRepBuilderAPI_MakeFace(w).Face()
    rv = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(cx, cy, cz), gp_Dir(0, 1, 0)), 2 * math.pi)
    rv.Build()
    if not rv.IsDone():
        raise KernelError(f"{what}: revolve failed")
    return one_solid(rv.Shape(), what)


def prism_y(poly_xz, y0, y1, what="prism"):
    """A closed polygon in an XZ plane extruded along Y from y0 to y1."""
    pts = [(x, y0, z) for x, z in poly_xz]
    face = BRepBuilderAPI_MakeFace(_poly_wire(pts)).Face()
    p = BRepPrimAPI_MakePrism(face, gp_Vec(0, y1 - y0, 0))
    p.Build()
    return one_solid(p.Shape(), what)


def cylinder(axis_origin, axis_dir, r, h):
    ax = gp_Ax2(_pnt(axis_origin), gp_Dir(*map(float, axis_dir)))
    return BRepPrimAPI_MakeCylinder(ax, float(r), float(h)).Shape()


def fillet_edges(shape, edge_filter, r, what="fillet"):
    """Fillet the edges of `shape` selected by edge_filter(edge) -> bool (a geometric rule, never an index)."""
    from OCP.TopAbs import TopAbs_EDGE
    mk = BRepFilletAPI_MakeFillet(shape)
    ex = TopExp_Explorer(shape, TopAbs_EDGE)
    n = 0
    while ex.More():
        e = TopoDS.Edge_s(ex.Current())
        if edge_filter(e):
            mk.Add(float(r), e)
            n += 1
        ex.Next()
    if not n:
        return shape, 0
    mk.Build()
    if not mk.IsDone():
        raise KernelError(f"{what}: fillet failed")
    return mk.Shape(), n


def edge_midpoint(e):
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    c = BRepAdaptor_Curve(e)
    p = c.Value((c.FirstParameter() + c.LastParameter()) / 2)
    return np.array([p.X(), p.Y(), p.Z()])


def boolean(kind, a, b, what):
    return _boolean(kind, a, b, what)


# ------------------------------------------------------------------------------------------------ skinned body
def skin_body(sections, tol3d=0.6, deg_max=6, what="body skin"):
    """Section-driven NURBS body: sections = [[(x, y, z), ...] per station], each the RIGHT half (y >= 0) from the
    bottom centre to the top centre with the same number of points (correspondence by index). One B-spline surface
    is fitted through the grid (stations along u, section points along v; GeomAPI_PointsToBSplineSurface.Approximate,
    C2, within tol3d of every point), mirrored at the symmetry plane Y = 0, closed at both ends by planar faces bounded
    by the surfaces' own end iso-curves, sewn, and made a solid. Exact symmetry by construction."""
    from OCP.TColgp import TColgp_Array2OfPnt
    from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCP.BRepLib import BRepLib
    from OCP.ShapeFix import ShapeFix_Solid
    from OCP.GeomAbs import GeomAbs_C2 as _C2
    nu, nv = len(sections), len(sections[0])
    if any(len(s) != nv for s in sections):
        raise KernelError(f"{what}: sections have different point counts")
    arr = TColgp_Array2OfPnt(1, nu, 1, nv)
    for i, sec in enumerate(sections, 1):
        for j, p in enumerate(sec, 1):
            arr.SetValue(i, j, _pnt(p))
    # Interpolation with iso-parametric (uniform) parameters: the surface passes through every section point. The
    # least-squares approximation and chord-length / centripetal interpolation overshoot by metres on this grid
    # (measured: bbox y down to -25 m), so they are not used. The bounding box is checked against the points.
    from OCP.Approx import Approx_ParametrizationType
    ap = GeomAPI_PointsToBSplineSurface()
    ap.Interpolate(arr, Approx_ParametrizationType.Approx_IsoParametric, False)
    if not ap.IsDone():
        raise KernelError(f"{what}: surface interpolation failed")
    surf = ap.Surface()
    P = np.array([p for sec in sections for p in sec], float)
    u0_, u1_, v0_, v1_ = surf.Bounds()
    Q = np.array([[(lambda q: (q.X(), q.Y(), q.Z()))(surf.Value(u, v)) for v in np.linspace(v0_, v1_, 48)]
                  for u in np.linspace(u0_, u1_, 6 * nu)]).reshape(-1, 3)
    span = P.max(0) - P.min(0)
    over = np.maximum(Q.max(0) - P.max(0), P.min(0) - Q.min(0)) / np.maximum(span, 1e-9)
    if over.max() > 0.08:
        raise KernelError(f"{what}: surface overshoots the section points by {100 * over.max():.0f} % of the size")
    right = BRepBuilderAPI_MakeFace(surf, 1e-6).Face()
    left = TopoDS.Face_s(transformed(right, mirror_y=True))
    # end caps from the two faces' boundary edges at u = first / last
    from OCP.BRepTools import BRepTools
    u0, u1, v0, v1 = BRepTools.UVBounds_s(right)
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    caps = []
    for u in (u0, u1):
        iso_r = surf.UIso(u)
        e_r = BRepBuilderAPI_MakeEdge(iso_r, v0, v1).Edge()
        e_l = TopoDS.Edge_s(transformed(e_r, mirror_y=True))
        w = BRepBuilderAPI_MakeWire(e_r, e_l).Wire()
        mf = BRepBuilderAPI_MakeFace(w, True)
        if not mf.IsDone():
            raise KernelError(f"{what}: end cap at u={u:.3f} is not planar")
        caps.append(mf.Face())
    sew = BRepBuilderAPI_Sewing(1e-3)
    for f in (right, left, *caps):
        sew.Add(f)
    sew.Perform()
    shell = sew.SewedShape()
    from OCP.TopAbs import TopAbs_SHELL
    ex = TopExp_Explorer(shell, TopAbs_SHELL)
    if not ex.More():
        raise KernelError(f"{what}: sewing produced no shell")
    ms = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(ex.Current()))
    sol = ms.Solid()
    BRepLib.OrientClosedSolid_s(sol)
    fx = ShapeFix_Solid(sol)
    fx.Perform()
    sol = one_solid(fx.Solid(), what)
    return sol, {"surface": {"type": "B-spline (interpolating, iso-parametric)", "u_poles": surf.NbUPoles(),
                             "v_poles": surf.NbVPoles(), "u_degree": surf.UDegree(), "v_degree": surf.VDegree(),
                             "overshoot_pct_of_size": [round(100 * float(v), 2) for v in over]}, "faces": 4}


# ------------------------------------------------------------------------------------------------ keypoint sections
SEG = {"bottom": 4, "corner": 3, "flank": 6, "shoulder": 5, "glass": 6, "roof": 7}
KEYPOINT_ORDER = ("z_bot", "z_max", "z_sh", "z_re", "z_top")


def _bez2(p0, c, p1, n, endpoint=False):
    t = np.linspace(0, 1, n, endpoint=endpoint)[:, None]
    return (1 - t) ** 2 * np.asarray(p0) + 2 * (1 - t) * t * np.asarray(c) + t ** 2 * np.asarray(p1)


def section_keypoints(k, env_z, env_w):
    """Half-section (y >= 0) of a station as a constrained sketch through named keypoints, bottom centre -> top centre,
    with a fixed number of points per segment (SEG) so every station has the same topology:
      bottom centre (0, z_bot) -> floor edge -> sill (w_sill, z_bot + r_low)          [flat floor + round corner]
      -> max width (y_max, z_max)                       [flank: end-view envelope shape, scaled to y_max]
      -> shoulder / beltline (y_sh, z_sh)               [quadratic, tangent vertical at z_max]
      -> roof edge (y_re, z_re)                         [side glass, outward bulge glass_bulge]
      -> top centre (0, z_top)                          [crown: horizontal tangent at the centre]
    k: dict with z_bot, z_top, y_max, z_max, y_sh, z_sh, y_re, z_re, r_low, glass_bulge.
    Constraint checks (raise KernelError): z_bot < z_bot + r_low < z_max <= z_sh <= z_re <= z_top, 0 < y_re <= y_sh <=
    y_max (within 0.5 mm)."""
    zb, zt, ym, zm = k["z_bot"], k["z_top"], k["y_max"], k["z_max"]
    ysh, zsh, yre, zre = k["y_sh"], k["z_sh"], k["y_re"], k["z_re"]
    rl, bulge = k["r_low"], k.get("glass_bulge", 0.0)
    eps = 0.5
    if not (zb + rl < zm - eps and zm <= zsh + eps and zsh <= zre + eps and zre <= zt + eps):
        raise KernelError(f"section x={k.get('x', 0):.1f}: heights out of order (z_bot {zb:.1f}, sill {zb + rl:.1f}, "
                          f"z_max {zm:.1f}, z_sh {zsh:.1f}, z_re {zre:.1f}, z_top {zt:.1f})")
    if not (0 < yre <= ysh + eps and ysh <= ym + eps):
        raise KernelError(f"section x={k.get('x', 0):.1f}: widths out of order (y_re {yre:.1f}, y_sh {ysh:.1f}, y_max {ym:.1f})")
    e = lambda z: float(np.interp(z, env_z, env_w))
    norm = max(e(zm), 1e-6)
    flank = lambda z: min(ym, ym * e(z) / norm)
    w_sill = flank(zb + rl)
    P = []
    for t in np.linspace(0, 1, SEG["bottom"], endpoint=False):
        P.append((t * (w_sill - rl), zb))
    for a in np.linspace(-np.pi / 2, 0, SEG["corner"], endpoint=False):
        P.append((w_sill - rl + rl * np.cos(a), zb + rl + rl * np.sin(a)))
    for z in np.linspace(zb + rl, zm, SEG["flank"], endpoint=False):
        P.append((flank(z), z))
    P += [tuple(p) for p in _bez2((ym, zm), (ym, zsh), (ysh, zsh), SEG["shoulder"])]
    # glass: straight from the beltline to the roof edge, bowed outward by bulge x its length
    g0, g1 = np.array([ysh, zsh]), np.array([yre, zre])
    L = np.linalg.norm(g1 - g0)
    nrm = np.array([g1[1] - g0[1], -(g1[0] - g0[0])]) / max(L, 1e-9)       # outward (towards +y)
    if nrm[0] < 0:
        nrm = -nrm
    P += [tuple(p) for p in _bez2(g0, (g0 + g1) / 2 + nrm * bulge * L * 2, g1, SEG["glass"])]
    pexp = k.get("crown_exp", 2.0)
    for t in np.linspace(0, 1, SEG["roof"]):
        y = yre * (1 - t)
        P.append((y, zt - (zt - zre) * (y / max(yre, 1e-9)) ** pexp))
    cap = k.get("cap")
    if cap is not None:                                            # hard drawing constraint: never wider than the end views
        cz, cw = cap
        P = [(min(y, float(np.interp(z, cz, cw))), z) if y > 0 else (y, z) for y, z in P]
    # successive points must be distinct (zero-length chords break the surface fit)
    out = [P[0]]
    for p in P[1:]:
        if np.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) < 0.05:
            p = (p[0] + 0.05, p[1] + 0.05)
        out.append(p)
    return out


def half_section_edge(x, half_yz):
    """One planar half-section (in the plane X = x) as an interpolating B-spline through the keypoint sketch's points,
    chord-length parametrised, tangent fixed along -Z/+Y... at the centreline: +Y at the bottom centre, -Y at the top
    centre, so the mirrored halves join with G1 across the symmetry plane and no section crosses Y = 0."""
    from OCP.TColgp import TColgp_Array1OfVec
    from OCP.TColStd import TColStd_HArray1OfBoolean
    pts = [(x, y, z) for y, z in half_yz]
    n = len(pts)
    arr = TColgp_HArray1OfPnt(1, n)
    for i, p in enumerate(pts, 1):
        arr.SetValue(i, _pnt(p))
    it = GeomAPI_Interpolate(arr, False, 1e-6)
    tang = TColgp_Array1OfVec(1, n)
    flags = TColStd_HArray1OfBoolean(1, n)
    for i in range(1, n + 1):
        tang.SetValue(i, gp_Vec(0, 0, 0))
        flags.SetValue(i, False)
    tang.SetValue(1, gp_Vec(0, 1, 0))
    tang.SetValue(n, gp_Vec(0, -1, 0))
    flags.SetValue(1, True)
    flags.SetValue(n, True)
    it.Load(tang, flags, True)
    it.Perform()
    if not it.IsDone():
        raise KernelError(f"section x={x:.1f}: interpolation failed")
    c = it.Curve()
    # the curve must stay on the +Y side (no overshoot through the symmetry plane)
    u0, u1 = c.FirstParameter(), c.LastParameter()
    ys = [c.Value(u).Y() for u in np.linspace(u0, u1, 400)[1:-1]]
    if min(ys) < -1e-3:
        raise KernelError(f"section x={x:.1f}: curve crosses the symmetry plane (min y {min(ys):.3f} mm)")
    return BRepBuilderAPI_MakeEdge(c).Edge()


def skin_body_v2(stations_half, what="body"):
    """Section-driven NURBS body: stations_half = [(x, [(y, z), ...]), ...] right halves (bottom centre -> top centre).
    Each half-section is a planar B-spline (half_section_edge); they are lofted (BRepOffsetAPI_ThruSections, open
    sections -> one B-spline face through every section), mirrored at Y = 0, closed at both ends by planar faces made of
    the first / last section edges and their mirror images, sewn and made a solid."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCP.BRepLib import BRepLib
    from OCP.ShapeFix import ShapeFix_Solid
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL
    edges = [half_section_edge(x, h) for x, h in stations_half]
    ts = BRepOffsetAPI_ThruSections(False, False, 1e-6)
    for e in edges:
        ts.AddWire(BRepBuilderAPI_MakeWire(e).Wire())
    ts.CheckCompatibility(False)
    ts.SetSmoothing(False)
    ts.Build()
    if not ts.IsDone():
        raise KernelError(f"{what}: loft of the half-sections failed")
    ex = TopExp_Explorer(ts.Shape(), TopAbs_FACE)
    faces_r = []
    while ex.More():
        faces_r.append(TopoDS.Face_s(ex.Current()))
        ex.Next()
    sew = BRepBuilderAPI_Sewing(1e-4)
    for f in faces_r:
        sew.Add(f)
        sew.Add(transformed(f, mirror_y=True))
    for e in (edges[0], edges[-1]):                     # caps from the exact end-section curves (+ mirror image)
        mw = BRepBuilderAPI_MakeWire(e, TopoDS.Edge_s(transformed(e, mirror_y=True)))
        if not mw.IsDone():
            raise KernelError(f"{what}: end cap wire could not be closed")
        mf = BRepBuilderAPI_MakeFace(mw.Wire(), True)
        if not mf.IsDone():
            raise KernelError(f"{what}: end cap is not planar")
        sew.Add(mf.Face())
    sew.Perform()
    ex = TopExp_Explorer(sew.SewedShape(), TopAbs_SHELL)
    if not ex.More():
        raise KernelError(f"{what}: sewing produced no shell")
    sol = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(ex.Current())).Solid()
    BRepLib.OrientClosedSolid_s(sol)
    fx = ShapeFix_Solid(sol)
    fx.Perform()
    sol = one_solid(fx.Solid(), what)
    nf = len(faces_r)
    return sol, {"construction": "planar half-section B-splines (keypoint sketches) -> ThruSections loft -> mirror at "
                                 "Y=0 -> planar end caps from the end sections -> sew -> solid",
                 "sections": len(edges), "loft_faces_per_side": nf}


def _interp_params(pts, params, t0=None, t1=None):
    """Interpolating cubic B-spline through pts at the given parameters, optional end tangents (scaled)."""
    from OCP.TColStd import TColStd_HArray1OfReal
    n = len(pts)
    arr = TColgp_HArray1OfPnt(1, n)
    for i, p in enumerate(pts, 1):
        arr.SetValue(i, _pnt(p))
    par = TColStd_HArray1OfReal(1, n)
    for i, t in enumerate(params, 1):
        par.SetValue(i, float(t))
    it = GeomAPI_Interpolate(arr, par, False, 1e-7)
    if t0 is not None:
        it.Load(gp_Vec(*t0), gp_Vec(*t1), True)
    it.Perform()
    if not it.IsDone():
        raise KernelError("interpolation failed")
    return it.Curve()


def skin_body_v3(stations_half, what="body"):
    """Section-driven NURBS body by skinning (Piegl & Tiller): stations_half = [(x, [(y, z), ...])] right halves,
    bottom centre -> top centre, the same point count at every station (keypoint sketches).
    1. one common v-parametrisation (mean chord length over all stations) -> every half-section is interpolated at the
       SAME parameters with end tangents +Y (bottom centre) / -Y (top centre) -> identical knot vectors;
    2. every pole row is interpolated along X with the stations' x positions as parameters -> identical u knots;
    3. the pole grid is one cubic x cubic B-spline surface through every section; mirrored at Y = 0; planar caps from
       the end sections; sewn; solid. Symmetric and G1 across the symmetry plane by construction."""
    from OCP.Geom import Geom_BSplineSurface
    from OCP.TColgp import TColgp_Array2OfPnt
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCP.BRepLib import BRepLib
    from OCP.ShapeFix import ShapeFix_Solid
    from OCP.TopAbs import TopAbs_SHELL
    xs = np.array([x for x, _ in stations_half], float)
    if np.any(np.diff(xs) <= 0):
        raise KernelError(f"{what}: stations must be strictly increasing in x")
    H = [np.asarray(h, float) for _, h in stations_half]
    nv = len(H[0])
    if any(len(h) != nv for h in H):
        raise KernelError(f"{what}: stations have different point counts")
    # 1. common v parameters
    chords = np.array([np.r_[0, np.cumsum(np.linalg.norm(np.diff(h, axis=0), axis=1))] for h in H])
    chords /= np.maximum(chords[:, -1:], 1e-12)
    tv = chords.mean(0)
    tv[0], tv[-1] = 0.0, 1.0
    tv = np.maximum.accumulate(tv + np.arange(nv) * 1e-9)
    curves = []
    for x, h, ch in zip(xs, H, chords):
        L = float(np.sum(np.linalg.norm(np.diff(h, axis=0), axis=1)))
        c = _interp_params([(x, y, z) for y, z in h], tv, (0, L * 0.6, 0), (0, -L * 0.6, 0))
        ys = [c.Value(u).Y() for u in np.linspace(c.FirstParameter(), c.LastParameter(), 600)[1:-1]]
        if min(ys) < -1e-3:
            raise KernelError(f"{what}: section x={x:.1f} crosses the symmetry plane (min y {min(ys):.3f} mm)")
        curves.append(c)
    npv = curves[0].NbPoles()
    if any(c.NbPoles() != npv for c in curves):
        raise KernelError(f"{what}: section curves are not compatible")
    vk = [curves[0].Knot(i) for i in range(1, curves[0].NbKnots() + 1)]
    vm = [curves[0].Multiplicity(i) for i in range(1, curves[0].NbKnots() + 1)]
    # 2. pole rows along x
    tu = (xs - xs[0]) / (xs[-1] - xs[0])
    rows = []
    for j in range(1, npv + 1):
        P = [curves[i].Pole(j) for i in range(len(curves))]
        rows.append(_interp_params([(p.X(), p.Y(), p.Z()) for p in P], tu))
    npu = rows[0].NbPoles()
    uk = [rows[0].Knot(i) for i in range(1, rows[0].NbKnots() + 1)]
    um = [rows[0].Multiplicity(i) for i in range(1, rows[0].NbKnots() + 1)]
    poles = TColgp_Array2OfPnt(1, npu, 1, npv)
    for j, r in enumerate(rows, 1):
        for i in range(1, npu + 1):
            poles.SetValue(i, j, r.Pole(i))
    def arr_r(v):
        a = TColStd_Array1OfReal(1, len(v))
        for i, x in enumerate(v, 1):
            a.SetValue(i, float(x))
        return a
    def arr_i(v):
        a = TColStd_Array1OfInteger(1, len(v))
        for i, x in enumerate(v, 1):
            a.SetValue(i, int(x))
        return a
    surf = Geom_BSplineSurface(poles, arr_r(uk), arr_r(vk), arr_i(um), arr_i(vm), rows[0].Degree(), curves[0].Degree())
    right = BRepBuilderAPI_MakeFace(surf, 1e-6).Face()
    # fidelity: the surface must stay within the sections' envelope (no overshoot between stations)
    allp = np.vstack([np.c_[np.full(len(h), x), h] for x, h in zip(xs, H)])
    Q = np.array([[(lambda q: (q.X(), q.Y(), q.Z()))(surf.Value(u, v)) for v in np.linspace(0, 1, 60)]
                  for u in np.linspace(0, 1, 8 * len(xs))]).reshape(-1, 3)
    span = allp.max(0) - allp.min(0)
    over = np.maximum(Q.max(0) - allp.max(0), allp.min(0) - Q.min(0)) / np.maximum(span, 1e-9)
    if over.max() > 0.03:
        raise KernelError(f"{what}: surface overshoots the sections by {100 * over.max():.1f} % of the size")
    sew = BRepBuilderAPI_Sewing(1e-4)
    sew.Add(right)
    sew.Add(transformed(right, mirror_y=True))
    for c in (curves[0], curves[-1]):
        e = BRepBuilderAPI_MakeEdge(c).Edge()
        mw = BRepBuilderAPI_MakeWire(e, TopoDS.Edge_s(transformed(e, mirror_y=True)))
        mf = BRepBuilderAPI_MakeFace(mw.Wire(), True)
        if not mf.IsDone():
            raise KernelError(f"{what}: end cap is not planar")
        sew.Add(mf.Face())
    sew.Perform()
    ex = TopExp_Explorer(sew.SewedShape(), TopAbs_SHELL)
    if not ex.More():
        raise KernelError(f"{what}: sewing produced no shell")
    sol = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(ex.Current())).Solid()
    BRepLib.OrientClosedSolid_s(sol)
    fx = ShapeFix_Solid(sol)
    fx.Perform()
    sol = one_solid(fx.Solid(), what)
    return sol, {"construction": "skinning: common-parameter half-section B-splines -> pole rows interpolated along X "
                                 "-> one cubic B-spline surface -> mirror at Y=0 -> planar end caps -> sew -> solid",
                 "sections": len(xs), "surface_poles": [npu, npv], "degree": [rows[0].Degree(), curves[0].Degree()],
                 "overshoot_pct_of_size": [round(100 * float(v), 3) for v in over]}
