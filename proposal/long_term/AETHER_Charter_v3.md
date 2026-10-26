# AETHER Charter v3

**Taking true holography out of the screen: a holographic display plan built from first principles**

Ng Wei Bin · 25 October 2026 · English edition of *AETHER 总纲 v3* (26 October 2026)

---

## 1. Executive summary

**What AETHER will do.** Our ultimate goal is a bank-card-sized device that projects a near-human-size **true hologram** into the middle of a room. Everyone in the room can see it without wearing anything, anyone can operate it directly with a finger, and nothing is sprayed into the air. This is the scene from *Iron Man*.

**Why nobody has done it.** Most products called "holograms" are reflection illusions, light-field screens or fog screens, not true holograms. Starting from the wave equation and the known Kirchhoff–Helmholtz integral, we derived a candidate constraint: **with passive optics alone, a true hologram behaves like a window** (Window constraint, H1). We also tried two workarounds that we have not seen applied this way before and calculated both to concrete numbers; under our assumptions both look impractical. These are candidate results that still need independent expert review. That leaves one door: **make the air at the image position emit light by itself.** Today, making air glow takes plasma-level intensity (about 10¹³ W/cm²). Our calculations show that neither the number of air molecules nor the total light intensity is the bottleneck. The bottleneck is an energy pathway that has not yet been discovered.

**Our strategy: two tracks.**

| Track | What | Time | Risk |
| --- | --- | --- | --- |
| **Product line** (buildable now) | Phase 0 AETHER Window software → Phase 1 window-scale true-hologram card | 0–36 months | Engineering risk, manageable |
| **Research line** (long-term prize) | Find a new mechanism that makes air glow locally under weak light | 2–10 years | High scientific risk, but success creates a whole new category |

The product line builds technical capability, users and revenue. If the research line succeeds, AETHER goes from "a better holographic display" to "the first device that can put an image into the air".

**What already exists:**

- A physics theory derived from first principles: Laws H1 and H3, a superoscillation analysis and an air-emission screening (see the theory folder).
- A working software demo, AETHER Window: a laptop and webcam give a head-tracked 3D window with gesture and voice control, at zero cost.
- A full technology and competitor survey (see the references folder).

## 2. Project definition

### 2.1 What "true holography" means

True holography uses the **interference and diffraction** of light to rebuild the entire light wave coming from an object. Therefore:

1. the eyes **focus** on the image exactly as on a real object;
2. changing the viewing angle reveals the object's **sides**;
3. no glasses are needed.

### 2.2 What is not true holography

| Name | Principle | Problem |
| --- | --- | --- |
| Pepper's ghost, holographic film | Angled glass or film reflects a screen | Flat image; needs glass |
| Light-field screens (Looking Glass, Sony) | Microlenses send different images in different directions | Simulated 3D; the eye cannot truly focus; the image stays in the screen |
| Fog screens, mist columns | Projection onto water mist in the air | Something must be sprayed into the air |
| Spinning mirrors or screens | A fast-rotating surface sweeps out a volume | Large mechanical structure |
| Laser plasma | Intense lasers light up points in the air | Noise and ozone, dangerous to eyes, expensive equipment |

### 2.3 AETHER's hard requirements

| Requirement | Content |
| --- | --- |
| Size | Bank card (85.6 × 54 mm) |
| Image | True hologram; final goal near human size |
| Viewing | Everyone in the room, nothing worn |
| Air | Nothing sprayed (no fog, particles or dye) |
| Interaction | Operate the image directly with a finger |
| Cost | Consumer level |

## 3. Physical foundations (investor version)

Full derivations are in *AETHER Physics Record* (theory folder). Here the four conclusions are explained with analogies.

### 3.1 Holographic Window Law H1: a true hologram is a window

**Analogy:** you see the scenery outside through a window. The scenery can be far away and huge, but you only see it through the window; look away from the window and there is nothing.

**Physics:** in empty air, all light in the room comes from the device. To see a point in the air, light must first converge through that point and then enter the eye, and that light can only have come from the device. So you can see the image only if the line "eye → image point", extended backwards, passes through the device.

