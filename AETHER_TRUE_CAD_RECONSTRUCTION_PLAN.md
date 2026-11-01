# AETHER Lab: True CAD Reconstruction Architecture and Execution Plan

**Purpose:** Replace the current drawing-to-mesh reconstruction as the authoritative model-generation path with an editable, feature-based CAD system backed by valid B-rep solids. Retain AETHER's existing AI orchestration, Three.js interaction, engineering explanation, and holographic simulation where they remain useful.

**Repository audited:** `ngweibin050-dev/aether`, branch `main`  
**Audit date:** 2 November 2026  
**Scope:** First-party AETHER Lab reconstruction, geometry, scene/state, export, server/compute, frontend viewport, tests, and architecture/results documentation.

---

## Executive decision

Do not try to repair the current visual hull by increasing smoothing, triangle counts, or prompting Muse Wonder more aggressively. That would improve the appearance of a mesh in some cases, but it would not create an engineering CAD model.

AETHER Lab needs a new authoritative modelling layer with:

1. **A native AETHER CAD document** containing components, sketches, datums, constraints, features, assembly joints, parameters, and provenance.
2. **A B-rep geometry kernel** that creates analytic and NURBS geometry and validates solids.
3. **A deterministic feature builder** that converts a typed CAD intermediate representation (IR) into B-rep operations. AI must not generate and execute arbitrary Python code.
4. **A drawing-understanding pipeline** that turns views, dimensions, centerlines, hidden lines, symbols, and part annotations into geometric observations and constraints.
5. **A reconstruction solver** that finds CAD features and parameters consistent with all supplied views, dimensions, and engineering rules.
6. **An assembly model** with explicit components, joints, degrees of freedom, interference checks, and gear relationships.
7. **A review and uncertainty system** that distinguishes measured facts from inferred geometry and asks for user input where the drawing is underdetermined.
8. **CAD-native export**, especially STEP, while GLB/STL become derived visualization/fabrication outputs rather than the source of truth.

The desired pipeline is:

```text
Same uploaded drawing
        |
        v
Image calibration and drawing understanding
        |
        v
Geometric observations + dimensions + semantic part hypotheses
        |
        v
Cross-view constraint graph and uncertainty model
        |
        v
Feature / surface / component hypotheses
        |
        v
Constraint solving and engineering validation
        |
        v
AETHER CAD feature graph
        |
        v
OpenCascade B-rep construction and validation
        |
        v
Assembly checks + drawing reprojection checks
        |
        +--------------------+
        |                    |
        v                    v
Editable CAD document     Adaptive tessellation for AETHER viewport
        |                    |
        v                    v
STEP / native project     GLB / optics / holographic simulation
```

A visual hull may remain as an **optional preview or envelope proposal**, but it must never be presented as a final CAD reconstruction.

---

# 1. What the current code actually does

This section records the source-derived findings that motivate the redesign.

## 1.1 There are two different drawing reconstruction routes

The upload router is `aether-lab/agent.py::photo_to_design()` and `aether-lab/vision.py::upload_kind()`.

### Route A — three-view drawing

The three-view route is approximately:

```text
photo_to_design(kind="three_view")
  -> agent._sheet_to_design()
  -> engine.sheet.naming_views()
  -> engine.sheet.sheet_to_solid()
  -> engine.hull.carve() / hull_field_slabs()
  -> engine.hull.surface_nets()
  -> decimation / smoothing / region segmentation
  -> engine.lab.import_sheet()
  -> mesh parts in scene state
```

Relevant source files:

- `aether-lab/agent.py`
- `aether-lab/vision.py`
- `aether-lab/engine/sheet.py`
- `aether-lab/engine/hull.py`
- `aether-lab/engine/segment.py`
- `aether-lab/engine/quality.py`
- `aether-lab/engine/lab.py`

The decisive limitation is in `engine/hull.py::carve()`: it intersects the filled side, top, and front silhouettes on a voxel grid. In simplified notation, the occupied space is:

\[
H(x,y,z)=S(x,z)\cap T(x,y)\cap F(y,z)
\]

That operation produces a **visual hull**. It can be consistent with three silhouettes without being the actual designed surface. Concave regions that are not visible in any silhouette—such as blind recesses, wheel wells, internal pockets, and complex surface transitions—cannot be recovered from the silhouettes alone.

`engine/sheet.py::sheet_to_solid()` then makes a scalar field, uses surface nets to make a triangle mesh, applies smoothing and decimation, assigns mesh regions using `segment.py`, and sends those mesh fragments into `lab.import_sheet()`. The parts are stored as `type="mesh"` with vertex and face arrays. That is still a mesh representation, not a parametric feature tree or analytic B-rep.

### Route B — single-view mechanical drawing

The single-view machine route is approximately:

```text
photo_to_design(kind="machine")
  -> agent._blueprint_to_design()
  -> Muse Spark drawing reading (_read_machine / _spark_read_drawing)
  -> engine.interpret.parts_from_read()
  -> Muse Wonder completion (_spark_complete; Muse Spark fallback)
  -> engine.rebuild.rebuild()
  -> geometry builders in engine.geometry.py
  -> lab.build_assembly()
```

Relevant source files:

- `aether-lab/agent.py`
- `aether-lab/vision.py`
- `aether-lab/engine/interpret.py`
- `aether-lab/engine/rebuild.py`
- `aether-lab/engine/geometry.py`
- `aether-lab/engine/outline.py`
- `aether-lab/engine/lab.py`

This route is more engineering-aware than the three-view hull route, but it is still largely a heuristic primitive/mesh reconstruction system:

- `interpret.py` converts model-read boxes and axis ends into typed hypotheses such as gear, wheel, link, piston, shaft, spring, frame, and plate.
- `rebuild.py` infers missing dimensions and depth. Examples include gear face width from module, wheel thickness from radius, link thickness from width, plate thickness from its dimensions, and a default overall machine depth based on the drawing's smaller side.
- Parts are layered using raster overlap and gear relationship heuristics. Hubs, pins, bearings/spacers, and frame structures may be added from rules or the AI completion.
- The system does create some useful geometry—for example, involute gear profiles and extruded outlines—but the `geometry.py` builders return triangle vertices and faces. They do not create an editable sequence of CAD features.

This is a useful concept-reconstruction prototype. It is not yet a general parametric CAD application.

## 1.2 The geometry layer is a custom triangle-mesh system

