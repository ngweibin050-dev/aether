# AETHER Decision Log

**How the project's direction was decided: every major discussion, the costs we looked at, what the founder rejected and why.**

Ng Wei Bin (founder) with Claude as research partner · 23–26 October 2026

This log is the "thought process" companion to the physics record (`theory/AETHER_Physics_Record.md`) and the references (`references/AETHER_References.md`). It is written in time order. Quotes from the founder are translated from Chinese. Every cost is an estimate unless stated otherwise.

---

## Summary: how we got here

| # | Date | Direction | Founder's verdict | Why |
| --- | --- | --- | --- | --- |
| 1 | 23 Oct | Derive the display physics from scratch, ignore existing projectors | Accepted as the method | "Like Newton before classical mechanics" |
| 2 | 23 Oct | AETHER-1: eye-tracked light-field card, BOM US$91–144 | Accepted, later superseded | Became charter v1.0/v1.1 |
| 3 | 24 Oct | Hackathon slice: AETHER Window software | Accepted | Buildable with a laptop, no cost |
| 4 | 24 Oct | Five-bottleneck physics attack (Theorems 4–5) | Accepted | Merged into charter v1.1 |
| 5 | 24 Oct | Compare with Looking Glass and Sony | Accepted | Laws confirmed; one new risk |
| 6 | 25 Oct | v2: card phone with one "reciprocal aperture" | Iterated v2.0 → v2.4, then **rejected** | "This is not holographic projection, it is a screen!" |
| 7 | 25 Oct | Ring + eyewear | **Rejected** | Misread: device is a bank card; "ring" was a size ratio |
| 8 | 25 Oct | AETHER Mist (photoswitch-dye mist) | **Rejected** | No chemicals sprayed into the air |
| 9 | 25 Oct | AETHER Column (pure-water mist + spinning mirror) | **Rejected** | "Do you think users and investors will accept spraying things into the air?" |
| 10 | 25 Oct | Transparent film aerial image / laser air plasma | **Both rejected** | "Don't give me Qing-dynasty ideas, give me something new" |
| 11 | 25 Oct | True holography from first principles (H1, H3, air emission) | **Accepted, current** | Matches the industry definition of true holography |
| 12 | 25 Oct | Submit a proposal (no prototype money) | Accepted | Founder cannot fund experiments or hardware |
| 13 | 26 Oct | Registration approved for the Meta hackathon | — | Build period 27 Oct 01:00 – 5 Nov 10:00 MYT |

---

## 23 October: defining the project and the method

**The ask.** The founder defined Project AETHER as a long-term R&D project: *a card-sized free-space volumetric display that shows 3D images floating in real space, controlled by the fingers, integrating display, interaction, computation and AI*. The brief explicitly said it is not a micro-projector, not a shrunken AR headset, and not just holographic software, and that the core breakthrough must come from the display itself. It laid out 15 sections and seven systems (A light sources, B micro-optics, C 3D display engine, D interaction, E electronics and power, F AI, G validation), and a research order: prove the display physics, then miniaturise, then add AI.

**The method the founder required.** "Reason from first principles like Newton before he wrote classical mechanics. Ignore existing projector approaches 0 %. Derive from pure physics and material properties; if a derivation fails, start again. Don't ask me questions until you have a correct answer."

**Feedback that shaped the work.**
- The founder objected to receiving a stage report: "Don't answer me; think the whole thing through and give me a plan that could be mass-produced." → From then on, deliverables are complete plans, not interim updates.
- "Follow the template I gave at the beginning; don't write your own six tasks." → Charters follow the founder's sections 1–15 and systems A–G.

**Result.** Stage-1 physics (Theorems 1–2, seven mechanisms ruled out) and charter v1.0 with AETHER-1: eye-tracked light field, ±25°, 2 viewers, 0–40 mm float, 9 mm thick, ~1.9 W.
**Cost at that point:** BOM US$91–144 at 100k units (later corrected to US$98–158).

