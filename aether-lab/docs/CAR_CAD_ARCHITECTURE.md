# AETHER Lab — Three-view car → parametric OpenCascade CAD

**Architecture and test strategy only. Nothing in this document is implemented yet.**
Target input: the car three-view sheet (`car_three_view`, the drawing that produced the visual-hull model shown in `test.jpg`).
Date: 1 Nov 2026.

Every statement is tagged:

- **[FACT-CODE]**: confirmed by reading the current repository.
- **[FACT-SHEET]**: measured on the sheet in this session (method stated).
- **[FACT-KERNEL]**: confirmed by running the kernel in this session.
- **[DESIGN]**: a proposed decision, not yet built or tested.
- **[OPEN]**: unresolved. It needs your decision or more evidence.

---

## 0. Input and provenance

| Item | Status |
|---|---|
| File used for this analysis: the image uploaded in chat, saved as `aether-lab/tests/inputs_local/car_three_view.webp` (884 × 1125 px, RGB, sha256 `a98506a4301e30ad…`) | [FACT-SHEET] |
| `tests/inputs_local/` is gitignored, like `tests/car_three_view.gif` already is (third-party brand image, internal use only) | [FACT-CODE] |
| The legacy pipeline was run on `tests/car_three_view.gif`. It is not known whether the uploaded webp has the same pixels as that GIF (webp may be a re-encode). | [OPEN-1] |
| `test.jpg` is used only as the "before" picture of the visual-hull failure, never as geometry evidence. `aether-model.glb` (106 mesh "sheet region" nodes) is the legacy output and is **not** used as evidence. | [DESIGN] |

The benchmark must name one canonical file and record its hash. All measurements below are on the webp.

---

## 1. What the sheet actually contains

### 1.1 Views and layout [FACT-SHEET]

Method: Otsu-style ink threshold (gray < 128), row/column ink profiles with a 40 px margin to ignore the stippled paper border, long horizontal ink runs for ground lines, and `engine/circles.find` for the wheels. Coordinates are sheet pixels, origin top-left.

| View | Box (x0, y0, x1, y1) px | Size | Ground line | Notes |
|---|---|---|---|---|
| Side | 91, 123, 800, 312 | 709 × 189 | y = 312–313, x 91–799 | Nose to the **left**. |
| Front | 89, 381, 433, 561 | 344 × 180 (incl. mirrors) | y = 561–562 | Identified as front by headlights, badge on bonnet and grille mesh. Centre x = 261. |
| Rear | 459, 379, 802, 561 | 343 × 182 (incl. mirrors) | y = 561–562 (shared) | Identified as rear by four exhaust tips, plate recess and louvres. Centre x = 630.5. |
| Top (plan) | 92, 639, 797, 993 | 705 × 354 incl. mirrors; **body 310** | none | Nose to the **left**, same as the side view. Centreline y = 816. |

- **Layout:** this is a styling-blueprint layout, not an ISO first- or third-angle sheet. Side view on top, front and rear side by side, plan view at the bottom. View roles therefore cannot come from position rules; they come from semantic evidence plus confirmation.
- **Dimensions:** none. There are no dimension lines, scale bar, title block or units. Every size in mm is therefore unmeasured until a real dimension is supplied (see 5.1).

### 1.2 Cross-view consistency [FACT-SHEET]

| Relation | Values | Agreement |
|---|---|---|
| Length: side vs top | 709 vs 705 px | 0.6 %. Same scale. |
| Height: side vs front vs rear (roof to ground) | 189 vs 180 vs 182 px | **side is 4–5 % taller** |
| Width: top body max vs front/rear outer tyre faces | 310 vs 298 px | end views 3.9 % narrower. Not a clean test, because the fender may be wider than the tyres. |
| Height and width together | 180/189 = 0.952; 298/310 = 0.961 | Consistent with the **end views being drawn ≈ 4–5 % smaller** than the side and top views. |

The legacy `sheet.match()` scores this as a size disagreement and averages it away [FACT-CODE: `_sheet_to_design` reports `size_disagreement_pct`]. The new pipeline must **not** average it [DESIGN]. Section 4.2 explains how.

### 1.3 Measured quantities (px, before scale) [FACT-SHEET]

| Quantity | Value | Source |
|---|---|---|
| Front wheel centre (side view) | (258, 256), tyre r = 53 | circle fit, support 1.0 |
| Rear wheel centre (side view) | (669, 254), tyre r = 57 | circle fit, support 1.0 |
| Wheelbase | 411 px (side scale) | rear − front centre |
| Rim lip radius (front and rear) | 43.6 / 43.6 | inner ring of the same fit |
| Other rings | 33.9 (both); 19.6 / 20.6 | inner rim step or brake disc? hub area [OPEN] |
| Front tyre faces (front view, y = 552) | x 112–161 and 361–410 → width ≈ 49, track (tyre centres) 249 | end-view scale |
| Rear tyre faces (rear view) | x 481–530 and 730–779 → width ≈ 49, track 249 | end-view scale |
| Overhangs (side) | front 167 px, rear 131 px | nose / tail to axle |
| Plan half-width profile (top view, body only) | 310 at x 260–340 and 660–700 (front and rear wheels), 292 at x 460–540 (doors) | column spans |
| Side roof profile peak | y = 123 at x ≈ 455 | column spans |

What these show:

- **The drawing shows different tyre sizes.** Outer radii differ (53 vs 57) while the rims are identical (43.6). That means different tyre sidewalls, not a fitting error. The reconstruction keeps front and rear tyres as **separate parameters**.
- **The plan view shows fender flares.** The body is 6 % wider at the axles than at the doors. The sections must vary in width; a constant cross-section would be wrong.
- **Tyre width does not differ in the drawing** (49 px front and rear). The illustrator drew them equal. We follow the drawing and record this as drawing-sourced, not corrected with outside knowledge.

### 1.4 Overlay

The measurement overlay (view boxes, ground lines, wheel circles, tyre faces, centrelines) is saved in the session scratchpad as `car_sheet_measured.png`. It is a derivative of a brand image, so it does not go in the repo.

---

## 2. Component inventory for this sheet

Read from the four views in this session by inspection plus the measurements above. In the implementation this inventory becomes a **typed observation file**: Muse Spark proposes it as strict JSON and you confirm it. No AI-written code is executed. The table is the expected answer that the interpretation stage is tested against.

Legend:

- **Role:** B = separate body / assembly component, F = feature of a body, R = face region (imprinted edges on a body face, no own volume).
- **Confidence:** H / M / L.