`aether-lab/engine/geometry.py` defines mesh builders for boxes, cylinders, tubes, cones, spheres, tori, gears, nozzles, coils, pipes, outlines, and related primitives. `local_mesh()` returns `(V, F)` arrays; `world_mesh()` applies transforms; `scene_meshes()` collects visible meshes.

`engine/outline.py` extracts image-mask boundaries, simplifies/vectorizes loops, nests holes, triangulates them, and extrudes them. This can make closed triangle meshes, and the tests include a watertight extrusion case. A watertight triangle mesh is not the same thing as an exact CAD B-rep solid with faces, edges, analytic curves/surfaces, and feature history.

`engine/lab.py` stores `state.parts` as JSON-friendly dictionaries. A part has a `type`, `params`, transform, parent, visibility, and other metadata. Imported mesh geometry is stored in the part parameters. `lab.meshes()` sends local vertex and face arrays to the frontend.

## 1.3 Export currently produces exchange meshes, not native CAD

`aether-lab/engine/export.py` exports:

- Binary STL in millimetres, Z-up.
- GLB in metres, Y-up, with per-node names, materials, and engineering metadata in `extras`.
- A one-page HTML build report.

There is no STEP B-rep export path in the current exporter. The GLB is a valid visualization/interchange mesh format when generated correctly; it is not an editable CAD feature document. A Blender import problem and a bad reconstruction are separate issues: GLB must be imported through Blender's glTF importer, but using the correct importer does not improve the geometry.

## 1.4 The frontend displays meshes

`aether-lab/ui/src/scene/Viewport.jsx` builds `THREE.BufferGeometry` from the mesh arrays and uses Three.js materials and `toCreasedNormals()`. It provides orbit controls, selection, transforms, section cuts, exploded view, isolation, and holographic shading.

The UI experience is valuable and should be retained. But the viewport currently renders tessellated triangles, not B-rep faces/edges from a CAD kernel. A proper CAD system should continue to render tessellated geometry in Three.js, but that tessellation must be generated from the authoritative B-rep and kept separate from the CAD definition.

## 1.5 The test suite does not certify CAD quality

`tests/test_physics.py` contains 36 tests, many of which verify optics and holographic simulation. Geometry-related tests verify selected properties such as a closed extruded mesh, involute gear meshing, synthetic drawing reconstruction, view matching, surface roughness, and GLB structure.

Those tests are useful, but they do not establish:

- a parametric feature history that recomputes after edits;
- robust B-rep validity;
- drawing-to-CAD accuracy on a benchmark with ground-truth CAD;
- a reliable constrained assembly solve;
- dimension/tolerance satisfaction;
- STEP export and round-trip integrity;
- robust feature references after upstream changes;
- production-grade surface quality across diverse real drawings.

`docs/RESULTS.md` itself records the unresolved car-body surface issue. In the internal car-sheet comparison, the documented latest build has roughness RMS 8.15°, 15.4% of measured surface edge length bent over 10°, and 355 flipped triangles. The same section records remaining tyre slabs, roof streaks, and plain-cylinder wheels. That is direct evidence that high silhouette agreement does not guarantee a high-quality surface.

## 1.6 Infrastructure worth retaining

The following are good foundations and should not be thrown away:

- Meta API orchestration and model attribution in `agent.py`.
- Muse Spark / Muse Wonder reading and completion plumbing.
- SAM 3.1 segmentation and image parsing in `vision.py`.
- The geometric reasoning already present in `interpret.py` and `rebuild.py`, especially the gear-specific work.
- The current AETHER scene interaction, hierarchy, undo/redo, section, explode, isolate, and hand/mouse interaction.
- The optics and hologram simulation modules (`optics.py`, `retina.py`, `eye.py`, `desk_wave.py`, `window.py`, `speckle.py`, `cutaway.py`, and related modules).
- Modal GPU infrastructure for optical simulation and any tasks that demonstrably benefit from GPU acceleration.
- The build report, dimension provenance, and measured-versus-assumed labels.

The CAD kernel should become a new geometry authority. It should not replace the optics theory or unnecessarily rewrite the entire user interface.

---

# 2. Define the actual target: what counts as “real CAD”

AETHER must not call a model “CAD” merely because it is a detailed mesh or because it can be opened in Blender.

## 2.1 Required output characteristics

A successful AETHER CAD model must have:

1. **Editable design intent:** dimensions and operations are represented as parameters and features, not only as vertices.
2. **B-rep geometry:** solids are represented by faces, edges, wires, analytic surfaces, and NURBS surfaces through a CAD kernel.
3. **Feature history:** sketches, extrusions, revolutions, holes, pockets, lofts, patterns, fillets, chamfers, etc. are named and ordered in a dependency graph.
4. **Component structure:** assemblies are made of individually addressable components with stable identities and relationships.
5. **Constraints:** dimensions and geometric relationships are explicit and can be solved/recomputed.
6. **Provenance:** every important dimension and geometric decision is tagged as measured, derived, inferred, assumed, or user-confirmed.
7. **Validation:** B-rep validity, geometric constraints, view correspondence, dimensions, and assembly interference are checked.
8. **Interoperability:** export STEP for CAD exchange; export GLB/STL as derived representations.
9. **Recomputability:** changing a parameter should rebuild dependent features or clearly show why the model cannot recompute.

## 2.2 What it must not promise

Even a robust CAD kernel cannot recover information that is absent from the input. A three-view drawing constrains shape, but it does not uniquely specify every concavity, blend, wall thickness, internal cavity, material, tolerance, or manufacturing intent. A single view is more underdetermined because depth is generally missing.

Therefore the promise should be:

> AETHER creates a structured, editable CAD reconstruction that satisfies the supplied drawing evidence and declared engineering assumptions, identifies unresolved ambiguity, and supports engineer review.

It should **not** promise that every arbitrary photo or incomplete sketch becomes manufacturing-ready with no human intervention.

Use explicit model maturity statuses:

- `Draft inference`
- `Geometrically valid`
- `Drawing-consistent`
- `Dimension-constrained`
- `Assembly-checked`
- `Engineer-reviewed`
- `Manufacturing-released` (only through a real engineering release process)

Do not automatically mark a generated model as engineer-reviewed or manufacturing-released.

---

# 3. Recommended technology architecture

## 3.1 CAD kernel decision

Run a short, measured technology spike before committing to a full integration.

### Primary candidate: CadQuery + OCP / OpenCascade

