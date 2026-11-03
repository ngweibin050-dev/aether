"""Physics checks for the AETHER Lab engine. Run: python -m tests.test_physics"""
import time

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
    lab.clear_scene(st)                   # a scene with only this design
    lab.build_assembly(st, "box in a ball", [
        {"name": "shell", "type": "sphere", "params": {"radius": 30}},
        {"name": "core", "type": "box", "params": {"w": 12, "d": 12, "h": 12}}], position=(0, 0, 30))   # bottom at 30: centre 60

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
    lab.clear_scene(st)                   # a scene with only this design
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
    lab.clear_scene(st)                   # a scene with only this design
    lab.build_assembly(st, "M", specs, position=[0, 0, 0], rotation=[90, 0, 0])
    fit = agent._fit_to_desk(st, st["selected"])
    sc = lab.desk_score(st)
    pairs = rep["gear_pairs"]
    print(f"  gear pairs {[(p.get('teeth'), p.get('contact_ratio')) for p in pairs]}, scale {fit['scale']}, "
          f"desk worst {sc['min_sharpness_pct']}% pass {sc['pass']}, depth/width {sc['depth_ratio']}")
    gears = [s for s in specs if s["type"] == "gear"]
    assert len(gears) == 2 and pairs and all(p["contact_ratio"] > 1.2 for p in pairs)
    assert {s["eng"]["kind"] for s in specs} >= {"gear", "pin", "frame", "hub"} and sc["pass"]
    assert sc["depth_ratio"] >= 0.3, "rebuilt mechanism is still flat"


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


def test_phase_only_pupil_gs():
    """17. One phase-only panel, solved for the tracked pupil band (pupil-GS), matches complex modulation within 2%
    for a point on and in front of the panel; naive kinoform / double-phase do not."""
    from engine import desk_wave
    for D, d in ((0.7, 0.7), (0.62, 0.7)):
        F = 2 / (1 / D + 1 / d)
        a = desk_wave.mtf_1d(desk_wave.point_psf(D, d, F, pitch=34.6e-6, encode="pupil_gs", dth=eye.DTH), eye.DTH)
        c = desk_wave.mtf_1d(desk_wave.point_psf(D, d, F, pitch=34.6e-6, encode="none", dth=eye.DTH), eye.DTH)
        k = desk_wave.mtf_1d(desk_wave.point_psf(D, d, F, pitch=34.6e-6, encode="phase", dth=eye.DTH), eye.DTH)
        print(f"  point {D} m: complex {c:.3f}, pupil-GS {a:.3f}, kinoform {k:.3f}")
        assert abs(a - c) < 0.02 and k < 0.5 * c


def test_inflate_solid():
    """18. Inflated outline: a lever outline becomes a rounded solid as thick as asked, with its holes kept."""
    from engine import geometry
    th = np.linspace(0, 2 * np.pi, 40, endpoint=False)
    outer = [[x, 8] for x in np.linspace(0, 100, 20)] + [[100 + 8 * np.cos(a), 8 * np.sin(a)] for a in np.linspace(np.pi / 2, -np.pi / 2, 15)] \
        + [[x, -8] for x in np.linspace(100, 0, 20)] + [[8 * np.cos(a), 8 * np.sin(a)] for a in np.linspace(-np.pi / 2, -3 * np.pi / 2, 15)]
    holes = [[[4 * np.cos(a), 4 * np.sin(a)] for a in th[::-1]], [[100 + 4 * np.cos(a), 4 * np.sin(a)] for a in th[::-1]]]
    V, F = geometry.inflate([{"outer": outer, "holes": holes}], 10)
    near_hole = np.hypot(V[:, 0], V[:, 1]) < 3
    print(f"  size {np.ptp(V, axis=0).round(1)} mm, vertices inside the hole: {int(near_hole.sum())}")
    assert abs(np.ptp(V[:, 2]) - 10) < 1.5 and abs(np.ptp(V[:, 0]) - 116) < 3 and not near_hole.any()


def test_interpret_read():
    """19. Engineer's interpretation: a drawing reading (types, boxes, axis ends) becomes clean standard parts -
    gears, a spoked wheel, forged links, cylinders - in a housing with real depth that passes the desk score."""
    from engine import interpret, rebuild, lab
    import agent
    box = lambda cx, cy, r: [cx - r, cy - r, cx + r, cy + r]
    read = [{"label": "housing", "type": "frame", "box": [150, 330, 1450, 1160]},
            {"label": "gear A", "type": "gear", "box": box(590, 650, 90), "teeth": 40},
            {"label": "gear B", "type": "gear", "box": box(395, 1040, 75), "teeth": 30},
            {"label": "flywheel", "type": "wheel", "box": box(1390, 480, 90)},
            {"label": "drive arm", "type": "arm", "box": [720, 470, 1400, 660], "ends": [[730, 650], [1390, 480]]},
            {"label": "cylinder", "type": "cylinder", "box": [650, 400, 750, 650], "ends": [[700, 410], [700, 640]]},
            {"label": "pivot", "type": "pin", "box": box(730, 650, 18)}]
    parts = interpret.parts_from_read(read, 1600, 1600, 300 / 1600)
    specs, rep = rebuild.rebuild(parts, (300, 300))
    st = lab.default_state()
    lab.clear_scene(st)                   # a scene with only this design
    lab.build_assembly(st, "M", specs, position=[0, 0, 0], rotation=[90, 0, 0])
    agent._fit_to_desk(st, st["selected"])
    sc = lab.desk_score(st)
    kinds = sorted({s["eng"]["kind"] for s in specs})
    arm = next(p for p in parts if p["label"] == "drive arm")
    print(f"  kinds {kinds}; arm {arm['length_mm']} mm at {arm['angle_deg']} deg; depth/width {sc['depth_ratio']}, "
          f"desk worst {sc['min_sharpness_pct']}% pass {sc['pass']}")
    assert {"gear", "wheel", "link", "piston", "pin", "frame", "hub"} <= set(kinds)
    assert abs(arm["angle_deg"] - 14.4) < 1 and sc["depth_ratio"] >= 0.3 and sc["pass"]



