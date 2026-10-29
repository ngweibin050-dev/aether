# AETHER — An AI Lab for Designing Real Holograms

**Meta AI Builders Hackathon 2026**
**Builder:** Ng Wei Bin (solo)
**Track:** Indie Developer (judged on creativity, technical ambition, and whether it works)
**Theme:** Push the Frontier

---

## Hackathon facts (for my own checklist)

| Item | Detail |
|---|---|
| Build window | Oct 26 – Nov 4, 2026. Submission and credit claim close **Nov 5, 10:00 MYT** (Nov 4, 9 PM EST). |
| Must submit | Platform entry + **3-minute demo video** + **public GitHub repo** |
| New work only | Everything shown is built during the event, in a **new repo** created after Oct 26. Earlier AETHER research is shown only as background and labeled "pre-event". |
| Rubric | Impact 30% · Use of Meta AI tooling 25% · Technical depth 20% · Demo 25% |
| Not allowed | Medical advice, simple image analyzers, dashboard-as-product, job screeners, personality analyzers, basic RAG, Streamlit apps, "AI for education" chatbots, nutrition coaches, sports coaches. AETHER is none of these. |
| Tools I have | Meta Model API ($150 credit), Baseten ($100), Modal ($100) |

---

## 1. One-line pitch

**Tell AETHER what 3D object you want to show. It calculates a real hologram for it, shows you what your eye would see at each depth, and tells you if the display you are designing can actually show it.**

---

## 2. The problem (plain words)

A normal 3D model on a screen is a picture. A **hologram** is different: it is a pattern that bends light so the light coming out looks exactly as if the object were really there. Your eye can focus on near and far parts, the way it does with real objects.

Many companies and labs are trying to build holographic displays for 3D design, medicine and work without headsets. To design one, an engineer has to answer questions like:

- "If my pixels are this big, will the object still look sharp?"
- "How far in front of the screen can the object float before it goes blurry?"
- "Will the image look grainy (speckle)?"

Today this means writing physics code by hand and running it again for every change. It is slow, it needs an optics expert, and it is hard to connect "the 3D object I want" with "the light my display must make".

**I hit this problem myself.** For the past week I have been designing AETHER, a no-headset holographic work desk. Every design question took me a new hand-written simulation (pre-event research, v4–v13). AETHER Lab is the tool I wish I had.

---

## 3. Who benefits

1. **Holographic display engineers and researchers.** They can try a design idea in minutes instead of days.
2. **Students and makers.** They can calculate a hologram, print it on film, and see it with a cheap laser pointer.
3. **Long term: everyone who works in 3D.** Better holographic displays mean designers, surgeons and engineers can see 3D models with true depth, without wearing a headset.

---

## 4. What AETHER does — 4 features

### Feature 1 — Talk to the 3D scene (must build)
The user types or speaks: *"Put a gear 8 cm in front of the screen and tilt it 30 degrees."*
Muse Spark turns this into exact tool calls. The 3D scene (Three.js) updates. The scene is the real input to the physics, not just a picture.

### Feature 2 — Calculate the hologram (must build)
AETHER turns the 3D object into thousands of tiny light points, adds up the light wave from every point, and produces the **hologram pattern**: the exact pattern a display panel would need to show.
Method: point-source computer-generated hologram (a standard, published method), encoded as a phase pattern.

### Feature 3 — See what the eye would see (must build)
AETHER sends the light from the hologram forward through space using wave physics (the angular spectrum method) and shows the **reconstruction**: the image that would appear.
The user can **sweep the focus**: near parts become sharp while far parts blur, just like a real object. This is the thing a normal 3D screen cannot do, and it is the clearest way to show judges what a hologram really is.

### Feature 4 — "Can my display show this?" check (must build, limited)
AETHER includes a ready-made design preset: **AETHER Desk**, the holographic work desk from my pre-event physics study. The user asks:

> *"Can AETHER Desk show this gear 10 cm in front of the screen, sharp enough to design with?"*

The Muse Spark agent runs the calculation at several heights, reads the results, and answers with numbers, for example: "sharp up to about X cm, then it blurs; the limit comes from the pixel size". The agent can also **search** for an answer: *"Find the biggest pixel size that keeps this gear sharp at 10 cm"* makes it run several calculations and report the best one.

### Feature 5 — Real-light check with a printed hologram (stretch, about RM50)
AETHER exports a printable hologram. I print it on transparent film and shine a low-power (Class 2, below 1 mW) laser pointer through it onto a wall. A phone photo of the wall goes back into AETHER, **SAM 3.1** cuts out the light pattern from the photo, and AETHER places it next to its own prediction.
This proves the calculation controls real light. It does **not** prove the AETHER Desk itself works; that would need a real display panel.

---

## 5. How Meta AI is used (25%)

Meta's models are the brain that runs the lab. They do not do the physics math; the physics code does that, so no number is made up.

| Meta model | What it does in AETHER |
|---|---|
| **Muse Spark 1.3** (core) | An agent with tools. It plans multi-step experiments, calls the tools with checked arguments, reads the computed results, and explains them. |
| **Muse Voice Transcribe** | Hands-free commands: "move it closer", "focus on the back tooth". |
| **SAM 3.1** (stretch) | Finds and cuts out the laser image in a phone photo so it can be compared with the prediction. |

