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


def test_see_inside():
    """7. Section cut, X-ray and explode reach the hologram: a part hidden inside a shell becomes visible."""
    from engine import lab
    st = lab.default_state()
    lab.build_assembly(st, "box in a ball", [
        {"name": "shell", "type": "sphere", "params": {"radius": 30}},
        {"name": "core", "type": "box", "params": {"w": 12, "d": 12, "h": 12}}], position=(0, 0, 60))

    def core_visible():
        P, owner, vis = lab._samples(st)
        names = [p["name"] for p, V, F in lab.geometry.scene_meshes(lab.cutaway.view_parts(st))]
        k = names.index("core")
        return int((vis & (owner == k)).sum()), P
    hidden, _ = core_visible()
    lab.set_view(st, section="z", section_mm=64)          # the desk viewer looks down, so cut the top off
    cut, P = core_visible()
    lab.set_view(st, section="off", xray=True)
    xray, _ = core_visible()
    lab.set_view(st, xray=False, explode=1)
    off = lab.explode_offsets(st)
    print(f"  core points seen from the eye: closed {hidden}, cut {cut} (all z <= 64: {bool((P[:, 2] <= 64 + 1e-9).all())}), x-ray {xray}; "
          f"explode moves {sum(1 for v in off.values() if any(abs(c) > 1 for c in v))} parts")
    assert hidden == 0 and cut > 20 and xray > 20 and (P[:, 2] <= 64 + 1e-9).all()


def test_desk_score_loop():
    """8. Design loop score: a tall design fails on the desk; moved onto the panel plane it passes."""
    from engine import lab
    st = lab.default_state()
    lab.build_assembly(st, "Tall", [{"name": "Body", "type": "tube", "params": {"outer": 40, "inner": 36, "height": 150}}],
                       position=[0, 0, 110])
    a = lab.desk_score(st)
    root = [p for p in st["parts"] if not p.get("parent")][0]
    lab.update_part(st, root["id"], position=[0, 0, 0])
    b = lab.desk_score(st)
    print(f"  at z 110: {a['min_sharpness_pct']}% pass {a['pass']}; at z 0: {b['min_sharpness_pct']}% pass {b['pass']}")
    assert not a["pass"] and b["pass"] and b["min_sharpness_pct"] > a["min_sharpness_pct"]


def test_photo_silhouette():
    """9. Photo measurements: a 12-tooth gear mask gives 12 lobes, a centre hole and the right size."""
    import vision
    from PIL import Image, ImageDraw
    im = Image.new("L", (400, 400), 0)
    d = ImageDraw.Draw(im)
    pts = [(200 + (180 if i % 4 in (0, 1) else 150) * np.cos(i / 48 * 2 * np.pi),
            200 + (180 if i % 4 in (0, 1) else 150) * np.sin(i / 48 * 2 * np.pi)) for i in range(48)]
    d.polygon(pts, fill=255)
    d.ellipse([160, 160, 240, 240], fill=0)
    m = vision.measure(np.asarray(im) > 127, size_mm=72)
    print(f"  lobes {m['lobes_around_centre']}, hole {m['centre_hole']} r {m['centre_hole_radius_mm']} mm, size {m['width_mm']} mm")
    assert m["lobes_around_centre"] == 12 and m["centre_hole"] and abs(m["width_mm"] - 72) < 1 and 6 < m["centre_hole_radius_mm"] < 10


def test_relative_sharpness_metric():
    """10. Sharpness metric: a 1D desk point on the panel is ~100% of full 2D; it drops with astigmatism."""
    on = eye.relative_sharpness(0.7, 0.7, 0.8 * eye.ARCMIN * 0.7)
    off = eye.relative_sharpness(0.7, 1 / (1 / 0.7 + 0.5), 0.8 * eye.ARCMIN * 0.7)
    D, d, ok = eye.line_of_sight([[0, 0, 0], [0, 0, 80]], [0, -450, 540])
    print(f"  on panel {on:.0%}, 0.5 D astigmatism {off:.0%}; oblique eye: point 80 mm up is {d[1]-D[1]:.3f} m "
          f"in front of the panel along the line of sight")
    assert on > 0.95 and off < on and ok.all() and abs(d[0] - D[0]) < 1e-9 and d[1] > D[1]