---

## 24 October: hackathon, physics attack, competitors

**"Can this idea enter a hackathon?"** Yes, but not as the full card. Recommendation: a 24–48 h software slice where a laptop webcam tracks the eyes and renders per-eye views so objects float in front of the screen, plus hand gestures and AI voice commands. The founder agreed → **AETHER Window**.

**"Is the long-term version too many fields to conquer?"** Answer: the real blocker is one physics problem (an image in air needs light to hit something or come from a surface), not the number of fields; hand tracking, AI and chips already exist. Advice: do display physics first on a desk-size prototype. → The founder asked to "conquer the physics step by step, with existing or new principles" → stage 3 (Theorems 4–5, ±50° view, 63–82 mm float).

**"Can Looking Glass and Sony be controlled by fingers?"** Neither has built-in hand tracking (external Ultraleap only for Looking Glass; Sony documents none). The founder asked us to read their sites and notes → competitor study. All AETHER laws confirmed; new risk: AETHER-1 needs a fast (≤ 1.5 ms) LCD.

**Meta AI Developer Hackathon.** The founder found the event. Recommendation: join (free, remote, Malaysia eligible, Indie track, "Push the Frontier"). Must use Meta's models instead of Claude.
- The founder corrected the application: the "what will you build" answer should not read like the long-term plan, and the "recent AI project" answer should be **BizPilot** (an SME operations co-pilot built with WorkBuddy, 39 MCP tools).
- **"Which has more potential, BizPilot or AETHER?"** For the hackathon, AETHER (memorable, ambitious). As a business, BizPilot is closer to revenue. Suggested both tracks.
- **"Honestly, how big is my chance to win?"** Estimated ~1–2 % for a top prize, 5–15 % for any award if executed well. Two weaknesses: judges are remote (head-tracked 3D does not show on video) and Meta models must be central (→ SAM for real objects).
- **"Is building hardware realistic?"** The card in 10 days: no (custom OLED, aspheric microlenses, fast panel). A desk test rig with a lenticular sheet on a tablet: yes, RM50–200. The founder found a RM23 lenticular sheet (50 LPI, ~0.51 mm lenses) and was advised to buy two.

**Charter v1.1 (25 Oct, early).** The founder asked to merge stages 3–4 into the charter and re-check everything. Corrections: fast LCD mandatory, polarization recycling required, **BOM US$98–158**, battery 7–9 Wh (3.6–4.7 h), 9.1 mm stack, Gen-3 redefined.

---

## 25 October morning: the card phone (v2.0 → v2.4)

**The founder's seven points on charter v1.1** (paraphrased):
1. Remove the infrared cameras. Keep a single opening that projects 3D/2D. Work out hand detection yourself. Don't only send each eye its own rays; it should shine out so everyone in a meeting can see, with an optional private mode.
2. "You said the card must tilt 50°. I disagree. It should be visible from any angle as long as the opening isn't blocked."
3. AETHER should replace the phone, at bank-card thickness.
4. "Remove your power and cooling system; that's a phone's system, not AETHER's."
5. Audio and typing are missing.
6. Adjustable brightness.
7. Run Android, iOS and other OSes. "Jump out of your fixed architecture and think of an AETHER structure nobody has thought of."

**v2.0 answer:** the reciprocal aperture (emitters and photodiodes share each microlens; the display finds pupils by retinal retro-reflection and feels fingers on the same rays). Two things physics does not allow, stated plainly: a day of energy does not fit in a bank-card thickness (~0.4 Wh vs ~2.3 Wh/day), and a small hole cannot float an image (the aperture must be nearly the whole card). iOS is licensed only for Apple hardware.