**Numbers:** a card held at 40 cm forms a "window" of about 12° × 8°. An off-the-shelf holographic chip (3.7 µm pixels) steers light only about ±4°. The card's area can hold at most about 66 billion pixels.

**What this means for the product:** a card-sized true hologram can be built, but the image lives in the card's "window". Eye tracking that sends light only into the viewer's pupils cuts the required pixels by orders of magnitude (the method of SeeReal in Germany). This is the Phase 1 product.

### 3.2 Two new workarounds, both calculated

| Workaround | Idea | Result |
| --- | --- | --- |
| Superoscillation | "Forge" the direction of light inside the 4 mm pupil so the eye believes it comes from outside the window | Needs about 2,260 extra oscillation cycles; energy cost about e⁻²⁰⁰⁰; closed |
| The room as the hologram plate (Law H3) | Shine the laser on the walls with a computed wavefront so the scattered light converges in mid-room | Geometrically beats the window law, but focusing efficiency is at most N/N_tot; even at the card's theoretical limit only about 0.008 %, so a human-size image needs kilowatts of laser; closed |

We believe H3 is a new law that can be published in its own right as an academic result of AETHER (literature check pending).

### 3.3 The only open door: make the air emit light

H1 and H3 hold for every "linear, passive" medium, so the only way out is for the air at the image position to **create new light**. The air is already in the room; nothing needs to be added.

- **The known method** is laser plasma, needing about 10¹³ W/cm², with noise and ozone, and dangerous to eyes.
- **Our calculation found:** a human-size image needs only about 113 lm, so each air molecule on the image surface only has to emit once every 18 hours on average. A two-photon estimate puts the required peak intensity four to five orders of magnitude below the plasma threshold. **Neither the number of molecules nor the light intensity is the bottleneck.**
- **The real bottleneck:** nitrogen and oxygen lack an energy pathway that weak light can excite and that emits visible light.

### 3.4 Discovery target

> Find a mechanism that makes a chosen point in air emit visible light: local, weak-light (peak ≤ 10⁸–10⁹ W/cm²), visible (400–700 nm), eye-safe, with ≤ 100 W total for a human-size image.

The most promising lead is the **red light of the aurora**: nitrogen's "first positive band" emits red light and can be re-excited cyclically with near-infrared light, so one molecule can emit again and again. The difficulty is getting nitrogen molecules into the required starting state with weak, local light. See the theory record §8.4–8.6.

## 4. Technology roadmap

| Phase | Name | Content | Time (est.) | Key gate |
| --- | --- | --- | --- | --- |
| 0 | AETHER Window | Software: head-tracked 3D window, gestures, AI voice, any laptop | Now–3 months | Tracking accuracy on real users |
| 1a | Holography dev kit | Desktop true hologram: off-the-shelf phase chip + lasers + eye tracking | 6–12 months | A clear, focusable floating image |
| 1b | AETHER Holo Card | Bank-card-size window-scale true hologram | 18–36 months | Thickness, power, cost |
| 2 | Air-emission research | Computational screening → measurements with university labs | In parallel, 2–10 years | Emission threshold lowered by ≥ 10⁴× |
| 3 | Room-scale AETHER | Starts only if Phase 2 succeeds | — | — |

## 5. Phase 0: AETHER Window (software)

**What it is:** it turns any laptop screen into a "3D window". The webcam tracks the viewer's eye position and renders the scene for that position in real time, so objects appear to float in front of or behind the screen and stay fixed in space as the head turns.

**Features:**

- Head-tracked off-axis rendering (objects float up to about 4 cm in front of the screen);
- Gestures: pinch to rotate, pull two hands apart to explode, point to highlight;
- AI voice: for example "take the engine apart" or "what does the piston do?"; the AI turns speech into scene actions and explains aloud;
- Window Law visualiser (W): a real-size card window that shows H1 live;
- Real objects into 3D models (P), two viewers (T), English/Chinese (L);
- Demo scenes: engine, solar system, DNA.

**Status:** running now (`C:\Aether\aether-window`, double-click `start.bat`).

**Honest note:** this is a visual effect produced by per-eye rendering, not a true hologram. Its role is to validate the interaction model, build users and show the AETHER product experience.

