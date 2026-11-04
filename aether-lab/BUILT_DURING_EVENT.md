# AETHER Lab — Built During the Meta Global AI Developer Hackathon 2026

**Builder:** Ng Wei Bin (individual submission)
**Event build window (from the participant's saved rules):** 26 October – 4 November 2026

> This file records the AETHER Lab software work. The repository also holds earlier AETHER background research and a
> historical AETHER Window prototype; see [`../AETHER_HACKATHON_PROVENANCE.md`](../AETHER_HACKATHON_PROVENANCE.md) for
> the separation. Times are Malaysia time (UTC+8); commit links open on GitHub.

## Timeline

| Date (MYT) | Commits | Work |
|---|---|---|
| 29 Oct, 23:51 | [`da980b2`](https://github.com/ngweibin050-dev/aether/commit/da980b228f7043a77393bf72dd5f2bab4d4c22b4) | First AETHER Lab generation: physics / optics engine, Muse Spark tool-calling agent, local server, Modal compute app, first tests and viewer |
| 30 Oct | [`55fcb07`](https://github.com/ngweibin050-dev/aether/commit/55fcb073a6d4f03e00e34ad70ac24cc0b135fadb), [`b26d0a3`](https://github.com/ngweibin050-dev/aether/commit/b26d0a37b1a30aa9845f449ff9a857022637ce0d) | Geometry and compute backend; React / Three.js interface; 3D rebuild; three-view processing; SAM 3.1 integration; live Meta API test |
| 31 Oct | see [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | Input routing, two-pass drawing reads, parameter validation, Modal engine redeploy, reference-run harness |
| 1 Nov | see [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | Explanation player and validation, Muse Wonder completion, gear pairs, exports, build report, demo menu with labelled recorded fallback, replay site |
| 1 Nov 19:42 – 2 Nov 08:35 | [`a0de429`](https://github.com/ngweibin050-dev/aether/commit/a0de429) … [`cb4c771`](https://github.com/ngweibin050-dev/aether/commit/cb4c771) (PR #1) | First CAD kernel: three-view sheet → parametric OpenCascade B-rep, `.aethercad` document, STEP with fresh-process round trip, CAD test suite |
| 2 Nov – 4 Nov 00:31 | [`ca2c985`](https://github.com/ngweibin050-dev/aether/commit/ca2c985) … [`8033c6d`](https://github.com/ngweibin050-dev/aether/commit/8033c6d) | CAD becomes the main path; patent machines become exact solids (`cad/assembly.py`); chat assistant (`assistant.py`); projects with autosave |
| 4 Nov, 09:29 | [`2e41fa8`](https://github.com/ngweibin050-dev/aether/commit/2e41fa8) | Drawing intake questions (`intake.py`), refinement on the real surface (`refine.py`), persistent undo (`history.py`), evidence page, plain-Muse-Spark baseline, external export checks |
| 4 Nov, 16:04 | [`d6d92b3`](https://github.com/ngweibin050-dev/aether/commit/d6d92b3) | **AI-written CAD:** `cad/codegen.py`, where Muse Wonder plans and writes a CadQuery program for any object, run in a sandbox and revised; one orchestrator with `build_cad` / `edit_cad`; car-only rules retired; 14 acceptance scenarios |
| 4 Nov, 19:58 – 22:01 | [`2a6e03e`](https://github.com/ngweibin050-dev/aether/commit/2a6e03e), [`6141658`](https://github.com/ngweibin050-dev/aether/commit/6141658) | Quality loop (instruction files, structured plan with constraints and unknowns, gates in `cad/quality.py`, real renders, Muse Spark critic, building blocks), parameters with provenance and `set_cad_param`, CAD jobs on Modal CPU (`modal_cad.py`, live progress, cancel), lighter display meshes, project and UI fixes |
| 4 Nov, 22:48 | [`912a6e5`](https://github.com/ngweibin050-dev/aether/commit/912a6e5) | Ground-truth benchmark (`tests/ground_truth/`, `docs/GROUND_TRUTH.md`) with a one-shot baseline; parameter corrections fixed (model-written `P()` removed in the sandbox); renderer cache fix |
| after 22:48 (uncommitted at the time of writing) | — | B-rep assembly of AI-written parts; connection diagram; B-rep topology; CAD feature tree; assembly drawing (item view, parts list, connection diagram); relation-based explanations; checked edits (`cad/codegen.py` edit mode); `build_brep_assembly` tool; X-ray, selection and move fixes; documentation. Committed with its real date and time |

## Background material, not AETHER Lab product code

- The initial push (25 October 2026) holds early AETHER concept material and physics / simulation work.
  `theory/AETHER_Physics_Record.md` dates its research to 23–26 October 2026: pre-event background.
- An earlier **AETHER Window** prototype (24–25 October) is visible in snapshot
  [`babf2a1`](https://github.com/ngweibin050-dev/aether/tree/babf2a1c3cc999803e317046b5b6d2a43f732f53/aether-window) and was
  dropped on 27 October ([`f55de6e`](https://github.com/ngweibin050-dev/aether/commit/f55de6e48656cbe2bb0e18f7f2ea4217404c45a5)).
  It is disclosed as earlier work, not claimed as an event-built feature.
- Other `theory/` and `references/` files span pre-event and event-period research; check each file's date before
  describing it as event-created.

## Evidence boundary

- AETHER Lab is software. No physical holographic display has been built; optical results are simulations.
- Drawings without dimensions give model-scale geometry. Inferred depths and hidden parts are labelled as such.
- Measured results: [`docs/GROUND_TRUTH.md`](docs/GROUND_TRUTH.md), [`docs/CAD_QUALITY.md`](docs/CAD_QUALITY.md),
  [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md), [`docs/EVIDENCE.md`](docs/EVIDENCE.md); results of the earlier pipelines
  are kept in [`docs/archive/`](docs/archive/).
