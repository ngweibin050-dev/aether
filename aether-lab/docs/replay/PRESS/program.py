PARAMS = {"length": {"value": 1100, "unit": "mm", "provenance": "assumed", "evidence": "no scale on drawing, 1100mm estimate in plan"}, "width": {"value": 340, "unit": "mm", "provenance": "assumed", "evidence": "depth not shown in single sectional view"}, "height": {"value": 760, "unit": "mm", "provenance": "inferred", "evidence": "side outline proportions relative to length"}, "base_height": {"value": 200, "unit": "mm", "provenance": "inferred", "evidence": "hatched base block in side view"}, "main_axis_z": {"value": 380, "unit": "mm", "provenance": "inferred", "evidence": "piston axis centre of cylinder in side view"}, "cylinder_bore": {"value": 152, "unit": "mm", "provenance": "inferred", "evidence": "bore 28 proportions"}, "panel_gap": {"value": 3.5, "unit": "mm", "provenance": "assumed", "evidence": "shut line requirement"}, "blade_thickness": {"value": 10, "unit": "mm", "provenance": "assumed", "evidence": "thin vertical blade 65"}, "crank_radius": {"value": 55, "unit": "mm", "provenance": "inferred", "evidence": "crank circle 55/51 proportions"}}

def P(name):
    return PARAMS[name]["value"]

def B(x1, x2, y1, y2, z1, z2):
    return cq.Solid.makeBox(x2 - x1, y2 - y1, z2 - z1, cq.Vector(x1, y1, z1))

def CX(r, x1, x2, y, z):
    return cq.Solid.makeCylinder(r, x2 - x1, cq.Vector(x1, y, z), cq.Vector(1, 0, 0))

def CY(r, y1, y2, x, z):
    return cq.Solid.makeCylinder(r, y2 - y1, cq.Vector(x, y1, z), cq.Vector(0, 1, 0))

def CZ(r, z1, z2, x, y):
    return cq.Solid.makeCylinder(r, z2 - z1, cq.Vector(x, y, z1), cq.Vector(0, 0, 1))

def tubeX(rOut, rIn, x1, x2, y, z):
    return CX(rOut, x1, x2, y, z).cut(CX(rIn, x1 - 2, x2 + 2, y, z))

def tubeY(rOut, rIn, y1, y2, x, z):
    return CY(rOut, y1, y2, x, z).cut(CY(rIn, y1 - 2, y2 + 2, x, z))

def fuse(*shapes):
    r = shapes[0]
    for s in shapes[1:]:
        r = r.fuse(s)
    return r

def F(s, r=2.5):
    try:
        return fillet_safe(s, r)
    except Exception:
        return s

parts = []

def add(name, shape, colour, material):
    parts.append({"name": name, "shape": shape, "colour": colour, "material": material})

zc = P("main_axis_z")
dg = "#3a3d42"
mg = "#6a6e75"
sv = "#c0c4c8"
bk = "#1a1a1a"
br = "#b08d4a"

# base
base = B(120, 1080, -170, 170, 40, 200).cut(B(150, 1050, -120, 120, 188, 202))
add("base_bed", F(base, 3), dg, "paint")
add("base_foot_left", F(B(180, 380, -185, 185, 0, 42).cut(CZ(12, -2, 44, 280, 0)), 2), dg, "paint")
add("base_foot_right", F(B(750, 950, -185, 185, 0, 42).cut(CZ(12, -2, 44, 850, 0)), 2), dg, "paint")

# headstock with die recess (bore leaves a floor at x=330 for die contact)
head = B(180, 360, -140, 140, 200, 560)
head = head.cut(CX(13, 176, 364, 0, zc))
head = head.cut(B(290, 362, 70, 142, 200, 275))
head = head.cut(B(300, 362, -142, -70, 200, 275))
head = head.cut(CX(78, 330, 364, 0, zc))
add("headstock_block", F(head, 3), dg, "paint")
cap = B(190, 350, -130, 130, 563, 665).cut(CX(13, 186, 354, 0, 640))
add("headstock_top_cap", F(cap, 3), dg, "paint")

