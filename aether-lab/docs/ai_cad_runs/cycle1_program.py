plan = '''
Object: Shelby/AC Cobra open two-seat roadster.
Orientation: side and plan views are drawn with the FRONT on the RIGHT and the rear on the LEFT.
Therefore u (measured from the left of the drawing) = 1 - x/LENGTH, with x=0 at the front bumper face.
Main body: loft of convex super-elliptical cross-sections through interpolated measured stations.
side_top is capped at 0.245*L to remove windscreen/roll-bar spikes, side_bottom is floored at
0.040*L to remove the wheels (which dip to z=0 in the side profile) and give the rocker line;
the underside centre of each section is then lifted (sides stay at side_bottom) so the end views
show the raised floor between the wheels while the side rocker line is unchanged.
Wheels: front centre x=0.205*L, rear x=0.775*L, tyre radius 400 mm with a 415 mm arch cut so
the tyre fills the drawn arch (round-4 385/445 left a red gap ring in the side overlay).
Parts: body; 4 tyres + rims; cockpit cut, dashboard, 2 low leather seats, steering wheel+column,
low diagonal cockpit brace; windscreen frame+glass at x~0.465*L tilted rearward (+22 deg about Y,
fixing round-4 forward lean) reaching the drawn spike height, narrower (880 mm) for the end views;
driver roll-bar hoop at x~0.705*L (moved forward from 0.735*L) with transverse top, forward side
diagonal and cross diagonal; bonnet scoop (lowered), fuel cap; oval grille, headlights, indicators,
tail lights; narrower chrome bumpers; door handles, one small mirror; side exhausts tucked to
y=740 so they do not widen the plan silhouette.
'''
length_mm = 3960.0
LENGTH = 3960.0
WIDTH = 0.4240 * LENGTH
HEIGHT = 0.3058 * LENGTH

us = [i / 20.0 for i in range(21)]
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

def box(sx, sy, sz, tx, ty, tz):
    return cq.Workplane('XY').box(sx, sy, sz).translate((tx, ty, tz))

def sgnpow(v, p):
    if v >= 0:
        return v ** p
    return -((-v) ** p)

# ---- main body loft: fuller super-ellipse sections, underside centre lifted ----
wires = []
for iu in range(41):
    u = iu / 40.0
    x = (1.0 - u) * LENGTH
    hw = interp(u, hw_f) * LENGTH
    zt = min(interp(u, top_f), 0.245) * LENGTH
    zb = interp(u, bot_f) * LENGTH
    if 0.03 < u < 0.97:
        zb = max(zb, 0.040 * LENGTH)
    zc = 0.5 * (zt + zb)
    rz = max(0.5 * (zt - zb), 16.0)
    pts = []
    for k in range(28):
        a = 2.0 * math.pi * k / 28.0
        y = hw * sgnpow(math.cos(a), 0.62)
        z = zc + rz * sgnpow(math.sin(a), 0.62)
        if z < zc:
            frac = y / hw if hw > 1.0 else 0.0
            z += 0.42 * rz * max(0.0, 1.0 - frac * frac)
        pts.append(cq.Vector(x, y, z))
    wires.append(cq.Wire.makePolygon(pts + [pts[0]]))
body = cq.Workplane('XY').newObject([cq.Solid.makeLoft(wires, True)])

wheel_r = 400.0
xf = 0.205 * LENGTH
xr = 0.775 * LENGTH
for wx in (xf, xr):
    body = body.cut(cyl(415.0, WIDTH + 300.0, (wx, -WIDTH/2 - 150.0, wheel_r), (0, 1, 0)))
cockpit_cut = cq.Workplane('XY').ellipse(470.0, 500.0).extrude(750.0).translate((0.565 * LENGTH, 0, 620.0))
body = body.cut(cockpit_cut)

parts = []
parts.append({"name": "body", "shape": body, "colour": "#173f8a", "material": "paint"})

# ---- wheels ----
for tag, wx in (("front", xf), ("rear", xr)):
    for side, sy in (("left", -1), ("right", 1)):
        tyre = cyl(wheel_r, 250.0, (wx, sy * 705.0 - 125.0, wheel_r), (0, 1, 0))
        rim = cyl(210.0, 260.0, (wx, sy * 705.0 - 130.0, wheel_r), (0, 1, 0))
        hub = cyl(55.0, 272.0, (wx, sy * 705.0 - 136.0, wheel_r), (0, 1, 0))
        parts.append({"name": tag + "_" + side + "_tyre", "shape": tyre, "colour": "#151515", "material": "rubber"})
        parts.append({"name": tag + "_" + side + "_rim", "shape": rim.union(hub), "colour": "#c8c8c8", "material": "chrome"})

# ---- cockpit interior ----
dash = box(90.0, 980.0, 110.0, 0.455 * LENGTH, 0, 760.0)
parts.append({"name": "dashboard", "shape": dash, "colour": "#222222", "material": "plastic"})
for side, sy in (("left", -230.0), ("right", 230.0)):
    base = box(430.0, 380.0, 90.0, 0.60 * LENGTH, sy, 590.0)
    back = cq.Workplane('XY').box(110.0, 380.0, 320.0).rotate((0, 0, 0), (0, 1, 0), 18.0).translate((0.66 * LENGTH, sy, 730.0))
    parts.append({"name": "seat_" + side, "shape": base.union(back), "colour": "#5a2d18", "material": "leather"})
