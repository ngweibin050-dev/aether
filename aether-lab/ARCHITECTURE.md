# AETHER 2.1 — Architecture

AETHER is a design desk for a no-headset holographic display. You build a 3D model with a
mouse and keyboard, with your hands, or by asking Muse Spark. AETHER then calculates the real
phase hologram for it and simulates what an eye would see.

Everything below is a simulation. No physical holographic display has been built.

```
 Browser (React + Vite + Tailwind + three.js)                 Python physics server
 ┌──────────────────────────────────────────┐   HTTP/JSON   ┌──────────────────────────────┐
 │ Laptop mode: gizmo, outliner, shortcuts  │──────────────▶│ server.py  (state + routes)  │
 │ Hand mode: MediaPipe hands → gestures    │  same tools   │ agent.py   Muse Spark loop   │
 │ Assistant: text / voice → Muse Spark     │◀──────────────│ compute.py local or Modal GPU│
 │ zustand store = one shared scene state   │  meshes, imgs │ engine/    wave optics       │
 └──────────────────────────────────────────┘               └──────────────────────────────┘
```

## 1. One state, three ways to edit it

- The server owns the scene (`state.parts`). Each part is a parametric primitive or an imported mesh, with a
  transform and a parent.
- The laptop gizmo, the hand controller and the AI agent all call the **same tools**: `add_part`,
  `update_part`, `build_assembly`, and so on. That is why switching mode (`Tab`) is instant, and why
  nothing is lost when you switch.
- Undo and redo snapshot `parts` before every change and restore the snapshot through `/api/scene`.
- The geometry has one source. Python builds every mesh (`engine/geometry.py`) and the browser only
  draws what it receives (`/api/meshes`). The picture you see is therefore the same geometry the
  physics engine uses.

### Laptop mode (Blender 4.x object-mode keymap)
Every action lives in one command list (`ui/src/commands.js`). The menu bar, right-click menu, Shift+A,
F3 search, pie menus, keyboard shortcuts and the hand menu all call the same list.

| Area | Keys / mouse |
|---|---|
| Navigate | MMB orbit, Shift+MMB pan, Ctrl+MMB or wheel zoom. Laptop: Alt+LMB orbit, Alt+Shift+LMB pan, two-finger scroll orbit, pinch zoom. Nav gizmo: click an axis, drag to orbit; zoom and pan handles |
| Views | Numpad (or number row) 1/3/7 front/right/top, Ctrl = opposite side, 5 ortho/persp, 0 = the viewer's eye, 2/4/6/8 orbit 15°, `.` frame selected, Home frame all, `` ` `` view pie |
| Select | LMB click, Shift+LMB add/remove, drag = box select (Ctrl subtracts), A all, Alt+A none, Ctrl+I invert, Shift+G parent, double-click = whole assembly |
| Transform | G / R / S follow the mouse; X Y Z lock an axis; type a number for an exact value; Ctrl snaps (1 mm, 5°, 0.1), Shift for precision; LMB/Enter confirm, RMB/Esc cancel. Alt+G/R/S clear. Toolbar gizmos for move / rotate / scale |
| Edit | Shift+A add at the 3D cursor, Shift+D duplicate and move, X / Del delete, H hide, Alt+H reveal, Shift+H hide others, Ctrl+P parent, Alt+P clear parent, F2 rename, Shift+S snap pie, Shift+RMB place the 3D cursor, drag in the outliner to re-parent |
| Shading | Z pie: wireframe, solid, hologram look. Alt+Z x-ray |
| File | Ctrl+S save scene JSON, Ctrl+O open, import glTF/GLB, export print film |
| Other | F3 search every action, F12 calculate hologram, Ctrl+F12 focus sweep, T toolbar, N item panel, Ctrl+Space hide all panels, Ctrl+Z / Ctrl+Shift+Z |

