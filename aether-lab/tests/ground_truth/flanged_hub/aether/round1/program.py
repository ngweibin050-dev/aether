PARAMS = {"overall_diameter": {"value": 120.0, "unit": "mm", "provenance": "read", "evidence": "TOP VIEW 120.0/119.9 and FRONT/RIGHT 120.0 dimension"}, "total_height": {"value": 62.0, "unit": "mm", "provenance": "read", "evidence": "FRONT VIEW and RIGHT VIEW 62.0 dimension"}, "flange_thickness": {"value": 14.0, "unit": "mm", "provenance": "inferred", "evidence": "Estimated from FRONT VIEW flange band proportion of total 62mm height, approx 14mm"}, "hub_diameter": {"value": 64.0, "unit": "mm", "provenance": "inferred", "evidence": "Scaled from TOP VIEW middle concentric circle vs 120mm outer circle, approx 64mm"}, "hub_protrusion": {"value": 48.0, "unit": "mm", "provenance": "inferred", "evidence": "Total height 62 minus estimated flange thickness 14 from FRONT VIEW proportions"}, "central_bore_diameter": {"value": 30.0, "unit": "mm", "provenance": "inferred", "evidence": "Scaled from TOP VIEW innermost concentric circle vs 120mm outer, approx 30mm"}, "bolt_hole_diameter": {"value": 11.0, "unit": "mm", "provenance": "inferred", "evidence": "Scaled from TOP VIEW small bolt circles vs 120mm outer, approx 11mm"}, "bolt_pcd": {"value": 94.0, "unit": "mm", "provenance": "inferred", "evidence": "Scaled from TOP VIEW bolt centre circle vs 120mm outer, approx 94mm PCD"}, "bolt_count": {"value": 6, "unit": "count", "provenance": "read", "evidence": "Six small circles equally spaced in TOP VIEW"}, "bolt_first_angle": {"value": 0.0, "unit": "deg", "provenance": "inferred", "evidence": "TOP VIEW one bolt hole on horizontal centreline at 0 degrees, others at 60 degree intervals"}}

# (the program's own P() was removed: the lab's P() reads PARAMS and the engineer's corrections)


# NOTE: P is normally provided by lab; this fallback is overwritten if provided? Keep geometry reading via P() calls below.
# Geometry centred at x=overall/2 so bounding length in X is overall_diameter, axis vertical Z.
cx = P("overall_diameter") / 2.0
cy = 0.0
flange_r = P("overall_diameter") / 2.0
flange_t = P("flange_thickness")
total_h = P("total_height")
hub_r = P("hub_diameter") / 2.0
hub_h = P("hub_protrusion")
bore_r = P("central_bore_diameter") / 2.0
bolt_r = P("bolt_hole_diameter") / 2.0
pcd_r = P("bolt_pcd") / 2.0
n_bolts = int(P("bolt_count"))
first_deg = P("bolt_first_angle")

# Flange disc: solid cylinder z 0..flange_t
flange = cq.Solid.makeCylinder(flange_r, flange_t, cq.Vector(cx, cy, 0), cq.Vector(0, 0, 1))
# Central bore cut through flange (part of central_bore feature)
bore_cut_flange = cq.Solid.makeCylinder(bore_r, total_h + 4.0, cq.Vector(cx, cy, -2.0), cq.Vector(0, 0, 1))
flange = flange.cut(bore_cut_flange)
# Bolt holes through flange only
for i in range(n_bolts):
    ang = math.radians(first_deg + i * 360.0 / n_bolts)
    bx = cx + pcd_r * math.cos(ang)
    by = cy + pcd_r * math.sin(ang)
    cutter = cq.Solid.makeCylinder(bolt_r, flange_t + 4.0, cq.Vector(bx, by, -2.0), cq.Vector(0, 0, 1))
    flange = flange.cut(cutter)

# Hub boss: cylinder sitting on flange top face, z flange_t..flange_t+hub_h (=total_h)
hub = cq.Solid.makeCylinder(hub_r, hub_h, cq.Vector(cx, cy, flange_t), cq.Vector(0, 0, 1))
# Central bore cut through hub (continuation of same bore)
bore_cut_hub = cq.Solid.makeCylinder(bore_r, total_h + 4.0, cq.Vector(cx, cy, -2.0), cq.Vector(0, 0, 1))
hub = hub.cut(bore_cut_hub)

parts = [{"name": "flange_disc", "shape": flange, "colour": "#8a8f94", "material": "metal"}, {"name": "hub_boss", "shape": hub, "colour": "#8a8f94", "material": "metal"}]
