plan = '''
Object: Shelby/AC Cobra open two-seat roadster.
Orientation: drawing side/plan views have FRONT on RIGHT, rear on LEFT, so measured u=1-x/LENGTH
with program frame x=0 at FRONT, x=LENGTH at rear, y=0 symmetry, z=0 ground.
Body: KEEP the proven side profile (cleaned side_top/side_bottom: windscreen spike u~0.50 and
roll-bar spike u~0.25 replaced by neighbour averages, tyre ground-touch dips replaced by the
0.0427L sill line, 36mm minimum end thickness) and the plan-profile intersect sampled exactly
from half_width(u) - this gave side IoU 0.89 and top 0.97.
End-view fix (main change): cross-sections are no longer centred super-ellipses. Every section
is built as a closed periodic spline whose half-width at each height z is
w(z)=half_width(u)*end_half_width(u,z/HEIGHT)/end_half_width(u,0.50H), with end_a (rear, u=0)
and end_b (front, u=1) linearly interpolated by station u - so the measured shoulder width
(full width h/H 0.05..0.65), bottom tuck and deck crown (narrowing above h/H 0.65) are carried
at every height. The flat underbody centre is RAISED 30..190mm above the sill line while the
outer skirts still reach side_bottom(u): the side silhouette still fills the measured outline,
but the front/rear projections no longer show a solid magenta slab between the wheels.
The old central y=+/-220mm side-profile core (which caused that slab) is replaced by TWO
side cores at y in [520,820] and [-820,-520], trimmed by the plan prism: they guarantee the
side silhouette at the outer body sides, where they overlap wheels/fenders in end view.
All body booleans are validity-checked with fallback to the last good solid.
Wheels (x4): radius 368mm (diameter 0.186L, as drawn, touching z=0) at centres read from the
side_bottom ground dips: front u~0.81 -> x=0.19L, rear u~0.225 -> x=0.775L. Ring tyres
(hollow centre, rounded shoulders); inside each a dark brake disc, an open chrome rim RING,
hub and 5 chrome spokes. Wheel-arch cuts follow the wheels.
Windscreen: where the end views draw it - centred and wide (1180mm base / 1060mm top, about
70% of body width as in the front view), top just below HEIGHT: base at cowl x=0.46L, raked
35deg, pane height 560 so its top lands near the measured windscreen spike u~0.50;
trapezoidal chrome FRAME only (outer minus inner opening) with a separate thin GLASS pane.
Roll bar: where the rear and side views draw it - single driver-side hoop centred y=-230mm
at x=0.71L (u~0.29, just behind the cockpit), top z~1140mm at the measured roll-bar spike
height, built from overlapping cylinders only (two legs, angled shoulders, top bar, a
forward-down diagonal brace in the hoop plane as drawn in the side view, and a rear stay).
Mirror moved inboard/down (y=-540, z~925) so it overlaps the windscreen/body silhouette in
end view instead of floating outside it, while staying visible in side/top views.
Other parts: hollow cockpit cut with floor, dashboard, 2 low leather seats, steering
wheel+column, gear lever, bonnet scoop with dark intake, rear fuel cap, oval front grille,
headlights sized as drawn (196mm chrome bucket / 172mm lamp) pushed forward so the lamp
faces sit proud of the nose, front indicators, tail lights, side vents, door handles, thin
front chrome bumper, two rear overriders, side exhausts tucked against the sills.
Main sizes/positions from measured outlines; small fitting sizes are engineering estimates.
'''
length_mm = 3960.0
LENGTH = 3960.0
WIDTH = 0.4240 * LENGTH
HEIGHT = 0.3058 * LENGTH
top_f = [0.1544,0.1957,0.2121,0.2204,0.2384,0.2894,0.2616,0.2301,0.1987,0.2099,0.3006,0.2451,0.2429,0.2414,0.2414,0.2264,0.2264,0.2234,0.2166,0.2039,0.1792]
bot_f = [0.1507,0.0735,0.0645,0.0555,0.0067,0.0007,0.0255,0.0412,0.0390,0.0427,0.0427,0.0427,0.0427,0.0427,0.0480,0.0240,0.0007,0.0067,0.0592,0.0652,0.1702]
hw_f = [0.1198,0.1859,0.1943,0.2029,0.2098,0.2120,0.2067,0.1977,0.1977,0.1980,0.1984,0.1984,0.1988,0.1992,0.2007,0.2063,0.2094,0.2082,0.2022,0.1890,0.1689]
enda_f = [0.1903,0.2075,0.2075,0.2075,0.2075,0.2075,0.2075,0.2075,0.2075,0.2075,0.2086,0.2098,0.2098,0.2068,0.1776,0.1537,0.1514,0.1484,0.1454,0.1365,0.0467]
endb_f = [0.1555,0.1972,0.1972,0.1972,0.1972,0.1972,0.1972,0.1972,0.1972,0.1972,0.1987,0.2028,0.2058,0.2039,0.1875,0.1540,0.1511,0.1481,0.1447,0.1362,0.0569]
body_top_f = list(top_f)
body_top_f[5] = 0.5 * (top_f[4] + top_f[6])
body_top_f[10] = 0.5 * (top_f[9] + top_f[11])
body_bot_f = list(bot_f)
for idx in (4, 5, 6, 15, 16, 17):
    body_bot_f[idx] = 0.0427