CadQuery is a Python parametric CAD library built on OCP bindings to the OpenCascade kernel. Its documented strengths include programmatic parametric construction and STEP export; it can run headlessly as a library. This fits AETHER's existing Python backend and deterministic builder model. See the CadQuery introduction: https://cadquery.readthedocs.io/en/latest/intro.html

Important compatibility point: the current AETHER owner environment is Python 3.14.8. CadQuery's current published binary-wheel support lists Python 3.9–3.12, so do **not** install it into the current Python 3.14 environment and hope it works. Run the CAD kernel in a dedicated Python 3.12 virtual environment or isolated worker. Keep the current AETHER server and optics environment intact until the worker integration is proven. See the current project installation notes: https://github.com/CadQuery/cadquery

CadQuery's constraint-based 2D sketch solver is explicitly documented as experimental and limited to line segments and arcs in the documented API. Do not make that experimental solver the foundation of AETHER's production sketch system without a dedicated reliability test. See: https://cadquery.readthedocs.io/en/latest/sketch.html

### Secondary candidate: FreeCAD / Sketcher / PartDesign

FreeCAD has a mature parametric Part Design methodology based on sequential features, and its Sketcher includes a geometric constraint solver. This makes it a serious candidate for sketch authoring and feature-history behaviour. See:

- https://www.freecad.org/features
- https://github.com/FreeCAD/FreeCAD-documentation/blob/Stable/docs/workbenches/part-design.md

FreeCAD can be run in console/headless mode, but its headless environment has GUI/view-provider limitations that must be tested for AETHER's server use. See: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Headless_FreeCAD.md

FreeCAD and other parametric CAD systems also face the topological naming problem: references to generated faces/edges can break when upstream geometry changes. The FreeCAD documentation recommends stable datum planes, axes, master sketches, and avoiding fragile references to generated faces where possible. AETHER must design around this issue rather than assume a feature tree is automatically robust. See: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Feature_editing.md

### Decision gate

Build the same small benchmark in both environments:

- constrained rectangular sketch with two holes;
- pad/extrude and pocket;
- revolved stepped shaft;
- two-component assembly with a concentric/revolute relationship;
- rebuild after changing an upstream dimension;
- B-rep validity check;
- STEP export and STEP re-import;
- stable naming/selection after recompute;
- Windows installation and headless operation.

Choose the primary kernel based on measured reliability, API stability, feature recompute, assembly support, Windows deployment, and licensing—not on a single attractive demo.

**Recommended starting direction:** keep AETHER's own document and feature graph, use CadQuery/OCP as the first B-rep construction backend, and prototype FreeCAD Sketcher as the candidate constraint solver/alternative worker. If CadQuery's solver proves insufficient, do not force it; use a proven constraint solver or FreeCAD Sketcher through a well-defined CAD worker interface.

## 3.2 Separate CAD worker process

Create an isolated CAD worker, for example:

```text
aether-lab/
  cad/
    schema/
    document/
    observations/
    reconstruction/
    constraints/
    features/
    assembly/
    validation/
    export/
  cad-worker/
    pyproject.toml       # dedicated, pinned Python 3.12 environment
    worker.py
    kernel_cadquery.py
    kernel_freecad.py    # optional spike / alternative adapter
```

The existing Python 3.14 server should communicate with the CAD worker via a local process protocol or localhost HTTP/JSON. Keep the CAD worker stateless per job at first: send a document + operation, receive a result + validation report. Later add job caching and persistent sessions after the contracts are stable.

Do not put B-rep work into the Modal T4 optics container by default. CAD boolean operations, feature recompute, and B-rep construction are CPU/kernel workloads unless profiling shows a specific accelerator opportunity. Keep Modal for the existing optics pipeline. The two subsystems should exchange B-rep-derived tessellation and provenance, not share hidden global state.

## 3.3 The AETHER CAD document must be the source of truth

Introduce a native, versioned document format such as `.aethercad` (a JSON manifest plus binary B-rep/cache payloads, packaged as a ZIP if needed).

Top-level schema:

```json
{
  "schema_version": "1.0",
  "units": "mm",
  "document_id": "stable-id",
  "source": {"image_hash": "...", "source_file": "..."},
  "observations": [],
  "parameters": [],
  "datums": [],
  "components": [],
  "features": [],
  "constraints": [],
  "joints": [],
  "validation": {},
  "provenance": {}
}
```

A component should include:

- stable component ID and human-readable name;
- semantic type (shaft, gear, housing, bracket, bearing, panel, body surface, etc.);
- coordinate system / placement;
- feature IDs that produce it;
- material/appearance metadata separate from geometry;
- engineering metadata and provenance;
- generated B-rep reference and tessellation cache version.

A feature should include:

- stable feature ID;
- operation (`Sketch`, `Pad`, `Revolve`, `Pocket`, `Hole`, `Loft`, `Sweep`, `Fillet`, `Chamfer`, `Pattern`, `Boolean`, etc.);
- input references and parameter values;
- named datum/plane/axis references;
- dependency IDs;
- recompute status and error details;
- resulting B-rep reference.

A dimension should carry:

```json
{
  "value": 24.0,
  "unit": "mm",
  "source_kind": "measured | derived | inferred | assumed | user_confirmed",
  "source_observation_ids": ["obs-..."],
  "uncertainty": {"min": 23.8, "max": 24.2},
  "confidence": 0.93,
  "status": "accepted | needs_review | rejected"
}
```

Do not silently write a guessed dimension into a field labelled measured. Preserve the image coordinates and source region that justify every measurement.

## 3.4 AETHER CAD IR, not AI-generated executable code

The Meta models should produce a typed, schema-validated **CAD intermediate representation**. They must not output arbitrary Python and ask the server to execute it.

Example IR:

```json
{
  "component": {"id": "housing-01", "kind": "bearing_housing"},
  "datums": [
    {"id": "base_plane", "type": "plane", "origin_mm": [0, 0, 0], "normal": [0, 0, 1]},
    {"id": "shaft_axis", "type": "axis", "origin_mm": [0, 0, 12], "direction": [0, 0, 1]}
  ],
  "features": [
    {"id": "sketch-01", "type": "sketch", "plane_ref": "base_plane", "geometry": [], "constraints": []},
    {"id": "pad-01", "type": "pad", "profile_ref": "sketch-01", "length_mm": 18.0},
    {"id": "bore-01", "type": "hole", "axis_ref": "shaft_axis", "diameter_mm": 8.0, "depth": "through_all"}
  ]
}
```

The deterministic builder maps each allowed operation to kernel API calls. Validate schema, units, numeric ranges, reference existence, dependency order, and operation compatibility before executing anything.