# cylinder block: bore, blade slot, and separate pockets for blade guides (no embedding)
cyl = B(364, 620, -145, 145, 200, 560)
cyl = cyl.cut(CX(96, 360, 624, 0, zc))
cyl = cyl.cut(B(438, 462, -50, 50, 500, 564))
cyl = cyl.cut(B(364, 624, 100, 148, 260, 500))
cyl = cyl.cut(B(364, 624, -148, -100, 260, 500))
cyl = cyl.cut(B(417, 445.5, -46, 46, 458, 587))
cyl = cyl.cut(B(454.5, 483, -46, 46, 458, 587))
add("cylinder_block", F(cyl, 3), dg, "paint")

# open crank housing frame
housing = fuse(B(624, 1080, -150, 150, 200, 240), B(624, 1080, -150, -110, 240, 580), B(624, 1080, 110, 150, 540, 580), B(624, 1080, 110, 150, 200, 260), B(624, 660, 110, 150, 260, 540), B(1040, 1080, 110, 150, 260, 540), B(1040, 1080, -110, 110, 240, 580), B(840, 1080, -110, 110, 540, 580), B(624, 700, -110, 110, 540, 580))
housing = housing.cut(CY(56, -160, -100, 970, zc))
housing = housing.cut(CX(60, 620, 700, 0, zc))
add("crank_housing", F(housing, 3), dg, "paint")
cover = B(660, 1040, 110, 122, 260, 540)
cover = cover.cut(CY(37, 104, 128, 970, zc))
cover = cover.cut(CY(10, 104, 128, 690, 510))
cover = cover.cut(CY(10, 104, 128, 690, 290))
add("crank_housing_side_cover", F(cover, 2), mg, "paint")
acc = B(760, 920, 122, 130, 300, 460).cut(CY(8, 116, 136, 840, zc))
add("crank_housing_access_panel", F(acc, 2), mg, "paint")

# cylinder internals: liner shortened to end at x=618, inside cylinder bore only
add("cylinder_liner", tubeX(95, 76, 560, 618, 0, zc), sv, "metal")
add("work_chamber_sleeve", tubeX(86, 76, 405, 558, 0, zc), sv, "metal")
# piston with a real annular groove cut into it (core remains, so one solid)
groove_cutter = CX(80, 573, 587, 0, zc).cut(CX(74, 572, 588, 0, zc))
piston_solid = CX(76, 560, 596, 0, zc).cut(groove_cutter)
add("piston", piston_solid, sv, "metal")
add("piston_face_plate", CX(50, 552, 560, 0, zc), dg, "plastic")
# seal ring sits IN the groove, OD proud by 0.5mm, no coincident volume
add("piston_seal_ring", tubeX(76.5, 74, 575, 585, 0, zc), bk, "rubber")
add("piston_rod", CX(18, 596, 748, 0, zc), sv, "metal")