def interp(u, vals):
    s = min(max(u, 0.0), 1.0) * 20.0
    i = int(math.floor(s))
    if i >= 20:
        return vals[20]
    f = s - i
    return vals[i] * (1.0 - f) + vals[i + 1] * f
def endw(u, hf):
    h = min(max(hf, 0.0), 1.0)
    return (1.0 - u) * interp(h, enda_f) + u * interp(h, endb_f)
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
def isgood(w):
    try:
        s = w.val()
        return s is not None and s.isValid() and s.Volume() > 5000.0
    except Exception:
        return False
def safeop(a, b, op):
    try:
        if op == 'union':
            r = a.union(b)
        elif op == 'cut':
            r = a.cut(b)
        else:
            r = a.intersect(b)
        if isgood(r):
            return r
    except Exception:
        pass
    return a
def profile_zt_zb(u):
    zt = interp(u, body_top_f) * LENGTH
    zb = interp(u, body_bot_f) * LENGTH
    if zt - zb < 36.0:
        zc0 = 0.5 * (zt + zb)
        zt = zc0 + 18.0
        zb = zc0 - 18.0
    return zt, zb
ustations = [0.0, 0.01, 0.025, 0.05, 0.08, 0.11, 0.14, 0.17, 0.20, 0.23, 0.26, 0.29, 0.32, 0.35, 0.38, 0.41, 0.44, 0.47, 0.50, 0.53, 0.56, 0.59, 0.62, 0.65, 0.68, 0.71, 0.74, 0.77, 0.80, 0.83, 0.86, 0.89, 0.92, 0.95, 0.975, 0.99, 1.0]
wires = []
for u in ustations:
    x = (1.0 - u) * LENGTH
    hw = interp(u, hw_f) * LENGTH * 0.99
    zt, zb = profile_zt_zb(u)
    sec = zt - zb
    if sec > 80.0:
        zbc = zb + min(190.0, max(45.0, 0.23 * sec))
    else:
        zbc = zb + 0.15 * sec
    wref = endw(u, 0.50)
    if wref < 0.05:
        wref = 0.21
    def wat(z, u=u, hw=hw, wref=wref):
        ratio = endw(u, z / HEIGHT) / wref
        if ratio > 1.02:
            ratio = 1.02
        if ratio < 0.42:
            ratio = 0.42
        return hw * ratio
    levels = [0.0, 0.07, 0.16, 0.28, 0.42, 0.58, 0.72, 0.84, 0.93, 1.0]
    pts = []
    pts.append(cq.Vector(x, 0.0, zbc))
    pts.append(cq.Vector(x, 0.60 * wat(zbc), zbc))
    pts.append(cq.Vector(x, 0.93 * wat(zb + 0.05 * sec), zb + 0.05 * sec))
    for f in levels:
        z = zb + f * sec
        pts.append(cq.Vector(x, wat(z), z))
    pts.append(cq.Vector(x, 0.0, zt))
    for f in reversed(levels):
        z = zb + f * sec
        pts.append(cq.Vector(x, -wat(z), z))
    pts.append(cq.Vector(x, -0.93 * wat(zb + 0.05 * sec), zb + 0.05 * sec))
    pts.append(cq.Vector(x, -0.60 * wat(zbc), zbc))
    try:
        edge = cq.Edge.makeSpline(pts, periodic=True)
        wires.append(cq.Wire.assembleEdges([edge]))
    except Exception:
        wires.append(cq.Wire.makePolygon(pts + [pts[0]]))
try:
    body = cq.Workplane('XY').newObject([cq.Solid.makeLoft(wires, False)])
except Exception:
    body = cq.Workplane('XY').newObject([cq.Solid.makeLoft(wires, True)])
top_pts = []
bot_pts = []
for i in range(41):
    u = i / 40.0
    zt, zb = profile_zt_zb(u)
    top_pts.append(cq.Vector((1.0 - u) * LENGTH, 0, zt))
    bot_pts.append(cq.Vector((1.0 - u) * LENGTH, 0, zb))
