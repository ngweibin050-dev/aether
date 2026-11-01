# AETHER Holography Roadmap: from a simulated desk to a holographic workbench

Ng Wei Bin · November 2026 · long-term proposal

**Status in one line: nothing optical has been built.** Every optical number below is a derivation or a simulation,
from the research notes in `theory/` or from the AETHER Lab engine (`aether-lab/engine/`). Values that were assumed
or recalled rather than checked are labelled *assumed*. Where a note and the engine disagree, the engine's number is
used and the disagreement is stated.

Sources are cited inline as file names. The theory notes v4–v13 and the two notes of 30 Oct were written during the
hackathon (27 Oct – 1 Nov 2026) as research, not product code; `theory/AETHER_Physics_Record.md` and
`proposal/AETHER_Decision_Log.md` are pre-event background (23–26 Oct).

---

## 1. The problem

A designer who builds a machine in CAD sees it on a flat screen. Depth is inferred from shading and rotation; the eyes
always focus on the glass. Headsets give stereo depth but put a device on the face, and stereo screens still make the
eye focus on the panel while the two eyes converge somewhere else.

AETHER's goal is a **workbench that shows a true hologram**: the full light wavefront of the object, so the eye
focuses at the object's real depth and each eye sees its own side, with the object standing on or just above the
desk where hands can reach it. Nothing is worn and nothing is released into the air.

## 2. The AETHER Desk concept

- **A flat holographic panel lying in the desk**, viewed by a seated user about 70 cm away
  (`theory/AETHER_Physics_v13_Desk_Front_zh.md`).
- **Eye-tracked:** the hologram only has to be correct inside a small eye box around each tracked pupil, which cuts
  the required pixel count by orders of magnitude (`theory/AETHER_Physics_Record.md` §2.4, §8;
  `theory/AETHER_Physics_v10_Remaining_Six_zh.md` §2).
- **One-dimensional (1D) holography:** true holography (coherent) in the vertical direction; in the horizontal
  direction, columns are mutually incoherent and each eye gets its own view. This is what makes the computation and
  the modulator speed fit (`theory/AETHER_Physics_v8_Card_Battery_zh.md`, `..._v9_1D_Focus_zh.md`).
- **The image sits on the panel**, partly above and partly below the glass, inside the zone where 1D holography still
  gives natural focus (section 3.3). Hands interact from the front and the sides (section 3.2).
- **The design software and AI come first.** AETHER Lab, built during the hackathon, already turns one paper machine
  drawing into a 3D assembly with Meta's models and scores how sharp each part would look on this desk (section 4).

## 3. Physics summary

### 3.1 The Window Law (geometry of any true hologram)

> *A point P is seen only if the line from the eye through P, extended backwards, passes through the panel.*
> (`theory/AETHER_Physics_Record.md` §8.1, "H1")

The record itself labels this an application of the known Kirchhoff–Helmholtz integral, a *candidate constraint*
whose arithmetic is reproducible but which has not been reviewed by a Fourier-optics expert (§8, status note of
26 Oct). Consequence for the desk: the usable cross-section at height h is at most W·(d − h)/d for a panel of width W
seen from distance d; a 27″ panel (59.8 × 33.6 cm) at 70 cm gives 60 × 34 cm at the surface and 51 × 29 cm at
10 cm height (`theory/AETHER_Physics_v13_Desk_Front_zh.md` §1).

**Engine check:** `lab.window_check` reproduces the rule (test 6: a point inside the window is visible, outside it is
not).

### 3.2 Hands in the image

The light of an image point comes from a small patch of the panel along the line panel → point → pupil
(about 0.3 mm wide at 5 cm height, 0.7 mm at 10 cm). A hand **in front of** the object occludes it correctly; a hand
**behind or inside** it blocks light that should appear in front of the hand: a depth conflict no software can fix
(`theory/AETHER_Physics_v13_Desk_Front_zh.md` §4). Interaction rule: work from the front and the sides; pull parts
towards the user. **Engine check:** test 6 ("hand behind a point → conflict, in front → natural").

### 3.3 The sharp zone of a 1D desk

In 1D holography the horizontal light comes from the panel plane, so an image point at distance D from the eye with
the panel at distance d has an astigmatism of |1/D − 1/d|. The depth budget follows (`..._v9_1D_Focus_zh.md`):

  Δz ≈ Δmax · d²   (the usable depth grows with the square of the viewing distance)

