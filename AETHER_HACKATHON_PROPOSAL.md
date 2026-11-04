# AETHER Lab — Hackathon Proposal

**Reconstructing undocumented machines into editable, traceable CAD with Meta's models**

Ng Wei Bin · solo · Meta Global AI Developer Hackathon 2026 · Indie Developer track · Theme: *Push the Frontier*

---

## In one paragraph

Many machines still in use have no CAD: only an old patent figure, a catalogue page or a three-view sketch. AETHER Lab
turns such a drawing into **real engineering CAD**: exact OpenCascade solids, STEP, a parts list, a connection
diagram. Muse Wonder plans the machine and **writes the CAD program itself**; Muse Spark checks the drawing,
critiques the renders and runs a 40-tool engineering assistant. AETHER's own code builds every solid, validates it,
measures it against the drawing, and labels every dimension as *measured*, *read*, *inferred* or *assumed*. The
engineer then corrects what was guessed, by chat, and the model updates in seconds without another AI call.

---

## 1. Impact: who benefits and why it matters

**The problem.** Maintenance engineers, machine restorers, museums and small factories keep legacy machines running
for which no digital model exists. Rebuilding one by hand means days of redrawing from incomplete paper, and the
result does not record which dimensions came from the drawing and which were estimated. That uncertainty is exactly
what causes a wrong spare part.

**What changes with AETHER Lab:**

| Today | With AETHER Lab |
|---|---|
| Redraw every part by hand from a drawing that has one view and no scale | Upload the drawing and get an exact CAD assembly in minutes |
| Guesses are invisible in the result | Every dimension carries its source: measured, read, inferred or assumed |
| What the drawing cannot show is silently invented | The unknowns are listed, each with what would resolve it (a dimension, another view) |
| Correcting means re-modelling | Correct a value by chat; the same program re-runs in about 10 s |
| The output is a picture | STEP, an assembly drawing with a parts list, a connection diagram, interference checks |

**Measured:** on parts with known dimensions, sizes written on the drawing come out exact, the scaled ones are a few
mm off and marked *inferred*, and correcting those brings feature diameters to zero error
([GROUND_TRUTH.md](aether-lab/docs/GROUND_TRUTH.md)).

## 2. Use of Meta AI tooling: beyond a basic integration

The models do not draw a picture; they **author engineering artefacts that code then verifies**.

| Model | Its job | Why it is more than an API call |
|---|---|---|
| **Muse Wonder** | Plans the assembly (parents, joints, evidence, unknowns, constraints) and writes the CadQuery / OpenCascade program | The model's output is *executable CAD*, run in a sandbox and held to geometric checks; it revises its own program from the checks for up to 3 rounds; edits are planned as the smallest change |
| **Muse Spark** | Checks a drawing before a build; critiques real 3D renders against a rubric; judges whether an edit was achieved; orchestrates every chat turn across 40 tools; writes explanations | A multimodal critic in the loop, and an orchestrator whose every claim (part ids, numbers, connections) is validated in code |
| **SAM 3.1** | Cuts a part out of a phone photo | The mask is measured (size, roundness, holes) for the rebuild |
| **Muse Voice Transcribe** | Hold-to-talk commands | Speech goes straight to the orchestrator |

**Models propose, code decides.** A one-shot baseline (Muse Wonder alone, no plan, checks or critic) is measured
next to the loop: on the pillow block it crashed with no solid, while the loop delivered a valid, correctable model.

## 3. Technical depth

- **Sandboxed program execution.** The model's code is parsed and checked before it runs: no imports, no file
  access, no dunders. It runs in a separate process with only CadQuery and the measured profiles available.
- **Exact geometry, validated.** Every part is an OpenCascade B-rep checked by BRepCheck, exported as STEP, and
  re-read in a fresh process.
- **Quality gates in code**, every round: floating parts, paper-thin parts, box share, parts passing through each
  other, planned-but-missing parts, mechanical constraints (coaxial, contact, clearance, gear mesh) measured on the
  solids, and a one-scale silhouette match against each drawn view.
- **Parameters with provenance**, read by the geometry through `P()`. A sandbox fix strips any model-written `P()`
  that would hide the user's corrections.
- **Checked edits.** An edit may change only its own parts. Code verifies the requested relation and reports every
  other part that moved; the model is replaced only when both pass.
- **The B-rep assembly** checks every pair of parts for contact and interference. On top of it: a connection diagram,
  the B-rep topology of each part, and an assembly drawing with an item view and parts list.
- **Cloud execution.** One Modal container per CAD job, so jobs run in parallel; progress streams live into the
  chat, Stop cancels a job, and transient API errors are retried.
- **Reproducible evidence.** The ground-truth benchmark, a five-object quality benchmark, 14 acceptance scenarios
  through the chat API, and 32 offline tests.

## 4. Demo

The video follows one machine and one claim: **from an undocumented drawing to CAD you can trust, because it shows
what it guessed.**
1. A 1909 patent drawing becomes 67 exact solids, with its unknowns listed.
2. The loop's own checks improve it within one run.
3. On a part with known dimensions, the inferred values are found, corrected by voice, and the error drops to zero.
4. The result leaves as STEP and an assembly drawing.

A hosted replay of recorded runs works without any setup.

## 5. What is not claimed

- These are engineering drafts, not certified CAD. Complex machines score 2–5 out of 10 with the critic.
- The ground truth is synthetic: drawings generated from known models. The next step is real, measured parts.
- One view cannot show depth: hidden geometry is inferred, and labelled as inferred. Real scale is assumed until a dimension is given.
- Muse Wonder can still model a feature wrongly (e.g. holes filled with "liner" solids) in ways the checks do not all catch yet.

## 6. After the hackathon

1. Ground truth on real parts, measured with calipers, and on real dimensioned drawings.
2. Reading dimension text and tolerances directly from drawings.
3. A required review step: an engineer confirms each inferred value before a model counts as final.
4. Longer term, AETHER's original vision: a holographic workbench that shows these models at true depth
   ([AETHER_LONG_TERM_PROPOSAL.md](AETHER_LONG_TERM_PROPOSAL.md)). It is simulation only; nothing optical is built.

What was built during the event, and what existed before, is set out in
[AETHER_HACKATHON_PROVENANCE.md](AETHER_HACKATHON_PROVENANCE.md).