def test_frame_clear_of_parts():
    """20. A base strip drawn behind a gear (as SAM traces it) must not become a slab through the gear: the frame
    body is cut clear of every part's silhouette (0 mm2 overlap), and the built-vs-drawing check runs."""
    from PIL import Image, ImageDraw
    from engine import interpret, rebuild
    read = [{"label": "gear", "type": "gear", "box": [500, 900, 800, 1200], "teeth": 24},
            {"label": "arm", "type": "lever", "box": [700, 400, 1300, 700], "ends": [[720, 680], [1280, 420]]},
            {"label": "base frame", "type": "base", "box": [100, 1100, 1500, 1400]}]
    parts = interpret.parts_from_read(read, 1600, 1600, 300 / 1600)
    specs, rep = rebuild.rebuild(parts, (300, 300))
    im = Image.new("RGB", (1600, 1600), "white")
    d = ImageDraw.Draw(im)
    d.ellipse([500, 900, 800, 1200], outline="black", width=6)
    d.rectangle([100, 1100, 1500, 1400], outline="black", width=6)
    check, _ = interpret.drawing_check(im, rep.pop("_silhouette"), 300 / 1600)
    built = [p["built_as"] for p in rep["parts"] if p["built_as"].startswith("frame")]
    print(f"  {built}; frame/part overlap {rep['checks']['frame_part_overlap_mm2']} mm2; lines on built parts "
          f"{check['drawing_lines_on_built_parts_pct']}% (recall); built outlines on ink {check['outline_on_ink_pct']} (precision)")
    assert rep["checks"]["frame_part_overlap_mm2"] == 0 and "base block" in built[0]
    assert check["drawing_lines_on_built_parts_pct"] > 80
    # precision catches what recall cannot: the arm is built but not drawn in this image, so the parts' outlines
    # mostly lie on blank paper (recall stays high because the frame covers the drawn lines)
    bk = check["outline_on_ink_by_kind_pct"]
    print(f"  precision by kind: { {k: v['pct'] for k, v in bk.items()} }")
    assert bk["link"]["pct"] < 10 and bk["link"]["px"] > 500          # the undrawn arm is caught
    # the gear keeps its drawn size: tip 28.1 mm needs module 2.16, no ISO 54 module within 3 % -> kept measured
    assert bk["gear"]["pct"] > 80



def test_modal_engine_mismatch():
    """21. Modal redeploys ONLY when its engine fingerprint differs from this computer's. An old engine copy: the
    server redeploys and retries on Modal (never a local CPU result); if the redeploy fails the user gets an error.
    A bad tool argument, or a tool error on the current engine, comes back as a clear error and deploys nothing."""
    import os
    import agent
    import compute
    from engine import lab
    old = os.environ.get("AETHER_COMPUTE")
    os.environ["AETHER_COMPUTE"] = "modal"

    class F:
        def __init__(self, fn):
            self.fn = fn

        def remote(self, *a):
            return self.fn(*a)
    new_ping = F(lambda: {"backend": "cupy-gpu", "engine": compute.LOCAL_ENGINE})
    new_run = F(lambda st, n, a: (dict(lab.run(st, n, a), _backend="test"), st))
    calls = []

    def fake_deploy(ok):
        def d():
            calls.append(ok)
            if not ok:
                return "modal: not logged in"
            compute._remote.update(ping=new_ping, run_tool=new_run)
            compute.check()
            return None
        return d
    saved = dict(compute._remote), dict(compute.status), compute.deploy
    try:
        local_runs = []
        real_local = compute._local
        compute._local = lambda *a: local_runs.append(a) or real_local(*a)
        st = lab.default_state()
        lab.run(st, "add_part", {"type": "inflate", "params": {"polygons": [{"outer": [[0, 0], [40, 0], [40, 20], [0, 20]], "holes": []}], "thickness": 8}})
        # a. old engine, redeploy fails -> error, no CPU run
        compute._remote.update(ping=F(lambda: "cupy-gpu"), run_tool=F(lambda st, n, a: ({"error": "KeyError: 'inflate'"}, st)))
        compute.deploy = fake_deploy(False)
        compute.check()
        assert compute.status["stale"]                       # an old deploy has no fingerprint at all
        r = compute.run(st, "desk_score", {})
        assert "error" in r and "_ran_on" not in r
        # b. old engine noticed after a remote error: the re-ping shows another fingerprint -> redeploy, retry on Modal
        compute.status.update(stale=False, checked=time.time())
        compute.deploy = fake_deploy(True)
        r2 = compute.run(st, "desk_score", {})
        assert r2["_ran_on"] == "modal" and not compute.status["stale"] and calls == [False, True] and not local_runs
        # c. a bad argument from the model: a clear error, no remote call, no deploy
        remote_calls = []
        compute._remote["run_tool"] = F(lambda st, n, a: remote_calls.append(n) or (dict(lab.run(st, n, a), _backend="test"), st))
        r3 = compute.run(st, "eye_view", {"focus_mm": 20})
        r4 = compute.run(st, "eye_view", {"focus_z_mm": "high"})
        assert r3.get("error_kind") == "bad_args" and "focus_mm" in r3["error"] and "focus_z_mm" in r3["error"]
        assert r4.get("error_kind") == "bad_args" and not remote_calls and calls == [False, True]
        # d. a real tool error on the current engine (same fingerprint): returned as is, no deploy
        compute._remote["run_tool"] = F(lambda st, n, a: ({"error": "TypeError: unsupported operand"}, st))
        r5 = compute.run(st, "desk_score", {})
        print(f"  old engine, deploy fails -> error; deploy ok -> {r2['_ran_on']}; bad argument -> \"{r3['error'][:60]}...\"; "
              f"tool error, same engine -> deploys {len(calls) - 2}")
        assert "TypeError" in r5["error"] and calls == [False, True] and not local_runs
        compute._local = real_local
        # every argument the agent's tool schemas offer is one the engine accepts
        import inspect
        for d in agent.TOOL_DEFS:
            n, props = d["function"]["name"], d["function"]["parameters"]["properties"]
            if n in lab.TOOLS:
                assert not [k for k in props if k not in inspect.signature(lab.TOOLS[n]).parameters], (n, props)
    finally:
        compute._remote.clear(); compute._remote.update(saved[0]); compute.status.update(saved[1]); compute.deploy = saved[2]
        if old is None:
            os.environ.pop("AETHER_COMPUTE", None)
        else:
            os.environ["AETHER_COMPUTE"] = old



