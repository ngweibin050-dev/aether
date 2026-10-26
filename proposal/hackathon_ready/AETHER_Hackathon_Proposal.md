# AETHER: True Holography, From First Principles

**Meta AI Developer Hackathon proposal** · Indie developer · Push the Frontier
Ng Wei Bin, Malaysia · 2026-10-25

---

## 1. Summary

**What AETHER is.** AETHER's long-term goal is a bank-card-sized device (85.6 × 54 mm) that places a near-human-size **true hologram** in the room. Everyone can see it without a headset, anyone can touch it with a finger, and nothing is sprayed into the air. It is the Iron Man scene, done honestly.

**Why nobody has built it.** Most products sold as "holograms" are reflections, light-field screens or fog. We started from the wave equation and proved one key fact: **with optics alone, a true hologram always behaves like a window** (Window Law H1). We then tried two workarounds and calculated both down to concrete numbers. Both are closed. That leaves one door open: **make the air at the image point emit light by itself.** Today this needs plasma-level intensity (about 10¹³ W/cm²). Our screening shows that neither the number of air molecules nor the total amount of light is the bottleneck. The bottleneck is a molecular pathway that nobody has found yet.

**Strategy: two tracks.**

| Track | What | Time | Risk |
| --- | --- | --- | --- |
| **Product** (buildable now) | Phase 0 AETHER Window software → Phase 1 window-scale true-hologram card | 0–36 months | Engineering; manageable |
| **Research** (the big prize) | Find a new mechanism that makes air glow locally under weak light | 2–10 years | High scientific risk, but success would create a new product category |

**What we build at this hackathon.** AETHER Window, the Phase 0 software. It turns any laptop with a webcam into a head-tracked 3D window that you control with your hands and voice. Meta's models are the brain, and an interactive explanation of the physics sits on top. It costs nothing to run.

**What already exists:**

- A first-principles physics theory: Window Law H1, Scattering-Focus Law H3, a superoscillation analysis and an air-emission screening.
- A working AETHER Window prototype on Windows (double-click `start.bat`).
- A full technology and competitor survey.
- A written record of every direction we explored and why we kept or dropped it (see `theory/` and `references/`).

## 2. The problem

### 2.1 What "true holography" means

A true hologram rebuilds the entire light wave of an object through interference and diffraction. As a result:

1. your eyes **focus** on it as they would on a real object;
2. moving your head reveals its **sides**;
3. no glasses are needed.

### 2.2 What is sold as "holograms" today

| Name | How it works | Problem |
| --- | --- | --- |
| Pepper's ghost, holo film | Angled glass or film reflects a screen | Flat image; needs glass |
| Light-field screens (Looking Glass, Sony) | Microlenses send different images in different directions | Simulated 3D; eyes cannot truly focus; the image stays inside the screen |
| Fog screens, mist columns | Projection onto water mist | Puts matter into the air |
| Spinning mirrors or screens | A fast-rotating surface sweeps out a volume | Large mechanical rig |
| Laser plasma | Intense pulses ionise air into dots of light | Noise, ozone, eye hazard, high cost |

### 2.3 AETHER's hard requirements

| Requirement | Target |
| --- | --- |
| Size | Bank card, 85.6 × 54 mm |
| Image | True hologram, eventually near human size |
| Viewing | Everyone in the room, nothing worn |
| Air | Nothing sprayed: no fog, particles or dye |
| Interaction | Touch the image with a finger |
| Cost | Consumer level |

## 3. What we derived from first principles

We started from only three facts: light obeys the linear wave equation in air, the eye senses only the wave that enters its pupil, and energy is conserved. The full derivations, simulations and the earlier studies that led here are in `theory/AETHER_Physics_Record.md`; the decisions and rejected directions are in `proposal/AETHER_Decision_Log.md`.