| Round | Founder's message | What changed | Numbers |
| --- | --- | --- | --- |
| v2.1 | "Don't use a battery. Physics doesn't forbid it; you just haven't thought of other ways. Radio or something?" Large aperture OK "but improve it". "Drop iOS." | Battery removed; Theorem 9 (ambient power) written; power nodes; 10 J supercapacitor; bezel-less 84 × 52 mm aperture, double-sided option, multi-card tiling | Card 1.0 mm (Ω-2 0.71 mm); BOM US$259–477; retail est. US$799–1,199 |
| — | "Are you sure there is enough power??" | Honest answer: not sure. Without sun or nodes it certainly cannot light the display; power figures may be low | — |
| v2.2 | "Can't use these. I want a **reliable** energy plan." Options offered: 2 mm built-in battery / bank-card + charging sleeve / stay battery-free. Founder asked "how long does 0.4 Wh last?" (≈ 55 min of private display per day), then chose **"2 mm battery + energy sleeve"** | Battery back; sleeve 15 Wh | 2.8 Wh, ~1.2 days (×2 power → ~14 h); sleeve 4–5 mm, ~4 recharges; card BOM US$262–483 + sleeve US$17–32 |
| — | "Compared to phones on the market, which lasts longer?" | Honest: a phone lasts longer on its own (iPhone Air ~12 Wh, 5000 mAh Android ~19 Wh); with the sleeve AETHER can match or exceed | — |
| v2.3 | "Write this battery consideration into the charter." Then: "No, don't write what investors might ask. Write the battery." | Section E1′ "Runtime considerations" (facts only, no investor Q&A) | — |
| — | "Can everything squeeze into 2 mm?" | On paper with zero margin; likely 2.3–2.5 mm in a first sample. Chip layer 0.2 mm very aggressive | — |
| v2.3 | Chose "keep 2 mm, battery 1.0 mm (~2.3 Wh)". Asked: "Won't the battery die fast? Phone batteries die every few years." | Battery-life section E1″: ~1 cycle/day like a phone; sleeve-based shallow cycling | ~1 day (×2 → 12 h); 80 % after ~3–4 years; service-replaceable back module US$39–59 |
| — | "The cost looks higher than a phone." | Yes, flagship-level. Half the cost is the aperture module (2.7 × 10⁸ microLEDs on CMOS) | Card + sleeve US$280–515; retail est. US$799–1,199 |
| — | "No camera? Mic? Speaker?" | Speaker and mics yes (glass panel speaker, mics in a micro-slit at the aperture rim); camera only scan-grade (~0.2–0.3 MP). Suggested a camera in the sleeve | — |
| — | "The energy sleeve is a charger, not for taking photos." | Withdrawn. Rule recorded: the sleeve is only a charger | — |
| v2.4 | "I want two holes, front and back, same functions: project, photo, video." Offered 2.4 mm vs 2.0 mm; founder: **"Go straight to 3 mm, put the extra into the battery."** | Two identical apertures; in-window cameras; Theorem 10 (camera pixels ∝ thickness²) | 3.6 Wh, ~1.5 days (×2 → 18 h); ~3.7 MP, 1440p; BOM US$428–812 (later quoted 445–844); retail est. US$1,199–1,999 |

**Cost discussion after v2.4.**

| Question from the founder | Answer (estimates) |
| --- | --- |
| "So expensive I'd lose my pants. If I buy only raw materials, what does one AETHER cost?" | Raw materials < US$15. The money is in processing: silicon backplane ~US$130–180 even in your own fab (fab costs US$3–5 billion); microLED line ~US$1 billion; SoC and memory must be bought (US$55–85). Fully self-built ~US$270–400 per unit only at millions of units |
| "If only those three use the existing supply chain and I make the rest?" | ~US$400–765 per unit, only ~10 % cheaper; the three bought parts are 85–90 % of cost. Self-built lines ~US$20–40 million. Correction given: the charter BOM assumed 2029–30 prices; at today's prices the two apertures cost about double |
| "How much more expensive than phones?" | BOM: mid-range US$150–250, flagship US$450–500, foldable US$600–700; AETHER v2.4 US$445–844 (2029–30) or US$735–1,425 (today) → 1–1.7× a flagship (future) or 1.6–3× (today) |
| "Would a smaller aperture hurt image quality?" | Sharpness unchanged (set by 0.15 mm lens pitch), but the picture shrinks and float height scales with width: 84 × 52 → 36/21 mm at 30°/45°; 60 × 40 → 26/15 mm (cost ~55 %); 40 × 30 → 17/10 mm (~27 %) |
| "How big are 84 × 52 and 60 × 40 mm? I have no feel for it." | 84 × 52 is almost a whole bank card (~3.9″, like an iPhone 4 screen); 60 × 40 is a matchbox face (~2.8″) |

