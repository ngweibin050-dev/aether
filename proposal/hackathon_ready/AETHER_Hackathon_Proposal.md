# AETHER: A 3D Window on Any Laptop, and a Path Toward True Holography

**Meta AI Developer Hackathon proposal** · Indie developer · Push the Frontier
Ng Wei Bin, Malaysia · 2026-10-26 (revision 2)

---

## 1. Summary

**What we are building at this hackathon.** AETHER Window is experimental spatial-computing software. It turns an ordinary laptop with a webcam into a head-tracked, hand-controlled 3D window. You move your head and the object stays fixed in space behind the glass. You pinch to grab and rotate it, and you speak to it. During the hackathon we connect Meta's models as the brain (Llama through the Meta Model API) and as the eyes (SAM, to turn real objects into 3D). The software costs nothing to run and needs no extra hardware.

**Why it exists.** AETHER Window is the first, software-only step of a longer project. That project's long-term goal is a bank-card-sized device that shows a **true hologram**: a reconstructed light wave your eyes can focus on and walk around, with nothing worn and nothing sprayed into the air. We have spent the project's first days deriving what physics allows for such a device and writing every step down.

**What we are and are not claiming.**

| Part | Status today |
| --- | --- |
| AETHER Window software (tracking, hands, scenes, two viewers, Window Law visualiser, bilingual UI) | **Built.** Code in `aether-window/`, runs on Windows with `start.bat`. |
| Meta model integration (Llama, SAM) | **Not yet connected.** The adapter is in place; we connect and demonstrate it during the event. |
| Physics analysis (constraints H1 and H3, superoscillation estimate, air-emission screening) | **Candidate results.** Derived and simulated by us with reproducible scripts, not yet reviewed by an independent expert. |
| Card-sized true-hologram hardware | **Proposal only.** No optical prototype exists. |

**Important distinction.** AETHER Window produces a depth illusion by rendering a separate perspective for the tracked eyes. It is not a hologram, and we say so on stage. The hologram is the long-term research goal.

## 2. What we build during the hackathon

AETHER Window needs nothing but a laptop and its webcam. It tests the interaction model a future holographic card would use, and it teaches the physics behind that card.

| Feature | Description | Status |
| --- | --- | --- |
| **Screen becomes a window** | The webcam tracks the face and irises and estimates the 3D position of the eyes. Off-axis (generalised perspective) projection makes objects float up to ~4 cm in front of the glass and stay fixed in space as you move. | Built; runs on the author's Windows PC |
| **Hands** | Pinch to grab and rotate, move two hands apart to explode a model, point to highlight. Mouse mode (M) is the fallback. | Built; runs on the author's PC; feel is being tuned |
| **Window Law visualiser** | Press W: a card-sized window appears on screen with live numbers and a top-down view of the light cone. Move your head and the object vanishes when your line of sight leaves the card, illustrating constraint H1. | Built (key W); live test pending |
| **Two viewers** | Press T: the screen splits into two windows, each rendered for one tracked person's eyes. | Built (key T); live test pending |
| **Real objects into 3D** | Press P: an object held up to the camera is segmented from the hand and turned into an approximate 3D model inside the window. | Built with a local segmenter (key P); SAM integration planned for the event |
| **Voice and AI** | Speech such as "take the engine apart" or "what does the piston do?" becomes structured scene actions and short spoken explanations. | Action layer and offline keyword parser built; Llama connection planned for the event |
| **English / Chinese** | Press L to switch the UI, speech recognition and voice. | Built |

"Built" means the code is present and was tested in a browser (with a simulated camera where noted). "Live test pending" means it has not yet been tried with real users on the author's machine. The recorded demo will show every feature live.

**Demo scenes:** engine, solar system, DNA.

**Technical stack:** Three.js, MediaPipe Face and Hand Landmarker, One-Euro filtering, a local Node server with zero install on Windows, and a structured action layer between the language model and the 3D scene (JSON actions with an offline fallback).

**Known limits:** single-webcam hand tracking is sensitive to lighting; iris-based depth accuracy has not been measured on real users; the depth effect works for the tracked viewers only.

## 3. How Meta's models will be used

None of these is connected yet. We will update this section with what actually works by the end of the event.

| Model | Role | Status |
| --- | --- | --- |
| **Llama via the Meta Model API** | Scene brain: turns free speech into a fixed action schema (explode, rotate, highlight part, switch scene, explain) and writes short explanations grounded in the scene's part list. | Adapter ready; API access pending; to be connected during the event |
| **SAM 3D Objects / SAM 3.1** | Turns a real object from the webcam into a segmented 3D asset for the window. | Planned; local segmenter used today |
| **Llama as physics tutor** | In Window Law mode, answers "why did it disappear?" from the visualiser's live numbers. | Planned; depends on Llama connection |