**Agent tools (what Muse Spark can call):**
`set_scene` · `move_object` · `set_display` (pixel size, wavelength, panel preset) · `make_hologram` · `propagate` (to a chosen depth) · `focus_sweep` · `measure_sharpness` · `measure_speckle` · `compare_photo` · `explain_result`

**Why this is more than a basic integration:**
- The model drives a real physics pipeline, step by step.
- It can run its own small experiments (a parameter search) to answer a design question.
- Every number in its answer comes from a tool result, and the app shows that number on screen.

---

## 6. Technology

| Part | Tool | Job |
|---|---|---|
| Web app | Three.js + plain JavaScript | 3D scene, chat/voice box, hologram and reconstruction views |
| Physics engine | Python + NumPy (written new during the event) | Point sampling, hologram calculation, wave propagation, sharpness and speckle numbers |
| Heavy calculations (core) | **Modal** (GPU) | The main physics engine: full-size holograms, focus sweeps, and the agent's parameter search (many calculations run in parallel). A small version also runs locally, so the demo still works if Modal is slow. |
| Spoken answers (optional) | **Baseten** text-to-speech | Reads the explanation aloud |
| AI | Meta Model API | Muse Spark, Muse Voice Transcribe, SAM 3.1 |

**Simple test cases (to prove the physics engine is right):**
1. A single light point must focus back to a single point at the right distance.
2. Two points at different depths: each is sharp only at its own depth.
3. Halving the pixel size must double how far the light can bend (a known physics law).

These tests run in the repo, and the results are shown in the README.

---

## 7. The physics, honestly

**What is calculated during the hackathon:** real wave-optics simulation with established methods. These are trustworthy calculations, but they are still a computer model, not a measurement.

**Background from my pre-event research (simulation only, nothing built):**
- AETHER Desk is a no-headset holographic desk. A camera follows the user's eyes, and the panel sends correct light only to where the eyes are.
- With today's liquid-crystal panels, my model says an object stays sharp and naturally focusable within about **±10 cm of the screen**, keeping 78–90% of full sharpness.
- Floating the object higher (about 25 cm, like in the films) needs light-modulating panels that refresh about 1,600 times per second (kHz class). Panels that fast do not exist yet at desk size.
- The image is for 1–2 people at a time, because of speckle (grainy light) limits.
- If a hand goes **behind** a holographic object, it blocks that object's light. So AETHER's design: hands work from the front and the sides.

**What is NOT claimed:** no physical holographic display has been built. The hackathon delivers the design tool, and optionally a printed-film test with real laser light.

---

## 8. 3-minute demo video plan

| Time | What the judges see |
|---|---|
| 0:00–0:20 | The problem: a flat 3D model versus a real object your eye can focus on. "A hologram has to make the light itself." |
| 0:20–0:50 | Voice: "Put a gear 8 cm in front of the screen and tilt it 30 degrees." The scene updates and the hologram pattern is calculated. |
| 0:50–1:30 | **Focus sweep:** front teeth sharp, then back teeth sharp. "This is what your eye would see." |
| 1:30–2:15 | "Can AETHER Desk show this at 10 cm?" The agent runs calculations, shows a sharpness graph, and answers with numbers. Then: "Find the biggest pixel size that still works." |
| 2:15–2:40 | (Stretch) The printed film and a laser on the wall, next to AETHER's prediction. |
| 2:40–3:00 | The vision: from a design tool today to a no-headset holographic workspace. What is proven, and what is next. |

---

## 9. Scope

**Must build:** 3D scene + Muse Spark tool calling · hologram calculation · wave propagation + focus sweep · AETHER Desk check with numbers · physics test cases · public repo + video.

**If time allows:** voice input · printed-film laser test + SAM 3.1 photo compare · spoken answers via Baseten · more objects.

**Out of scope:** a physical holographic display · photo-to-3D of any object · claiming my theory is experimentally proven.

---

## 10. Build plan (7 days)

| Date | Work |
|---|---|
| Oct 28–29 | New repo. Python physics engine + 3 test cases. |
| Oct 30–31 | Web app: Three.js scene, hologram and reconstruction views, focus sweep. Physics on Modal plus a local fallback. |
| Nov 1 | Muse Spark agent with all tools; AETHER Desk preset. |
| Nov 2 | "Can my display show this?" and the parameter search. Voice input. |
| Nov 3 | Stretch: print the film, run the laser test, SAM 3.1 compare. Polish. |
| Nov 4 | Record the video, write the README, **submit by the evening of Nov 4 (MYT)**. |

---

## 11. Risks and what I do about them

| Risk | Plan |
|---|---|
| Hologram patterns look like random noise to judges | Always show the reconstruction and the focus sweep next to the pattern. |
| Big calculations are slow | Small resolution locally; Modal GPU for the big version; cache results for the video. |
| AI gives wrong numbers | It can only quote tool results, and the app shows those numbers on screen. |
| Laser test fails | It is a stretch goal. The demo does not depend on it. |
| "Is this new work?" | New repo and dated commits; pre-event research is shown only as labeled background. |
