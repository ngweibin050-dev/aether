plan = '''
Object: Shelby/AC Cobra open two-seat roadster, blue.
Orientation: side and plan views drawn with FRONT on RIGHT, rear on LEFT, so u=1-x/LENGTH (x=0 front bumper, x=LENGTH rear). Plan has same left/right. End_a = rear view, end_b = front view.
Body: loft of convex super-ellipse polygon sections (exponent 0.65, 20 pts) through 14 interpolated measured stations, ruled=False for smoothness. side_top capped 0.245*L to remove windscreen/roll spikes, side_bottom floored 0.040*L to remove wheels and keep rocker line, underside centre lifted 0.45*rz for flat wide floor seen in end views. Wheel-arch cuts r=355 at xf=0.205*L front, xr=0.775*L rear, tyre r=340 fills arch to ground. Cockpit elliptical hollow cut open at top.
Parts from measured/drawing: 4 tyres+rims+hubs, cockpit floor, dash, 2 leather seats, steering wheel+column, gear lever, tilted windscreen chrome frame + glass (x~0.462*L, 22deg rearward, 980 wide), driver roll hoop + forward diagonal + rear stay (x~0.695*L), bonnet scoop, fuel cap, oval grille, headlight buckets+lamps, indicators, tail lights, side vents, door handles, stalk mirror, thin chrome bumpers, side exhausts tucked at y=730 z=150.
'''
length_mm = 3960.0
LENGTH = 3960.0
WIDTH = 0.4240 * LENGTH
HEIGHT = 0.3058 * LENGTH
top_f = [0.1544,0.1957,0.2121,0.2204,0.2384,0.2894,0.2616,0.2301,0.1987,0.2099,0.3006,0.2451,0.2429,0.2414,0.2414,0.2264,0.2264,0.2234,0.2166,0.2039,0.1792]
bot_f = [0.1507,0.0735,0.0645,0.0555,0.0067,0.0007,0.0255,0.0412,0.0390,0.0427,0.0427,0.0427,0.0427,0.0427,0.0480,0.0240,0.0007,0.0067,0.0592,0.0652,0.1702]
hw_f = [0.1198,0.1859,0.1943,0.2029,0.2098,0.2120,0.2067,0.1977,0.1977,0.1980,0.1984,0.1984,0.1988,0.1992,0.2007,0.2063,0.2094,0.2082,0.2022,0.1890,0.1689]
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
def tube(r, p1, p2):
    dx, dy, dz = p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2]
    ln = math.sqrt(dx*dx + dy*dy + dz*dz)
    return cyl(r, ln, p1, (dx/ln, dy/ln, dz/ln))
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
stations = [0.0,0.07,0.15,0.22,0.30,0.38,0.45,0.52,0.60,0.68,0.76,0.84,0.92,1.0]
wires = []
for u in stations:
    x = (1.0 - u) * LENGTH
    hw = interp(u, hw_f) * LENGTH
    zt = min(interp(u, top_f), 0.245) * LENGTH
    zb = interp(u, bot_f) * LENGTH
    if 0.03 < u < 0.97:
        zb = max(zb, 0.040 * LENGTH)
    zc = 0.5 * (zt + zb)
    rz = max(0.5 * (zt - zb), 20.0)
    pts = []
    for k in range(20):
        a = 2.0 * math.pi * k / 20.0
        y = hw * sgnpow(math.cos(a), 0.65)
        z = zc + rz * sgnpow(math.sin(a), 0.65)
        if z < zc:
            frac = y / hw if hw > 1.0 else 0.0
            z += 0.45 * rz * max(0.0, 1.0 - frac * frac)
        pts.append(cq.Vector(x, y, z))
    wires.append(cq.Wire.makePolygon(pts + [pts[0]]))
body = cq.Workplane('XY').newObject([cq.Solid.makeLoft(wires, False)])
wheel_r = 340.0
xf = 0.205 * LENGTH
xr = 0.775 * LENGTH
for wx in (xf, xr):
    body = body.cut(cyl(355.0, WIDTH + 300.0, (wx, -WIDTH/2 - 150.0, wheel_r), (0, 1, 0)))
