# AETHER — Holographic Workbench

**Meta AI Builders Hackathon 2026 · Indie track · by Ng Wei Bin · Oct 26 – Nov 4**

AETHER is two things:

- **AETHER Lab** — the hackathon submission. Built Oct 26 – Nov 4. Give it one page of a century-old patent drawing and Meta's models turn it into a working 3D assembly, explain it part by part, and score how sharp every part would look on a holographic desk. [→ aether-lab/](aether-lab/)
- **The long-term vision** — a physical desk with a true holographic panel. No headset. The eye focuses at the object's real depth. Hands reach in from the front. Grounded in the physics research done during the hackathon. [→ AETHER_LONG_TERM_PROPOSAL.md](AETHER_LONG_TERM_PROPOSAL.md)

---

## For judges — four sections of the rubric

### 1. Impact (30 pts)
> *Real-world potential, who benefits, fit with the problem statement*

**Today (software):** Engineers and designers who reverse-engineer old machines from paper drawings. A 100-year-old patent with no scale and no second view goes in; a full 3D assembly — with gears that mesh, shafts through the stack, dimensions labelled — comes out in under 3 minutes. The explanation highlights each part on screen as it speaks. The result exports as a GLB or STL for printing or further CAD work.

**Long term (hardware):** The AETHER Desk puts that 3D assembly on a holographic workbench the size of a monitor, lying flat in the desk. The eye focuses at the object's real depth. Hands reach in from the sides. No headset, no glasses, nothing in the air. The same AI pipeline that built the model today feeds the hologram tomorrow.

The card form factor (bank-card sized, 5 mm thick, all-day battery) makes the same holographic display personal and portable — a window you hold up, not a desk you sit at.

[→ Full hardware proposal](LONG_TERM_PROPOSAL.md)

---

### 2. Use of Meta AI tooling (25 pts)
> *Creative use beyond a basic integration*