Not copied from Blender: mesh edit mode (parts are parametric solids, edited by their parameters in the
Item panel), modifiers, materials, animation and rendering. Tab switches Laptop / Hand mode instead of
entering edit mode.

### Hand mode (MediaPipe Hand Landmarker, 21 joints per hand, runs in the browser)
The first hand drives an **air cursor** (the point between thumb and index tip, which stays still while
pinching). A pinch is a real pointer press on whatever is under the cursor, so every button, menu,
slider, panel and the hold-to-talk microphone work in hand mode exactly as with a mouse.

| Gesture | Action |
|---|---|
| Point | Move the air cursor |
| Pinch (tap) | Click any button, menu item or part |
| Pinch-hold on a part | Grab it: move in the view plane; move the hand toward/away from the camera to push/pull |
| Pinch-hold on empty space | Orbit the view (a short tap deselects) |
| Pinch-hold on UI | Drag sliders and panels, hold the microphone |
| Two-hand pinch, part selected | Rotate about the vertical axis and scale |
| Two-hand pinch, nothing selected | Pull apart = explode the assembly, push together = assemble |
| V-sign held 0.6 s | Hand menu: add part, explode, delete, section cut, duplicate, x-ray, all actions (search), hologram |
| Fist held 0.8 s | Deselect / close a menu |
| Both palms open 1 s | Calculate the hologram and run a focus sweep |

Camera to desk mapping: image x → desk x, image y → height, apparent palm size → depth.
Twice a second the hand joints are sent to the server for the occlusion check (section 3.4).

## 2. Text-to-CAD

Muse Spark gets a `build_assembly` tool whose schema lists the part library: gear, tube,
cylinder, cone, sphere, torus, box, nozzle (bell), coil, blade ring and pipe. It writes the
assembly as JSON (parts, parameters, positions, parent links). The server checks every part and
reports any it rejects back to the model, so the model can fix them.

Imported meshes, such as a GLB file or the output of a 3D generation API, go through `import_mesh`.
They are **decimated** to about 4,000 triangles by vertex clustering and scaled to about 80 mm, so
they cannot overload the optics.

**Honest limits.** "A Raptor engine" comes out as a simplified parametric model of its main
components, not manufacturer data. UV unwrapping is skipped on purpose: the hologram is lit by a
single laser colour and uses no textures.

## 3. Physics engine (`engine/`)

Units: the scene is in mm. The hologram panel is the plane z = 0, and light travels toward +z
(the viewer).

### 3.1 Scene → light points
Points are sampled on the surfaces, weighted by triangle area × part brightness (`sample_surface`).
**Hidden-surface removal** works from the eye, using an angular z-buffer (`window.visible_from`).
Each point P is binned by its viewing direction u = (P−E)ₓ/(E_z−P_z), v = (P−E)ᵧ/(E_z−P_z).
A point survives if it is within 1.5 bin widths of the nearest depth in its own bin **and** within 6 bin
widths of the nearest depth in the 3×3 neighbourhood. The second rule closes the gaps that random
sampling leaves in a shell, so inner parts do not leak through (sphere test: wrongly visible points
448 → 6 of 3,000; a box inside the sphere leaks 0 points instead of 55).

### 3.2 Computer-generated hologram
Each point j, with amplitude a_j and random phase φ_j, contributes a converging spherical wave
on the hologram:

  U_H(x,y) = Σ_j a_j · exp(i(φ_j − k r_j)) / r_j,  r_j = √((x−x_j)² + (y−y_j)² + z_j²),  k = 2π/λ

**Anti-aliasing.** A point only writes inside the disc where its local fringe frequency
ρ/(λ r) ≤ 1/(2p). That is ρ ≤ z_j · tan θ_max, with sin θ_max = λ/(2p) (p = pixel pitch).

**Wavefront Recording Plane (WRP; Shimobaba 2009, multi-plane version).** Points are cut into
depth slabs 1.5 mm thick. Each slab is written onto a plane just in front of it, so the windows
are tiny, and that plane is then carried to the hologram with the angular spectrum method. This
is 5× faster than writing every point onto the hologram, and focuses better (test 5).