sw_dir = cq.Vector(-0.55, 0, 0.835).normalized()
steer = cq.Workplane('XY').newObject([cq.Solid.makeTorus(125.0, 15.0, cq.Vector(0.475 * LENGTH, -230.0, 870.0), sw_dir)])
column = cyl(18.0, 230.0, (0.475 * LENGTH + 20.0, -230.0, 855.0), (1, 0, -0.35))
parts.append({"name": "steering_wheel", "shape": steer.union(column), "colour": "#2a2a2a", "material": "plastic"})
dp1 = (0.47 * LENGTH, -320.0, 750.0)
dp2 = (0.66 * LENGTH, 110.0, 750.0)
ddx, ddy = dp2[0] - dp1[0], dp2[1] - dp1[1]
dlen = math.sqrt(ddx * ddx + ddy * ddy)
brace = cyl(22.0, dlen, dp1, (ddx / dlen, ddy / dlen, 0))
parts.append({"name": "cockpit_brace", "shape": brace, "colour": "#888888", "material": "metal"})

# ---- windscreen: tilted rearward (top toward +x/rear), narrower for end views ----
frame = cq.Workplane('XY').box(34.0, 880.0, 360.0).rotate((0, 0, 0), (0, 1, 0), 22.0).translate((0.465 * LENGTH, 0, 1010.0))
glass = cq.Workplane('XY').box(18.0, 800.0, 275.0).rotate((0, 0, 0), (0, 1, 0), 22.0).translate((0.465 * LENGTH + 12.0, 0, 1015.0))
parts.append({"name": "windscreen_frame", "shape": frame, "colour": "#cccccc", "material": "chrome"})
parts.append({"name": "windscreen_glass", "shape": glass, "colour": "#bcd8e8", "material": "glass"})

# ---- roll bar: hoop + forward side diagonal + cross diagonal ----
rbx = 0.705 * LENGTH
leg1 = cyl(30.0, 290.0, (rbx, -390.0, 830.0), (0, 0, 1))
leg2 = cyl(30.0, 290.0, (rbx, -70.0, 830.0), (0, 0, 1))
topbar = cyl(30.0, 380.0, (rbx, -420.0, 1115.0), (0, 1, 0))
sd_len = math.sqrt((0.125 * LENGTH) ** 2 + 255.0 ** 2)
sdiag = cyl(26.0, sd_len, (rbx, -230.0, 1110.0), (-0.125 * LENGTH / sd_len, 0, -255.0 / sd_len))
diag_len = math.sqrt((0.10 * LENGTH) ** 2 + 230.0 ** 2)
diag = cyl(24.0, diag_len, (rbx, -230.0, 1110.0), (-0.10 * LENGTH / diag_len, 0, -230.0 / diag_len))
parts.append({"name": "roll_bar", "shape": leg1.union(leg2).union(topbar).union(sdiag), "colour": "#333333", "material": "metal"})
parts.append({"name": "roll_bar_brace", "shape": diag, "colour": "#333333", "material": "metal"})

# ---- bonnet scoop, fuel cap ----
scoop = box(420.0, 350.0, 45.0, 0.235 * LENGTH, 0, 862.0)
parts.append({"name": "bonnet_scoop", "shape": scoop, "colour": "#173f8a", "material": "paint"})
cap = cyl(56.0, 28.0, (0.715 * LENGTH, 0, 955.0), (0, 0, 1))
parts.append({"name": "fuel_cap", "shape": cap, "colour": "#dddddd", "material": "chrome"})

# ---- front grille, lights, bumpers, handles, mirror ----
grille = cq.Workplane('YZ').ellipse(320.0, 100.0).extrude(45.0).translate((-25.0, 0, 470.0))
parts.append({"name": "grille", "shape": grille, "colour": "#1c1c1c", "material": "metal"})
for side, sy in (("left", -560.0), ("right", 560.0)):
    hl = cyl(110.0, 65.0, (55.0, sy, 640.0), (-1, 0, 0))
    parts.append({"name": "headlight_" + side, "shape": hl, "colour": "#fff2b0", "material": "light"})
    ind = box(35.0, 55.0, 85.0, 5.0, sy * 0.82, 430.0)
    parts.append({"name": "front_indicator_" + side, "shape": ind, "colour": "#ff9a1e", "material": "light"})
    tl = box(35.0, 60.0, 105.0, LENGTH - 5.0, sy, 660.0)
    parts.append({"name": "tail_light_" + side, "shape": tl, "colour": "#c01818", "material": "light"})
    handle = box(105.0, 22.0, 26.0, 0.52 * LENGTH, (785.0 if sy > 0 else -785.0), 740.0)
    parts.append({"name": "door_handle_" + side, "shape": handle, "colour": "#dddddd", "material": "chrome"})
mir = box(36.0, 80.0, 55.0, 0.44 * LENGTH, -585.0, 980.0)
parts.append({"name": "mirror_left", "shape": mir, "colour": "#dddddd", "material": "chrome"})
fb = box(42.0, 1150.0, 75.0, -28.0, 0, 390.0)
rb = box(42.0, 1100.0, 75.0, LENGTH + 28.0, 0, 500.0)
parts.append({"name": "front_bumper", "shape": fb, "colour": "#dddddd", "material": "chrome"})
parts.append({"name": "rear_bumper", "shape": rb, "colour": "#dddddd", "material": "chrome"})

# ---- side exhaust pipes (tucked in) ----
for side, sy in (("left", -740.0), ("right", 740.0)):
    pipe = cyl(38.0, 1450.0, (0.33 * LENGTH, sy, 190.0), (1, 0, 0))
    parts.append({"name": "side_exhaust_" + side, "shape": pipe, "colour": "#cccccc", "material": "chrome"})