try:
    e_top = cq.Edge.makeSpline(top_pts)
    e_bot = cq.Edge.makeSpline(list(reversed(bot_pts)))
    e_front = cq.Edge.makeLine(top_pts[-1], bot_pts[-1])
    e_rear = cq.Edge.makeLine(bot_pts[0], top_pts[0])
    side_wire = cq.Wire.assembleEdges([e_top, e_front, e_bot, e_rear])
except Exception:
    side_wire = cq.Wire.makePolygon(top_pts + list(reversed(bot_pts)) + [top_pts[0]])
side_face = cq.Face.makeFromWires(side_wire)
core_r = cq.Solid.extrudeLinear(side_face, cq.Vector(0, 300.0, 0)).translate(cq.Vector(0, 520.0, 0))
core_l = cq.Solid.extrudeLinear(side_face, cq.Vector(0, 300.0, 0)).translate(cq.Vector(0, -820.0, 0))
body = safeop(body, cq.Workplane('XY').newObject([core_r]), 'union')
body = safeop(body, cq.Workplane('XY').newObject([core_l]), 'union')
plan_pts = []
for i in range(101):
    u = i / 100.0
    plan_pts.append(cq.Vector((1.0 - u) * LENGTH, interp(u, hw_f) * LENGTH, -200.0))
for i in range(100, -1, -1):
    u = i / 100.0
    plan_pts.append(cq.Vector((1.0 - u) * LENGTH, -interp(u, hw_f) * LENGTH, -200.0))
plan_wire = cq.Wire.makePolygon(plan_pts + [plan_pts[0]])
plan_prism = cq.Solid.extrudeLinear(cq.Face.makeFromWires(plan_wire), cq.Vector(0, 0, HEIGHT + 700.0))
body = safeop(body, cq.Workplane('XY').newObject([plan_prism]), 'intersect')
wheel_r = 368.0
xf = 0.19 * LENGTH
xr = 0.775 * LENGTH
for wx in (xf, xr):
    body = safeop(body, cyl(395.0, WIDTH + 300.0, (wx, -WIDTH/2 - 150.0, wheel_r), (0, 1, 0)), 'cut')
cockpit_cut = cq.Workplane('XY').ellipse(560.0, 475.0).extrude(760.0).translate((0.565 * LENGTH, 0, 600.0))
body = safeop(body, cockpit_cut, 'cut')
if not isgood(body):
    body = safeop(body, box(900.0, 900.0, 500.0, 0.565 * LENGTH, 0, 850.0), 'cut')
parts = []
parts.append({"name": "body", "shape": body, "colour": "#17408b", "material": "paint"})
for tag, wx in (("front", xf), ("rear", xr)):
    for side, sy in (("left", -1), ("right", 1)):
        cy = sy * 690.0
        outy = cy + sy * 96.0
        tyre = cyl(wheel_r, 235.0, (wx, cy - 117.5, wheel_r), (0, 1, 0))
        tyre = safeop(tyre, cyl(195.0, 249.0, (wx, cy - 124.5, wheel_r), (0, 1, 0)), 'cut')
        try:
            tt = tyre.edges().fillet(22.0)
            if isgood(tt):
                tyre = tt
        except Exception:
            pass
        brake = cyl(160.0, 22.0, (wx, cy + sy * 52.0 - 11.0, wheel_r), (0, 1, 0))
        ring = cyl(188.0, 30.0, (wx, outy - 15.0, wheel_r), (0, 1, 0))
        ring = safeop(ring, cyl(154.0, 38.0, (wx, outy - 19.0, wheel_r), (0, 1, 0)), 'cut')
        hub = cyl(50.0, 46.0, (wx, outy - 23.0, wheel_r), (0, 1, 0))
        rim = safeop(ring, hub, 'union')
        for k in range(5):
            spoke = box(132.0, 26.0, 36.0, wx + 86.0, outy, wheel_r)
            spoke = spoke.rotate((wx, 0, wheel_r), (wx, 1, wheel_r), k * 72.0)
            rim = safeop(rim, spoke, 'union')
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
    parts.append({"name": "seat_" + side, "shape": safeop(base, back, 'union'), "colour": "#5a2d18", "material": "leather"})
