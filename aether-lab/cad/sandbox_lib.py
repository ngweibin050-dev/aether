"""General CAD building blocks for model-written programs (cad/codegen.py). Object-independent operations on
CadQuery / OpenCascade solids; a program calls them by name. Units mm; frame X length (front x = 0), Y across, Z up.

Every function returns a cq.Workplane holding solids (or a list of them for split_panels) and raises ValueError with
a plain explanation when the input cannot make a valid solid, so the model can fix its call."""
from __future__ import annotations

import math

import cadquery as cq

AXES = {"side": ("XZ", 1), "top": ("XY", 2), "front": ("YZ", 0)}       # view -> plane of its drawing, axis it looks along


def _wp(shape):
    return cq.Workplane("XY").newObject([shape])


def _solid(obj):
    vals = obj.vals() if isinstance(obj, cq.Workplane) else [obj]
    sol = [v for v in vals if isinstance(v, cq.Shape)]
    if not sol:
        raise ValueError("no solid in the input")
    return sol[0] if len(sol) == 1 else cq.Compound.makeCompound(sol)


def _normalise_loop(loop, n=32):
    """A closed section loop made loft-safe: duplicates removed, counter-clockwise, starting at its top point,
    resampled to n points evenly by arc length. Loops that start at different points or wind differently twist a
    loft into an invalid solid; after this every section is parametrised the same way."""
    pts = []
    for a, b in loop:
        if not pts or math.hypot(a - pts[-1][0], b - pts[-1][1]) > 1e-6:
            pts.append((float(a), float(b)))
    if len(pts) > 2 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-6:
        pts.pop()
    if len(pts) < 3:
        raise ValueError("a section has fewer than 3 distinct points")
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    if area < 0:
        pts.reverse()
    ca = sum(p[0] for p in pts) / len(pts)
    top = max(range(len(pts)), key=lambda i: (round(pts[i][1], 6), -abs(pts[i][0] - ca)))
    pts = pts[top:] + pts[:top]
    ring = pts + [pts[0]]
    seg = [math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(ring, ring[1:])]
    total = sum(seg)
    out, acc, j = [], 0.0, 0
    for k in range(n):
        target = total * k / n
        while j < len(seg) - 1 and acc + seg[j] < target:
            acc += seg[j]
            j += 1
        t = (target - acc) / seg[j] if seg[j] > 1e-12 else 0.0
        p, q = ring[j], ring[j + 1]
        out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def smooth_loft(sections, axis="x"):
    """A smooth solid through closed sections. sections = [(t, [(a, b), ...]), ...]: t is the position along `axis`
    (x by default) and (a, b) the loop in the plane across it ((y, z) for axis x), any number of points >= 3 in any
    order of winding: every loop is normalised (same winding, same start, same point count) before the smooth loft
    (ruled=False), and OpenCascade's shape repair is tried before giving up."""
    if len(sections) < 2:
        raise ValueError("smooth_loft needs at least 2 sections")
    sections = sorted(sections, key=lambda s_: s_[0])
    wires = []
    for t, loop in sections:
        nl = _normalise_loop(loop)
        if axis == "x":
            pts = [cq.Vector(t, a, b) for a, b in nl]
        elif axis == "y":
            pts = [cq.Vector(a, t, b) for a, b in nl]
        else:
            pts = [cq.Vector(a, b, t) for a, b in nl]
        wires.append(cq.Wire.assembleEdges([cq.Edge.makeSpline(pts, periodic=True)]))
    sol = cq.Solid.makeLoft(wires, ruled=False)
    if not sol.isValid():
        from OCP.ShapeFix import ShapeFix_Shape
        fx = ShapeFix_Shape(sol.wrapped)
        fx.Perform()
        fixed = cq.Shape.cast(fx.Shape())
        if fixed.isValid():
            sol = fixed
        else:
            raise ValueError("smooth_loft made an invalid solid even after normalising the sections: a section loop "
                             "crosses itself, or neighbouring sections differ too much (add sections in between)")
    return _wp(sol)