---

# 4. New drawing-understanding pipeline

The current reading step is useful but must change its output. It should no longer jump directly from image boxes to “a gear at this box” or “a car as a solid hull.” It must create a rich set of observations first.

## 4.1 Input calibration and page analysis

1. Preserve the original upload and its cryptographic hash.
2. Detect page boundaries, crop, skew, rotation, scan perspective, and view regions.
3. Normalize contrast and line width without destroying hidden-line conventions, centerlines, dimensions, or hatching.
4. Detect title block, drawing number, units, scale, projection symbol, revision, and notes.
5. Determine whether views are orthographic, isometric, section views, detail views, exploded views, or photographs.
6. Ask the user to confirm projection convention if it is ambiguous. Never infer first-angle vs third-angle silently.

## 4.2 Extract geometric observations

Use classical computer vision for measurable pixel geometry and Meta models for semantic understanding. Keep these responsibilities separate.

Observations should include:

- line segments, arcs, circles, ellipses, splines, closed profiles;
- centerlines and axes;
- visible edges, hidden edges, section lines, break lines, hatching;
- dimension lines, extension lines, arrowheads, tolerance symbols, diameter/radius symbols;
- repeated-hole patterns, symmetry, pitch circles, gear teeth, fastener patterns;
- view identity, view scale, and coordinate transform;
- text labels, part numbers, callouts, section references;
- confidence, source bounding box, source pixels, and model-space candidates.

Each observation is a geometric or textual fact, not yet a CAD feature.

## 4.3 Cross-view association

Match the same physical edge, circle, hole axis, shaft center, or feature between views. Use geometric consistency and projection transforms. Build a graph in which observations in different views may refer to the same 3D entity.

Examples:

- A circle in the front view plus two parallel lines in the side view may describe a cylinder.
- A rectangle in one view and an identical profile in another may indicate an extrusion.
- Concentric circles plus a section view may define a turned/bored part.
- A centerline crossing two circles may define two axes and a possible gear-train plane.
- A dimension stated once may constrain the same entity in multiple projections.

If two views disagree beyond drawing tolerances, do not average away the conflict. Mark it and show the conflict to the user.

## 4.4 AI roles

Use models as specialists, not as the geometry kernel:

- **Drawing analyst:** extracts semantic labels, view roles, callouts, and possible component identities.
- **Mechanical design analyst:** proposes likely feature families and component relationships from evidence.
- **Alternative-hypothesis analyst:** independently proposes competing interpretations for ambiguous geometry.
- **CAD planner:** maps accepted observations to typed CAD IR.
- **Verification engineer:** checks whether the proposed CAD features satisfy dimensions, projections, and assembly rules.

A deterministic verifier decides whether the output passes. A model cannot approve its own result merely by saying it is correct.

Use agreement between models as one signal, not as ground truth. Record disagreements and evidence.

---

# 5. Reconstruction algorithms: do not force every drawing through one method

The correct representation depends on the object and the information available.

## 5.1 Mechanical prismatic parts

For brackets, plates, mounting blocks, covers, and many housings:

1. Reconstruct a constrained 2D sketch from the best-defined view.
2. Infer/measure the extrusion direction and thickness from another view or dimension.
3. Build `Sketch -> Pad/Extrude`.
4. Add pockets, counterbores, slots, holes, bosses, ribs, and fillets as separate features.
5. Validate projected outlines and all dimensions.

If thickness is not shown, the feature cannot be treated as measured. Use an explicit assumed range and expose it to the user.

## 5.2 Rotational parts

For shafts, bushings, rollers, pins, pulleys, and turned components:

1. Detect the axis/centerline.
2. Extract a half-profile from the section or side view.
3. Reconstruct a constrained axial profile.
4. Build `Sketch -> Revolve`.
5. Add bores, grooves, threads, shoulders, chamfers, and retaining features as separate features when supported by evidence.

This produces cylindrical/conical/toroidal surfaces rather than approximating every round surface with many flat triangles.

## 5.3 Gears and mechanisms

Keep and improve the gear work already present in `engine/geometry.py` and `engine/rebuild.py`, but move the final solid to the CAD kernel.

- Infer tooth count only when it can be supported by the drawing resolution or an explicit annotation.
- Determine module, pressure angle, addendum/dedendum, bore, face width, and profile shift from dimensions/standards/user confirmation; do not silently assume every default gear is a standard unshifted spur gear.
- Preserve the existing gear mesh check as a preliminary analytic check, then add true CAD contact/interference analysis.
- Define assembly joints explicitly: concentric, revolute, fixed, slider, planar, gear relation, and other required types.
- Solve component placement from joints and dimensions; report remaining degrees of freedom.
- Run collision/interference and clearance checks.

## 5.4 Single-view machine reconstruction

A single view generally does not reveal depth. The new pipeline should:

1. Read all visible parts and axes.
2. Generate possible component classes and feature templates.
3. Infer candidate depths/thicknesses from known standards, similar parts, labels, and engineering relationships.
4. Build more than one candidate when the depth interpretation is materially ambiguous.
5. Show which values came from the drawing and which were inferred.
6. Ask the user to approve or edit the key missing dimensions before a model is promoted beyond `Draft inference`.

The current `_spark_complete()` + `rebuild.rebuild()` approach is a useful proposal generator, but should not be the final geometry authority. The replacement should convert the proposals into a constraint graph and CAD IR, then run a deterministic solve and validation pass.

## 5.5 Three-view car or freeform product reconstruction

A car body is not a normal extrusion and should not be treated as a generic visual hull.

For a car-like object, use a surface-reconstruction workflow:

1. Identify the main body envelope, symmetry plane, front/rear, wheelbase, wheel centers, roof, hood, deck, windows, fenders, bumpers, and other semantic regions.
2. Associate those features across side/top/front views.
3. Establish longitudinal station planes along the vehicle length.
4. Propose cross-sections from the available top/front/side evidence and semantic priors.
5. Fit smooth section curves and construct NURBS/lofted surface patches for hood, roof, side body, fenders, and other panels.
6. Keep panel boundaries as named 3D curves/surface features rather than cutting a voxel hull into arbitrary mesh patches.
7. Check surface continuity across patch boundaries (position, tangent, and where required curvature continuity).
8. Validate all projected silhouettes against every source view.
9. Expose uncertain sections and inferred surface regions for user correction.
10. Create solid thickness/inner surfaces only when required and justified; otherwise mark the body as a surface model, not a closed solid suitable for manufacturing.

