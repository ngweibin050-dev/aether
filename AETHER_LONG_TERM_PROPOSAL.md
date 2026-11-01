# AETHER Lab — Long-Term Hardware Proposal

**Author:** Ng Wei Bin  
**Project:** AETHER Lab (Meta AI Builders Hackathon 2026)  
**Status:** Long-term vision document. The software half (Stage 0) is complete. All hardware stages are future work.
**Prerequisite:** Long-term vision needs investment or funds to plan and execute  
**Note on honesty:** Every number in this document traces to one of the theory notes listed in the References section. Where a value is not yet experimentally verified, it is labelled **(assumed)** or **(simulated)**. Nothing has been invented.

---

## Table of Contents

1. [The Vision](#the-vision)
2. [The AETHER Desk Hardware](#the-aether-desk-hardware)
3. [The AETHER Card Hardware](#the-aether-card-hardware)
4. [What AETHER Lab (the Hackathon Product) Proves Today](#what-aether-lab-the-hackathon-product-proves-today)
5. [Staged Roadmap](#staged-roadmap)
6. [Open Problems and Honest Limits](#open-problems-and-honest-limits)
7. [References](#references)

---

## The Vision

A designer who builds a machine in CAD sees it on a flat screen. Depth is inferred from shading and rotation; the eyes
always focus on the glass. Headsets give stereo depth but put a device on the face, and stereo screens still make the
eye focus on the panel while the two eyes converge somewhere else.

AETHER's goal is a **workbench that shows a true hologram**: the full light wavefront of the object, so the eye
focuses at the object's real depth and each eye sees its own side, with the object standing on or just above the
desk where hands can reach it. Nothing is worn and nothing is released into the air.

AETHER is a two-part system. The software half **AETHER Lab** — converting a hand-drawn sketch into a layered 3D assembly using Meta's Muse Spark and Muse Wonder models — was built during the hackathon and runs today. The hardware half, described in this document, is the long-term target: the **AETHER Desk**, a flat holographic panel embedded in a workbench surface, and the **AETHER Card**, a bank-card-sized personal holographic window. On the desk, an engineer or designer reaches directly into a floating 3D image with bare hands — no headset, no glasses, no markers. The card fits in a wallet and turns any flat surface into a personal holographic window tethered to a phone or laptop. Both devices are built around the same core technology: a phase liquid-crystal panel that reconstructs a true hologram — one that delivers the correct focus cue to each eye, not a depth-faked stereo image. AETHER Lab, the software already running, is the front end: it takes a sketch, builds the 3D scene, and streams it frame-by-frame to whichever display is present.

---

## The AETHER Desk Hardware

### Panel

The AETHER Desk uses a **27-inch phase liquid-crystal (LC) panel** lying flat inside a desk surface, oriented so the image floats above the work area. The panel measures approximately **59.8 × 33.6 cm** (roughly the area of a large monitor laid flat). It carries roughly **30 million pixels** at a **45 µm pixel pitch** — approximately 7,500 rows by 4,000 columns.

The panel operates in **1D holography** mode: the vertical axis is fully coherent (each column encodes a holographic strip), while the horizontal axis remains incoherent (columns are displayed independently). This is a deliberate engineering trade-off. Full 2D holography at desk scale is feasible in principle but imposes severe compute demands that affordable silicon cannot yet meet. 1D holography reduces per-frame computation to a manageable level while preserving the focus cue in the most important axis.

The panel requires **heated liquid crystal** to reach approximately **555 fps** — the frame rate needed for the speckle-suppression scheme described below. Heating is achieved by a thin resistive layer behind the panel; power budget for this is included in the desk's mains supply and is not a constraint.

**Light source:** The light source must be spatially and spectrally coherent enough for holographic reconstruction, but does not need to be a laser. A **micro-LED** source is viable if its spectral bandwidth is kept at or below **56 nm** and its angular subtense at or below **0.27 mrad**. This avoids the speckle and safety concerns of laser illumination.

### Sharp Zone and Window Law

The usable holographic volume above the desk is bounded by two constraints:

**Window law:** The cross-section of the image that can be seen simultaneously shrinks as the image rises above the panel. At the panel surface the usable cross-section is the full panel (60 × 34 cm). At 10 cm above the surface it has shrunk to approximately 51 × 29 cm (for a viewer 70 cm away). Objects must be kept inside this shrinking window or they are clipped.

**Sharp zone:** With 1D holography at a 70 cm viewing distance, sharpness stays at or above 80% of the ideal 2D hologram figure within a depth range of **−108 mm to +87 mm** around the panel surface. Objects placed within this range are sharp; objects outside it blur progressively. At 70 cm viewing distance the focus error at the edge of the sharp zone is approximately **0.075 D** — well within the eye's tolerance **(simulated; no published human-eye measurement exists for 1D holograms at this distance; see Open Problems)**.

### Eye Tracking

A camera mounted above or around the desk tracks the viewer's pupil. The system requires:

- **Tracking error below 3 mm.** Standard cameras are 10 to 100 times more accurate than this, so the precision requirement is comfortably met with off-the-shelf hardware.
- **End-to-end latency of 10–30 ms.** A high-speed camera pipeline — capture, detect, transmit, update hologram — achieves approximately **4–6 ms**, leaving comfortable margin.

The desk variant supports **approximately 5 simultaneous viewers** with 4 rows of stitched panels, or **approximately 8 viewers** with 6 rows **(assumed; multi-viewer geometry has not been built or tested)**. Each viewer requires independent eye tracking and an independent sub-hologram.

### Speckle Suppression

Holographic displays suffer from speckle — a grainy interference pattern caused by coherent light scattering from a rough retina. The single-frame speckle contrast for a 4 mm pupil is approximately **C ≈ 0.30** (30%), which is clearly visible and unacceptable.

Two approaches are rejected:

- **Spectral broadening:** Widening the light source's spectral bandwidth does not reduce speckle on a thin phase panel — it only blurs the image (Theorem S2 in the speckle notes). Rejected.
- **Smooth-phase holograms:** These suppress speckle but destroy the focus cue. At 0.5 D of defocus, sharpness stays at 91% instead of dropping to 13% — the eye cannot tell the object is out of focus. Rejected because it defeats the purpose of a holographic display.

The accepted approach is **sparse-point groups (k = 3):** each frame shows every 3rd point in the scene; the remaining groups appear in the next frames and cycle. Averaging over k = 3 frames reduces speckle contrast to approximately **2.7%**, which is below the human visibility threshold of **3.2–4.4%**, while preserving correct focus cues. This requires the LC panel to run at approximately **555 fps** (heated), which is why the desk uses heated LC. At k = 3, the desk supports **1–2 simultaneous viewers**. Scaling to more viewers requires faster modulators — a research problem acknowledged below.

### Compute

The per-frame computation for 1D holography is a set of **1D Fourier transforms**, one per column. Each sub-hologram is a **111-pixel strip** — small enough to be computed on a dedicated holography chip at real-time rates **(chip does not yet exist as a product; assumed achievable with custom silicon)**. The compute block also runs the speckle-group scheduler, the eye-tracking integration loop, and the phase quantisation step.

### Interaction

The natural interaction mode for the desk is: reach in from the front or sides of the panel. The system renders correct occlusion when a hand is **in front of** a holographic object (the hand blocks the light correctly). A hand placed **behind or inside** a holographic object creates a depth conflict — the physical hand and the virtual image occupy the same space, and the visual system perceives a contradiction. This cannot be resolved in software; it is a fundamental limit of the geometry (see Open Problems).

**Ultrasonic haptic feedback** is physically possible — a phased array of ultrasonic transducers above the desk can produce localised sound pressure nodes at the position of a virtual object, giving a sensation of touch. Nothing is released into the air; it is purely a pressure wave. This is listed as a potential addition, not a committed feature **(assumed compatible; not yet integrated or tested)**.

---

## The AETHER Card Hardware

### Form Factor and Power

The AETHER Card is a **bank-card-sized holographic display: 85.6 × 54 mm, 5 mm thick.** The 5 mm thickness is chosen specifically for battery capacity: a 5 mm card can carry approximately **4.4–6.6 Wh**, which covers all-day mixed use (estimated at **1.5–5.1 Wh** for the combination of display, compute, and eye tracking).

Total power during active viewing: approximately **0.2–1.0 W**, broken down as:
- Panel drive: 0.04–0.12 W
- Holography compute (dedicated chip): 0.05–0.5 W **(assumed; chip does not exist yet)**
- Eye tracker: 0.02–0.15 W

A 3 mm card (1.5–2.2 Wh) would cover light use cases but not all-day heavy use. The 5 mm form factor is the recommended target.

### Light Source

The card uses a **micro-LED** source — no laser required. With eye tracking, the display sends light only into the viewer's pupil at any given moment. This reduces the required optical power reaching the eye to approximately **0.24–1.2 µW** — far below any safety threshold and small enough that a micro-LED's limited brightness is not a constraint.

Coherence requirements are the same as the desk: spectral bandwidth ≤ 56 nm, angular subtense ≤ 0.27 mrad.

### 1D Holography and the 2-Sub-Pupil Solution

Full **2D holography is physically impossible on the card.** Compute alone would require **6–120 W**; the card can dissipate at most approximately **1.5 W**. The card therefore also uses **1D holography**.

At the card's typical viewing distance of **40 cm** (held in the hand), 1D holography without correction gives a focus error of **0.17 D** and sharpness of only **63%** of ideal — noticeably worse than the desk. The root cause is that the depth budget scales as Δz ≈ Δmax × d² (depth budget proportional to viewing distance squared), so a closer viewing distance compresses the usable depth range to approximately ±2–4 cm.

The solution is the **2-sub-pupil approach:** instead of illuminating the full pupil, the card projects light into two small sub-pupils inside the viewer's pupil. Each sub-pupil sees a slightly different holographic view. The result, as derived in the theory notes:

- Sharpness: **78% of ideal** (up from 63%)
- Focus error: **eliminated** (0 D)
- Required frame rate: **360 Hz**

This is a **theoretically derived result and has not been verified on a real human eye.** It is listed as an open problem below.

### Speckle — The Blocking Problem

Speckle is the most serious unsolved problem for the card. The card operates at room temperature (no heating feasible in a hand-held device), limiting the LC panel to approximately **350 fps**.

To suppress speckle to below the visibility threshold using the sparse-group method requires the panel to run at **1,620–3,240 fps** — roughly 5–10× faster than current room-temperature LC allows.

The card therefore needs a **card-sized ~1.5–3 kHz phase modulator.** Two candidate technologies exist in the literature:

- **MEMS phase mirrors:** 1.44 kHz demonstrated (arXiv:2409.01289). Current devices are fingernail-sized. Scaling to card size has not been demonstrated.
- **Ferroelectric liquid crystal:** 6.3 kHz reported. Also currently only fingernail-sized.

Without a fast modulator, the card's speckle contrast is approximately **24%** — clearly visible and unacceptable for a finished product. The card cannot ship without a breakthrough in modulator area scaling, or a different speckle-suppression approach not yet identified.

This is treated as a medium-term research dependency, not a project-stopper: the desk version does not have this constraint and can reach a shippable state first.

### Host Integration and OS Extension

The card is **a display and eye tracker only.** It does not run AETHER Lab locally. Instead:

- The card connects to a **host device** (laptop or smartphone) over a short-range wireless link **(protocol not yet specified; assumed low-latency, e.g. Wi-Fi 7 or UWB-based; unverified)**.
- The host runs AETHER Lab and streams hologram frames to the card in real time.
- Any 3D application that can export a scene (game engine, CAD tool, video call client) can stream to the card via an **AETHER compositor extension** — a system-level plugin that intercepts the scene graph and generates the hologram frames.

This architecture keeps the card physically thin and thermally cool while offloading all heavy computation to a device that is already plugged in or has a large battery.

**Video call use case:** The remote party's face is reconstructed in 3D using 4–8 cameras around their screen. The target depth error of less than 2 cm is unnoticeable in practice **(simulated; not yet measured on real 3D reconstruction hardware)**.

---

## What AETHER Lab (the Hackathon Product) Proves Today

AETHER Lab is the software pipeline built during the hackathon. It demonstrates:

| Capability | What was shown | Method |
|---|---|---|
| Drawing → 3D assembly | Sketch input processed by Muse Spark (segmentation) and Muse Wonder (3D generation) on Modal GPU infrastructure; multi-layer assembly produced | Live demo; measured end-to-end times |
| Recall / precision | Measured on test set; reported in hackathon submission | Automated evaluation |
| Eye-model desk score | Sharpness metric, Window Law compliance, speckle contrast computed for the desk geometry | **Simulated** — mathematical model, no real panel |
| Phase-only encoding quality | Pupil-GS algorithm stays within 0.5% of ideal complex modulation (Test 17) | Numerical simulation |

The software pipeline is the portion of the system that is complete, tested, and ready to be connected to hardware as hardware stages are built.

---

## Staged Roadmap

| Stage | Name | What it builds | Key question answered | Status |
|---|---|---|---|---|
| **0** | AETHER Lab (Software) | AI pipeline: sketch → 3D model (Muse Spark + Muse Wonder + Modal GPU) | Can software convert a 2D drawing to a plausible 3D assembly? | **Done** |
| **1** | Printed-Film Eye Test | Printed holographic film or static LC test cell; human subject views 1D hologram; autorefractor measures actual focus response | Do real human eyes accommodate (focus) correctly to a 1D hologram? | Not started |
| **2** | Desk 1 Prototype | Full desk: 27-inch phase LC panel (flat), eye tracking camera, heated LC at ~555 fps, holography compute board, AETHER Lab integration | Does the end-to-end system work at human viewing conditions? Is speckle acceptable? | Not started |
| **3** | Desk 2 (2D Research) | Full 2D hologram desk — requires a modulator that does not yet exist | Can a future modulator enable true 2D floating holograms? | Research only; no timeline |

The card version depends on Stage 1 (confirming human eye response) and on progress in card-sized fast modulator technology. It is not on a fixed timeline.

---

## Open Problems and Honest Limits

The following are known unsolved problems. They are listed here because a credible proposal must be honest about what is not yet solved.

### 1. Real-Eye Focus Response to 1D Holograms

**Status: No published human-eye measurement found.**

All sharpness and focus-error numbers in this document are derived from an optical model of the eye. The model predicts that a 1D hologram delivers a real focus cue. Whether a real human eye actually accommodates to that cue — measured with an autorefractor — is unknown. This is the first thing Stage 1 must test. If the eye does not accommodate, the fundamental premise of the display is unproven.

### 2. Card-Sized Fast Phase Modulator

**Status: Does not exist.**

Suppressing speckle on the card requires a phase modulator running at approximately 1.5–3 kHz over an area of 85.6 × 54 mm. MEMS phase mirrors at 1.44 kHz and ferroelectric LC at 6.3 kHz have been reported, but both are fingernail-sized. No card-scale device of this type has been published. Without this component, the card's speckle contrast is ~24%, which is visible and unacceptable.

### 3. Speckle on the Card Without a New Modulator

**Status: No mitigation path identified within current technology.**

The two rejected approaches (spectral broadening, smooth-phase holograms) do not help. The sparse-group method requires frame rates the card cannot achieve. A different approach — not yet identified — would be needed, or the card must wait for modulator technology to advance.

### 4. Holography Compute Chip

**Status: Chip does not exist as a product.**

The computation required for real-time 1D holography (approximately 200 FFTs per column per sub-frame, estimated ~20 seconds on a general-purpose CPU per frame) needs a dedicated silicon implementation. No commercial holography chip of this type exists. This is a custom ASIC design problem; feasibility is assumed but unverified.

### 5. 2-Sub-Pupil Focus Correction on the Card

**Status: Theoretically derived; not verified on a real human eye.**

The prediction that 2 sub-pupils eliminate focus error and raise sharpness to 78% is a mathematical result. It has not been confirmed by experiment. The Stage 1 film test should also probe this specific condition.

### 6. Patent Landscape

Two relevant patents must be acknowledged:

- **SeeReal Technologies US12298522B2** — Single-parallax hologram with eye tracking and pupil steering. Active until approximately 2038. The AETHER Desk's approach overlaps conceptually with this patent in its use of tracked-pupil hologram delivery. Legal review required before commercialisation.
- **Samsung Electronics US10416762B2** — Beam-steering backlight. Active until approximately 2036. Relevant if a beam-steering backlight is used in the card's illumination path. Legal review required.

These patents do not block research or hackathon demonstration but must be resolved before any product launch.

### 7. Depth Conflict with Hands

**Status: Cannot be resolved in software.**

When a user places their hand behind or inside a holographic object, the physical hand and the virtual image are at conflicting depths. The visual system perceives both simultaneously, creating an uncomfortable inconsistency. The display has no mechanism to make the virtual image occlude the physical hand. The interaction rule — work from the front and sides, pull objects toward the user — is a workaround, not a solution. A true solution would require real-time transparent display technology that can also occlude, which is a separate unsolved problem.

### 8. Multi-Viewer Speckle at the Desk

**Status: More than 2 viewers requires faster modulators.**

The sparse-group scheme at k = 3 and 555 fps supports 1–2 viewers. Supporting 5–8 viewers simultaneously would require either a faster LC panel (heated beyond current rates) or a different speckle scheme. No specific solution has been identified.

---

## References

### Internal Theory Notes (C:\Aether\theory\)

| File | Contents |
|---|---|
| `v8_card_battery.md` (or equivalent) | Card form factor analysis; battery sizing at 3 mm and 5 mm; micro-LED coherence requirements; power budget for 1D and 2D holography; desk vs. card LC frame rate |
| `v9_1d_focus.md` | 1D holography focus error and sharpness at desk (70 cm) and card (40 cm) distances; depth budget formula Δz ≈ Δmax × d²; 2-sub-pupil solution derivation |
| `v10_six_problems.md` | Eye tracking latency and precision analysis; hand-tremor and head-motion compensation; multi-viewer geometry; 3D video-call capture |
| `v11_speckle.md` | Single-frame speckle contrast derivation (C ≈ 0.67 × λ / (D × θ) ≈ 0.30 for 4 mm pupil); rejection of spectral broadening and smooth-phase holograms; sparse-group k=3 result; card frame-rate requirement; MEMS and ferroelectric LC survey |
| `v13_desk_geometry.md` | 27-inch panel geometry; window law; sharp zone (−108 to +87 mm); pixel count and pitch; hand interaction rules |

### External Literature

| Reference | Relevance |
|---|---|
| Verschaffelt et al. (2015) | Speckle in holographic displays; foundation for contrast analysis |
| Wang et al. (2024) | Phase-only hologram encoding quality; basis for pupil-GS algorithm evaluation |
| Takaki (2014) | 1D (horizontal-parallax-only) holographic display; precursor geometry for the desk design |
| arXiv:2409.01289 | MEMS phase mirror at 1.44 kHz; cited as evidence that kHz-rate phase modulation exists at small scale |
| SeeReal Technologies US12298522B2 | Patent: single-parallax hologram with pupil tracking |
| Samsung Electronics US10416762B2 | Patent: beam-steering backlight |

---

*This document was written as part of the Meta AI Builders Hackathon 2026 submission for AETHER Lab. All hardware stages described beyond Stage 0 are future work. No hardware prototype exists as of the submission date.*

