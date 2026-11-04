# AETHER — Hackathon Provenance and Scope

**Event:** Meta Global AI Developer Hackathon 2026  
**Track:** Indie Developer  
**Theme:** Push the Frontier  
**Builder:** Ng Wei Bin (individual submission)  
**Repository:** https://github.com/ngweibin050-dev/aether  
**Scope of this submission:** **AETHER Lab**, the software product described below  
**Last repository snapshot checked for this statement:** `912a6e5` (4 November 2026, 22:48 MYT), plus the uncommitted work described in §3.3

This document distinguishes earlier AETHER work from the software developed for the hackathon. It is deliberately conservative: the existence of a file in Git is not, by itself, proof of when the underlying work was first created.

## 1. What is being submitted

AETHER is the umbrella project. **AETHER Lab is the hackathon submission**: software that turns a mechanical drawing (or a description, or a photo of a part) into editable engineering CAD. Muse Wonder plans the assembly and writes the CadQuery / OpenCascade program; AETHER's code runs it in a sandbox, validates every solid, checks it against the drawing, and labels every dimension with its source; Muse Spark critiques the result and runs the engineering assistant. The application also contains a simulator for a holographic viewing desk, which is a long-term research direction, not the focus of this submission.

The **AETHER Desk** and **AETHER Card** are long-term hardware concepts. They are not part of the working hackathon deliverable. No physical holographic display has been built. All optical sharpness, speckle, focus-zone and hologram results in this repository are computed simulations, not measurements from a physical display or a human-eye experiment.

AETHER Lab is intended as an early-stage reconstruction and inspection aid for engineers and designers working with legacy mechanical drawings. It is **not** represented as certified CAD, manufacturing-ready engineering data, or a replacement for a qualified engineer's review. Where a source drawing omits scale, depth or hidden geometry, the output may contain model-scale assumptions or AI-proposed geometry. Such inferred content must remain identified as estimated or guessed.

## 2. Work that existed before AETHER Lab

The following material is background or an earlier prototype. It is not claimed as newly created AETHER Lab functionality for this hackathon.

### 2.1 AETHER concept, early research and simulation

The repository's initial push is dated **25 October 2026, 12:09 MYT** (GitHub commit `44e60b2ffea1ac960dcacf13159345b00fb00348`). It contains early project proposal material, references and physics/simulation work. The file `theory/AETHER_Physics_Record.md` identifies its research period as **23–26 October 2026**. These materials provide project background; they are not the AETHER Lab application implementation.

- Initial commit: https://github.com/ngweibin050-dev/aether/commit/44e60b2ffea1ac960dcacf13159345b00fb00348
- Physics record: https://github.com/ngweibin050-dev/aether/blob/main/theory/AETHER_Physics_Record.md

### 2.2 Earlier AETHER Window prototype

An earlier software prototype called **AETHER Window** existed before the AETHER Lab implementation. Its purpose was different: turn a laptop screen into a head-tracked perspective window, with webcam-based face/eye tracking, hand gestures, voice/AI scene commands, and an experimental object-capture workflow.

