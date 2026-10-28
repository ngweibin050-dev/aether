# AETHER References

**Every competitor, paper, product and tool studied in Project AETHER, what we learned from each, and how it shaped our decisions.**

Ng Wei Bin · 23–26 October 2026 · living document

Companion files: `theory/AETHER_Physics_Record.md` (derivations and simulations) and `proposal/AETHER_Decision_Log.md` (decisions, costs, rejections).

**Status labels:** **Read** = the page was opened and read during the project; **Cited** = used in our documents with a link, not re-read in depth; **Unverified** = recalled from memory, no link yet, must be checked before citing externally.

---

## Contents

1. The landscape: five kinds of "hologram"
2. Light-field screens: Looking Glass and Sony (detailed study)
3. Volumetric media: fog, spinning mirrors, traps, levitation, dyes
4. Air plasma and air lasing
5. Computational (true) holography
6. Physics and optics sources behind our laws
7. Prior art for the card-phone architecture (v2)
8. Energy, battery and regulation sources
9. AI, 3D and software tools used in AETHER Window
10. Hackathon and project context
11. Market data
12. What we borrowed and what makes AETHER different
13. Verification checklist

---

## 1. The landscape: five kinds of "hologram"

Most products sold as holograms are not true holograms. We classify everything by physical principle; this table is how AETHER positions itself.

| Class | Principle | True hologram? | Anything in the air? | Examples |
| --- | --- | --- | --- | --- |
| A Reflection illusion | Angled glass or film reflects a screen | No | Yes (glass/film) | Pepper's ghost, virtual-singer concerts |
| B Light-field screen | Screen + microlenses send different images in different directions | No (simulated) | No, but the image stays in the screen's window | Looking Glass, Sony Spatial Reality Display |
| C Volumetric medium | Put matter in the air (mist, particles) or sweep a volume with a moving surface | No | Yes | Fog screens, 360° fog projection, spinning mirrors, optical traps, acoustic levitation |
| D Air plasma | Intense lasers ionise air into glowing dots | No (point emitters) | No | Aerial Burton, Fairy Lights |
| E Computational holography | Laser + phase chip rebuild the full wavefront | **Yes** | No, but limited by the Window Law | SeeReal, KAIST, academic prototypes |

Definition source (supplied by the founder, **Read**): screen.com.hk, "The ultimate goal of display technology: holographic projection" — <https://www.screen.com.hk/industry-news/%E9%A1%AF%E7%A4%BA%E6%8A%80%E8%A1%93%E7%9A%84%E7%B5%82%E6%A5%B5%E7%9B%AE%E6%A8%99-%E5%85%A8%E6%81%AF%E6%8A%95%E5%BD%B1%EF%BC%81/>. It defines true holography as wavefront reconstruction by interference and diffraction, and calls Pepper's ghost and holographic film pseudo-holography. Its list of "known" techniques (spinning mirror, vapour, laser plasma) matched the class C/D ideas we had proposed, which is why the founder rejected them.

**AETHER's position:** class E is the only true hologram but obeys our H1 Window Law. The near-term product is window-scale class E; the long-term research attacks class D's physical bottleneck (lower the air-emission threshold by orders of magnitude).

---

## 2. Light-field screens: Looking Glass and Sony (detailed study, 24 Oct)

The founder asked whether either product supports finger control, then asked us to read their official sites and notes for anything useful.

### 2.1 Verified specifications

Looking Glass Go lens parameters come from a real unit's calibration JSON in the official Bridge SDK docs, which is more reliable than marketing numbers. "≈" marks values we calculated from published parameters. Neither company publishes pop-out depth.

