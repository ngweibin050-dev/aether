# Graph Report - aether-lab  (2026-10-30)

## Corpus Check
- 43 files · ~198,448 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: (none) 2, .wasm 2, .css 2)

## Summary
- 422 nodes · 870 edges · 14 communities (11 shown, 3 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 62 edges (avg confidence: 0.85)
- Token cost: 79,371 input · 0 output

## Community Hubs (Navigation)
- Printable Film Hologram
- Muse Agent & Architecture
- Geometry Mesh Builders
- React UI & 3D Viewport
- Optics Propagation & Measurement
- Legacy Web Viewer
- UI Package Dependencies
- Holography Theory & Papers
- Eye Model & Desk Sharpness
- Hand Tracking Gestures
- Speckle Analysis

## God Nodes (most connected - your core abstractions)
1. `useStore` - 30 edges
2. `Icon()` - 14 edges
3. `App()` - 12 edges
4. `_hologram()` - 11 edges
5. `Grid` - 10 edges
6. `react` - 10 edges
7. `Viewport()` - 10 edges
8. `_grid()` - 9 edges
9. `_samples()` - 9 edges
10. `_png()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `AETHER React UI Entry (ui/index.html)` --semantically_similar_to--> `AETHER Lab Legacy Web UI (web/index.html)`  [INFERRED] [semantically similar]
  ui/index.html → web/index.html
- `chat()` --calls--> `for_agent()`  [EXTRACTED]
  agent.py → engine/lab.py
- `Gear Scene Controls (distance, tilt, teeth)` --conceptually_related_to--> `Text-to-CAD (build_assembly part library)`  [INFERRED]
  web/index.html → ARCHITECTURE.md
- `Hologram and Eye-View Reconstruction Panels with Focus Sweep` --conceptually_related_to--> `Focus Sweep (true focus cues)`  [INFERRED]
  web/index.html → ARCHITECTURE.md
- `Hologram and Eye-View Reconstruction Panels with Focus Sweep` --conceptually_related_to--> `Eye View through Pupil (optics.eye_view)`  [INFERRED]
  web/index.html → ARCHITECTURE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Scene-to-Eye Hologram Pipeline** — architecture_hidden_surface_removal, architecture_point_cloud_cgh, architecture_wavefront_recording_plane, architecture_phase_only_encoding, architecture_band_limited_angular_spectrum, architecture_eye_view [EXTRACTED 1.00]
- **AETHER Theory Laws Applied at Desk Scale** — architecture_window_law, architecture_hand_shadow_rule, architecture_desk_sharpness, architecture_sharp_zone, architecture_aether_physics_record [EXTRACTED 1.00]
- **Three Editing Modes Sharing One Tool Set** — architecture_laptop_mode, architecture_hand_mode, architecture_muse_spark, architecture_shared_scene_state [EXTRACTED 1.00]

## Communities (14 total, 3 thin omitted)

### Community 0 - "Printable Film Hologram"
Cohesion: 0.07
Nodes (37): binary_fourier_hologram(), export_png(), predicted_wall(), target_image(), wall_size(), local_mesh(), add_part(), build_assembly() (+29 more)

### Community 1 - "Muse Agent & Architecture"
Cohesion: 0.05
Nodes (23): chat(), _post(), transcribe(), AETHER 2.0 Architecture, Compute Backend (CuPy on Modal T4 / NumPy fallback), Hand Mode (MediaPipe Hand Landmarker gestures), import_mesh with Vertex-Clustering Decimation, Laptop Mode (Blender-style gizmo, outliner, shortcuts) (+15 more)

### Community 2 - "Geometry Mesh Builders"
Cohesion: 0.07
Nodes (32): _align_z(), blade_ring(), bounds(), box(), coil(), cone(), cylinder(), decimate() (+24 more)

### Community 3 - "React UI & 3D Viewport"
Cohesion: 0.11
Nodes (38): react, api(), App(), CameraSetup(), EyeAndWindow(), Gizmo(), HandJoints(), Panel() (+30 more)

### Community 4 - "Optics Propagation & Measurement"
Cohesion: 0.07
Nodes (20): to_numpy(), best_depth(), energy_near(), peak_near(), speckle_contrast(), angular_spectrum(), eye_view(), focus_sweep() (+12 more)

### Community 5 - "Legacy Web Viewer"
Cohesion: 0.08
Nodes (39): api(), applyResult(), ask(), box, busy(), camera, chunks, clock (+31 more)

### Community 6 - "UI Package Dependencies"
Cohesion: 0.08
Nodes (33): autoprefixer, @mediapipe/tasks-vision, postcss, react-dom, @react-three/drei, @react-three/fiber, tailwindcss, three (+25 more)

### Community 7 - "Holography Theory & Papers"
Cohesion: 0.08
Nodes (27): AETHER Physics Record / Physics v9, v11, v13, Fringe-Frequency Anti-Aliasing Disc, Band-Limited Angular Spectrum Method, Desk Sharpness 1D-Hologram Eye Model (desk_check, search_column_width), Eye View through Pupil (optics.eye_view), Focus Sweep (true focus cues), Hand-Shadow Rule / Depth Conflict (hand_check), Hidden-Surface Removal via Angular Z-Buffer (+19 more)

### Community 8 - "Eye Model & Desk Sharpness"
Cohesion: 0.19
Nodes (8): best_focus(), desk_sharpness(), eye_box(), mtf(), psf(), search_column_width(), ok(), test_eye_model_desk()

### Community 9 - "Hand Tracking Gestures"
Cohesion: 0.26
Nodes (11): BONES, d2(), gestureOf(), HandTracker(), commit(), draw(), loop(), nearestPart() (+3 more)

### Community 10 - "Speckle Analysis"
Cohesion: 0.32
Nodes (3): compare(), contrast(), test_patch()

## Knowledge Gaps
- **9 isolated node(s):** `Fringe-Frequency Anti-Aliasing Disc`, `Shimobaba 2009 (WRP)`, `Phase-Only Encoding for Phase SLM`, `Matsushima 2009 (band-limited ASM)`, `Verschaffelt 2015 (speckle visibility threshold)` (+4 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 142 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AETHER Lab Legacy Web UI (web/index.html)` connect `Holography Theory & Papers` to `Muse Agent & Architecture`, `Legacy Web Viewer`?**
  _High betweenness centrality (0.454) - this node is a cross-community bridge._
- **What connects `Fringe-Frequency Anti-Aliasing Disc`, `Shimobaba 2009 (WRP)`, `Phase-Only Encoding for Phase SLM` to the rest of the system?**
  _9 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Printable Film Hologram` be split into smaller, more focused modules?**
  _Cohesion score 0.0671602326811211 - nodes in this community are weakly interconnected._
- **Why does `three` connect `UI Package Dependencies` to `Hand Tracking Gestures`, `React UI & 3D Viewport`, `Legacy Web Viewer`?**
  _High betweenness centrality (0.205) - this node is a cross-community bridge._
- **Should `Muse Agent & Architecture` be split into smaller, more focused modules?**
  _Cohesion score 0.05454545454545454 - nodes in this community are weakly interconnected._
- **Should `Geometry Mesh Builders` be split into smaller, more focused modules?**
  _Cohesion score 0.06818181818181818 - nodes in this community are weakly interconnected._
- **Should `React UI & 3D Viewport` be split into smaller, more focused modules?**
  _Cohesion score 0.1063973063973064 - nodes in this community are weakly interconnected._