The [project decision record](https://github.com/ngweibin050-dev/aether/blob/babf2a1c3cc999803e317046b5b6d2a43f732f53/proposal/AETHER_Decision_Log.md), recorded in that snapshot, dates its design and iteration to **24–25 October 2026**. Its source is visible in the repository snapshot at commit `babf2a1c3cc999803e317046b5b6d2a43f732f53` (26 October 2026, 10:01 MYT). The following commit, `f55de6e48656cbe2bb0e18f7f2ea4217404c45a5` (27 October 2026, 10:09 MYT), is explicitly titled *“Wrong demonstration window for hackathon, will redo after event starts (on 27 Oct 2026 onwards)”* and removes that earlier demonstration from the subsequent project direction.

- Earlier snapshot: https://github.com/ngweibin050-dev/aether/tree/babf2a1c3cc999803e317046b5b6d2a43f732f53/aether-window
- Replacement / change-of-direction commit: https://github.com/ngweibin050-dev/aether/commit/f55de6e48656cbe2bb0e18f7f2ea4217404c45a5

**AETHER Window is disclosed as pre-existing work, not as an AETHER Lab feature built for the event.** It is not part of the current `main` branch's AETHER Lab product tree and is not used as evidence that the AETHER Lab workflow was built during the hackathon. The Git snapshot date above is the date the source appears in that repository snapshot; the earlier development dates come from the project decision record, not from a cryptographically verified source-file creation timestamp.

## 3. AETHER Lab work created during the hackathon

The AETHER Lab implementation first appears in GitHub history in the commit **“Aether lab first generation”**, dated **29 October 2026, 23:51 MYT**:

- First AETHER Lab generation: https://github.com/ngweibin050-dev/aether/commit/da980b228f7043a77393bf72dd5f2bab4d4c22b4
- Second generation: https://github.com/ngweibin050-dev/aether/commit/55fcb073a6d4f03e00e34ad70ac24cc0b135fadb
- Third generation: https://github.com/ngweibin050-dev/aether/commit/b26d0a37b1a30aa9845f449ff9a857022637ce0d

The subsequent event-period commits add and refine the actual submission. In order:

| Date (MYT) | Commits | Work |
|---|---|---|
| 30 Oct – 1 Nov | `55fcb07` … `0d38f31` | Drawing reading with Muse Spark, completion of unseen views with Muse Wonder, 3D rebuild, React / Three.js interface, wave-optics and eye-model simulation on Modal GPU, grounded explanations, exports, replay site |
| 1 – 2 Nov | `a0de429` … `cb4c771` (PR #1) | First CAD kernel: a three-view sheet to a parametric OpenCascade B-rep with STEP export and a CAD test suite |
| 2 – 4 Nov 00:31 | `ca2c985` … `8033c6d` | CAD becomes the main path; patent machines become exact solids; the chat assistant and projects with autosave |
| 4 Nov 09:29 | `2e41fa8` | Drawing intake questions, refinement on the real surface, persistent undo history, evidence page, plain-Muse-Spark baseline |
| 4 Nov 16:04 – 22:01 | `d6d92b3`, `2a6e03e`, `6141658` | **AI-written CAD**: Muse Wonder plans and writes the CAD program for any object; quality gates, real renders and a Muse Spark critic; parameters with provenance; one orchestrator; CAD jobs on Modal CPU; acceptance tests |
| 4 Nov 22:48 | `912a6e5` | Ground-truth benchmark with a one-shot baseline; working parameter corrections; documentation |

### 3.3 Work after the last commit

Work done after `912a6e5` (late 4 November into the early hours of 5 November MYT) includes: the B-rep assembly of AI-written parts, the connection diagram, B-rep topology, the CAD feature tree, the assembly drawing (item view, parts list, connection diagram), relation-based explanations, checked edits, the `build_brep_assembly` tool, and this documentation. It will be committed with its real date and time. Whether it falls inside the official build window depends on the deadline's stated time zone; it is not backdated either way.

The detailed record is `aether-lab/BUILT_DURING_EVENT.md` and `aether-lab/docs/CHANGELOG.md`.

- Architecture: https://github.com/ngweibin050-dev/aether/blob/main/aether-lab/ARCHITECTURE.md
- Evidence: https://github.com/ngweibin050-dev/aether/blob/main/aether-lab/docs/EVIDENCE.md
- Ground truth: https://github.com/ngweibin050-dev/aether/blob/main/aether-lab/docs/GROUND_TRUTH.md
- Input sources: https://github.com/ngweibin050-dev/aether/blob/main/aether-lab/docs/INPUTS.md

## 4. Meta AI tooling and external components

AETHER Lab uses Meta models as runtime components in a multi-stage application workflow. The repository documentation identifies the roles and source files for Muse Spark, Muse Wonder, Muse Voice Transcribe and SAM 3.1 (Muse Image was used for concept illustrations until 4 November and then removed: Explain shows renders of the built model only). The application also uses non-Meta infrastructure and software, including Modal for hosted compute and third-party libraries/frameworks such as React, Vite and Three.js.

These services, models, frameworks, model weights and third-party libraries are not claimed as code written by the builder. Third-party agent/design skill material used locally during development is not part of the submitted repository. The public-domain patent and NASA drawing inputs are separately attributed in `aether-lab/docs/INPUTS.md`. NASA is not a project sponsor and does not endorse AETHER.

The distinction between a model's contribution and the application's own engineering is important:

- Meta models interpret, complete, explain or segment inputs as documented.
- AETHER's own code validates structured outputs, builds and checks geometry, manages scene state, performs simulations, and renders/export the result.
- Where the system infers a hidden part, depth or relationship, that inference is not a measured fact merely because a model proposed it.

AI coding assistants (including Anthropic's Claude Code) were used during development to write and review code and documentation under the builder's direction. They are development tools, distinct from the Meta models that run inside AETHER Lab. Bundled libraries and model weights are not claimed as authored by the builder.

## 5. Evaluation and limitations

The benchmark figures (`aether-lab/docs/GROUND_TRUTH.md`, `CAD_QUALITY.md`, `ACCEPTANCE.md`, `EVIDENCE.md`; earlier pipelines in `docs/archive/`) are project-run measurements on the listed inputs, model configurations and compute setup. They are not independent industrial validation. The ground truth uses drawings generated from known models (synthetic), and the README lists the known shortcomings.

The NASA X-2 first untouched run must remain distinguished from the later post-fix run: once that drawing was used to identify and fix a problem, the post-fix result is no longer a held-out validation result. The results document records this distinction.

No user study, industrial deployment, production-CAD certification or physical holographic-display validation is claimed here unless separately added with dated evidence.

## 6. Git history and evidence policy

The repository history is preserved as the development record; the commit links above let a reviewer inspect each
snapshot. Git timestamps are metadata, not proof of when every line was first written, and the commits are unsigned,
so no cryptographic attestation is claimed. History has not been rewritten, squashed or backdated. Live runs,
recorded replays, simulations, assumptions and measured results are labelled as such in the UI and the documentation.

**In short: AETHER existed before the event as research; AETHER Window was an earlier, abandoned prototype; AETHER Lab
is the software submission, whose implementation began on 29 October and was developed in the commits listed above.**
