PARAMS = {"length": {"value": 100.0, "unit": "mm", "provenance": "read", "evidence": "100.0 dimension under TOP and FRONT views"}, "width": {"value": 60.0, "unit": "mm", "provenance": "read", "evidence": "60.0 dimension on TOP view and under RIGHT view"}, "height": {"value": 70.0, "unit": "mm", "provenance": "read", "evidence": "70.0 dimension on FRONT and RIGHT views"}, "plate_thickness": {"value": 8.0, "unit": "mm", "provenance": "inferred", "evidence": "thickness of bottom strip in FRONT view and side strip in TOP/RIGHT views, proportioned to 70 mm height"}, "gusset_thickness": {"value": 8.0, "unit": "mm", "provenance": "inferred", "evidence": "width of central rib strip in TOP and FRONT views, similar to plate thickness"}, "gusset_height": {"value": 50.0, "unit": "mm", "provenance": "inferred", "evidence": "triangular rib in RIGHT view rises from base top to below top of vertical plate"}, "gusset_length": {"value": 42.0, "unit": "mm", "provenance": "inferred", "evidence": "foot of triangular rib in RIGHT view measured proportionally along 60 mm base"}, "hole_diameter": {"value": 12.0, "unit": "mm", "provenance": "inferred", "evidence": "diameter of circular holes in FRONT and TOP views proportioned to 100 mm length"}, "hole_end_offset": {"value": 25.0, "unit": "mm", "provenance": "inferred", "evidence": "hole centres in FRONT/TOP views at approximately quarter and three-quarter length positions"}}

def cut_hole(shape, centre, direction):
    r = P("hole_diameter") / 2.0
    start = (centre[0] - direction[0] * 2.0, centre[1] - direction[1] * 2.0, centre[2] - direction[2] * 2.0)
    cyl = cq.Solid.makeCylinder(r, P("plate_thickness") + 4.0, cq.Vector(start[0], start[1], start[2]), cq.Vector(direction[0], direction[1], direction[2]))
    return shape.cut(cq.Workplane("XY").newObject([cyl]))

L = P("length")
W = P("width")
H = P("height")
t = P("plate_thickness")

base = cq.Workplane("XY").box(L, W, t, centered=(False, True, False))
base = fillet_safe(base, 1.0)
base_hole_y = -W / 2.0 + t + (W - t) / 2.0
base_hole_z = t / 2.0
base = cut_hole(base, (P("hole_end_offset"), base_hole_y, base_hole_z), (0, 0, 1))
base = cut_hole(base, (L - P("hole_end_offset"), base_hole_y, base_hole_z), (0, 0, 1))

vert_h = H - t
vertical = cq.Workplane("XY").box(L, t, vert_h, centered=(False, True, False)).translate((0, -W / 2.0 + t / 2.0, t))
vertical = fillet_safe(vertical, 1.0)
vert_hole_y = -W / 2.0 + t / 2.0
vert_hole_z = t + vert_h / 2.0
vertical = cut_hole(vertical, (P("hole_end_offset"), vert_hole_y, vert_hole_z), (0, 1, 0))
vertical = cut_hole(vertical, (L - P("hole_end_offset"), vert_hole_y, vert_hole_z), (0, 1, 0))

gt = P("gusset_thickness")
gh = P("gusset_height")
gl = P("gusset_length")
y_inner = -W / 2.0 + t
z_base = t
gusset = cq.Workplane("YZ").polyline([(y_inner, z_base), (y_inner + gl, z_base), (y_inner, z_base + gh)]).close().extrude(gt).translate((L / 2.0 - gt / 2.0, 0, 0))
gusset = fillet_safe(gusset, 0.8)

parts = [{"name": "base_plate", "shape": base, "colour": "#8a9199", "material": "metal"}, {"name": "vertical_plate", "shape": vertical, "colour": "#8a9199", "material": "metal"}, {"name": "gusset_rib", "shape": gusset, "colour": "#7f878f", "material": "metal"}]