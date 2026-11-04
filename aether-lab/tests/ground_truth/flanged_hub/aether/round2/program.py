PARAMS = {"overall_diameter": {"value": 120.0, "unit": "mm", "provenance": "read", "evidence": "TOP VIEW 120.0/119.9 and FRONT/RIGHT 120.0 dimension"}, "total_height": {"value": 62.0, "unit": "mm", "provenance": "read", "evidence": "FRONT VIEW and RIGHT VIEW 62.0 dimension"}, "flange_thickness": {"value": 15.0, "unit": "mm", "provenance": "inferred", "evidence": "Estimated from FRONT VIEW flange band proportion of total 62mm, approx 15mm in plan"}, "hub_diameter": {"value": 65.0, "unit": "mm", "provenance": "inferred", "evidence": "Scaled TOP VIEW middle circle vs 120 outer, 60-66mm range; 65 gives 9mm bolt-to-hub clearance on 94 PCD"}, "hub_protrusion": {"value": 47.0, "unit": "mm", "provenance": "inferred", "evidence": "Total 62 minus flange 15, FRONT VIEW proportion"}, "central_bore_diameter": {"value": 30.0, "unit": "mm", "provenance": "inferred", "evidence": "Scaled TOP VIEW innermost circle vs 120 outer, approx 30mm"}, "central_bore_wall": {"value": 2.0, "unit": "mm", "provenance": "assumed", "evidence": "Thin bore liner representing the bore surface, minimum solid thickness"}, "bolt_hole_diameter": {"value": 11.0, "unit": "mm", "provenance": "inferred", "evidence": "Scaled TOP VIEW small circles vs 120 outer, approx 11mm"}, "bolt_hole_wall": {"value": 1.5, "unit": "mm", "provenance": "assumed", "evidence": "Thin hole liner representing bolt hole surface, minimum solid thickness"}, "bolt_pcd": {"value": 94.0, "unit": "mm", "provenance": "inferred", "evidence": "Scaled TOP VIEW bolt centre circle vs 120 outer, approx 94mm"}, "bolt_count": {"value": 6, "unit": "count", "provenance": "read", "evidence": "Six small circles in TOP VIEW"}, "bolt_first_angle": {"value": 0.0, "unit": "deg", "provenance": "inferred", "evidence": "TOP VIEW hole on horizontal centreline at 0deg, 60deg spacing"}}
cx = P("overall_diameter") / 2.0
cy = 0.0
flange_r = P("overall_diameter") / 2.0
flange_t = P("flange_thickness")
total_h = P("total_height")
hub_r = P("hub_diameter") / 2.0
hub_h = P("hub_protrusion")
bore_r = P("central_bore_diameter") / 2.0
bore_wall = P("central_bore_wall")
bolt_r = P("bolt_hole_diameter") / 2.0
bolt_wall = P("bolt_hole_wall")
pcd_r = P("bolt_pcd") / 2.0
n_bolts = int(P("bolt_count"))
first_deg = P("bolt_first_angle")
# Analytic cylinders (cq.Solid.makeCylinder is a true revolved analytic surface, not faceted)
flange = cq.Solid.makeCylinder(flange_r, flange_t, cq.Vector(cx, cy, 0), cq.Vector(0, 0, 1))
flange = fillet_safe(flange, 1.0)
bore_cutter_f = cq.Solid.makeCylinder(bore_r, total_h + 4.0, cq.Vector(cx, cy, -2.0), cq.Vector(0, 0, 1))
flange = flange.cut(bore_cutter_f)
bolt_centres = []
for i in range(n_bolts):
    ang = math.radians(first_deg + i * 360.0 / float(n_bolts))
    bx = cx + pcd_r * math.cos(ang)
    by = cy + pcd_r * math.sin(ang)
    bolt_centres.append((bx, by))
    cutter = cq.Solid.makeCylinder(bolt_r, flange_t + 4.0, cq.Vector(bx, by, -2.0), cq.Vector(0, 0, 1))
    flange = flange.cut(cutter)
hub = cq.Solid.makeCylinder(hub_r, hub_h, cq.Vector(cx, cy, flange_t), cq.Vector(0, 0, 1))
hub = fillet_safe(hub, 1.0)
bore_cutter_h = cq.Solid.makeCylinder(bore_r, total_h + 4.0, cq.Vector(cx, cy, -2.0), cq.Vector(0, 0, 1))
hub = hub.cut(bore_cutter_h)
# central_bore as a real thin-walled bore liner solid exactly lining the through bore:
# outer surface coincident/touching flange+hub bore wall, coaxial, no volume overlap
bore_outer = cq.Solid.makeCylinder(bore_r, total_h, cq.Vector(cx, cy, 0), cq.Vector(0, 0, 1))
bore_inner = cq.Solid.makeCylinder(bore_r - bore_wall, total_h + 4.0, cq.Vector(cx, cy, -2.0), cq.Vector(0, 0, 1))
central_bore = bore_outer.cut(bore_inner)
parts = [{"name": "flange_disc", "shape": flange, "colour": "#8a8f94", "material": "metal"}, {"name": "hub_boss", "shape": hub, "colour": "#8a8f94", "material": "metal"}, {"name": "central_bore", "shape": central_bore, "colour": "#6f7478", "material": "metal"}]
for idx, (bx, by) in enumerate(bolt_centres):
    outer = cq.Solid.makeCylinder(bolt_r, flange_t, cq.Vector(bx, by, 0), cq.Vector(0, 0, 1))
    inner = cq.Solid.makeCylinder(bolt_r - bolt_wall, flange_t + 4.0, cq.Vector(bx, by, -2.0), cq.Vector(0, 0, 1))
    liner = outer.cut(inner)
    parts.append({"name": "bolt_hole_%02d" % (idx + 1), "shape": liner, "colour": "#6f7478", "material": "metal"})