| Product | Panel | Optics | Views / angle | Distance and viewers | Brightness / refresh | Interaction | Price (US$) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Looking Glass Go | 6″, 1440 × 2560, 491 dpi (≈ 51.7 µm pixel), 6.2 mm thick | Slanted lenticular, pitch 80.76/inch (≈ 0.315 mm), slope −6.62 (≈ 8.6°), no tracking | Quilt of 66 views, calibrated cone 54° (marketed 58°); ≈ 56k px per view | 25–30 cm, multiple viewers | Unpublished / 60 Hz | No touch, buttons only; AI 2D→3D and GPT characters | 299 |
| Looking Glass Portrait | 7.9″ | Lenticular + thick acrylic block | 48 views, 58° | Multiple | Unpublished | External Ultraleap | — |
| Looking Glass HLD (2026) | 16″ / 27″ / 86″, 1.7 / 2.2 / ≈ 5 cm thick | Fixed etched "holographic background volume" + ordinary 2D video, no eye tracking | Not true multiview | A dozen or more viewers | Unpublished | None | 2k / 4k / 20k |
| Sony ELF-SR1 | 15.6″ 4K LCD (≈ 90 µm pixel), tilted 45° | High-speed eye sensor + micro-optical lens (designed for 2 eyes plus "pseudo views") | ±25° H, +20°/−40° V | 30–75 cm, 1 person | 500 nits / content ≥ 60 fps | None built in | 4,999 |
| Sony ELF-SR2 | 27″ 4K LCD (≈ 156 µm pixel), 64 W | Same, 2nd-gen sensor; crosstalk correction and super-resolution in the display | Unpublished | 2 people *alternating* (firmware 1.20+) | 400 nits / 60 Hz, 14 ms response | None built in | 4,750 |

Sony's published process details: lens-to-panel bonding accuracy is only "tens of micrometres", the residual misalignment is corrected in real-time image processing; the sensor captures "every few milliseconds" and a neural network estimates 3D face pose, working even with masks.

### 2.2 Claims we checked

| Claim | Result |
| --- | --- |
| Looking Glass finger/gesture control needs an external Leap Motion/Ultraleap | True. Official docs only describe Ultraleap; the old 16″ shipped with a Leap Motion in the box; Go has no touch |
| Sony SRD finger control needs an external Ultraleap | Mostly true, reworded: neither SR1 nor SR2 has built-in gestures; the sensor tracks face and eyes only; Sony pages name no hand device |
| Both products' images are mostly behind the screen | Half true: content sits in a virtual box straddling the screen plane, sharpest at the plane; neither publishes pop-out depth; Sony tilts 45° so objects appear to stand on the screen |

### 2.3 Rendering pipelines

| | Looking Glass | Sony SRD |
| --- | --- | --- |
| Per frame | N off-axis views (66 on Go) tiled into a quilt, then interleaved to sub-pixels with calibration | Two off-axis renders at the tracked eye positions; only rays that reach the eyes |
| Content format | Quilt (bottom-left = leftmost view); filename `name_qs11x6a0.5625` encodes columns × rows and aspect | No exchange format; real-time 3D scenes via Unity/Unreal plug-ins |
| Per-unit calibration | Bridge returns pitch, slope, center, viewCone, DPI, invView per serial number | Lens misalignment corrected in the display pipeline |
| Quality controls | "Depthiness"; keep subject on the zero-parallax plane; depth-of-field blur to hide view jumps | Crosstalk correction in three levels (mid-tones only 23–234, full range, local high-precision); moved into display hardware on SR2 |
| Web | `@lookingglass/webxr`, three.js r141+; parameters targetDiam, fovy, depthiness, numViews, tileHeight | None |
| Compute | Quilts usually 4K–8K textures | Reviewer's RTX 2070S ran most demos at full CPU/GPU load |

Both products' top image-quality problem is crosstalk (ghosting), worst with fast head motion and large brightness differences between near and far objects. It can be reduced, not removed. Sony correcting only grey levels 23–234 shows pre-compensation works by subtracting leakage, so pure black and pure white cannot be corrected.

### 2.4 What these products confirmed

All AETHER laws were confirmed and none refuted (details in the physics record §5). New risk discovered: SR2's LCD responds in 14 ms, while AETHER-1's 240 Hz 4-slot scheme leaves 4.17 ms per slot, so a fast OCB/FLC LCD (≤ 1–2 ms) became mandatory.

