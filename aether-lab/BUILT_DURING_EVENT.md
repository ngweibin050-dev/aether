# AETHER Lab — Built During Meta AI Builders Hackathon 2026

**Builder:** Ng Wei Bin (individual submission)  
**Event build window in the participant's saved rules:** 26 October – 4 November 2026  
**Repository snapshot covered by this timeline:** up to 4 November 2026 (see the last rows of the table)

> **Scope note:** This file records the AETHER Lab software work. The repository also contains earlier AETHER background research and a historical AETHER Window prototype. Not every file in the repository was first created during the event. See the root-level `HACKATHON_PROVENANCE.md` for the explicit separation.

## Event-period product timeline

GitHub API timestamps are stored in UTC; the Malaysia times below are UTC+8.

| Date (MYT) | Evidence in Git history | Product work recorded |
|---|---|---|
| 29 Oct, 23:51 | [`da980b2`](https://github.com/ngweibin050-dev/aether/commit/da980b228f7043a77393bf72dd5f2bab4d4c22b4) | First AETHER Lab generation: initial physics/optics engine, Muse Spark tool-calling agent, local server, Modal compute app, first physics tests and initial viewer. |
| 30 Oct, 07:54 | [`55fcb07`](https://github.com/ngweibin050-dev/aether/commit/55fcb073a6d4f03e00e34ad70ac24cc0b135fadb) | Second generation: expanded geometry, compute backend and additional physics/visibility functionality. |
| 30 Oct, 15:55 | [`b26d0a3`](https://github.com/ngweibin050-dev/aether/commit/b26d0a37b1a30aa9845f449ff9a857022637ce0d) | Third generation: React/Three.js interface, wave-optics/retina work, 3D reconstruction and rebuild path, three-view processing, segmentation integration and live Meta API test. |
| 31 Oct | See commits and [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | Input routing, stable two-pass drawing reads and reconciliation, parameter validation, Modal engine fingerprint/redeploy handling, reference-run harness and recorded evaluation outputs. |
| 1 Nov, through the snapshot above | See commits and [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | Explanation player and validation, Muse Image concept illustrations, Muse Wonder completion, gear-pair handling, plausibility filtering, three-view fixes, GLB/STL export, build report, demo menu and clearly labelled recorded fallback. |

| 1 Nov, 19:42 – 2 Nov, 08:35 | [`a0de429`](https://github.com/ngweibin050-dev/aether/commit/a0de429) … [`cb4c771`](https://github.com/ngweibin050-dev/aether/commit/cb4c771) (branch `feature/true-cad-kernel`, merged as PR #1) | **True CAD kernel:** a three-view sheet now becomes a parametric OpenCascade B-rep (`cad/`). This added the pinned CadQuery/OCP worker, the `.aethercad` document with its feature history and provenance, the AI stages S1–S8, the region features (imprints and pockets), STEP export with a fresh-process round trip, per-view reprojection, and the CAD test suite. |
| 2 Nov – 4 Nov, 00:31 | [`ca2c985`](https://github.com/ngweibin050-dev/aether/commit/ca2c985) … [`8033c6d`](https://github.com/ngweibin050-dev/aether/commit/8033c6d) | CAD became the main path. Machines rebuilt from patent figures now become exact solids (`cad/assembly.py`). Added the chat assistant (`assistant.py`) and projects with autosave (`projects.py`). |
| 4 Nov, 09:29 | [`2e41fa8`](https://github.com/ngweibin050-dev/aether/commit/2e41fa8) | Intake questions (`intake.py`), refinement placed on the real surface (`refine.py`), an undo history that survives a restart (`history.py`); evidence page (`docs/EVIDENCE.md`, `python -m tests.evidence`), plain-Muse-Spark baseline, external export checks, the end-to-end story test (`docs/STORY.md`), and car body surface fairing. |
| 4 Nov (after 09:29) | this commit | View detection fix (a straight body side inside a plan view is no longer read as a ground line), a CC0 car sheet as a new test input, the recorded CAD demo, and README / architecture rewritten around the CAD workflow. |
| 4 Nov, afternoon | this commit | **AI-written CAD and one orchestrator.**
- `cad/codegen.py`: Muse Wonder plans and writes a CadQuery program for any object; it is run in a sandbox, checked against the drawing view by view, and revised.
- New chat tools `build_cad` and `edit_cad`; every drawing upload is routed to them, and the car-only rules are retired.
- Tests and records: the audit (`docs/AI_ORCHESTRATION_AUDIT.md`), 14 / 14 acceptance tests (`tests/acceptance_ai.py`, `docs/ACCEPTANCE.md`), and the roadster cycles (`docs/ai_cad_runs/`). |

Only completed work up to the snapshot date is listed. Later work must be added with its actual date after it is completed.

## Background material — not AETHER Lab product code

- The initial project/research push is dated 25 October 2026. It contains early AETHER concept material and physics/simulation work.
- `theory/AETHER_Physics_Record.md` labels its research period as 23–26 October 2026. It is pre-event background/context and must not be described as an AETHER Lab feature built during the hackathon.
- The repository history includes an earlier AETHER Window prototype. The [project decision record](https://github.com/ngweibin050-dev/aether/blob/babf2a1c3cc999803e317046b5b6d2a43f732f53/proposal/AETHER_Decision_Log.md), recorded in that snapshot, dates its design/implementation iterations to 24–25 October. Its source is visible in the 26 October snapshot [`babf2a1`](https://github.com/ngweibin050-dev/aether/tree/babf2a1c3cc999803e317046b5b6d2a43f732f53/aether-window); the subsequent 27 October change-of-direction commit [`f55de6e`](https://github.com/ngweibin050-dev/aether/commit/f55de6e48656cbe2bb0e18f7f2ea4217404c45a5) says that this was the wrong demonstration window and that the hackathon demo would be redone. AETHER Window is disclosed as earlier work, not claimed as event-built AETHER Lab functionality.
- Other theory and reference files span both pre-event and event-period work. Check each file's date/source before describing it as event-created.

## Technical and evidence boundary

- AETHER Lab is software; no physical holographic display has been built.
- Optical results are simulations, not physical measurements.
- Patent drawings without dimensions produce model-scale geometry; inferred depths and hidden parts are estimates/guesses and must be labelled as such.
- `docs/RESULTS.md` contains the detailed benchmark procedure, runs, known failure cases and hold-out distinctions. Do not quote a post-fix result as held out if that input was used to develop the fix.
- `docs/INPUTS.md` identifies the drawing sources and attribution.
- `docs/CHANGELOG.md` is the detailed change record. Add entries with real dates and test results; do not backdate them.
