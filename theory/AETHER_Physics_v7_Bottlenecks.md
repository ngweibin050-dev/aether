# AETHER Physics v7: Attacking the Three Holographic-Window Bottlenecks

Oct 27, 2026 · Ng Wei Bin

Follows v6 (`AETHER_Physics_v6_Window_and_Air_Mirror.md`) and the prior-art note (`../references/AETHER_Prior_Art_Holographic_Window_2026-10-27.md`). Numbers: `simulations/aether_bottlenecks_v7.py` → `simulations/results_v7.json`. Labels: Established, Derived, Estimate, Assumed, Speculative; "from memory" means not re-verified.

## Answer

All three bottlenecks (fast phase LC, cost, large size) give way to three moves that each use known physics and existing factory processes:

1. **Thin reflective high-birefringence LC.** Use the light twice (a mirror behind the LC) and a high-birefringence mixture. The layer drops from 3.2 µm to 0.8 µm. Response time scales as thickness squared, so it falls 16×, from about 8.5 ms to about 0.5 ms. That is fast enough for 360–850 Hz sub-frames (Derived, with Assumed material constants).
2. **1D ("vertical-parallax-only") hologram encoding plus a lenticular eye split.** The panel is a true hologram only vertically. Horizontally, a lenticular sheet sends a separate image to each eye, the way glasses-free 3D screens do. Both eyes are served at once, so the required rate halves to 180 Hz. The pixel count falls 5×, and the panel is scanned along its coarse direction (Derived; this is SeeReal's published approach, from memory).
3. **Re-use mass-market panel classes.** With moves 1–2 the card panel has about 2.6 million pixels on about 856 scan lines, which is phone-class. The TV panel has about 28 million pixels on about 4,200 scan lines at 180 Hz, which is close to an 8K TV panel (33 million pixels, 4,320 lines, 120 Hz) rotated 90° (Derived).

Price paid: move 2 gives true focus cues mainly through vertical wavefront curvature. Whether the eye accommodates correctly to such a 1D hologram needs a perception check (Speculative). This is now the most important open question for Route A.

## 1. Bottleneck: fast phase liquid crystal

**What the panel must do.** A phase-only pixel must delay light by any amount from 0 to 2π, and then settle to a new value within one sub-frame. At 360 Hz a sub-frame is 2.78 ms. That time also has to cover writing the pixel row and flashing the laser.

**Why ordinary LC is slow (Established, Jakeman–Raynes).** When the voltage changes, the LC molecules relax with time constant

```latex
\tau \approx \frac{\gamma_1\, d^2}{K_{11}\, \pi^2}
```

Here γ₁ is the rotational viscosity, K₁₁ the elastic constant and d the layer thickness. To delay red light (635 nm) by a full 2π, d = λ/Δn in transmission, where Δn is the birefringence. Display LC has Δn ≈ 0.1–0.2, so d ≈ 3.2 µm. With γ₁ ≈ 0.1 Pa·s and K₁₁ ≈ 12 pN (Assumed, from memory) that gives τ ≈ 8.5 ms: too slow.

**The lever is d², not chemistry alone (Derived).**

| Design | Layer d | τ | Max sub-frame rate (≈ 1/2.2τ) |
| --- | --- | --- | --- |
| Transmissive, Δn 0.20 | 3.2 µm | 8.5 ms | 53 Hz |
| Transmissive, Δn 0.40 | 1.6 µm | 2.1 ms | 214 Hz |
| Reflective, Δn 0.20 | 1.6 µm | 2.1 ms | 214 Hz |
| **Reflective, Δn 0.40** | **0.8 µm** | **0.53 ms** | **854 Hz** |
| Reflective, Δn 0.40, low-viscosity (γ₁ 0.05) | 0.8 µm | 0.27 ms | 1,709 Hz |

- **Reflective** means a mirror behind the LC, so light passes through twice and only half the thickness is needed. Phase-only LCoS microdisplays already work this way (Established). For a window, light comes in from a thin front light guide, as in e-readers, and leaves the same side.
- **High Δn (0.3–0.4)** mixtures exist (from memory) but are more viscous and less UV-stable. That is a materials-engineering trade, not a physics wall.
- **Overdrive**, a brief over-voltage, speeds up switching-on by several times (Established in LCD TVs). The time constant above is the slower relaxation direction.
- **Pixel-to-layer ratio.** At 0.8 µm thickness, the card pixel (18 µm) is about 22× wider than the layer is thick, so fringing fields between neighbouring pixels stay small (Derived; the ratio is better than in LCoS).

**Alternatives kept as backups.** Blue-phase LC switches in under 1 ms, but needs high voltage and a thick layer for 2π (from memory). Ferroelectric LC switches in microseconds, but only gives 2 phase levels (0 or π). That halves efficiency and adds twin images (Established).

**Result (Derived, Assumed constants).** A reflective, 0.8 µm, Δn ≈ 0.4 nematic phase layer meets 360 Hz with margin and reaches about 850 Hz. Low-viscosity mixtures roughly double that. Fast phase LC is an engineering target with a clear recipe, not an unknown.

## 2. Reduce the rate and pixels you need: 1D encoding

**Why v6 needed 360 Hz.** It assumed 2 eyes × 3 colours × 60 Hz, all shown one after another, because the hologram's repeated copies make a second eye 63 mm away see a ghost.

**1D encoding (Derived; SeeReal's published approach, from memory).** Make the hologram fine (18–90 µm pitch) only in the vertical direction. Make it coarse in the horizontal direction (100–250 µm) and put a lenticular sheet, or the steering backlight, on top that sends left columns to the left eye and right columns to the right eye. Each eye then gets a vertical-only hologram:

- **Rate:** both eyes are served at the same time, so the panel needs 3 colours × 60 Hz = **180 Hz** (or 60 Hz with RGB sub-pixels).
- **Pixels:** the horizontal direction no longer needs hologram-fine pitch.
- **Focus:** vertical wavefront curvature still carries depth, and horizontal depth comes from the two eyes seeing different images. Whether accommodation follows a 1D curvature cue as well as a full 2D one is the key **open perception question** (Speculative).

| Window | Fine pitch (vertical) | Coarse pitch (horizontal, Assumed) | Scan lines | Pixels | Rate | Time to write one line (rolling scan) |
| --- | --- | --- | --- | --- | --- | --- |
| Card (0.4 m) | 18 µm | 100 µm | 856 | 2.6 × 10⁶ | 180 Hz | 6.5 µs |
| Desk (0.7 m) | 31.5 µm | 150 µm | 4,000 | 4.3 × 10⁷ | 180 Hz | 1.4 µs |
| TV (2 m) | 90 µm | 250 µm | 4,200 | 2.8 × 10⁷ | 180 Hz | 1.3 µs (2.6 µs with two driven halves) |

Compare full 2D at 360 Hz: card 1.4 × 10⁷ pixels, 0.93 µs per line; TV 7.8 × 10⁷ pixels, 0.42 µs per line. Those line times are too short for normal TFT backplanes.

**Rolling scan (Established in LCD TVs).** Lines are written one after another across the whole sub-frame. A band of laser light follows behind and lights each line only after its LC has settled. This doubles the time available per line compared with "write everything, then flash".

**Smaller viewing window (Derived).** The pitch is p = λd/w. Shrinking the window from 10 mm to 7 mm or 5 mm (still larger than a 4 mm pupil, but tracking must be tighter) gives card pitches of 25.7 / 36 µm and 7.0 / 3.6 million pixels for full 2D. That is a second, independent lever.

## 3. Bottleneck: cost

**The point is to reuse what factories already make (Derived from the table above; prices Estimate, from memory).**

| Window | Equivalent mass-market panel | Why it matches |
| --- | --- | --- |
| Card, 1D encoding | Phone LCD (about 2,400 × 1,080 = 2.6 M pixels) | 2.6 M pixels, 856 lines, 1,411 ppi in the fine direction (phones are 400–500 ppi, VR LCDs over 1,000 ppi) |
| TV, 1D encoding | 8K TV panel (7,680 × 4,320 = 33 M pixels, 120 Hz) | 28 M pixels, 4,200 lines, 180 Hz; 282 ppi in the fine direction |

Differences from a normal panel, all with established processes:

- **Phase-only LC mode (ECB, homogeneous alignment)** instead of VA/IPS, with no colour filter and no polariser loss (the lasers are already polarised). This is the same backplane and different cell processing (Established in LCoS).
- **Reflective pixel electrodes** (a metal mirror per pixel), as in reflective LCD and LCoS.
- **Thin 0.8 µm cell gap.** LCoS holds this on small chips; on large glass it needs tight spacers (see section 4).

**Cost estimate (Estimate, Assumed panel cost per area).** If phase panels cost about the same per area as their mass-market twins plus 50–100% for the thin-gap and reflective steps:

- Card: area 0.0046 m², phone-class glass at about US$2,000–4,000/m² → US$10–20, plus extra steps → about **US$15–35 panel**, consistent with v6.
- TV: area 0.63 m², 8K-class glass at about US$300–600/m² → US$190–380, plus extra steps → about **US$300–700 panel**. That is lower than v6's US$400–1,200 because 1D encoding removes the need for 7.8 × 10⁷ fine pixels.

Cost is driven by yield on a new cell process, not by any physics limit. The fastest route is partnering with an existing LCD or LCoS maker rather than building a factory.

## 4. Bottleneck: large size

Large size adds three physics-based problems. Each has a derived tolerance:

1. **Cell-gap uniformity.** A thickness error δd changes the phase by 2πΔn δd/λ. Keeping the wavefront error below λ/10 at blue needs δd ≲ 0.11 µm (Δn 0.4) or 0.23 µm (Δn 0.2) (Derived). On a 0.8 µm gap that is about ±14%. LCD lines hold a few percent (from memory), so this is achievable. Any remaining error is fixed in software: measure each panel's phase map once and pre-correct every hologram (Established in SLM calibration).
2. **Flatness over 1 m.** Glass bow does not matter in itself. What matters is that the hologram reaching each eye is consistent across the panel, so the field lens and calibration map absorb slow shape errors (Derived; mirrors point 1).
3. **Driving speed.** Long gate lines on large glass are slow (RC delay). With 1D encoding there are 4,200 lines at 180 Hz, 1.3 µs per line, or 2.6 µs if the panel is split into two halves driven from both sides. Oxide (IGZO) TFTs drive 8K at 120 Hz with about 1.9 µs lines today (from memory), so this sits at the edge of current practice (Estimate).

Other large-size items that are engineering, not physics: a laser front light guide over 1 m² with uniform output, and speckle (several laser lines per colour, as in v6).

## Revised verdict for Route A

| Bottleneck | v6 status | v7 move | v7 status |
| --- | --- | --- | --- |
| Fast phase LC | 360 Hz needed, LC ~200 Hz | Reflective 0.8 µm, Δn ≈ 0.4; overdrive | ≈ 850 Hz achievable (Derived, Assumed constants) |
| Rate per viewer | 360 Hz | 1D encoding + lenticular eye split | 180 Hz |
| Pixels / line time | 1.4 × 10⁷ (card), 7.8 × 10⁷ (TV); sub-µs lines | 1D encoding, rolling scan, split drive | Phone-class (card), 8K-TV-class (TV) |
| Cost | US$40–95 card, US$800–2,100 TV | Reuse phone / 8K panel classes | Panel about US$15–35 card, US$300–700 TV (Estimate) |
| Large size | Unquantified | Gap tolerance and calibration map | ±14% gap tolerance; driving at the edge of 8K practice |

**New single most important open question.** Does a 1D (vertical-parallax-only) hologram plus a two-eye lenticular split give natural, comfortable focus? If yes, every Route A bottleneck has a known-process solution. If no, AETHER needs full 2D holograms, back at 360 Hz and sub-microsecond line times, where 0.8 µm reflective LC still solves the speed problem but the backplane does not yet.

## Next steps (no lab needed first)

1. **Software simulation, now with the 1D option:** compute a face hologram for the card in full 2D and in 1D encoding, then simulate what each eye sees when focused near and far. Compare blur at the wrong depth. This tests the open question numerically before any perception study.
2. **Materials check from published data:** high-Δn (≥ 0.35) nematic mixtures, their γ₁/K₁₁, UV stability, and reported thin-cell LCoS response times. This turns the Assumed constants into sourced ones.
3. **Prior-art and patent check** of SeeReal's 1D-encoding and lenticular patents, since move 2 is closest to their claims.
4. **Later, with a partner:** a small reflective 0.8 µm phase test cell (LCoS makers already build these) to measure the real response time.

**Values from memory to verify:** γ₁ and K₁₁ of display nematics, available Δn of stable mixtures, blue-phase and ferroelectric LC figures, phone and 8K panel pixel counts and line times, IGZO line-time capability, LCD cell-gap tolerance, panel cost per m², and SeeReal's 1D-encoding approach.