Three silhouettes do not contain enough information to uniquely recover every surface. AETHER must use explicit priors and user review rather than claim that the mathematically unique original design has been recovered.

## 5.6 Architecture and other disciplines

Do not make “master architect and engineer” one universal prompt or one geometry heuristic. Mechanical CAD, architectural/BIM, industrial design, and organic product surfaces need different ontologies, constraints, materials, and validation.

Keep the core document/kernel generic, but introduce domain-specific recognizers and feature planners as separate modules. Add an architecture/BIM workflow only after the mechanical CAD pipeline passes its own quality gates.

---

# 6. Feature builder and assembly architecture

## 6.1 Feature library, first release

Implement reliable, deterministic operations in this order:

**Sketch and datum layer**

- datum plane, axis, coordinate system;
- line, arc, circle, slot, rectangle, polygon, spline;
- coincidence, horizontal, vertical, parallel, perpendicular, tangent, concentric, equal, symmetry, distance, angle, radius, diameter, fixed, and construction geometry;
- dimensional constraints with units and tolerance.

**Solid feature layer**

- pad/extrude;
- revolve;
- pocket/cut-through;
- hole, counterbore, countersink;
- loft;
- sweep;
- shell/thickness;
- rib/web;
- linear/circular pattern;
- mirror;
- fillet/chamfer;
- Boolean union/cut/common;
- gear-specific feature generator.

Keep fillets/chamfers late in the feature sequence where possible because they are often more fragile when upstream geometry changes.

## 6.2 Stable feature references

Do not base every feature on fragile face numbers such as `Face7` or `Edge14` from a previous operation. Use stable named datums, master sketches, axes, planes, construction geometry, and semantic references wherever possible. Store the geometric selection rule and the resolved kernel reference, and detect/recover from topological naming changes.

This is a known general CAD problem, not a FreeCAD-only defect. FreeCAD's documentation provides good guidance on using datum geometry and master sketches rather than attaching everything to generated faces: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Feature_editing.md

## 6.3 Assembly model

An assembly is not merely parent/child transforms. It must contain:

- separate component documents/B-rep solids;
- coordinate systems and placements;
- joints and joint frames;
- fixed, revolute, slider, planar, cylindrical, ball, and gear relationships as appropriate;
- degrees of freedom and solver residuals;
- interference and clearance reports;
- exploded-view directions independent of the physical solved placement;
- constraints labelled as measured, inferred, or user-defined.

Do not report a machine as mechanically operable just because two gear circles appear to touch. Require correct axes, center distance, tooth/module compatibility, face overlap, gear phasing, and interference/contact checks appropriate to the mechanism.

---

# 7. B-rep construction, validation, and export

## 7.1 B-rep validation gates

For every generated component, check:

- the kernel shape is non-null;
- expected number of solids is present;
- every solid is topologically/geometrically valid;
- shells and wires are closed and correctly oriented where required;
- no unintended self-intersections or invalid faces;
- volume is positive and finite for closed solids;
- bounding box and key dimensions are plausible;
- all dimensional and geometric constraints are within tolerance;
- feature recompute succeeds and dependencies remain valid.

OpenCascade provides `BRepCheck_Analyzer` for checking the validity of shapes and their subshapes. This is necessary but not sufficient: a valid B-rep can still be the wrong part or fail to match the drawing. See: https://www.occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html

## 7.2 STEP becomes the primary engineering export

Add:

- `.step` / `.stp` as the primary neutral CAD exchange output;
- `.aethercad` as the native editable project, preserving feature graph, observations, source drawing, dimensions, constraints, provenance, and CAD kernel data/cache;
- `.glb` as the viewport/AR/web visualization derivative;
- `.stl` as a tessellated manufacturing/printing derivative, with an explicit note that mesh export discards parametric history.

OpenCascade's STEP translator supports writing STEP and can include assembly/product structure, colors, visibility, and validation properties through the appropriate writer interface. See: https://occt3d.com/dev/doc/overview/html/occt_user_guides__step.html

Round-trip every STEP export: export -> import into a fresh CAD document -> re-run B-rep checks -> compare volume, bounding box, component count, and important dimensions within declared tolerances.

## 7.3 Rendering is downstream of CAD

The Three.js viewport remains. It should receive adaptive tessellation generated from B-rep faces using configurable chordal and angular deflection. The mesh cache is disposable and regenerated when the B-rep or tessellation settings change.

Normals should be generated with cross-component boundary awareness. The current export computes normals per mesh fragment, which can create shading seams between adjacent mesh pieces. In the new architecture, use B-rep face normals and a controlled tessellation/material policy, preserving real sharp edges and smoothing genuinely continuous surfaces.

The optics engine should sample surfaces from the B-rep-derived tessellation. It must not reconstruct CAD from the optical mesh.

---

# 8. Validation strategy: “reliable” must be measurable

AETHER must stop treating one successful render or a high silhouette score as proof of CAD correctness.

## 8.1 Build a ground-truth benchmark

For every benchmark item, store:

- original source drawing(s);
- known dimensions and tolerances;
- ground-truth STEP or native CAD reference when available;
- annotated components/features and view correspondence;
- expected assembly relationships;
- ambiguity labels for intentionally missing information;
- a held-out evaluation flag.

Start with several part families:

1. plate/bracket with holes and pockets;
2. turned shaft with steps, grooves, and bore;
3. bearing housing with a bore and mounting features;
4. gear pair and simple mechanical assembly;
5. multi-view freeform body such as the car input;
6. at least one single-view underdetermined case with known ground truth and known missing dimensions.

The car must be one quality benchmark, not the only benchmark.

## 8.2 Metrics

**CAD kernel / topology**

- B-rep validity pass rate;
- valid solid count;
- feature recompute pass rate;
- failed references after upstream parameter edits;
- STEP round-trip pass rate.

**Dimensional correctness**

- dimension residuals against stated dimensions;
- relative error of known lengths, diameters, radii, and angles;
- constraint residual and tolerance compliance.

**Drawing consistency**

- projection silhouette IoU per view;
- symmetric contour distance / Hausdorff-style error;
- dimension-line and centerline correspondence;
- edge/feature correspondence, not just filled silhouette overlap.

**Surface quality**

- analytic surface type distribution (plane/cylinder/cone/sphere/torus/NURBS);
- curvature continuity across intended smooth patch boundaries;
- adaptive tessellation chordal/angular error;
- surface fold/self-intersection checks;
- mesh normal continuity for display output.