# crosshead and rod: eye / bush / pin all with 1mm radial clearances, no coincident solids
ch = B(730, 812, -55, 55, 314, 446).cut(CY(23, -60, 60, 770, zc)).cut(CX(19, 726, 816, 0, zc))
add("crosshead_block", F(ch, 3), sv, "metal")
add("crosshead_pin", CY(22, -72, 88, 770, zc), sv, "metal")
add("crosshead_pin_bush", tubeY(28, 22, 56, 84, 770, zc), br, "metal")
rod_eye = tubeY(34, 29, 56, 84, 770, zc)
rod = fuse(rod_eye, CX(17, 770, 912, 70, zc), B(790, 920, 58, 82, 368, 392))
add("connecting_rod", F(rod, 2), sv, "metal")
# big end bore 48, bearing shell 37-47, crank journal 36: all clear, none coincident
add("connecting_rod_big_end", tubeY(68, 48, 35, 105, 970, zc), sv, "metal")
add("big_end_bearing_shell", tubeY(47, 37, 37, 103, 970, zc), br, "metal")
add("crankshaft", CY(36, -100, 190, 970, zc), sv, "metal")
add("crankshaft_end_nut", tubeY(30, 15, 190, 212, 970, zc), sv, "metal")
add("main_bearing_left", tubeY(55, 37, -150, -110, 970, zc), dg, "metal")
add("main_bearing_right", tubeY(55, 37, 110, 150, 970, zc), dg, "metal")
# bearing cap inboard of rear bearing, touching its face at y=-110 only, split line visible
capb = B(925, 1015, -110, -72, 380, 442).cut(CY(37, -116, -66, 970, zc))
add("main_bearing_cap", F(capb, 2), mg, "paint")
# flywheel EXTERNAL on front of crankshaft, 8mm clear of housing front face (y=150)
fly = fuse(tubeY(95, 37, 158, 178, 970, zc), tubeY(45, 37, 150, 186, 970, zc))
for dx, dz in [(52, 0), (-52, 0), (0, 52), (0, -52)]:
    fly = fly.cut(CY(17, 154, 182, 970 + dx, zc + dz))
add("crank_gear_flywheel", F(fly, 2), sv, "metal")
add("crosshead_guide_top", F(B(620, 832, -60, 60, 447, 461).cut(CX(6, 616, 836, 0, 454)), 2), sv, "metal")
add("crosshead_guide_bottom", F(B(620, 832, -60, 60, 300, 314).cut(CX(6, 616, 836, 0, 307)), 2), sv, "metal")

# motor: casing bored r15 so shaft (r14) runs with clearance and protrudes both ends
motor = fuse(CX(55, 850, 1020, 0, 640), B(870, 910, -35, 35, 580, 600), B(960, 1000, -35, 35, 580, 600), CX(40, 1020, 1035, 0, 640))
motor = motor.cut(CX(15, 815, 1075, 0, 640))
add("drive_motor_casing", F(motor, 3), dg, "paint")
endcap = CX(48, 1035, 1052, 0, 640).cut(CX(15, 1030, 1057, 0, 640))
add("drive_motor_end_cap", endcap, dg, "paint")
add("drive_motor_shaft_nut", tubeX(20, 15, 1068, 1088, 0, 640), sv, "metal")
add("drive_motor_shaft", CX(14, 820, 1068, 0, 640), sv, "metal")
add("top_tie_rod", CX(10, 342, 855, 0, 640), sv, "metal")
add("top_tie_rod_nut_left", tubeX(18, 11, 318, 342, 0, 640), sv, "metal")
add("top_tie_rod_nut_right", tubeX(18, 11, 855, 879, 0, 640), sv, "metal")

# blade: lofted plate tapering to a thin cutting edge (not a box)
try:
    blade = smooth_loft([(455, [(449, -40), (451, -40), (451, 40), (449, 40)]), (485, [(445, -40), (455, -40), (455, 40), (445, 40)]), (685, [(445, -40), (455, -40), (455, 40), (445, 40)])], axis="z")
except Exception:
    blade = B(445, 455, -40, 40, 470, 685).fuse(B(449, 451, -40, 40, 455, 472))
add("cutting_blade", blade, sv, "metal")
add("blade_holder", F(B(428, 472, -50, 50, 685, 758).cut(CZ(8, 680, 762, 450, 0)), 2), dg, "metal")
# guides sit in their pockets, bottom face contact at z=458, 0.5mm side clearance to blade
add("blade_guide_plate_left", F(B(418, 444.5, -45, 45, 458, 585), 1.5), sv, "metal")
add("blade_guide_plate_right", F(B(455.5, 482, -45, 45, 458, 585), 1.5), sv, "metal")

