# AETHER Lab: the application

This folder is the hackathon product. The overview, results and screenshots are in the
[project README](../README.md); the evidence is indexed in [docs/README.md](docs/README.md).

## How a drawing becomes CAD

```
drawing / description
   │
   ├─ intake.py          Muse Spark checks the drawing: what it shows, what is missing, one question if critical
   ├─ cad/codegen.py     Muse Wonder plans every component (parent, joint, evidence, unknowns, constraints)
   │                     Muse Wonder writes the CadQuery program  ─►  sandboxed run (separate process, checked AST)
   │                     checks: BRepCheck · quality gates (cad/quality.py) · one-scale silhouette vs the drawing
   │                     real renders (cad/render_views.py) ─► Muse Spark critic ─► revise, up to 3 rounds
   │                     edits: an edit plan, only the named parts may change, relations verified, regressions reported
   └─ modal_cad.py       the same loop on Modal CPU: one container per job, live progress, cancellable
        │
        ▼
assistant.py   Muse Spark orchestrator, 40 tools: build / edit / correct a parameter / drawing / explain /
               B-rep assembly / inspect / measure / export / hologram (simulation) …
server.py, ui/ local server and the React / three.js app
```

| Module | What it does |
|---|---|
| `cad/codegen.py` | The AI-written CAD loop (plan, write, run, check, critique, revise), edit mode, parameter re-runs |
| `cad/quality.py` | Quality gates and mechanical constraints measured on the solids |
| `cad/assembly.py` | B-rep assembly: validation, contacts, interference, mates |
| `cad/drawing.py` | Technical / assembly drawing: three views, item view, parts list, connection diagram |
| `cad/worker.py` | The CAD worker (pinned CadQuery / OpenCascade environment): meshes, topology, exports |
| `prompts/` | The instruction files Muse Wonder (`cad_engineer.md`) and the critic (`cad_critic.md`) work from |
| `explain.py` | Grounded explanations: every part id, number and connection checked against the model |
| `engine/` | Geometry, scene, and the holographic-desk wave-optics simulator (long-term research) |

## Run it (Windows)

1. Python 3.12+ and a Meta Model API key in `.env` at the repository root: `META_API=...` (never commit it).
2. `cad-worker\setup.ps1` once: an isolated Python 3.12 with CadQuery 2.8 / OpenCascade.
3. Optional, for parallel and cancellable CAD jobs on Modal CPU: `python -m modal deploy modal_cad.py` (needs the
   Modal secret `aether-meta` holding `META_API`). Without it, the local CAD worker is used.
4. `start.bat`: installs the requirements and opens http://localhost:8765 once the lab is ready.

## Tests

| Command | What | Needs a key |
|---|---|---|
| `cad-worker\.venv\Scripts\python -m pytest tests/test_physics.py` | 32 offline tests (geometry, CAD, optics) | no |
| `tests/ground_truth/` (`make_parts.py`, `run_baseline.py`, `run_aether.py`, `run_corrections.py`, `score.py`, `report.py`) | Ground truth → `docs/GROUND_TRUTH.md` | yes |
| `python -m tests.acceptance_ai` | 14 scenarios through the chat API → `docs/ACCEPTANCE.md` | yes |
| `python -m tests.cad_quality_bench` | Five-object quality benchmark → `docs/CAD_QUALITY.md` | yes |

## Honesty rules the code follows

- **Models propose, code decides:** no measured value comes from a model; every dimension carries its source.
- **A failed build or edit never replaces a valid model.**
- **Recorded runs are always labelled "RECORDED · not live".**
- **No holographic display has been built;** optical results are simulations.
- Inputs are public-domain patent drawings, NASA graphics and a CC0 car sheet (`docs/INPUTS.md`); NASA does not
  endorse this project.

MIT licence (`LICENSE`).