**Encoding.** The hologram is phase-only, φ_H = arg U_H, which is what a phase spatial light
modulator can show.

### 3.3 Propagation and seeing
**Band-limited angular spectrum** (Matsushima 2009):

  U(z) = F⁻¹{ F{U(0)} · exp(i2πz√(λ⁻² − f_x² − f_y²)) · W },
  W = 0 for |f| > 1 / (λ√((2Δf z)² + 1)), padded 2×.

**Focus sweep.** The field is propagated to several depths through the object, which shows that
near and far parts come into focus at different depths (true focus cues).

**Eye view.** This is the image an eye forms (`optics.eye_view`), in three steps:
1. Propagate the hologram field to the eye plane (z = L).
2. Multiply by a circular pupil centred at the eye (x_e, y_e). Only light entering the pupil is seen.
3. Propagate back by −(L − z_f) to the depth z_f where the eye focuses.

Moving the eye shows parallax, and points outside the window disappear. This is the Window Law,
computed rather than assumed.

**Two scales.** A 27-inch hologram would need about 3×10⁷ pixels at 45 µm. For that reason, the full
wave simulation runs on a lab-scale phase modulator (1024² × 8 µm = 8.2 mm), with the scene
shrunk uniformly (the factor is shown in the UI). Desk-scale questions use the geometric laws
and the eye model below.

### 3.4 Laws from the AETHER theory, applied at desk scale
- **H1 Window Law** (Physics Record §8.1). The eye sees P only if the line from the eye through P,
  extended back, hits the panel: E + t(P−E) at z = 0, with t = E_z/(E_z−P_z), must lie inside the
  598 × 336 mm panel. Tool: `window_check`, which reports the visible percentage per part.
- **Hand-shadow rule** (Physics v13 §4). P's light runs panel → P → pupil.
  - A hand on the segment panel → P blocks light that should have come out in front of the hand.
    This is a **depth conflict**, which software cannot fix.
  - A hand on the segment P → eye is ordinary, correct occlusion.
  Tool: `hand_check`, which models the tracked joints as 9 mm spheres.
- **Desk sharpness** (Physics v9/v13 eye model). The AETHER Desk is a 1D hologram: the vertical
  wavefront curvature is true (1/D) and the horizontal one comes from the panel plane (1/d). The
  retinal PSF is computed through a 4 mm pupil, and sharpness is the MTF at 15 cycles/degree with
  the best eye focus, relative to a full 2D hologram. The eye box is e = λd/p_v (8.2 mm for 45 µm
  at 70 cm). Tools: `desk_check` and `search_column_width`, which runs a 7-step bisection over
  column width.
- **Sharp zone.** v13 gives about ±100 mm for an eye straight in front of the panel. The seated eye looks down at about 50°, so a point's distance from the panel along the line of sight is longer than its height. desk_score and window_check compute `sharp_zone_mm` for the actual eye position (about −108..+87 mm at 80 % for the default eye).
  Floating at 25 cm would need kHz phase modulators, which do not exist yet.

### 3.5 Seeing inside (`engine/cutaway.py`, tool `set_view`)
The view settings are part of the scene state, so the 3D viewport **and the hologram** use them:
- **Section cut** along x, y or z at a world coordinate. Surface points on the removed side are dropped
  before hidden-surface removal, so inner surfaces become visible to the eye and enter the light field.
  The desk viewer looks down from 70 cm, so a Z cut opens the inside to the eye; X and Y cuts open it
  from the side (visible in the viewport and in eye views from the side).
- **Exploded view**: coaxial parts (shells, stator, rotor, shaft) are re-stacked along the assembly's
  main axis in their original order, each in its own slot, so nested parts slide out of each other.
  Off-axis parts (coils, magnets, bolts) ride with the coaxial part they sit in and move outward
  radially. Offsets are linear in the explode factor (0–1); the UI animates them.