**Assembly quality**

- constraint residuals;
- unresolved degrees of freedom;
- joint satisfaction;
- component interference and minimum clearances;
- gear contact and phasing checks.

**Uncertainty quality**

- fraction of dimensions correctly labelled measured/derived/inferred/assumed;
- coverage of user-confirmed values;
- frequency of hidden dimensions incorrectly presented as facts;
- reliability calibration of model confidence.

## 8.3 Required regression tests

Add tests for:

- sketch fully constrained / under-constrained / over-constrained cases;
- pad/pocket/revolve/loft recompute after changing upstream dimensions;
- stable datum references after profile changes;
- invalid sketch loops and self-intersecting profiles;
- B-rep validity and closed-solid integrity;
- assembly constraint solve and degrees of freedom;
- collision/interference detection;
- STEP export/re-import equality within tolerances;
- GLB tessellation visually consistent with the B-rep;
- drawing projection residual across every view;
- a fixed car regression with surface continuity checks;
- missing dimension tests where AETHER must ask/label assumptions rather than fabricate certainty.

Keep the existing 36 physics tests. Add CAD tests as a separate suite so optics passing does not imply CAD passing.

---

# 9. Migration plan: staged execution with acceptance gates

Do not ask Claude to rewrite the whole repository in one cloud task. Implement one stage at a time, keep the current application runnable, and require the gate below to pass before moving on.

## Phase 0 — Freeze the baseline and create a reconstruction case file

**Tasks**

1. Create a dedicated branch, for example `feature/true-cad-kernel`.
2. Preserve the current visual reconstruction implementation unchanged under a clearly named legacy route.
3. Add the exact original image used to generate the bad car model, not a Blender screenshot.
4. Preserve its image hash, model export, model report, current run JSON, current reading JSON, and screenshots of the output.
5. Identify whether the image is a three-view drawing, single-view drawing, or photo. Do not use `test.jpg` (the screenshot) as the original drawing unless it actually is the original source.
6. Capture the current baseline metrics and known defects from `docs/RESULTS.md`.

**Acceptance gate**

A reproducible case folder can rerun the same current pipeline and produce the known baseline. No existing optics or interaction features are removed.

## Phase 1 — CAD kernel technology spike

**Tasks**

1. Create a separate Python 3.12 environment for CadQuery/OCP; do not change the current Python 3.14 server environment.
2. Prototype the same plate, shaft, bearing housing, gear, and assembly in CadQuery/OCP.
3. Prototype sketch constraint use; measure whether the documented CadQuery sketch solver is adequate. It is explicitly experimental, so do not assume it is production-ready.
4. In parallel, test FreeCAD/Sketcher/PartDesign headless for constrained sketching and feature recompute.
5. Run B-rep validity checks and STEP round trips on both.
6. Test Windows install, process startup, error handling, resource usage, and repeated rebuild stability.
7. Record a decision matrix and select the backend.

**Acceptance gate**

A command-line worker creates a real B-rep plate with holes, a revolved shaft, and a two-component assembly; validates them; exports STEP; re-imports the STEP; and reports dimensions/volume within tolerance. The worker starts reliably on Windows without changing the current AETHER environment.

## Phase 2 — Native AETHER CAD document and IR

**Tasks**

1. Define a versioned `.aethercad` schema.
2. Implement stable IDs for document, components, features, sketches, datums, dimensions, observations, constraints, and joints.
3. Implement the measured/derived/inferred/assumed/user-confirmed provenance model.
4. Implement feature dependency graph and topological recompute order.
5. Implement strict schema validation and unit validation.
6. Add serialization, migration, undo checkpoints, and corrupted-document recovery.
7. Build a simple CAD tree view in the backend before integrating drawing AI.

**Acceptance gate**

A manually authored `.aethercad` test project can be saved, closed, reopened, edited, recomputed, and STEP-exported without losing feature identities or provenance.

## Phase 3 — Deterministic CAD feature builder

**Tasks**

1. Implement datums and sketches.
2. Implement constrained line/arc/circle geometry.
3. Implement pad, revolve, pocket, hole, loft, sweep, pattern, mirror, fillet, chamfer, shell, and Boolean operations.
4. Add named datum-based references; avoid raw face-index dependencies.
5. Implement deterministic builders for standard mechanical components (gear, shaft, bearing, pulley, link, housing, bracket).
6. Store feature inputs and outputs, plus kernel errors and validation status.
7. Create adaptive tessellation from B-rep for the Three.js viewport.

**Acceptance gate**

A human-created test part has a readable feature history, can be edited by changing dimensions, rebuilds deterministically, remains valid, and produces a matching STEP and GLB preview.

## Phase 4 — Drawing observation extraction

**Tasks**

1. Build page rectification and drawing calibration.
2. Detect and classify views and projection convention.
3. Extract lines, arcs, circles, centerlines, hidden lines, section hatching, dimensions, tolerances, and annotations.
4. Associate geometric observations across views.
5. Store every observation with source-image coordinates, coordinate transform, confidence, and evidence links.
6. Use Muse Spark / SAM to propose semantic identities, but keep measured vector geometry in a separate observation layer.
7. Add a review overlay allowing a user to accept/fix a detected edge, dimension, centerline, or view assignment.

**Acceptance gate**

AETHER can produce a structured drawing observation file for benchmark sheets with correct view roles, dimensions, centerlines, and feature candidates. It must show uncertainty instead of hiding failed detections.

## Phase 5 — CAD reconstruction solver for prismatic and rotational parts

**Tasks**

1. Build feature hypotheses from observations.
2. Generate constrained sketches from dimensioned profiles.
3. Solve extrusion depth, axis, radius, bore, and feature positions across views.
4. Build B-rep features using the deterministic feature builder.
5. Compare projected B-rep geometry against every source view.
6. Reconcile dimensions and constraints; surface conflicts.
7. Maintain candidate alternatives if multiple models fit the same image.

**Acceptance gate**

On the benchmark set, dimensioned plates, brackets, shafts, bores, and bearing housings produce valid editable CAD feature trees with defined drawing/dimension residual thresholds. No guessed dimension may be mislabelled measured.

## Phase 6 — Mechanical assembly reconstruction

**Tasks**

1. Detect component identities and part boundaries.
2. Generate separate part documents and assembly coordinate systems.
3. Infer joints from axes, holes, contact faces, bearings, pins, and gear geometry.
4. Solve assembly placements and degrees of freedom.
5. Run interference, clearance, and contact checks.
6. Use existing `interpret.py` and `rebuild.py` rules as candidate-generators, not final geometry generators.
7. Use Muse Wonder to propose alternatives and missing parts, but require evidence or explicit “assumed” status.