| Model | What it does in AETHER Lab | Where in code |
|---|---|---|
| **Muse Spark** (`muse-spark-1.3`) | Reads the drawing: whole sheet + 4 close-ups at 2×, each run twice (temperature 0, strict JSON); a part is kept when both passes agree or the drawing confirms it. Also writes and validates the step-by-step explanation; runs the tool-calling design agent | `agent.py`, `explain.py` |
| **Muse Wonder** (`muse-wonder-1.0`) | Engineer's completion: given Muse Spark's part list, it adds the views the drawing never shows — depths, hidden shafts, bearings, which gears mesh — each with a one-line reason | `agent.py` |
| **Muse Image** (`muse-image-1.0`) | One concept illustration per explanation step, always labelled "AI illustration — concept, not the measured model"; runs in parallel | `explain.py` |
| **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`) | Hold-to-talk commands: "Explain this machine" opens the explanation player | `agent.py` |
| **SAM 3.1** (`sam-3.1`) | Photo → model: cuts a part out of a photo, counts teeth and lobes, measures roundness; the mask feeds the 3D rebuild | `agent.py` |

Every step in the UI shows which model (or engine) did it and how long it took, e.g. "Muse Spark · read drawing · 30 s".

The models are used as a **pipeline**, not as individual Q&A endpoints: Muse Spark reads → Muse Wonder completes the unseen views → the physics engine rebuilds every part as a solid → Muse Spark explains the result grounded in the model (every part ID and number is checked in code before the step is accepted).

[→ aether-lab/ARCHITECTURE.md](aether-lab/ARCHITECTURE.md)

---

### 3. Technical Depth (20 pts)
> *Sound, refined engineering with real craft*

**The AI pipeline:**
- Two-pass reading (temperature 0 × 2) with a reconciliation step. Agreement required or drawing-level evidence needed.
- Muse Wonder completion is validated against the part list; a failed call falls back to Muse Spark (labelled in the UI).
- The explanation validator runs every part ID and every number Muse Spark produces through a code check against the built model. 0 rejected steps on all three demos.

**The physics engine (`aether-lab/engine/`):**
- Involute gears that actually mesh (module, pressure angle, tooth count from the drawing reading).
- The Window Law and sharp-zone simulation: every part is scored against a wave-optics eye model (4 mm pupil, 530 nm, 15 c/deg) for sharpness, speckle, and geometric visibility on the holographic desk.
- Phase-only encoding (pupil-GS): within 0.5% of ideal complex modulation (test 17 of 36).
- Heavy compute (hologram, eye focus sweep, desk score) runs on a Modal T4 GPU; the server redeploys Modal itself when the engine fingerprint changes.

**Measured results (live runs, Meta API, Modal GPU):**

| Input | Metric | Result |
|---|---|---|
| D — metal press, US Patent 929,594 | full run time | 108.9 s and 110.5 s (two passes) |
| C — gearbox, US Patent 1,770,035 (**held out**) | full run time | 121.1 s and 161.4 s |
| B, D, C | drawing recall / parts precision | B 76.3 / 62.9 %, D 72.3 / 77.8 %, C 73.6 / 80.4 % |
| NASA X-3 three-view | view match (side / top / front) | 100.0 / 99.5 / 98.9 % |
| NASA X-2 (**held out**) first run | view match | 92.6 / 65.8 / 95.1 % |
| All parts, all demos | pixel staircase on outlines | 0.00 % |
| Test suite | `python tests/test_physics.py` | 36 / 36 pass |

**Honest misses:** B precision (62.9 %) is below the 70 % target; C runtime (up to 161 s) exceeds the 90 s target; patent drawings have no scale (sizes are model scale throughout).

[→ aether-lab/docs/RESULTS.md](aether-lab/docs/RESULTS.md) · [→ aether-lab/ARCHITECTURE.md](aether-lab/ARCHITECTURE.md)

---

### 4. Demo (25 pts)
> *A working demo that holds up, and a demo video worth watching*

**Hosted replay (no key, no server):** Pre-computed results of all three demos — interactive 3D viewer in the browser, real GLB models, full explanation steps.
→ https://ngweibin050-dev.github.io/aether/

**Demo menu in the app:**
- **D** — metal drawing press (US Patent 929,594)
- **C** — speed-reduction gearbox (US Patent 1,770,035, held out — never used for tuning)
- **G** — NASA X-3 three-view sheet → solid mesh

Each demo has a live run (requires Meta API key) and a recorded fallback always labelled "RECORDED · not live".

**Run locally:**
```bash
cd aether-lab
pip install -r requirements.txt   # numpy, pillow, modal
# set META_API=... in .env
start.bat                          # or: python server.py → http://localhost:8765
```

Heavy physics runs on Modal GPU (`modal token new` once). Tests need no API key: `python tests/test_physics.py`.

---

## Repository layout

```
aether-lab/          ← hackathon product (built Oct 26 – Nov 4)
  agent.py           ← Meta AI pipeline: read, complete, explain, voice, SAM
  server.py          ← local Python server (serves ui/dist, handles API calls)
  engine/            ← 3D physics engine (gears, hologram, eye model, export)
  ui/                ← React + Vite + Three.js front end
  docs/              ← static replay site (GitHub Pages, no server needed)
  tests/             ← 36 physics tests; smoke tests for Meta API
  ARCHITECTURE.md    ← full system design
  BUILT_DURING_EVENT.md ← event timeline and what was built when

LONG_TERM_PROPOSAL.md  ← hardware roadmap (desk + card device)
theory/              ← physics research notes (written during hackathon, Oct 27–30)
references/          ← patent survey, prior art, external references
proposal/            ← hackathon proposal drafts, decision log
```

> The `theory/` and `references/` folders are research notes written during the hackathon as background for the physics engine and the long-term proposal. They are not product code.

---

## Honesty

- No holographic display has been built. Every optical number (sharpness, speckle, sharp zone, phase-only encoding) is a simulation with a diffraction-limited eye model.
- Patent drawings have no scale. All sizes are model scale; real sizes are unknown unless a dimension appears on the drawing.
- Live AI results are never faked. The recorded demo fallback is always labelled.
- Inputs are public-domain patent drawings and NASA graphics ([docs/INPUTS.md](aether-lab/docs/INPUTS.md)). NASA does not endorse this project.

MIT licence ([aether-lab/LICENSE](aether-lab/LICENSE)).
