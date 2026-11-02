"""Pure gear mathematics (ISO 54 modules, involute outline, mesh check). No geometry is built here: these are the
numbers a future CAD involute-gear feature (Phase C) uses. Moved out of engine/geometry.py when the triangle-mesh
primitive builders were removed (Phase A)."""
import numpy as np


STANDARD_MODULES = (0.5, 0.6, 0.8, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20)   # ISO 54 series I


MODULES_II = (0.55, 0.7, 0.9, 1.125, 1.375, 1.75, 2.25, 2.75, 3.5, 4.5, 5.5, 7, 9, 11, 14, 18)   # ISO 54 series II


def snap_module(m):
    return min(STANDARD_MODULES, key=lambda s: abs(np.log(s / m)))


def module_for(m, tol=0.03):
    """The module a gear drawn at measured module m gets: a standard ISO 54 module (series I first, then series II)
    only if it is within tol of m; otherwise the measured module itself, so the built gear keeps the drawn size
    (snapping 2.16 to 2 made a drawn 28 mm tip circle 26 mm). Returns (module, source)."""
    for series, name in ((STANDARD_MODULES, "ISO 54 series I"), (MODULES_II, "ISO 54 series II")):
        s = min(series, key=lambda v: abs(np.log(v / m)))
        if abs(s / m - 1) <= tol:
            return float(s), f"{name} (within {100 * abs(s / m - 1):.1f} % of the drawn size)"
    return round(float(m), 3), f"measured from the drawing (no ISO 54 module within {100 * tol:.0f} %)"


def gear_profile(teeth=12, module=2.0, pressure_angle=20.0, phase=0.0, flank_pts=7):
    """Involute spur gear outline (standard full-depth teeth, no profile shift), counter-clockwise.

    Pitch radius r = m z / 2, base rb = r cos(alpha), tip ra = r + m, root rf = r - 1.25 m. Flank = involute of the
    base circle; tooth half-angle at radius R: pi/(2z) + inv(alpha) - inv(alpha_R), inv(a) = tan a - a,
    alpha_R = arccos(rb / R). Below the base circle (small tooth counts) the flank continues radially.
    phase (deg): rotation of tooth 0, which is centred on the +x axis at phase 0."""
    z = int(teeth)
    m = float(module)
    al = np.radians(pressure_angle)
    r = m * z / 2
    rb, ra, rf = r * np.cos(al), r + m, r - 1.25 * m

    def inv(a):
        return np.tan(a) - a

    def half(R):
        return np.pi / (2 * z) + inv(al) - inv(np.arccos(np.clip(rb / R, -1, 1)))

    R = np.linspace(max(rb, rf), ra, flank_pts)
    h = half(R)
    pts = []
    for k in range(z):
        c = np.radians(phase) + 2 * np.pi * k / z
        # root -> right flank up -> tip arc -> left flank down
        if rf < rb:
            pts.append((rf, c - h[0]))
        pts += [(Ri, c - hi) for Ri, hi in zip(R, h)]
        pts += [(ra, c + t) for t in np.linspace(-h[-1], h[-1], 4)[1:-1]]
        pts += [(Ri, c + hi) for Ri, hi in zip(R[::-1], h[::-1])]
        if rf < rb:
            pts.append((rf, c + h[0]))
        # root arc to the next tooth
        a0, a1 = c + h[0], c + 2 * np.pi / z - h[0]
        pts += [(rf, t) for t in np.linspace(a0, a1, 5)[1:-1]]
    P = np.array([[Ri * np.cos(t), Ri * np.sin(t)] for Ri, t in pts])
    return P, {"module": m, "teeth": z, "pitch_radius": r, "base_radius": rb, "tip_radius": ra, "root_radius": rf,
               "pressure_angle": pressure_angle}


def gear_mesh_check(z1, z2, module, centre_distance, pressure_angle=20.0):
    """Two standard spur gears: ideal centre distance a = m (z1 + z2) / 2 and the contact ratio
    eps = (sqrt(ra1^2 - rb1^2) + sqrt(ra2^2 - rb2^2) - a sin(alpha)) / (pi m cos(alpha)); needs eps >= 1.2."""
    al = np.radians(pressure_angle)
    a0 = module * (z1 + z2) / 2
    r1, r2 = module * z1 / 2, module * z2 / 2
    ra1, ra2 = r1 + module, r2 + module
    rb1, rb2 = r1 * np.cos(al), r2 * np.cos(al)
    a = float(centre_distance)
    eps = (np.sqrt(ra1 ** 2 - rb1 ** 2) + np.sqrt(ra2 ** 2 - rb2 ** 2) - a * np.sin(al)) / (np.pi * module * np.cos(al))
    return {"ideal_centre_distance_mm": round(a0, 3), "centre_distance_mm": round(a, 3),
            "error_mm": round(a - a0, 3), "contact_ratio": round(float(eps), 3),
            "ok": bool(abs(a - a0) <= 0.05 * module and eps >= 1.2)}
