PARAMS = {
    "length": {"value": 120.0, "unit": "mm", "provenance": "read", "evidence": "Front and right views dimension 120.0 across flange; top view 119.9/120.0"},
    "width": {"value": 120.0, "unit": "mm", "provenance": "read", "evidence": "Top view dimension 120.0 across circular flange"},
    "height": {"value": 62.0, "unit": "mm", "provenance": "read", "evidence": "Front and right views dimension 62.0 total height"},
    "flange_thickness": {"value": 15.0, "unit": "mm", "provenance": "inferred", "evidence": "Flange band height proportioned from front/right views against 62.0 total height"},
    "boss_diameter": {"value": 66.0, "unit": "mm", "provenance": "inferred", "evidence": "Boss circle in top view and boss width in front view proportioned against 120.0 flange diameter"},
    "bore_diameter": {"value": 28.0, "unit": "mm", "provenance": "inferred", "evidence": "Central circle in top view proportioned against 120.0 flange diameter"},
    "bolt_hole_diameter": {"value": 11.0, "unit": "mm", "provenance": "inferred", "evidence": "Six small circles in top view proportioned against 120.0 flange diameter"},
    "bolt_circle_diameter": {"value": 95.0, "unit": "mm", "provenance": "inferred", "evidence": "Centres of six holes in top view proportioned against 120.0 flange diameter"},
    "bolt_count": {"value": 6, "unit": "count", "provenance": "read", "evidence": "Six bolt holes visible equally spaced in top view"},
    "edge_fillet": {"value": 1.5, "unit": "mm", "provenance": "assumed", "evidence": "Small machined edge break; no radius dimensioned on drawing"}
}
parts = []
cx = P("length") / 2.0
flangeRadius = P("width") / 2.0
bossRadius = P("boss_diameter") / 2.0
boreRadius = P("bore_diameter") / 2.0
holeRadius = P("bolt_hole_diameter") / 2.0
pcdRadius = P("bolt_circle_diameter") / 2.0
totalHeight = P("height")
flangeThickness = P("flange_thickness")
flange = cq.Solid.makeCylinder(flangeRadius, flangeThickness, cq.Vector(cx, 0, 0), cq.Vector(0, 0, 1))
boss = cq.Solid.makeCylinder(bossRadius, totalHeight, cq.Vector(cx, 0, 0), cq.Vector(0, 0, 1))
body = flange.fuse(boss)
body = fillet_safe(body, P("edge_fillet"))
cutHeight = totalHeight * 1.4
cutBase = -totalHeight * 0.2
boreCutter = cq.Solid.makeCylinder(boreRadius, cutHeight, cq.Vector(cx, 0, cutBase), cq.Vector(0, 0, 1))
body = body.cut(boreCutter)
count = int(P("bolt_count"))
for i in range(count):
    ang = 2.0 * math.pi * i / count
    hx = cx + pcdRadius * math.cos(ang)
    hy = pcdRadius * math.sin(ang)
    holeCutter = cq.Solid.makeCylinder(holeRadius, cutHeight, cq.Vector(hx, hy, cutBase), cq.Vector(0, 0, 1))
    body = body.cut(holeCutter)
parts.append({"name": "flanged_hub", "shape": body, "colour": "#8a8f94", "material": "metal"})