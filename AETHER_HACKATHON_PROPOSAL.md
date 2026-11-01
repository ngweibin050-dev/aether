# AETHER Holography Roadmap: from a simulated desk to a holographic workbench

Ng Wei Bin · November 2026 · hackathon proposal

In this hackathon, **Nothing optical has been built.** Every optical number below is a derivation or a simulation,
from the research notes in `theory/` or from the AETHER Lab engine (`aether-lab/engine/`). Values that were assumed
or recalled rather than checked are labelled *assumed*. Where a note and the engine disagree, the engine's number is
used and the disagreement is stated.

Sources are cited inline as file names. The theory notes v4–v13 and the two notes of 30 Oct were written during the
hackathon (27 Oct – 1 Nov 2026) as research, not product code; `theory/AETHER_Physics_Record.md` are pre-event background (23–26 Oct).

---

## 1. Problem Statement

**Bridging the Gap Between 2D Mechanical Drawings and 3D Understanding**

Mechanical knowledge is often trapped in two-dimensional drawings. Understanding how a machine is constructed from these drawings can be challenging, particularly when dealing with century-old patents, incomplete documentation, single-view illustrations, or assemblies with hidden components.

A conventional reconstruction workflow requires engineers to manually interpret the drawing, identify individual components, estimate missing dimensions and depths, construct each part, and determine how the components fit together. This process is time-consuming, requires specialist experience, and leaves room for interpretation errors.

**The challenge becomes even greater when:**
- Information is missing: Old drawings may contain no scale, incomplete dimensions, or insufficient views.
- Components are hidden: Shafts, bearings, internal structures, and connections may not be visible.
- Spatial relationships are unclear: A flat drawing does not immediately communicate depth, alignment, or assembly relationships.
- Understanding takes time: Engineers and students must mentally reconstruct the machine before they can meaningfully inspect or explain it.

The result is a significant gap between what a drawing shows and what a person needs to understand.


## 2. Target User
**Primary users**
- Mechanical engineers: For preliminary reconstruction and understanding of legacy mechanical designs.
- Engineering students and educators: For visualising mechanical assemblies and learning how individual components interact.

**Secondary users**
- Product and industrial designers: For exploring mechanical concepts from sketches and technical illustrations.
- Maintenance and restoration technicians: For gaining an initial understanding of older machinery when original documentation is limited.
- Researchers and historians of engineering: For studying historical mechanisms and patent designs.

## 3. Our Solution - AETHER Lab

AETHER Lab is an AI-powered mechanical reconstruction and holographic simulation workbench. It transforms mechanical drawings into interactive 3D assemblies, helps users understand how the machine is constructed, and explores how those assemblies could be viewed through AETHER's future holographic display.

**A. AI-powered drawing interpretation**

AETHER Lab uses a coordinated pipeline of Meta AI models:
- Muse Spark: Interprets the mechanical drawing, identifies visible components, and generates a structured part description.
- Muse Wonder: Acts as an engineering completion model, inferring missing depth, thickness, hidden shafts, bearings, and possible component relationships. Inferred details are explicitly distinguished from information visible in the original drawing.
- SAM 3.1: Supports image segmentation for identifying and isolating components in photographs.
- Muse Voice Transcribe: Enables voice-based commands and interaction.
- Muse Image: Generates supporting conceptual illustrations to help users understand individual components. These illustrations are not treated as measured 3D geometry.

**B. Parametric 3D reconstruction**

AETHER's geometry engine converts the interpreted components into structured 3D geometry and assembles them into an interactive model.

Users can inspect individual components, rotate the assembly, explore internal structures through section cuts and exploded views, and examine how parts fit together.

The reconstructed model can also be exported in GLB and STL formats for further inspection and downstream workflows.

**C. Geometry and optical evaluation**

AETHER Lab does more than generate a 3D visualisation. It applies computational checks to examine the reconstructed geometry against the source drawing, including how well the generated parts correspond to the original drawing views.

Its wave-optics simulation engine then explores the viewing characteristics of the reconstructed assembly under different holographic display configurations.

Users can:
- Run a focus sweep to examine how different depths come into focus.
- Inspect simulated holographic output at different focal planes.
- Compare the simulated 1D AETHER Desk against a full 2D/3D hologram reference.
- Evaluate optical characteristics such as visibility, sharpness, viewing region, and speckle.

These optical results are computational simulations, not measurements from a physical holographic display (but helpful for [→ AETHER_LONG_TERM_PROPOSAL.md](AETHER_LONG_TERM_PROPOSAL.md))

D. Towards a new way of interacting with engineering

AETHER Lab brings together AI-assisted reconstruction, interactive 3D engineering, and computational holography in one workbench.

It is the first software stage of the broader AETHER vision: a future in which engineers can move beyond viewing mechanical designs on conventional flat displays and interact with spatially reconstructed objects through a holographic workbench.

## 4. Technical Results (measured IN THIS HACKATHON, will improve in the newer version)

