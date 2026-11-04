# Demo video script: one story, 3 minutes

**The story:** a machine that exists only as a drawing becomes editable CAD that says what it measured, what it
inferred and what it cannot know; an engineer corrects it by conversation; the result is checked against the real
part. Show only AETHER Lab's CAD reconstruction (built during the event). Leave out the hologram desk, optics and hand
mode: they are not this story.

Before recording: `start.bat` (the browser opens when the lab is ready); Demo menu → *Warm up the GPU* is not needed
for this story. Have `tests/ground_truth/pillow_block/drawing.png` and the 1909 patent sheet at hand.

| time | screen | say (short) |
|---|---|---|
| 0:00–0:15 | The 1909 patent sheet (US 929,594), one sectional view | "This machine exists only as a 1909 patent drawing. One view, no scale, half of it hidden. Nobody has its CAD." |
| 0:15–0:45 | Demo → *P · 1909 patent → CAD* (or the recorded run). The chat steps show who works: **Muse Spark** checks the drawing, **Muse Wonder** plans every part, writes the CAD program; the **AETHER engine on Modal CPU** builds and checks; **Muse Spark** critiques real renders | "Muse Wonder plans 67 parts and writes a real OpenCascade program. Code checks every round: floating parts, parts passing through each other, mechanical constraints. Muse Spark looks at real renders and scores them." |
| 0:45–1:10 | Round 1 vs the kept round (renders / gates in the chat result; docs/CAD_QUALITY.md numbers) | "Round 1 had 35 parts passing through each other and 11 failed constraints. The kept round: 2 and 0." |
| 1:10–1:35 | View → **Drawing reading**: the sheet beside the plan, each part with its evidence; the **unknowns** list | "And it says what it cannot know: the machine's depth needs a plan view, the real scale needs a dimension, the drive train is behind the cover." |
| 1:35–2:15 | **Does it work? Ground truth.** Upload `pillow_block/drawing.png`: "Rebuild this part from its engineering drawing as editable CAD." Then View → **CAD document**: parameters marked *measured* (written on the drawing: exact) and *inferred* (scaled off it) | "To check it, we drew parts whose real sizes we know. The sizes written on the drawing come out exact. The ones it had to scale off the drawing are marked inferred, and they are a few millimetres off: bore 34 instead of 30." |
| 2:15–2:40 | Correct by chat: "the bore is 30 mm, the base is 14 mm thick, the bolt holes are 12 mm" (set_cad_param re-runs the same program in ~10 s) | "An engineer with calipers corrects the inferred values by chat. The same program re-runs in ten seconds, no AI call. Every feature diameter now matches: error zero, both bolt holes found." |
| 2:40–2:55 | The ground-truth table (docs/GROUND_TRUTH.md) and the one-shot baseline row | "Asked once, without the loop, Muse Wonder's program for this part crashed. With the loop: a valid solid, every number traceable, correctable to zero error." |
| 2:55–3:00 | File → Export STEP | "STEP out, into any CAD system. Built with Muse Spark, Muse Wonder, SAM 3.1 and Muse Voice." |

Numbers used above come from: docs/CAD_QUALITY.md (the press), docs/GROUND_TRUTH.md (pillow block, baseline,
correction). Re-check them against those files right before recording if anything was re-run.