**Minimum we commit to:** at least one Meta model connected and shown in a real, useful interaction in the recorded demo.

## 4. Three-minute demo

1. Move your head: the engine stays fixed in space behind the "window".
2. Say "take it apart", then pinch and rotate a piston (Llama, once connected).
3. Hold up a real object: it becomes a 3D model in the window (SAM, once connected).
4. Press W: "A true hologram from a small device also behaves like a window. Here is our analysis of why, and what would have to change."

## 5. Research direction: what physics allows for a holographic card

This section explains the research behind the long-term goal. The full derivations, assumptions, simulations and every rejected idea are in `theory/AETHER_Physics_Record.md`, and the decisions are in `proposal/AETHER_Decision_Log.md`.

**How to read these results.** We derived them from three starting assumptions: light obeys the linear wave equation in air, the eye senses only the wave that enters its pupil, and energy is conserved. They are **candidate constraints**. The arithmetic is reproducible, but whether the models capture all the relevant physics still needs review by someone experienced in Fourier optics and computational holography. They could be wrong if an assumption fails.

| Candidate result | What it says | Key assumptions | Numbers (from our scripts) |
| --- | --- | --- | --- |
| **H1 Window constraint** | This is an application of the known Kirchhoff–Helmholtz integral, not a new law. If all light in the room comes from the device, you see a reconstructed point P only if the line from your eye through P continues on and hits the device's aperture. The hologram behaves like a window. | Linear, passive air; all light originates at the aperture; no scattering medium at P. | A card at 40 cm spans 12.2° × 7.7°. A 3.7 µm phase chip steers ±4.1°; 0.5 µm pixels would give ±32°. Card capacity ≈ 6.6 × 10¹⁰ pixels. |
| **Superoscillation estimate** | A band-limited wave can locally imitate a direction it does not contain. We estimated the cost of using this to escape H1. | Standard superoscillation energy scaling applied over a 4 mm pupil. | About 2,260 extra phase cycles; energy fraction about e⁻²⁰⁰⁰. Looks impractical under these assumptions. |
| **H3 Scattering-focus bound** | If the laser is shaped so that light scattered by the walls converges in mid-room, focusing efficiency is at most N / N_total (controlled modes over wall modes). | Random diffuse walls; wavefront-shaping theory; mode count estimated from wall area and wavelength. | 60 m² of wall gives N_total ≈ 8.5 × 10¹⁴; efficiency about 0.008 % even at the card's limit; a human-size image would need kilowatts. Looks impractical under these assumptions. |
| **Air-emission screening** | H1 and H3 assume passive linear optics. The remaining option is for the air at P to emit new light. | Rough cross-sections and lifetimes, some quoted from memory and flagged for checking. | A human-size image needs ~113 lm, about one photon per surface molecule every ~18 h. A two-photon estimate is four to five orders of magnitude below the plasma threshold (10¹³–10¹⁴ W/cm²). |

**What the screening suggests (a hypothesis, not a demonstrated route).** If the estimates hold, the bottleneck is not the number of air molecules or the total light. It is finding a molecular pathway that weak light can drive, that emits visible light, and that is eye-safe. The most interesting lead is the N₂ first-positive band (the red of the aurora), which near-infrared light might recycle. Energy requirements, excitation pathway, emission rates and safety all need expert review and experiments.

> **Research question:** can a chosen point in air be made to emit visible light (400–700 nm) at a peak intensity of at most 10⁸–10⁹ W/cm², eye-safe, using no more than 100 W for a human-size image?

**Reproducibility.** Every number above comes from `theory/simulations/aether_holography_v3.py` (results in `results_v3.json`, figures in `figs/v3_*.png`). Running `python aether_holography_v3.py` regenerates them. Our next step is to write H1 as a precisely stated theorem with its assumptions, and to check H3 against the wavefront-shaping literature before calling it new.

## 6. Long-term goal

### 6.1 The vision

A bank-card-sized device (85.6 × 54 mm) that shows a true hologram. Everyone in the room can see it without a headset, anyone can touch it with a finger, and nothing is sprayed into the air.

A true hologram rebuilds the object's light wave through interference and diffraction, so your eyes **focus** on it as on a real object, moving your head reveals its **sides**, and no glasses are needed.

### 6.2 What is sold as "holograms" today

| Name | How it works | Limitation |
| --- | --- | --- |
| Pepper's ghost, holo film | Angled glass or film reflects a screen | Flat image; needs glass |
| Light-field screens (Looking Glass, Sony) | Microlenses send different images in different directions | Eyes cannot truly focus; the image stays near the screen |
| Fog screens, mist columns | Projection onto water mist | Puts matter into the air |
| Spinning mirrors or screens | A fast-rotating surface sweeps out a volume | Large mechanical rig |
| Laser plasma | Intense pulses ionise air into dots of light | Noise, ozone, eye hazard, high cost |