All numbers below are from `aether-lab/docs/RESULTS.md` (live runs with Meta's
API and a Modal T4 GPU) or from the test suite (`python tests/test_physics.py`, 35 tests passing on 1 Nov).

| What | Measured |
|---|---|
| One-view patent drawing → 3D assembly (Muse Spark reads, Muse Wonder completes the unseen views) | demo D (press) 108.9–110.5 s, C (gearbox) 121.1–161.4 s per full run incl. explanation, two passes each |
| How well the build matches the drawing (recall / parts precision, replayed readings) | B 76.3 / 62.9 %, D 72.3 / 77.8 %, C (held out) 73.6 / 80.4 % |
| Three-view sheet → solid, view match on the delivered mesh | NASA X-3: 100.0 / 99.5 / 98.9 %; held-out NASA X-2 first run 92.6 / 65.8 / 95.1 % |
| Explanation grounded in the built model (every part id and number checked in code) | 6 steps, 0 rejected, 12–20 s on D and C |
| Eye-model desk score of every part (sharp zone, Window Law, speckle) | live on every build; e.g. D 108/108 parts ≥ 80 % sharp |
| Phase-only encoding for the desk (pupil-GS) | within 0.5 % of complex modulation (test 17) |

These prove the **software pipeline** and the **simulation**. They do not prove that a real panel or a real eye
behaves as simulated.

## 5. Real World Impact

AETHER Lab aims to deliver measurable benefits across engineering, education, and mechanical preservation.

### Expected Benefits
| Target users | Expected benefits | Proposed impact targets |
|---|---|---|
| Mechanical engineers | Automate initial drawing interpretation and 3D assembly reconstruction, reducing repetitive modelling work. | **Around 30% less time** to produce a preliminary, inspectable 3D assembly. |
| Engineering students | Improve understanding of mechanical components through interactive 3D models, exploded views, and AI-guided explanations. | **10 percentage points higher accuracy** in identifying components and understanding assembly relationships. |
| Designers | Quickly transform early mechanical sketches into 3D concepts for visual inspection and refinement. | **40% less time** spent on initial concept visualisation. |
| Maintenance and restoration technicians | Make legacy machinery easier to understand when original CAD files or complete documentation are unavailable. | Enable preliminary assembly understanding through interactive 3D models and AI-guided explanations. |
| Engineering researchers | Convert historical patent drawings into inspectable digital models. | Generate initial 3D assemblies in approximately 109–161 seconds in AETHER Lab's recorded demonstrations. |

These figures represent proposed performance targets rather than measured outcomes. They define the improvements AETHER Lab aims to achieve and will be evaluated through subsequent user testing.

### Preliminary User Evaluation

An exploratory pilot evaluation was conducted with Evan Lim, a Faculty of Engineering student, to assess AETHER Lab's effectiveness in mechanical drawing interpretation and understanding.

| Evaluation metric | Without AETHER Lab | With AETHER Lab |
|---|---:|---:|
| Task completion time | 35 minutes | 5 minutes |
| Correct answers | 7/10 (70%) | 9/10 (90%) |
| Confidence level | 3/5 | 4/5 |

**Key findings:**
- **85.7% reduction in task completion time**, from 35 minutes to 5 minutes.
- **20-percentage-point improvement in assessment score**, from 70% to 90%.
- **20% increase in confidence rating**, from 3/5 to 4/5.

**Participant feedback:**

The participant highlighted AETHER Lab's usefulness for rapid prototyping and mechanical drawing interpretation. In particular, two reconstruction approaches were identified:

- **Trace Mode:** Follows the original mechanical drawing more closely, but may not always produce mechanically logical interpretations.
- **Interpret Mode:** Focuses on understanding the intended mechanism and generating a conceptual assembly quickly, although the resulting geometry may require further refinement.

The participant also noted that reconstruction performance may vary depending on drawing quality and the completeness of the original information. Well-depicted drawings are generally easier to interpret than incomplete or ambiguous sketches.

**Conclusion:** This preliminary evaluation suggests that AETHER Lab can help users understand and reconstruct mechanical assemblies more efficiently. Further testing with additional participants and a wider range of mechanical drawings is necessary to validate these findings.

*Evaluation sample: 1 participant. Results represent an exploratory pilot and should not be generalised to all engineering users.*


## 6. Future Work - What is not built, only simulated, or assumed 

