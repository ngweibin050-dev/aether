"""Physics checks for the AETHER Lab engine. Run: python -m tests.test_physics"""
import numpy as np

from engine import optics, measure, eye

GRID = optics.Grid(n=512, pitch=8e-6, wavelength=532e-9)


def test_single_point_focuses():
    """1. A single light point must focus back to one point at the right distance."""
    z = 0.05
    holo = optics.phase_only(optics.point_hologram([[0.2e-3, -0.3e-3, z]], GRID))
    rc = GRID.to_index(0.2e-3, -0.3e-3)
    zs = np.linspace(0.04, 0.06, 21)
    stack = optics.focus_sweep(holo, zs, GRID)
    z_best, _ = measure.best_depth(stack, zs, rc)
    i = stack[10]
    peak = np.unravel_index(np.argmax(i), i.shape)
    energy = measure.energy_near(i, rc, radius=2)
    print(f"  focus at {z_best*100:.2f} cm (target 5.00), peak pixel {peak} vs {rc}, "
          f"energy in 5x5 px {energy:.0%}")
    assert abs(z_best - z) <= 0.001
    assert abs(peak[0] - rc[0]) <= 1 and abs(peak[1] - rc[1]) <= 1
    assert energy > 0.3


def test_two_depths():
    """2. Two points at different depths: each is sharp only at its own depth."""
    pts = [[-0.5e-3, 0, 0.04], [0.5e-3, 0, 0.07]]
    holo = optics.phase_only(optics.point_hologram(pts, GRID))
    zs = np.linspace(0.03, 0.08, 51)
    stack = optics.focus_sweep(holo, zs, GRID)
    za, va = measure.best_depth(stack, zs, GRID.to_index(-0.5e-3, 0))
    zb, vb = measure.best_depth(stack, zs, GRID.to_index(0.5e-3, 0))
    # how much point A dims when the eye focuses on B's depth
    a_at_b = va[int(np.argmin(np.abs(zs - 0.07)))] / max(va)
    print(f"  point A sharp at {za*100:.1f} cm (4.0), point B at {zb*100:.1f} cm (7.0); "
          f"A at B's depth keeps {a_at_b:.1%} of its peak")
    assert abs(za - 0.04) <= 0.001 and abs(zb - 0.07) <= 0.001
    assert a_at_b < 0.05


def test_pixel_size_sets_bending():
    """3. Halving the pixel size doubles how far light can bend; past the limit the light goes the wrong way."""
    fine = optics.Grid(512, 8e-6, 532e-9)
    coarse = optics.Grid(512, 16e-6, 532e-9)
    ratio = np.sin(fine.max_angle) / np.sin(coarse.max_angle)
    target = 0.8 * fine.max_angle                  # 80 % of the fine grid's limit
    found = {}
    for name, g in (("8 um", fine), ("16 um", coarse)):
        X, _ = g.coords()
        tilt = np.exp(1j * g.k * X * np.sin(target))  # hologram that should bend light by `target`
        far = np.abs(np.fft.fftshift(np.fft.fft2(tilt))) ** 2
        f = np.fft.fftshift(np.fft.fftfreq(g.n, d=g.pitch))
        col = np.unravel_index(np.argmax(far), far.shape)[1]
        found[name] = np.degrees(np.arcsin(f[col] * g.wavelength))
    want = np.degrees(target)
    print(f"  max bend ratio {ratio:.3f} (expect 2); asked for {want:.2f} deg: "
          f"8 um pixels send light to {found['8 um']:.2f} deg, 16 um pixels to {found['16 um']:.2f} deg")
    assert abs(ratio - 2) < 0.01
    assert abs(found["8 um"] - want) < 0.02
    assert abs(found["16 um"] - want) > 0.5


def test_eye_model_desk():
    """4. Eye model: full 2D hologram ~0.855 at 15 c/deg; 1D desk loses sharpness with height."""
    near = eye.desk_sharpness(0.05)
    far = eye.desk_sharpness(0.15)
    print(f"  2D reference {near['mtf_2d']:.3f}; desk at +5 cm {near['relative']:.0%}, "
          f"+15 cm {far['relative']:.0%}; eye box at 45 um pitch {eye.eye_box(45e-6)*1e3:.1f} mm")
    assert 0.80 < near["mtf_2d"] < 0.90
    assert near["relative"] > far["relative"]


def test_wrp_matches_direct():
    """5. Fast WRP hologram focuses a point as well as the direct method (same depth, same pixel)."""
    z = 0.05
    pts = np.array([[0.2e-3, -0.3e-3, z]])
    rc = GRID.to_index(0.2e-3, -0.3e-3)
    out = {}
    for name, f in (("direct", optics.point_hologram), ("wrp", optics.wrp_hologram)):
        holo = optics.phase_only(f(pts, GRID, phases=[0.0]))
        zs = np.linspace(0.045, 0.055, 11)
        z_best, _ = measure.best_depth(optics.focus_sweep(holo, zs, GRID), zs, rc)
        out[name] = (z_best, measure.energy_near(optics.reconstruct(holo, z, GRID), rc, 2))
    print(f"  direct: focus {out['direct'][0]*100:.2f} cm, {out['direct'][1]:.0%} in spot; "
          f"wrp: focus {out['wrp'][0]*100:.2f} cm, {out['wrp'][1]:.0%} in spot")
    assert abs(out["wrp"][0] - z) <= 0.0005 and out["wrp"][1] > 0.3


def test_window_law_and_hand():
    """6. Window Law: a point is visible only through the panel; a hand behind a point causes a depth conflict."""
    from engine import window
    eye = [0, 0, 700]
    inside = window.window_mask(np.array([[100, 50, 80]]), eye, 598, 336)[0]
    outside = window.window_mask(np.array([[400, 0, 100]]), eye, 598, 336)[0]
    nat, con = window.hand_check(np.array([[0, 0, 80]]), eye, [[0, 0, 40]], 10)     # hand under the point
    nat2, con2 = window.hand_check(np.array([[0, 0, 80]]), eye, [[0, 0, 150]], 10)  # hand above the point
    print(f"  inside window: {inside}, outside: {outside}; hand behind point -> conflict {con[0]}, "
          f"hand in front -> natural {nat2[0]}")
    assert inside and not outside and con[0] and not nat[0] and nat2[0] and not con2[0]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print(name, "-", fn.__doc__.strip())
            fn()
            print("  PASS")
