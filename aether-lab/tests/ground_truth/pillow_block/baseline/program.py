PARAMS = {"length": {"value": 140.0, "unit": "mm", "provenance": "read", "evidence": "140.0 dimension below TOP and FRONT views"}, "width": {"value": 40.0, "unit": "mm", "provenance": "read", "evidence": "40.0 dimension on TOP and RIGHT views"}, "height": {"value": 70.0, "unit": "mm", "provenance": "read", "evidence": "69.9/70.0 height dimension on FRONT/RIGHT views, rounded to 70"}, "base_thickness": {"value": 14.0, "unit": "mm", "provenance": "inferred", "evidence": "bottom flange band proportion in FRONT view"}, "pedestal_width": {"value": 72.0, "unit": "mm", "provenance": "inferred", "evidence": "stepped pedestal width proportion in FRONT view"}, "pedestal_top_height": {"value": 36.0, "unit": "mm", "provenance": "inferred", "evidence": "shoulder/step height proportion in FRONT and RIGHT views"}, "arch_width": {"value": 52.0, "unit": "mm", "provenance": "inferred", "evidence": "semicircular arch width proportion in FRONT view"}, "bore_diameter": {"value": 30.0, "unit": "mm", "provenance": "inferred", "evidence": "central bore circle diameter relative to arch in FRONT view, dashed edges in TOP view"}, "bore_center_height": {"value": 44.0, "unit": "mm", "provenance": "inferred", "evidence": "bore centre height in FRONT view, coincident with arch centre from height minus arch radius"}, "bolt_hole_diameter": {"value": 11.0, "unit": "mm", "provenance": "inferred", "evidence": "circles in TOP view at base ends, dashed lines in FRONT view"}, "bolt_hole_end_offset": {"value": 20.0, "unit": "mm", "provenance": "inferred", "evidence": "bolt hole centre distance from each end in TOP/FRONT views"}, "cap_depth": {"value": 36.0, "unit": "mm", "provenance": "inferred", "evidence": "cap slightly narrower than 40mm base, lines in TOP/RIGHT views"}, "cap_flange_thickness": {"value": 8.0, "unit": "mm", "provenance": "inferred", "evidence": "cap flange band above pedestal shoulder in FRONT view"}, "cap_bolt_diameter": {"value": 6.0, "unit": "mm", "provenance": "assumed", "evidence": "standard M6 cap bolt for a housing of this size, not dimensioned"}, "cap_bolt_head_diameter": {"value": 10.0, "unit": "mm", "provenance": "assumed", "evidence": "standard socket head for M6 bolt, not dimensioned"}, "cap_bolt_engagement": {"value": 10.0, "unit": "mm", "provenance": "assumed", "evidence": "thread engagement into lower housing, not shown"}}

def box_solid(sx, sy, sz, x0, y0, z0):
    return cq.Solid.makeBox(sx, sy, sz, cq.Vector(x0, y0, z0))

def cyl_y(r, length, cx, cy0, cz):
    return cq.Solid.makeCylinder(r, length, cq.Vector(cx, cy0, cz), cq.Vector(0, 1, 0))

def cyl_z(r, length, cx, cy, z0):
    return cq.Solid.makeCylinder(r, length, cq.Vector(cx, cy, z0), cq.Vector(0, 0, 1))

cx = P("length") / 2.0
step_z = P("pedestal_top_height")
arch_r = P("arch_width") / 2.0
arch_cz = P("height") - arch_r
bore_r = P("bore_diameter") / 2.0
bore_cz = P("bore_center_height")
flange_top = step_z + P("cap_flange_thickness")
bolt_x_off = (P("pedestal_width") / 2.0 + arch_r) / 2.0
bolt_lx = cx - bolt_x_off
bolt_rx = cx + bolt_x_off
head_h = P("cap_flange_thickness") * 0.75

base = box_solid(P("length"), P("width"), P("base_thickness"), 0, -P("width") / 2.0, 0)
pedestal = box_solid(P("pedestal_width"), P("width"), step_z - P("base_thickness"), cx - P("pedestal_width") / 2.0, -P("width") / 2.0, P("base_thickness"))
lower = base.fuse(pedestal)
lower = lower.cut(cyl_y(bore_r, P("width") + 10.0, cx, -P("width") / 2.0 - 5.0, bore_cz))
lower = lower.cut(cyl_z(P("bolt_hole_diameter") / 2.0, P("base_thickness") + 10.0, P("bolt_hole_end_offset"), 0, -5.0))
lower = lower.cut(cyl_z(P("bolt_hole_diameter") / 2.0, P("base_thickness") + 10.0, P("length") - P("bolt_hole_end_offset"), 0, -5.0))
lower = lower.cut(cyl_z(P("cap_bolt_diameter") / 2.0 + 0.5, P("cap_bolt_engagement") + 5.0, bolt_lx, 0, step_z - P("cap_bolt_engagement")))
lower = lower.cut(cyl_z(P("cap_bolt_diameter") / 2.0 + 0.5, P("cap_bolt_engagement") + 5.0, bolt_rx, 0, step_z - P("cap_bolt_engagement")))
lower = fillet_safe(lower, 1.2)

cap_flange = box_solid(P("pedestal_width"), P("cap_depth"), P("cap_flange_thickness"), cx - P("pedestal_width") / 2.0, -P("cap_depth") / 2.0, step_z)
arch_rect = box_solid(P("arch_width"), P("cap_depth"), arch_cz - flange_top, cx - arch_r, -P("cap_depth") / 2.0, flange_top)
arch_cyl = cyl_y(arch_r, P("cap_depth"), cx, -P("cap_depth") / 2.0, arch_cz)
cap = cap_flange.fuse(arch_rect).fuse(arch_cyl)
cap = cap.cut(box_solid(P("length"), P("width") + 10.0, step_z, 0, -P("width") / 2.0 - 5.0, 0))
cap = cap.cut(cyl_y(bore_r, P("width") + 10.0, cx, -P("width") / 2.0 - 5.0, bore_cz))
cap = cap.cut(cyl_z(P("cap_bolt_diameter") / 2.0 + 0.5, P("cap_flange_thickness") + 5.0, bolt_lx, 0, step_z - 2.5))
cap = cap.cut(cyl_z(P("cap_bolt_diameter") / 2.0 + 0.5, P("cap_flange_thickness") + 5.0, bolt_rx, 0, step_z - 2.5))
cap = cap.cut(cyl_z(P("cap_bolt_head_diameter") / 2.0 + 0.5, head_h + 2.0, bolt_lx, 0, flange_top - head_h))
cap = cap.cut(cyl_z(P("cap_bolt_head_diameter") / 2.0 + 0.5, head_h + 2.0, bolt_rx, 0, flange_top - head_h))
cap = fillet_safe(cap, 1.2)

def cap_bolt(bx):
    shaft = cyl_z(P("cap_bolt_diameter") / 2.0, P("cap_bolt_engagement") + P("cap_flange_thickness") - head_h, bx, 0, step_z - P("cap_bolt_engagement"))
    head = cyl_z(P("cap_bolt_head_diameter") / 2.0, head_h, bx, 0, flange_top - head_h)
    return shaft.fuse(head)

parts = [{"name": "lower_housing", "shape": lower, "colour": "#5f707e", "material": "paint"}, {"name": "top_cap", "shape": cap, "colour": "#5f707e", "material": "paint"}, {"name": "cap_bolt_left", "shape": cap_bolt(bolt_lx), "colour": "#9aa0a3", "material": "metal"}, {"name": "cap_bolt_right", "shape": cap_bolt(bolt_rx), "colour": "#9aa0a3", "material": "metal"}]