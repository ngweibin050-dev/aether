# AETHER Lab: AI-orchestration acceptance tests

`python -m tests.acceptance_ai`, 2026-11-04 15:25: a test server with its own project, driven through the chat API (what the UI calls). Each check reads what executed (tool results, files, the scene).

**14 / 14 pass.**

| # | test | request | tools the AI called | check | result | s |
|---|---|---|---|---|---|---|
| 1 | Unfamiliar drawing -> 3D model | Create a 3D model from this engineering drawing. | build_cad | 1 build call(s), 1 built (a failed first attempt the AI retried counts only if the retry built); program models in scene=1; kept={'round': 4, 'iou': {}, 'mean_iou': None, 'object': 'Supersonic jet aircraft (F-104-like si | PASS | 289.1 |
| 2 | Modify the model in natural language | Make the wings thicker and add more detail to the cockpit canopy. | inspect, edit_cad | edit_cad changed=True version=2 | PASS | 265.7 |
| 3 | Blueprint from the current model | Generate an engineering blueprint from the current 3D model. | make_drawing | make_drawing called, 2 drawing files | PASS | 11.7 |
| 4 | Explain the machine | Explain how this machine works. | explain_machine | explain_machine called, 12 steps in the Explain panel | PASS | 62.1 |
| 5 | Explain one component | Explain the function of the component called 'fuselage'. | inspect | tools ['inspect'] on 'fuselage' (program model: True) | PASS | 17.2 |
| 6 | Simulate the assembly | Simulate the movement of the current assembly. | open_panel |  + said what cannot be simulated | PASS | 20.0 |
| 7 | Hologram of the current model | Calculate a hologram of this 3D model. | make_hologram | make_hologram ran: {"lit_pixels": 32682, "points_used": 32682, "method": "rendered view -> depth layers (0.02 D) -> 2x2 sparse groups", "scale_note": "small lab-SLM demo, scene shrunk to fit 8 mm; not wave-equivalent to | PASS | 52.8 |
| 8 | Change a holography parameter and recalculate | Calculate it again with a larger viewing distance. | set_display, make_hologram | recalculated with [('make_hologram', {})] | PASS | 44.7 |
| 9 | Measure and analyse | What is the volume, surface area and centre of mass of this model? | analyze, calculate, calculate, calculate | analyze: {"parts": [{"part": "fuselage", "volume_cm3": 10389626.74, "area_cm2": 400953.5, "density_g_cm3": 7.85, "mass_g": 81558569.9, "closed": false}, {"part": "main_wing", "volume_cm3": 2497109.11, "area_cm | PASS | 26.2 |
| 10 | Export in different formats | Export this model as STEP and as STL. | export_model, export_model | export_model formats ['step', 'stl'], 2 files | PASS | 7.5 |
| 11 | Several operations in one request | Paint it dark red, then export it as GLB and give me its blueprint. | modify, inspect, export_model, make_drawing | tools used ['export_model', 'inspect', 'make_drawing', 'modify']; needed ['export_model', 'make_drawing', 'modify'] | PASS | 20.5 |
| 12 | Follow-up that refers to earlier results | Now export it as 3MF too. | export_model | 'it' resolved to ['supersonic_jet'] | PASS | 7.1 |
| 13 | An invalid operation does not corrupt the model | Change the model so that its overall length is a negative number: -500 mm. | - | program versions [2] -> [2], parts 46 -> 46 (last valid state kept) | PASS | 14.4 |
| 14 | An object category with no construction code | Create a mechanical clamp with an adjustable screw and two gripping jaws. | build_cad | build_cad from a description only: built=True, parts=7 | PASS | 270.4 |

Full calls, results and replies: `output/acceptance/results.json`.

**Read with care:**

- **Test 6 (simulation)** passed by honesty, not by a solver. AETHER has no general motion or collision solver.
  The AI said so, opened the physics panel and offered what it can do (explode, section, explain).
- **Test 8 (hologram parameter)** really changed the viewing distance (`set_display distance_mm=600`) and
  recalculated. Its reply could not name the previous value.
- **Test 13 (invalid operation):** the AI refused a negative length, explained why, and called no tool. The program
  version (2) and the part count (46) stayed the same.
- **Test 1 (unfamiliar drawing):** the NASA X-3 sheet has three views, so its outlines were not measured
  automatically. Muse read the drawing from the image, and renders checked the model (no IoU).
- **Earlier runs of this file:**
  - Run 1 failed test 1: the outline measurement only accepted four-view sheets.
  - Run 2 failed tests 13 and 14. In test 14, programs arrived wrapped in Markdown fences, the sandbox rejected
    them, and the AI fell back to the old primitive tool. In test 13, the request ("minus 500 mm") was ambiguous.
  - Both causes were fixed before this run: the fallback to the image, fence stripping, a "retry build_cad, do not
    fall back" rule, and an unambiguous test request.