**Rejection.** "This is not what I want. I imagined ring size projecting near-human size. Find a new plan; you can refer to frontier tech but reason it yourself. Don't fool me with this set. **This is not holographic projection, it's a screen!!!**"

**Lesson:** a light-field aperture is physically honest but is experienced as a screen. The founder's goal is a large image in the room, not a 3D phone display.

---

## 25 October midday: a human-size image in the room

| Step | What was proposed | Founder's response | Lesson recorded |
| --- | --- | --- | --- |
| 1 | Ring-sized device: physics forbids a room-size image from a ring (2° keyhole, air does not glow, energy); best option ring + eyewear (decision card offered A eyewear / B room installation / C surface projection) | "?? Bank card bro! What eyes, what ring? That was a **ratio**, are you being silly?" | Device stays a bank card. Never propose glasses or rings |
| 2 | — | "I hope this plan cuts cost and gives the effect I wanted. Don't give me 'physics limits'; limits can be broken by new theory. Tell a Qing-dynasty person about phones and they'd say impossible. Reason seriously." | Frame walls as assumptions to break and experiments to run, stay honest |
| 3 | **AETHER Mist**: card + palm-size mist base with photoswitch dye; UV light sheet selects a layer; true 360°. Kit US$163–275 (about 1/3 of v2.4) | "Dye mist sprays things into the air?" → "Dye mist rejected, give me a new plan." | No chemicals in the air |
| 4 | **AETHER Column**: pure-water mist (like a humidifier), spinning-mirror projector, 24–36 views, 360°. Desk kit US$196–335 (30–50 cm figure); floor kit US$263–450 (1.2–1.7 m figure) | "Can't you understand? Do you think users and investors will buy spraying things into the air??" | **Hard rule: nothing may be released into the air, not even water** |
| 5 | Two options: transparent-film floating image (cheap, safe, image ≈ film size) or femtosecond laser air plasma (true mid-air, 360°, expensive, crackling) | "Neither. Stop giving me Qing-dynasty ideas, give me something new!!!" | No already-known techniques |
| 6 | Honest answer: no known fourth mechanism; offered a research-bounty spec instead of inventing one | Founder sent an article defining true holography (screen.com.hk): wavefront reconstruction; Pepper's ghost, film, mist, spinning mirrors and plasma are "pseudo-holography" | Our class-1/class-3 proposals were exactly the article's pseudo-holograms |
| 7 | Computational holography card (RGB lasers + phase SLM + eye tracking, SeeReal-like), stating honestly that a true hologram is a window | "Go back to physics. First principles. Conquer the theory first; plan AETHER only when it's feasible. You may create unprecedented theory, like Newton." | Physics first, no new charter until theory is feasible |

**Result (stage 7):** H1 Window Law, superoscillation closed, H3 scattering-focus law, light budget 113 lm, and the only open door: make air emit light under weak illumination. See the physics record §8.

---

## 25 October afternoon: from theory to a hackathon submission