def test_ground_line_rule():
    """25. A ground line under a view is not part of the object and is erased; a part's own flat bottom edge stays.
    The line counts as ground only if it runs past the object's outline (measured just above it) on at least one side."""
    import numpy as np
    from engine import views as sheet
    # a: a body on two wheels standing on a ground line that runs past the body on the right
    m = np.zeros((120, 400), bool)
    m[20:22, 40:300] = m[60:62, 40:300] = m[20:62, 40:42] = m[20:62, 298:300] = True             # body outline
    yy, xx = np.mgrid[:120, :400]
    for cx in (90, 250):
        m |= np.abs(np.hypot(yy - 80, xx - cx) - 18) < 1.5                                       # wheels
    m[98:100, 30:380] = True                                                                     # ground line, to x = 380
    out = sheet._drop_ground_under(m)
    assert not out[98:100, 320:380].any() and out[20:62, 40:42].all()          # line gone past the body, body kept
    # b: a plate whose flat bottom edge is the lowest line of the view: kept
    p = np.zeros((120, 400), bool)
    p[30:32, 50:350] = p[90:92, 50:350] = p[30:92, 50:52] = p[30:92, 348:350] = True
    assert sheet._drop_ground_under(p)[90:92, 50:350].all()
    print("  ground line past the body erased, a plate's own bottom edge kept")


def test_clean_edges():
    """27. No pixel staircase reaches a built part: a pixel-traced outline is vectorised into lines and arcs within
    1.5 px of the trace (staircase 0 %), and every part of the synthetic machine (test 13) scores 0 %."""
    import numpy as np
    from engine import geometry, lab, outline as ol, quality, rebuild
    import vision
    from tests.synth_drawing import drawing
    yy, xx = np.mgrid[:240, :300]
    m = ((yy - 120) ** 2 + (xx - 100) ** 2 < 60 ** 2) | ((yy > 40) & (yy < 200) & (xx > 100) & (xx < 260))
    raw = np.asarray(ol.trace(m)[0], float)
    P, dev = ol.vectorize(raw)
    raw_score = quality.staircase([np.r_[np.asarray(ol.simplify(raw.tolist(), 0.0)), raw[:1]]])[0]
    clean_score = quality.staircase([np.r_[P, P[:1]]])[0]
    print(f"  traced circle + rectangle: {len(raw)} px points -> {len(P)} (lines + arc), deviation {dev:.2f} px, "
          f"staircase {raw_score} % -> {clean_score} %")
    assert dev <= 1.5 and clean_score == 0 and raw_score > 5
    im, objs, mmpx = drawing()                         # traced (SAM path): outlines from masks, vectorised
    info, _ = vision.blueprint_parts(im, ["gear"], objs=objs, mm_per_px=mmpx, scale_source="test")
    specs, rep = rebuild.rebuild(info["parts"], info["drawing_mm"])
    st = lab.default_state()
    lab.clear_scene(st)                   # a scene with only this design
    lab.build_assembly(st, "synthetic", specs, position=[0, 0, 0], rotation=[0, 0, 0])
    worst = max(quality.part_staircase(V, F, mmpx)[0] for p, V, F in geometry.scene_meshes(st["parts"]) if p["type"] != "group" and len(F))
    print(f"  synthetic machine: worst part staircase {worst} %, frame outline deviation {rep['checks']['frame_outline_max_dev_mm']} mm")
    assert worst == 0


def test_surface_check():
    """28. 3-D surface check of a delivered mesh (what no view's outline shows): a vertex pushed through a plate is
    counted as a fold and keep_unflipped puts it back."""
    import numpy as np
    from engine import quality
    n = 12
    yy, xx = np.mgrid[:n, :n]
    V0 = np.c_[xx.ravel(), yy.ravel(), np.zeros(n * n)].astype(float)
    q = np.arange(n * n).reshape(n, n)[:-1, :-1].ravel()
    F = np.r_[np.c_[q, q + 1, q + n + 1], np.c_[q, q + n + 1, q + n]]
    V1 = V0.copy()
    V1[5 * n + 5, :2] += 1.6                          # dragged across its neighbours: its triangles turn over
    bad, fixed = quality.folds(V1, F), quality.keep_unflipped(V0, V1, F)
    print(f"  pushed vertex: {bad}; put back {fixed[1]} vertices -> {quality.folds(fixed[0], F)}")
    assert bad["flipped_triangles"] > 0 and quality.folds(fixed[0], F)["flipped_triangles"] == 0