**Not built:** any holographic panel, backlight, eye tracker for the desk, or the printed film of section 6.
**Only simulated:** every sharpness, speckle, sharp-zone and phase-only number above, with a diffraction-limited eye
model (no ocular aberrations), a 1′ spatial average for speckle, and ideal tracking.
**Assumed or unverified** (from the notes' own lists):
- where a real eye actually focuses on a 1D hologram — no published measurement was found
  (`..._v9_1D_Focus_zh.md`, `..._v10_Remaining_Six_zh.md` §5); it needs a prototype and an autorefractor;
- the eye's integration time for fine speckle (1/60 s or 1/30 s), which sets the frame budget (`..._v11` §7, `..._v12` §7);
- texture masking of speckle on real surfaces; possible aliasing of the sparse point lattice (`..._v11` §7);
- luminous efficacy, optical efficiency, NPU energy, micro-LED brightness, LC elastic constant K
  (`..._Master_Report_v4-v10_zh.md` §2: "not found");
- in AETHER Lab: real sizes of patent drawings (they have no scale; sizes are model scale), depths and thicknesses
  added by the engineer's completion (labelled "guessed" in every part).

**Staged roadmap (WHAT TO BUILD IN LONG TERM)**

| Stage | What | Proves | Needs | Status |
|---|---|---|---|---|
| 0. Software (done) | AETHER Lab: drawing → assembly, explanation, desk simulation, GLB/STL export | content pipeline; eye-model predictions | laptop, Meta API, Modal GPU | built during the event (section 4) |
| 1. Printed-film test | Print a static 1D hologram of one simple object on film (the Lab already exports a 2400 dpi film, `lab.export_film`), light it with a narrow source, look at it and measure where the eye focuses (autorefractor) | whether a real eye focuses on a 1D hologram as the model predicts; real speckle | a film print, a light source, an eye-test instrument | not done; cost not estimated in the notes |
| 2. Desk prototype, Desk 1 | Phase liquid-crystal panel with eye tracking, 1D holography, pupil-GS encoding, sparse-group speckle reduction; image within −108 … +87 mm of the surface | the full loop with a moving viewer; frame budget; tracking latency (≤ 10–30 ms, `..._v10` §2) | a phase panel (no desk-size part identified), tracker, GPU | not started; cost not estimated in the notes |
| 3. Desk 2 (research) | Full 2D hologram floating ~25 cm above the desk | free-floating image | a kilohertz large-area phase modulator that does not exist (`..._v13` §3) | research only |

Order is set by risk: stage 1 answers the largest open question (real-eye focus) at the lowest cost.

## 7. Risks and Limitations

### A. Current AETHER Lab Limitations

| Limitation | Impact |
|---|---|
| Missing drawing dimensions and scale | Real-world dimensions cannot always be recovered from the original drawing. |
| Inferred hidden geometry | Reconstructed components may require further engineering verification. |
| Imperfect drawing interpretation | Complex, ambiguous, or incomplete drawings may reduce reconstruction quality. |
| Simulated holographic output | Optical performance has not yet been validated using physical holographic hardware. |

### B. Long-Term AETHER Desk Challenges

| Challenge | What Needs to Be Solved |
|---|---|
| Real-eye focus | Validate simulated focus behaviour through physical experiments and eye-focus measurements. |
| Speckle | Reduce unwanted interference patterns while maintaining sufficient display frame rates. |
| Optical efficiency | Improve display brightness while reducing computational and power requirements. |
| Hand interaction | Resolve depth conflicts and occlusion between users' hands and holographic images. |

**Additional Research Considerations**

Patent restrictions, optical display technologies, and the feasibility of free-space holographic imaging require further investigation as AETHER progresses towards physical hardware development. These topics will be addressed in the long-term AETHER research roadmap.

## 8. References

Theory notes (in-event research, 27 Oct – 30 Oct 2026, every file in `theory/` folder):
`AETHER_Physics_Master_Report_v4-v10_zh.md` (checked constants, consolidated conclusions) ·
`AETHER_Physics_v8_Card_Battery_zh.md` (light, power) · `AETHER_Physics_v9_1D_Focus_zh.md` (1D focus, depth budget) ·
`AETHER_Physics_v10_Remaining_Six_zh.md` (tracking, viewers, literature) · `AETHER_Physics_v11_Speckle_zh.md`
(Theorems S1, S2; sparse groups) · `AETHER_Physics_v12_Card_Incoherent_zh.md` · `AETHER_Physics_v13_Desk_Front_zh.md`
(desk, hands) · `AETHER_Phase_Only_Pupil_GS_and_3D_Rebuild_2026-10-30_zh.md` (pupil-GS) ·
`AETHER_Lab_Audit_Fixes_2026-10-30_zh.md` (oblique sharp zone, wave-simulation check).
Pre-event background: `theory/AETHER_Physics_Record.md` (H1 Window Law), `proposal/AETHER_Decision_Log.md`.
Patents: `references/AETHER_Patents_Holographic_Window_2026-10-27.md`.

External sources as cited in those notes: Verschaffelt et al., *Sci. Rep.* 5, 14105 (2015) (speckle visibility);
Wang, Chen, Chakravarthula, *ACM TOG* 2024, arXiv:2409.00028 (smooth vs random phase and focus cues); Takaki 2014,
super multi-view displays; Green, Powers, Banks 1980 (depth of field); Thibos et al., *Applied Optics* 31:3594 (1992)
(longitudinal chromatic aberration); arXiv:2409.01289 (MEMS phase light modulator, 1.44 kHz); Meadowlark Optics UHSP1K
and Yang et al., SID 2019 (fast phase LC); Goodman, *Statistical Optics* (van Cittert–Zernike).