- **Isolate** shows only the chosen parts (with their children and parents).
- **X-ray** skips hidden-surface removal: the hologram shows the whole object as see-through.

### 3.6 Speckle (Physics v11)
The test is a flat, evenly lit patch, viewed through a pupil whose blur spot (λ(L−z)/D) covers
several surface points. The tool compares three cases:
- a single frame, where C = σ/μ ≈ 1 (fully developed speckle);
- the average of k² random-phase frames, where C ≈ C₁/k;
- k×k **sparse point groups**, where points shown together are k lattice cells apart.

Result at k = 3: 0.995 → 0.358 (random) and 0.288 (groups). The visible threshold is about
0.03–0.04 (Verschaffelt 2015), so speckle stays an open problem. The tool reports this honestly.

### 3.8 What the viewer's eye sees (`engine/retina.py`, tools `focus_sweep`, `eye_view`)

The hologram panel shows a picture a person recognises, computed from the theory, not raw light points.

1. Render the current view (cut / exploded / x-ray included) from the seated eye at (0, −450, 540) mm, about 70 cm from the panel centre: a z-buffer of ~3.6 M surface samples, Lambert + rim shading. Each pixel keeps its depth D and the distance d to the panel along its ray.
2. Window Law (H1): pixels whose eye→point ray misses the 598×336 mm panel are dark.
3. Split the picture into 0.02-dioptre depth layers. Each layer is blurred by the eye's own PSF (Physics v9): PSF = |FFT(pupil · e^{−iW})|², 4 mm pupil, 530 nm, W = ½k[X²(1/Dx − 1/F) + Y²(1/Dy − 1/F)], F = focus distance.
   - AETHER Desk 1D: Dy = D (true vertical curvature), Dx = d (panel), plus the 150 µm column box blur (v13).
   - full 2D hologram: Dx = Dy = D.  ordinary 3D screen: Dx = Dy = d.
4. Speckle (v11/v12): a pooled speckle texture from k×k sparse point groups (desk: vertical-only coherent, columns horizontally incoherent) multiplies the image; 3×3 gives ≈3.6 % contrast, near the 3.2–4.4 % visibility threshold.
5. Sharpness readout = area-weighted MTF at 15 c/deg divided by the MTF a full 2D hologram would give for the same
   pixels at the same eye focus (so full 2D = 100 % by definition). `in_focus_vs_full_2d_pct` uses only the layers
   within the eye's ±0.25 D depth of field. A layer the eye is NOT focused on can exceed 100 % on the desk (its
   horizontal stays at the panel, which may be nearer the focus than the defocused 2D image): that is physics.
6. Colour mode adds the eye's longitudinal chromatic aberration (Thibos et al., Appl. Opt. 31:3594, 1992):
   R(λ) = 1.68524 − 633.46/(λ − 214.102) D, eye focused for 520 nm.
7. `which_eye`: centre, left, right (±31.5 mm) or both (side-by-side) to see the stereo disparity.

`focus_sweep` repeats step 3–5 for several focus heights (the vertical slider); `eye_view` does one at a chosen height and display.

### 3.10 Oblique sharp zone (`eye.line_of_sight`, `lab.sharp_zone`, `desk_score`)

The eye looks down at ~50°, so a point's astigmatism |1/D − 1/d| is measured along its own line of sight (d = eye
→ panel through that point), not vertically. `desk_score` scores every vertex this way (worst value) and reports
the area-weighted mean. `sharp_zone` bisects the heights where a point on the centre line stays ≥ 80 % of full 2D:
−108 … +87 mm for the default eye. The 1D/2D ratio for (astigmatism, column blur) is precomputed in
`engine/sharpness_table.json` (0–1.5 D × 0.4–1.3′, same `eye.psf`), so `desk_score` takes ~0.4 s instead of ~30 s.

