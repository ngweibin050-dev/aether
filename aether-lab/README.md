# AETHER 2.0 — Holographic design desk

Design a 3D model with a mouse and keyboard, with your hands in the air, or by asking Muse Spark.
AETHER calculates the real phase hologram for that model, simulates what your eye would see, and
checks whether a no-headset holographic desk could show it sharply.

Built for the Meta AI Builders Hackathon 2026 (Oct 26 – Nov 4). Every result is a wave-optics
**simulation**. No physical holographic display has been built.

- **Laptop mode**: a Blender-style gizmo (G / R / S, X/Y/Z axis lock), an outliner, numeric
  properties, undo and redo, and GLB import with automatic decimation.
- **Hand mode**: MediaPipe hand tracking. Pinch to grab and move, pinch with both hands to rotate
  and scale, show both open palms to calculate the hologram. It shares the same scene state as
  laptop mode.
- **Text-to-CAD**: Muse Spark designs assemblies from a parametric part library (gears, tubes,
  nozzles, coils, blade rings…).
- **AI design loop**: Muse Spark and the physics engine take turns. The wave-optics eye model scores every
  part on the AETHER Desk (`desk_score`), Muse Spark moves, turns or scales the design, the engine scores it
  again, until every part is sharp and inside the window. The UI shows the before/after eye views.
- **Photo of a real part**: SAM 3.1 cuts the part out of a phone photo; AETHER measures the silhouette
  (size, centre hole, number of teeth or blades); Muse Spark rebuilds it from the parametric library.
- **Voice**: hold the mic button; Muse Voice Transcribe turns speech into a command.

Meta models used: Muse Spark 1.3 (agent with tool calling), SAM 3.1 (segmentation, `/v1/responses`),
Muse Voice Transcribe 1.0 (`/v1/asr/transcribe`).
- **Physics**: point-cloud CGH with hidden surfaces removed, the Wavefront Recording Plane method,
  the band-limited angular spectrum method, an eye view through the pupil, the Window Law, the
  hand-occlusion depth-conflict check, the 1D-desk eye model, and sparse-group speckle analysis.
  It runs on CuPy GPU (on Modal) or NumPy.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design and the equations.

## Run (Windows)
1. Install Python 3.11+.
2. Put your Meta key in `.env` (in this folder or the parent folder): `META_API=...`
3. Double-click `start.bat`, or run `pip install -r requirements.txt` and then `python server.py`.
4. Open http://localhost:8765 . The built UI is in `ui/dist`, so Node is not needed.

To change the UI, run `cd ui && npm install && npm run dev` (dev server on :5173, which proxies to :8765),
then `npm run build`.

Physics runs on a Modal GPU by default: `modal token new`, then `modal deploy modal_app.py` once (and again after
engine changes). Add `AETHER_COMPUTE=local` to `.env` to run it on this computer instead.

## Tests
`python -m tests.test_physics` runs 16 checks (focus depth, two depths, pixel pitch and bend angle, eye model,
WRP vs direct, Window Law and hand conflict, see-inside, the design-loop score, photo silhouette measurements,
sharpness metric, watertight outlines, involute gear mesh, drawing rebuild, wave simulation vs eye model,
three-view import, full-2D reference).

Laser safety for the optional printed-film test: use only a Class 2 (<1 mW) red laser and aim it
at a wall.
