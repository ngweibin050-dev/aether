plan = '''
Object: Shelby/AC Cobra open two-seat roadster.
Orientation: drawing side/plan views have FRONT on RIGHT, rear on LEFT, so measured u=1-x/LENGTH
with program frame x=0 at FRONT, x=LENGTH at rear, y=0 symmetry, z=0 ground.
Body: smooth ruled=False loft through 25 interpolated measured stations. Periodic spline
super-ellipse sections follow half_width(u) (scaled 0.98 to remove the magenta fringe in the
plan overlay) and the cleaned side_top/side_bottom(u): windscreen spike at u~0.50 and roll-bar
spikes at u~0.25-0.30 replaced by the smooth deck/cowl line and lightly smoothed (no flat cap,
no exaggerated waves), wheel ground-touch values in side_bottom floored to the sill line.
Extreme end stations are given a minimum 70mm lens thickness (centred on the measured end
mid-height) so the spline cannot overshoot into the upturned fins seen at nose/tail in the
last renders. Wheel-arch cuts at front x=0.205L, rear x=0.775L.
Wheels (x4): R415 ring tyres (hollow centre, rounded shoulders, touching ground z=0, enlarged
to fill the red wheel circles in the side overlay); inside each a dark brake disc, an open
chrome rim RING (not a solid disc), hub and 5 chrome spokes on the outboard face, matching
the concentric/spoked wheels in the views.
Windscreen: at cowl x~0.465L, base embedded in body top. Trapezoidal chrome FRAME only
(outer minus inner opening, thin border) raked 30deg rearward, pane height 490 and base
width 1020/top 910 so the top reaches the measured windscreen spike (~0.30L) and matches
the wider, taller, red windscreen outline in the end views; separate thin GLASS pane
(glass material) fitted inside the frame opening, same rake, attached at base.
Other parts from drawing: hollow cockpit cut with floor, dashboard, 2 low leather seats,
steering wheel+column, gear lever, arched driver roll hoop (legs + half-torus top) with a
diagonal brace running across and DOWN TO THE REAR cockpit floor (as in side/plan views,
not forward to the dash) plus a short rear stay, bonnet scoop with dark front intake, rear
fuel cap, smaller oval front grille set into the nose, headlight buckets+lamps raised and
pushed forward so they sit proud on the nose instead of buried in it, front indicators,
tail lights, side vents and door handles on the curved body surface, mirror pulled inboard
onto a stalk attached at the cowl (no floating mirror), thin front chrome bumper hugging
the nose, two rear overriders (as drawn), side exhausts tucked up against the sills.
Main sizes/positions from measured outlines; small fitting sizes are engineering estimates.
'''
length_mm = 3960.0
LENGTH = 3960.0
WIDTH = 0.4240 * LENGTH
HEIGHT = 0.3058 * LENGTH
top_f = [0.1544,0.1957,0.2121,0.2204,0.2384,0.2894,0.2616,0.2301,0.1987,0.2099,0.3006,0.2451,0.2429,0.2414,0.2414,0.2264,0.2264,0.2234,0.2166,0.2039,0.1792]
bot_f = [0.1507,0.0735,0.0645,0.0555,0.0067,0.0007,0.0255,0.0412,0.0390,0.0427,0.0427,0.0427,0.0427,0.0427,0.0480,0.0240,0.0007,0.0067,0.0592,0.0652,0.1702]
hw_f = [0.1198,0.1859,0.1943,0.2029,0.2098,0.2120,0.2067,0.1977,0.1977,0.1980,0.1984,0.1984,0.1988,0.1992,0.2007,0.2063,0.2094,0.2082,0.2022,0.1890,0.1689]
body_top_f = list(top_f)
body_top_f[5] = 0.226
body_top_f[6] = 0.224
body_top_f[10] = 0.214
sm_top = list(body_top_f)
for i in range(2, 19):
    sm_top[i] = 0.25 * body_top_f[i - 1] + 0.5 * body_top_f[i] + 0.25 * body_top_f[i + 1]
def interp(u, vals):
    s = min(max(u, 0.0), 1.0) * 20.0
    i = int(math.floor(s))
    if i >= 20:
        return vals[20]
    f = s - i
    return vals[i] * (1.0 - f) + vals[i + 1] * f