### 3.11 True-scale 1D desk wave simulation (`engine/desk_wave.py`, tool `desk_wave_view`)

Checks the desk eye model with waves at true scale: vertical = coherent 1D sub-holograms at the projected pitch
p·cos(tilt) (34.6 µm), field-lens backlight, propagated to the eye box (λd/p), cut by the pupil chord, focused
on the retina; horizontal = incoherent columns with geometric defocus per chord + column blur; Gauss–Legendre
chords cover the round pupil. With ideal complex modulation it matches the analytic eye model within ~1 %
(0.855/0.855 on the panel, 0.775/0.776 at 0.62 m). Phase-only encodings (double-phase, kinoform) add haze of
0.4–1.7× the signal here, because a 10.7 mm eye box with a 4 mm pupil leaves no guard band: an open problem
(needs complex modulation or a larger eye box), left as `encode=` experimental, default `none`.

### 3.12 Drawing → 3D (`engine/outline.py`, `engine/rebuild.py`, `engine/hull.py`)

- Outlines: marching squares → RDP → hole nesting → ear clipping with hole bridges → watertight extrusion.
- Gears: standard involute (ISO 54 module snap, r = mz/2, rb = r cos α, ra = r + m, rf = r − 1.25m), contact ratio
  check, mesh phase so teeth sit in gaps (rasterised overlap < 0.5 mm²). `turn_gear` turns a gear and every gear
  meshed with it (ratio −z1/z2) or on the same pin.
- Rebuild by kind (gear, wheel, pin, shaft, spring, piston, frame, link, plate): meshing gears share a layer, other
  parts are layered by raster overlap; pins run along the axis; frames become back plate + hidden front plate +
  standoffs. Each part keeps `eng.dims` with the source of every number (read from drawing / measured / assumed).
- Three views (front, top, right side) → visual hull on a voxel grid → watertight surface + Taubin smoothing
  (`import_three_view`, button 3V). Hidden pockets and blind holes are filled; dashed lines are not read.
- CAD meshes: STL / OBJ / GLB import keeps real millimetres (`import_mesh` with `size_mm = 0`). STEP: export STL.

### 3.9 Lab-scale phase hologram (`make_hologram`, `optics.image_hologram`)

The same rendered view is shrunk to the lab grid (1024², 8 µm), split into 8 depth layers, and each layer is back-propagated with the band-limited angular spectrum. Layers are summed into 2×2 sparse point groups (Takaki-style): 4 phase-only subframes, each with one pixel of every 2×2 cell lit, so neighbouring points never interfere. The reconstruction averages the 4 subframe intensities, which is what the eye does when they are shown in sequence. The phase pattern itself looks like noise; that is normal.

### 3.7 Compute (Modal GPU by default)

- Heavy tools (`eye_view`, `focus_sweep`, `make_hologram`, `propagate`, desk checks, film) run on Modal: `modal_app.run_tool` on an NVIDIA T4, image `nvidia/cuda:12.4.1-runtime` + `cupy-cuda12x`. Scene edits stay local.
- `engine/backend.py` picks CuPy when a GPU is present, NumPy otherwise. `retina.render` (surface sampling, z-buffer splat via `cupyx.scatter_min/add`) and `retina.retina` (per-layer PSF + FFT convolution) run on `xp`, so the same code is GPU on Modal and CPU locally.
- One container, kept warm 10 minutes, holds the rendered view in memory: the Calculate button asks for one eye view first (one render + one focus), then the 7-step sweep reuses the render.
- `server.py` warms the container at start (`compute.warm`, Modal function `ping`). If Modal fails, the tool returns an error naming the cause; `AETHER_FALLBACK=local` allows a CPU fallback, `AETHER_COMPUTE=local` runs everything on this computer.
- Full colour (`color=true`, default): R 638 / G 520 / B 450 nm lasers, each with its own pupil PSF (diffraction and defocus scale with λ) and an independent speckle pattern (seed per laser); luminance speckle = sqrt(Σ(w_i c_i)²) with Rec.709 weights, ≈2.6 % vs 3.6 % for one laser. Part colours: the part's `color` (hex) or a material guess from its name (`retina.MATERIALS`). Sharpness is reported for the green channel.

