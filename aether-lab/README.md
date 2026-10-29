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

Optional cloud GPU: `pip install modal`, `modal token new`, `modal deploy modal_app.py`, then add
`AETHER_COMPUTE=modal` to `.env`.

## Tests
`python -m tests.test_physics` runs 6 physics checks (focus depth, two depths, pixel pitch and
bend angle, eye model, WRP vs direct, Window Law and hand conflict).

Laser safety for the optional printed-film test: use only a Class 2 (<1 mW) red laser and aim it
at a wall.