# die fills headstock recess and contacts its floor at x=330
die = tubeX(75, 28, 330, 410, 0, zc)
add("die_block", die, dg, "metal")
add("pressure_disc", CX(45, 410, 420, 0, zc), sv, "metal")
add("ejector_rod", CX(8, 175, 410, 0, zc), sv, "metal")
# spring: ribbed revolved profile (bellows/coil read), inner r9 clear of rod r8
spts = [(9, 0), (18, 0), (18, 5)]
for i in range(1, 10):
    spts.append((12, i * 10))
    spts.append((18, i * 10 + 5))
spts.append((18, 100))
spts.append((9, 100))
try:
    spring = revolve_profile(spts, (232, 0, zc), (1, 0, 0))
except Exception:
    spring = tubeX(18, 9, 232, 332, 0, zc)
add("ejector_spring", spring, sv, "metal")
add("spring_collar_left", CX(24, 214, 232, 0, zc), dg, "metal")
add("spring_collar_right", CX(24, 332, 350, 0, zc), dg, "metal")
add("feed_rod", CX(14, 20, 202, 0, zc), sv, "metal")
clamp = B(70, 132, -35, 35, 340, 420).cut(CX(15, 66, 136, 0, zc))
add("feed_rod_clamp_block", F(clamp, 2), dg, "metal")
add("feed_clamp_bolt", CZ(8, 302, 340, 100, 0), sv, "metal")
# feed lever: tapered plate plus a real eye boss at the pivot, readable silhouette
lever = fuse(B(88, 104, -7, 7, 418, 532), CY(19, -7, 7, 96, 532))
lever = lever.cut(CY(11, -12, 12, 96, 532))
add("feed_lever", F(lever, 2), sv, "metal")
add("feed_lever_pivot_pin", CY(10, -22, 22, 96, 532), sv, "metal")
add("feed_link", F(B(100, 172, 12, 20, 438, 452).cut(CY(5, 8, 24, 108, 445)), 1.5), sv, "metal")
add("feed_link_horizontal", F(B(132, 212, 22, 30, 438, 452).cut(CY(5, 18, 34, 204, 445)), 1.5), sv, "metal")
add("link_pivot_lower", CY(8, 4, 32, 168, 445), sv, "metal")

# lubricator
add("lubricator_block", F(B(598, 650, -20, 20, 560, 592).cut(CZ(6, 556, 596, 624, 0)), 2), dg, "metal")
add("lubricator_cap_screw", CZ(11, 592, 614, 624, 0), sv, "metal")
add("lubricator_drip_valve", CZ(6, 578, 594, 638, 0), br, "metal")
add("lubricator_drop_pin", CZ(4, 500, 562, 640, 0), sv, "metal")
# discharge chute: thin-walled U channel on the FRONT face of headstock (y=140), fully external
chute = fuse(B(300, 360, 140, 178, 202, 210), B(300, 308, 140, 178, 210, 268), B(352, 360, 140, 178, 210, 268))
add("discharge_chute", chute, dg, "metal")
# fasteners placed on outer faces, touching not buried
add("die_retaining_bolt_top", CY(12, 140, 164, 330, 432), sv, "metal")
add("die_retaining_bolt_bottom", CY(12, 140, 164, 330, 328), sv, "metal")
add("crank_cover_bolt_top", CY(10, 122, 142, 690, 510), sv, "metal")
add("crank_cover_bolt_bottom", CY(10, 122, 142, 690, 290), sv, "metal")
add("big_end_cap_bolt", CZ(8, 448, 474, 970, 70), sv, "metal")
add("crank_housing_oil_knob", CZ(14, 580, 602, 1020, 0), bk, "plastic")
add("cylinder_top_cover_plate", F(B(535, 618, -50, 50, 560, 570).cut(CZ(6, 556, 574, 578, 0)), 1.5), sv, "metal")
add("cylinder_cover_screw", CZ(6, 570, 584, 578, 0), sv, "metal")