| Quantity | Note | Engine (used) |
|---|---|---|
| Full 2D hologram, eye model (4 mm pupil, 530 nm, 15 c/deg) | 0.855 (`..._v13_Desk_Front_zh.md` §2) | 0.855 (test 4) |
| 1D desk, image 5 cm above the panel, % of full 2D | 89 % (`..._v13_Desk_Front_zh.md` §2, 70 cm table) | **94 %** (test 4) |
| 1D desk, 15 cm above | 59 % (same table) | **61 %** (test 4) |
| Sharp zone, ≥ 80 % of full 2D | about ±10 cm around the surface (`..._v13_Desk_Front_zh.md` §2) | **−108 … +87 mm**, computed along each point's own line of sight for an eye at (0, −450, 540) mm looking down ~50° (`theory/AETHER_Lab_Audit_Fixes_2026-10-30_zh.md` §2; shown in the Lab UI) |

The note's table uses vertical height; the engine uses the oblique line of sight of a seated viewer, which is why it
is stricter above the panel. The engine's numbers are the ones to use.

**Independent check in the engine:** a true-scale wave simulation of the 1D desk panel (coherent vertical
sub-hologram, incoherent columns) matches the analytic eye model within about 1 %: 0.855 vs 0.855 for a point on the
panel, 0.775 vs 0.776 at 0.62 m (test 14; `..._Lab_Audit_Fixes_2026-10-30_zh.md` §4). This validates the eye model
against itself in two independent methods; it is not a measurement with a real eye.

Floating an object 25 cm above the desk (the "film" version) needs full 2D holography, about 2 × 10⁸ pixels and a
kilohertz-rate large-area phase modulator that does not exist today (`..._v13_Desk_Front_zh.md` §3: "Desk 2", a
second-stage research item).

### 3.4 Speckle

Coherent light produces speckle (grain). The visibility threshold is a contrast of about 3.2–4.4 % for a still image
and 4.8–6.9 % for a moving one (Verschaffelt et al. 2015, cited in `..._v11_Speckle_zh.md` §1).

- **Single-frame floor (Theorem S1):** C ≈ 0.67 · λ / (D·θ): about 0.30 for a 4 mm pupil averaged over 1′
  (`..._v11_Speckle_zh.md` §2). One frame cannot be speckle-free.
- **Spectral width does not help a thin phase panel (Theorem S2):** 0 → 6 % bandwidth changed the contrast only from
  0.291 to 0.289 (`..._v11_Speckle_zh.md` §3).
- **Smooth-phase holograms remove speckle but also the focus cue** (sharpness at 0.5 D defocus stays 91 % instead of
  13 % for a real object) — rejected (`..._v11_Speckle_zh.md` §4; Wang et al. 2024).
- **Sparse point groups work:** show every k-th point per frame and cycle the k groups. For 1D holography (only the
  vertical is coherent) k = 3 gives **2.7 %** at focus and 5.0 % at 0.5 D defocus with correct focus cues, at the cost
  of k = 3 times the frames (`..._v11_Speckle_zh.md` §4, §5). **Engine:** the Lab's 3 × 3 sparse-group model reports
  2.6–3.5 % on the live demo scenes (Physics panel, Nov 1).
- **Frame budget:** with k = 3, a heated liquid crystal (~0.6 ms, ~555 frames/s) serves 1–2 viewers
  (`..._v11_Speckle_zh.md` §5; `..._v13_Desk_Front_zh.md` §5).

### 3.5 Phase-only encoding

A phase-only panel cannot write the complex field directly. In the desk geometry (projected vertical pitch 34.6 µm,
eye box 10.7 mm at 0.7 m, 4 mm pupil) the naive encodings fail: kinoform MTF 0.041 (ideal 0.855), double-phase 0.103,
most of the light becoming haze (`theory/AETHER_Phase_Only_Pupil_GS_and_3D_Rebuild_2026-10-30_zh.md` §1).

**Pupil-band phase retrieval (pupil-GS):** because the eye is tracked, only the 4.6 mm band around the pupil must be
right; a Gerchberg–Saxton loop with a "don't care" region outside the band solves one phase-only column. Degree-of-
freedom count: the band needs 0.86 N real conditions for N phase unknowns, so a near-exact solution exists when eye
box / pupil band > 2 (here 2.33) (same note §2). **Engine (test 17):** pupil-GS 0.852 vs complex modulation 0.855 for
a point on the panel, 0.771 vs 0.775 at 8 cm in front; kinoform 0.041 / 0.143. Cost: light efficiency — image error
2.2 % at η = 0.05 of the brightest column's light, 40 % at η = 0.5 (same note §2), i.e. several times more backlight;
the eye needs only microwatts (`..._v8_Card_Battery_zh.md`). Open: compute (200 FFTs per column per sub-frame; ~20 s
for 160 × 160 on a CPU), tracking error beyond 0.3 mm, real liquid-crystal quantisation and fringing (not modelled).