def test_outline_watertight():
    """11. Drawing outline -> closed solid: a plate with a hole has no open edges and the right volume."""
    from engine import outline
    yy, xx = np.mgrid[:200, :200]
    m = ((abs(xx - 100) < 80) & (abs(yy - 100) < 60)) & ~((xx - 100) ** 2 + (yy - 100) ** 2 < 30 ** 2)
    polys = outline.mask_polygons(m, 0.5, (100, 100), eps_px=0.7, min_area_px=20)
    V, F = outline.extrude(polys[0]["outer"], polys[0]["holes"], 5.0)
    V, F = np.asarray(V), np.asarray(F)
    _, idx = np.unique(np.round(V, 4), axis=0, return_inverse=True)   # walls and caps carry their own vertices
    G = idx.ravel()[F]
    e = np.sort(np.concatenate([G[:, [0, 1]], G[:, [1, 2]], G[:, [2, 0]]]), 1)
    _, c = np.unique(e, axis=0, return_counts=True)
    vol = abs(np.einsum("ij,ij->i", V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum() / 6)
    want = (80 * 60 - np.pi * 15 ** 2) * 5
    print(f"  open edges {(c != 2).sum()}, volume {vol:.0f} mm3 vs {want:.0f}")
    assert (c != 2).sum() == 0 and abs(vol / want - 1) < 0.03   # pixel outline of the hole


def test_involute_mesh():
    """12. Involute gears: z20/z30 m2 at 50 mm centres have contact ratio > 1.2 and their teeth do not overlap."""
    from engine import geometry, rebuild
    chk = geometry.gear_mesh_check(20, 30, 2, 50)
    ph = rebuild.mesh_phase(0.0, 20, 30, 0.0)
    # rasterise both gears at the mesh phase: tooth areas must not overlap
    from engine.geometry import gear_profile
    def raster(z, phase, cx):
        from PIL import Image, ImageDraw
        im = Image.new("1", (1200, 800), 0)
        pts = gear_profile(z, 2.0, 20.0, phase)[0]
        ImageDraw.Draw(im).polygon([(600 + 10 * (x + cx - 25), 400 - 10 * y) for x, y in pts], fill=1)
        return np.asarray(im)
    over = (raster(20, 0.0, 0) & raster(30, ph, 50)).sum() / 100
    print(f"  contact ratio {chk['contact_ratio']}, gear 2 phase {ph:.2f} deg, tooth overlap {over:.2f} mm2")
    assert chk["contact_ratio"] > 1.2 and chk["ok"] and over < 0.5


def test_rebuild_synthetic():
    """13. Drawing rebuild: frame + two meshing gears + pin + link + spring become a layered 3D mechanism that
    stands upright, fits the sharp zone and passes the desk score (synthetic drawing, no network)."""
    import vision
    from engine import rebuild, lab
    import agent
    from tests.synth_drawing import drawing
    im, objs, mmpx = drawing()
    info, _ = vision.blueprint_parts(im, ["gear"], objs=objs, mm_per_px=mmpx, scale_source="test")
    specs, rep = rebuild.rebuild(info["parts"], info["drawing_mm"])
    st = lab.default_state()
    lab.build_assembly(st, "M", specs, position=[0, 0, 0], rotation=[90, 0, 0])
    fit = agent._fit_to_desk(st, st["selected"])
    sc = lab.desk_score(st)
    pairs = rep["gear_pairs"]
    print(f"  gear pairs {[(p.get('teeth'), p.get('contact_ratio')) for p in pairs]}, scale {fit['scale']}, "
          f"desk worst {sc['min_sharpness_pct']}% pass {sc['pass']}")
    gears = [s for s in specs if s["type"] == "gear"]
    assert len(gears) == 2 and pairs and all(p["contact_ratio"] > 1.2 for p in pairs)
    assert {s["eng"]["kind"] for s in specs} >= {"gear", "pin", "frame"} and sc["pass"]


def json_short(x):
    import json
    return json.dumps(x, default=str)[:160]


def test_wave_matches_eye_model():
    """14. 1D desk wave simulation (complex modulation) matches the analytic eye model within 2%."""
    from engine import desk_wave
    for D, d in ((0.7, 0.7), (0.62, 0.7)):
        F = 2 / (1 / D + 1 / d)
        dth = eye.DTH
        prof = desk_wave.point_psf(D, d, F, pitch=34.6e-6, dth=dth)
        marg = eye.psf(d, D, F).sum(1)
        a, b = desk_wave.mtf_1d(prof, dth), desk_wave.mtf_1d(marg / marg.sum(), dth)
        print(f"  point {D} m, panel {d} m: wave {a:.3f}, eye model {b:.3f}")
        assert abs(a - b) < 0.02 * max(b, 0.1) + 0.01


def test_three_view_hull():
    """15. Three-view drawing -> solid: an L-bracket's visual hull has the right size and volume and is closed."""
    from PIL import Image, ImageDraw
    from engine import hull
    S = 4
    def view(w, h, rects):
        im = Image.new("L", (w * S + 80, h * S + 80), 255)
        d = ImageDraw.Draw(im)
        for x0, y0, x1, y1 in rects:
            d.rectangle([40 + x0 * S, 40 + y0 * S, 40 + x1 * S, 40 + y1 * S], fill=0)
        return im
    front = view(60, 50, [(0, 0, 60, 50)])
    top = view(60, 40, [(0, 0, 60, 40)])
    side = view(40, 50, [(0, 40, 40, 50), (30, 0, 40, 50)])
    V, F, rep = hull.three_view(front, top, side, 60)
    vol = abs(np.einsum("ij,ij->i", V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum() / 6)
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), 1)
    _, c = np.unique(e, axis=0, return_counts=True)
    print(f"  size {rep['size_mm']} mm, volume {vol:.0f} mm3 (true 48000), open edges {(c != 2).sum()}")
    assert all(abs(a - b) < 1.5 for a, b in zip(rep["size_mm"], (60, 40, 50)))
    assert abs(vol / 48000 - 1) < 0.05 and (c != 2).sum() == 0


def test_retina_full2d_is_100():
    """16. Simulated retina: a full 2D hologram scores 100% against itself; the 1D desk scores less where the eye
    is focused. (A layer the eye is NOT focused on can score above 100%: the desk's horizontal stays focused at
    the panel, which may be nearer the eye's focus than the defocused 2D image. That is physics, not a bug.)"""
    from engine import lab, retina
    st = lab.default_state()
    lab.add_part(st, "box", {"w": 40, "d": 40, "h": 2}, "Plate", position=[0, 0, 60])
    full = retina.retina(st, focus_z_mm=60, display="full2d", n=240, speckle=False)
    desk = retina.retina(st, focus_z_mm=60, display="desk1d", n=240, speckle=False)
    print(f"  in focus (+-0.25 D): full 2D {full['in_focus_vs_2d']:.1%}, desk 1D {desk['in_focus_vs_2d']:.1%} "
          f"({desk['in_focus_share']:.0%} of the image in focus)")
    assert abs(full["in_focus_vs_2d"] - 1) < 0.005 and abs(full["sharpness_vs_2d"] - 1) < 0.005
    assert desk["in_focus_vs_2d"] < 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print(name, "-", fn.__doc__.strip())
            fn()
            print("  PASS")
