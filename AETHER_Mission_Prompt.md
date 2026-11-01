# Mission: take AETHER Lab from 56/100 to a top-5 submission (technical side)

Paste everything below this line into Claude Code (VS Code), with `C:\Aether` open as the workspace.
`C:\Aether\CLAUDE.md` holds the standing rules; read it first and obey it over anything else.

---

You are the lead engineer finishing **AETHER Lab** (`C:\Aether\aether-lab`) for the Meta AI Builders Hackathon 2026
(Indie track, theme "Push the Frontier"). The submission closes **Nov 5 2026, 10:00 MYT**. The owner (Ng Wei Bin)
records the 3-minute video only after you finish, so every technical piece must be finished, verified and stable
before then. Plan the work so the product is demo-ready by **Nov 3, 22:00 MYT**, leaving a day for the video.

The goal is the maximum score under the official rubric. No one can promise 100/100. Your job is to remove every
reason a strict Meta judge would take a point away, and to prove each claim with a measurement.

## 0. Read first (in this order), then stop and report
1. `C:\Aether\CLAUDE.md` (rules).
2. `C:\Aether\proposal\hackathon_ready\Meta AI Builders Hackathon 2026 Rules.txt` and
   `C:\Aether\proposal\hackathon_ready\AETHER_Hackathon_Proposal.md`.
3. `C:\Aether\aether-lab\README.md`, `ARCHITECTURE.md`, `agent.py`, `server.py`, `compute.py`, `vision.py`,
   `engine\*.py` (skim; read `lab.py`, `rebuild.py`, `interpret.py`, `circles.py`, `sheet.py`, `retina.py` fully),
   `ui\src\store.js`, `ui\src\ui\*.jsx`, `tests\test_physics.py`.
4. The physics background you need: `C:\Aether\theory\AETHER_Physics_v9_1D_Focus_zh.md`,
   `AETHER_Physics_v11_Speckle_zh.md`, `AETHER_Physics_v12_Card_Incoherent_zh.md`,
   `AETHER_Physics_v13_Desk_Front_zh.md`, `AETHER_Lab_Audit_Fixes_2026-10-30_zh.md`,
   `AETHER_Phase_Only_Pupil_GS_and_3D_Rebuild_2026-10-30_zh.md`.

Then run the test suite and the Meta smoke test, and send the owner (in Chinese) a short report: what works,
what fails, and your plan with times. Wait for their "go" before step 2 (repo work). Steps 1, 3–8 you may start
right after the report.