### 3.6 Light, power and pixels

- **Light to the eye:** about 0.24 µW (indoor, 200 cd/m²) to 1.2 µW (outdoor) per eye for a card-sized window at
  40 cm, because tracking sends light only into the pupil (`..._v8_Card_Battery_zh.md`; luminous efficacy and optical
  efficiency *assumed*).
- **Coherence needed by a 1D sub-hologram:** bandwidth ≤ 56 nm and source angle ≤ 0.27 mrad (card case; same note),
  so a small micro-LED can replace a laser in principle.
- **Desk pixels:** vertical 45 µm (eye box 7–10 mm), about 7,500 rows × 4,000 columns ≈ 3 × 10⁷
  (`..._v13_Desk_Front_zh.md` §5). Engine: eye box 8.2 mm at a 45 µm pitch (test 4).
- **Liquid-crystal speed (checked constants):** 0.6 ms measured for a fast heated phase LC; 0.96 ms at room
  temperature by recalculation (`..._Master_Report_v4-v10_zh.md` §2, §3.1).

## 4. What AETHER Lab already proves in software (measured)

AETHER Lab (`aether-lab/`, built 27 Oct – 3 Nov 2026) is the software half of the desk: it produces the 3D content and
predicts how it would look on the desk. All numbers below are from `aether-lab/docs/RESULTS.md` (live runs with Meta's
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

## 5. What is not built, only simulated, or assumed

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

## 6. Staged roadmap

| Stage | What | Proves | Needs | Status |
|---|---|---|---|---|
| 0. Software (done) | AETHER Lab: drawing → assembly, explanation, desk simulation, GLB/STL export | content pipeline; eye-model predictions | laptop, Meta API, Modal GPU | built during the event (section 4) |
| 1. Printed-film test | Print a static 1D hologram of one simple object on film (the Lab already exports a 2400 dpi film, `lab.export_film`), light it with a narrow source, look at it and measure where the eye focuses (autorefractor) | whether a real eye focuses on a 1D hologram as the model predicts; real speckle | a film print, a light source, an eye-test instrument | not done; cost not estimated in the notes |
| 2. Desk prototype, Desk 1 | Phase liquid-crystal panel with eye tracking, 1D holography, pupil-GS encoding, sparse-group speckle reduction; image within −108 … +87 mm of the surface | the full loop with a moving viewer; frame budget; tracking latency (≤ 10–30 ms, `..._v10` §2) | a phase panel (no desk-size part identified), tracker, GPU | not started; cost not estimated in the notes |
| 3. Desk 2 (research) | Full 2D hologram floating ~25 cm above the desk | free-floating image | a kilohertz large-area phase modulator that does not exist (`..._v13` §3) | research only |

Order is set by risk: stage 1 answers the largest open question (real-eye focus) at the lowest cost.

## 7. Risks and open problems

1. **Real-eye focus on 1D holograms** is unmeasured (section 5). If the eye does not focus as modelled, the sharp zone
   shrinks.
2. **Speckle vs viewers:** sparse groups need ~3× the frames; with today's heated LC about 1–2 viewers
   (`..._v11` §5). More viewers need faster modulators (MEMS phase mirrors reported at 1.44 kHz, `..._v11` §7).
3. **Phase-only encoding cost:** pupil-GS needs several times more backlight and heavy per-frame computation; real LC
   effects not modelled (section 3.5).
4. **Patents:** SeeReal US12298522B2 (single-parallax hologram encoding with tracking) is active to about 2038 and is
   the main risk; Samsung US10416762B2 (beam-steering backlight) to about 2036
   (`references/AETHER_Patents_Holographic_Window_2026-10-27.md`, preliminary, not legal advice).
5. **Hands:** a hand behind or inside the image causes a depth conflict that software cannot fix (section 3.2).
6. **Not pursued:** images in empty air away from a panel need the air itself to emit light, which all known pathways
   only reach as plasma (`..._Master_Report_v4-v10_zh.md` §1); this roadmap stays with a panel the user looks through.

## 8. References

Theory notes (in-event research, 27 Oct – 30 Oct 2026, `theory/`):
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
