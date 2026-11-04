PARAMS = {"length": {"value": 100, "unit": "mm", "provenance": "measured", "evidence": "FRONT VIEW 100.0 and TOP VIEW 100.0 dimension"}, "width": {"value": 60, "unit": "mm", "provenance": "read", "evidence": "TOP VIEW 60.0 and RIGHT VIEW 60.0 dimension"}, "height": {"value": 70, "unit": "mm", "provenance": "read", "evidence": "FRONT VIEW 70.0 and RIGHT VIEW 70.0 dimension"}, "plate_thickness": {"value": 10, "unit": "mm", "provenance": "assumed", "evidence": "Strip height in FRONT/RIGHT/TOP views, no thickness callout, estimated 8-12mm"}, "hole_diameter": {"value": 12, "unit": "mm", "provenance": "assumed", "evidence": "Circles drawn in FRONT/TOP views with no diameter note, estimated from size vs 100mm width"}, "hole_offset_x": {"value": 25, "unit": "mm", "provenance": "inferred", "evidence": "Hole circles symmetric about centre X=50 in FRONT and TOP views"}, "hole_spacing": {"value": 50, "unit": "mm", "provenance": "inferred", "evidence": "Two hole circles symmetric about centre, estimated centres at 25 and 75"}, "base_hole_y": {"value": 32, "unit": "mm", "provenance": "inferred", "evidence": "Base hole position from back face estimated from TOP VIEW circle placement"}, "upright_hole_z": {"value": 38, "unit": "mm", "provenance": "inferred", "evidence": "Upright hole height estimated from FRONT VIEW circle placement"}, "gusset_thickness": {"value": 8, "unit": "mm", "provenance": "assumed", "evidence": "Central rectangle width in FRONT/TOP views, no dimension annotated"}, "gusset_length_y": {"value": 48, "unit": "mm", "provenance": "inferred", "evidence": "RIGHT VIEW triangle foot along base estimated from hypotenuse foot"}, "gusset_height_z": {"value": 58, "unit": "mm", "provenance": "inferred", "evidence": "RIGHT VIEW triangle top along upright estimated from hypotenuse top"}, "weld_radius": {"value": 3, "unit": "mm", "provenance": "assumed", "evidence": "Fabricated welded construction estimate, no weld symbol visible"}}

def prism(points, vec):
    pts = [cq.Vector(p[0], p[1], p[2]) for p in points]
    pts.append(cq.Vector(points[0][0], points[0][1], points[0][2]))
    wire = cq.Wire.makePolygon(pts)
    face = cq.Face.makeFromWires(wire)
    return cq.Solid.extrudeLinear(face, cq.Vector(vec[0], vec[1], vec[2]))

def box(x0, y0, z0, dx, dy, dz):
    return cq.Solid.makeBox(dx, dy, dz, cq.Vector(x0, y0, z0))

L = P("length")
W = P("width")
H = P("height")
t = P("plate_thickness")
hr = P("hole_diameter") / 2
hx1 = P("hole_offset_x")
hx2 = hx1 + P("hole_spacing")
by = P("base_hole_y")
uz = P("upright_hole_z")
gt = P("gusset_thickness")
gl = P("gusset_length_y")
gh = P("gusset_height_z")
wr = P("weld_radius")
cx = L / 2
gx0 = cx - gt / 2
gx1 = cx + gt / 2
overshoot = 2

base = box(0, 0, 0, L, W, t)
for hx in (hx1, hx2):
    cyl = cq.Solid.makeCylinder(hr, t + 2 * overshoot, cq.Vector(hx, by, -overshoot), cq.Vector(0, 0, 1))
    base = base.cut(cyl)

upright = box(0, 0, 0, L, t, H)
for hx in (hx1, hx2):
    cyl = cq.Solid.makeCylinder(hr, t + 2 * overshoot, cq.Vector(hx, -overshoot, uz), cq.Vector(0, 1, 0))
    upright = upright.cut(cyl)

gusset = prism([(gx0, t, t), (gx0, gl, t), (gx0, t, gh)], (gt, 0, 0))

weld_base = prism([(0, t, t), (0, t + wr, t), (0, t, t + wr)], (L, 0, 0))

b1 = prism([(gx0, t, t), (gx0 - wr, t, t), (gx0, t, t + wr)], (0, gl - t, 0))
b2 = prism([(gx1, t, t), (gx1 + wr, t, t), (gx1, t, t + wr)], (0, gl - t, 0))
b3 = prism([(gx0, t, t), (gx0 - wr, t, t), (gx0, t + wr, t)], (0, 0, gh - t))
b4 = prism([(gx1, t, t), (gx1 + wr, t, t), (gx1, t + wr, t)], (0, 0, gh - t))
c1 = box(gx0 - wr, gl - wr, t, gt + 2 * wr, wr, wr)
c2 = box(gx0 - wr, t, gh - wr, gt + 2 * wr, wr, wr)
weld_gusset = b1.fuse(b2).fuse(b3).fuse(b4).fuse(c1).fuse(c2)

parts = [{"name": "base_plate", "shape": base, "colour": "#9aa3a8", "material": "metal"}, {"name": "upright_plate", "shape": upright, "colour": "#9aa3a8", "material": "metal"}, {"name": "gusset_rib", "shape": gusset, "colour": "#8f979d", "material": "metal"}, {"name": "weld_base_upright", "shape": weld_base, "colour": "#7d858b", "material": "metal"}, {"name": "weld_gusset", "shape": weld_gusset, "colour": "#7d858b", "material": "metal"}]