# AETHER Lab — one paper drawing in, a working 3D machine out

> **Migration status (Phase A, in progress):** The hackathon measurements below are historical mesh results. Machine and part-photo reconstruction, text-to-CAD, mesh imports and recorded demos are disabled. The current CAD route and STEP import are being tested; see [Phase 0/A report](docs/PHASE_0_A_REPORT.md).

Give AETHER Lab one page of a mechanical drawing — a 100-year-old patent figure with no scale and no second view —
and Meta's models turn it into a working 3D assembly: **Muse Spark** reads every part on the sheet, **Muse Wonder**
completes the views the drawing never shows (depths, hidden shafts and bearings, which gears mesh, each with its
reason), and the engine rebuilds every part as the solid it is (involute gears that mesh, pins through the stack,
plates with their holes). Muse Spark then explains the machine step by step, highlighting each part it talks about,
with every part and number checked against the built model. Finally a wave-optics eye model checks how sharp each
part would look on the **AETHER Desk**, a holographic workbench we are designing — **simulated, not built**.

Built during the Meta AI Builders Hackathon 2026 (Oct 26 – Nov 4) by Ng Wei Bin. See `BUILT_DURING_EVENT.md`.

- The hosted mesh replay (`docs/replay*`) was removed in the CAD migration (Phase A): it showed mesh reconstructions.
- Long-term holography proposal: [`docs/HOLOGRAPHY_ROADMAP.md`](docs/HOLOGRAPHY_ROADMAP.md)
- Every number below: [`docs/RESULTS.md`](docs/RESULTS.md) (live runs, real Meta API, Modal T4 GPU)

## Results

| Input (public domain) | What is measured | Result |
|---|---|---|
| D — metal drawing press, US Patent 929,594 Fig. 1 | full live run: read → complete → rebuild → desk score → explain | 108.9 s and 110.5 s (two passes); 6 explanation steps, 0 rejected |
| C — speed-reduction gearbox, US Patent 1,770,035 Fig. 1 (**held out**: never used for tuning before step 3) | full live run | 121.1 s and 161.4 s; 6 steps, 0 rejected |
| B — motor reduction gearing, US Patent 1,699,653 Fig. 1 | drawing lines on built parts (recall) / built outline on the ink (parts precision), saved readings replayed through the current rebuild | 76.3 % / 62.9 % |
| D, same measure | | 72.3 % / 77.8 % |
| C, same measure | | 73.6 % / 80.4 % |
| G — NASA X-3 three-view sheet | view match of the delivered 40,000-triangle mesh (side / top / front) | 100.0 / 99.5 / 98.9 %, 50.6–53.1 s |
| NASA X-2 three-view (**held out**, first untouched run) | view match | 92.6 / 65.8 / 95.1 % |
| NASA X-2 after the fix it revealed (no longer held out) | view match | 99.7 / 95.5 / 99.6 % |
| All built parts | pixel staircase on part outlines | 0.00 % |
| Test suite | `python tests/test_physics.py` | 36 / 36 pass |

**Honest misses:** parts precision on B (62.9 %) is below our 70 % target (dense section drawing); C's recall
(73.6 %) is below 75 % (a tighter silhouette covers fewer lines by accident); a full run takes 100–160 s against a
90 s target; X-2's tail tips are still carved from the top view; patent drawings have no scale, so every size is
**model scale, real size unknown** unless a dimension is read on the drawing (Explain and the build report say so).
Muse Wonder as the *reader* was measured too: higher recall, lower precision on D and C (F1 B 68.9 → 70.6,
D 75.0 → 72.8, C 76.9 → 78.0), so Muse Spark reads and Muse Wonder completes.

## Meta models used

| Model | What it does in AETHER Lab | Measured result |
|---|---|---|
| **Muse Spark** (`muse-spark-1.3`) | Reads the drawing: whole sheet + 4 close-ups at 2×, each twice (temperature 0, strict JSON); a part is kept when both readings agree or the drawing confirms it. Writes the step-by-step explanation; runs the tool-calling design agent | reading 29.8–41.9 s per demo run; recall / precision above; explanation 11.8–15.4 s, 6 steps, 0 rejected by the validator |
| **Muse Wonder** (`muse-wonder-1.0`, medium effort) | Engineer's completion of the unseen views: machine depth, each part's plane and thickness, hidden shafts / bearings / base with a one-line reason each, gear pairs a section does not show | 35.0–74.8 s per demo run; every added part carries its reason; a failed call falls back to Muse Spark and the step label says so |
| **Muse Image** (`muse-image-1.0`) | One concept illustration per explanation, always labelled "AI illustration — concept, not the measured model"; runs in parallel, dropped after 30 s | 9.3–20.0 s in the demo passes |
| **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`) | Hold-to-talk commands; "Explain this machine" opens the explanation | owner's test: a spoken one-line request to design a smartphone was transcribed word for word; 34 s from speech to a 15-part model with its focus sweep |
| **SAM 3.1** (`sam-3.1`) | Cuts a part out of a photo (boxes + masks); the mask gives size, roundness, holes and teeth for the rebuild | smoke test: gear found, 12 lobes counted, confidence 0.91, 4.4 s |

Every step in the UI shows which model (or engine) did it and in how many seconds, e.g.
"Muse Spark · read drawing · 30 s", "Muse Wonder · complete the unseen views · 38 s", "Modal T4 GPU · eye focus sweep".

## Current migration functionality

- Import external STEP solids as validated OpenCascade B-rep components. Their provenance is external; feature history is not invented.
- Attempt the existing multi-view B-rep route with the separate CAD worker. An unavailable worker or failed build returns an error, without a mesh fallback.
- Use derived B-rep tessellations for viewport and optics. Machine drawing, part-photo, text-to-CAD, 3V hull, mesh imports and recorded demos are unavailable.
- Export STEP and GLB from the CAD document; the old scene mesh exports are removed.

## Run locally (Windows)

1. Python 3.11+ (`pip install -r requirements.txt`: numpy, Pillow, modal) and a Meta Model API key in `.env`
   (this folder or its parent): `META_API=...`. Never commit `.env`.
2. Heavy physics (hologram, eye view, focus sweep, desk score, three-view build) runs on a Modal GPU:
   `modal token new` once; the server deploys the Modal app itself when the engine changes (`deploy_modal.bat` does it
   by hand). `AETHER_COMPUTE=local` exists only for the offline tests.
3. `python server.py`, then open http://localhost:8765 (the built UI is in `ui/dist`; Node is only needed to change
   it: `cd ui && npm install && npm run build`).
4. Tests: see [Phase 0/A report](docs/PHASE_0_A_REPORT.md) for current commands, failures and skips. The older mesh tests need migration.
5. Three-view CAD: run `cad-worker\setup.ps1` once (an isolated Python 3.12 + CadQuery/OpenCascade environment; the
   lab's own Python is untouched). CAD tests: `cad-worker\.venv\Scripts\python.exe -m pytest tests\cad -q`.

## Honesty

- **No holographic display has been built.** Every optical number (sharpness, speckle, sharp zone, phase-only
  encoding) is a simulation with a diffraction-limited eye model; see the roadmap for what is assumed.
- Sizes from patent drawings are model scale; depths, thicknesses and added parts come from the engineer's completion
  and are tagged "guessed" in every part, with the reason.
- Live AI results are never faked; recorded mesh demos have been removed.
- Inputs are public-domain patent drawings and NASA graphics (`docs/INPUTS.md`). NASA does not endorse this project.

MIT licence (`LICENSE`).
