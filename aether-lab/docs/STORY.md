# AETHER Lab — one workflow, end to end

`python -m tests.e2e_story`, 2026-11-04 09:19: a test server and project of its own, driven through the app's HTTP API (what the UI calls), Muse Spark 1.3 + SAM 3.1 + OpenCascade.

**8 / 8 steps pass, 7.8 min.**

| # | step | result | seconds | what happened |
|---|---|---|---|---|
| 1 | Upload a three-view drawing; the CAD build starts (assumptions labelled) | PASS | 14.8 | asked first: False; build started in the background; assumed ['real size / dimensions'] |
| 2 | CAD build + detail pass in the background (exact B-rep) | PASS | 225.6 | jobs [('cad_ddc720', 'done', 96.9), ('cad_detail', 'done', 127.5)]; model Lamborghini-style sports car (CAD from three views); regions ['glass', 'headlight', 'tail light'] |
| 3 | Refine by chat; the result's own check passes | PASS | 43.0 | status checks_passed; 10 changes; tools ['inspect', 'modify', 'modify', 'add_parts'] |
| 4 | Section view by chat | PASS | 24.0 | section y at 0.0 mm |
| 5 | A real B-rep feature by chat (pocket), document recomputed | PASS | 138.4 | cad_feature added ['Pocket: front air intake (assistant, front view)'] |
| 6 | CAD document validated | PASS | 0.5 | 59 features, status {'state': 'ok', 'rebuilt_features': 1, 'cached_features': 58, 'seconds': 3.76, 'param_hash': 'c6398ab4fbe5bfd7', 'validation': {'components': {'body': {'name': 'body', 'brepcheck_valid': True, 'solids': 1, 'shells': 1, 'faces': 102, 'edges': 1461, 'free_edges': 0, 'volume_mm3': 5799386681.094, 'area_mm2': 24184852.865, 'centre_mm': [2375.693, 0.0, 575.697], 'bbox_mm': [14.405,  |
| 7 | STEP export by chat, re-read in a fresh OpenCascade process | PASS | 20.0 | Lamborghini-style_sports_car_CAD_from_th.step: 7177452 bytes, re-read: 11 solid(s) {'groups': [], 'document_id': 'step:Lamborghini-style_sports_car_CAD_from_th.step'} |
| 8 | Restart: the project reopens with its history; undo / redo of the refine step | PASS | 2.2 | reopened: 25 parts, 4 history steps; undo 'make the car more detailed: driver and passenger seats with seat belts, a das…' -> 16 parts (removed Driver seat, Passenger seat, Driver belt, Passenger belt, Dashboard, Steering wheel (+18 more); put back Wheel front right, Wheel front left, Wheel rear right, Wheel rear left, Body shell, Tyre (wheel fr) (+9 more); restored Body shell; also ['add a real C |