def test_explain_grounded():
    """30. Explain this machine (explain.py, no API): the validator rejects a step naming a part the model does not have
    and a step with a number that is not in the model (an invented 300 mm); a measured size, the tooth counts and the
    ratio computed from them pass; with no scale on the drawing a size in mm must say "model scale, real size unknown"; teeth assumed from the size give "ratio unknown". A first answer with a bad step is retried once; a step still bad is dropped and
    counted. If Muse Image fails, the explanation is still returned, with the reason and no picture."""
    import agent
    import explain
    P = lambda i, n, k, dims=None, joints=None, reason=None: {
        "id": i, "name": n, "type": "cylinder", "eng": {"kind": k, "dims": dims or {}, "joints": joints or [],
                                                        **({"reason": reason} if reason else {})}}
    st = {"parts": [
        P("f1", "housing 1", "frame", {"width_mm": [120.0, "traced"], "thickness_mm": [8.0, "assumed from its size"]}),
        P("s1", "input shaft a", "shaft", {"diameter_mm": [12.0, "traced"]}),
        P("g1", "pinion 3", "gear", {"teeth": [20, "counted"], "module_mm": [2.0, "ISO 54"]}, [{"type": "gear_mesh", "with": "wheel 4"}]),
        P("g2", "wheel 4", "gear", {"teeth": [30, "counted"], "module_mm": [2.0, "ISO 54"]}),
        P("s2", "output shaft b", "shaft", {"diameter_mm": [16.0, "traced"]}),
        P("b1", "bearing", "added", {"bore_mm": [12.0, "engineer: shaft size"]}, reason="a shaft needs a bearing in the wall")]}
    fx = explain.facts(st)
    gp = fx["gear_pairs"]
    assert len(gp) == 1 and (gp[0]["gear_a"], gp[0]["gear_b"], gp[0]["ratio_b_to_a"]) == ("g1", "g2", 1.5)
    # teeth assumed from the size (not counted): no ratio, said so
    st2 = {"parts": [dict(p, eng={**p["eng"], "dims": {**p["eng"]["dims"], "teeth": [p["eng"]["dims"]["teeth"][0], "assumed from the size"]}})
                     if p["id"] == "g2" else p for p in st["parts"]]}
    gp2 = explain.facts(st2)["gear_pairs"][0]
    assert "ratio_b_to_a" not in gp2 and gp2["ratio"].startswith("unknown")
    assert fx["parts"][0]["dims"]["thickness_mm"]["src"] == "guessed" and fx["parts"][0]["dims"]["width_mm"]["src"] == "measured"
    good = {"title": "Gears slow it down", "text": "The 20-tooth pinion drives the 30-tooth wheel. That is a 1.5 to 1 reduction.",
            "parts": ["g1", "g2"], "camera": "front", "explode": False}
    bad_id = dict(good, parts=["g1", "g9"])
    invented = dict(good, text="The housing is 300 mm wide. It holds both shafts.", parts=["f1"])
    errs = explain.validate({"steps": [good, bad_id, invented]}, fx)
    print(f"  validator: good {errs[0]}, bad id {errs[1]}, invented number {errs[2]}")
    assert errs[0] == [] and any("g9" in e for e in errs[1]) and any("300" in e for e in errs[2])
    # a patent drawing has no scale: a size in mm must say "model scale, real size unknown" (or use proportions)
    bare = dict(good, text="The input shaft is 12 mm across. It drives the pinion.", parts=["s1"])
    said = dict(good, text="The input shaft is 12 mm across (model scale, real size unknown). It drives the pinion.", parts=["s1"])
    e_unknown = explain.validate({"steps": [bare, said]}, fx)
    e_known = explain.validate({"steps": [bare]}, explain.facts(st, {"known": True, "source": "read from 2 dimension(s)"}))
    print(f"  no scale: bare mm {e_unknown[0]}, labelled {e_unknown[1]}; scale read: bare mm {e_known[0]}")
    assert fx["scale"]["real_size_known"] is False and any("model scale" in e for e in e_unknown[0])
    assert e_unknown[1] == [] and e_known[0] == []
    base = [dict(good, title=f"Step {k}") for k in "ABCDEF"]
    answers = [{"machine": "reducer", "steps": base + [invented]}, {"machine": "reducer", "steps": base + [bad_id]}]
    calls = []
    real_json, real_post = agent._spark_json, agent._post
    agent._spark_json = lambda content, *a, **k: (calls.append(content) or answers.pop(0), {"calls": 1, "retried": False})
    def no_image(path, body, timeout=120):
        raise TimeoutError("Muse Image did not answer")
    agent._post = no_image
    try:
        r = explain.explain(st, image=None)
    finally:
        agent._spark_json, agent._post = real_json, real_post
    print(f"  explain: {len(r['steps'])} steps kept, rejected {r['rejected_steps']}, retried {r['retried']}, "
          f"illustration {r['illustration']}")
    assert len(calls) == 2 and "300" in calls[1][-1]["text"] and r["retried"]
    assert len(r["steps"]) == 6 and len(r["rejected_steps"]) == 1 and "g9" in str(r["rejected_steps"])
    assert r["illustration"]["data_url"] is None and r["illustration"]["error"]
    assert r["illustration"]["label"] == "AI illustration — concept, not the measured model"


