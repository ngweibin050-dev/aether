# AETHER CAD — three-view drawing → parametric OpenCascade B-rep

This package replaces the visual hull as AETHER Lab's three-view reconstruction. A sheet with side, top and end views
becomes an editable CAD document (`.aethercad`) with a feature history. Its geometry is valid OpenCascade B-rep
solids, exported as STEP. The GLB and the viewport meshes are tessellations derived from that B-rep.

The design and its test plan are in [`docs/CAR_CAD_ARCHITECTURE.md`](../docs/CAR_CAD_ARCHITECTURE.md). Measured results
are in [`docs/CAD_RESULTS.md`](../docs/CAD_RESULTS.md).

## Setup (once)

The CAD kernel runs in its own pinned Python 3.12 environment. Your lab's Python is not touched.

```bash
aether-lab/cad-worker/setup.sh            # Linux / macOS
```

```powershell
aether-lab\cad-worker\setup.ps1           # Windows (PowerShell)
```

`server.py` finds `cad-worker/.venv` automatically. `AETHER_CAD_PYTHON` overrides the interpreter path. Without that
environment, three-view uploads fall back to the legacy visual-hull preview, which is labelled "not CAD" everywhere.

## Use

- **In AETHER Lab:** upload a sheet and choose *Three-view sheet → Build CAD from three views* (or *Auto*). The
  **CAD document** panel shows:
  - maturity and recompute status;
  - the feature tree;
  - every parameter with its provenance, each editable (each edit is a transactional recompute);
  - the assumptions;
  - the four reprojection overlays;
  - STEP / GLB / `.aethercad` / report downloads. The File menu also has *Export STEP*.
- **HTTP:**
  - `POST /api/cad/from_sheet {image}`
  - `POST /api/cad/param {id, value | clear_override}`
  - `GET /api/cad/document`
  - `GET /api/cad/export.step|.glb|.aethercad`
  - `GET /api/cad/report.json`
- **Command line:**

```bash
cd aether-lab
cad-worker/.venv/bin/python -c "from cad import pipeline as P; d, r = P.build('sheet.png', 'out'); P.finalize(d, r, 'out')"
```

## How it works (five stages)

| Stage | Module | What it does |
|---|---|---|
| 1. Drawing interpretation | `observations.py` | **Views:** finds the views, fits each view's scale and records the conflicts between views.<br>**Measured on the ink:** profiles, wheel circles and arches, spoke and lug counts, closed regions, exhaust tips. |
| 2. AI stages | `ai.py` | **Muse Spark:** S1 view roles, S3 region labels, S8 advisory review.<br>**Muse Wonder:** S3 cross-check, S5 section hypotheses, S6 transitions, S7 alternatives.<br>**SAM 3.1:** S2 segmentation checks.<br>Every answer is strict JSON, gated against the drawing, stored, and replayed only for an identical prompt. |
| 3. Object interpretation | `vehicle.py`, `planner.py` | **Curves:** cabin curves from labelled regions, and section keypoint fields, all in mm.<br>**Planner:** writes the typed document: parameters with relations and provenance, observations, features, components, joints, assumptions. |
| 4. CAD construction | `document.py`, `ops.py`, `kernel.py` | **Recompute:** feature DAG, cached by input hash; an edit either fully succeeds or rolls back.<br>**Operations:** section sketch, skinned NURBS body, wheel wells, region pockets and imprints, revolved tyres, rims with Y-spokes, mirrors, exhaust tips, mirror copies. |
| 5. Validation and export | `validate.py`, `export.py`, `reproject.py`, `tessellate.py` | **Validation:** BRepCheck, closure, orientation, tolerances, Boolean argument analysis, interference.<br>**STEP:** XCAF export, then re-import in a fresh process and comparison.<br>**GLB:** B-rep normals, edges and face materials.<br>**Reprojection:** per-view comparison against the drawing. |

`worker.py` is the JSON-lines process `server.py` talks to (through `cad_client.py`).

## What is measured and what is not

Every parameter carries one provenance class: `measured`, `derived`, `inferred`, `assumed`, `unresolved` or
`user_confirmed`.

- **Pixels are measured; millimetres are derived.** The car sheet has no dimension, so the scale is the assumed
  overall length of 4500 mm until you confirm a real one. Editing `overall_length` rescales everything consistently.
- **Inferred:** the cross-section shape between the measured extremes. The end views give only the maximum envelope;
  Muse Wonder proposes the shape fractions, and reprojection picks between them.
- **Assumed:** recess depths, wheel-well depth and rim detail depths. Each is a named parameter with a stated range.
- **Hard drawing constraints applied:**
  - no section is wider than the end-view silhouette at its height;
  - the top, bottom and plan width at every station equal the measured curves. No model can override these.

## Tests

```bash
cad-worker/.venv/bin/python -m pytest tests/cad -q                  # all (the slow ones take minutes)
cad-worker/.venv/bin/python -m pytest tests/cad -q -m "not slow"
```

The car sheet is a third-party image. It is kept out of the repository (`tests/inputs_local/`, gitignored), and the
tests that need it skip without it. The model answers they replay are in `tests/cad/fixtures/car_hypotheses.json`.

## Limits (honest)

- **Not a uniquely determined object.** Three silhouettes plus the drawn lines constrain the outline, the cabin and
  the region outlines, not every hidden surface. The model is a reconstruction that satisfies the drawing and the
  stated assumptions.
- **No interior.** The body is a closed exterior envelope (styling solid), not sheet-metal panels.
- **Grilles and louvres are recesses plus materials**, not individually modelled cells.
- **Speed:** a full build takes about 4–10 minutes on a laptop-class CPU, most of it STEP round-trip checking. A
  parameter edit that changes the body rebuilds the body features (about 1–2 minutes).
- **Windows:** the CAD environment has been tested on Linux only so far.
