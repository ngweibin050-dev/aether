# Phase 0 and Phase A — work in progress

## Phase 0: observed baseline

- Checkout: `feature/cad-phase-0-a`, based on `43a2c6f` from `origin/feature/true-cad-kernel`; that commit is not on `origin/main` (`cb4c771` at inspection). The commit removed engine-side visual hull, but machine/part-photo, import, demo and other mesh paths remained.
- Before the current edits: Python 3.13 local environment, `python -m pytest tests/test_physics.py -q` from both the lab and repository root: **29 passed** (about 28 s); the reported import-path problem was not reproduced in these invocations and its original cause is unidentified.
- Before edits: CAD environment Python 3.13 with CadQuery 2.8.0 and OCP 7.9.3.1.1: **25 passed, 26 skipped**, 1.36 s. Skips require the absent `tests/inputs_local/car_three_view.webp`.
- `test.jpg` at repository root: 775 × 447, SHA-256 `120ed5324b6594b3e49e61952ebbbbd8f3acc7f4a0efbc72fbfa47f41c0e3061`; inspected as a Blender viewport screenshot of a selected car mesh, not a usable orthographic drawing. It is not the benchmark drawing.
- The documented 884 × 1125 third-party car benchmark, SHA-256 prefix `a98506a4301e30ad`, is not present. Its previously reported IoUs, STEP round trip and validation cannot be reproduced or frozen here. **Baseline blocked**, not passed.
- Remaining legacy entry points inventoried: photo dispatcher (machine/part and trace), chat assembly and part tools, geometry-changing update, primitive builders, GLB/STL/OBJ and 3V controls, direct tool and Modal dispatch, scene injection and undo/redo, initial/reset scene, recorded demos, scene mesh exports, and old replay scripts/docs.

## Phase A: work done, not yet accepted

- Implemented disabled machine/part-photo and mesh tools, server-side scene edit checks, empty reset, removal of legacy mesh builders and replay data, and STEP import of validated external B-rep components. UI source removes old import/add/3V controls and provides STEP import; the committed UI bundle was rebuilt. CAD GLB remains derived from B-rep.
- Offline Phase A safety suite: `AETHER_COMPUTE=local /data/labvenv/bin/python -m pytest tests/test_phase_a.py -q` — **21 passed, 0 failed, 0 skipped**, 9.18 s. AI and Modal are mocked; no deployed Modal or browser is verified.
- Current CAD suite: `AETHER_COMPUTE=local /data/cadvenv/bin/python -m pytest tests/cad -q` — **29 passed, 0 failed, 26 skipped**, 3.68 s. The 26 skipped cases need the missing benchmark drawing. Four STEP/rollback tests include a synthetic 10 × 20 × 30 mm box, an invalid file, a surface-only STEP, API/reset, and mocked final-validation failure.
- UI production build: `cd ui && npm run build` — success, 6.11 s. A build is not a browser test.
- The car-image tests remain skipped. The existing physics suite has **15 failures and 14 passes** after removing legacy builders (19.00 s on final run): tests still call removed mesh-generation/reconstruction APIs. They must be migrated to B-rep-derived fixtures or retired with explicit rationale; do not call Phase A complete while they fail.
- Pending: complete entry-point/UI/browser/Modal and failure-atomicity coverage, resolve the old test migration, verify all scene and document transactions including concurrent requests and downstream failures, and audit remaining legacy callers and historical documentation. An external STEP document has external geometry, not invented editable construction history. No machine or part-photo CAD builder has been implemented.

## Environment and reproducibility

Local Linux, Python 3.13 isolated lab and CAD environments; CAD pins are intended for Python 3.12, which was not tested here. No live Meta, SAM, Modal, browser or benchmark run is claimed. Temporary environments, credentials, generated output and benchmark inputs are not committed. Synthetic STEP tests use an OpenCascade 10 × 20 × 30 mm box generated within the test; it is not the user image or benchmark.