def test_plausible_parts_and_section_gears():
    """31. Rebuild sanity on a one-view reading (no API): a shaft whose traced width is < 1 % of the machine takes its
    box estimate when that is plausible and is dropped when it is not (both listed in report["implausible"]); two gears
    cut edge-on in a section, axes parallel, faces overlapping, axis gap = r1 + r2, are recorded as a meshing pair from
    the geometry, with "ratio unknown" since their teeth were not counted; a pair proposed by the engineer's completion
    is recorded as guessed, with its reason."""
    from engine import rebuild
    base = {"confidence": 1, "angle_deg": 0.0, "interpreted": True}
    P = [dict(base, n=1, label="housing", kind="frame", centre_mm=[0, 0], length_mm=200, width_mm=120, elongation=1.7),
         dict(base, n=2, label="shaft a", kind="shaft", centre_mm=[0, -40], length_mm=150, width_mm=1.2, elongation=125,
              width_source="two drawn sides", width_estimate_mm=10.0),
         dict(base, n=3, label="hairline", kind="shaft", centre_mm=[0, 50], length_mm=80, width_mm=0.9, elongation=89,
              width_source="two drawn sides", width_estimate_mm=1.0),
         dict(base, n=4, label="sun", kind="gear", centre_mm=[-20, 0], length_mm=30, width_mm=10, radius_mm=15,
              tip_radius_mm=15, edge_on=True, face_mm=10, axis_deg=0.0, view_note="section", elongation=3),
         dict(base, n=5, label="planet", kind="gear", centre_mm=[-20, 35], length_mm=40, width_mm=10, radius_mm=20,
              tip_radius_mm=20, edge_on=True, face_mm=10, axis_deg=0.0, view_note="section", elongation=4),
         dict(base, n=6, label="output", kind="gear", centre_mm=[60, 0], length_mm=40, width_mm=12, radius_mm=20,
              tip_radius_mm=20, edge_on=True, face_mm=12, axis_deg=0.0, view_note="section", elongation=3.3)]
    comp = {"gear_pairs": [{"a": 5, "b": 6, "reason": "planet drives the output through the carrier"}]}
    specs, rep = rebuild.rebuild(P, [240, 160], comp)
    acts = {x["label"]: x["action"] for x in rep["implausible"]}
    print(f"  implausible: {rep['implausible']}")
    print(f"  gear pairs: {rep['gear_pairs']}")
    assert acts == {"shaft a": "width from the box estimate", "hairline": "dropped"}
    assert not any("hairline" in s_["name"] for s_ in specs)
    sa = next(s_ for s_ in specs if s_["name"].startswith("shaft a"))
    assert sa["params"]["radius"] == 5.0 and "estimated from the box" in sa["eng"]["dims"]["diameter_mm"][1]
    src = {(g["a"], g["b"]): g for g in rep["gear_pairs"]}
    assert src[(4, 5)]["source"].startswith("geometry: edge-on") and src[(4, 5)]["ratio"].startswith("unknown")
    assert src[(5, 6)]["source"].startswith("guessed by Muse Spark") and "carrier" in src[(5, 6)]["source"]
    assert (4, 6) not in src and (6, 4) not in src                     # far apart: no pair
    sun = next(s_ for s_ in specs if s_["name"].startswith("sun"))
    assert any(j["type"] == "gear_mesh" and "geometry" in j["source"] for j in sun["eng"]["joints"])


def test_models_stand_on_base():
    """32. Every build route leaves the model standing on the display surface: the lowest point of the whole group is
    at z = 0 (within 0.1 mm), x / y as built. Routes: text-to-CAD (a 160 mm motor built around its origin, which used to
    sink half through the surface), text-to-CAD asked to float 100 mm up (its lowest point at 100), an imported mesh,
    a three-view sheet; a drawing rebuild stood upright and fitted to the desk stands on it too, unless it is taller than
    the sharp zone above the surface: then it is centred in the zone and the fit says why part of it is behind it."""
    import io
    import numpy as np
    from PIL import Image, ImageDraw
    import agent
    import vision
    from engine import geometry, lab, rebuild
    from tests.synth_drawing import drawing
    def bottom(st):                                    # the model just built (the default scene has others)
        g = lab._find(st, st["selected"])
        while g.get("parent"):
            g = lab._find(st, g["parent"])
        return float(geometry.bounds(lab.subtree(st, g["id"]))[0][2])
    got = {}
    st = lab.default_state()
    lab.clear_scene(st)                   # a scene with only this design
    lab.build_assembly(st, "motor", [{"type": "cylinder", "name": "stator", "params": {"radius": 60, "height": 160}},
                                     {"type": "cylinder", "name": "shaft", "params": {"radius": 8, "height": 220}}])
    got["text-to-CAD"] = bottom(st)
    st = lab.default_state()
    lab.clear_scene(st)                   # a scene with only this design
    lab.build_assembly(st, "motor", [{"type": "box", "name": "b", "params": {"w": 40, "d": 40, "h": 40}}], position=[0, 0, 100])
    got["text-to-CAD, 100 mm up"] = bottom(st) - 100
    st = lab.default_state()
    V = np.array([[x, y, z] for x in (-20, 20) for y in (-20, 20) for z in (-30, 30)], float)
    F = [[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]]
    lab.import_mesh(st, "box", V.ravel().tolist(), np.array(F).ravel().tolist(), size_mm=0)
    got["mesh import"] = bottom(st)
    dim, objs, mmpx = drawing()
    info, _ = vision.blueprint_parts(dim, ["gear"], objs=objs, mm_per_px=mmpx, scale_source="test")
    specs, rep = rebuild.rebuild(info["parts"], info["drawing_mm"])
    st = lab.default_state()
    lab.clear_scene(st)                   # a scene with only this design
    lab.build_assembly(st, "Machine from drawing", specs, position=[0, 0, 0], rotation=[90, 0, 0])
    fit = agent._fit_to_desk(st, st["selected"])
    below = bottom(st)
    print(f"  lowest point per route (mm): { {k: round(v, 3) for k, v in got.items()} }; drawing rebuild fitted to "
          f"the desk: lowest point {below:.1f} mm, note: {fit.get('note')}")
    assert all(abs(v) <= 0.1 for v in got.values()), got
    # fitted to the desk: on the surface, or (taller than the sharp zone above it) centred in the zone, said so
    assert abs(below) <= 0.1 or (below < 0 and "behind the display surface" in fit["note"] and abs(below - fit["bottom_z_mm"]) <= 0.1)