cockpit_cut = cq.Workplane('XY').ellipse(580.0, 460.0).extrude(780.0).translate((0.565 * LENGTH, 0, 600.0))
body = body.cut(cockpit_cut)
parts = []
parts.append({"name": "body", "shape": body, "colour": "#17408b", "material": "paint"})
for tag, wx in (("front", xf), ("rear", xr)):
    for side, sy in (("left", -1), ("right", 1)):
        tyre = cyl(wheel_r, 250.0, (wx, sy * 700.0 - 125.0, wheel_r), (0, 1, 0))
        rim = cyl(195.0, 254.0, (wx, sy * 700.0 - 127.0, wheel_r), (0, 1, 0))
        dark = cyl(140.0, 256.0, (wx, sy * 700.0 - 128.0, wheel_r), (0, 1, 0))
        hub = cyl(52.0, 264.0, (wx, sy * 700.0 - 132.0, wheel_r), (0, 1, 0))
        parts.append({"name": tag + "_" + side + "_tyre", "shape": tyre, "colour": "#141414", "material": "rubber"})
        parts.append({"name": tag + "_" + side + "_rim", "shape": rim.union(hub), "colour": "#d0d0d0", "material": "chrome"})
        parts.append({"name": tag + "_" + side + "_rim_centre", "shape": dark, "colour": "#3a3a3a", "material": "metal"})
floor = rbox(1020.0, 860.0, 50.0, 0.565 * LENGTH, 0, 615.0, 18.0)
parts.append({"name": "cockpit_floor", "shape": floor, "colour": "#1e1e1e", "material": "plastic"})
dash = rbox(95.0, 940.0, 115.0, 0.445 * LENGTH, 0, 750.0, 20.0)
parts.append({"name": "dashboard", "shape": dash, "colour": "#222222", "material": "plastic"})
for side, sy in (("left", -235.0), ("right", 235.0)):
    base = rbox(460.0, 390.0, 100.0, 0.60 * LENGTH, sy, 605.0, 28.0)
    back = cq.Workplane('XY').box(115.0, 390.0, 340.0)
    try:
        back = back.edges().fillet(24.0)
    except Exception:
        pass
    back = back.rotate((0, 0, 0), (0, 1, 0), 17.0).translate((0.67 * LENGTH, sy, 740.0))
    parts.append({"name": "seat_" + side, "shape": base.union(back), "colour": "#5a2d18", "material": "leather"})
