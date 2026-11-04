# AETHER Lab — reconstruct undocumented machines into traceable, editable CAD

**Meta Global AI Developer Hackathon 2026 · Indie Developer track · Ng Wei Bin (solo) · built Oct 26 – Nov 4**

Many machines exist only as old drawings: one view, no scale, hidden parts, the maker long gone. AETHER turns that
incomplete evidence into **editable OpenCascade CAD that says what it measured, what it inferred and what it cannot
determine**, then lets an engineer correct it by conversation.

Upload an engineering drawing (or describe the object). **Muse plans the model and writes the CAD program
itself**: a CadQuery program on OpenCascade, for any object, with no built-in recipe for cars, presses or clamps.
AETHER runs the program in a sandbox and checks every solid. With a drawing, it also compares every view against
it, and Muse revises the program until the checks are as good as it can get them.

You then keep engineering by talking to it. One AI orchestrator chooses the tools and calls them for you:

- "make the wings thicker" (a new version of the program);
- "generate its blueprint";
- "explain how it works";
- "calculate a hologram";
- "what is its centre of mass";
- "export STEP".

- **Demo video (3 min):** _link added on submission_
- **Hosted replay (no key, no server):** https://aether-lab-delta.vercel.app/replay.html — the CAD demo opens first
- **Evidence (every number, and how to reproduce it):** [aether-lab/docs/EVIDENCE.md](aether-lab/docs/EVIDENCE.md)
- **Acceptance tests (14 / 14 through the chat API):** [aether-lab/docs/ACCEPTANCE.md](aether-lab/docs/ACCEPTANCE.md) · **Audit:** [aether-lab/docs/AI_ORCHESTRATION_AUDIT.md](aether-lab/docs/AI_ORCHESTRATION_AUDIT.md)
- **Architecture:** [aether-lab/ARCHITECTURE.md](aether-lab/ARCHITECTURE.md) · **What was built when:** [aether-lab/BUILT_DURING_EVENT.md](aether-lab/BUILT_DURING_EVENT.md)

---

## Why not just ask Muse Spark?

We gave plain Muse Spark (no tools) the same car sheet, the same part vocabulary and the same model frame, and
asked three times. (The AETHER row is the earlier rule-based pipeline; the AI-written program now replaces it,
below.) Both outputs were scored the same way: each view's silhouette, compared with the
drawing's ink.

| | IoU side | IoU top | IoU end | what you get |
|---|---|---|---|---|
| **AETHER (CAD pipeline)** | **0.974** | **0.988** | **0.978** | valid B-rep solids, STEP, feature history |
| plain Muse Spark, answer 1 | 0.861 | 0.927 | 0.922 | a list of primitives |
| plain Muse Spark, answer 2 | 0.412 | 0.928 | 0.880 | a list of primitives |
| plain Muse Spark, answer 3 | 0.324 | 0.918 | 0.909 | a list of primitives |

Two of Spark's three answers look plausible from above but are wrong from the side: the body was drawn as a
flat profile and never stood upright. Nothing in an answer says which one is right. AETHER *measures* the
sheet and checks every view, so the model reasons and the code verifies. Script: `tests/baseline_spark.py`.

## What it does

1. **Measure (code, no model).** Where the drawing has the standard views, their outlines are measured from the
   ink. The program receives them as functions (`side_top(u)`, `half_width(u)` …), so its geometry is grounded
   in the drawing.
2. **Plan and write (Muse Wonder).** Muse writes a plan: what the object is, every part, and where each size
   comes from. Then it writes the CadQuery program that builds every part as a named, coloured solid.
3. **Run (sandbox).** The program's syntax tree is checked first: no imports, no file access, no dunders,
   no `exec`/`eval`. It then runs in a separate process with only CadQuery, `math` and the measured profiles in
   scope. Every part must pass OpenCascade's BRepCheck.
4. **Check and revise.** Code compares each view with the drawing (IoU) and renders the model. Muse sees the
   overlays, scores and renders and rewrites the program. The best checked round is kept.
5. **Keep engineering by chat.** Each turn goes to one Muse Spark orchestrator that chooses among ~35 tools.
   It can change the program, make a drawing from the B-rep, explain the model, calculate a hologram, analyse
   mass properties, or export STEP/GLB/STL/3MF. A change that fails never replaces the last valid model.

## Measured results

**The loop, measured** ([CAD_QUALITY.md](aether-lab/docs/CAD_QUALITY.md); the same five objects after every change):