def test_export_files():
    """33. Export (engine/export.py): the STL holds every visible triangle in millimetres with the scene's bounds; the GLB
    is valid glTF 2.0 (header, JSON + BIN chunks), one node per part, positions in metres with y up, and each node's
    extras carry the part's sizes with their source (measured / assumed); the one-page report lists the parts and
    separates measured from guessed sizes."""
    import json
    import struct
    import numpy as np
    import vision
    from engine import export, geometry, lab, rebuild
    from tests.synth_drawing import drawing
    im, objs, mmpx = drawing()
    info, _ = vision.blueprint_parts(im, ["gear"], objs=objs, mm_per_px=mmpx, scale_source="test")
    specs, rep = rebuild.rebuild(info["parts"], info["drawing_mm"])
    st = lab.default_state()
    lab.clear_scene(st)                   # a scene with only this design
    lab.build_assembly(st, "synthetic", specs, rotation=[90, 0, 0])
    meshes = [(p, V, F) for p, V, F in geometry.scene_meshes(st["parts"]) if p["type"] != "group" and len(F)]
    lo, hi = geometry.bounds(st["parts"])
    b = export.stl(st)
    n = struct.unpack("<I", b[80:84])[0]
    T = np.frombuffer(b[84:], dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])["v"].reshape(-1, 3)
    assert n == sum(len(F) for _, _, F in meshes) and len(b) == 84 + 50 * n
    assert np.allclose(T.min(0), lo, atol=0.01) and np.allclose(T.max(0), hi, atol=0.01)
    g = export.glb(st)
    magic, ver, total = struct.unpack("<4sII", g[:12])
    jl, jt = struct.unpack("<I4s", g[12:20])
    doc = json.loads(g[20:20 + jl])
    bl, bt = struct.unpack("<I4s", g[20 + jl:28 + jl])
    assert (magic, ver, total, jt, bt) == (b"glTF", 2, len(g), b"JSON", b"BIN\x00") and bl == doc["buffers"][0]["byteLength"]
    assert len(doc["nodes"]) == len(meshes)
    mx = np.max([doc["accessors"][m["primitives"][0]["attributes"]["POSITION"]]["max"] for m in doc["meshes"]], 0)
    mn = np.min([doc["accessors"][m["primitives"][0]["attributes"]["POSITION"]]["min"] for m in doc["meshes"]], 0)
    assert np.allclose(mx, [hi[0] / 1000, hi[2] / 1000, -lo[1] / 1000], atol=1e-5)      # (x, z, -y) in metres
    assert np.allclose(mn, [lo[0] / 1000, lo[2] / 1000, -hi[1] / 1000], atol=1e-5)
    srcs = [v[1] for nd in doc["nodes"] for v in nd["extras"]["dims"].values() if isinstance(v, list)]
    assert any("assumed" in str(x) for x in srcs) and any("assumed" not in str(x) for x in srcs)
    page = export.report_html(st, {"gear_pairs": rep["gear_pairs"]}, [{"label": "read_drawing", "s": 28.0}])
    assert f"{len(meshes)} parts" in page and "guessed / assumed" in page and "Muse Spark" in page
    assert " × ".join(f"{v:.1f}" for v in (hi - lo)) in page            # world size (the group's rotation applied)
    assert "model scale, real size unknown" in page                      # no dimension read: the report says so
    print(f"  STL {n} triangles ({len(b) / 1e6:.2f} MB), GLB {len(doc['nodes'])} nodes ({len(g) / 1e6:.2f} MB), "
          f"report {len(page) / 1e3:.0f} kB; bounds {np.round(lo, 1)} .. {np.round(hi, 1)} mm")


def test_wonder_fallback():
    """34. The engineer's completion asks Muse Wonder (the reading stays on Muse Spark); when a Muse Wonder call fails, the
    same call is made on Muse Spark and the result says so (meta["model"], meta["fallback"]), and the step label names
    both ("Muse Wonder + Muse Spark (fallback)"). No API: the HTTP call is replaced."""
    import agent
    sent = []
    def fake_post(path, body, timeout=120):
        sent.append(body["model"])
        if body["model"] == "muse-wonder-1.0":
            raise TimeoutError("preview model busy")
        return {"choices": [{"message": {"content": '{"view": "front", "parts": [], "dimensions": []}'}}]}
    real = agent._post
    agent._post = fake_post
    try:
        obj, meta = agent._spark_json("read", None, "t", model="muse-wonder-1.0")
    finally:
        agent._post = real
    print(f"  calls {sent}; answered by {meta['model']}; {meta['fallback']}")
    assert sent == ["muse-wonder-1.0", "muse-spark-1.3"] and meta["model"] == "muse-spark-1.3" and "Muse Wonder failed" in meta["fallback"]
    assert agent.who(["muse-wonder-1.0", "muse-spark-1.3"]) == "Muse Wonder + Muse Spark (fallback)"
    assert agent.who(["muse-wonder-1.0"] * 10) == "Muse Wonder"
    assert agent.READ_MODEL == "muse-spark-1.3" and agent.COMPLETE_MODEL == "muse-wonder-1.0"     # owner's decision, Nov 1


