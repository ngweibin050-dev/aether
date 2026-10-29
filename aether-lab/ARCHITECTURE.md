# AETHER 2.0 — Architecture

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

### Laptop mode
Blender-style keys: `G` move, `R` rotate, `S` scale, `X/Y/Z` lock an axis, `Shift+D` duplicate,
`Del` delete, `H` hide, `Ctrl+Z` / `Ctrl+Shift+Z` undo and redo, `Enter` calculate the hologram,
`[` and `]` show or hide the side panels, `/` open the assistant. The outliner shows the part
hierarchy, the property panel edits numbers exactly, and you can import a GLB model.

### Hand mode (MediaPipe Hand Landmarker, 21 joints per hand, runs in the browser)
| Gesture | Action |
|---|---|
| Pinch (thumb + index) | Select the nearest part and drag it in 3D |
| Pinch with both hands | Rotate around the vertical axis and scale (by the distance between the hands) |
| Fist held 0.8 s | Deselect |
| Both palms open for 1 s | Calculate the hologram and run a focus sweep |

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
In each bin, a point survives only if its depth is within one bin width of the nearest depth.

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
- **Sharp zone.** The design should stay within ±100 mm of the panel (v13: 78–90 % of full sharpness).
  Floating at 25 cm would need kHz phase modulators, which do not exist yet.

### 3.5 Speckle (Physics v11)
The test is a flat, evenly lit patch, viewed through a pupil whose blur spot (λ(L−z)/D) covers
several surface points. The tool compares three cases:
- a single frame, where C = σ/μ ≈ 1 (fully developed speckle);
- the average of k² random-phase frames, where C ≈ C₁/k;
- k×k **sparse point groups**, where points shown together are k lattice cells apart.

Result at k = 3: 0.995 → 0.358 (random) and 0.288 (groups). The visible threshold is about
0.03–0.04 (Verschaffelt 2015), so speckle stays an open problem. The tool reports this honestly.

### 3.6 Compute
`engine/backend.py` uses CuPy when a CUDA GPU exists (on Modal: `modal deploy modal_app.py`, T4) and
NumPy otherwise. `compute.py` sends the heavy tools to Modal and falls back to local compute if
the call fails.

## 4. Meta AI integration
- **Muse Spark 1.3** runs the agent. It has 18 tools with JSON schemas, and its explanations must
  quote tool results.
- **Muse Voice Transcribe** handles hold-to-talk voice input.

## 5. Tests (`python -m tests.test_physics`)
1. A single point refocuses at its depth.
2. Two depths are each sharp only at their own depth.
3. Pixel pitch sets the bend angle, and aliasing appears past the limit.
4. The eye model reproduces the full-hologram reference (0.855) and the 1D desk falls off with height.
5. WRP equals the direct method in focus depth, with better energy concentration.
6. Window Law and hand-conflict geometry.

## 6. What was left out, and why
- **Node-based material editor.** Holograms here are single-colour laser light, so only per-part
  brightness matters optically. A node graph would add UI without changing the physics.
- **WebXR.** The product goal is no headset, so a WebXR session would demo the opposite. Hand
  tracking uses a plain webcam.
- **Meshy or Luma API.** These are paid services and they do not count toward Meta tooling. The
  `import_mesh` path accepts their GLB output if a key is added later.
