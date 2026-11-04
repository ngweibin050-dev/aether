# AETHER Lab: AI-orchestration acceptance tests

`python -m tests.acceptance_ai`, 2026-11-05 02:50: a test server with its own project, driven through the chat API (what the UI calls). Each check reads what executed (tool results, files, the scene).

**13 / 14 pass.**

| # | test | request | tools the AI called | check | result | s |
|---|---|---|---|---|---|---|
| 1 | Unfamiliar drawing -> 3D model | Create a 3D model from this engineering drawing. | build_cad | 1 build call(s), 1 built (a failed first attempt the AI retried counts only if the retry built); program models in scene=1; kept={'round': 3, 'iou': {}, 'mean_iou': None, 'object': 'Douglas X-3 Stiletto supersonic resear | PASS | 754.2 |
| 2 | Modify the model in natural language | Make the wings thicker and add more detail to the cockpit canopy. | inspect, edit_cad, set_cad_param, edit_cad | edit_cad changed=True version=3 | PASS | 1781.3 |
| 3 | Blueprint from the current model | Generate an engineering blueprint from the current 3D model. | make_drawing | make_drawing called, 2 drawing files | PASS | 41.0 |
| 4 | Explain the machine | Explain how this machine works. | explain_machine | explain_machine called, 12 steps in the Explain panel | PASS | 87.4 |
| 5 | Explain one component | Explain the function of the component called 'fuselage_mid_body'. | inspect | tools ['inspect'] on 'fuselage_mid_body' (program model: True) | PASS | 11.5 |
| 6 | Simulate the assembly | Simulate the movement of the current assembly. | inspect, build_brep_assembly |  | FAIL | 99.8 |
| 7 | Hologram of the current model | Calculate a hologram of this 3D model. | make_hologram | make_hologram ran: {"lit_pixels": 26115, "points_used": 26115, "method": "rendered view -> depth layers (0.02 D) -> 2x2 sparse groups", "scale_note": "small lab-SLM demo, scene shrunk to fit 8 mm; not wave-equivalent to | PASS | 38.9 |
| 8 | Change a holography parameter and recalculate | Calculate it again with a larger viewing distance. | set_display, make_hologram | recalculated with [('make_hologram', {})] | PASS | 46.6 |
| 9 | Measure and analyse | What is the volume, surface area and centre of mass of this model? | analyze, calculate, calculate | analyze: {"parts": [{"part": "fuselage_mid_body", "volume_cm3": 6905356.94, "area_cm2": 262969.7, "density_g_cm3": 7.85, "mass_g": 54207052.0, "closed": false}, {"part": "fuselage_aft_section", "volume_cm3": 6 | PASS | 26.4 |
| 10 | Export in different formats | Export this model as STEP and as STL. | export_model, export_model | export_model formats ['step', 'stl'], 2 files | PASS | 8.5 |
| 11 | Several operations in one request | Paint it dark red, then export it as GLB and give me its blueprint. | modify, modify, inspect, export_model, make_drawing | tools used ['export_model', 'inspect', 'make_drawing', 'modify']; needed ['export_model', 'make_drawing', 'modify'] | PASS | 30.7 |
| 12 | Follow-up that refers to earlier results | Now export it as 3MF too. | export_model | 'it' resolved to ['selected'] | PASS | 6.9 |
| 13 | An invalid operation does not corrupt the model | Change the model so that its overall length is a negative number: -500 mm. | - | program versions [3] -> [3], parts 53 -> 53 (last valid state kept) | PASS | 7.2 |
| 14 | An object category with no construction code | Create a mechanical clamp with an adjustable screw and two gripping jaws. | build_cad | build_cad from a description only: built=True, parts=11 | PASS | 440.9 |

Full calls, results and replies: `output/acceptance/results.json`.