def split_panels(body, lines, gap=3.5):
    """Split a body into separate panels with a shut line (a gap of `gap` mm) along each cut line.
    lines = [(view, [(a, b), ...]), ...]: a polyline drawn in that view ("side": (x, z), "top": (x, y),
    "front": (y, z)), extruded straight through the body along the view direction. Returns a list of panels
    (cq.Workplane each), sorted by centre x then z; name them in your program."""
    b = _solid(body)
    bb = b.BoundingBox()
    big = 4 * max(bb.xlen, bb.ylen, bb.zlen) + 100
    cutter = None
    for view, pts in lines:
        if view not in AXES or len(pts) < 2:
            raise ValueError(f"cut line needs a view in {list(AXES)} and at least 2 points")
        plane, ax = AXES[view]
        pts = [tuple(map(float, q)) for q in pts]
        for i0, i1 in ((0, 1), (-1, -2)):                     # extend both ends: a line drawn to the edge still cuts through
            (ax_, ay_), (bx_, by_) = pts[i0], pts[i1]
            d = math.hypot(ax_ - bx_, ay_ - by_) or 1.0
            pts[i0] = (ax_ + (ax_ - bx_) / d * 300.0, ay_ + (ay_ - by_) / d * 300.0)
        for p, q in zip(pts, pts[1:]):
            dx, dy = q[0] - p[0], q[1] - p[1]
            L = math.hypot(dx, dy)
            if L < 1e-6:
                continue
            ang = math.degrees(math.atan2(dy, dx))
            mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            slab = (cq.Workplane(plane).center(*mid).transformed(rotate=(0, 0, ang))
                    .rect(L + gap, gap).extrude(big / 2, both=True))
            cutter = slab if cutter is None else cutter.union(slab)
    if cutter is None:
        raise ValueError("no cut line")
    res = _wp(b).cut(cutter)
    sols = [s for s in res.solids().vals() if s.Volume() > 1e-3 * b.Volume()]
    if len(sols) < 2:
        raise ValueError("the cut lines did not divide the body: make each line cross the body completely")
    sols.sort(key=lambda s: (round(s.Center().x, 1), round(s.Center().z, 1)))
    return [_wp(s) for s in sols]


def recess(body, view, outline, depth, from_side="min"):
    """Cut an opening `depth` mm deep into the body's outer surface, as seen in `view`: outline = closed polygon
    [(a, b), ...] in that view's plane ("front": (y, z), "side": (x, z), "top": (x, y)). from_side: "min" cuts from
    the low end of the view axis (the front for view "front", the -y side for "side", the bottom for "top"),
    "max" from the high end. Returns (body_with_recess, floor) where floor is the recess's bottom face position
    along the view axis (put the lamp housing / plate there)."""
    b = _solid(body)
    plane, ax = AXES[view]
    bb = b.BoundingBox()
    lo, hi = [(bb.xmin, bb.xmax), (bb.ymin, bb.ymax), (bb.zmin, bb.zmax)][ax]
    reach = max(abs(lo), abs(hi)) + 500                    # long enough to pass through the whole body
    prism = cq.Workplane(plane).polyline(list(outline)).close().extrude(reach, both=True)
    common = _wp(b).intersect(prism)
    cs = [s for s in common.solids().vals()]
    if not cs:
        raise ValueError("recess outline does not overlap the body in that view")
    cb = cq.Compound.makeCompound(cs).BoundingBox()
    c_lo, c_hi = [(cb.xmin, cb.xmax), (cb.ymin, cb.ymax), (cb.zmin, cb.zmax)][ax]
    if from_side == "min":
        a0, a1, floor = c_lo - 200, c_lo + depth, c_lo + depth
    else:
        a0, a1, floor = c_hi - depth, c_hi + 200, c_hi - depth
    # the tool: the outline extruded between a0 and a1 along the view axis
    tool = cq.Workplane(plane).polyline(list(outline)).close().extrude(a1 - a0)
    vec = [cq.Vector(a0, 0, 0), cq.Vector(0, a0, 0), cq.Vector(0, 0, a0)][ax]
    # Workplane(plane) extrudes along its normal: XZ's normal is -Y, so place it by its actual extent
    tb = tool.val().BoundingBox()
    t_lo = [tb.xmin, tb.ymin, tb.zmin][ax]
    shift = [cq.Vector(a0 - t_lo, 0, 0), cq.Vector(0, a0 - t_lo, 0), cq.Vector(0, 0, a0 - t_lo)][ax]
    tool = tool.translate(shift)
    out = _wp(b).cut(tool)
    if not _solid(out).isValid():
        raise ValueError("recess made an invalid solid: use a simpler outline or a smaller depth")
    return out, floor


