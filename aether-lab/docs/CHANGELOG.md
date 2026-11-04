# Changelog

Work during the Meta Global AI Developer Hackathon 2026 (build window Oct 26 – Nov 4). Dates are when the work was
done (Malaysia time); see `BUILT_DURING_EVENT.md` for the commits.

## 2026-11-05 (after midnight; committed with its real date)

- **Checked edits** (`cad/codegen.py` edit mode): an edit is planned as the smallest change (Muse Wonder names the
  parts to change and the relations that must hold); only those parts may change; code verifies the relations on the
  geometry and reports every other part that moved; Muse Spark judges close-up renders before / after; the model is
  replaced only when the change is verified and nothing else broke. Reason: an edit of the roadster's windshield had
  rewritten 38 plan entries and 110 unrelated program lines.
- **B-rep assembly of AI-written parts** (`cad/assembly.py` reads each part's own `.brep`): the roadster's 117 parts
  all built and valid (before: 0). New chat tool `build_brep_assembly`.
- **Connection diagram**, **B-rep topology** (faces / edges / vertices of a part, from OpenCascade), **CAD feature
  tree** nested by mounting with each part's operations (`feature_ops.py`).
- **Assembly drawing**: item view with numbered balloons, parts list, connection diagram, in one PDF.
- **Explain** walks through the real connections from the plan; a connection step must name connected parts.
- Fixes: X-ray readability, group selection highlight, right-click selects the part, single-part moves kept, a
  duplicated CAD part keeps its mesh, a project with a mesh-less part opens.
- **No object recipes anywhere in the build path:** `prompts/cad_engineer.md` rewritten as object-neutral engineering
  principles (examples from machines, mechanisms, vehicles, products; "a hole is a cut, never a liner"); the critic
  rubric made neutral; the unreachable entry points of the retired car pipeline removed (`agent._sheet_to_cad`,
  `server.start_cad_job`, the three-view background branch), its route retired.
- **Edits judged fairly:** an edit is compared with the model as it was (defects it already had are not counted
  against it); part sizes compared from the exact geometry (a meshed part's box had produced false "changed" parts);
  before / after close-ups render the same parts; the cloud job survives a short network drop while polling.
- Verification: `pytest tests/test_physics.py` 32 passed; the assembly build, topology, connections, assembly
  drawing and chat tool tested on the 1909 press and the roadster; the roadster windshield edit re-run on the real
  model (plan: change `windshield_glass` only, 3 checks; result recorded in the commit). Acceptance on the final code:
  13 / 14 (`docs/ACCEPTANCE.md`; test 6 failed on wording, see the note there).

## 2026-11-04

- **AI-written CAD** (`cad/codegen.py`): Muse Wonder plans the assembly and writes a CadQuery / OpenCascade program for
  any object, run in a sandbox, checked by quality gates and against the drawing, critiqued by Muse Spark on real
  renders, revised up to 3 rounds. One orchestrator (`assistant.py`) with `build_cad`, `edit_cad`, `set_cad_param`.
- **Cloud CAD** on Modal CPU (`modal_cad.py`, `cad_remote.py`): one container per job, live progress in the chat,
  Stop cancels, retries on transient Meta API errors.
- **Ground truth** (`tests/ground_truth/`, `docs/GROUND_TRUTH.md`): three parts with known dimensions; AETHER vs a
  one-shot baseline vs an engineer's correction. Parameter corrections fixed (a model-written `P()` hid them).
- Lighter display meshes (a 20 m model: 1.3 M → 35 k triangles), project autosave without re-reading the file,
  auto-refresh of Modal status and project name, the app stays editable during a CAD job.
- Verification: 14 / 14 acceptance scenarios (`docs/ACCEPTANCE.md`), 32 offline tests.

## 2026-11-01

- **Muse Wonder** (`muse-wonder-1.0`) reads the dense drawing and does the engineer's completion (reading effort low);
  a failed call falls back to Muse Spark and the step label names both. Recall +8-16 points on B / D / C, precision
  -11 to -14 on D / C (RESULTS.md). Test 34.
- **Exports**: GLB (metres, y up, part records in node extras), STL (mm), one-page build report (File menu). Test 33.
- **Demo menu**: D, C, G live (warm-up first; machines are then explained); the last successful live run of each is
  kept and can be shown only as a RECORDED run (banner, labels).
- **Thin wings are not ground lines**: a horizontal line with another stroke 3-10 px beside it is one side of a thin
  closed shape (X-2's front-view wing) and is not erased. X-2 92.6 / 65.8 / 95.1 -> 99.7 / 95.5 / 99.6 %.
- **Models stand on the display surface**: every build and import ends with `place_on_base` (lowest point at z = 0;
  build_assembly's position z = height of the lowest point). "Place on base" (Object menu, Shift+B). A model taller than
  the sharp zone above the surface, or moved below it by the design loop, says why part of it is behind the surface.
  Test 32.
- **Every step shows who did it and how long**: "Muse Spark · read drawing · 28 s", "Modal T4 GPU · eye focus sweep",
  "Muse Voice Transcribe · speech to text"; finished steps stay in the chat. Voice "Explain this machine" opens Explain.
- **Gear pairs in sections**: edge-on gears pair by geometry (parallel axes, overlapping faces, axis gap = r1 + r2 or
  R - r); the engineer's completion may name missing pairs, built as "guessed" with the reason; ratios only from
  counted teeth, else "ratio unknown". Explain says which pairs were measured or guessed.
- **Plausibility filter**: shafts / pistons / springs thinner than 1 % of the machine take their box estimate or are
  dropped, listed in the report. Test 31.
- **Explain this machine** (`explain.py`, `/api/explain`, `ui/ExplainPlayer.jsx`): Muse Spark explains the BUILT model
  in 5–10 steps; every part id and number is checked against the model in code, one retry, invalid steps dropped and
  counted. The step player highlights each step's parts (others x-ray), moves the camera (front / top / iso / section),
  explodes on request. Muse Image draws one labelled concept illustration in parallel (30 s limit; optional).
  The viewport now frames around a top-docked panel too. Test 30.
- **Smooth bodies at 1 px per voxel**: anti-aliased view masks and `sheet.blur_thick`; `quality.roughness`; test 29.
- **3-D surface check of the delivered mesh** (`quality.folds`, `quality.mesh_staircase`, reported as
  `surface_check` with the official view match; folds per build stage in `mesh.folds`). Test 28.
- **Fold guard**: a seam-smoothing or zig-zag move that turns a triangle over is put back
  (`quality.keep_unflipped`). G: 525 -> 153 folded edges after seam smoothing; view match unchanged
  (100 / 99.6 / 99.0). The rib row on G's swept wing edge is measured but not fixed.
- **New held-out three-view**: NASA Bell X-2 (public domain); X-36 is no longer held out. First X-2 run: 92.6 / 65.8 /
  95.1 (thin wings in the front view not filled), recorded as is.

## 2026-10-31

- **Modal redeploys only on a real engine change.** `compute.run` used to treat any remote `TypeError` / `KeyError`
  as "Modal runs an old engine" and redeploy, so one bad argument from Muse Spark could stall a demo for minutes.
  Now the engine fingerprint is the only trigger: arguments are checked against the tool's signature before the call
  (`lab.check_args`: unknown, missing or non-numeric arguments come back to Spark as a clear `bad_args` error), and a
  remote error only re-pings Modal for its fingerprint, redeploying once if that differs. Test 21 covers all four
  cases (old engine + failed deploy, old engine + deploy, bad argument, real tool error on the current engine).
- **Arguments that are not JSON** are returned to Spark as an error instead of running the tool with `{}`.
- **Uploads are routed by what the image is, not by commas in the prompt.** `vision.upload_kind` measures the image
  (edge density for line drawing vs photo; separate views and their size agreement for a three-view sheet) and the
  upload form has an explicit choice: Auto · Machine drawing · Three-view sheet · Part photo. The prompt is now an
  optional hint. The routing and its evidence are the first step in the chat's step list.
- **`tests/run_reference.py`**: reference runs with the real key and Modal through the UI's own upload function;
  saves JSON and images per run and writes `docs/archive/RESULTS.md`.
- `graphify-out/` added to `.gitignore`.
- **Copyright-free reference inputs** (`tests/inputs/`, sources in `docs/INPUTS.md`): Fig. 1 of US 1,699,653 (motor
  reduction gearing) and of US 929,594 (metal drawing press), and NASA's X-3 three-view. The earlier stock / brand
  images are kept for internal comparison only.
- **Three-view sheets drawn to the edge**: when the first pass finds fewer than three views, `sheet.panels` pads the
  sheet and drops only lines longer than half its width (NASA's X-3: 1 view found before, 3 after; car sheet unchanged).
- **Stable drawing reading (step 3)**: every Muse Spark JSON call uses temperature 0, a fixed seed and a strict JSON
  schema (`agent._spark_json`; the API was probed: unknown parameters are rejected, these are accepted), retries once on
  invalid JSON and has its own timeout. Each image (whole sheet + 4 close-ups) is read twice; a part is kept when both
  readings agree (box IoU >= 0.4, same kind) or a measured circle confirms it (`interpret.agree`); the dropped parts are
  logged. A failed reading stops the build with the reason instead of falling back silently; a failed completion is
  reported and the depths are marked assumed. Step errors show their text in the live step list. Test 24.
- **Engineer's completion gives a reason per added part** (strict schema), kept in `eng.reason`.
- **Precision next to recall**: `drawing_check` now reports the share of built outlines (parts, frames) within 2 px of
  the drawing's ink, measured on the rebuild's own outline polygons; test 20 checks that an undrawn part is caught.
  The "Built vs drawing" card shows recall and precision.
- **Engineer's completion: `json_object` + `reasoning_effort: low`** instead of the strict schema (same parts, 143.5 s
  and 29k output tokens -> 35.6 s); its structure is checked in code. The strict schema stays on the drawing reading.
- **GPU warm-up**: every upload starts the Modal `run_tool` container while Muse Spark reads (desk_score 12-96 s -> 3 s).
- **Reading deadline**: the parallel readings get 60 s; stragglers are logged and not waited for (one run hit an API
  slowdown: all ten calls 77-88 s, two timeouts, 205 s in total).
- **Precision per part kind** (`outline_on_ink_by_kind_pct`) and an offline replay tool (`tests/replay_rebuild.py`)
  that runs a saved reading through the current rebuild, so every fix below was measured without new API calls.
- **Outlines that match the drawing**, each measured on the saved readings of B (gearing) and D (press):
  - gears and wheels with no measured circle and a non-square box are **seen edge-on** (side views, sections): built
    as discs whose axis lies in the drawing plane, with the drawn rectangle as outline (B wheels 7 % -> 45 %,
    gears 82 % -> 89 %);
  - shafts, pistons and springs: the outline is the rotated cylinder actually built, not the reader's upright box;
  - upright rectangles move each side onto the drawn line next to it (`fit_box_to_ink`), long parts take their width
    from their two drawn sides (`fit_width_to_ink`); wheels no longer get invented spokes;
  - gear module: an ISO 54 module (series I, then II incl. 2.25) only within 3 % of the drawn size, else the measured
    module (snapping 2.16 to 2 had made a 28 mm gear 26 mm).
  - B parts precision 63.9 % -> 71.8 %, D 77 % -> 82.4 % (replayed, same readings).
- **A part only one reading saw is kept when the drawing confirms it**: a measured circle (round parts) or drawn lines
  on 3–4 sides of its box (other parts), to win back recall the agreement had cost.
- Live steps show seconds per step and the total; the held-out drawing US 1,770,035 Fig. 1 is never tuned on.

## 2026-11-01

- **One official precision method**: the outer edge of the built silhouette (as the check image draws it). Each part's
  own outline had also counted edges inside other parts (B run 7: 68.9 % vs 56.4 %); per-kind numbers stay as a
  labelled diagnostic.
- **Agreement accepts one object under two names** (gear / wheel): on D run 7 "54 wheel" and "55 large gear" were the
  same box (IoU 0.82) and both were dropped. D recall 68.4 % -> 76.8 % (3 live runs).
- **Region naming runs in parallel with the hull** and with low reasoning effort (G import 104–172 s -> 38 s alone).
- Runs now save every single reading and the full dropped list, so other agreement rules can be replayed offline.
- `docs/archive/PROGRESS.md`: status of every step with the measured numbers.
