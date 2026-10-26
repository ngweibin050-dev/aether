# AETHER

**A working head-tracked 3D window for any laptop, a first-principles study of true holography, and a long-term research proposal for a card-sized holographic device.**

AETHER has three parts, in order of how real they are today:

1. **AETHER Window** (working demo): software that turns a laptop and webcam into a head-tracked 3D window you control with your hands.
2. **Physics record** (analysis): first-principles constraints on what a true hologram can and cannot do, with the Python that produced every number.
3. **The card** (vision): a bank-card-sized device (85.6 × 54 mm) that shows a true hologram in free air. This is a research proposal, not a product.

> **Honesty note.** AETHER Window is per-eye perspective rendering on an ordinary screen. It is **not** a hologram. The physics results are candidate constraints that have not been peer reviewed. Nothing in this repository is a working holographic display.

---

## 1. AETHER Window (the demo)

A webcam tracks your eyes. The screen is rendered as a window into a 3D room, so objects sit in front of and behind the glass and stay fixed in space when you move your head. No glasses, no extra hardware.

| Feature | What it does |
| --- | --- |
| Head-tracked window | Off-axis projection from your real eye position (MediaPipe Face Landmarker, interpupillary distance + iris ranging, One-Euro filtering). |
| Hand gestures | Pinch and drag to rotate, two-hand pinch and pull apart to explode a model, point to highlight a part. |
| Voice commands | Hold Space and speak. A local keyword parser maps speech to scene actions today; a language model can be plugged in (see below). |
| 360° scan to 3D | Press **P**, turn an object one full circle in front of the camera, press **P** again. Hands are cut out, outlines are carved into a mesh (visual hull + surface nets), **E** exports `.obj`. |
| Two viewers | Press **T** to split the screen into two windows, one per tracked viewer. |
| Window Law demo | Press **W** to show a card-sized window with live numbers explaining why every optical hologram behaves like a window (H1 below). |
| Languages | Press **L** to switch English / 中文. |

### Run it

**Windows**

1. Install [Node.js](https://nodejs.org) LTS.
2. Double-click `aether-window/start.bat`. The browser opens http://localhost:8787.
3. Allow the camera.

**macOS / Linux**

```bash
cd aether-window
node server.mjs
# open http://localhost:8787 in Chrome
```

Three.js, MediaPipe and all models are bundled, so there is no `npm install` and it runs offline (speech recognition uses Chrome's Web Speech API and needs internet; you can type commands instead).

**First-time calibration (about 30 seconds)**

1. Press **C**, hold a bank card against the screen, resize the frame with `[` and `]` until it matches, press Enter.
2. Sit 50 cm from the screen and press **D**.
3. Press **F** for full screen. Press **M** for mouse viewpoint if the camera is unavailable. Press **H** for all keys.

### AI models: status

**Meta Llama and SAM are not connected yet.** The server already has a provider slot for them (`aether-window/ai.config.example.json`, copy to `ai.config.json`, which is git-ignored), and they will be wired in and demonstrated during the **Meta Global AI Developer Hackathon (27 Oct – 5 Nov 2026)**. Until then the demo runs on the local keyword parser and the in-browser visual-hull scanner. The language model is restricted to a fixed action schema (`explode`, `rotate`, `select`, `clear_select`, `load_scene`, `run`, `reset`, `capture`), so it cannot break the scene.

See [`aether-window/README.md`](aether-window/README.md) for the full key list, architecture and known limits.

### Known limits

- Depth is correct only for the tracked viewer(s); bystanders see a skewed image.
- Iris/IPD distance accuracy on real users has not been measured.
- Webcam hand tracking depends on lighting.
- Visual-hull scans cannot capture concave areas (the inside of a cup is filled in).

---

## 2. Physics (candidate constraints)

Starting point: light obeys the linear wave equation in air, the eye senses only the wave entering its pupil, and energy is conserved. Full derivations are in [`theory/AETHER_Physics_Record.md`](theory/AETHER_Physics_Record.md); scripts and figures are in [`theory/simulations/`](theory/simulations/).

| Result | Statement | Status |
| --- | --- | --- |
| **H1 Window constraint** | An application of the known Kirchhoff–Helmholtz integral: with passive optics, you see an image point only if the line from your eye through it ends on the device. A true hologram from a card is a window. A card at 40 cm spans about 12° × 8°. | Known physics, applied to this device |
| **Superoscillation workaround** | Faking light from outside the window costs roughly e⁻²⁰⁰⁰ in energy across a 4 mm pupil. | Impractical under our assumptions |
| **H3 Scattering-focus bound** | Using room walls as the hologram: focusing efficiency ≤ N / N_total, about 0.008% for a 60 m² room, so a human-size image would need kilowatts of laser. | Candidate result, not peer reviewed |
| **Air-emission screening** | The only route left for linear passive optics is for the air itself to emit light. Photon and molecule budgets are not the bottleneck; a low-threshold excitation pathway in N₂/O₂ is. Today this takes plasma intensities (~10¹³ W/cm²). | Open research question |

"Closed" in the documents means impractical under the stated assumptions, not proven impossible.

---

## 3. Vision: the card (long-term research proposal)

A bank-card-sized device that places a near-human-size true hologram (full wavefront, natural focus, side views) in the room. Visible to everyone without a headset, touchable with a finger, and nothing sprayed into the air (no fog, mist or particles).

| Phase | What | Status |
| --- | --- | --- |
| 0 | AETHER Window software | Working demo (this repo) |
| 1 | Window-scale true hologram card (laser + phase modulator + eye tracking) | Proposed, not built |
| 2 | Low-threshold air emission (light in free air without plasma) | Research question, no known mechanism |

Documents:

- [`proposal/hackathon_ready/AETHER_Hackathon_Proposal.md`](proposal/hackathon_ready/AETHER_Hackathon_Proposal.md): hackathon proposal
- [`proposal/hackathon_ready/AETHER_Demo_Script.md`](proposal/hackathon_ready/AETHER_Demo_Script.md): 3-minute demo script
- [`proposal/long_term/AETHER_Charter_v3.md`](proposal/long_term/AETHER_Charter_v3.md): long-term charter
- [`proposal/AETHER_Decision_Log.md`](proposal/AETHER_Decision_Log.md): every direction tried, its cost, and why it was kept or rejected
- [`references/AETHER_References.md`](references/AETHER_References.md): prior art, competitors (Looking Glass, Sony SRD, others) and sources

---

## Repository layout

```
aether-window/   Working demo (Node server + browser app, models and libraries vendored)
theory/          Physics record and Python simulations (results*.json, figs/)
proposal/        Hackathon proposal, demo script, long-term charter, decision log
references/      Prior art, competitor survey, source list
```

## Author

Ng Wei Bin, Malaysia. Indie entry, Meta Global AI Developer Hackathon 2026.