def cyl(r, h, base, direc):
    n = math.sqrt(direc[0]*direc[0] + direc[1]*direc[1] + direc[2]*direc[2])
    d = cq.Vector(direc[0]/n, direc[1]/n, direc[2]/n)
    return cq.Workplane('XY').newObject([cq.Solid.makeCylinder(r, h, cq.Vector(base[0], base[1], base[2]), d)])
def cylbtw(r, p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dz = p2[2] - p1[2]
    h = math.sqrt(dx*dx + dy*dy + dz*dz)
    return cyl(r, h, p1, (dx, dy, dz))
def box(sx, sy, sz, tx, ty, tz):
    return cq.Workplane('XY').box(sx, sy, sz).translate((tx, ty, tz))
def rbox(sx, sy, sz, tx, ty, tz, r):
    s = cq.Workplane('XY').box(sx, sy, sz)
    try:
        s = s.edges().fillet(r)
    except Exception:
        pass
    return s.translate((tx, ty, tz))
def sgnpow(v, p):
    return v ** p if v >= 0 else -((-v) ** p)
wires = []
for iu in range(25):
    u = iu / 24.0
    x = (1.0 - u) * LENGTH
    hw = interp(u, hw_f) * LENGTH * 0.98
    zt = interp(u, sm_top) * LENGTH
    zb = interp(u, bot_f) * LENGTH
    if 0.03 < u < 0.97:
        zb = max(zb, 0.042 * LENGTH)
    if zt - zb < 70.0:
        zc0 = 0.5 * (zt + zb)
        zt = zc0 + 35.0
        zb = zc0 - 35.0
    zc = 0.5 * (zt + zb)
    rz = max(0.5 * (zt - zb), 18.0)
    pts = []
    for k in range(32):
        a = 2.0 * math.pi * k / 32.0
        y = hw * sgnpow(math.cos(a), 0.60)
        z = zc + rz * sgnpow(math.sin(a), 0.60)
        if z < zc:
            frac = y / hw if hw > 1.0 else 0.0
            z += 0.22 * rz * max(0.0, 1.0 - frac * frac)
        pts.append(cq.Vector(x, y, z))
    try:
        edge = cq.Edge.makeSpline(pts, periodic=True)
        wires.append(cq.Wire.assembleEdges([edge]))
    except Exception:
        wires.append(cq.Wire.makePolygon(pts + [pts[0]]))
body = cq.Workplane('XY').newObject([cq.Solid.makeLoft(wires, False)])
wheel_r = 415.0
xf = 0.205 * LENGTH
xr = 0.775 * LENGTH
for wx in (xf, xr):
    body = body.cut(cyl(442.0, WIDTH + 300.0, (wx, -WIDTH/2 - 150.0, wheel_r), (0, 1, 0)))
cockpit_cut = cq.Workplane('XY').ellipse(540.0, 475.0).extrude(760.0).translate((0.565 * LENGTH, 0, 600.0))
body = body.cut(cockpit_cut)
parts = []
parts.append({"name": "body", "shape": body, "colour": "#17408b", "material": "paint"})
for tag, wx in (("front", xf), ("rear", xr)):
    for side, sy in (("left", -1), ("right", 1)):
        cy = sy * 690.0
        outy = cy + sy * 96.0
        tyre = cyl(wheel_r, 235.0, (wx, cy - 117.5, wheel_r), (0, 1, 0))
        tyre = tyre.cut(cyl(218.0, 249.0, (wx, cy - 124.5, wheel_r), (0, 1, 0)))
        try:
            tyre = tyre.edges().fillet(24.0)
        except Exception:
            pass
        brake = cyl(182.0, 22.0, (wx, cy + sy * 52.0 - 11.0, wheel_r), (0, 1, 0))
        ring = cyl(212.0, 30.0, (wx, outy - 15.0, wheel_r), (0, 1, 0))
        ring = ring.cut(cyl(176.0, 38.0, (wx, outy - 19.0, wheel_r), (0, 1, 0)))
        hub = cyl(56.0, 46.0, (wx, outy - 23.0, wheel_r), (0, 1, 0))
        rim = ring.union(hub)
        for k in range(5):
            spoke = box(152.0, 26.0, 40.0, wx + 100.0, outy, wheel_r)
            spoke = spoke.rotate((wx, 0, wheel_r), (wx, 1, wheel_r), k * 72.0)
            rim = rim.union(spoke)
        parts.append({"name": tag + "_" + side + "_tyre", "shape": tyre, "colour": "#141414", "material": "rubber"})
        parts.append({"name": tag + "_" + side + "_rim", "shape": rim, "colour": "#d8d8d8", "material": "chrome"})
        parts.append({"name": tag + "_" + side + "_brake", "shape": brake, "colour": "#2e2e2e", "material": "metal"})
floor = rbox(820.0, 880.0, 46.0, 0.575 * LENGTH, 0, 612.0, 16.0)
parts.append({"name": "cockpit_floor", "shape": floor, "colour": "#1e1e1e", "material": "plastic"})
dash = rbox(90.0, 940.0, 105.0, 0.462 * LENGTH, 0, 742.0, 18.0)
parts.append({"name": "dashboard", "shape": dash, "colour": "#222222", "material": "plastic"})
for side, sy in (("left", -230.0), ("right", 230.0)):
    base = rbox(420.0, 360.0, 88.0, 0.605 * LENGTH, sy, 600.0, 26.0)
    back = cq.Workplane('XY').box(105.0, 360.0, 320.0)
    try:
        back = back.edges().fillet(22.0)
    except Exception:
        pass
    back = back.rotate((0, 0, 0), (0, 1, 0), 16.0).translate((0.672 * LENGTH, sy, 735.0))
    parts.append({"name": "seat_" + side, "shape": base.union(back), "colour": "#5a2d18", "material": "leather"})
swdir = cq.Vector(-0.55, 0, 0.835).normalized()
steer = cq.Workplane('XY').newObject([cq.Solid.makeTorus(122.0, 14.0, cq.Vector(0.478 * LENGTH, -230.0, 862.0), swdir)])
column = cylbtw(16.0, (0.472 * LENGTH, -230.0, 838.0), (0.505 * LENGTH, -230.0, 748.0))
lever = cylbtw(10.0, (0.548 * LENGTH, -55.0, 632.0), (0.560 * LENGTH, -48.0, 752.0))
knob = cq.Workplane('XY').newObject([cq.Solid.makeSphere(24.0, cq.Vector(0.560 * LENGTH, -48.0, 758.0))])
parts.append({"name": "steering_wheel", "shape": steer.union(column), "colour": "#2a2a2a", "material": "plastic"})
parts.append({"name": "gear_lever", "shape": lever.union(knob), "colour": "#bbbbbb", "material": "chrome"})
ws_base_x = 0.465 * LENGTH
ws_base_z = 735.0
ws_rake = 30.0
outer = cq.Workplane('YZ').polyline([(-510.0, 0.0), (510.0, 0.0), (455.0, 490.0), (-455.0, 490.0)]).close().extrude(36.0).translate((-18.0, 0, 0))
inner = cq.Workplane('YZ').polyline([(-482.0, 28.0), (482.0, 28.0), (428.0, 462.0), (-428.0, 462.0)]).close().extrude(44.0).translate((-22.0, 0, 0))
ws_frame = outer.cut(inner)
ws_frame = ws_frame.rotate((0, 0, 0), (0, 1, 0), ws_rake).translate((ws_base_x, 0, ws_base_z))
glass_pane = cq.Workplane('YZ').polyline([(-476.0, 34.0), (476.0, 34.0), (422.0, 456.0), (-422.0, 456.0)]).close().extrude(8.0).translate((-4.0, 0, 0))
glass_pane = glass_pane.rotate((0, 0, 0), (0, 1, 0), ws_rake).translate((ws_base_x, 0, ws_base_z))
parts.append({"name": "windscreen_frame", "shape": ws_frame, "colour": "#cccccc", "material": "chrome"})
parts.append({"name": "windscreen_glass", "shape": glass_pane, "colour": "#bcd8e8", "material": "glass"})
rbx = 0.695 * LENGTH
roll = cylbtw(28.0, (rbx, -370.0, 815.0), (rbx, -370.0, 1000.0))
roll = roll.union(cylbtw(28.0, (rbx, -90.0, 815.0), (rbx, -90.0, 1000.0)))
arc = cq.Workplane('XY').newObject([cq.Solid.makeTorus(140.0, 28.0, cq.Vector(rbx, -230.0, 1000.0), cq.Vector(1, 0, 0))])
roll = roll.union(arc)
roll = roll.cut(box(500.0, 700.0, 320.0, rbx, -230.0, 840.0))
roll = roll.union(cylbtw(23.0, (rbx, -230.0, 1128.0), (0.665 * LENGTH, 285.0, 845.0)))
roll = roll.union(cylbtw(21.0, (rbx, -355.0, 1115.0), (rbx + 320.0, -100.0, 875.0)))
parts.append({"name": "roll_bar", "shape": roll, "colour": "#2f2f2f", "material": "metal"})
scoop = rbox(400.0, 330.0, 58.0, 0.250 * LENGTH, 0, 908.0, 18.0)
scoop_open = box(30.0, 240.0, 32.0, 0.250 * LENGTH - 198.0, 0, 916.0)
parts.append({"name": "bonnet_scoop", "shape": scoop, "colour": "#17408b", "material": "paint"})
parts.append({"name": "bonnet_scoop_intake", "shape": scoop_open, "colour": "#101010", "material": "metal"})
cap = cyl(46.0, 20.0, (0.795 * LENGTH, 0, 932.0), (0, 0, 1))
parts.append({"name": "fuel_cap", "shape": cap, "colour": "#dddddd", "material": "chrome"})
grille = cq.Workplane('YZ').ellipse(255.0, 72.0).extrude(40.0).translate((-14.0, 0, 462.0))
parts.append({"name": "grille", "shape": grille, "colour": "#191919", "material": "metal"})
for side, sy in (("left", -548.0), ("right", 548.0)):
    bucket = cyl(108.0, 150.0, (185.0, sy, 672.0), (-1, 0, 0))
    lamp = cyl(94.0, 152.0, (178.0, sy, 672.0), (-1, 0, 0))
    parts.append({"name": "headlight_bucket_" + side, "shape": bucket, "colour": "#dddddd", "material": "chrome"})
    parts.append({"name": "headlight_" + side, "shape": lamp, "colour": "#fff2b0", "material": "light"})
    ind = rbox(34.0, 52.0, 78.0, 26.0, sy * 0.84, 405.0, 9.0)
    parts.append({"name": "front_indicator_" + side, "shape": ind, "colour": "#ff9a1e", "material": "light"})
    tl = rbox(34.0, 58.0, 100.0, LENGTH - 18.0, sy * 0.90, 650.0, 9.0)
    parts.append({"name": "tail_light_" + side, "shape": tl, "colour": "#c01818", "material": "light"})
    vent = box(150.0, 26.0, 82.0, 0.365 * LENGTH, (758.0 if sy > 0 else -758.0), 552.0)
    parts.append({"name": "side_vent_" + side, "shape": vent, "colour": "#111111", "material": "metal"})
    handle = box(104.0, 24.0, 24.0, 0.525 * LENGTH, (715.0 if sy > 0 else -715.0), 730.0)
    parts.append({"name": "door_handle_" + side, "shape": handle, "colour": "#dddddd", "material": "chrome"})
mir = rbox(34.0, 78.0, 52.0, 0.448 * LENGTH, -688.0, 962.0, 9.0)
stalk = cylbtw(9.0, (0.458 * LENGTH, -618.0, 898.0), (0.448 * LENGTH, -678.0, 952.0))
parts.append({"name": "mirror_left", "shape": mir.union(stalk), "colour": "#dddddd", "material": "chrome"})
fb = rbox(32.0, 1020.0, 48.0, -26.0, 0, 372.0, 12.0)
parts.append({"name": "front_bumper", "shape": fb, "colour": "#dddddd", "material": "chrome"})
for side, sy in (("left", -470.0), ("right", 470.0)):
    ovr = rbox(44.0, 150.0, 74.0, LENGTH + 12.0, sy, 500.0, 10.0)
    parts.append({"name": "rear_overrider_" + side, "shape": ovr, "colour": "#dddddd", "material": "chrome"})
for side, sy in (("left", -748.0), ("right", 748.0)):
    pipe = cylbtw(30.0, (0.315 * LENGTH, sy, 205.0), (0.715 * LENGTH, sy, 205.0))
    tip = cylbtw(34.0, (0.715 * LENGTH, sy, 205.0), (0.745 * LENGTH, sy, 208.0))
    parts.append({"name": "side_exhaust_" + side, "shape": pipe.union(tip), "colour": "#c9c9c9", "material": "chrome"})