### 6.3 Requirements

| Requirement | Target |
| --- | --- |
| Size | Bank card, 85.6 × 54 mm |
| Image | True hologram, eventually near human size |
| Viewing | Everyone in the room, nothing worn |
| Air | Nothing sprayed: no fog, particles or dye |
| Interaction | Touch the image with a finger |
| Cost | Consumer level |

### 6.4 Roadmap

| Phase | Name | What | Time (est.) | Gate |
| --- | --- | --- | --- | --- |
| 0 | AETHER Window | Software: head-tracked 3D window, gestures, AI voice, any laptop | Now–3 months | Reliable tracking on real users; Meta models connected |
| 1a | Holography dev kit | Desktop true hologram: off-the-shelf phase chip + lasers + eye tracking | 6–12 months | A floating image the eyes can focus on |
| 1b | AETHER Holo Card | Bank-card-size, window-scale true hologram | 18–36 months | Thickness, power, cost |
| 2 | Air-emission research | Computational screening → university lab partners | In parallel, 2–10 years | Emission threshold lowered by ≥ 10⁴× |
| 3 | Room-scale AETHER | Starts only if Phase 2 succeeds | — | — |

**Phase 1 in one paragraph.** The card would hold tiny RGB lasers and a phase-modulator chip that displays a computed hologram, rebuilding the object's light wave in front of the card. An eye-tracking camera finds the viewer's pupils and steers the viewing window onto them every frame (the approach SeeReal has published), which cuts the pixels needed by orders of magnitude. The image would float above the card within the window constraint. Estimated bill of materials at volume: US$170–365; estimated retail: US$499–899. These are estimates pending supplier quotes.

## 7. After the hackathon

| When | Milestone |
| --- | --- |
| Month 0–1 | AETHER Window finished with at least one Meta model; clean recorded demo |
| Month 3 | H1 written as a formal theorem; H3 checked against the literature; air-emission screening report |
| Month 6 | Dev kit shows its first focusable floating image (needs funding) |
| Month 12 | Dev kit with eye tracking and finger interaction; H3 bench test (30 cm white box, US$2–5k) |
| Month 18–36 | Holo Card prototype |

**First funding target:** about US$110–270k for the dev kit and a research partnership.

**Business model:** Phase 0 software licences for education, museums and retail, plus a developer SDK; Phase 1a dev kits for labs and studios; Phase 1b the consumer Holo Card; Phase 2 patents and licensing if the research succeeds.

## 8. Honesty and risks

- **AETHER Window is a per-eye rendering illusion, not a hologram.** We say so on stage.
- **Meta models are not yet connected.** We claim only what we demonstrate by the end of the event.
- **The physics results are candidate constraints**, derived by us and not yet independently reviewed. They may change.
- **A room-scale hologram would need a mechanism nobody has demonstrated.** We state the research question; we do not claim to have the answer.
- **No optical hardware exists.** Phase 1 specifications and costs are estimates.
- Single-webcam hand tracking is sensitive to lighting; mouse mode is the fallback.
- Iris-based depth accuracy has not yet been measured on real users.
- Literature figures quoted from memory are flagged in the theory record and will be checked against the original papers.

## 9. Builder

**Ng Wei Bin**, independent developer, Malaysia. Previous AI project: [BizPilot](https://github.com/ngweibin050-dev/BizPilot), an operations co-pilot for Malaysian SMEs with 39 tools, approval levels and automation.

**Will recruit:** an optical engineer (holography and lasers), a computational holography engineer, and a university physics adviser (ultrafast lasers and molecular spectroscopy) to review the candidate results.

## Appendix: files

| Folder | File | Contents |
| --- | --- | --- |
| aether-window | start.bat, README.md | The runnable demo |
| proposal/hackathon_ready | AETHER_Hackathon_Proposal.md | This document |
| proposal/hackathon_ready | AETHER_报名表.md, AETHER_Demo_Script.md | Form answers and demo recording script |
| proposal | AETHER_Decision_Log.md | Our thought process: every discussion, cost and rejected direction, with reasons |
| proposal/long_term | AETHER_Charter_v3.md (English) / AETHER_总纲_v3.html (Chinese) | Full long-term charter |
| theory | AETHER_Physics_Record.md | Every physics study in the project, in order, with evidence labels |
| theory/simulations | 5 Python scripts, results JSON, 19 figures | Reproducible simulations behind every number |
| references | AETHER_References.md | Every competitor, paper and tool we studied, with links |
