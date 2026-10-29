# AETHER Lab

**Design real holograms by talking to them.** Tell AETHER what 3D object to show. It calculates a real
(computer-generated) hologram, simulates the light to show what your eye would see at each depth, and
checks whether a holographic display design, AETHER Desk, can show it sharply.

Built for the Meta AI Builders Hackathon 2026 (Oct 26 – Nov 4). All code in this repo was written during the event.
The AETHER Desk numbers come from my pre-event physics study and are labeled as such.

## How it works

```
You (text or voice) → Muse Spark agent → tool calls → physics engine (local or Modal) → images + numbers → Muse Spark explains
```

- **Muse Spark** (Meta Model API) plans multi-step experiments and calls the lab tools. It never makes up numbers: every number it quotes is a tool result, and the app shows the same number on screen.
- **Physics engine** (`engine/`, NumPy):
  - `optics.py`: point-source computer-generated hologram (anti-aliased per point), band-limited angular spectrum propagation (Matsushima 2009), phase-only encoding
  - `eye.py`: wave-optics eye model (4 mm pupil, 15 cycles/degree) for judging a 1D-holographic desk display
  - `film.py`: binary Fourier hologram for printing on film and testing with a laser pointer
  - `lab.py`: the tools the agent can call
- **Modal** runs the heavy tools in the cloud (`modal_app.py`); the app falls back to local compute if Modal is unavailable.

### Agent tools
`set_scene`, `move_object`, `set_display`, `make_hologram`, `propagate`, `focus_sweep`, `desk_check`,
`search_column_width`, `measure_speckle`, `export_film`

## Physics checks

```
python -m tests.test_physics
```

| Test | Result |
|---|---|
| A single light point refocuses at the right depth | focus at 5.00 cm (target 5.00), 49 % of light in a 5×5-pixel spot |
| Two points at 4 cm and 7 cm are each sharp only at their own depth | 4.0 cm and 7.0 cm; point A keeps <0.1 % of its peak at B's depth |
| Halving pixel size doubles the bend angle; past the limit light goes the wrong way | ratio 2.000; asked 1.52°: 8 µm pixels → 1.53°, 16 µm pixels → −0.38° (aliased) |
| Eye model: full hologram reference; the 1D desk loses sharpness with height | 2D MTF 0.855; desk +5 cm 94 %, +15 cm 61 % |

## Run it (Windows)

1. Python 3.11+ installed.
2. Put your Meta key in `.env` (this folder or the parent folder): `META_API=...`
3. Double-click `start.bat`, or run `pip install -r requirements.txt` then `python server.py`.
4. Open http://localhost:8765

Cloud compute (optional): `pip install modal`, `modal token new`, `modal deploy modal_app.py`, then add `AETHER_COMPUTE=modal` to `.env`.

## Honest limits

- Everything shown is a **simulation** with established wave-optics methods. No physical holographic display was built.
- The full wave simulation runs on a small lab-scale hologram (~8 mm). Desk-scale questions use the eye model, because a 27-inch hologram has ~30 million pixels.
- The printed-film test (optional) shows a 2D picture on a wall. It proves the calculation controls real light; it does not prove the desk design.

Laser safety: use only a Class 2 (<1 mW) red laser pointer, aim it at a wall, never into eyes.