## 4. Meta AI integration
- **Muse Spark 1.3** runs the agent. It has 20 tools (including `set_view`, so "cut it in half and
  explode it" works by voice or text) with JSON schemas, and its explanations must
  quote tool results.
- **Closed design loop** (`agent.optimize`, tool `optimize_for_desk`, button *Fix for desk*). The engine's
  `desk_score` gives, per part, its height range, the v13 eye-model sharpness at its worst point
  (relative to a full 2D hologram, cached on a 5 mm grid) and the share visible through the panel (Window
  Law), plus pass/fail and hints. Muse Spark gets the score with only `update_part` available, changes the
  design (move the root group towards z = 0, lay it flat, scale ≥ 0.6, never delete or reshape), the
  engine re-scores it, up to 3 rounds. Before/after eye views (full colour, focused on the top of the
  design) are computed on the GPU. The model proposes; the physics decides.
- **SAM 3.1** (`vision.py`, `POST /api/photo`). The phone photo (≤ 768 px) goes to `POST /v1/responses`
  (model `sam-3.1`, streamed) with a one-noun concept prompt. Boxes and masks are parsed and decoded with
  Meta's `meta-sam-parser`. The best mask gives silhouette numbers: size (longest side = the size the user
  types), roundness, centre hole radius (the centroid is background), and lobes around the centre (gear
  teeth, fan blades; peaks of the smoothed radial profile). Muse Spark gets these numbers plus the
  cut-out on white and rebuilds the part with `build_assembly`; if the model rejects images it gets the
  numbers only. One photo shows one side, so depth is assumed and the reply must say so.
- **Muse Voice Transcribe** handles hold-to-talk voice input: the browser re-encodes the recording to
  16 kHz mono WAV and the server posts it to `POST /v1/asr/transcribe` (multipart `request` JSON + `audio`).

## 5. Tests (`python -m tests.test_physics`)
1. A single point refocuses at its depth.
2. Two depths are each sharp only at their own depth.
3. Pixel pitch sets the bend angle, and aliasing appears past the limit.
4. The eye model reproduces the full-hologram reference (0.855) and the 1D desk falls off with height.
5. WRP equals the direct method in focus depth, with better energy concentration.
6. Window Law and hand-conflict geometry.
7. Seeing inside: a box inside a closed sphere is hidden (0 points); a Z cut and X-ray reveal it.
8. Design-loop score: a 150 mm tube at z = 110 mm fails (55.5 %); moved to z = 0 it passes (89.4 %).
9. Photo silhouette: a 12-tooth gear mask gives 12 lobes, a centre hole and the typed size.
10. Sharpness metric: on the panel ≈100 % of full 2D; oblique line-of-sight geometry.
11. Outline extrusion is watertight with the right volume (plate with a hole).
12. Involute pair z20/z30 m2: contact ratio 1.605, teeth do not overlap at the mesh phase.
13. Synthetic drawing rebuild: frame + two meshing gears + pin + link + spring → upright layered mechanism that passes the desk score.
14. Wave simulation vs eye model within 2 %.
15. Three-view L-bracket → closed solid, size within 1.5 mm, volume within 5 %.
16. Simulated retina: full 2D = 100 %; desk 1D below it where the eye is focused.

## 6. What was left out, and why
- **Node-based material editor.** Holograms here are single-colour laser light, so only per-part
  brightness matters optically. A node graph would add UI without changing the physics.
- **WebXR.** The product goal is no headset, so a WebXR session would demo the opposite. Hand
  tracking uses a plain webcam.
- **Meshy or Luma API.** These are paid services and they do not count toward Meta tooling. The
  `import_mesh` path accepts their GLB output if a key is added later.