def revolve_profile(points, axis_origin=(0, 0, 0), axis_dir=(0, 1, 0)):
    """A solid of revolution: points = closed profile [(r, h), ...] (r distance from the axis >= 0, h along it),
    revolved 360 degrees about the axis through axis_origin along axis_dir (wheels: axis_dir (0, 1, 0))."""
    if len(points) < 3 or min(r for r, _ in points) < 0:
        raise ValueError("revolve_profile needs >= 3 points with r >= 0")
    prof = cq.Workplane("XZ").polyline([(r, h) for r, h in points]).close().revolve(360, (0, 0, 0), (0, 1, 0))
    s = prof.val()
    d = cq.Vector(*axis_dir).normalized()
    z = cq.Vector(0, 0, 1)                                   # XZ-plane revolve axis is the workplane's local y = global z
    if (d - z).Length > 1e-9:
        axis = z.cross(d)
        ang = math.degrees(math.acos(max(-1.0, min(1.0, z.dot(d)))))
        s = s.rotate(cq.Vector(0, 0, 0), axis if axis.Length > 1e-9 else cq.Vector(1, 0, 0), ang)
    return _wp(s.translate(cq.Vector(*axis_origin)))


def sweep_tube(points, r):
    """A round tube of radius r along a smooth curve through 3D points (roll bars, belts, cables, handles, threads).
    Tries a smooth sweep first; for paths the kernel cannot sweep (long helices, tight bends) it builds the tube from
    short cylinders joined by spheres, which always makes a valid solid."""
    if len(points) < 2:
        raise ValueError("sweep_tube needs >= 2 points")
    pts = [cq.Vector(*map(float, p)) for p in points]
    try:
        path = cq.Workplane("XY").spline(pts, includeCurrent=False)
        t = (pts[1] - pts[0]).normalized()
        xd = t.cross(cq.Vector(0, 0, 1)) if abs(t.z) < 0.99 else cq.Vector(1, 0, 0)
        out = cq.Workplane(cq.Plane(origin=pts[0], xDir=xd, normal=t)).circle(r).sweep(path, transition="round")
        if out.val().isValid() and out.val().Volume() > 0:
            return out
    except Exception:
        pass
    pieces = []                                           # fallback: segments + joints (robust, slightly faceted)
    for a_, b_ in zip(pts, pts[1:]):
        d = b_ - a_
        if d.Length > 1e-6:
            pieces.append(cq.Solid.makeCylinder(r, d.Length, a_, d.normalized()))
    pieces += [cq.Solid.makeSphere(r, p_, angleDegrees1=-90, angleDegrees2=90) for p_ in pts[1:-1]]
    if not pieces:
        raise ValueError("sweep_tube: all points are the same")
    solid = pieces[0]
    for q in pieces[1:]:                                  # one at a time: a single many-argument fuse lost pieces
        solid = solid.fuse(q)
    solid = solid.clean()
    if solid.Volume() < 0.5 * sum(q.Volume() for q in pieces[:len(pts) - 1]):
        raise ValueError("sweep_tube: the tube pieces did not join into one solid; use fewer, smoother points")
    if not solid.isValid():
        raise ValueError("sweep_tube could not make a valid tube along these points: use fewer, smoother points")
    return _wp(solid)


def fillet_safe(obj, r, selector=None):
    """Round edges with radius r (all edges, or a CadQuery selector such as '|Z' or '>Z'); if the kernel cannot,
    the input is returned unchanged (never raises)."""
    try:
        w = obj if isinstance(obj, cq.Workplane) else _wp(obj)
        out = (w.edges(selector) if selector else w.edges()).fillet(r)
        if _solid(out).isValid():
            return out
    except Exception:
        pass
    return obj


NAMES = {"smooth_loft": smooth_loft, "split_panels": split_panels, "recess": recess, "revolve_profile": revolve_profile,
         "sweep_tube": sweep_tube, "fillet_safe": fillet_safe}