swdir = cq.Vector(-0.55, 0, 0.835).normalized()
steer = cq.Workplane('XY').newObject([cq.Solid.makeTorus(126.0, 15.0, cq.Vector(0.465 * LENGTH, -235.0, 870.0), swdir)])
column = cyl(17.0, 240.0, (0.468 * LENGTH, -235.0, 852.0), (1, 0, -0.38))
lever = cyl(11.0, 135.0, (0.54 * LENGTH, -60.0, 635.0), (0.25, 0, 1))
parts.append({"name": "steering_wheel", "shape": steer.union(column), "colour": "#2a2a2a", "material": "plastic"})
parts.append({"name": "gear_lever", "shape": lever, "colour": "#bbbbbb", "material": "chrome"})
frame_outer = cq.Workplane('XY').box(30.0, 980.0, 330.0).rotate((0, 0, 0), (0, 1, 0), 22.0).translate((0.462 * LENGTH, 0, 1010.0))
frame_inner = cq.Workplane('XY').box(40.0, 880.0, 235.0).rotate((0, 0, 0), (0, 1, 0), 22.0).translate((0.462 * LENGTH, 0, 1018.0))
frame = frame_outer.cut(frame_inner)
glass = cq.Workplane('XY').box(14.0, 875.0, 232.0).rotate((0, 0, 0), (0, 1, 0), 22.0).translate((0.462 * LENGTH + 2.0, 0, 1018.0))
parts.append({"name": "windscreen_frame", "shape": frame, "colour": "#cccccc", "material": "chrome"})
parts.append({"name": "windscreen_glass", "shape": glass, "colour": "#bcd8e8", "material": "glass"})
rbx = 0.695 * LENGTH
leg1 = cyl(30.0, 300.0, (rbx, -405.0, 830.0), (0, 0, 1))
leg2 = cyl(30.0, 300.0, (rbx, -65.0, 830.0), (0, 0, 1))
topbar = cyl(30.0, 400.0, (rbx, -435.0, 1125.0), (0, 1, 0))
diag = tube(24.0, (rbx, -380.0, 1115.0), (rbx - 470.0, 300.0, 845.0))
rearstay = tube(24.0, (rbx, -235.0, 1120.0), (rbx + 330.0, -235.0, 880.0))
parts.append({"name": "roll_bar", "shape": leg1.union(leg2).union(topbar).union(diag).union(rearstay), "colour": "#2f2f2f", "material": "metal"})
scoop = rbox(430.0, 360.0, 60.0, 0.25 * LENGTH, 0, 885.0, 20.0)
parts.append({"name": "bonnet_scoop", "shape": scoop, "colour": "#17408b", "material": "paint"})
cap = cyl(57.0, 30.0, (0.80 * LENGTH, 0, 925.0), (0, 0, 1))
parts.append({"name": "fuel_cap", "shape": cap, "colour": "#dddddd", "material": "chrome"})
grille = cq.Workplane('YZ').ellipse(330.0, 105.0).extrude(50.0).translate((-28.0, 0, 465.0))
parts.append({"name": "grille", "shape": grille, "colour": "#191919", "material": "metal"})
for side, sy in (("left", -565.0), ("right", 565.0)):
    bucket = cyl(122.0, 55.0, (72.0, sy, 645.0), (-1, 0, 0))
    lamp = cyl(108.0, 70.0, (58.0, sy, 645.0), (-1, 0, 0))
    parts.append({"name": "headlight_bucket_" + side, "shape": bucket, "colour": "#dddddd", "material": "chrome"})
    parts.append({"name": "headlight_" + side, "shape": lamp, "colour": "#fff2b0", "material": "light"})
    ind = rbox(38.0, 58.0, 88.0, 8.0, sy * 0.80, 425.0, 10.0)
    parts.append({"name": "front_indicator_" + side, "shape": ind, "colour": "#ff9a1e", "material": "light"})
    tl = rbox(38.0, 62.0, 108.0, LENGTH - 8.0, sy, 655.0, 10.0)
    parts.append({"name": "tail_light_" + side, "shape": tl, "colour": "#c01818", "material": "light"})
    vent = box(150.0, 24.0, 85.0, 0.365 * LENGTH, (812.0 if sy > 0 else -812.0), 560.0)
    parts.append({"name": "side_vent_" + side, "shape": vent, "colour": "#111111", "material": "metal"})
    handle = box(108.0, 22.0, 26.0, 0.525 * LENGTH, (788.0 if sy > 0 else -788.0), 745.0)
    parts.append({"name": "door_handle_" + side, "shape": handle, "colour": "#dddddd", "material": "chrome"})
mir = rbox(38.0, 85.0, 58.0, 0.44 * LENGTH, -575.0, 975.0, 10.0)
stalk = tube(10.0, (0.44 * LENGTH, -545.0, 930.0), (0.44 * LENGTH, -575.0, 960.0))
parts.append({"name": "mirror_left", "shape": mir.union(stalk), "colour": "#dddddd", "material": "chrome"})
fb = rbox(40.0, 1150.0, 70.0, -30.0, 0, 385.0, 14.0)
rb = rbox(40.0, 1100.0, 70.0, LENGTH + 30.0, 0, 495.0, 14.0)
parts.append({"name": "front_bumper", "shape": fb, "colour": "#dddddd", "material": "chrome"})
parts.append({"name": "rear_bumper", "shape": rb, "colour": "#dddddd", "material": "chrome"})
for side, sy in (("left", -730.0), ("right", 730.0)):
    pipe = cyl(37.0, 1250.0, (0.36 * LENGTH, sy, 150.0), (1, 0, 0))
    tip = cyl(41.0, 120.0, (0.36 * LENGTH + 1250.0, sy, 150.0), (1, 0, 0.03))
    parts.append({"name": "side_exhaust_" + side, "shape": pipe.union(tip), "colour": "#c9c9c9", "material": "chrome"})
