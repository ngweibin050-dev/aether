# AETHER Physics v5: Can Air Itself Light Up?

Oct 27, 2026 · @Ng Wei Bin

Follow-up to the [AETHER Theoretical Dossier](https://claude.ai/artifact/DfRMqtK24b4WANEsgh26aV): this is the "next derivation" it named.

## Answer

The ordinary way (air absorbs light, then glows) is closed: every visible-emitting channel in ambient air needs at least 1.3 × 10¹⁴ W/cm², which is the air-breakdown (plasma) regime. That explains why every published mid-air display uses plasma. One door is still open, and it is a different kind of physics: air can act as a **phase-conjugate mirror** at a chosen point (degenerate four-wave mixing). This needs no energy level in N₂ or O₂, works at 10¹² W/cm² (about 10–30× below breakdown), and only needs microwatts of light into each eye. It is not proven to work as a display.

- **Closed (Derived, with one Assumed scaling rule):** absorption-then-emission channels, single photon to 24 photons, at any eye-safe wavelength.
- **Closed for a single card alone (Derived, Theorem H):** coherent processes driven from one card emit forward, inside about twice the card's cone, toward where the pump beams also go.
- **Open (Speculative architecture, Derived budget):** pumps crossing the image from two opposite sides (an emitter plus a side reflector, both outside the image space), plus a weak probe beam from near each viewer, for example the viewer's own card. The light returns from the point in the air to that viewer.

Numbers: `aether_air_channels_v5.py` → `results_v5.json` (project folder aether/v4). Labels: Established, Derived, Estimate, Assumed, Speculative.

## Step 1. Theorem G for any number of photons

For an n-photon process the visible photon rate from a focused Gaussian pump, with voxel depth δ\_z and peak intensity I, is (Derived):

```latex
S = \frac{\eta\, n_{air}\, \sigma_n\, c_n\, \delta_z\, P_{avg}\, I^{\,n-1}}{2n\,(h\nu)^n}, \qquad c_n = \int_{-\infty}^{\infty}\frac{dx}{(1+x^2)^{n-1}} = \frac{\sqrt{\pi}\,\Gamma(n-\tfrac32)}{\Gamma(n-1)}
```

Derivation in one line: the beam cross-section integral of I^n is (2P/πw²)^n·πw²/(2n); the axial integral gives z\_R·c\_n; then fix w₀² = λδ\_z/2π and P\_pk = Iπw₀²/2. For n = 2, c₂ = π and the formula reduces exactly to Theorem G of the dossier (the script re-derives 0.39 GM for 1550 nm, 10 W, 10¹¹ W/cm²).

**Cross-sections (Assumed scaling rule, then checked).** Without resonances, σ\_n ≈ s^n τ^{n−1}, with an allowed-transition size s ≈ 10⁻¹⁷ cm² and a virtual-state lifetime τ ≈ 10⁻¹⁶ s. This gives 1 GM for n = 2, which matches typical molecules.

**Check against a known fact.** The same rule predicts that O₂ (ionisation 12.07 eV, so 8 photons at 800 nm) has a 69% chance of ionising in a 100 fs pulse at 10¹⁴ W/cm². Measured air ionisation by femtosecond pulses does set in around 10¹³–10¹⁴ W/cm². The rule therefore reproduces the known breakdown threshold without tuning, so its predictions below can be trusted to within about an order of magnitude in intensity.

## Step 2. Every light-emitting channel in air, screened

Every channel that makes ambient air absorb light and re-emit visible light needs at least 1.3 × 10¹⁴ W/cm², at or above the point where air ionises. So any such display is a plasma display. Settings: 113 lm image, 10 W average pump, 1 mm voxel; the lowest required intensity over 800, 1064 and 1550 nm pumps is shown.

| Visible light source in air | Energy to reach | Photons needed | Visible yield η (Estimate, from memory) | Lowest required intensity (W/cm²) | Why |
| --- | --- | --- | --- | --- | --- |
| N₂⁺ ion, 391/428 nm (violet-blue) | 18.7 eV | 13–24 | \~10⁻² | 1.3 × 10¹⁴ (1550 nm) | Needs ionisation first: this is the plasma route |
| O atom, 557.7 nm (aurora green) | 9.3 eV (break O₂ and excite) | 7–12 | \~10⁻⁶ (quenched by collisions) | 3.0 × 10¹⁴ (1550 nm) | Dissociation plus collisional quenching |
| N₂ first positive, 580–1000 nm (aurora red) | 7.35 eV | 5–10 | \~10⁻⁸ (spin-forbidden, quenched) | 5.8 × 10¹⁴ (1550 nm) | Triplet state cannot be reached by light directly |
| O₂ b-state, 762 nm (deep red) | 1.63 eV | 2–3 | \~10⁻⁹ (spin-forbidden, eye barely sees 762 nm) | 1.6 × 10¹⁷ (1550 nm) | Forbidden and almost invisible |
| H₂O, CO₂, Ar | 7–11.5 eV | 6+ | 0 visible | n/a | Emit ultraviolet (OH at 309 nm) or need ionisation |

**Can resonances or pulse shaping rescue it?** A real intermediate state on the way up would help, but N₂ and O₂ have no allowed, long-lived state below about 6 eV. The one allowed state there (O₂ B, 6.1 eV) falls apart within picoseconds. Pulse shaping (coherent control) gains about 10–100× in rate; because rate scales as I^n, that lowers the required intensity by only (100)^{1/(n−1)}, about 1.5–2× for n ≥ 7. Not enough.

**Result (Derived, under the Assumed scaling rule):** the incoherent door is closed. Light in, light out through the air's own energy levels means plasma.

## Step 3. The coherent loophole and the momentum-cone theorem

There is a second way air can make new light at a point, and it needs no energy levels at all: light mixing with light through air's tiny nonlinearity (n₂ ≈ 3 × 10⁻¹⁹ cm²/W, from memory). Step 2 does not apply to it. What controls it instead is momentum conservation.

**Rules (Established).** In third-order mixing, ω\_s = ω₁ + ω₂ − ω₃ and the output must satisfy k\_s = k₁ + k₂ − k₃ (phase matching). Air has almost no dispersion, so |k| = ω/c for every beam.

- **Sum processes (third harmonic, ω + ω + ω):** |k₁ + k₂ + k₃| equals the sum of magnitudes only for collinear beams, and the Gouy phase of a focus cancels the net third harmonic from a focus inside a uniform medium (textbook result, Boyd). No voxel. Closed.
- **Degenerate four-wave mixing (all four frequencies equal):** with K = k₁ + k₂, the output lies on a cone around K with half-angle α, where cos α = |K|/(2k).

**Theorem H, momentum cone (Derived here).** If every input beam comes from one card, all wave vectors lie within the card's half-angle β seen from P. Then |K| ≥ 2k cos β, so α ≤ β, and K itself lies within β of the axis. The output therefore leaves P within 2β of the card axis, heading away from the card.

| Image distance from card | Theorem A cone β | Theorem H cone 2β |
| --- | --- | --- |
| 0.3 m | 8.1° | 16.2° |
| 1.0 m | 2.5° | 4.9° |

Coherent mixing driven from one card can at most double the window, and the strong pump beams travel toward the same viewers, which is an eye hazard. **For a single card alone, the door is closed.**

**The escape (Derived).** Make K ≈ 0 by sending two pump beams through P from opposite sides. Then α = 90° and the output is k\_s = −k₃: exact phase conjugation. A weak probe beam arriving from any direction is sent straight back along its own path. Tilting the pumps by a small angle ε shifts the returned beam by about ε, so a probe sent from a card held about 10 cm below someone's eyes can be returned into the eyes from 1 m away (ε ≈ 0.1 rad). The returned light really leaves the point P in the air, so the viewer sees P with nothing behind it.

This is the only mechanism found in this pass that is not ruled out by Theorems A, F, G or H.

## Step 4. The surviving design: air as a phase-conjugate mirror

The energy works out because of eye tracking: the image only has to send about 0.1 µW into each pupil, so a mirror-strength of 10⁻⁵ is enough. Safety and stray light are the real problems.

**Layout (Speculative).** Two pump beams of the same colour meet head-on at the voxel P. They come from an emitter on one side of the image space and a reflector or second emitter on the other, both outside the image space. The viewer's own card sends a weak probe pulse at P. P returns it to that viewer's eyes. The pump foci scan through the image voxel by voxel. Nothing is added to the air.

| Quantity | Formula or source | Value | Type |
| --- | --- | --- | --- |
| Mirror strength of 1 mm of air | R ≈ (4π n₂ I L/λ)² | 5 × 10⁻⁷ at 10¹¹; 5 × 10⁻⁵ at 10¹²; 5 × 10⁻³ at 10¹³ W/cm² | Derived (n₂ from memory) |
| Light needed into one eye | Theorem D | \~0.1 µW | Estimate |
| Probe power from the viewer's card | 0.1 µW / R at 10¹² W/cm² | \~2.3 mW average | Estimate |
| Peak power per pump (50 µm focus) | I πw₀²/2 | 3.9 × 10⁷ W | Derived |
| Average power per pump, 10⁵ voxels at 60 Hz, 100 fs pulses | peak × duty (6 × 10⁻⁷) | \~23 W (2.3 W for 10⁴ voxels) | Estimate |
| Stray glow along each pump beam (Rayleigh) | Theorem F | \~30% of one voxel's brightness per voxel length: faint visible lines | Estimate |
| Largest voxel that still gives correct focus at 1 m | δ ≲ 2√(λd/π) | \~0.8 mm | Derived |
| Colour | Output colour = pump colour | Needs red, green and blue pump sets | Established |

**What breaks first (ranked).**

1. **Eye safety.** Watt-level visible femtosecond pumps are Class 4 lasers. They must run in paths that never cross where eyes can be and end in beam dumps. The probe (milliwatts) also continues past P and must be dumped. Not yet computed against the safety standard.
2. **Stray beam lines.** Pump light scatters off air along its whole path at roughly a third of voxel brightness. Contrast may be acceptable; this needs a perception check.
3. **Scan rate.** 10⁵ voxels at 60 Hz needs megahertz pulse trains at tens of watts. Fewer voxels or many foci at once (a phase SLM in the pump) reduces this.
4. **Single-card form factor.** This design needs pumps from two opposite sides, so it is a card plus a frame or base around the image space, not a card alone. Theorem H says a lone card cannot do it.

**Prior art (from memory, not re-verified).** Phase conjugation by degenerate four-wave mixing is textbook (Hellwarth, Yariv and Pepper, 1977), and four-wave mixing in air and flames is used for gas diagnostics. Using air as a scanned phase-conjugate mirror for a display is not known to me; novelty is unverified.

## Verdict and next calculation

| Route to making air light up | Verdict | Deciding result |
| --- | --- | --- |
| Air absorbs, then glows (any number of photons, any eye-safe wavelength) | Incompatible with established physics below breakdown | Steps 1–2: ≥ 1.3 × 10¹⁴ W/cm² |
| Coherent light mixing driven by one card alone | Incompatible: stays inside a 2β forward cone | Theorem H |
| Air as a scanned phase-conjugate mirror, pumps from two sides, probe from each viewer | Not ruled out; energy feasible; safety, stray light and scan rate unresolved | Step 4 |

**The single most important open question has changed.** It is no longer "is there a hidden energy level in air?" (answer: no). It is now: can a scanned phase-conjugate voxel in air reach R ≥ 10⁻⁵ at sub-millimetre size, with every laser beam kept eye-safe in a room where people move?

**Next calculation (no lab needed).** A full model of degenerate four-wave mixing with focused Gaussian beams in air: actual χ⁽³⁾ of air for femtosecond and picosecond pulses, Gouy phase, overlap volume, voxel size versus focus cue, plus a laser-safety exposure calculation for the room layout.

**First decisive experiment (needs a partner lab with a femtosecond amplifier, Estimate).** Two counter-propagating 800 nm pumps plus a probe in open air. The prediction is a phase-conjugate return of R ≈ 10⁻⁵ to 10⁻³ at 10¹² to 10¹³ W/cm² from a millimetre region. A measured return at that level would show "air as a mirror at a chosen point" directly.

**Values from memory to verify:** n₂ of air, CIE V(λ) values, N₂/O₂ state energies and quenching rates, femtosecond breakdown thresholds, and the 1977 phase-conjugation references.