## The strict review this mission answers (2026-10-31, 56/100)
| Criterion | Now | Why points were lost |
|---|---|---|
| Impact (30) | 14 | No real user today (the holographic desk is not built). Six features, no clear core. No numbers (time saved, parts recovered). The strongest feature (drawing → 3D) is not even in the README. |
| Meta AI tooling (25) | 17 | Deep Muse Spark use (agent + tool calls, physics closed loop 55.5% → 89.4%, drawing reading with 4 close-ups, region naming, engineer completion of unseen views) and SAM 3.1 live. But the newest Spark features were never run with the real key, voice is untested, and Spark's reading of the same drawing varies run to run (26 parts one run, 13 the next). |
| Technical depth (20) | 15 | Real wave optics (point CGH, band-limited ASM, eye model, phase-only pupil GS), involute gears, three-view hull (97–99% outline match), circle measurement, 23 tests, Modal GPU. Lost on: many dimensions are "assumed", fragile deployment history (stale Modal engine, black screen), no export of the result. |
| Demo (25) | 10 | No video yet (owner's job), no fixed demo path, live AI results vary, no fallback if the network is slow. |

## The story to build toward (one sentence, everywhere)
**"AETHER turns any engineering drawing — even a single view — into a working 3D assembly that Meta's models
complete like a senior engineer, then proves whether a no-headset holographic desk could show it sharply."**
Users: maintenance and manufacturing engineers with legacy paper drawings; holographic display engineers.
Everything in the UI, README and API naming should serve this story. Features that do not serve it stay in the
code but leave the main path (they are not deleted).

## Skills and tools you must use (where each one fits)
Before step 1, list every skill you can load (`~/.claude/skills`, `C:\Aether\.claude\skills`, and the skills in
`C:\Aether\.agents\skills`, which were installed for other agents: read their `SKILL.md` directly if they are not
loaded for you). Tell the owner which ones you found. Then use them like this:
| Skill | Use it for | Step |
|---|---|---|
| `chrome-devtools-cli` (Chrome DevTools MCP) | Drive the real UI at http://localhost:8765: run the 3 demo scenarios, read console errors, watch network calls to `/api/*`, record a performance trace, take screenshots for README and RESULTS.md | 1, 3, 7 |
| `impeccable` | UI audit and polish of the main path (Demo menu, chat steps, Physics panel, check images): run its audit/critique, then polish, harden and clarify. Keep the existing look (glass panels, holo shader) | 4, 5, 7 |
| `design-taste-frontend` | Review layout, type and colour of new UI parts (added-parts list, checks, export, status chip) so they match the rest | 4, 5, 7 |
| `web-design-guidelines` | Final accessibility and UX check of the UI before "ready for video" | final checklist |
| `graphify` | Build or refresh the code map of `aether-lab` (there is already a `graphify-out\` folder) to find callers and dead code fast in step 0; keep `graphify-out\` out of the submission repo | 0, 2 |
| `agent-reach` | Read its `SKILL.md` first; use it only if it helps check facts on the web (e.g. Meta API docs at dev.meta.ai/docs). Never send keys or the owner's files anywhere through it | 3, 8 |
| `skill-creator` | Not needed, unless the owner asks for a reusable skill | — |
| `reverse-engineer-anything` (REA) | Not for this project. Do not use it on AETHER or on third-party software | — |
A skill that does not fit a step is not used just to say it was used. If a skill wants to rewrite large parts of
the UI, change the product story, or install packages, ask the owner first. Report in each step which skills you
used and what they found.

## Work plan (each step has a definition of done; do not mark a step done without its proof)

### 1. Baseline and live verification (Meta tooling, Demo)
- Run `tests\test_physics.py` and `tests\smoke_meta.py`. Fix anything red.
- Run the two reference inputs with the real key, 3 runs each, through the real server path
  (write `tests\run_reference.py` that calls the same functions the UI calls and saves JSON + images to
  `output\reference\<input>\run<k>\`):
  - one-view machine: `tests\blueprint_example2.jpg` (and the dense machine sheet the owner used on Oct 30, if present);
  - three-view car: `tests\car_three_view.gif`.
- Record per run: parts built, `drawing_lines_on_built_parts_pct`, view-match IoU (car), gear pairs, time per stage,
  Spark tokens/calls, errors.
- **Done when:** `docs\RESULTS.md` has a table of the 6 runs with mean and spread, and every failure is either fixed
  or listed with its cause.

### 2. A submission repo judges can trust (gate: disqualification risk)
- `aether-lab` currently lives inside the old `C:\Aether` repo next to pre-event research. Propose to the owner
  (wait for "go"): a clean folder `C:\AetherLab-submission\` that is a copy of `aether-lab` without `.env`,
  `__pycache__`, `output\`, `graphify-out\`, `ui\node_modules\`, test scratch files. The owner creates the new
  GitHub repo and does `git init` / commit / push themselves; you give them the exact commands.
- Write in that folder:
  - `README.md` — the one-sentence story, a 30-second GIF/screenshot placeholder list, the problem with numbers
    from RESULTS.md, how Meta models are used (a table: model → what it decides → where in code),
    architecture diagram (Mermaid), run instructions (Windows, one-click `start.bat`), test instructions,
    honest limits ("simulation, not a built display"; what is assumed).
  - `BUILT_DURING_EVENT.md` — dated list of what was built Oct 26 – Nov 4 (use file history and ARCHITECTURE.md),
    and a short "pre-event background" section naming the physics notes v4–v13 as prior research NOT included as code.
  - `LICENSE` (MIT unless the owner says otherwise).
- Secret scan before the owner pushes: search the folder for `LLM_`, `sk-`, `api_key`, `Bearer `, `META_API=`,
  `.env`; report zero hits or fix.
- **Done when:** the folder runs from a fresh clone (`pip install -r requirements.txt`, `python server.py`,
  open :8765) and the secret scan is clean.

### 3. Make the AI reading reliable (Meta tooling, Demo)
- Spark drawing reading (`agent._read_machine`, `_spark_read_drawing`): ask for strict JSON with a schema, use the
  lowest-variance settings the API supports (check the docs for temperature / seed / response_format), retry once
  on invalid JSON, and run the whole-sheet read twice: keep a part when both reads agree (box IoU ≥ 0.4, same kind)
  OR when a measured circle (`engine\circles.py`) confirms it; log what was dropped.
- Give every Meta call a timeout, a clear error in the chat steps, and no silent fallback to made-up data.
- **Done when:** on the 3 reference runs the part count spread is ≤ 15% and `drawing_lines_on_built_parts_pct`
  is ≥ 75% on the machine sheet (report the real numbers either way).

### 4. Engineer completion that a judge can see (Meta tooling, Impact)
- `_spark_complete` (unseen views): make Spark return, per added hidden part, a one-line engineering reason
  ("shaft: gear 3 has no axle; bearing: shaft passes the housing wall"). Show these reasons in the UI as a list
  next to the model, and highlight added parts in a distinct colour with an "(added by Muse Spark)" tag.
- Add a "Why it works" check computed by the engine, not by the model: every gear has a shaft, meshing gears share a
  plane and module, no two solids intersect (voxel or bounding-volume test), every moving part has a pivot.
  Spark's completion is applied only where these checks pass; failures are shown.
- **Done when:** on the machine sheet the UI lists the added parts with reasons and the checks show pass/fail counts.

### 5. Results engineers can take away (Impact, Technical depth)
- Export the built assembly: GLB (part names and colours kept) and STL (one file per part in a zip, or one merged
  file), from both the UI (File → Export) and a tool the agent can call. Use three.js `GLTFExporter` in the UI or a
  small numpy STL/GLB writer in Python; no new heavy dependency.
- Export a one-page "build report" (HTML or Markdown) per model: parts list with source of each dimension
  (measured / read by Spark / assumed), gear pairs, checks, desk sharpness.
- **Done when:** an exported GLB opens in Blender with the right part names and an STL opens in a slicer.

### 6. The holographic-desk proof (Technical depth, Impact)
- Keep the physics honest and tied to the theory notes. One click after a model is built: Muse Spark runs
  `desk_score` / `focus_sweep` on Modal, explains which parts are sharp at which height, and offers "Fix for desk"
  (the existing closed loop). Show the before/after numbers.
- Re-read v9/v11/v12/v13: check that the eye view, speckle and sharp zone in `engine\retina.py` / `eye.py` match the
  notes (pupil, columns, sparse-group speckle k=3, oblique eye at [0,-450,540]). Fix and test any mismatch.
- **Done when:** a new test proves each of these against the numbers in the notes, and the UI shows the sharp zone
  in mm.

### 7. Demo path that cannot break (Demo)
- A "Demo" menu with 3 fixed scenarios, in story order:
  1. one-view machine drawing → 3D assembly with Spark completion → checks → explode/section → export;
  2. three-view car sheet → named, multi-part body;
  3. "Can the desk show it?" → focus sweep → Fix for desk.
  Each runs live. If a live call fails or takes > 60 s, the UI offers "show the recorded run" from
  `output\reference` with a visible "recorded" badge.
- Startup self-check on `server.py` start: Meta key present (do not print it), Meta API reachable, Modal engine
  version matches, UI built. Show the result as a status chip.
- Performance: measure each stage; the machine path should finish in under 90 s live. Show elapsed time per step.
- Remove or hide anything on the main path that is untested (voice, hand mode) unless step 8 makes it work.
- **Done when:** the owner can run all 3 scenarios twice in a row without an error or a black screen
  (test it with a headless browser script, e.g. Playwright, and with the real server).

### 8. Optional, only if 1–7 are done before Nov 3 12:00 MYT
- Voice: make push-to-talk work with Muse Voice Transcribe and test with a real recording.
- SAM 3.1 on drawings: use it to cut out the parts Spark names, to improve outline accuracy, and measure the gain.
- Muse Spark "explain this machine": a grounded explanation that names parts by their ids and how motion flows
  (gear → link → lever), with the parts highlighting in the 3D view as it speaks.

## How to report
- After each step: in Chinese, at most 10 lines: what changed (files), proof (command and result, numbers),
  what is still unverified, and the commit message the owner should use (English, one line + bullets).
- Keep `docs\RESULTS.md` and `docs\CHANGELOG.md` up to date; the README numbers must come from RESULTS.md.
- If something cannot reach its target, say so with the measured number. Do not hide it and do not lower the
  target silently.
- Ask the owner only when a decision changes the product's story, needs money, or touches GitHub; otherwise choose
  the most likely option, do it, and say what you chose.

## Final checklist (all must be true before you tell the owner "ready for video")
- [ ] All tests pass (`test_physics.py` + new tests), `smoke_meta.py` passes with the real key.
- [ ] `docs\RESULTS.md` has real numbers from ≥ 3 live runs per reference input.
- [ ] The submission folder runs from a fresh copy; secret scan clean; README, BUILT_DURING_EVENT.md, LICENSE present.
- [ ] The 3 demo scenarios run twice in a row live, each with a recorded fallback that is labelled.
- [ ] Every Meta model call is visible in the UI's step list with what it decided.
- [ ] Export GLB/STL works and opens in Blender.
- [ ] Every assumed number is labelled "assumed" in the UI and the build report.
- [ ] Nothing claims a physical holographic display exists.
- [ ] A final DevTools run of all 3 scenarios shows no console errors, and the `impeccable` audit has no open high-severity issues.