**Acceptance gate**

A known assembly is reconstructed into individual valid B-rep components with correct joint types, solved positions, reported degrees of freedom, and no unexplained interference. The assembly can be edited and recomputed.

## Phase 7 — Freeform product surfaces (car body)

**Tasks**

1. Add a freeform surface ontology separate from mechanical prismatic feature recognition.
2. Identify symmetry, stations, section curves, wheel centers, roof/hood/deck boundaries, fenders, windows, and body panel regions.
3. Build section-driven loft/NURBS patches rather than a silhouette-intersection solid.
4. Enforce intended G0/G1/G2 continuity across patches where appropriate.
5. Check projected surfaces against side/top/front views.
6. Add explicit user-editable section stations and control curves.
7. Convert to a closed solid only when a defensible inner surface/wall thickness exists; otherwise call it a surface model.
8. Add real car reference CAD to a held-out test set. Do not tune on the held-out reference after viewing the results.

**Acceptance gate**

The same car input generates a patch-based, editable CAD surface model with controlled smoothness, no visible unintended slabs, stable component boundaries, and quantified projection/surface errors against ground truth. It must beat the old visual-hull baseline on surface metrics, not only on silhouette score.

## Phase 8 — UI, editing, and exports

**Tasks**

1. Extend the current outliner into a Feature Tree and Assembly Tree.
2. Add editable sketches, dimensions, constraints, datum planes, feature parameters, and component joints.
3. Add a review mode for unresolved/assumed geometry.
4. Keep the current orbit, section, explode, isolate, selection, hand, and holographic controls.
5. Replace mesh-authoritative scene objects with B-rep-backed CAD components; tessellate only for viewport rendering.
6. Add Save/Open `.aethercad`, Export STEP, Export GLB, Export STL, and a detailed build/validation report.
7. Add autosave, recovery after kernel failure, operation rollback, and deterministic undo/redo around feature transactions.

**Acceptance gate**

A user can open a CAD document, inspect the feature tree, edit a sketch/dimension, recompute, inspect the assembly, and export STEP. Re-imported STEP remains valid and matches the source model within tolerance.

## Phase 9 — Production reliability and quality release

**Tasks**

1. Run all existing optics tests and the separate CAD suite.
2. Add held-out drawings and ground-truth CAD; do not tune on the held-out set.
3. Run repeated recomputes, parameter perturbations, save/reopen cycles, and STEP round trips.
4. Add crash recovery and corrupted B-rep handling.
5. Profile large drawings and assemblies; optimize only after correctness is established.
6. Publish the supported feature matrix and known limitations.
7. Require a validation report before users can label a model engineer-reviewed.

**Acceptance gate**

CAD release thresholds are published and met on the held-out benchmark. Every output is traceable, reproducible, and has a clear validation status.

---

# 10. Suggested repository structure after migration

```text

aether-lab/
  agent.py                       # conversation/orchestration; delegates to CAD planner
  vision.py                      # image loading, segmentation, CV utilities
  server.py                      # HTTP API and user session
  compute.py                     # existing Modal/optics routing
  engine/                        # retain optics engine and legacy mesh utilities
  cad/
    document.py                  # native document model
    schema.py                    # typed IR validation
    provenance.py                # measured/inferred/assumed evidence
    observations/
      calibration.py
      views.py
      dimensions.py
      primitives.py
      annotation.py
      association.py
    reconstruction/
      planner.py
      prismatic.py
      rotational.py
      assembly.py
      freeform.py
      uncertainty.py
    constraints/
      sketch.py
      dimension.py
      assembly.py
      solver_adapter.py
    features/
      sketch.py
      pad.py
      revolve.py
      pocket.py
      hole.py
      loft.py
      sweep.py
      fillet.py
      chamfer.py
      patterns.py
      gear.py
    kernel/
      protocol.py
      cadquery_adapter.py
      freecad_adapter.py         # only if chosen/needed
    validation/
      brep.py
      dimensions.py
      projections.py
      surface.py
      assembly.py
      export_roundtrip.py
    export/
      step.py
      glb.py
      stl.py
      aethercad.py
  cad-worker/                     # isolated Python 3.12 CAD runtime
  ui/src/
    scene/                        # Three.js renderer fed from CAD tessellation
    cad/                          # feature tree, sketch editor, constraints, review UI
    ui/                           # retain/rework existing panels
  tests/
    cad/
      kernel/
      features/
      constraints/
      drawing_benchmarks/
      assembly/
      exports/
    physics/                      # keep existing optics validation
```

Names are illustrative; do not perform a mass file move until the new architecture is working and testable.

---

# 11. What must happen to the existing code

| Existing file/module | Decision | Reason |
|---|---|---|
| `agent.py` | Keep orchestration; replace final drawing-build call with CAD IR planning/validation | AI routing and Meta integration remain useful |
| `vision.py` | Keep and extend | SAM/image parsing remains useful, but needs geometric observations and calibration |
| `engine/interpret.py` | Reuse as candidate recognizer; do not treat its output as finished CAD | Box/type heuristics are useful proposals, not exact features |
| `engine/rebuild.py` | Gradually retire as authoritative builder; port validated gear/layer rules into new CAD feature and assembly services | It guesses depths/thicknesses and creates mesh specs |
| `engine/sheet.py` | Keep optional visual-hull preview; replace final three-view CAD output with feature/surface reconstruction | It currently creates a visual hull and triangle mesh |
| `engine/hull.py` | Keep for preview/optical geometry experiments; not final CAD authority | Voxel hull is not design-intent CAD |
| `engine/segment.py` | Reuse for panel/region observations, not as the method of producing separate CAD components | Triangle region split is not a component feature model |
| `engine/outline.py` | Reuse vectorization utilities; route profiles to CAD sketch/B-rep construction | Existing extrusion is triangle mesh |
| `engine/geometry.py` | Keep for optics/sample mesh and primitives where useful; add CAD-kernel-backed feature builders | Current builders return V/F meshes |
| `engine/quality.py` | Keep mesh quality metrics for tessellation; add B-rep and surface quality checks | Current checks don't certify CAD intent or B-rep validity |
| `engine/lab.py` | Evolve scene state to reference CAD documents/components and provide tessellated meshes to optics/UI | Current scene parts are param/mesh dictionaries |
| `engine/export.py` | Replace/extend with STEP + `.aethercad`; GLB/STL become derived export adapters | Current GLB/STL only export meshes |
| `ui/src/scene/Viewport.jsx` | Keep rendering/interaction; feed from B-rep tessellation and expose CAD selection IDs | Three.js remains suitable as display layer |
| `ui/src/store.js` | Extend to document/feature state, transaction/recompute state and validation results | Current state mainly tracks parts/meshes |
| `ui/src/commands.js` and panels | Keep interaction model; add sketch/feature/joint/review commands | Existing Blender-like navigation/tools are reusable |
| optics modules | Keep unchanged initially | Holography is downstream of geometry and largely independent |
| `compute.py` / Modal | Keep for optics; add separate CAD worker routing | B-rep workload should not be tied to T4 optics functions |