**Uses and revenue:** education (3D courseware), museum and retail displays, developer SDK licensing.

## 6. Phase 1: window-scale true-hologram card

### 6.1 Principle

The card contains tiny red, green and blue lasers and a phase-modulator chip. The chip displays a computed hologram in real time, rebuilding the object's light wave in the air in front of the card. An eye-tracking camera finds the viewer's pupils, and beam-steering optics move the "viewing window" onto the pupils every frame. Therefore:

- the image is a **true hologram** the eye can genuinely focus on;
- the image can float out of the card surface and be touched with a finger;
- the viewer must look through the card (H1 Window Law).

### 6.2 Target specifications (estimates)

| Item | 1a dev kit | 1b card |
| --- | --- | --- |
| Size | Desktop box | 85.6 × 54 mm; thickness target ≤ 10 mm, long term 5 mm |
| Holographic chip | Off-the-shelf 4K phase chip (3.7 µm) | Custom chip, target ≤ 2 µm |
| Native steering range | ±4.1° | ±7.6° (2 µm) |
| Usable range with eye tracking | ±20°–30° | ±20°–30° |
| Simultaneous viewers | 1 | 1–2 |
| Float distance | A few cm (to be measured) | A few cm (to be measured) |
| Finger interaction | Near-infrared camera | Near-infrared on the same optical path |
| Power | Mains | About 1.5–3 W |

### 6.3 Card bill of materials (volume, estimates)

| Part | Cost (US$, est.) |
| --- | --- |
| Phase-modulator chip | 40–120 |
| RGB lasers | 15–40 |
| Beam-steering optics | 20–50 |
| Eye-tracking camera | 10–20 |
| Processor and memory | 55–85 |
| Battery, power, housing, assembly | 30–50 |
| **Total** | **170–365** |

Estimated retail price US$499–899. Phase-chip and steering-optics prices need supplier quotes.

## 7. Phase 2: air-emission research

**Why it is worth funding:** it is the only physical route to a room-scale true hologram. Whoever finds the mechanism first owns the foundational patents of the whole category.

**How (no own lab needed):**

| Step | Content | Cost |
| --- | --- | --- |
| T1 computational screening | Use published data to compute emission yield and required intensity for each research line; eliminate impossible directions | 0 |
| T2 H3 verification | Verify the scattering-focus law in a 30 cm white box; publishable | US$2,000–5,000 |
| T3 measurement | Partner with a university ultrafast-laser lab to measure the promising directions | Partnership or research grant |

**Success criterion:** on a desktop, make a point in air emit visible light at a peak intensity ≥ 10⁴× below plasma, with eye-safe illumination.

## 8. Competitive landscape

| Competitor | Type | Price | AETHER's difference |
| --- | --- | --- | --- |
| Looking Glass Go | Light-field screen | US$299 | AETHER Phase 1 is a true, focusable hologram; built-in finger interaction |
| Sony Spatial Reality Display | Eye-tracked light-field screen | US$4,999 (SR1) | Same; bank-card size |
| SeeReal | Eye-tracked computational holography | Licensing | AETHER brings card size plus interaction, and has a long-term research line |
| Fog screens, spinning mirrors, plasma | Volumetric displays | Custom projects | AETHER adds nothing to the air and has no mechanical structure |

**Market interest:** GM Insights estimates the holographic display market at about US$4.3 billion in 2025 and about US$40.8 billion in 2035 (CAGR about 25.5 %). This figure includes many "pseudo-holographic" products and is a reference only.

## 9. Business model

1. **Software (Phase 0):** education and display licences, developer SDK.
2. **Dev kit (Phase 1a):** sold to research institutions, design studios and developers.
3. **Consumer product (Phase 1b):** AETHER Holo Card.
4. **Intellectual property (Phase 2):** papers and patents on Law H3 and the air-emission mechanism, plus licensing.

## 10. Funding needs (estimates)

| Phase | Use | Amount (US$) |
| --- | --- | --- |
| 0 | Cloud services, AI APIs, demo equipment | 0–5,000 |
| 1a | Phase-chip dev kit, lasers, optics; 1–2 part-time engineers for 12 months | 60,000–120,000 |
| 2 | T2 experiment; research funding with universities (government and university grants possible) | 50,000–150,000 |
| 1b | Card prototype, custom optics, engineering team | 500,000–1,500,000 (Series A) |