def test_fill_holes_fast():
    """35. Hole filling (outline.fill_holes) gives the same pixels as the plain flood from the border on 500 random
    masks, and fills a 1200 x 950 frame with a long winding pocket in well under a second: the per-pixel flood took
    2.8-5.3 s per frame on C's frames (four per rebuild), which made C's rebuild 4 s -> 17-38 s after Part A."""
    import time
    import numpy as np
    from engine import outline as ol
    rng = np.random.default_rng(0)
    for _ in range(500):
        m = rng.random(tuple(rng.integers(1, 60, 2))) < rng.uniform(0.1, 0.8)
        assert np.array_equal(ol.fill_holes(m), ol.fill_holes_flood(m))
    m = np.zeros((950, 1200), bool)
    m[5:945, 5:1195] = True
    for i in range(20, 1180, 12):                      # a comb: the outside reaches deep between the teeth
        m[(15 if (i // 12) % 2 else 0):(950 if (i // 12) % 2 else 935), i:i + 5] = False
    m[400:420, 600:640] = False                        # ... and one enclosed hole
    t = time.time()
    f = ol.fill_holes(m)
    dt = time.time() - t
    t = time.time()
    g = ol.fill_holes_flood(m)
    dt0 = time.time() - t
    print(f"  500 random masks identical; comb frame: {dt:.2f} s (flood {dt0:.2f} s)")
    assert np.array_equal(f, g) and dt < 1.0


def test_demo_drawings_replayed():
    """36. The demo drawings D and C, rebuilt from their saved Muse Spark readings (no API): outline (recall and parts
    precision against the drawing), surface (no pixel staircase on any part) and time (rebuild < 5 s), at today's
    measured baselines (D run 12: 83.8 / 77.0 %, C run 3: 74.3 / 72.7 %, 0 %, 0.7-1.8 s) with a small margin: a regression
    guard on the real demo inputs. Which fix each threshold needs is shown by the synthetic tests: the staircase by
    test 27 (a raw pixel trace scores > 5 %), the time by test 35 (the old hole fill takes ~9 s on a comb frame; on
    these saved readings it takes only ~3 s, the 16-38 s came with deeper completions). Skipped when the saved runs
    (output/, not in the public repository) are absent."""
    import base64
    import json
    import os
    import time
    from pathlib import Path
    import vision
    from engine import circles, geometry, interpret, lab, quality, rebuild
    from tests.run_reference import INPUTS, OUT
    cases = {"patent_US929594_fig1": ("run12", 80, 75), "heldout_US1770035_fig1": ("run3", 72, 70)}   # min recall, min precision
    if not all((OUT / n / r / "replay.json").exists() for n, (r, _, _) in cases.items()):
        print("  SKIPPED: the saved reference runs are not in this copy")
        return
    for name, (run, min_rec, min_prec) in cases.items():
        rp = json.loads((OUT / name / run / "replay.json").read_text(encoding="utf-8"))
        im = vision.load_image("data:x;base64," + base64.b64encode((Path(__file__).parent / INPUTS[name][0]).read_bytes()).decode(), 1024)
        parts = interpret.parts_from_read(rp["read_parts_px"], *im.size, rp["mm_per_px"], ink=circles.ink_mask(im)[0])
        t = time.time()
        specs, rep = rebuild.rebuild(parts, rp["drawing_mm"], rp.get("completion"), frame_cell_mm=rp["mm_per_px"])
        dt = time.time() - t
        chk, _ = interpret.drawing_check(im, rep.pop("_silhouette"), rp["mm_per_px"])
        st = lab.default_state()
        lab.clear_scene(st)                   # a scene with only this design
        lab.build_assembly(st, "replay", specs, position=[0, 0, 0], rotation=[0, 0, 0])
        worst = max(quality.part_staircase(V, F, rp["mm_per_px"])[0]
                    for p, V, F in geometry.scene_meshes(st["parts"]) if p["type"] != "group" and len(F))
        rec, prec = chk["drawing_lines_on_built_parts_pct"], chk["outline_on_ink_pct"]["parts"]
        print(f"  {name} {run}: rebuild {dt:.1f} s, recall {rec} %, parts precision {prec} %, worst staircase {worst} %")
        assert rec >= min_rec and prec >= min_prec and worst == 0 and dt < 5


def test_machine_reading():
    """A dense one-view machine sheet: circles measured on the ink, close-up readings merged, pins sized by their part."""
    from PIL import Image, ImageDraw
    from engine import circles, interpret, rebuild
    im = Image.new("RGB", (800, 500), "white")
    d = ImageDraw.Draw(im)
    for _ in range(0, 800, 7):                                          # hatching must not count as circles
        d.line([(_, 380), (_ + 60, 480)], fill=(70, 90, 200), width=1)
    rings = [(200, 200, 80), (200, 200, 20), (520, 180, 45), (650, 330, 12), (120, 400, 10)]
    for x, y, r in rings:
        d.ellipse([x - r, y - r, x + r, y + r], outline=(30, 40, 160), width=2)
    found = circles.find(im)
    print(f"  {len(found)} circles: " + ", ".join(f"({c['cx']:.0f},{c['cy']:.0f}) r{c['r']:.0f}" for c in found))
    for x, y, r in [(200, 200, 80), (520, 180, 45), (650, 330, 12), (120, 400, 10)]:
        assert any(abs(c["cx"] - x) <= 3 and abs(c["cy"] - y) <= 3 and abs(c["r"] - r) <= 3 for c in found), (x, y, r)
    big = next(c for c in found if c["r"] > 70)
    assert any(abs(q - 20) <= 3 for q in big["rings"]), big          # the hub ring is the same part
    assert len(found) == 4
    # whole sheet + a close-up: duplicates merge, the close-up adds what the sheet missed, rough boxes snap
    whole = [{"label": "flywheel", "type": "wheel", "box": [125, 128, 270, 275]},
             {"label": "lever", "type": "lever", "box": [190, 150, 560, 230], "ends": [[200, 200], [520, 180]]}]
    close = [{"label": "flywheel", "type": "wheel", "box": [122, 121, 279, 280]},
             {"label": "small gear", "type": "gear", "box": [470, 130, 565, 228], "teeth": 18}]
    parts = interpret.merge_reads([(whole, "whole sheet"), (close, "close-up")], 800, 500)
    assert len(parts) == 3, parts
    parts, snap = interpret.snap_circles(parts, found, 800, 500)
    print(f"  merged {len(parts)} parts; {snap}")
    assert snap["snapped"] == 2 and snap["added"] == 2
    fw = next(p for p in parts if p["label"] == "flywheel")
    assert abs((fw["box"][2] - fw["box"][0]) / 2 - 80) <= 3 and fw.get("measured")
    # rebuilt: a measured pivot inside the lever is as long as the lever (+ collars), not the machine depth
    P = interpret.parts_from_read(parts, 800, 500, 0.25)
    specs, rep = rebuild.rebuild(P, [200, 125])
    pins = [s for s in specs if s["eng"]["kind"] == "pin"]
    assert pins and all(s["params"]["height"] <= rep["stack_depth_mm"] + 2.1 for s in pins)
    assert not any("block" in s["name"] for s in specs)


def test_reading_agreement():
    """24. Muse Spark reads each image twice: a part is kept when both readings agree or a measured circle confirms it,
    the rest is logged as dropped; an answer that is not JSON is retried once, then fails loudly (no made-up parts)."""
    import agent
    from engine import interpret
    a = [{"label": "big gear", "type": "gear", "box": [100, 100, 300, 300], "teeth": 40},
         {"label": "lever", "type": "lever", "box": [300, 120, 700, 200]},
         {"label": "bracket", "type": "bracket", "box": [600, 400, 680, 470]}]              # only reading A: dropped
    b = [{"label": "gear", "type": "gear", "box": [104, 96, 306, 302]},
         {"label": "arm", "type": "arm", "box": [310, 125, 690, 210], "ends": [[320, 160], [680, 170]]},
         {"label": "pivot pin", "type": "pin", "box": [480, 380, 520, 420]}]               # only B, on a measured circle
    circ = [{"cx": 500.0, "cy": 400.0, "r": 21.0}]
    kept, dropped = interpret.agree(a, b, circ)
    labels = sorted(k["label"] for k in kept)
    print(f"  kept {labels}; dropped {[(d['label'], d['why'][:30]) for d in dropped]}")
    assert labels == ["big gear", "lever", "pivot pin"] and [d["label"] for d in dropped] == ["bracket"]
    # the same one-reading bracket is kept when the drawing shows its outline (drawn lines on its box's sides)
    import numpy as np
    ink = np.zeros((600, 800), bool)
    ink[400:402, 600:680] = ink[468:470, 600:680] = True
    ink[400:470, 600:602] = ink[400:470, 678:680] = True
    kept2, dropped2 = interpret.agree(a, b, circ, ink=ink)
    assert "bracket" in [k["label"] for k in kept2] and not dropped2
    assert "lines" in next(k for k in kept2 if k["label"] == "bracket")["agreed"]
    # one object, two names (D run 7: "54 wheel" / "55 large gear", box IoU 0.82): agreement, kept as the gear
    k3, d3 = interpret.agree([{"label": "54", "type": "wheel", "box": [0, 0, 100, 100]}],
                             [{"label": "55 large gear", "type": "gear", "box": [4, 2, 104, 98]}], [])
    assert len(k3) == 1 and not d3 and k3[0]["type"] == "gear"
    g = next(k for k in kept if k["label"] == "big gear")
    lv = next(k for k in kept if k["label"] == "lever")
    assert g["teeth"] == 40 and abs(g["box"][2] - 303) < 1e-9 and lv["ends"] == [[320, 160], [680, 170]]
    # JSON answers: retried once with the error shown, then a clear SparkError
    answers, sent = [], []

    def fake_post(path, body, timeout=120):
        sent.append(body)
        return {"choices": [{"message": {"content": answers.pop(0)}}]}
    real = agent._post
    agent._post = fake_post
    try:
        answers[:] = ["parts: gear", '{"view": "side", "parts": [], "dimensions": []}']
        obj, meta = agent._spark_json("read", agent.READ_SCHEMA, "t")
        assert obj["view"] == "side" and meta["retried"] and meta["calls"] == 2
        assert sent[0]["temperature"] == 0 and sent[0]["response_format"]["json_schema"]["strict"]
        assert "not valid JSON" in sent[1]["messages"][-1]["content"]
        answers[:] = ["no", "still no"]
        try:
            agent._spark_json("read", None, "t")
            raise AssertionError("no error")
        except agent.SparkError as e:
            print(f"  invalid JSON twice -> {e}")
    finally:
        agent._post = real


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print(name, "-", fn.__doc__.strip())
            fn()
            print("  PASS")