### 2.5 Sources (all Read)

- Looking Glass, How it works — <https://lfdocs.lookingglassfactory.com/keyconcepts/how-it-works>
- Looking Glass, Quilts — <https://lfdocs.lookingglassfactory.com/keyconcepts/quilts>
- Looking Glass Bridge SDK web integration (Go calibration JSON) — <https://lfdocs.lookingglassfactory.com/software/looking-glass-bridge-sdk/web-application-integration.md>
- Looking Glass Ultraleap docs — <https://lfdocs.lookingglassfactory.com/software/index/leap>
- Looking Glass 16″ legacy page — <https://lfdocs.lookingglassfactory.com/legacy/legacy-hardware/looking-glass-16.md>
- `@lookingglass/webxr` README — <https://cdn.jsdelivr.net/npm/@lookingglass/webxr@0.6.0/README.md>
- Looking Glass HLD overview — <https://lookingglassfactory.com/hld-overview>
- Patent US11683472B2, "Superstereoscopic display with enhanced off-angle separation" (priority 2018-02-27) — <https://patents.google.com/patent/US11683472> (must be designed around; describes tracking damping and dead-reckoning on loss)
- New Atlas review of Looking Glass Go — <https://newatlas.com/technology/review-looking-glass-go/>
- Holoxica model table — <https://www.holoxica.com/looking-glass-gen2-displays>
- Ultraleap case study with Looking Glass — <https://ultraleap.com/company/news/case-study/looking-glass-hand-tracking-interactions>
- Sony Eye-sensing Light Field Display technology — <https://www.sony.co.jp/en/technology/eye-sensing_light_field_display>
- Sony visual design guide — <https://xyn.sony.net/en/developer/technical/spatial-reality-display/design/visual-design>
- Sony crosstalk correction (Unity) — <https://xyn.sony.net/en/developer/setup/spatial-reality-display/unity/crosstalkcorrection>
- Sony ELF-SR2 product page — <https://pro.sony/ue_US/products/spatial-reality-displays/elf-sr2>
- Sony India SRD microsite — <https://www.sony.co.in/microsite/b2b/spatial-reality-display.html>
- CGarchitect review of SR1 — <https://cgconnect.chaos.com/insights/articles/c2d3d64c-sony-spatial-reality-display-reviewed>
- B&H ELF-SR2 specifications — <https://www.bhphotovideo.com/c/product/1761839-REG/sony_elf_sr2_27_4k_spatial.html>

---

## 3. Volumetric media: fog, spinning mirrors, traps, levitation, dyes

| Technology | Key idea | Source | Status | Role in AETHER |
| --- | --- | --- | --- | --- |
| 360° fog projection | Several projectors around a fog column; droplets' forward scattering gives each direction its own image | Yagi et al., SIGGRAPH Asia 2011 — <https://history.siggraph.org/?p=193304> | Cited | Basis of "AETHER Column", rejected (nothing sprayed) |
| 360° light field (spinning mirror) | High-speed projector + spinning mirror shows a different view in each direction | Jones et al., USC ICT, SIGGRAPH 2007 — <https://vgl.ict.usc.edu/Research/3DDisplay/> | Cited | Basis of "AETHER Column", rejected |
| Optical trap display | A laser traps a particle and moves it fast to draw by persistence of vision | BYU, *Nature* 2018 | Unverified | Ruled out (Class 3B/4 lasers, matter in air) |
| Acoustic levitation display | Ultrasound array levitates a bead lit by light; can add haptics and sound | *Nature* 2019 | Unverified | Simulated (stage 1); dock accessory only |
| Photoswitchable dye 3D display | UV-activated dye read out by visible light makes a volumetric image in liquid | Patel et al., *Nature Chemistry* 2017 | Unverified | Basis of "AETHER Mist", rejected (chemicals in air) |
| Xolography | Two-colour light-sheet volumetric photopolymerisation | *Nature* 2020 | Unverified | Cited as prior art for Mist |
| Integral imaging | Microlens arrays record and replay a 3D light field | Lippmann, 1908 | Textbook | AETHER-1 optics converged on this principle |
| Holography | Wavefront recording and reconstruction | Gabor, 1948 (Nobel Prize 1971) | Textbook | Definition of the current target |