| object | input | solids | gates on the kept round | IoU, one scale (side / top / ends) | critic (0-10) |
|---|---|---|---|---|---|
| 1909 drawing press | ONE sectional patent view | 67 | all 28 mechanical constraints pass, 2 overlaps | - (one view) | 5 |
| engine | description | 90 | clean except 5 of 27 constraints | - | 5 |
| clamp | description | 22 | clean | - | 5 |
| roadster | CC0 four-view drawing | 99 | 5 floating, 8 of 29 constraints | 0.87 / 0.94 / 0.86 / 0.88 | 3 |
| car | four-view drawing (third-party, local only) | 118 | 55 % box-like, 15 floating | 0.91 / 0.94 / 0.83 / 0.83 | 2 |

What the code checks do within one run, for example the press:
- parts passing through each other: 35 → 2;
- plain boxes: 39 % → 0 %;
- failed mechanical constraints: 11 → 0;
- critic: 2 → 5.

The press's plan lists what one view cannot fix, each with what would resolve it:
- the machine's depth (plan and end views);
- the real scale (a dimensioned drawing);
- the drive train behind the cover (the patent text);
- the blade mechanism cut off the sheet (the uncropped sheet).

Every key dimension carries its provenance (measured, read, inferred, assumed or user). An engineer can correct a value
by chat, and the same program re-runs without being rewritten.

**These are not finished designs yet.** The critic scores 2-5 out of 10, and the cars are the weakest. The targets
(IoU >= 0.95 per view on four-view drawings, 0 floating or overlapping parts, critic >= 9) are goals, not results. The
earlier roadster cycles, measured with the shape-only score, are in
[docs/ai_cad_runs](aether-lab/docs/ai_cad_runs/README.md).

**Acceptance tests ([ACCEPTANCE.md](aether-lab/docs/ACCEPTANCE.md)): 14 / 14 through the chat API.**
- A three-view jet built from the drawing: an aircraft, with no dedicated code.
- Its geometry changed by chat (a new program version).
- A blueprint generated from the B-rep, and the Explain panel opened with 12 steps.
- A hologram calculated, then recalculated at 600 mm.
- Mass properties measured; STEP, STL, GLB and 3MF exported.
- One request that combined several tools, and a follow-up that said only "it".
- An invalid request refused with nothing changed.
- A clamp built from a description alone.

One test passed only by being honest: AETHER has no general motion solver, and it said so.

**Earlier pipeline** (car-only rules, from [EVIDENCE.md](aether-lab/docs/EVIDENCE.md); kept as the record of
what was measured with it):

| What | Result |
|---|---|
| Three-view car sheet → B-rep, silhouette IoU vs the drawing | side 0.980 · top 0.991 · front 0.975 · rear 0.975 |
| Public CC0 car sheet (Shelby Cobra four-view, Wikimedia Commons), first full run | side 0.905 · top 0.971 · front 0.775 · rear 0.781; 9 / 9 valid solids; STEP 9 / 9. Lower because it is an **open roadster**: the vehicle module assumes a closed body, so it covers the cockpit and builds neither the windscreen nor the roll bar ([EVIDENCE §1b](aether-lab/docs/EVIDENCE.md)) |
| Solids valid (OpenCascade `BRepCheck`) | 11 / 11 |
| STEP round trip, re-read in a fresh process | 11 / 11, volume within 6.7e-09 |
| Whole workflow through the app's API (`tests/e2e_story.py`) | 8 / 8 steps: drawing → CAD → refine → section → pocket → validate → STEP → restart + undo |
| Refine by chat / everyday requests | 5 / 5 · 16 / 16 |
| Exports opened outside AETHER (trimesh) | 9 / 9 GLB / STL / 3MF, size within 0.004 mm |

**Two workflows, two levels of evidence.**

