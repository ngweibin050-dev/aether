# Built during the event

Meta AI Builders Hackathon 2026 build window: **Oct 26 – Nov 4, 2026**. Builder: Ng Wei Bin (solo).
Every file in this repository was written in that window. Dates below come from the original repository's commit
history and, for files not yet committed there, from file creation times (Malaysia time, UTC+8).

## Timeline

| Date | What was built |
|---|---|
| Oct 29 | First generation: physics engine (`engine/optics.py` point / WRP / layer holograms, band-limited angular spectrum, `eye.py` eye model, `film.py`), Muse Spark agent with tool calling (`agent.py`), local server, Modal GPU app (`modal_app.py`, `compute.py`), first test suite (`tests/test_physics.py`), first web viewer |
| Oct 30 (morning) | Second generation: parametric geometry library (`geometry.py`: involute gears, tubes, coils, blade rings...), GPU/CPU backend (`backend.py`), Window Law and hand-occlusion check (`window.py`), speckle analysis (`speckle.py`), `ARCHITECTURE.md` |
| Oct 30 (afternoon) | Third generation: React + three.js design desk (`ui/`), wave-optics retina (`retina.py`), true-scale desk wave simulation and phase-only pupil-GS (`desk_wave.py`), section / explode / x-ray (`cutaway.py`), drawing outlines and rebuild (`outline.py`, `rebuild.py`), three-view visual hull (`hull.py`), SAM 3.1 photo path (`vision.py`), live Meta smoke test |
| Oct 30 – 31 (night) | Engine fingerprint and automatic Modal redeploy (`version.py`), named car parts with recesses (`detail.py`), multi-view sheet reader (`sheet.py`, `segment.py`), circle measurement on drawings (`circles.py`), engineer's interpretation of a drawing with Muse Spark close-up reading (`interpret.py`), public landing page (`ui/src/site`) |
| Oct 31 | Modal redeploys only on a real engine change; tool arguments checked before every call; uploads routed by what the image is; reference-run harness (`tests/run_reference.py`, `docs/RESULTS.md`) |

`docs/CHANGELOG.md` lists every change from Oct 31 onward in detail.

## Background research (not part of this repository)

Before writing this code, the builder wrote physics notes on a no-headset holographic desk (notes v4–v13: 1D
holography and focus, speckle, card and desk geometry; the latest are dated Oct 27–28). They are **not included here,
as code or as text**. AETHER Lab re-implements the models it needs (eye model, speckle groups, Window Law, sharp zone)
from scratch in `engine/`, and every number it shows is computed by this code. No holographic display has been built:
all optics in this repository are simulations.