| Founder's message | Decision |
| --- | --- |
| "I understand, but I can't do experiments…" | Computation first (T1, free), then university labs with the results; H3 bench test costs a few thousand dollars and can be done by a makerspace |
| "I asked because of the hackathon. Write all of this into a proposal; I'll submit that. I don't even have money for a prototype." | English proposal: vision + first-principles physics + discovery target + zero-cost AETHER Window built during the event with Meta models |
| "Build AETHER Window directly on my PC at C:\Aether." | Zero-install Windows build (`start.bat`) copied to `C:\Aether\aether-window` |
| "Which charter is the latest?" | No valid charter: v2.4 was rejected as a screen. Wrote **charter v3** (two tracks: product line now, research line for air emission) |
| "Write it into C:\Aether: proposal, references, theory folders. Detailed, professional and easy for investors." "Delete irrelevant files in those folders." | v3 HTML documents written; old light-field files listed for manual deletion (no delete permission) |

**Charter v3 numbers (estimates):** Phase 1b Holo Card BOM US$170–365, retail US$499–899; first funding ask US$110–270k (dev kit US$60–120k + research US$50–150k); Series A for the card US$0.5–1.5 M.

---

## 25 October evening: AETHER Window demo feedback

| Founder's feedback | What happened | Lesson |
| --- | --- | --- |
| "It works, but the hand feel is poor." | Round 1: depth from inter-pupil distance instead of iris size, smoothing, stable hand slots, debounced pinch, every-frame detection | — |
| Port error; "fingers must be very obvious to be detected"; wants the window-law demo | Port handled; pinch made more sensitive; **W key Window Law visualiser** added | — |
| "The camera reads my other fingers as thumb and index." → stricter rules → "**The feel got worse.**" → relaxed + debug view → "Still bad, redesign." | Tried MediaPipe GestureRecognizer with metric pinch thresholds | Don't tighten gesture thresholds blind; ask for diagnostics |
| "Your original version was better than all of these." | Reverted to the original gesture code; kept only the W demo and server fix | Don't retune gestures without specific feedback |
| Original gestures "OK, not best" | Generic AI layer (Meta / OpenAI / Anthropic config), photo capture, two-viewer split (T), EN/中文 (L) | — |
| Colour cut-out left holes in the face | Switched to MediaPipe InteractiveSegmenter | — |
| "No, I don't want a video, I want a 3D model of the object. Why make a stupid thing?" | Replaced view-dependent photos with a real mesh (visual hull) | Clarify "3D" means a mesh |
| "It must auto-recognise; if my hand holds the object, the model must not include my hand." | Object detection + hand masking | — |
| Real scan came out as a blob ("…") | Root cause: unknown per-frame angles. Added Meta **SAM 3D Objects** via Runware (~US$0.006 per model, needs the founder's key) | Browser-only multi-view scanning is not good enough |
| "Can I avoid Runware and just use SAM 3D?" | Running SAM 3D locally needs Linux + ≥ 32 GB NVIDIA GPU; options: Meta's event API (if provided) or Meta's free web demo + drag-in .glb | Pending: founder will share Llama API and SAM access once the event starts |

---

## 26 October

- Registration **approved** for the Meta Global AI Developer Hackathon (remote; build Tue 27 Oct 01:00 → Thu 5 Nov 10:00 MYT).
- The founder asked for complete English records of the proposal, theory and references, "so judges can see our thought process", including discussions, costs and every rejection with reasons (this document).

---

## Standing rules that came out of these decisions

1. The device is a **bank card** (85.6 × 54 mm). No rings, no glasses.
2. **Nothing may be released into the air**: no dye, no water mist, no fog, no particles.
3. **No already-known techniques** presented as the innovation ("no Qing-dynasty ideas").
4. Target is **true holography** (full wavefront reconstruction: natural focus, side views).
5. **Physics first**; product plans wait until the theory is feasible.
6. Do not stop at "impossible": name the hidden assumption, attack it, compute the cost, and stay honest about what is unproven.
7. The **energy sleeve is only a charger**.
8. Deliver complete documents, not interim reports; investor-facing documents state facts, not anticipated investor Q&A.
9. Budget reality: the founder cannot fund experiments or prototypes, so near-term work is computation, software and partnerships.