- **Three-view sheet → verified B-rep** (above). Every view is checked against the drawing.
- **Single-view patent figure → inferred mechanism.** One view cannot show depth, so Muse Wonder proposes the
  hidden shafts, bearings and depths, and each one is labelled as inferred. 79–86 % of the drawing's lines land
  on built parts, but only **60–72 %** of the built outline lies on the drawing's ink. That is reported, not
  hidden ([EVIDENCE §3](aether-lab/docs/EVIDENCE.md#3-drawing---mechanism-patent-drawings)).

**Measured vs assumed.** The sheets carry no dimension, so the real size is *assumed* (and shown as assumed)
until the user gives one. Shape is measured, size is not. Agreement in every view is necessary but not
sufficient: the cross-sections between the views are inferred.

## Meta models, and what each one decides

| Model | What it decides in AETHER |
|---|---|
| **Muse Spark** (`muse-spark-1.3`) | reads a sheet like an engineer taking a job (what it shows, what is missing, the one question to ask); labels parts and regions; runs every chat turn as a tool loop; writes grounded explanations, where every part id and number is checked in code |
| **Muse Wonder** (`muse-wonder-1.0`) | writes and revises the CAD program for any object, from a drawing or a description; plans every part and where its size comes from |
| **SAM 3.1** (`sam-3.1`) | finds regions on the drawing (glass, lights, intakes) that become B-rep imprints and pockets; cuts a part out of a photo |
| **Muse Image** (`muse-image-1.0`) | one concept illustration per explanation, always labelled "not the measured model" |
| **Muse Voice Transcribe** | hold-to-talk commands |

Models propose, code decides. No model output is ever executed, and no model sets a measured value.

## Try it

**No setup:** the [hosted replay](https://aether-lab-delta.vercel.app/replay.html) shows recorded runs, each
labelled "RECORDED · not live". It has the CAD car (B-rep viewer, IoU per view, STEP download) and two
patent mechanisms.

**Run it locally** (Windows; Python 3.12+; a Meta Model API key for live runs):

```bash
cd aether-lab
cad-worker\setup.ps1             # once: the pinned CAD kernel env (CadQuery 2.8 / OpenCascade)
# put META_API=... in .env (repo root)
python -m modal deploy modal_cad.py   # optional: CAD jobs on Modal CPU, parallel and cancellable
                                 # (needs the Modal secret aether-meta with META_API; else the local CAD worker is used)
start.bat                        # http://localhost:8765 — Demo menu: CAD car (recorded), D press, C gearbox
```

**Check the numbers without a key:** `python -m tests.test_physics`, `python -m tests.test_history`,
`python -m tests.baseline_spark --score` (re-scores the saved Spark answers), `python -m tests.evidence`.

## Limits

- The demo car sheet in the evidence is a third-party drawing. It is used for measurement only and is not
  redistributed in this repository. The [CC0 Cobra sheet](aether-lab/docs/INPUTS.md) is the public, reproducible
  input.
- Model-written programs are executed, inside the sandbox described above. That is a deliberate change from the
  earlier rule that no model output is ever executed.
- Outline measurement needs the standard views (side, top, two ends). Other sheets are read from the image by Muse,
  checked by renders, and their sizes are labelled as estimates.
- There is no general motion or collision solver yet. Physical parameters (mass, friction, torque) are asked for,
  never invented.
- Sizes are assumed until a dimension is given. Hidden geometry is inferred and labelled.
- Single-view mechanisms: about 1 in 3 built outline pixels is not on the drawing.

## The long-term vision: a holographic desk

AETHER started as research toward a no-headset holographic workbench. The same CAD model would sit at its
true depth on a desk panel. The wave-optics engine (phase holograms, an eye model, a "Window Law") is in
`aether-lab/engine/` and [ARCHITECTURE Part B](aether-lab/ARCHITECTURE.md). **All of it is simulation. No
display has been built.** The roadmap is in [AETHER_LONG_TERM_PROPOSAL.md](AETHER_LONG_TERM_PROPOSAL.md).

## Repository layout

```
aether-lab/            the hackathon product
  cad/                 drawing → parametric OpenCascade B-rep (runs in cad-worker/.venv)
  assistant.py         Muse Spark chat tool loop; refine.py, intake.py, history.py, projects.py
  agent.py, explain.py patent-figure reading, completion and grounded explanation
  engine/              mechanism rebuild (gears, outlines) + holographic-desk simulation
  server.py, ui/       local server and React / three.js app
  tests/               evidence, e2e story, Spark baseline, export checks, physics tests
  docs/                EVIDENCE, STORY, RESULTS, INPUTS, hosted replay (index.html, replay.html)
theory/, references/   research notes behind the long-term proposal (not product code)
```

Inputs are public-domain patent drawings, NASA graphics and a CC0 car sheet ([INPUTS.md](aether-lab/docs/INPUTS.md)),
except the third-party car sheet noted above. NASA does not endorse this project. MIT licence
([aether-lab/LICENSE](aether-lab/LICENSE)).