The first funding target is 1a plus 2, about US$110–270k in total, delivering within 12 months a "desktop true-hologram demo + H3 paper + air-emission computation report".

## 11. Milestones

| Time | Milestone |
| --- | --- |
| Month 0–1 | AETHER Window completed at the hackathon with AI models connected |
| Month 3 | T1 computational screening report; H3 paper draft |
| Month 6 | 1a dev kit shows its first focusable floating image |
| Month 12 | 1a adds eye tracking and finger interaction; T2 experiment complete |
| Month 18–36 | 1b card prototype |
| Ongoing | T3 experimental partnership; if the air-emission threshold breaks through, start Phase 3 |

## 12. Risks and responses

| Risk | Likelihood | Response |
| --- | --- | --- |
| No air-emission mechanism is found | High | The product line does not depend on it; research funding is staged and screened by computation first |
| Card cannot be made thinner than 10 mm | Medium | Start with a desktop version and a phone accessory; develop thin laser-backlight waveguides |
| Phase-chip cost is high | Medium | Volume negotiation; eye tracking reduces pixel needs |
| Eye-tracking accuracy is insufficient | Medium | Measure on real users in Phase 0 first |
| Laser safety | Low–medium | Design power and optical path to laser-product safety standards |
| Being mistaken for "pseudo-holography" | Medium | Always distinguish Phase 0 (visual effect) from Phase 1 (true hologram) in public |

## 13. Directions we rejected (evidence that we compared seriously)

| Version | Plan | Reason for rejection |
| --- | --- | --- |
| v1 | Microlens light-field screen (AETHER-1) | Essentially a screen, not a hologram |
| v2.4 | 3 mm bank-card phone with front and back light-field apertures | Same; BOM US$445–844, too expensive |
| Mist | Photoswitch-dye mist | Sprays chemicals into the air; unsafe; not acceptable |
| Column | Pure-water mist column + spinning-mirror multiview | Still sprays something into the air; existing technology |
| Film, plasma | Transparent-film floating image; air plasma | The first needs a film; the second is expensive, dangerous and noisy |

None of this was wasted: same-ray finger sensing, AI scene commands and eye-tracked rendering all carried into the current route. The full reasoning and numbers for each are in `proposal/AETHER_Decision_Log.md` and `theory/AETHER_Physics_Record.md`.

## 14. Team

**Ng Wei Bin**, independent developer in Malaysia, project founder. Previous AI project: [BizPilot](https://github.com/ngweibin050-dev/BizPilot), an operations assistant for Malaysian SMEs with 39 tools, approval levels and automation.

**Planned hires:** an optical engineer (holography and lasers), a computational holography algorithm engineer, and a university physics adviser (ultrafast lasers and molecular spectroscopy).

## 15. Final recommendations

1. **Now:** enter the hackathon with AETHER Window, showing the interaction experience and the physics theory.
2. **Within 3 months:** complete T1 computational screening and the H3 paper to build academic credibility.
3. **Raise a first US$110–270k:** build the desktop true-hologram dev kit and start the air-emission research partnership.
4. **Communication principle:** always distinguish honestly between "the window-scale true hologram we can build now" and "the room-scale hologram that needs a new discovery". That honesty is AETHER's biggest difference from the "pseudo-holograms" on the market.

## Appendix: file index

| Folder | File | Contents |
| --- | --- | --- |
| proposal/long_term | AETHER_Charter_v3.md (this file), AETHER_总纲_v3.html (Chinese) | Long-term charter |
| proposal | AETHER_Decision_Log.md | Every discussion, cost and rejection, in time order |
| proposal/hackathon_ready | AETHER_Hackathon_Proposal.md / .html, AETHER_Demo_Script.md, AETHER_报名表.md | Hackathon submission materials |
| theory | AETHER_Physics_Record.md, simulations/ | All derivations, simulations and figures |
| references | AETHER_References.md | Competitors, papers and tools with links |
| aether-window | start.bat | Software demo |
