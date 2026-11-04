# AETHER — Hackathon Provenance and Scope

**Event:** Meta Global AI Developer Hackathon 2026  
**Track:** Indie Developer  
**Theme:** Push the Frontier  
**Builder:** Ng Wei Bin (individual submission)  
**Repository:** https://github.com/ngweibin050-dev/aether  
**Scope of this submission:** **AETHER Lab**, the software product described below  
**Last repository snapshot checked for this statement:** `0d38f31b69cb7f21c585f3a4b5ab5a9ba53fd7c2` (1 November 2026, 21:31 MYT)

This document distinguishes earlier AETHER work from the software developed for the hackathon. It is deliberately conservative: the existence of a file in Git is not, by itself, proof of when the underlying work was first created.

## 1. What is being submitted

AETHER is the umbrella project. **AETHER Lab is the hackathon submission**: software that takes a mechanical drawing or supported image input, uses Meta models to interpret and complete the assembly, constructs an inspectable 3D model, explains the resulting model, and evaluates a simulated holographic viewing condition.

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

The subsequent event-period commits add and refine the actual submission, including the drawing-reading and model-orchestration pipeline, 3D reconstruction and parametric geometry, the React/Three.js interface, wave-optics and eye-model simulation, Modal GPU computation, explanation validation, export, evaluation harnesses, test coverage and recorded/live demo paths.

The repository's `aether-lab/docs/CHANGELOG.md` records the detailed changes for 31 October and 1 November. `aether-lab/BUILT_DURING_EVENT.md` records the broader implementation sequence. Both should be kept aligned with the actual Git history and updated only when a change has really been completed.

- Detailed changelog: https://github.com/ngweibin050-dev/aether/blob/main/aether-lab/docs/CHANGELOG.md
- AETHER Lab architecture: https://github.com/ngweibin050-dev/aether/blob/main/aether-lab/ARCHITECTURE.md
- Evaluation results: https://github.com/ngweibin050-dev/aether/blob/main/aether-lab/docs/RESULTS.md
- Input sources: https://github.com/ngweibin050-dev/aether/blob/main/aether-lab/docs/INPUTS.md

The current repository snapshot referenced at the top of this document is dated **1 November 2026, 21:31 MYT**. Work after that point must be documented with its real commit date and must not be described as already completed in this snapshot.

## 4. Meta AI tooling and external components

AETHER Lab uses Meta models as runtime components in a multi-stage application workflow. The repository documentation identifies the roles and source files for Muse Spark, Muse Wonder, Muse Voice Transcribe and SAM 3.1 (Muse Image was used for concept illustrations until 4 November and then removed: Explain shows renders of the built model only). The application also uses non-Meta infrastructure and software, including Modal for hosted compute and third-party libraries/frameworks such as React, Vite and Three.js.

These services, models, frameworks, model weights and third-party libraries are not claimed as code written by the builder. The `.agents/skills/` directory contains imported third-party agent/design skill material; it should not be presented as original AETHER source code. The public-domain patent and NASA drawing inputs are separately attributed in `aether-lab/docs/INPUTS.md`. NASA is not a project sponsor and does not endorse AETHER.

The distinction between a model's contribution and the application's own engineering is important:

- Meta models interpret, complete, explain or segment inputs as documented.
- AETHER's own code validates structured outputs, builds and checks geometry, manages scene state, performs simulations, and renders/export the result.
- Where the system infers a hidden part, depth or relationship, that inference is not a measured fact merely because a model proposed it.

Any AI coding assistants or code-generation tools used during development should be disclosed accurately in the event submission if required by the official rules. They are distinct from the Meta models used at runtime. Do not claim third-party generated code, bundled libraries or model weights as personally authored.

## 5. Evaluation and limitations

The benchmark figures in `aether-lab/docs/RESULTS.md` are project-run measurements on the listed inputs, model configurations and compute setup. They are not independent industrial validation. The current README reports known shortcomings, including imperfect drawing precision/recall and processing times that exceed the original 90-second target on some runs.

The NASA X-2 first untouched run must remain distinguished from the later post-fix run: once that drawing was used to identify and fix a problem, the post-fix result is no longer a held-out validation result. The results document records this distinction.

No user study, industrial deployment, production-CAD certification or physical holographic-display validation is claimed here unless separately added with dated evidence.

## 6. Git history and evidence policy

The repository history is being preserved as the development record. The commit links above are intended to let a reviewer inspect the relevant snapshots and changes.

Git commit timestamps are metadata, not proof by themselves of when every line was first written. The commits inspected for this statement are **unsigned** in GitHub's verification metadata. This document therefore does not claim cryptographic attestation. It combines the visible commit sequence with the project's dated notes and the current source tree.

For the remainder of the event:

1. Make commits when real work is completed, using the actual current date and a message describing the change.
2. Keep commits small enough that a reviewer can identify the feature, tests and files changed.
3. Update `aether-lab/docs/CHANGELOG.md` with the actual date, user-visible change, key implementation files, tests run and their results.
4. Do not rewrite, squash, rebase or amend the existing event history to make the timeline look cleaner. Do not backdate commits.
5. Keep live runs, recorded replays, simulations, assumptions and measured results visibly distinguished in the UI and documentation.

This provenance statement is intended to make the boundary clear: **AETHER existed before the event; AETHER Window was an earlier prototype; AETHER Lab is the software submission whose implementation began on 29 October and was developed in the event-period commits listed above.**

## 7. Changelog entry format for the remaining event work

Add an entry to `aether-lab/docs/CHANGELOG.md` only after the work has actually been completed:

```markdown
## 2026-11-02 — [short feature name]

- **User-visible change:** [what the user can now do]
- **Implementation:** [important files/modules changed]
- **Meta calls:** [model and actual role, or “none”]
- **Verification:** [exact command or live scenario] — [actual result]
- **Known limitation:** [what remains incomplete or uncertain]
- **Commit:** [fill in the real short SHA after committing]
```

Do not write planned work as completed work, and do not report a test as passing unless it was run against the commit being described.