| Result | What it says | Numbers |
| --- | --- | --- |
| **H1 Window Law** | By the Kirchhoff–Helmholtz integral, all light in the room comes from the device. You see image point P only if the line from your eye through P continues on and hits the card. A true hologram is a window. | A card at 40 cm spans 12.2° × 7.7°. A 3.7 µm phase chip steers light ±4.1°; 0.5 µm pixels would give ±32°. The card can hold at most about 6.6 × 10¹⁰ pixels. |
| **Workaround 1: superoscillation** | A band-limited wave can locally imitate a direction it does not contain, so light could appear to come from outside the window. | About 2,260 extra phase cycles across a 4 mm pupil; energy cost about e⁻²⁰⁰⁰. **Closed.** |
| **Workaround 2: the room as the hologram (H3)** | Shape the laser so that light scattered by the walls converges in mid-room. Geometrically this beats H1. We derived that the focusing efficiency is at most N / N_total. | 60 m² of wall gives N_total ≈ 8.5 × 10¹⁴. Even at the card's theoretical limit, efficiency is about 0.008 %, so a human-size image needs kilowatts of laser power. **Closed.** |
| **The one open door** | H1 and H3 hold for every linear, passive medium. The only exit is for the air at P to create new light. | Today: 10¹³–10¹⁴ W/cm² (plasma). |

**What our screening found.** A human-size image needs about 113 lumens. That means each air molecule on the image surface only has to emit a photon once every ~18 hours. A two-photon estimate puts the required peak intensity four to five orders of magnitude below the plasma threshold. **Molecule count and intensity are not the bottleneck.** The missing piece is an energy pathway in nitrogen or oxygen that weak light can excite and that emits visible light. The best lead is the red glow of the aurora (the N₂ first-positive band): near-infrared light can recycle it, so one molecule can emit many times.

> **Discovery target:** make a chosen point in air emit visible light (400–700 nm) at a peak intensity of at most 10⁸–10⁹ W/cm², eye-safe, using no more than 100 W in total for a human-size image.

We believe H3 is a new result in its own right and could be published once a literature check confirms it.

## 4. Roadmap

| Phase | Name | What | Time (est.) | Gate |
| --- | --- | --- | --- | --- |
| 0 | AETHER Window | Software: head-tracked 3D window, gestures, AI voice, any laptop | Now–3 months | Tracking accuracy on real users |
| 1a | Holography dev kit | Desktop true hologram: off-the-shelf phase chip + lasers + eye tracking | 6–12 months | A floating image the eyes can focus on |
| 1b | AETHER Holo Card | Bank-card-size, window-scale true hologram | 18–36 months | Thickness, power, cost |
| 2 | Air-emission research | Computational screening → university lab partners | In parallel, 2–10 years | Emission threshold lowered by ≥ 10⁴× |
| 3 | Room-scale AETHER | Starts only if Phase 2 succeeds | — | — |

**Phase 1 in one paragraph.** The card holds tiny RGB lasers and a phase-modulator chip that displays a computed hologram, rebuilding the object's light wave in the air in front of the card. An eye-tracking camera finds the viewer's pupils and steers the viewing window onto them every frame (the SeeReal approach), which cuts the number of pixels needed by orders of magnitude. The result is a true hologram that floats above the card and can be touched, seen through the card as H1 requires. Estimated bill of materials at volume: US$170–365; estimated retail price: US$499–899.

## 5. What we build during the hackathon

AETHER Window needs nothing but a laptop and its webcam. It validates the interaction model that the Holo Card will use, and it teaches the physics.

| Feature | Description | Status |
| --- | --- | --- |
| **Screen becomes a window** | The webcam tracks the irises and estimates the 3D position of the eyes. Off-axis (generalised perspective) projection makes objects float up to ~4 cm in front of the glass and stay fixed in space as you move. | Working |
| **Hands** | Pinch to grab and rotate, move two hands apart to explode a model, point to highlight. Mouse mode (M) is the fallback. | Working |
| **Window Law visualiser** | Press W: a card-sized window appears on screen with live numbers and a top-down view of the light cone. Move your head and the object vanishes exactly when your line of sight leaves the card, so judges *see* H1. | Working |
| **Voice and AI on Meta models** | Speech such as "take the engine apart" or "what does the piston do?" becomes structured scene actions and spoken explanations through the Meta Model API (Llama). | Model adapter ready (one config line); on-device keyword fallback works today; Llama connected during the event |
| **Real objects into 3D** | Press P: an object held up to the camera is recognised, separated from the hand and turned into a 3D model inside the window. | Pipeline working with local cut-out; SAM 3D / SAM 3.1 plugs into the server during the event |
| **Two viewers** | Press T: the screen splits into two windows, each rendered for one tracked person's eyes. | Working |
| **English / Chinese** | Press L to switch the UI, speech recognition and voice. | Working |