**Why AETHER dropped this class:** every option either puts something into the air or needs a large mechanism. Users and investors will not accept spraying anything into the air (founder's rule, 25 Oct).

---

## 4. Air plasma and air lasing

| Item | Facts | Source | Status |
| --- | --- | --- | --- |
| Laser-induced air plasma displays | Focused fs/ns lasers ionise air at ~10¹³–10¹⁴ W/cm²; glowing points; crackle, ozone, eye hazard | Aerial Burton (Japan, ns lasers, outdoor), Fairy Lights (Univ. of Tsukuba, fs lasers, touchable) | Names and years Unverified |
| Air lasing (N₂⁺ at 391/428 nm) | Femtosecond pulses make air a coherent gain medium | LOA (ENSTA Paris) — <https://loa.ensta-paris.fr/research/f-ilm-research-group/lasing-effect-in-air-and-nitrogen/>; Shanghai teams | Cited |

**Meaning for AETHER:** the only known "add nothing, air glows by itself" route. Our research target is a mechanism with a threshold 10⁴–10⁶× lower (physics record §8.6).

---

## 5. Computational (true) holography

| Item | Key idea | Source | Role in AETHER |
| --- | --- | --- | --- |
| SeeReal Technologies (Germany) | Small RGB lasers + diffractive optics make a coherent plane wave; LC phase chip shows a hologram built from sub-holograms (one per scene point); a camera tracks the eyes and active beam steering moves a small "viewing window" onto each pupil every frame, so pixels only need to cover the pupil region | <https://seereal.com/how-does-it-work-seereals-holographic-display-principle-in-a-nutshell> (Cited) | Most direct reference for the Phase 1 Holo Card; AETHER adds card size and finger interaction |
| KAIST volume-speckle holography | A scattering layer behind the SLM spreads light and, with wavefront coding, enlarges the hologram's effective étendue and viewing angle | *Nature Photonics* 2017 — <https://koasas.kaist.ac.kr/handle/10203/222701> (Cited) | We scaled the idea to room walls and derived H3, showing ≥ 10⁴ energy shortfall |

---

## 6. Physics and optics sources behind our laws

| Topic | Used for | Source | Status |
| --- | --- | --- | --- |
| Radiative transfer equation | Three ways to see a point (§1 of the physics record) | Standard radiative transfer texts | Textbook |
| Rayleigh scattering of air, King factor | Theorem 1 | Standard optics texts | Textbook |
| Kirchhoff–Helmholtz integral theorem | H1 Window Law | Born & Wolf, *Principles of Optics* | Textbook |
| Grating equation sin θ = λ/2p; space-bandwidth product | Steering angle vs pixel pitch; card pixel limit | Same | Textbook |
| Superoscillation (Aharonov, Berry) and its energy cost | Attack 1 | <https://ar5iv.arxiv.org/html/1209.6572> | Cited |
| Wavefront shaping through scattering media; phase-conjugation focus enhancement ≈ πN/4 | H3 derivation | Vellekoop & Mosk and related work | Unverified (exact origin) |
| Gor'kov acoustic radiation potential | Acoustic levitation simulation | Standard acoustics literature | Textbook |
| ISO 9613-1 atmospheric sound absorption | Ultrasound absorption figure | ISO 9613-1 | Standard |
| Earnshaw's theorem | Ruling out static levitation | Textbook | Textbook |
| Eye depth of field ≈ ±0.3 D | Theorem 3 | Vision-science literature | To be tested on users |
| Laser safety (Class 1 limits), IEC 62471 photobiological safety | Plasma rejection; IR illumination | IEC 60825 / IEC 62471 | Standard |
| Air nonlinear index n₂ ≈ 3 × 10⁻¹⁹ cm²/W | "Air is linear" starting fact | Nonlinear optics literature | Unverified value |
| N₂ A³Σu⁺ lifetime ~2 s; O₂ quenching k ≈ 2.5 × 10⁻¹² cm³/s | Metastable-ladder hypothesis | Molecular kinetics literature | Unverified |
| N₂ first-positive band (B³Πg → A³Σu⁺, 580–1000 nm) in aurora and red sprites | Best research lead | Atmospheric physics literature | Textbook-level, specific data to be checked |

---

## 7. Prior art for the card-phone architecture (v2, 25 Oct)

Every component of the reciprocal-aperture phone had prior work; we found no example combining them in one aperture. These were researched on 25 Oct; links were not stored in our notes, so treat them as **Unverified** until re-linked.

| Prior work | What it showed | Used for |
| --- | --- | --- |
| Oh et al., *Science* 2017 (UIUC dual-function nanorod LEDs) | One pixel can emit, sense light, detect finger proximity and harvest ambient light | Emit-and-sense pixels |
| MIT BiDi Screen (2009) | LCD used as a mask for depth sensing through a display | Display-as-sensor precedent |
| HP Labs, *Nature* 2013 (multi-directional diffractive backlight, Leia's predecessor) | 64 views, 90° zone with a thin light guide; directions fixed; needs LCD; cannot sense | Rejected as AETHER's direction layer |
| Fraunhofer array projection | Lenslet-array projectors | Ω-3 surface projection |
| Wi-Charge | Infrared power beaming ~1 W at metres | Theorem 9 source list |
| University of Tokyo quasistatic cavity resonator, *Nature Electronics* 2021 | ~5 W to a phone anywhere in a room at ~37 % efficiency | Theorem 9 source list |
| UW Passive Wi-Fi (backscatter) | µW-level communication | Sleep mode |
| University of Washington battery-free phone (2017) | Calls without a battery | Battery-free variant (v2.1) |
| Yang Ming Chiao Tung University indoor perovskite PV | Record indoor efficiency (~38.7 %) | Indoor light harvesting |
| Adhikary & Vertanen mid-air typing research | ~16 wpm mid-air typing | Typing estimate |
| CMU Toffee | Around-device acoustic touch | Typing/touch options |
| Microchip GestIC | Electric-field gesture sensing | Gesture options |
| LG Display thin actuators | Panel-as-speaker | Audio through glass |
| Humane AI Pin (Wikipedia) | Laser palm projection overheated, ~9 minutes per projection, discontinued Feb 2025 | Reason not to use laser projection |
| Betavolt BV100 (China, 2024) | 100 µW betavoltaic, 50-year life | Rejected: µW only |
| Renata CP042350 | 0.42 mm thin cell, 28 mAh × 3 V (~174 Wh/L) | Theorem 8 reference |
| Apple iOS licence | iOS only licensed for Apple hardware | iOS dropped (founder's choice) |

---

## 8. Energy, battery and regulation sources

| Item | Used for | Status |
| --- | --- | --- |
| ICNIRP 2020 RF exposure guidelines (public limit 10 W/m²) | Far-field RF cap ~23 mW | Cited |
| EU Regulation 2023/1670 (smartphone ecodesign: battery ≥ 80 % after 800 cycles; stricter if non-user-replaceable; IP67) | Battery-life target 1000 cycles ≥ 80 % + IP67 | To be checked against the legal text |
| EU Battery Regulation 2023/1542 | Replaceability | To be checked |
| iPhone Air (~12 Wh, 5.64 mm), Galaxy S25 Edge (5.8 mm), 5000 mAh Android (~19 Wh) | Runtime comparison | Recalled figures, not teardown-verified |
| Phone BOM ranges (mid-range US$150–250, flagship 450–500, foldable 600–700) | Cost comparison | Recalled teardown estimates, not verified |
| 12″ mature-node wafer foundry price ~US$1,200–2,500 per wafer | Backplane cost | Estimate |

---

## 9. AI, 3D and software tools used in AETHER Window

| Tool | Use | Source | Status |
| --- | --- | --- | --- |
| Three.js (0.160, vendored) | 3D rendering, off-axis projection | <https://threejs.org> | In use |
| MediaPipe Tasks Vision 0.10.14 (Face Landmarker, Hand Landmarker, Gesture Recognizer, Interactive Segmenter `magic_touch`, EfficientDet-Lite0) | Eye/hand tracking, segmentation, object recognition | <https://ai.google.dev/edge/mediapipe> | In use (models vendored) |
| One-Euro filter | Low-latency smoothing of tracking | Casiez et al., CHI 2012 | In use |
| Generalised perspective (off-axis) projection | Screen-as-window rendering | Kooima, "Generalized Perspective Projection" (2009) | In use |
| Meta Llama via the Meta/Llama API (OpenAI-compatible base URL `https://api.llama.com/compat/v1`, model `Llama-4-Maverick-17B-128E-Instruct-FP8` preset) | Speech → structured scene actions; physics tutor | Hackathon-provided | Preset unverified until event docs arrive |
| Meta SAM 3D Objects | Single photo → textured 3D mesh (GLB) | Runware docs — <https://runware.ai/docs/models/meta-sam-3d-objects.md>; launch coverage — <https://3dprintingindustry.com/news/meta-launches-ai-design-tool-sam-3d-for-realistic-3d-reconstruction-from-single-images-246986/> | Integrated against a mock; live call needs a key |
| SAM 3D local setup requirements (Linux, ≥ 32 GB NVIDIA GPU) | Why local inference is not possible on the founder's laptop | <https://huggingface.co/spaces/HorizonRobotics/EmbodiedGen-Texture-Gen/blob/main/thirdparty/sam3d/doc/setup.md> | Read |
| Meta SAM 3.1 | Segmentation of real objects | Meta Model API (event) | Planned |
| Runware (~US$0.006 per SAM 3D run, ~1 min) | Hosted SAM 3D | Runware docs above | Optional, paid |
| Lenticular sheet, 50 LPI (≈ 0.51 mm lenses), ~RM23 | Optional glasses-free desk rig | Marketplace listing found by the founder | Optional |

---

## 10. Hackathon and project context

| Item | Link | Notes |
| --- | --- | --- |
| Meta Global AI Developer Hackathon (Cerebral Valley) | <https://cerebralvalley.ai/e/meta-ai-developer-hackathon> | Remote, worldwide, Indie and Startup tracks, US$1M pool; must use Meta Model API or Meta open weights. Registration approved 26 Oct; build 27 Oct 01:00 → 5 Nov 10:00 MYT |
| BizPilot (founder's previous AI project) | <https://github.com/ngweibin050-dev/BizPilot> | SME operations co-pilot; WorkBuddy agent SDK, 39 MCP tools, approvals, Supabase RLS |

---

## 11. Market data

| Figure | Source | Caveat |
| --- | --- | --- |
| Holographic display market ~US$4.3 B (2025) → ~US$40.8 B (2035), CAGR ~25.5 % | GM Insights — <https://www.gminsights.com/industry-analysis/holographic-display-market> | Includes many class A/B/C pseudo-holographic products; demand indicator only |

---

## 12. What we borrowed and what makes AETHER different

### 12.1 Borrowed engineering practices

1. **Per-unit calibration instead of precision bonding** (Sony tens-of-µm bonding + software correction; Looking Glass per-serial calibration JSON).
2. **Slanted lens arrays against pixel grids** to avoid moiré (Looking Glass Go ≈ 8.6°).
3. **Crosstalk pre-compensation with grey headroom** (Sony's three levels).
4. **Graceful tracking loss:** damping, dead reckoning < 200 ms, then fall back to static multiview (Looking Glass patent; Sony works with masks and low light).
5. **Asymmetric vertical cone** (Sony +20°/−40°) for desk viewing.
6. **Quilt compatibility** to reuse the Looking Glass content ecosystem.
7. **Psychological float cues:** contact shadows, frames, opaque borders (HLD, Looking Glass patent). Several were added to AETHER Window.
8. **Eye-tracked viewing windows** (SeeReal) for the Phase 1 Holo Card.

### 12.2 Differences

| Dimension | Looking Glass Go | Sony SRD | AETHER |
| --- | --- | --- | --- |
| Image type | Untracked multiview | Eye-tracked stereo | Phase 1: true hologram (wavefront reconstruction), window-scale |
| Finger interaction | None; external Ultraleap on large units | None built in | Built in, finger co-located with the floating image |
| Viewers | Many, low resolution each | 1 (SR2 alternates 2) | 1–2 (Phase 1) |
| Long-term path | 2D video + etched background (HLD) | — | Research line on air emission for room-scale holography |
| Price | US$299 | US$4,750–4,999 | Holo Card est. US$499–899 |

Their leads must be acknowledged: Unity/Unreal plug-ins and the quilt ecosystem are mature, and Sony has a second-generation sensor and in-display crosstalk correction. Looking Glass's 2026 move to HLD suggests the mass market pays for *presence* more than parallax, so AETHER's demo must prove "touchable and editable", not only "looks 3D".

### 12.3 Originality, stated honestly

Pure reasoning repeatedly converged on known principles (integral imaging, eye-tracked stereo, acoustic levitation, SeeReal-style viewing windows), so "eye tracking + microlenses" is **not** AETHER's innovation. Candidate contributions are: the theorem-based design limits (Theorems 2–10, H1); the H3 scattering-focus law; the air-emission screening and discovery target; same-ray emit/sense pixels and retinal retro-reflection viewer finding (v2); and finger interaction co-located with floating images. A patent and literature search is required before any claim (known patent to design around: US11683472B2).

---

## 13. Verification checklist (before any external citation)

- [ ] BYU optical trap display (*Nature* 2018)
- [ ] Acoustic levitation display (*Nature* 2019)
- [ ] Patel et al. photoswitch dye display (*Nature Chemistry* 2017); xolography (*Nature* 2020)
- [ ] Aerial Burton and Fairy Lights names, years and parameters
- [ ] Sony SR2 price
- [ ] N₂(A) quenching rate constant by O₂; N₂(A) radiative lifetime
- [ ] Air nonlinear index n₂
- [ ] Original source of the πN/4 phase-conjugation focusing enhancement (Vellekoop & Mosk)
- [ ] Re-link all v2 prior-art items in §7
- [ ] Meta API model names and SAM availability once the event documentation is published

- Constants check (28 Oct 2026): sourced values for LC speed and viscosity, Δn, thin-cell energy density, panel prices, laser thresholds, air n₂, depth of field, stereoacuity, latency and speckle thresholds. See section 2 "常数查证表" (verification table) and section 6 "主要来源" (main sources) of `../theory/AETHER_Physics_Master_Report_v4-v10_zh.md`.
- Speckle sources (v11, 28 Oct 2026): Verschaffelt 2015 (Sci. Rep. 5, 14105); arXiv 2409.01289 (MEMS phase light modulator, 1.44 kHz); "Holographic femtosecond laser processing using 6.3 kHz pulse-to-pulse spatial light modulation with binary phase masks"; Takaki & Yokouchi 2011 (Opt. Express); Wang 2024; Williams 1985. See section 8 "来源" (sources) of `../theory/AETHER_Physics_v11_Speckle_zh.md`.
- Card horizontally-incoherent option (v12, 28 Oct 2026): Verschaffelt 2015 (Sci. Rep. 5, 14105); van Cittert-Zernike theorem (Goodman, Statistical Optics); Takaki 2014. See section 8 "来源" (sources) of `../theory/AETHER_Physics_v12_Card_Incoherent_zh.md`.