Do not remove the old routes until the new path has passed the benchmark. Rename the old routes clearly as `Preview reconstruction (visual hull)` or `Legacy mesh reconstruction` so nobody mistakes them for CAD.

---

# 12. Master rules for Claude / any coding agent

Give the coding agent these rules before it writes code:

1. Do not patch the old visual hull and call the result CAD.
2. Do not replace the visual hull with another voxel/point-cloud/triangle-mesh technique and call it parametric CAD.
3. The authoritative model must be an editable feature graph backed by valid B-rep solids/surfaces.
4. AI outputs typed JSON IR only. Never execute model-generated Python or shell code.
5. Every dimension must be labelled with evidence and provenance.
6. If an input does not determine a dimension/surface, represent ambiguity and request confirmation or mark it assumed.
7. Three-view silhouette overlap is necessary but not sufficient. Validate feature edges, dimensions, B-rep, surface continuity, and assembly relationships.
8. Keep the optics engine, current UI interactions, and legacy route running during migration.
9. Keep the CAD kernel in an isolated, pinned environment. Do not destabilize the existing Python 3.14 environment.
10. Implement one phase at a time. Do not start Phase 4 before Phase 1 has selected and passed a kernel spike.
11. Add automated tests and a real benchmark for every new feature before merging it.
12. Never claim “manufacturing ready” unless the model has the required dimensions, tolerances, material/process information, validation, and engineer release.

## Suggested first Claude task

```text
Work only on Phase 1 (CAD kernel technology spike) of AETHER_TRUE_CAD_RECONSTRUCTION_PLAN.md.

First inspect the current repository structure and existing Python environment. Do not edit or break the existing AETHER Lab runtime. Create an isolated Python 3.12 CAD worker environment, test CadQuery/OCP on Windows, and separately evaluate whether FreeCAD/Sketcher headless is viable for AETHER's server use.

Create automated proof cases for: (1) a dimensioned plate with two holes, (2) a revolved stepped shaft, (3) a bearing housing with a through-bore and mounting holes, (4) a two-component concentric assembly, (5) an upstream parameter change and recompute, (6) B-rep validation, (7) STEP export/re-import, and (8) stable feature references after edit.

Record exact versions, install commands, failures, timings, kernel checks, and STEP round-trip comparisons in cad-worker/TECH_SPIKE.md. Do not modify the existing drawing-to-mesh pipelines yet. Do not claim success based only on screenshots; the tests and STEP round trip must pass. Stop after Phase 1 and report the evidence plus a recommendation for the primary kernel and sketch constraint approach.
```

---

# 13. Acceptance criteria for the ultimate result

AETHER Lab should not be declared “true CAD” until all of the following are demonstrated:

- The same input drawing produces a native `.aethercad` file with components, features, sketches, parameters, constraints, and provenance.
- At least one representative part is created from sketches and exact CAD features, not only a mesh.
- Dimensions explicitly stated in the drawing are satisfied within the drawing's tolerance or flagged as conflicting.
- Missing values are visibly marked inferred/assumed and can be edited.
- Recomputing after parameter changes preserves valid feature dependencies or gives a clear repair workflow.
- Each component passes the CAD kernel's B-rep validation.
- Assemblies expose joints, degrees of freedom, and interference/clearance results.
- All source views are projected from the resulting CAD and compared with the drawing.
- STEP exports re-import successfully into a fresh CAD document and match key geometry within tolerances.
- GLB rendering is derived from the CAD model and visibly matches it.
- The holographic/optical engine uses a tessellation derived from the CAD, without becoming the source of geometric truth.
- The held-out benchmark is evaluated without tuning on the held-out drawings.
- A technical report distinguishes measured, derived, inferred, and assumed model content.

“Reliable like Blender” should mean dependable application behaviour—stable editing, undo/redo, document recovery, selection, export, predictable rendering, and useful error messages—not that AETHER can infer unknowable dimensions. Blender is primarily a digital content creation tool; AETHER's target is an engineering CAD workflow. The geometry kernel, validation, and feature history are what make that distinction real.

---

# 14. Final recommendation

The immediate next move is **not** to rewrite `sheet.py`, `hull.py`, or `geometry.py` in place. It is to complete the isolated kernel spike and agree on the native AETHER CAD document/IR contract.

Once the kernel spike passes, build one narrow end-to-end path first:

**dimensioned three-view bracket -> observations -> constrained sketch -> pad -> holes/pockets -> valid B-rep -> STEP -> re-import validation -> Three.js preview.**

That is the first proof that AETHER has crossed from drawing-to-mesh into actual CAD. Then extend the same architecture to gears/assemblies, single-view machines, and finally freeform car bodies. This staged path creates a reliable engineering foundation instead of another impressive-looking but structurally limited mesh demo.

## External technical references

- CadQuery introduction and OCP/OpenCascade foundation: https://cadquery.readthedocs.io/en/latest/intro.html
- CadQuery install/runtime compatibility notes: https://github.com/CadQuery/cadquery
- CadQuery sketch API and experimental constraint solver warning: https://cadquery.readthedocs.io/en/latest/sketch.html
- CadQuery assembly constraints: https://cadquery.readthedocs.io/en/latest/assy.html
- FreeCAD PartDesign feature-based modelling: https://github.com/FreeCAD/FreeCAD-documentation/blob/Stable/docs/workbenches/part-design.md
- FreeCAD feature-reference stability guidance: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Feature_editing.md
- FreeCAD headless/console operation: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Headless_FreeCAD.md
- OpenCascade B-rep validation (`BRepCheck_Analyzer`): https://www.occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html
- OpenCascade STEP translator: https://occt3d.com/dev/doc/overview/html/occt_user_guides__step.html
