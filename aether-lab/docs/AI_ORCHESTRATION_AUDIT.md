# AETHER Lab: AI orchestration audit (4 Nov 2026)

This audit checks AETHER Lab against the directive "the AI is the engineer, AETHER's tools are the instruments". It
records what the code does today, what is object-specific, and the order of the changes. It was written before
those changes were made.

## 1. What already matches the directive

**There is one orchestrator.** `assistant.py` runs one Muse Spark tool loop per user turn (`turn()`), with up to 16
steps. Every turn starts with a scene summary, so the model knows the models, parts, selection, files and results.
References like "it" and "the car" resolve against that summary (`resolve()`). The model chooses the tools and their
order; there is no fixed pipeline per sentence. Safety lives in code:

- a scene is never emptied;
- removing something needs a target that resolves;
- every changing turn leaves an undo step (`history.py`);
- the reply lists the changes computed from the scene itself (`diff()`), so a claimed change that did not happen
  shows.

**Tools the AI can already discover and call** (each has a JSON schema; `assistant.TOOL_DEFS`):

| family | tools | executes in |
|---|---|---|
| inspection | `inspect`, `list_parts`, `analyze` (volume, area, mass, centre of mass, closed meshes) | `assistant.py`, `engine/lab.py` |
| creation | `create_model` (parts from a generic primitive library), `build_from_drawing`, `import_file` | `engine/lab.py`, `agent.py`, `cad/` |
| modification | `add_parts`, `cad_feature` (B-rep imprint / pocket), `modify`, `remove`, `undo`, `redo` | `refine.py`, CAD worker |
| drawings | `make_drawing` (front / top / side from the B-rep, hidden lines, dimensions, title block; SVG + PDF) | CAD worker |
| export | `export_model` (glb, stl, 3mf, step) | `engine/export.py`, CAD worker |
| explanation | `explain_machine` (Explain panel; every part id and number checked against the model) | `explain.py` |
| scene / view | `set_view` (section, explode, isolate, x-ray), `open_panel` | `engine/cutaway.py`, UI |
| holography | `make_hologram`, `propagate`, `focus_sweep`, `eye_view`, `desk_wave_view`, `speckle_compare`, `export_film` | `engine/` via `compute.py` (Modal GPU or local) |
| desk physics | `window_check`, `hand_check`, `desk_check`, `desk_score`, `search_column_width`, `optimize_for_desk` | `engine/` |
| mechanism | `turn_gear` (turns a gear and every gear meshed with it) | `engine/lab.py` |
| other | `calculate` (safe arithmetic), `web_search`, `ask_user` | `assistant.py` |

## 2. What violates it: object-specific intelligence

| where | what is hard-coded | effect |
|---|---|---|
| `cad/vehicle.py`, `cad/planner.py::plan_vehicle`, `cad/pipeline.py` | The whole three-view → CAD path is a car recipe: wheels and arches, a roof "greenhouse", mirrors, exhaust tips, the order of cross-section stations, `REGION_RULES` | Only closed cars work. The CC0 roadster came out with its cockpit covered and no windscreen or roll bar. Any other object cannot be built from a three-view sheet. |
| `engine/rebuild.py::KINDS` and the rebuild per kind | Single-view mechanisms are rebuilt through 7 fixed kinds (gear, spring, link, piston, frame, wheel, shaft) | A part outside those kinds is forced into one of them |
| `refine.py::SLOTS`, `refine.vehicle()` | Vehicle interior "slots" (driver_seat, dashboard, steering_wheel …) with fixed sizes and positions | Interior detail works for cars only |
| `assistant.cad_feature` | "needs a CAD vehicle body (front at -x)" | B-rep features only on the car body |
| `create_model` | A fixed primitive library (box, tube, gear, cone …) placed by the model | General, but it cannot make real CAD shapes (lofts, sweeps, booleans): the "boxes" look |

## 3. The change: one general CAD capability the AI drives

**New: `cad/codegen.py`, the AI-written CAD program.** For any object, from a drawing, a description, or both:

1. Code measures the drawing: views, silhouettes, profiles. No model is involved.
2. Muse writes a CadQuery (OpenCascade) program: a plan, then named, coloured parts.
3. The program runs in a sandbox:
   - its syntax tree is checked first: no imports, no dunders, no `exec`, `eval` or `open`;
   - only `cq`, `math` and the measured profile functions are in scope;
   - it runs in a separate process, without the API key, under a time limit.
4. Every part must pass BRepCheck. Code compares each view with the drawing.
5. Muse sees the overlays, the scores and any errors, and rewrites the program.
6. The best round that passed the checks is kept.

The program is the editable parametric source: an edit is a new version of the program, and a failed version never
replaces the last valid model.

**This changes one earlier rule.** "No model output is ever executed" becomes "a model-written CAD program runs only
after the static check, in a sandboxed process, and its result counts only if every solid is valid".

### Order of work

1. **Phase 2 (first, it is the core):**
   - `build_from_drawing` and `create_model` use the CAD program;
   - a new tool `edit_cad_program` changes an existing program model;
   - `vehicle.py` and `plan_vehicle` stop being the default path. They stay in the repository only until the
     evidence for them is re-measured, and are then removed.
2. **Phase 3:** `cad_feature`, `analyze`, `make_drawing`, `export_model` and `explain_machine` work on program
   models. These tools are general already; the work is to point them at the program model's B-rep.
3. **Phase 4–5:** the 14 acceptance tests, run through the chat API (what the UI calls), with a record for each:
   - the request;
   - the tools the AI chose and the calls it made;
   - the results and artifacts;
   - the validation;
   - the limits.

## 4. Gaps this audit does not close today

- **Motion simulation** exists only as `turn_gear`. There is no general kinematics or collision solver: the B-rep
  interference check is in `cad/assembly.py` but is not yet a chat tool. Requests like "simulate this assembly"
  must say what can and cannot be computed.
- **Physical parameters** (mass, friction, torque) are not part of the model. The AI must ask for them, not invent
  them.
- **Manufacturing tolerances** are never invented: drawings show only the dimensions the model has.