**Demo scenes:** engine, solar system, DNA.

**Technical stack:** Three.js, MediaPipe Face and Hand Landmarker, One-Euro filtering, a local Node server with zero install on Windows, and a structured action layer between the language model and the 3D scene (JSON actions with an offline fallback).

## 6. How Meta's models are used

1. **Llama via the Meta Model API** is the scene brain. It turns free speech into a fixed action schema (explode, rotate, highlight part, switch scene, explain) and writes short spoken explanations grounded in the scene's part list.
2. **SAM 3D Objects / SAM 3.1** turn real objects from the webcam into segmented 3D assets for the window.
3. **Physics tutor.** In Window Law mode, Llama answers "why did it disappear?" using the live numbers from the visualiser, so the demo explains itself.

## 7. Three-minute demo

1. Move your head: the engine stays fixed in space behind the "window".
2. Say "take it apart", then pinch and rotate a piston.
3. Hold up a real object: Meta's SAM turns it into a 3D model.
4. Press W: "Every hologram is a window. Here is why, and here is the one experiment that could change it."

## 8. After the hackathon

| When | Milestone |
| --- | --- |
| Month 0–1 | AETHER Window finished with Meta models at the hackathon |
| Month 3 | Air-emission screening report; H3 paper draft |
| Month 6 | Dev kit shows its first focusable floating image |
| Month 12 | Dev kit with eye tracking and finger interaction; H3 bench test (30 cm white box, US$2–5k) |
| Month 18–36 | Holo Card prototype |

**First funding target:** about US$110–270k for the dev kit plus the research partnership. Within 12 months this delivers a desktop true-hologram demo, the H3 paper and the air-emission screening report.

**Business model:** Phase 0 software licences for education, museums and retail, plus a developer SDK; Phase 1a dev kits for labs and studios; Phase 1b the consumer Holo Card; Phase 2 patents and licensing.

## 9. Honesty and risks

- **A room-scale hologram is not possible with known physics.** We state exactly which discovery it needs, and we do not claim to have it.
- **Phase 0 is a visual effect produced by per-eye rendering, not a true hologram.** We say so on stage. Phase 1 is true holography, limited by the Window Law.
- Hand tracking from a single webcam is sensitive to lighting; mouse mode is the fallback for live demos.
- Iris-based depth accuracy has not yet been measured on real users.
- Literature figures quoted from memory are flagged in the theory record and will be checked against the original papers.
- Phase 1 costs and specifications are estimates pending supplier quotes.

## 10. Builder

**Ng Wei Bin**, independent developer, Malaysia. Previous AI project: [BizPilot](https://github.com/ngweibin050-dev/BizPilot), an operations co-pilot for Malaysian SMEs with 39 tools, approval levels and automation.

**Will recruit:** an optical engineer (holography and lasers), a computational holography engineer, and a university physics adviser (ultrafast lasers and molecular spectroscopy).

## Appendix: files

| Folder | File | Contents |
| --- | --- | --- |
| proposal/hackathon_ready | AETHER_Hackathon_Proposal.md / .html | This document |
| proposal/hackathon_ready | AETHER_报名表.md | Ready-to-paste form answers |
| proposal/hackathon_ready | AETHER_Demo_Script.md | Three-minute demo recording script |
| proposal | AETHER_Decision_Log.md | Our thought process: every discussion, cost and rejected direction, with reasons |
| proposal/long_term | AETHER_Charter_v3.md (English) / AETHER_总纲_v3.html (Chinese) | Full long-term charter |
| theory | AETHER_Physics_Record.md | Every physics study in the project, in order: derivations, theorems, numbers |
| theory/simulations | 5 Python scripts, results JSON, 19 figures | Reproducible simulations behind every number |
| theory | AETHER_物理理论_v3.html | Current theory (Chinese) |
| references | AETHER_References.md | Every competitor, paper and tool we studied, with links |
| references | AETHER_前沿技术与竞品_v3.html, Looking Glass/Sony .docx | Earlier surveys (Chinese) |
| aether-window | start.bat | Runnable demo |
