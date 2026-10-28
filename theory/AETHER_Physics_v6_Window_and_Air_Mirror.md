# AETHER Physics v6: The Holographic Window and the Air Mirror

Oct 27, 2026 · @Ng Wei Bin

## Answer

**Route A, the holographic window, can be built with known physics.** A card needs about 1.4 × 10⁷ phase pixels at 18 µm. A TV-size window that shows a life-size person sitting behind it needs about 7.8 × 10⁷ pixels at 90 µm. Both pitches are already made in today's LCD factories. The hard part is not pixel size. It is a **fast phase-only liquid crystal**: at least 360 Hz per viewer for colour, where ordinary LC reaches about 200 Hz. Estimated parts cost is about US$40–95 for the card module and US$800–2,100 for a TV-size window.

**Route B, the air mirror, survives a stricter test and gains a big advantage, but it is not a consumer path.** If the viewer's card focuses its probe beam onto the point P, the air sends back a wave that truly spreads from P. Focus and parallax are then correct, and the return covers a card-sized patch that reaches both eyes. Keeping the probe eye-safe (Class 1) needs pump peaks of at least 2.4 × 10¹² W/cm² and about 6–60 W of visible femtosecond laser per colour. Those lasers would also cut a finger placed inside the image.

Follows [v5](https://claude.ai/artifact/2CoYAAxk7ZswRJAUMTrrEX) and the [dossier](https://claude.ai/artifact/DfRMqtK24b4WANEsgh26aV). Numbers: `aether_v6.py` → `results_v6.json` (project folder aether/v4). Labels: Established, Derived, Estimate, Assumed, Speculative; values marked "from memory" are not re-verified.

## Route A. How the holographic window works

The window is a stack of five thin layers plus a camera. Light leaves only toward the tracked pupils, so the whole image needs microwatts of laser light.

1. **RGB laser diodes at the edge** (Established). Red 635, green 532, blue 450 nm. They feed a flat light guide.
2. **Steerable backlight** (Estimate for the card version). A flat waveguide with a holographic out-coupler sends a converging beam toward the viewer. Switching between several laser input angles moves the converging point sideways. This steers the viewing window without moving parts. The card needs about ±23 cm of sideways range at 40 cm (±30°); a TV at 2 m needs about ±1.15 m.
3. **Phase-only liquid-crystal panel** (Derived pitch; Established technology class). Each pixel delays the light by 0–2π. The pitch is p = λd/w, set by blue light, the viewing distance d and a 10 mm viewing window w. For a full 2π at red, the LC layer is about 3.2 µm thick (birefringence 0.2). Pixels are 6–28× wider than the layer is thick, so neighbouring pixels do not smear into each other.
4. **Holographic field-lens film** (Established). A thin film acting as a lens of focal length about d. It turns the panel's light into a converging wave aimed at the eye.
5. **Eye-tracking camera** (Established). It finds both pupils every frame. The computer then shows each eye its own hologram in turn and moves the window onto that pupil.

**Why this is true holography, not a 3D screen.** The panel rebuilds the full light wave of the scene (phase and amplitude) inside the viewing window. The eye's own lens then focuses on the depth of each object, and moving within the window shows parallax. That is Theorems A, B and E of the dossier, now with real component choices.

**Why the other eye does not see a ghost.** The panel's pattern repeats in the viewer plane every λd/p = w = 10 mm. The other eye, 63 mm away, would sit in a repeated copy, so the two eyes are served one after the other in time (Established method).

## Route A. Numbers for three window sizes

The bigger the window and the farther the viewer, the coarser the pixels may be. A TV-size window at 2 m uses 90 µm pixels (282 ppi), as fine as a laptop screen and finer than any TV today, spread over a TV-sized panel (Estimate from memory of typical panel densities).

| Quantity | Card (85.6 × 54 mm, 0.4 m) | Desk (60 × 34 cm, 0.7 m) | TV (105 × 60 cm, 2 m) | Type |
| --- | --- | --- | --- | --- |
| Pixel pitch p = λ\_blue d/w | 18 µm (1,411 ppi) | 31.5 µm (806 ppi) | 90 µm (282 ppi) | Derived |
| Phase pixels | 1.4 × 10⁷ | 2.1 × 10⁸ | 7.8 × 10⁷ | Derived |
| Hologram compute (30 depth layers, 3 colours, 2 eyes, 60 Hz) | 3.7 × 10¹² op/s | 6.1 × 10¹³ op/s | 2.2 × 10¹³ op/s | Estimate |
| Data into the panel | 41 Gbit/s | 590 Gbit/s | 224 Gbit/s | Estimate |
| Steering range needed (±30°) | ±23 cm | ±40 cm | ±1.15 m | Derived |
| What you see | A small scene or a face, through a pocket window | A person from the waist up, at arm's length | A life-size person 1 m behind the glass, 29° wide view | Derived |

**Light needed (Estimate).** About 0.1 µW per eye reaches the retina. Allowing 50% panel, 50% film and 30% window-fill efficiency, each colour needs about 3 µW of laser per viewer. That is far below eye-safety limits and below a laser pointer by a factor of about 300.

**Viewers.** Each viewer needs 2 eyes × 3 colours × 60 Hz = 360 holograms per second if colours are shown one after another. A 720 Hz panel serves 2 viewers; a 1,440 Hz panel serves 4 (Derived).

**The life-size video call (the dream).** The TV-size window works like a real window into the other person's room: they sit about 1 m behind the glass at true size, with true depth and focus, and eye contact. The remote side needs a 3D capture of the person (several cameras plus AI reconstruction). Only the 3D scene is sent, not the hologram; the hologram is computed at the receiving end.

## Route A. Bottlenecks, cost and prior art

The single bottleneck that decides whether Route A becomes a product is a phase-only LC panel that switches at 360–1,440 Hz. Everything else is a known part or a known factory process.

| Bottleneck | Why | Known ways out | Status |
| --- | --- | --- | --- |
| Fast phase LC | Ordinary nematic LC switches in \~5 ms (\~200 Hz); one viewer needs 360 Hz | Blue-phase or ferroelectric LC; thinner high-birefringence LC; spatial colour (separate RGB pixels, 3× pixel count) | Engineering; the main research target |
| Steering backlight in 1–2 mm | Converging beam must follow the eye over ±30° | Multi-input waveguide with holographic out-coupler; laser array behind the field lens | Engineering |
| Speckle | Laser light makes grainy images | Several slightly different laser lines per colour; time averaging | Engineering, partial trade with depth range |
| Compute and data | 2–6 × 10¹³ op/s for desk or TV | Neural hologram methods; hologram computed on the display driver from compact 3D data | Within today's GPUs (Estimate) |
| Large high-ppi phase glass (desk, TV) | 282–806 ppi over 0.2–0.6 m² | Laptop-class LCD processes on large glass | Engineering, cost |

**Estimated parts cost (Estimate, not quotes).**

| Part | Card module | TV-size window |
| --- | --- | --- |
| Phase LC panel | US$15–40 | US$400–1,200 |
| Steering backlight and field-lens film | US$5–15 | US$80–200 |
| RGB laser diodes | US$6–15 | US$20–50 |
| Eye-tracking camera | US$2–5 | US$20 |
| Driver and compute | US$10–20 (phone does the rest) | US$300–600 |
| **Total** | **US$40–95** | **US$820–2,070** |

**Prior art (from memory, not re-verified).** Eye-tracked holographic windows: SeeReal Technologies. Holographic display start-ups: VividQ, Swave, Light Field Lab. Neural hologram computation: MIT "tensor holography" (2021). 3D video calls without holography: Google Project Starline (a light-field screen, not a hologram). AETHER's distinct combination, not yet checked for novelty: a card-size pocket window plus a home window, both true holograms, built around seeing family.

## Route B. The air mirror, refined

One new result makes the air mirror much better than v5 thought, and one makes it much harder.

**Better: correct focus comes for free (Derived).** A phase-conjugate mirror sends back the exact reverse of the incoming wave. If the probe from the viewer's card is focused onto P, the probe arrives as a wave converging onto P. Its reverse is a wave diverging from P, travelling back over the same cone to the card's aperture (shifted to eye height by the small pump tilt ε). So:

- The returned light truly spreads from P, so the eye focuses at P and sees correct parallax across the whole patch.
- The patch is the size of the card's aperture, 8.6 × 5.4 cm, wide enough for both eyes (63 mm apart) when the card is held near the face.
- The voxel is the probe's focus: about 2 µm at 0.5 m and 4 µm at 1 m, far sharper than needed. The pump beams only set the mirror strength.
- Each viewer sees only what their own card draws. The view is private, and shared pumps serve everyone.

**Mirror strength and probe safety (Derived; n₂ from memory).** R ≈ (4π n₂ I L/λ)² for 1 mm of air at 532 nm.

| Pump peak (W/cm²) | Mirror strength R | Probe needed for 0.1 µW per eye | Probe eye-safe (Class 1, ≤ 0.39 mW)? |
| --- | --- | --- | --- |
| 1 × 10¹² | 5.0 × 10⁻⁵ | 2.3 mW | No |
| 2.5 × 10¹² | 3.1 × 10⁻⁴ | 0.37 mW | Yes, just |
| 5 × 10¹² | 1.3 × 10⁻³ | 0.09 mW | Yes |
| 1 × 10¹³ | 5.0 × 10⁻³ | 0.02 mW | Yes, but at the edge of air breakdown |

So the probe is eye-safe only if the pumps run at 2.4 × 10¹² W/cm² or more, within a factor of 4–40 of breakdown.

**Harder: the pumps (Estimate).** Average power per pump colour at 2.5 × 10¹² W/cm², 50 µm focus, 60 Hz:

| Image points | 30 fs pulses | 100 fs pulses |
| --- | --- | --- |
| 10,000 | 1.8 W | 5.9 W |
| 100,000 | 18 W | 59 W |

Shorter pulses help in this table, but air's nonlinearity is about 3× weaker for 30 fs pulses (from memory), which cancels most of the gain. Realistic: about 6–60 W of visible femtosecond laser per colour.

**Safety problems (Established hazard classes; detailed exposure calculation not done).**

1. The pumps are Class 4. Their paths must be enclosed except where they cross the image, end in beam dumps, and switch off within milliseconds when the camera sees any face or hand entering a beam.
2. **A finger inside the image would sit in a femtosecond focus at about 10¹² W/cm², which is the tissue-ablation range** (from memory). Touch interaction must therefore blank the points near the finger, which works against touching the image.
3. Diffuse reflections of watt-level beams from walls can also be hazardous, so the beams must never hit open walls.

**Cost reality (Estimate, from memory).** Visible femtosecond lasers of 5–60 W cost on the order of US$50,000–200,000 today. Route B is a research and lab-demo path, not a product, unless such lasers become about 1,000× cheaper.

## Verdict and next steps

| Route | What the viewer sees | Physics | Engineering gap | Cost class | Verdict |
| --- | --- | --- | --- | --- | --- |
| A. Holographic window (card, desk, TV) | True hologram through a window; life-size family at TV size | Allowed (Derived) | Fast phase LC (360–1,440 Hz), steering backlight, speckle | US$40–95 card module; \~US$1–2k TV | **Main line: feasible after engineering** |
| B. Air mirror | A private point floating in open air with nothing behind it, correct focus | Not ruled out (Derived) | 6–60 W visible fs lasers per colour, Class 4 safety, no touching | Lab-only today | **Research line: long-term, unproven** |

**Route A next steps (no lab needed).**

1. Choose the LC: compare blue-phase, ferroelectric and thin high-birefringence nematic LC for 2π phase at 360+ Hz, from published data.
2. Design the steering backlight for the card: number of laser input angles, waveguide thickness and efficiency.
3. Speckle budget: how many laser lines per colour keep speckle invisible while preserving about 1 m of depth.
4. Simulation: compute a real hologram of a face on a laptop and show what each eye would see. This is software, so it can be built and shown without hardware.

**Route B next steps.**

1. A laser-safety exposure calculation for a room layout (pump paths, dumps, interlock reaction time).
2. A full four-wave-mixing model with focused beams and real femtosecond n₂.
3. First experiment, needing a partner lab: counter-propagating pumps plus a focused probe in open air; predicted return R ≈ 10⁻⁴–10⁻³ at 2.5–10 × 10¹² W/cm².

**Values from memory to verify:** air n₂ for 30 and 100 fs, LC switching times, panel densities, laser prices, tissue-ablation threshold, Class 1 limit (0.39 mW), and the prior-art companies named.