swdir = cq.Vector(-0.55, 0, 0.835).normalized()
steer = cq.Workplane('XY').newObject([cq.Solid.makeTorus(122.0, 14.0, cq.Vector(0.478 * LENGTH, -230.0, 862.0), swdir)])
column = cylbtw(16.0, (0.472 * LENGTH, -230.0, 838.0), (0.505 * LENGTH, -230.0, 748.0))
lever = cylbtw(10.0, (0.548 * LENGTH, -55.0, 632.0), (0.560 * LENGTH, -48.0, 752.0))
knob = cq.Workplane('XY').newObject([cq.Solid.makeSphere(24.0, cq.Vector(0.560 * LENGTH, -48.0, 758.0))])
parts.append({"name": "steering_wheel", "shape": safeop(steer, column, 'union'), "colour": "#2a2a2a", "material": "plastic"})
parts.append({"name": "gear_lever", "shape": safeop(lever, knob, 'union'), "colour": "#bbbbbb", "material": "chrome"})
ws_base_x = 0.46 * LENGTH
ws_base_z = 730.0
ws_rake = 35.0
outer = cq.Workplane('YZ').polyline([(-590.0, 0.0), (590.0, 0.0), (530.0, 560.0), (-530.0, 560.0)]).close().extrude(36.0).translate((-18.0, 0, 0))
inner = cq.Workplane('YZ').polyline([(-562.0, 28.0), (562.0, 28.0), (503.0, 532.0), (-503.0, 532.0)]).close().extrude(44.0).translate((-22.0, 0, 0))
ws_frame = safeop(outer, inner, 'cut')
ws_frame = ws_frame.rotate((0, 0, 0), (0, 1, 0), ws_rake).translate((ws_base_x, 0, ws_base_z))
glass_pane = cq.Workplane('YZ').polyline([(-556.0, 34.0), (556.0, 34.0), (497.0, 526.0), (-497.0, 526.0)]).close().extrude(8.0).translate((-4.0, 0, 0))
glass_pane = glass_pane.rotate((0, 0, 0), (0, 1, 0), ws_rake).translate((ws_base_x, 0, ws_base_z))
parts.append({"name": "windscreen_frame", "shape": ws_frame, "colour": "#cccccc", "material": "chrome"})
parts.append({"name": "windscreen_glass", "shape": glass_pane, "colour": "#bcd8e8", "material": "glass"})
rbx = 0.71 * LENGTH
roll = cylbtw(26.0, (rbx, -360.0, 800.0), (rbx, -360.0, 1020.0))
roll = safeop(roll, cylbtw(26.0, (rbx, -100.0, 800.0), (rbx, -100.0, 1020.0)), 'union')
roll = safeop(roll, cylbtw(26.0, (rbx, -360.0, 1020.0), (rbx, -322.0, 1092.0)), 'union')
roll = safeop(roll, cylbtw(26.0, (rbx, -138.0, 1092.0), (rbx, -100.0, 1020.0)), 'union')
roll = safeop(roll, cylbtw(26.0, (rbx, -330.0, 1088.0), (rbx, -130.0, 1088.0)), 'union')
roll = safeop(roll, cylbtw(23.0, (rbx, -230.0, 1088.0), (rbx - 400.0, -230.0, 835.0)), 'union')
roll = safeop(roll, cylbtw(21.0, (rbx, -345.0, 1050.0), (rbx + 320.0, -100.0, 875.0)), 'union')
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
    bucket = cyl(98.0, 160.0, (150.0, sy, 672.0), (-1, 0, 0))
    lamp = cyl(86.0, 165.0, (142.0, sy, 672.0), (-1, 0, 0))
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
mir = rbox(34.0, 78.0, 52.0, 0.448 * LENGTH, -540.0, 925.0, 9.0)
stalk = cylbtw(9.0, (0.458 * LENGTH, -520.0, 880.0), (0.448 * LENGTH, -535.0, 918.0))
parts.append({"name": "mirror_left", "shape": safeop(mir, stalk, 'union'), "colour": "#dddddd", "material": "chrome"})
fb = rbox(32.0, 1020.0, 48.0, -30.0, 0, 372.0, 12.0)
parts.append({"name": "front_bumper", "shape": fb, "colour": "#dddddd", "material": "chrome"})
for side, sy in (("left", -470.0), ("right", 470.0)):
    ovr = rbox(44.0, 150.0, 74.0, LENGTH + 12.0, sy, 500.0, 10.0)
    parts.append({"name": "rear_overrider_" + side, "shape": ovr, "colour": "#dddddd", "material": "chrome"})
for side, sy in (("left", -748.0), ("right", 748.0)):
    pipe = cylbtw(30.0, (0.315 * LENGTH, sy, 225.0), (0.715 * LENGTH, sy, 225.0))
    tip = cylbtw(34.0, (0.715 * LENGTH, sy, 225.0), (0.745 * LENGTH, sy, 228.0))
    parts.append({"name": "side_exhaust_" + side, "shape": safeop(pipe, tip, 'union'), "colour": "#c9c9c9", "material": "chrome"})