| # | Component | Evidence (views) | Geometric type | CAD representation | Role | Known (px) | Inferred / assumed | Conf. | Construction strategy |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Main body shell (exterior envelope) | all 4 | doubly-curved freeform | closed B-rep solid from NURBS lofts | B | length 709, plan width profile, side top/bottom profiles, end-view envelopes | section shapes between end views; interior not modelled | H (outline), M (sections) | section-driven loft (§3) |
| 2 | Greenhouse / cabin (windscreen, roof, rear glass to engine cover) | side, front, rear, top | freeform, narrower than body (tumblehome) | second loft fused to the body | F (Boolean fuse into 1) | roof profile (side), windscreen trapezoid (front), roof width ≈ 121 px at top (front) | tumblehome angle between the drawn end-view lines | M | loft on the beltline, fused |
| 3 | Front wheel arch ×2 | side (arch line around tyre) | cylindrical cut | Cut feature: cylinder about the front axle datum, radius = arch radius | F | axle centre; arch radius (to measure) | arch depth into body (inner wheel-well wall) | H position, L depth | Boolean cut |
| 4 | Rear wheel arch ×2 | side | as #3 | as #3 | F | as #3 | as #3 | H / L | Boolean cut |
| 5 | Front wheel ×2 (tyre + rim) | side (full face), front (tyre faces), top (hidden) | revolved + patterned | **Separate solids:** tyre (revolve of a tyre section), rim (revolve of barrel/lip profile + 5 Y-spokes as an extruded sketch, polar pattern ×5) + 5 lug bosses (pattern) + centre cap | B | r_tyre 53, r_rim 43.6, width 49 (end scale), track 249 | tyre section shape, spoke depth/offset, rim barrel inner radius | H overall, M spokes, L section | revolve, extrude, polar pattern, cut |
| 6 | Rear wheel ×2 | side, rear | as #5 | as #5, own parameters | B | r_tyre 57, r_rim 43.6, width 49 | as #5 | H / M / L | as #5 |
| 7 | Brake disc behind spokes? | side: ring r ≈ 33.9 visible through spokes | revolved disc | optional separate solid | B | r 33.9 | thickness, offset | **L**: may just be the rim barrel step | **[OPEN-4]**: build only if confirmed |
| 8 | Exterior mirror ×2 | all 4 (the most consistent small feature) | small freeform housing + stalk | separate solid: housing loft (2–3 sections) + stalk sweep | B | position in side / front / top; housing size in front | housing depth (from top view), stalk path | H position, M shape | loft + sweep + fuse |
| 9 | Side window (DLO) | side; top (glass edge line) | region on greenhouse face | imprinted face region, glass material | R | outline in side view | none for a flush region; recess depth unknown | H | project the side-view curve along Y onto the body and split the face |
| 10 | Rear quarter window | side (small window behind door) | region | as #9 | R | outline | none | H | as #9 |
| 11 | Windscreen | front (trapezoid), top (large panel), side (A-pillar line) | region | imprinted region | R | front, top outline | none | H | split face by curve projected along Z (top view) |
| 12 | Door (shut lines) and door handle | side (door outline, handle); top (shut-line ends) | panel line; handle = small recess | door: imprinted panel line. Handle: shallow pocket (assumed depth) | R + F | door outline, handle outline | handle depth assumed | H line, L depth | split face; pocket |
| 13 | Side air intake (behind door, ahead of rear wheel) | side (triangular scoop with blade); top (cut near x ≈ 500–560) | concave recess | Cut feature (lofted cutter) | F | outline in side and top | depth into body | M | loft cutter → Boolean cut |
| 14 | Sill / side skirt blade | side (long lower line, blade above sill) | lower body break | bottom-profile break in the sections + imprinted line | F / R | side lower profile | blade overhang | M | section parameter + split |
| 15 | Front splitter / lip | side (thin forward lip at nose bottom); front (lower edge) | thin plate | separate thin solid: plan outline (top view nose) extruded by the measured thickness | B | thickness and overhang in side view | plan depth behind the bumper | M | sketch → pad |
| 16 | Front lower intakes with hex mesh (3 sections) | front (mesh areas), side (mesh triangle at nose), top (front corner slots) | recessed openings + mesh | Cut (pocket) per opening + mesh material on the floor face. Hex cells are **not** modelled one by one. | F | outlines in front view | pocket depth; mesh pattern pitch | H outline, L depth | project outline → cut |
| 17 | Headlights ×2 | front, side, top | region with inner graphic | imprinted region (+ optional 1–2 mm recess, assumed) | R | outlines in 3 views | recess | H | split face |
| 18 | Bonnet creases ×2 | front, top (two lines) | feature lines | imprinted edges | R | curves in top and front | whether they are creases or edges | M | project curve → split |
| 19 | Front badge | front, top (small emblem) | tiny region | recorded as an annotation only, no geometry (below drawing resolution, no depth) | (annotation) | position | none | H position | none. Listed so it is not silently dropped. |
| 20 | Engine cover louvres / bays | top (3 transverse bays + rear slat grille), rear (≈ 5 horizontal slats) | ribs over a recess | Pocket + linear pattern of ribs | F | bay outlines (top), slat count (rear) | rib height, pocket depth | M count, L depth | cut + pad + linear pattern |
| 21 | Rear spoiler lip / ducktail | side (tail kick-up), rear (top edge) | part of the tail surface | last body stations | F | side tail profile | none | H | sections near the tail |
| 22 | Tail-light band (with mesh) | rear (full-width band), side (tail light), top | region + shallow recess | imprinted region + mesh material | R | outline in rear view | recess | H | split |
| 23 | Rear diffuser with mesh sections | rear (lower mesh), side (rear lower fins) | recesses + fins | cut recess + fins as pads | F | rear outline, fin positions (side) | fin depth | M | cut + pad pattern |
| 24 | Exhaust tips ×4 (two twin pairs) | rear (4 circles); side (partly, at the tail) | tubes | separate solids: tube (revolve or extrude with bore) along −X | B | centres and radii in rear view | length (protrusion) | H position, L length | sketch circle → pad with a hole |
| 25 | Licence-plate recess | rear (rectangle) | shallow pocket | Cut feature | F | outline | depth | H outline, L depth | pocket |
| 26 | Rear badge / script | rear | tiny region | annotation only (as #19) | (annotation) | position | none | H | none |
| 27 | Side marker lights (small lines on front corners) | front | tiny regions | annotation only | (annotation) | position | none | M | none |

**Deliberately excluded, because the sheet does not show them** (each logged as "not modelled: no evidence"):

- Axles, suspension, underbody details: no view shows them. Wheel placement uses axle **datums** (lines), not invented axle solids.
- Interior, seats, wipers, door inner structure.
- Glass thickness and body panel thickness.

Your prompt listed axles as an example. They are not drawn, so by your own rule 1.6 they stay out unless you ask for them, and then only as "assumed".

**Low-impact ambiguities:**

- Which side of the car the side view shows, and whether the plan view is from above with the car's left at the top or the bottom. The car is symmetric in every drawn feature that matters here (the badge is centred, the exhausts are symmetric), so this does not change the geometry. It is recorded, not guessed [OPEN-5].

---

## 3. Body cross-sections: derivation and parameterisation

### 3.1 Model frame [DESIGN]

- **X** runs along the car: X = 0 at the nose tip, + towards the tail.
- **Y** is lateral: Y = 0 on the symmetry plane.
- **Z** is up: Z = 0 on the ground line.
- Units are mm; the scale is set as in §5.1.
- Datums are named and stable:
  - `PLANE_SYM` (XZ)
  - `PLANE_GROUND` (XY)
  - `AXIS_FRONT` and `AXIS_REAR`: lines parallel to Y through the wheel centres
  - `STATION_i` planes (parallel to YZ)

### 3.2 View-to-model transforms [DESIGN]

Each view gets an affine map `px → model`. It is stored in the document as an **observation transform**, with its own scale and a per-view residual:

- **Side:** `x = (u − u_nose)·k`, `z = (v_ground − v)·k`.
- **Top:** `x = (u − u_nose_top)·k_top`, `y = (v_c − v)·k_top`, with `v_c = 816`.
- **Front and rear:** `y = ±(u − u_c)·k_end`, `z = (v_ground_end − v)·k_end`. The rear view is mirrored in y relative to the front view.

The scales are solved by least squares over the shared quantities:

- length: side vs top
- height: side vs front vs rear
- max body width: top vs end views at fender height. Not at tyre height, because tyres may sit inboard of the fender.

The solver reports each view's residual. It also reports the **fitted end-view scale ratio**: about 0.95 is expected. That ratio then needs your choice [OPEN-2]:

- **(a) accept per-view scales** (treat the end views as drawn smaller), or
- **(b) force one scale**, accept the 5 % height conflict, and let the conflict appear in the reprojection metrics.

The default is (a). It is labelled "derived: per-view scale fitted, residual X %". It is never silent.

### 3.3 Observations extracted from the drawing (curves, not volumes) [DESIGN]

All of these are 2D polylines in px with source pixels. They are fitted to B-splines (least squares, fairness term) and each stores its max fit deviation in px.

| Curve | View | Use |
|---|---|---|
| `Ztop(x)` | side, upper silhouette excluding mirror | roof, bonnet, engine-cover centreline height |
| `Zbot(x)` | side, lower silhouette excluding wheels and arches | splitter, sill, diffuser bottom |
| `Ybody(x)` | top, half-width outline excluding mirrors, both halves fitted and averaged after a symmetry check | plan outline with fender flares |
| `Zbelt(x)` | side, lower edge of the side window and the shoulder line | where the greenhouse meets the body |
| `Ygh(x)` | top, greenhouse edges (windscreen and roof outline lines) | greenhouse half-width |
| `Efront(z)`, `Erear(z)` | front and rear outer half-silhouettes excluding mirrors and tyres | cross-section envelope shape: tumblehome, shoulder, lower taper |
| `Wcab_front(z)`, `Wcab_rear(z)` | windscreen trapezoid (front), rear-glass edges (rear) | greenhouse section shape |

Existing code reused **only to produce observations** [FACT-CODE: these functions exist]:

- `sheet.panels`, `sheet.view_mask`, `sheet._drop_ground_line`: view finding and filled silhouettes. The silhouettes are also the reference for §7.
- `circles.find` and `sheet.wheels`: wheel circles.
- `segment.regions` and `outline.vectorize`: closed regions and line vectorisation for #9–#25.

None of their voxel or mesh outputs feed the CAD body.

### 3.4 Station placement [DESIGN]

Stations are named, ordered, and each is attached to a datum. A station's position is **relative**: `x = datum + t·span`. That way an axle or wheelbase edit moves the dependent stations. Placement rules:

1. **Mandatory structural stations:**
   - nose tip (+ε)
   - bumper face (end of the front fascia)
   - front axle ± arch radius (arch edges)
   - A-pillar foot (windscreen base, from the side view)
   - roof peak
   - rear end of the roof / start of the engine cover
   - rear axle ± arch radius
   - rear deck end
   - tail lip
2. **Curvature-adaptive stations:** extra stations wherever `Ztop`, `Zbot` or `Ybody` turn by more than 4° or deviate from a linear interpolation by more than 0.5 px between existing stations.
3. **Expected count:** ≈ 14–22 for the lower body and 6–10 for the greenhouse. A spacing check rejects stations closer than 2 % of the length, since those make loft wiggle.

### 3.5 Section template and correspondence [DESIGN]

Every lower-body station uses the **same** closed, symmetric section built from 7 control points per half (mirrored, so 12 unique). All sections have identical topology, so the loft has guaranteed point-to-point correspondence and one seam on the bottom centreline.

| Point | Meaning | Value source |
|---|---|---|
| P0 | bottom centre (0, Zbot) | side `Zbot(x)` (measured) |
| P1 | floor edge / sill corner | `Ybody(x)·c_sill`; `c_sill` from `Efront` / `Erear` lower taper (derived) |
| P2 | max-width point (Ybody, z_max) | `Ybody(x)` from top (measured); `z_max` from the end-view envelope (derived), blended along x (**inferred**) |
| P3 | shoulder / beltline | `Zbelt(x)` from side (measured); y from the end-view envelope (inferred) |
| P4 | deck edge (where the bonnet / engine cover meets the side) | end-view envelope (inferred) |
| P5 | top centre (0, Ztop_lower) | side profile with the greenhouse removed (measured where visible, inferred under the cabin) |

Constraints:

- Horizontal tangent at P0 and P5 (G1 across the symmetry plane).
- Vertical tangent at P2.

The section curve is an interpolating periodic B-spline through the mirrored points with those tangent constraints (`Geom2dAPI_Interpolate` with tangents). It is placed on `STATION_i`.

**Blending the end-view envelopes along X** is the main **inferred** step. Only two cross-section silhouettes exist (front and rear maximum envelopes), not true sections. The shape fractions (`c_sill`, the shoulder-height fraction, tumblehome) are taken from `Efront` for stations ahead of the cabin centre and from `Erear` behind it, with a smoothstep blend between them. Every station records `shape_source: "blend(front 0.7, rear 0.3)" → inferred`. This is the statement of underdetermination: other section shapes would reproduce the same three silhouettes.

### 3.6 Patch decomposition: why the body is not one loft [DESIGN]

| Patch | Stations | Why separate |
|---|---|---|
| L1 lower body | nose → tail | full-length envelope with fender flares. The arches are cut later. |
| G1 greenhouse | windscreen base → engine-cover start | narrower (tumblehome), different section template (windscreen trapezoid → roof → fastback). One loft cannot represent the step between the cabin and the shoulder without degenerate sections. |
| Nose cap, tail cap | first and last stations | the end faces are blunt in the side view and the bumper face is visible in the front view, so they are **filled surfaces** bounded by the first or last section (`BRepFill_Filling` with G1 to the loft where possible). A loft cannot close on itself. |

Assembly of the body solid:

```
L1 + caps → sew → solid
G1 + caps → solid
fuse(L1, G1)
cut arches (#3, #4)
cut intakes / pockets (#13, #16, #20, #23, #25)
imprint regions (#9–#12, #17, #18, #22)
optional fillet G1∩L1 seam
```

The fillet runs last. If it fails, the feature status becomes `failed_optional` and the model stays valid without it.

**Continuity targets:**

- **Within L1 and G1:** C2 (loft with `SetContinuity(C2)`, smoothing on). [FACT-KERNEL: a C2 smoothed `BRepOffsetAPI_ThruSections` loft built a valid B-spline solid in a test.]
- **Between L1 and G1:** a G0 seam after the fuse, with an optional fillet giving G1. The achieved angle is reported (§6).
- **Caps:** G1 attempted. The achieved max normal angle is reported.

### 3.7 Body parameters (editable)

| Group | Parameters |
|---|---|
| Global | `scale_mm_per_px`, `end_view_scale_ratio`, `overall_length`, `ride_height` |
| Datums | `front_axle_x`, `wheelbase`, `front_track`, `rear_track` |
| Per station | `t` (position), `z_top`, `z_bot`, `y_max`, `z_max`, `y_belt`, `z_belt`, `c_sill`, `deck_y`, `override` flags |
| Loft | continuity, smoothing, approximation tolerance |
| Features | arch clearance and depth, intake depths, louvre count and depth, exhaust protrusion |

---

## 4. CAD document (`.aethercad`) [DESIGN]

A JSON manifest is the source of truth. A versioned and typed schema is validated before every build. B-rep caches (`.brep` per feature output) are disposable.

```jsonc
{
  "schema": "aethercad/1",
  "units": "mm",
  "source": {"file": "car_three_view.webp", "sha256": "a985…", "views": {...transforms + residuals...}},
  "maturity": "draft_inference",              // never auto-promoted past drawing_consistent
  "parameters": [{"id":"wheelbase","value":"<411 px × scale>","unit":"mm","provenance":"derived",
                  "evidence":["obs.wheel_front","obs.wheel_rear","param.scale"],"uncertainty":{"min":..,"max":..},
                  "status":"accepted"}],
  "observations": [{"id":"obs.ztop","view":"side","kind":"profile_curve","px":[[u,v],...],
                    "fit":{"type":"bspline","max_dev_px":0.8},"extracted_by":"cv:sheet.view_mask"}],
  "datums": [{"id":"AXIS_FRONT","type":"axis","origin":["param.front_axle_x",0,"param.r_tyre_f"],"dir":[0,1,0]}],
  "components": [{"id":"body","kind":"body_shell","features":["st.*","loft.L1",...],"material":"paint"},
                 {"id":"wheel_fl","kind":"wheel","placement":{"datum":"AXIS_FRONT","side":"+y"},
                  "features":["tyre_f.revolve","rim_f.revolve","rim_f.spokes",...]}],
  "features": [{"id":"loft.L1","op":"loft","inputs":["sec.L1.00",...,"sec.L1.17"],
                "params":{"continuity":"C2","smoothing":true,"ruled":false},
                "depends_on":[...],"status":"ok|failed|failed_optional|stale","error":null,"brep":"cache/loft.L1.brep",
                "validation":{...}}],
  "joints": [{"id":"j.wheel_fl","type":"revolute","a":"body","b":"wheel_fl","axis":"AXIS_FRONT"}],
  "assumptions": [{"id":"A-07","text":"cross-section shape blended between front and rear envelopes",
                   "affects":["sec.L1.*"],"class":"inferred","editable_via":["st.*.override"]}],
  "validation": {...}, "history": [...transactions...]
}
```

- **Allowed operations** (an enum, each mapped to fixed kernel calls in `cad/features/`): `datum_plane`, `datum_axis`, `section_curve`, `sketch` (lines / arcs / circles / splines + constraints), `loft`, `filled_surface`, `sew_solid`, `revolve`, `pad`, `pocket`, `cut_tool_loft`, `boolean_fuse`, `boolean_cut`, `split_face_by_projection`, `polar_pattern`, `linear_pattern`, `mirror`, `fillet`, `chamfer`, `sweep`.
- **AI output:** Muse Spark may only fill `observations` (semantic labels, view roles, component candidates) and propose `assumptions`, through a strict JSON schema. A deterministic planner turns accepted observations into features. **No generated code is executed.**
- **Constraints:** sketches use `dimension`, `coincident`, `tangent`, `horizontal`, `vertical`, `concentric`, `symmetric`, `equal`. Sections are solved explicitly (the interpolation with tangent constraints in §3.5). The experimental CadQuery sketch solver is **not** used for the body. Wheel and exhaust sketches are fully dimensioned, so no solver is needed [DESIGN; avoids the risk your plan flagged].

---

## 5. Uncertainty and assumptions

### 5.1 Scale [OPEN-3]

The sheet has no dimension. Every mm value is therefore **not measured** until you supply one real length (overall length, wheelbase or tyre diameter). Then `scale_mm_per_px` becomes `user_confirmed`, and the other sizes become `derived`.

Until then the default is `overall_length = 4500 mm`, labelled `assumed: placeholder, no dimension on the sheet`. I will not take dimensions of the real car model from memory or the web and present them as drawing facts. If you want manufacturer data used, it enters as `external_reference` with its source.

### 5.2 Provenance classes

Your four classes, plus two the workflow needs:

| Class | Meaning |
|---|---|
| `measured` | read from a calibrated drawing quantity |
| `derived` | computed from measured values and stated relationships |
| `inferred` | estimated from projections or conventions |
| `unresolved` | no evidence; a placeholder with a wide range, flagged red |
| `user_confirmed` | entered or approved by you |
| `external_reference` | from outside the drawing, with its source |

**Pixel quantities are `measured` in px, but `derived` in mm** (because of the scale). The report shows both.

### 5.3 Rules

- Every parameter and feature input points to its observation ids and assumption ids.
- The build report lists, per component, the share of driving parameters in each class.
- A user override records the old value, the new value and the time.
- Where several readings fit, the alternatives are listed with their fit residuals, not hidden. Examples: the brake disc vs rim step (#7), and front-view-at-fender vs tyre width for the scale.

---

## 5A. Muse Spark, Muse Wonder and SAM 3.1 in the drawing-understanding pipeline

**Requirement (yours):**

- All three models stay integrated and work together on:
  - visual interpretation
  - segmentation
  - component recognition
  - geometric hypothesis generation
  - ambiguity resolution
- For this car, Muse Wonder also reasons about section profiles, surface transitions and plausible interpretations.
- **No model is the geometry authority.** Every proposal becomes a validated, typed CAD specification built deterministically through OpenCascade.
- No AI-generated executable code may be used.

### 5A.1 What exists today [FACT-CODE]

| Model | Current use | Where |
|---|---|---|
| Muse Spark (`muse-spark-1.3`) | Front/rear decision for the end views. Naming of numbered mesh regions. Both use JSON responses. | `agent._spark_which_front`, `_spark_name_regions` |
| Muse Wonder (`muse-wonder-1.0`) | Engineer's completion of one-view machines (depths, hidden parts). Falls back to Muse Spark if the call fails. | `agent._spark_complete`, `COMPLETE_MODEL` |
| SAM 3.1 | Photo/part segmentation and blueprint part masks. **Not used on the three-view route today.** | `vision.segment`, `vision.blueprint_parts` |

Plumbing that is reused as-is:

- `_spark_json`: strict JSON schema, temperature 0, seed, one retry on invalid JSON, Muse Wonder → Muse Spark fallback.
- Attribution: `who()` and the step list showing which model did what and how long it took.

### 5A.2 Roles in the new pipeline [DESIGN]

Every model call returns **only** JSON that matches a strict schema. It is stored as an `observation` or a `hypothesis` with `{model, model_version, prompt_hash, seed, response_hash, latency_s}`. Nothing a model returns is executed. Nothing it returns enters the CAD document until a deterministic gate accepts it.

| Stage | Model(s) | Input | Typed output (schema) | Deterministic gate before use |
|---|---|---|---|---|
| S1 View roles | **Muse Spark** (×2 seeds) + CV | the 4 view crops (boxes from `sheet.panels`) | `{view_id: "side" \| "front" \| "rear" \| "top", nose_direction, evidence:[...]}` | Both seeds agree **and** they agree with the CV size match (length side ≈ top, ±2 %); otherwise the question goes to you. Front/rear also checked against SAM masks (headlights vs exhaust tips, S2). |
| S2 Segmentation | **SAM 3.1** (text prompts from S3 candidates: "wheel", "side mirror", "headlight", "side window", "air intake", "exhaust tip", "grille", ...) | each view crop | per view: masks + boxes + score | Mask kept only if it lies inside the view silhouette, its outline coincides with drawn ink (≥ 60 % of the mask boundary within 2 px of ink) and score ≥ threshold. Wheels must also agree with `circles.find` (centre ±3 px, r ±5 %). |
| S3 Component recognition | **Muse Spark** proposes, **Muse Wonder** cross-checks | view crops + SAM mask overlays (numbered) | component list per §2 schema: `{id, kind, views:[{view, mask_ref \| box}], role_proposal: body \| feature \| region \| annotation, reason}` | A component is accepted when it is seen in ≥ 1 view with a gated mask/box, and both models agree on kind and role. If they disagree, both readings go into the ambiguity list and you decide. Cross-view consistency: a component visible in side and top must project to the same x-range ±3 %. |
| S4 Correspondence | **Muse Spark** | masks across views | `{component_id: {side: mask, top: mask, front: mask, rear: mask}}` pairing | x-range (side ↔ top), z-range (side ↔ end views) and y-range (top ↔ end views) must agree within the fitted scales (§3.2); a pairing that violates them is rejected. |
| S5 Section-profile hypotheses | **Muse Wonder** (medium effort, ≥ 2 independent samples) | the 4 views, extracted curves (`Ztop`, `Zbot`, `Ybody`, `Zbelt`, `Efront`, `Erear`) plotted with the station positions marked | per station: `{station_id, shape_fractions: {c_sill, z_max_frac, tumblehome_deg, deck_edge_frac}, range: {min, max}, reason}` | Values are clamped to hard bounds from the drawing: `y_max` = measured plan half-width **exactly** (never taken from the model); `z_top` and `z_bot` = measured side profile **exactly**. Only the *shape fractions* between those measured extremes may come from Muse Wonder. Each sample is built and reprojected; the one with the best front/rear envelope fit (§7) and fairness (B2) wins. The others stay recorded as **alternatives**. |
| S6 Surface-transition hypotheses | **Muse Wonder** | the same plus component list | `{transition: "greenhouse↔body" \| "nose cap" \| "tail cap" \| "arch lip" \| ..., intent: G0 \| G1 \| G2 \| sharp_crease, evidence_lines:[...], reason}` | Allowed values only. An intent is applied only where the drawing does **not** show a crease line there (a drawn line means a sharp edge or panel break). The achieved continuity is measured (§6) and reported against the intent. |
| S7 Interpretation alternatives | **Muse Wonder** | ambiguity list (OPEN-2, OPEN-4, recess depths, ...) | `{ambiguity_id, options:[{value_or_choice, plausibility, reason}]}` | Never decides by itself. Options with plausibility below threshold are dropped; the others are shown to you or built as alternatives. Values stay `inferred` (model) until you confirm (`user_confirmed`). |
| S8 Verification and explanation | **Muse Spark** | reprojection overlays + report numbers | `{issues:[{view, region, description}], explanation_steps:[...]}` | Advisory only. Issues it raises are logged; pass/fail comes only from the §6/§7 metrics. The explanation is checked like `explain.validate` today: every number and part id it mentions must exist in the document. |

**Model failure:** if a model call fails or times out, the stage falls back to CV-only evidence plus the documented default assumption, and records `model_failed: <reason>`. A Muse Wonder failure falls back to Muse Spark for S5–S7 as today, and the step list says so. The build never pretends a model answered when it did not.

### 5A.3 Why this keeps the models out of geometry authority [DESIGN]

1. **Hard limits.** Measured curves (`Ztop`, `Zbot`, `Ybody`, wheel circles, view boxes) come from CV on the ink and cannot be overridden by a model. Models only fill quantities the drawing leaves open, inside bounds the drawing implies.
2. **Fixed operations.** Every model output is a set of numbers and enum choices in a schema. The planner maps them to the fixed feature operations of §4; there is no field that carries code, expressions or file paths.
3. **The kernel decides validity.** A hypothesis that produces an invalid solid, a failed Boolean or worse reprojection is rejected by the kernel and the metrics, regardless of the model's stated confidence.
4. **Provenance.** Every value a model contributed carries `provenance: inferred`, `source: {model, call id}`. The report counts model-derived parameters separately from CV-measured ones.

### 5A.4 Determinism and cost [DESIGN]

- Model answers vary between runs even at temperature 0. `agent._spark_json`'s own docstring states this [FACT-CODE].
- Every model response is therefore stored in the document's `observations`/`hypotheses`. A **rebuild or recompute replays the stored JSON** and does not call the models again. Results are reproducible, and recompute tests (R1–R7) run offline with no API key.
- New model calls happen only on a new upload, or when you ask for "re-interpret" on one stage.
- Expected calls per upload (estimate): S1 2, S2 ≈ 4 views × ≈ 10 prompts, S3 2, S4 1, S5 2–3, S6 1, S7 1, S8 1. Latency is dominated by S5 (Muse Wonder, medium effort; ~25–65 s per call measured on the machine route in `docs/RESULTS.md`).

---

## 6. Validation of every solid and the assembly [DESIGN]

The validation suite runs after every recompute, per feature output and per final component. Results are stored in `features[].validation` and the document's `validation`.

| Check | OCCT facility | Pass criterion |
|---|---|---|
| Topological / geometric validity | `BRepCheck_Analyzer` | `IsValid()` true |
| Solid closure / shell integrity | `ShapeAnalysis_FreeBounds` (free edges), `BRepLib::OrientClosedSolid`, solid classifier with a far point | 0 free edges; far point classified OUT |
| Boolean argument sanity | `BOPAlgo_ArgumentAnalyzer` (self-intersection, small edges, rebuilt faces, continuity) before each Boolean | no faults |
| Boolean result | `BRepAlgoAPI_*`: `HasErrors` / `HasWarnings` reported; volume accounting `V(A∪B) = V(A)+V(B)−V(A∩B)` and `V(A−B) = V(A)−V(A∩B)` | relative error < 1e-6 |
| Volume / mass properties | `BRepGProp::VolumeProperties` | finite, > 0, within the expected range from the bounding-box envelope |
| Degenerate entities | `ShapeAnalysis_Edge`, `ShapeAnalysis_ShapeContents`; small-face / sliver detection | 0 degenerate edges; no face < 1e-4 of the total area unless expected |
| Tolerances | `BRep_Tool::Tolerance` max over vertices / edges / faces | ≤ 1e-3 × model size; growth reported |
| Loft validity | section compatibility (same edge count, orientation, seam alignment) checked before the build; afterwards, sample normals on a 50 × 50 grid per face: no normal flip, curvature bounded; profile fidelity: re-intersect the loft with each station plane and compare with the input section | max deviation < 0.05 mm at the stations |
| Fairness (no loft wiggle) | `Ztop`/`Zbot`/`Ybody` re-sampled from the B-rep between stations vs the observation curves | max deviation < 1.5 px equivalent |
| Patch continuity | normals across shared edges (L1 / G1 seam, caps) | reported in degrees; target G1 ≤ 1° where intended |
| Interference / clearance | pairwise `BRepAlgoAPI_Common` volume and `BRepExtrema_DistShapeShape` | wheels vs body: no overlap, min clearance ≥ the `arch_clearance` parameter; mirror vs body: contact only at the stalk joint |
| Recompute validity | §8 | |

**Failure policy:**

- Any failed mandatory check sets the component status to `invalid`.
- Document maturity drops to `draft_inference`.
- STEP export is **blocked**. GLB may be exported only with "INVALID" in the file metadata and UI.
- No previous geometry is shown as current. The last valid geometry can be shown only greyed and labelled `stale`.

---

## 7. Three-view reprojection and accuracy [DESIGN]

1. **Projection.**
   - Silhouettes: orthographic projection of the **B-rep assembly** into each view frame using the inverse of the §3.2 transform (same px scale and origin as the drawing). Adaptive fine tessellation (chordal deflection 0.02 mm), rasterised with 4× supersampling.
   - Edges: `HLRBRep_Algo` (exact hidden-line removal on the B-rep) for visible sharp and outline edges.
2. **Reference.** The drawing's filled silhouette per view (`sheet.view_mask`, ground line removed) and its ink lines.
3. **Metrics, per view, never merged into one score:**
   - silhouette IoU (filled)
   - boundary deviation: symmetric mean, 95th percentile and Hausdorff of outline-to-outline distance, in px and mm
   - normalised contour distance: mean deviation / view diagonal
   - alignment error: residual translation and scale from an ICP fit of the projected outline to the drawn outline. Ideally ≈ 0 because the frames are fixed; a large value means the transform is wrong.
   - feature-edge recall and precision: HLR edges within 2 px of ink, and ink lines within 2 px of an HLR edge, inside the body region. This tests interior lines (windscreen, headlights, door) that the silhouette does not.
   - dimensional deviations: length, height, wheelbase, overhangs, tyre radii (front and rear), rim radius, track, tyre width, body max width, roof width.
4. **Images per view:** the drawing alone; the projection alone; an overlay (drawing grey, projected outline cyan, drawn-but-not-built ink red, built-but-not-drawn edges magenta); and a signed distance heat strip along the outline.
5. **Stated limitation, printed in every report:** a matching projection does not prove the hidden 3D shape. In particular, the cross-sections between the front and rear views are inferred (§3.5), and the arch depth, intake depths and louvre depths are assumed.
6. **Baseline.** The same metrics run on the legacy visual-hull mesh for the same sheet. The legacy hull will likely score higher on silhouette IoU (it is built to match silhouettes exactly), so it must **not** be the only comparison. The plan compares surface quality (roughness, flipped triangles, slabs) and edge precision, where the CAD model should win.

---

## 8. Feature history, recompute and its tests [DESIGN]

**Model:**

- The features form a DAG (`depends_on`). Recompute follows topological order from the changed parameter's dependents.
- Each feature output is cached by the hash of its resolved inputs, so only invalidated features rebuild.
- A recompute is a **transaction**. It either commits the new valid state or rolls back to the previous one, with `last_error` naming the feature and the kernel message.
- Undo and redo work on transactions.

**References** are datums, station planes and named section curves, never raw face indices. Imprints project named 2D curves from a view plane onto the body; the face to split is chosen by projection hit, not by index.

**Recompute tests:**

| Edit | Expected dependents | Expected result |
|---|---|---|
| wheelbase +5 % | `AXIS_REAR`; stations attached to it; arch cuts; rear wheels; reprojection | valid; rear wheel moves by Δ; side-view length changes; IoU recomputed |
| `STATION_roofpeak.z_top` +3 % | L1 / G1 lofts; fuse; downstream cuts and imprints | valid; volume increases; Z at that station equals the new value ± 0.05 mm |
| rear `r_tyre` +4 % | rear tyre; interference check | valid; or **fails explicitly** if the clearance goes below `arch_clearance` (an expected failure test) |
| station `y_max` set ≤ 0 | (schema) | rejected before kernel calls; status unchanged |
| two stations swapped (non-monotone x) | loft | `failed` with the loft error; STEP blocked; previous valid geometry marked stale |
| `end_view_scale_ratio` 0.95 → 1.0 | every section from the envelopes | valid; front / rear projection metrics change; report shows the delta |
| change then undo | all | geometry hash equals the original |

---

## 9. STEP round-trip integrity [DESIGN]

1. **Export** from the validated B-rep with `STEPCAFControl_Writer` (AP214 or AP242). It keeps the assembly structure, component names and colours. Only when every component is valid.
2. **Re-import** with `STEPCAFControl_Reader` into a fresh process (no shared memory with the builder).
3. **Re-validate** with the §6 checks.
4. **Compare per component** (matched by name):

| Measure | Tolerance |
|---|---|
| counts: solids, faces, edges | exact |
| volume, surface area | relative 1e-6 |
| centre of mass | 1e-4 mm |
| bounding box | 1e-4 mm |
| sampled geometric deviation: 2,000 points on the original faces → `BRepExtrema_DistShapeShape` to the re-imported shape, and the reverse direction | max ≤ 1e-3 mm (stated tolerance); mean and max reported |

5. **Report** every measured value, not just pass / fail.

[FACT-KERNEL] On one toy C2 loft, STEP export → import kept validity and volume (15692.26 mm³ both). That is not evidence for the car. The car test above is the acceptance test (E).

---

## 10. GLB and the AETHER Lab integration [DESIGN]

**Process split** [DESIGN, matches the plan's isolation rule]:

- A new `aether-lab/cad-worker/` holds a pinned Python 3.12 venv (CadQuery 2.8.0 + OCP). It runs as a child process speaking JSON-RPC over stdin / stdout.
- `server.py` (your Python 3.14 environment) never imports OCP.
- [FACT-KERNEL: CadQuery 2.8.0 / Python 3.12 installs and runs on this Linux container.] **Not yet tested on your Windows machine** [OPEN-6].

**New API** [DESIGN]:

| Endpoint | Purpose |
|---|---|
| `POST /api/cad/from_sheet` | upload → observations → plan → build → validate → reproject |
| `GET /api/cad/document` | the feature tree, parameters, provenance, validation |
| `POST /api/cad/param` | transactional edit + recompute |
| `GET /api/export.step` | blocked if invalid |
| `GET /api/export.aethercad` | the native document |

The existing `/api/export.glb` then exports the B-rep tessellation.

**Scene state** [DESIGN; based on FACT-CODE]:

- Today a part is `{type, params, position, …}` and `geometry.local_mesh` builds the triangles; `type: "mesh"` parts carry `vertices` / `faces` in params, and `server.lean()` / `restore()` already strip and restore those heavy fields.
- The new part type `"cad"` carries `{document_id, component_id, tess_hash}` plus the worker's tessellation in the same heavy fields.
- `geometry.local_mesh` returns that tessellation unchanged. So the optics, desk score, explode, section and hand tools keep working with **no** CAD knowledge.
- The Modal engine fingerprint changes (a new part type), so `compute.py` triggers its existing auto-redeploy.

**Tessellation for display** [DESIGN]:

- `BRepMesh_IncrementalMesh` with linear deflection 0.1 mm and angular 0.3 rad.
- Normals come **from the B-rep faces** (`BRepLProp_SLProps`), shared along G1 edges and split along sharp edges. This replaces the viewport's `toCreasedNormals` guess for CAD parts, which removes the shading seams the old export had between mesh pieces.
- Real B-rep edges (sharp and imprinted panel lines) are sent as the `l` line list. `Viewport.jsx` `EdgeLines` already draws a supplied line list [FACT-CODE].

**GLB:** one node per component (body, wheel ×4, mirror ×2, exhausts ×4, splitter), in metres, Y up (same convention as `export.glb`). The `extras` carry `component_id`, the feature list, provenance counts and `"authoritative": "aethercad document + STEP; this GLB is a tessellated view"`. Blender imports it with its glTF importer.

**UI:**

- The Outliner shows the assembly tree.
- A new **Feature Tree** panel shows features, status (ok / failed / stale) and assumptions.
- The Right panel edits parameters, which calls `/api/cad/param`.
- A maturity badge shows on the model.
- The existing orbit, section, explode, isolate, hand and holo controls stay unchanged.

---

## 11. What happens to the existing code

| Module | Decision | Reason |
|---|---|---|
| `agent.py::_sheet_to_design` | **Adapt.** Route three-view uploads to the CAD pipeline, with stages S1–S8 of §5A (Muse Spark, Muse Wonder, SAM 3.1) | the models stay in the pipeline as observers and hypothesis generators, not geometry authors |
| `agent.py::_spark_name_regions` | **Replace** with the typed component-inventory call (S3) | today it names mesh regions after carving |
| `agent.py::_spark_json`, `who()`, fallback logic | **Reuse** unchanged for every S1–S8 call | strict JSON, fallback and attribution already work |
| `vision.segment` (SAM 3.1) | **Reuse** for S2 on each view crop; add the ink-coincidence gate | SAM is not used on the three-view route today |
| `lab.import_sheet`, `sheet.sheet_to_solid`, `hull.carve`, `hull.surface_nets`, `hull_field*`, `segment.split` / `assign` | **Retain only as "Legacy preview (visual hull), not CAD"**, behind an explicit option and labelled in the UI and GLB | prohibited as the final method |
| `sheet.panels`, `view_mask`, `match`, `wheels`, `_drop_ground_line`, `front_rear_candidates` | **Reuse** in `cad/observations/` | view and silhouette extraction is evidence, not geometry |
| `circles.find`, `segment.regions`, `outline.vectorize` / `simplify` | **Reuse** for observations | measured curves and circles |
| `geometry.py` | **Keep** for primitive parts and optics; add the `"cad"` part type | display and physics need one mesh source |
| `export.py` | **Adapt.** GLB from B-rep tessellation for CAD parts; STEP from the worker; report gains provenance classes and validation | GLB / STL become derived outputs |
| `quality.py` | **Keep** for tessellation and legacy comparison metrics | |
| optics, `compute.py`, Modal | **Keep unchanged** (auto-redeploy for the new part type) | geometry stays upstream of optics |
| `tests/test_physics.py` | **Keep.** Add `tests/cad/` as a separate suite | optics passing must not imply CAD passing |

---

## 12. Test matrix

`tests/cad/`, run as `cad-worker/.venv/bin/python -m pytest tests/cad`. Inputs: the canonical sheet; synthetic sheets for unit tests.

| ID | Test | Input | Expected | Fails when |
|---|---|---|---|---|
| K1 | kernel smoke | primitives | loft, revolve, cut valid; STEP round trip | any invalid |
| O1 | view detection | sheet | 4 views; boxes within ±3 px of §1.1 | wrong count or role |
| O2 | view roles | sheet + Muse Spark JSON | side, front, rear, top as §1.1 | front / rear swapped, or no confirmation recorded |
| O3 | scale fit | sheet | length residual ≤ 1 %; end-view ratio reported (≈ 0.95) | conflict averaged silently / no residual |
| O4 | wheels | sheet | 2 circles ±2 px centre, radii 53 ± 2 and 57 ± 2, rims 43.6 ± 2 | missing or merged wheels |
| O5 | profile curves | sheet | `Ztop` / `Zbot` / `Ybody` fit max dev ≤ 1.5 px; mirrors excluded from `Ybody` | mirror in the plan outline |
| O6 | inventory | sheet | §2 rows 1–27 present (as body / feature / region / annotation) | an identifiable item missing, or an unlisted item added without an assumption |
| D1 | schema | malformed docs | rejected with a path to the bad field | accepted |
| D2 | save / reopen | doc | identical ids, params, provenance, geometry hash | any change |
| B1 | sections | stations | equal topology; no self-intersection; symmetric (max \|y⁺ + y⁻\| < 1e-6) | mismatch |
| B2 | L1 / G1 lofts | sections | valid, closed, C2 inside, profile fidelity < 0.05 mm | invalid / wiggle |
| B3 | body solid | all body features | §6 all pass; 1 solid; volume > 0 | any check fails |
| B4 | arch cuts | body + datums | arch centre at the axle ± 0.05 mm; wheel clearance ≥ param | overlap |
| W1 | wheels | params | 4 separate solids; tyre and rim revolved; spokes polar ×5; front ≠ rear tyre radius as drawn | cylinder primitives, or equal radii |
| C1 | small components | mirrors, exhausts, splitter | valid; positions within 2 px reprojected | invalid / misplaced |
| V1 | assembly validation | full model | every component valid; no unintended interference | overlap > 1 mm³ |
| R1–R7 | recompute | §8 table | as stated, including the expected explicit failures | silent stale geometry, or a wrong pass |
| S1 | STEP round trip | full model | §9 within 1e-3 mm | outside tolerance / count mismatch |
| S2 | STEP blocked when invalid | broken doc | export refused with the reason | file written |
| P1 | reprojection side | model | IoU, boundary metrics, dims and images produced; targets IoU ≥ 0.95, p95 boundary ≤ 3 px | no images / one merged score |
| P2 | reprojection top | model | same; target IoU ≥ 0.95 | |
| P3 | reprojection front / rear | model | reported with the scale choice of OPEN-2; target IoU ≥ 0.92 | |
| P4 | feature edges | model | HLR edge precision and recall per view reported | not reported |
| P5 | legacy comparison | legacy hull + CAD | both metric sets side by side; surface-quality comparison | |
| G1 | GLB | model | opens in the Three.js viewport and in Blender's glTF importer; nodes = components; normals from the B-rep; bbox matches the B-rep ± deflection | mesh from anything other than the validated B-rep |
| I1 | integration | upload in the UI | Feature Tree shows; a parameter edit recomputes; optics tools run on the tessellation | UI shows the legacy hull as CAD |
| M1 | AI schemas | recorded and malformed model responses | valid JSON accepted; extra fields, code-like strings, out-of-range values rejected with the reason | anything outside the schema reaches the planner |
| M2 | AI cannot override measurements | Muse Wonder proposal with `y_max` / `z_top` different from the measured curves | measured values kept; proposal logged as rejected | a measured value changes |
| M3 | AI failure fallback | simulated timeout / HTTP 500 for each stage | CV-only + default assumption; `model_failed` recorded; Muse Wonder → Muse Spark fallback named | silent success / crash |
| M4 | Replay determinism | stored responses | rebuild with no API key gives an identical geometry hash | any model call during recompute |
| M5 | SAM gate | SAM masks on the 4 views | wheel masks agree with `circles.find`; masks off the ink rejected | stray mask accepted |
| M6 | Section hypotheses | ≥ 2 Muse Wonder samples | each built and scored; winner by metric; others kept as alternatives | winner chosen by model confidence |
| M7 | No code execution | static check of the pipeline | no `eval` / `exec` / `compile` / subprocess on model output anywhere in `cad/` and `agent.py` | any such path |
| T1 | traceability | doc | every parameter has a provenance class + evidence; the report counts classes; no `measured` mm without `user_confirmed` scale | any `measured` without evidence |

The numeric reprojection targets are **proposals** [OPEN-7]. The drawing is a stylised illustration, not an engineering drawing, so achievable values are unknown until the first build.

---

## 13. Acceptance status (A–I)

Nothing is demonstrated yet.

| Req. | Proven by | Status |
|---|---|---|
| A valid B-rep | B3, V1 | not demonstrated |
| B feature history | D2, document inspection, Feature Tree | not demonstrated |
| C recompute | R1–R7 | not demonstrated |
| D wheels as real solids | W1 | not demonstrated |
| E STEP integrity | S1, S2 | not demonstrated (toy loft only) |
| F three-view comparison | P1–P5 | not demonstrated |
| G AETHER Lab viewport | G1, I1 | not demonstrated |
| H traceable assumptions | T1, report | not demonstrated |
| I decomposition | O6 + review against §2 | inventory drafted; not demonstrated |

---

## 14. Risks and open questions

| ID | Risk / question | Impact | Mitigation / what I need |
|---|---|---|---|
| OPEN-1 | Is the uploaded webp pixel-identical to `car_three_view.gif`? | benchmark reproducibility; legacy comparison fairness | Upload the GIF, or confirm the webp as canonical |
| OPEN-2 | End views ≈ 5 % smaller than side and top | front / rear metrics, section envelopes | Choose (a) per-view scale (default) or (b) one scale |
| OPEN-3 | No dimension on the sheet | every mm value | Give one real length, or accept the 4,500 mm placeholder labelled assumed |
| OPEN-4 | Ring r ≈ 33.9 inside the rim: brake disc or rim step? | one component more or less | Your call; default is not modelled, listed as ambiguous |
| OPEN-5 | Which car side the side view shows | none for the geometry (symmetric) | recorded only |
| OPEN-6 | CadQuery on Windows / Python 3.12 not tested | deployment on your machine | test on your PC before integration |
| OPEN-7 | Reprojection targets | pass / fail thresholds | agree after the first build |
| R1 | Loft wiggle with many stations | fairness | station spacing rule; fairness check B2; approximation instead of interpolation if needed |
| R2 | Booleans and fillets on B-spline faces (fuse L1 / G1, arch cuts, intake cutters) are the most fragile OCCT operations | invalid solids | `BOPAlgo_ArgumentAnalyzer` before each; fuzzy value; fillets last and optional; explicit failure status |
| R3 | Section shapes between the end views are inferred | hidden-shape error invisible in silhouettes | labelled; editable per station; feature-edge metrics (P4) give some independent check |
| R4 | Mesh areas (hex grilles) and louvre depth | detail fidelity | modelled as recesses + material, not cells; depths assumed |
| R5 | Time: the hackathon ends Nov 4 | scope | Build in the order K1 → O → B → W → V / S → P → G / I. Small components (#13, #16, #20, #23, #25) come after the body, wheels, STEP and reprojection work. |
| R6 | Brand / IP | the sheet and its 3D derivative are a trademarked design | keep the input and outputs out of the public repo and the hosted replay (already gitignored); internal benchmark only |
| R8 | Muse Wonder section proposals vary run to run and may be implausible | unstable body shape | measured extremes fixed; fractions bounded; ≥ 2 samples scored by reprojection; responses stored and replayed (§5A.4) |
| R9 | SAM 3.1 on line drawings (it is trained mostly on photos) may give poor masks | missed components | ink-coincidence gate; CV regions (`segment.regions`) as a second source; misses go to the ambiguity list, not silently dropped |
| R10 | API latency and cost of S1–S8 | upload time well above 90 s | stages in parallel where independent (S1 ∥ S2); replay on recompute; one "re-interpret" per stage on demand |
| R7 | Legacy hull beats CAD on silhouette IoU | misleading comparison | report surface and edge metrics too (P5) |

---

## 15. Build order after you approve this

1. **Worker + document + validation + STEP** (K1, D1–D2, S1–S2) on hand-authored test parts.
2. **Observations from the sheet** (O1–O6), with the scale decision, and the model stages S1–S4 (M1, M3, M5, M7).
3. **Body:** stations, sections, L1 / G1 lofts, caps, fuse, arches (B1–B4, R1–R7), with Muse Wonder section and transition hypotheses S5–S7 (M2, M4, M6).
4. **Wheels, mirrors, exhausts, splitter** (W1, C1, V1).
5. **Reprojection report** (P1–P5).
6. **AETHER Lab integration:** GLB, Feature Tree, parameter edits (G1, I1).
7. **Remaining recess and region features** (#9–#25 that were not done in step 3).
