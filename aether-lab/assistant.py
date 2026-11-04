"""AETHER's assistant: understands any message and acts on the scene safely.

One Muse Spark tool loop per user turn, built so that whatever the user types the right thing happens:

- It always knows the scene: every turn starts with a summary of the models on the desk (name, what it is, parts, size,
  colours, named regions such as the glass of a CAD car body), the selection, the project files and which results
  exist. "The car", "it", "the window" resolve against that (resolve()).
- Intent first (SYSTEM): knowledge and maths are answered without touching the scene; teaching opens the Explain
  player; create / refine / modify / add / remove / export / derive a drawing / look something up each map to their
  own tool; a destructive request that is ambiguous is asked back as a question with options (ask_user).
- Safety is in code, not only in the prompt: creating never empties the scene (no replace), removing needs a target
  that resolves, every turn that changes the scene leaves an undo snapshot, and the reply carries the list of what
  actually changed, computed from the scene itself (diff()), so a claim of a change that did not happen is visible.
- Results that are files (exports, drawings) come back as download cards; questions come back as clickable options.
"""
from __future__ import annotations

import ast
import copy
import json
import math
import operator
import os
import re
import threading
import time
import urllib.error
import uuid
from pathlib import Path

import numpy as np

import agent
import compute
import history as steps  # the project's undo history (history.py)
import refine
from engine import geometry, lab, retina, snap

ROOT = Path(__file__).resolve().parent
MAX_STEPS = 16
EFFORT_FIRST = os.environ.get("AETHER_CHAT_EFFORT_FIRST", "medium")
EFFORT_NEXT = os.environ.get("AETHER_CHAT_EFFORT_NEXT", "low")

# ------------------------------------------------------------------------------------------------ the system prompt
SYSTEM = """You are AETHER, the assistant inside AETHER Lab, a 3D engineering workspace with a simulated holographic desk.
You talk with people of every level (a student who asks "what is a 3D model", an engineer, someone who is upset) and you
act on their 3D scene with tools.

HOW TO HANDLE EVERY MESSAGE (decide the intent first, silently):
1. Knowledge / chat ("what is a 3D model", "how does a hologram work", greetings): answer in plain words. Do NOT call
   scene tools and do not change the scene.
2. Maths or unit conversion ("45+64", "3 inch in mm"): call calculate and give the result. Never do arithmetic in your
   head.
3. Learn / understand a machine ("help me learn this machine", "explain the machine", "how does it work"): call
   explain_machine (it opens the step-by-step Explain player in the app). Then give a short overview.
4. Inspect ("what is this part", "how big", "is it valid"): call inspect (and list_parts if needed), then answer.
5. Create something new ("make a clamp", or a drawing / blueprint attached with "build this"): build_cad. YOU are the
   engineer: you write the CAD program for whatever the object is (no built-in recipe exists for any object). Give the
   attached drawing as `file` and what the user wants as `description`. It takes minutes; it reports per round what
   was built and how it checked against the drawing. Tell the user what was measured from the drawing, what you
   estimated, and what still does not match. (build_from_drawing / create_model are older paths: use them only if the
   user asks for a quick rough model or for a photo of a single part.) The new model is placed BESIDE what is already
   there; nothing is removed.
   If build_cad reports built=false, read its round errors, call build_cad ONCE more with a clearer description, and
   if that fails too, tell the user plainly what failed. Do not fall back to create_model unless the user agrees.
   CHANGING THE GEOMETRY of a build_cad model (inspect says kind "cad program"): edit_cad with the user's request.
   Colour, visibility, position or size of the whole model: modify (that is display, not geometry).
   MISSING INFORMATION: build_from_drawing first checks the drawing (views, size, what it is, anything cut off). If
   something critical is missing it does NOT build: it asks the user (the question and answer buttons are shown for
   you). When the user answers, call build_from_drawing again for the same file with what they said in `answers`
   (overall_length_mm if they gave a size, object if they said what it is) and assume=true if they said they do not
   have it. Then list in your reply what was assumed. For a text request, ask (ask_user, with a sensible default as
   one option) only when a missing fact changes what gets built a lot (e.g. "a gearbox" with no ratio for a real
   machine); otherwise build with clear defaults and say what you assumed.
6. Refine an existing model ("more detailed", "add lights, a number plate, mirrors, seats"): call inspect on it ONCE.
   A "cad program" model: edit_cad, always (add_parts is refused for it).
   An OLDER model (a CAD model from a three-view sheet, or a parametric model) asked for MUCH more detail or realism
   ("a lot", "like a real car", "more attractive"): do not stick panels on its single body. Rebuild it with build_cad
   from its drawing (the project file it was built from) and the user's request as `description`, so that it is made
   of real separate parts. The new model goes beside the old one. Tell the user that, and that they can remove the old
   one. Small additions to older models (one badge, one colour) can still use the steps below.
   It tells you what the model ALREADY has (parts, CAD features, named regions), its real size, and which side is its
   FRONT. What you add must look like it belongs to THIS model (same finish, on its real surface, real proportions),
   never toy blocks stuck on it. In this order of preference:
   a. Use what is there. A CAD body's windows are its 'glass' region and its lamps its lamp regions ('headlight',
      'tail light'; on older models one 'light' region): recolour them with modify(region=...), each in its own
      colour. Never add a part over a region, never add something inspect already lists.
   b. New SURFACE details (a lamp, number plate, grille, intake, badge, stripe, window where there is no glass region):
      add_parts with attach {side, u, v} and the outline size in params (w = width along u, d = height along v, in
      real mm). They become thin panels that follow the model's curved surface exactly (instant). Use cad_feature
      (exact B-rep imprint / pocket, 1-3 minutes per batch) ONLY when the user asks for real CAD features / a real
      recess, or for a CAD export that must carry them.
   c. Separate parts: add_parts, EVERY part with attach. Use the shaped part types, not box: rbox (rounded panel,
      handle, trim, bracket), seat, seat_belt, steering_wheel, dashboard, engine, exhaust_tip, interior_mirror, plus
      cylinder / tube / torus / gear for mechanisms. A plain "box" is made an rbox automatically. Fasteners and
      bearings are STANDARD parts by designation, never invented shapes: hex_bolt {size: "M8", length}, hex_nut,
      washer, ball_bearing {designation: "6204"} (sizes from ISO tables); gears with a standard module.
      VEHICLES (inspect says it has wheels): interior parts use attach {slot: ...} (driver_seat, passenger_seat,
      driver_belt, passenger_belt, dashboard, steering_wheel, rear_view_mirror, engine_bay, center_console); their
      place, orientation and size come from the car itself, so give no params unless the user asked for a size.
      Other models: {side, u, v} ON a surface, or {side: "inside", u, v, w}; parts inside are shrunk to fit the body.
   add_parts answers with checks (floating / outside / overlap / duplicate) and a picture. Look at it; fix what is
   wrong in at most 2 rounds and say plainly what is still not right. Parts inside a closed body are hidden: say so
   and offer the section view ("cut it in half"). Never rebuild the model, never remove it to refine it, never add a
   part twice (to change a part you added, use modify).
7. Modify ("make the window blue", "move it left", "bigger", "hide the wheels", "rename"): call modify on exactly what
   was named. Change nothing else. A CAD body's named regions (glass = windows; headlight, tail light = lamps; any
   region added with cad_feature) can be coloured with modify(target=<model>, region="glass", color=...).
8. Add a file ("put this GLB beside the car"): import_file with placement "beside"; the existing models stay.
9. Remove ("remove the model", "delete the wheels"): only when the user clearly asks. Call remove with the target. If it
   is not clear which model is meant (two or more models and the user says "it" / "the model"), call ask_user with
   the candidates as options instead of guessing.
10. Export ("export to GLB and send it to me", "give me the STEP"): export_model. The file appears as a download card
    in the chat; say so in one sentence.
11. Drawings ("make a reliable blueprint / technical drawing from the model"): make_drawing (orthographic views with
    hidden lines from the exact B-rep, overall dimensions, title block, as SVG + PDF).
12. Current facts from the web ("latest version of ...", prices, news, standards): web_search, and cite the sources.
13. "Undo", "go back", "that was wrong, revert": undo.
14. Desk / hologram / sharpness questions: the physics tools (desk_score, focus_sweep, window_check, eye_view ...).
15. Opening a panel or view ("show the CAD panel", "cut it in half", "explode it"): open_panel / set_view.
16. Something AETHER cannot do: say so plainly and offer the closest thing it can do.

AMBIGUITY: if a request could DESTROY or REPLACE work and the target is unclear, ask (ask_user, 2-4 short options).
If it is harmless and unclear, do the most likely thing and say what you assumed in one sentence.

TONE: answer in the user's language and register (English, Chinese, Malay, Manglish ...). Short, plain sentences.
If the user is angry or rude, do not argue, do not lecture and do not apologise more than once: acknowledge in a few
words, do exactly the requested change (the smallest correct one), and say what changed. Example: "Sorry about that.
The car windows are blue now (glass region of the body). Say 'undo' to go back."

HONESTY: use tools for every number about the scene; never invent measurements. Never say you changed something unless
the tool result says so. A model rebuilt from a drawing or text is a simplified model, not manufacturer data; desk and
hologram results are simulations of a display that has not been built.

UNITS: millimetres. The display surface is z = 0; models stand on it. Positions in create_model are in the new
model's own frame. Round parts have their axis along local z. With attach, a part's local z points out of the surface
(a box's h or a cylinder's height is its thickness out of the surface) and its local x runs along u.

PART TYPES and their params (use exactly these names): """ + "; ".join(f"{k}({v})" for k, v in geometry.PARAM_HELP.items())

# ------------------------------------------------------------------------------------------------ tool schemas
_P = {"type": "number"}
_V3 = {"type": "array", "items": _P, "minItems": 3, "maxItems": 3}
_TARGET = {"type": "string", "description": "a model or part: its name (as in the scene summary), id, 'selected', or 'all'"}
_PART = agent._PART
_ATTACH = {"type": "object", "description": "where the part goes on the model (instead of position)", "properties": {
    "slot": {"type": "string", "enum": list(refine.SLOTS), "description": "VEHICLES: a named place measured on the model "
             "(driver_seat, passenger_seat, driver_belt, passenger_belt, dashboard, steering_wheel, rear_view_mirror, "
             "engine_bay, center_console): position, orientation and size are worked out from the car; no side / u / v"},
    "side": {"type": "string", "enum": list(refine.SIDES) + ["inside"]},
    "u": {**_P, "description": "0..1 across that side: front/rear: model's left->right; left/right/top: rear->front"},
    "v": {**_P, "description": "0..1: front/rear/left/right: bottom->top; top: left->right; inside: left->right"},
    "w": {**_P, "description": "inside only: bottom->top 0..1"},
    "proud_mm": {**_P, "description": "how far the outer face stands above the surface (default 60% of thickness)"},
    "spin_deg": {**_P, "description": "turn about the surface normal"}}}
_PART_ATTACH = {**_PART, "properties": {**_PART["properties"], "attach": _ATTACH}}

NEW_SCHEMAS = [
    ("calculate", "Exact arithmetic / unit maths. Supports + - * / // % **, parentheses, sqrt, sin, cos, tan, asin, acos, "
     "atan, pi, e, log, log10, exp, radians, degrees, abs, round, min, max.",
     {"expression": {"type": "string"}}, ["expression"]),
    ("web_search", "Search the web (Meta search grounding) for current facts; returns an answer with source links.",
     {"query": {"type": "string"}}, ["query"]),
    ("inspect", "Facts about one model or part: what it is, its parts (names, types, colours, sizes), bounding box in the "
     "model's own frame and on the desk, named regions, B-rep validation if built.", {"target": _TARGET}, ["target"]),
    ("explain_machine", "Open the step-by-step Explain player for a model (Muse Spark explains how it works, each step "
     "highlights its parts). Use for 'explain', 'teach me', 'help me learn'.", {"target": _TARGET}, []),
    ("build_cad", "Build a NEW, real CAD model of ANY object: you (Muse) write a CadQuery / OpenCascade program for it, "
     "it runs in a sandbox, every part is validated as an exact solid, and the program is revised against the "
     "attached drawing (view-by-view comparison) or against renders of the model, for a few rounds (minutes). Give "
     "`file` for an attached drawing / blueprint, `description` for what to build or what the user wants (both if you "
     "have both). The program becomes the model's editable source. Prefer this for every new model.",
     {"description": {"type": "string"}, "file": {"type": "string"}, "name": {"type": "string"},
      "rounds": {"type": "integer", "description": "revision rounds, 2-5 (default 3; each round takes several minutes)"}}, []),
    ("edit_cad", "Change a model built with build_cad by revising its CAD program (geometry: thicker walls, holes, more "
     "detail, other proportions, new parts...). The new version replaces the model only if every solid is valid; "
     "otherwise the model stays as it was. Colour / visibility / position changes are NOT geometry: use modify.",
     {"model": _TARGET, "instruction": {"type": "string"}, "rounds": {"type": "integer"}}, ["model", "instruction"]),
    ("set_cad_param", "Correct named PARAMETERS of a build_cad model (inspect lists them with their value, provenance "
     "and evidence): e.g. the user says the real wheelbase is 2400 mm, or the wall must be 3 mm. The same program is re-run "
     "with the new values (no rewrite, seconds to a minute); if the values break the model it stays as it was. Use this "
     "instead of edit_cad whenever the change is a value of an existing parameter.",
     {"model": _TARGET, "values": {"type": "object", "description": "parameter name -> new value (in its unit)"}},
     ["model", "values"]),
    ("create_model", "Create a NEW model from parametric parts (text-to-CAD). It is placed beside the existing models; "
     "nothing is removed. Aim for 6-25 parts that capture the real structure.",
     {"name": {"type": "string"}, "parts": {"type": "array", "items": _PART}}, ["name", "parts"]),
    ("add_parts", "Refine an EXISTING model: add separate parts to it, each placed with attach (on the real surface of "
     "one side, or inside). Answers with checks and a picture of the result.",
     {"model": _TARGET, "parts": {"type": "array", "items": _PART_ATTACH}}, ["model", "parts"]),
    ("cad_feature", "Add details to a CAD model's BODY as exact B-rep features, ALL in one call (one rebuild, about "
     "1-2 minutes): imprint (an outline that becomes its own colourable region: lamp, plate, door line, badge) or "
     "pocket (a recess depth_mm deep: grille, intake, plate recess). side: front / rear / top, or left / right (a side "
     "feature is made on BOTH sides: the body is symmetric). Outline: shape rect / ellipse centred at (u, v) with "
     "width_mm x height_mm (real mm), or polygon points [[u, v], ...]; u, v as in attach. color: the new region's "
     "colour. Answers with what was built, what could not be, and a picture of the result.",
     {"model": _TARGET, "features": {"type": "array", "items": {"type": "object", "properties": {
         "op": {"type": "string", "enum": ["imprint", "pocket"]},
         "side": {"type": "string", "enum": ["front", "rear", "left", "right", "top"]},
         "shape": {"type": "string", "enum": ["rect", "ellipse", "polygon"]}, "u": _P, "v": _P,
         "width_mm": _P, "height_mm": _P, "points": {"type": "array", "items": {"type": "array", "items": _P}},
         "name": {"type": "string", "description": "what it is (becomes the region name, e.g. 'headlight')"},
         "color": {"type": "string"}, "depth_mm": _P}, "required": ["op", "side", "name"]}}},
     ["model", "features"]),
    ("modify", "Change exactly what is named: colour (hex or name), region colour of a CAD body (its named regions, "
     "e.g. 'glass', 'headlight', 'tail light'; 'light' = every lamp region), "
     "move_by [dx,dy,dz] mm, position, rotation [deg], scale_by (uniform factor), visible, new_name, params.",
     {"target": _TARGET, "color": {"type": "string"}, "region": {"type": "string"}, "move_by": _V3, "position": _V3,
      "rotation": _V3, "scale_by": _P, "visible": {"type": "boolean"}, "new_name": {"type": "string"},
      "params": {"type": "object"}}, ["target"]),
    ("remove", "Remove a model or part (and what is under it). Only when the user asked to remove it. Undoable.",
     {"target": _TARGET}, ["target"]),
    ("export_model", "Export a model (or 'all') as a file the user downloads from the chat: glb (viewer / web), stl "
     "(3D printing), step (CAD, exact B-rep).", {"target": _TARGET, "format": {"type": "string", "enum": ["glb", "stl", "3mf", "step"]}},
     ["target", "format"]),
    ("make_drawing", "Technical drawing of a model from its exact B-rep: front, top and side views with hidden lines, "
     "overall dimensions and a title block, as SVG + PDF download cards.", {"target": _TARGET, "title": {"type": "string"}},
     ["target"]),
    ("build_from_drawing", "Build a 3D model from an attached drawing, blueprint or photo (by file name). kind: auto, "
     "machine (one view of a mechanism), three_view (side/top/end sheet -> parametric CAD), part (photo of one part). "
     "The drawing is checked first: if something critical is missing, the user is asked instead (nothing is built). "
     "The new model is placed beside the existing ones.",
     {"file": {"type": "string"}, "kind": {"type": "string", "enum": ["auto", "machine", "three_view", "part"]},
      "hint": {"type": "string", "description": "what the object is, if the user said"},
      "answers": {"type": "object", "description": "what the user answered to the check's question",
                  "properties": {"overall_length_mm": _P, "object": {"type": "string"}, "other": {"type": "string"}}},
      "assume": {"type": "boolean", "description": "true when the user said they do not have the missing information"}},
     ["file"]),
    ("import_file", "Bring an attached 3D file (glb, gltf, stl, obj) into the scene beside the existing models.",
     {"file": {"type": "string"}, "name": {"type": "string"}}, ["file"]),
    ("analyze", "Mass properties of a model or part in real mm: volume, surface area, mass (density from each part's "
     "material or name, or the given material for all), centre of mass, size, and which meshes are not closed. For "
     "'how heavy', 'what does it weigh', 'centre of gravity', 'volume'.", {"target": _TARGET, "material": {"type": "string"}},
     ["target"]),
    ("undo", "Undo the user's last step (an assistant turn or an edit in the app). Only the parts that step changed "
     "go back; other models are not touched. Tell the user exactly what the result's 'what' says was undone.", {}, []),
    ("redo", "Redo the last undone step.", {}, []),
    ("ask_user", "Ask the user one short question with 2-4 options (shown as buttons). Use when a destructive request "
     "is ambiguous. Ends your turn.", {"question": {"type": "string"},
                                        "options": {"type": "array", "items": {"type": "string"}}}, ["question", "options"]),
    ("open_panel", "Open a panel in the app: assembly (B-rep tree, mates, checks), drawing (balloons on the read drawing), "
     "optics (desk simulation figure), cad (CAD document), physics.",
     {"panel": {"type": "string", "enum": ["assembly", "drawing", "optics", "cad", "physics"]}}, ["panel"]),
]
KEEP = {"set_view", "set_eye", "set_display", "make_hologram", "propagate", "desk_wave_view", "focus_sweep", "eye_view",
        "window_check", "hand_check", "desk_check", "search_column_width", "desk_score", "optimize_for_desk",
        "speckle_compare", "export_film", "turn_gear", "list_parts"}
TOOL_DEFS = [d for d in agent.TOOL_DEFS if d["function"]["name"] in KEEP] + [
    {"type": "function", "function": {"name": n, "description": d,
                                      "parameters": {"type": "object", "properties": p, "required": r}}}
    for n, d, p, r in NEW_SCHEMAS]

# ------------------------------------------------------------------------------------------------ scene helpers
REGION_WORDS = {"glass": ("window", "windows", "windscreen", "windshield", "glass", "窗", "玻璃", "tingkap", "cermin"),
                "light": ("light", "lights", "lamp", "lamps", "headlight", "headlights", "taillight", "灯", "lampu")}


def roots(state):
    ids = {p["id"] for p in state["parts"]}
    return [p for p in state["parts"] if not p.get("parent") or p["parent"] not in ids]


def root_of(state, p):
    by = {q["id"]: q for q in state["parts"]}
    seen = set()
    while p.get("parent") in by and p["id"] not in seen:
        seen.add(p["id"])
        p = by[p["parent"]]
    return p


def kind_of(model, state):
    e = model.get("eng") or {}
    if e.get("kind") == "cad program":
        return "cad program"
    if e.get("cad_document"):
        return "CAD model (exact B-rep, from a three-view sheet)"
    sub = lab.subtree(state, model["id"])
    if any((q.get("eng") or {}).get("from_drawing") for q in sub):
        return "machine rebuilt from a drawing"
    if any(q["type"] == "mesh" for q in sub):
        return "imported mesh"
    return "parametric model" if model["type"] == "group" else f"single {model['type']} part"


def _bbox(parts):
    """World bounding box of a model's parts. The groups stay in the list: without them the parts' parent transforms
    (a CAD model's display scale) were lost, the box came out in the wrong frame, and arrange() threw a CAD car
    metres off the desk."""
    if not any(p["type"] != "group" for p in parts):
        return None, None
    lo, hi = geometry.bounds(parts)
    return np.asarray(lo, float), np.asarray(hi, float)


def local_bbox(state, model):
    """The model's bounding box in its OWN frame (what add_parts positions are relative to)."""
    sub = [p for p in lab.subtree(state, model["id"]) if p["id"] != model["id"]]
    if not sub:
        return None
    M = np.linalg.inv(geometry.world_matrix(model, {p["id"]: p for p in state["parts"]}))
    pts = []
    by = {p["id"]: p for p in state["parts"]}
    for p in sub:
        if p["type"] == "group":
            continue
        V, _ = geometry.world_mesh(p, by)
        if len(V):
            pts.append(V @ M[:3, :3].T + M[:3, 3])
    if not pts:
        return None
    P = np.vstack(pts)
    return P.min(0).round(1).tolist(), P.max(0).round(1).tolist()


def regions_of(state, model):
    out = set()
    for p in lab.subtree(state, model["id"]):
        out |= set(((p.get("params") or {}).get("region_names")) or [])
    return sorted(r for r in out if r)


def scene_summary(state, ctx):
    lines = []
    rs = roots(state)
    if not rs:
        lines.append("The desk is empty.")
    for m in rs:
        sub = lab.subtree(state, m["id"])
        parts = [p for p in sub if p["type"] != "group"]
        lo, hi = _bbox(sub)
        size = f"{(hi - lo)[0]:.0f} x {(hi - lo)[1]:.0f} x {(hi - lo)[2]:.0f} mm on the desk" if lo is not None else "empty"
        sc = (m.get("scale") or [1])[0]
        cols = sorted({p.get("color") for p in parts if p.get("color")})[:5]
        names = [p["name"] for p in parts][:30]
        regs = regions_of(state, m)
        lines.append(f"- MODEL \"{m['name']}\" (id {m['id']}): {kind_of(m, state)}; {len(parts)} part(s); {size}"
                     f"{'' if abs(sc - 1) < 1e-6 else f' (shown at {sc:.3g}x)'}; position {[round(v) for v in m['position']]}"
                     + (f"; colours {cols}" if cols else "") + (f"; regions {regs}" if regs else "")
                     + (f"; parts: {', '.join(names)}{' ...' if len(parts) > 30 else ''}" if m["type"] == "group" else ""))
    sel = state.get("selected")
    if sel:
        p = next((q for q in state["parts"] if q["id"] == sel), None)
        if p:
            lines.append(f"Selected: \"{p['name']}\" (id {p['id']}).")
    files = ctx.get("files") or []
    if files:
        lines.append("Project files: " + ", ".join(f"{f['name']} ({f['kind']})" for f in files[-15:]))
    att = ctx.get("attachments") or []
    if att:
        lines.append("Attached to THIS message: " + ", ".join(f"{f['name']} ({f['kind']})" for f in att))
    for j in (ctx.get("jobs") or {}).values():
        if j.get("state") == "running" and j.get("kind") == "cad_build":
            lines.append(f"Building in the background: {j['label']} (started {time.time() - j['t0']:.0f} s ago, takes about "
                         "2 minutes). It is not on the desk yet: it appears by itself when done.")
    pend = [(n, r) for n, r in INTAKE.items() if r.get("asked") and not r.get("answers")]
    for n, r in pend[-2:]:
        gaps = [g["what"] for g in ((r.get("assessment") or {}).get("missing") or [])]
        lines.append(f"Waiting to build '{n}': the user was asked about {gaps}. Their next message is probably the answer: "
                     "call build_from_drawing for that file with answers / assume.")
    have = [k for k, v in (ctx.get("have") or {}).items() if v]
    if have:
        lines.append("Available results: " + ", ".join(have))
    h = steps.listing()
    if h["steps"]:
        lines.append("Undo history (newest first): " + "; ".join(f"'{x['label']}' ({x['source']})" for x in h["steps"][:4]))
    else:
        lines.append("Undo history: empty.")
    return "CURRENT SCENE\n" + "\n".join(lines)


class Stopped(Exception):
    """The user pressed Stop: the turn ends now (what was done so far stays, as one undo step)."""


def _chat_call(payload, stopped, timeout=180):
    """Muse Spark, but Stop answers at once: the request runs in a thread and is abandoned when the user stops."""
    box = {}

    def run():
        try:
            box["r"] = agent._post("/chat/completions", payload, timeout=timeout)
        except Exception as e:                            # noqa: BLE001 - re-raised in the caller's thread
            box["e"] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    while t.is_alive():
        t.join(0.2)
        if stopped():
            raise Stopped()
    if "e" in box:
        raise box["e"]
    return box["r"]


def _program_job(ctx, cmd, **args):
    """A CAD-program job (build / edit / parameter re-run): on Modal CPU when deployed, else the local worker; Stop in
    the chat cancels it either way (cad_remote.program_job)."""
    import cad_remote
    step = ctx.get("on_step") or (lambda e: None)
    where = "Modal CPU (cloud)" if cad_remote.available() else "local CAD worker"
    eta = ("about 30 s" if cmd == "program_rerun" else
           f"usually {'10-20' if args.get('sheet') else '6-12'} min for {args.get('rounds', 3)} rounds")
    label = f"CAD job on {where}, {eta}"
    step({"stage": "tool", "tool": label})

    def progress(m):
        """The job's own progress lines as steps: each runs until the next one starts (so its time is that stage's),
        named by who does it: Muse Wonder plans and writes, the AETHER engine builds and checks, Muse Spark critiques."""
        m = str(m)
        if "Muse Wonder" in m or m.startswith("plan:"):
            who = "Muse Wonder"
        elif "critic" in m and "rendering" not in m:
            who = "Muse Spark (critic)"
        else:
            who = "AETHER engine · " + ("Modal CPU" if where.startswith("Modal") else "this computer")
        m = m.replace("Muse Wonder ", "").replace("Muse Wonder: ", "")
        step({"stage": "tool", "tool": m, "who": who})
    import contextlib
    try:
        with (ctx.get("unlocked") or contextlib.nullcontext)():     # the app stays editable while the job runs
            return cad_remote.program_job(cmd, stopped=ctx.get("stopped") or (lambda: False), on_progress=progress, **args)
    except cad_remote.Stopped:
        raise Stopped()
    finally:
        step({"stage": "done", "tool": label})


def _cad_call(ctx, cmd, wait_s=480, **args):
    """A CAD worker request that WAITS while a build or the detail pass holds the worker (failing after 45 s made the
    assistant fall back to boxes), shown as a step, and ends when the user presses Stop."""
    import cad_client
    stopped = ctx.get("stopped") or (lambda: False)
    t0, said = time.time(), False
    while True:
        try:
            return cad_client.call(cmd, timeout=2, **args)
        except cad_client.Busy:
            if stopped():
                raise Stopped()
            if time.time() - t0 > wait_s:
                raise
            if not said:
                (ctx.get("on_step") or (lambda e: None))({"stage": "tool", "tool": "waiting for the CAD worker"})
                said = True


def _await_details(state, ctx, m):
    """A CAD model whose detail pass (windows, lamps, grille: the body's named regions) is still running: wait for the
    worker, then bring the details in, so refining starts from the finished model and colours its real regions."""
    doc_id = (m.get("eng") or {}).get("cad_document")
    if not doc_id or not CAD_REIMPORT:
        return m
    job = (ctx.get("jobs") or {}).get("cad_detail") or {}
    if job.get("state") != "running":
        # the scene can lag the document (an old whole-scene undo put back a body from before the detail pass): the
        # document has built imprints (headlight, glass...) but the body on the desk has no regions -> bring them in
        if regions_of(state, m):
            return m
        try:
            import cad_client
            d = cad_client.call("document", timeout=5)
        except Exception:
            return m
        if d.get("document_id") != doc_id or not any("imprint" in f.get("op", "") and f.get("status") in ("ok", None)
                                                      for f in d.get("features") or []):
            return m
    else:
        d = _cad_call(ctx, "document")
    if d.get("document_id") == doc_id:
        CAD_REIMPORT(m["name"])
        m = next((q for q in roots(state) if (q.get("eng") or {}).get("cad_document") == d["document_id"]), m)
    return m


class Ambiguous(ValueError):
    def __init__(self, what, options):
        super().__init__(f"'{what}' matches more than one thing: {options}. Ask the user which one (ask_user).")
        self.options = options


def resolve(state, target, prefer_models=False):
    """A name / id / 'selected' / 'it' / 'all' -> list of parts (models are their root groups). Raises ValueError when
    nothing matches and Ambiguous when several different things match a vague reference."""
    t = str(target or "").strip()
    tl = t.lower()
    rs = roots(state)
    if tl in ("all", "everything", "scene"):
        return rs
    if tl in ("", "selected", "it", "this", "that", "the model", "model", "this model", "the object"):
        sel = next((p for p in state["parts"] if p["id"] == state.get("selected")), None)
        if sel is not None:
            return [root_of(state, sel) if (prefer_models or tl in ("the model", "model", "this model")) else sel]
        if len(rs) == 1:
            return rs
        if not rs:
            raise ValueError("the desk is empty")
        raise Ambiguous(t or "it", [m["name"] for m in rs])
    exact = [p for p in state["parts"] if p["id"] == t or p["name"].lower() == tl]
    if exact:
        models = [p for p in exact if p in rs]
        return models if (prefer_models and models) else exact
    words = [w for w in re.split(r"\W+", tl) if len(w) > 1]
    hits = [p for p in state["parts"] if tl in p["name"].lower()] or \
           [p for p in state["parts"] if words and all(w in p["name"].lower() for w in words)]
    if not hits:
        raise ValueError(f"nothing named '{t}' in the scene (models: {[m['name'] for m in rs]})")
    model_hits = [p for p in hits if p in rs]
    if prefer_models and model_hits:
        return model_hits
    return hits


def snapshot(state):
    return steps.snapshot(state)


def diff(before, state):
    """What actually changed in the scene (for the reply's 'What changed' list)."""
    def key(p):                                      # a CAD part re-imported after a CAD edit gets a new id: same part
        e = p.get("eng") or {}
        return ("cad", e["cad_document"], e["cad_component"]) if e.get("cad_document") and e.get("cad_component") else p["id"]
    b = {key(p): p for p in before["parts"]}
    a = {key(p): p for p in state["parts"]}
    out = []
    added = [a[i] for i in a if i not in b]
    removed = [b[i] for i in b if i not in a]
    if added:
        top = [p for p in added if p.get("parent") not in {q["id"] for q in added}]
        names = [p["name"] for p in added if p["type"] != "group"]
        for t in top:
            host = next((q for q in state["parts"] if q["id"] == t.get("parent")), None)
            n = len([p for p in lab.subtree(state, t["id"]) if p["type"] != "group"])
            out.append(f"Added {t['name']}" + (f" to {root_of(state, host)['name']}" if host else " to the desk")
                       + (f" ({n} parts)" if n > 1 else ""))
        if not top and names:
            out.append("Added " + ", ".join(names[:8]))
    if removed:
        top = [p for p in removed if p.get("parent") not in {q["id"] for q in removed}]
        out += [f"Removed {p['name']}" for p in top]
    fields = {"color": "colour", "region_colors": "region colour", "position": "position", "rotation": "rotation",
              "scale": "display size", "visible": "visibility",
              "name": "name", "params": "shape"}

    def same(k, x, y):                               # a CAD part's mesh changes with its features: say "CAD geometry"
        if k == "params" and x.get("type") == "cad":
            pa, pb = x.get("params") or {}, y.get("params") or {}
            return len(pa.get("faces") or []) == len(pb.get("faces") or []) and pa.get("region_names") == pb.get("region_names")
        return x.get(k) == y.get(k)
    for i in a:
        if i in b:
            ch = [("CAD geometry (new features)" if k == "params" and a[i].get("type") == "cad" else label)
                  for k, label in fields.items() if not same(k, a[i], b[i])]
            if ch:
                out.append(f"Changed {b[i]['name']}: " + ", ".join(ch))
    return out[:40]


# ------------------------------------------------------------------------------------------------ desk layout
DESK_W, DESK_D, MARGIN, GAP = 598.0, 336.0, 0.92, 20.0


def arrange(state, keep=None):
    """Every model stands on the desk (lowest point at z = 0), fits the sharp zone in height, and the models sit side by
    side along x inside the desk's width (one uniform display scale each; real sizes are untouched in eng)."""
    rs = [m for m in roots(state) if m.get("visible", True)]
    if not rs:
        return {}
    for m in rs:                                       # height: the sharp zone, as _fit_to_desk does for one model
        if m["type"] == "group":
            agent._fit_to_desk(state, m["id"])
        else:
            lab.place_on_base(state, m["id"], 0.0)
    boxes = {}
    for m in rs:
        lo, hi = _bbox(lab.subtree(state, m["id"]))
        if lo is not None:
            boxes[m["id"]] = (lo, hi)
    total = sum((hi - lo)[0] for lo, hi in boxes.values()) + GAP * (len(boxes) - 1)
    deep = max(((hi - lo)[1] for lo, hi in boxes.values()), default=0)
    k = min(1.0, MARGIN * DESK_W / max(total, 1e-6), MARGIN * DESK_D / max(deep, 1e-6))
    if k < 0.999:                                      # all together too wide or deep for the desk: shrink each
        for m in rs:
            if m["id"] in boxes:
                m["scale"] = [float(v) * k for v in m["scale"]]
        boxes = {m["id"]: _bbox(lab.subtree(state, m["id"])) for m in rs if m["id"] in boxes}
        total = sum((hi - lo)[0] for lo, hi in boxes.values()) + GAP * (len(boxes) - 1)
    x = -total / 2
    for m in rs:
        if m["id"] not in boxes:
            continue
        lo, hi = boxes[m["id"]]
        w = (hi - lo)[0]
        dx = x + w / 2 - (lo[0] + hi[0]) / 2
        dy = -(lo[1] + hi[1]) / 2
        m["position"] = [float(m["position"][0] + dx), float(m["position"][1] + dy), float(m["position"][2])]
        lab.place_on_base(state, m["id"], 0.0)
        x += w + GAP
    lab._bump(state)
    return {"models": len(boxes), "display_scale_applied": round(k, 3) if k < 0.999 else 1.0}


# ------------------------------------------------------------------------------------------------ tools
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.UAdd: operator.pos}
_FN = {k: getattr(math, k) for k in ("sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "log", "log10", "exp",
                                     "radians", "degrees", "floor", "ceil")}
_FN.update(abs=abs, round=round, min=min, max=max)
_CONST = {"pi": math.pi, "e": math.e}


def calculate(expression):
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name) and n.id in _CONST:
            return _CONST[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 1000:
                raise ValueError("exponent too large")
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FN and not n.keywords:
            return _FN[n.func.id](*[ev(x) for x in n.args])
        raise ValueError(f"not allowed in a calculation: {ast.dump(n)[:60]}")
    expr = str(expression).replace("^", "**").replace("×", "*").replace("÷", "/")
    v = ev(ast.parse(expr, mode="eval"))
    if isinstance(v, float):
        v = float(f"{v:.12g}")                         # 3 * 25.4 = 76.2, not 76.19999999999999
        if v.is_integer() and abs(v) < 1e15:
            v = int(v)
    return {"expression": expression, "result": v}


def web_search(query):
    t = time.time()
    r = agent._post("/responses", {"model": agent.MODEL, "input": query, "tools": [{"type": "web_search"}]}, timeout=120)
    text, sources = [], []
    for item in r.get("output") or []:
        if item.get("type") != "message":
            continue
        for c in item.get("content") or []:
            if c.get("type") == "output_text":
                text.append(c.get("text") or "")
                for a in c.get("annotations") or []:
                    if a.get("type") == "url_citation" and a.get("url") not in {s["url"] for s in sources}:
                        sources.append({"title": a.get("title") or a.get("url"), "url": a.get("url")})
    return {"answer": "\n".join(text).strip()[:4000], "sources": sources[:8], "s": round(time.time() - t, 1)}


def refine_facts(state, m):
    """What a refine needs: the model's real size, its front and the meaning of attach's sides, and the CAD features
    its body already has."""
    V, _, _ = refine.model_mesh(state, m)
    out = {}
    if len(V):
        out["size_mm"] = [round(float(x)) for x in V.max(0) - V.min(0)]
    f = snap.front_axis(m)
    out["front"] = ("the -x end (a CAD vehicle's nose)" if f[0] < -0.5 else "the -y side" if f[1] < -0.5 else str(f.tolist()))
    out["sides_for_attach"] = "front, rear, left (the model's own left), right, top, bottom, inside"
    doc_id = (m.get("eng") or {}).get("cad_document")
    if doc_id:
        try:
            import cad_client
            d = cad_client.call("document", timeout=20)
            if d.get("document_id") == doc_id:
                out["cad_features"] = [f["label"] for f in d["features"] if f.get("label") and f.get("status") in ("ok", None)
                                       and any(w in f["op"] for w in ("imprint", "pocket", "mirror", "exhaust", "cut"))][:40]
                out["cad_features_editable"] = True
            else:
                out["cad_features_editable"] = False
        except Exception as e:
            out["cad_features_note"] = f"CAD worker not reachable ({type(e).__name__})"
    return out


def inspect(state, ctx, target):
    hits = resolve(state, target, prefer_models=True)
    out = []
    for m in hits[:3]:
        m = _await_details(state, ctx, m)
        sub = lab.subtree(state, m["id"])
        parts = [p for p in sub if p["type"] != "group"]
        lo, hi = _bbox(sub)
        info = {"name": m["name"], "id": m["id"], "kind": kind_of(root_of(state, m), state), "parts": len(parts),
                "desk_bbox_mm": [lo.round(1).tolist(), hi.round(1).tolist()] if lo is not None else None,
                "own_frame_bbox_mm": local_bbox(state, m) if m["type"] == "group" else None,
                "display_scale": (m.get("scale") or [1])[0], "regions": regions_of(state, m),
                "part_list": [{"name": p["name"], "type": p["type"], "color": p.get("color"),
                               "kind": (p.get("eng") or {}).get("kind")} for p in parts[:60]]}
        e = (root_of(state, m).get("eng") or {})
        if e.get("kind") == "cad program":              # its source: the program Muse wrote, its version and its checks
            pf = Path(e["program"]).with_name("params.json")
            info["parameters"] = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else {}
            plf = Path(e["program"]).with_name("plan.json")
            if plf.exists():                              # what the evidence cannot determine, and the declared relations
                pl = json.loads(plf.read_text(encoding="utf-8"))
                info["unknowns"] = pl.get("unknowns") or []
                info["constraints"] = pl.get("constraints") or []
            info["cad_program"] = {"version": e.get("version"), "built_from": "drawing + request" if e.get("sheet") else "request",
                                   "request": e.get("request"), "length_mm": e.get("length_mm"),
                                   "program_excerpt": Path(e["program"]).read_text(encoding="utf-8")[:3000]}
            try:
                rep = json.loads(Path(e["report"]).read_text(encoding="utf-8"))
                info["cad_program"]["checks"] = {k: (rep.get("best") or {}).get(k) for k in ("iou", "mean_iou", "round")}
            except (OSError, ValueError):
                pass
        elif m["type"] == "group":
            info.update(refine_facts(state, m))
        asm = (ctx.get("asm") or {}).get("summary")
        if asm and m["type"] == "group":
            info["brep_check"] = {k: asm.get(k) for k in ("valid_solids", "built", "mates_satisfied", "mates", "interferences")}
        out.append(info)
    return {"models": out}


def _color(c):
    names = {"blue": "#2f6fe0", "red": "#d23b3b", "green": "#2fa84f", "yellow": "#f2c230", "black": "#151515",
             "white": "#f4f4f4", "grey": "#8a8f98", "gray": "#8a8f98", "silver": "#c4cbd4", "orange": "#f08a24",
             "purple": "#8a4fd8", "pink": "#ef6fa8", "cyan": "#2ec4d6", "gold": "#d4a72c", "brown": "#7a4b2a",
             "biru": "#2f6fe0", "merah": "#d23b3b", "hijau": "#2fa84f", "hitam": "#151515", "putih": "#f4f4f4",
             "蓝": "#2f6fe0", "蓝色": "#2f6fe0", "红": "#d23b3b", "红色": "#d23b3b", "绿": "#2fa84f", "绿色": "#2fa84f",
             "黑": "#151515", "黑色": "#151515", "白": "#f4f4f4", "白色": "#f4f4f4", "黄": "#f2c230", "黄色": "#f2c230"}
    c = str(c).strip()
    return retina.hex_color(names.get(c.lower(), c))


def match_regions(names, key):
    """The named regions of a CAD body a request means: exact ("tail light"), a group ("light" = every lamp region:
    headlight, tail light ...), or a synonym ("windows" = glass)."""
    k = str(key or "").lower().strip()
    names = [str(n).lower() for n in names or []]
    if k in names:
        return [k]
    hit = [n for n in names if k and (k in n or n in k)]
    if hit:
        return hit
    for base, words in REGION_WORDS.items():
        if k == base or k in words:
            return [n for n in names if base in n or (base == "light" and "lamp" in n)]
    return []


def modify(state, target, color=None, region=None, move_by=None, position=None, rotation=None, scale_by=None,
           visible=None, new_name=None, params=None):
    tl = str(target).lower()
    region_key = region.lower().strip() if region else None
    try:
        hits = resolve(state, target)
    except Ambiguous:
        raise
    except ValueError:
        # "the window" / "the tail lights" with no part of that name: a CAD body region
        if not region_key:
            region_key = next((k for k, w in REGION_WORDS.items() if any(x in tl for x in w)), None)
            for m in roots(state):                     # a region named in the target itself ("tail light")
                region_key = next((r for r in regions_of(state, m) if r in tl), region_key)
        if not region_key:
            raise
        hits = [m for m in roots(state) if match_regions(regions_of(state, m), region_key)]
        if not hits:
            raise ValueError(f"no part named '{target}' and no model with a '{region_key}' region")
    changed = []
    for p in hits:
        if region_key and color:
            bodies = [q for q in lab.subtree(state, root_of(state, p)["id"])
                      if match_regions((q.get("params") or {}).get("region_names"), region_key)]
            if not bodies:
                raise ValueError(f"{p['name']} has no '{region_key}' region (regions: {regions_of(state, root_of(state, p))})")
            for q in bodies:
                rc = dict(q.get("region_colors") or {})
                for nm in match_regions(q["params"]["region_names"], region_key):
                    rc[nm] = _color(color)
                    changed.append(f"{q['name']} {nm} -> {rc[nm]}")
                q["region_colors"] = rc
            continue
        kw = {}
        if color:
            kw["color"] = _color(color)
        if position is not None:
            kw["position"] = position
        if move_by is not None:
            kw["position"] = [float(a) + float(b) for a, b in zip(p["position"], move_by)]
        if rotation is not None:
            kw["rotation"] = rotation
        if scale_by is not None:
            kw["scale"] = [float(v) * float(scale_by) for v in p["scale"]]
        if visible is not None:
            kw["visible"] = visible
        if new_name:
            kw["name"] = new_name
        if params:
            kw["params"] = params
        if color and p["type"] == "group":           # colouring a model = colouring its parts
            for q in lab.subtree(state, p["id"]):
                if q["type"] != "group":
                    q["color"] = kw["color"]
            kw.pop("color")
        if kw:
            lab.update_part(state, p["id"], **kw)
            changed.append(f"{p['name']}: {', '.join(kw)}")
    lab._bump(state)
    if scale_by is not None or move_by is not None or position is not None:
        for m in {root_of(state, p)["id"] for p in hits}:
            lab.place_on_base(state, m, 0.0)
    return {"changed": changed}


def remove(state, target):
    hits = resolve(state, target)
    if len(hits) > 1 and len({root_of(state, p)["id"] for p in hits}) > 1 and str(target).lower() not in ("all", "everything"):
        raise Ambiguous(target, [p["name"] for p in hits][:6])
    names = []
    for p in hits:
        if any(q["id"] == p["id"] for q in state["parts"]):
            names.append(p["name"])
            lab.delete_part(state, p["id"])
    return {"removed": names}


def _model_state(state, target):
    hits = resolve(state, target, prefer_models=True)
    ids = set()
    for h in hits:
        ids |= {p["id"] for p in lab.subtree(state, h["id"])}
    return {**state, "parts": [p for p in state["parts"] if p["id"] in ids]}, hits


def _real_size(sub):
    """The models at their REAL size for a file (a desk shows each one at a display scale: the 4.5 m car is 0.55 m
    there; an independent check of the exports found the files carried the display size). Each model's group keeps
    its rotation, loses its display scale and stands at the origin on z = 0; parts are untouched."""
    parts = [dict(p) for p in sub["parts"]]
    ids = {p["id"] for p in parts}
    for p in parts:
        if p["type"] == "group" and p.get("parent") not in ids:
            p["scale"], p["position"] = [1.0, 1.0, 1.0], [0.0, 0.0, 0.0]
    out = {**sub, "parts": parts}
    lo, _ = geometry.bounds(parts)
    for p in parts:
        if p["type"] == "group" and p.get("parent") not in ids:
            p["position"] = [0.0, 0.0, -float(lo[2])]
    return out


def _slug(s):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_")[:40] or "model"


def export_model(state, ctx, target, format):
    sub, hits = _model_state(state, target)
    name = _slug(hits[0]["name"] if len(hits) == 1 else "aether_scene")
    out = Path(ctx["exports_dir"])
    out.mkdir(parents=True, exist_ok=True)
    from engine import export as ex
    if format != "step":
        sub = _real_size(sub)
    if format == "glb":
        f = out / f"{name}.glb"
        f.write_bytes(ex.glb(sub))
    elif format == "stl":
        f = out / f"{name}.stl"
        f.write_bytes(ex.stl(sub))
    elif format == "3mf":
        f = out / f"{name}.3mf"
        f.write_bytes(ex.three_mf(sub))
    elif format == "step":
        import cad_client
        f = out / f"{name}.step"
        r = cad_client.call("export_parts", timeout=45, parts=_with_heavy(sub["parts"], ctx), kind="step", path=str(f),
                            cad_brep_dir=str(ctx["cad_brep_dir"]), title=hits[0]["name"])
        if r.get("left_out"):
            ctx.setdefault("notes", []).append(f"not in the STEP (no exact B-rep): {[x['name'] for x in r['left_out']][:8]}")
    else:
        raise ValueError(f"unknown format {format}")
    return _download(ctx, f, f"{hits[0]['name'] if len(hits) == 1 else 'Scene'} · {format.upper()}")


DENSITY = (("steel", 7.85), ("iron", 7.2), ("alumin", 2.7), ("brass", 8.5), ("copper", 8.96), ("titan", 4.5),
           ("glass", 2.5), ("rubber", 1.1), ("tyre", 1.1), ("tire", 1.1), ("plastic", 1.2), ("abs", 1.05), ("nylon", 1.15),
           ("pla", 1.24), ("wood", 0.6), ("carbon", 1.6), ("foam", 0.05), ("seat", 0.15), ("leather", 0.9))


def analyze(state, target, material=None):
    """Mass properties of a model or part in its real millimetres (model frame): volume, surface, mass (density from
    each part's material / name, steel when unknown, or the material the user names), centre of mass, size."""
    from engine import export as ex
    hits = resolve(state, target, prefer_models=True)
    if len(hits) != 1:
        raise Ambiguous(target, [h["name"] for h in hits])
    m = root_of(state, hits[0])
    pick = {p["id"] for p in lab.subtree(state, hits[0]["id"])}
    ms = [(p, V, F) for p, V, F, _ in snap.model_meshes(state, m) if p["id"] in pick and p["type"] != "group"]
    dens, assumed = {}, []
    for p, _, _ in ms:
        key = (material or ((p.get("eng") or {}).get("material") or "") + " " + p["name"]).lower()
        rho = next((d for w, d in DENSITY if w in key), None)
        if rho is None:
            rho = 7.85
            assumed.append(p["name"])
        dens[p["id"]] = rho
    r = ex.analyze(ms, dens)
    r["parts"] = sorted(r["parts"], key=lambda x: -x["mass_g"])[:25]
    if assumed:
        r["density_assumed_steel_for"] = assumed[:12]
    if r["open_meshes"]:
        r["note"] = "open (not watertight) meshes: their volume and mass are approximate"
    if (m.get("eng") or {}).get("cad_document"):
        r["note_cad"] = "a drawn CAD body is a SOLID (no cabin, no panels): its mass is that of a solid block, not a car"
    return r


def _with_heavy(parts, ctx):
    restore = ctx.get("restore")
    return restore(parts) if restore else parts


def _download(ctx, f, label):
    d = {"name": f.name, "label": label, "url": f"/api/files/{f.parent.name}/{f.name}", "bytes": f.stat().st_size}
    ctx.setdefault("downloads", []).append(d)
    return {"file": f.name, "bytes": d["bytes"], "shown_as": "download card in the chat"}


def make_drawing(state, ctx, target, title=None):
    import cad_client
    sub, hits = _model_state(state, target)
    name = _slug(hits[0]["name"])
    out = Path(ctx["exports_dir"])
    out.mkdir(parents=True, exist_ok=True)
    r = cad_client.call("export_parts", parts=_with_heavy(sub["parts"], ctx), kind="drawing", path=str(out / f"{name}_drawing"),
                        cad_brep_dir=str(ctx["cad_brep_dir"]), title=title or hits[0]["name"], timeout=45)
    for f, lab_ in ((r["pdf"], "Drawing · PDF"), (r["svg"], "Drawing · SVG")):
        _download(ctx, Path(f), f"{hits[0]['name']} · {lab_}")
    ctx.setdefault("images", {})["drawing"] = r["png_data_url"]
    return {"views": r["views"], "solids": r["solids"], "left_out": r.get("left_out", []), "size_mm": r["size_mm"],
            "note": "orthographic views of the exact B-rep with hidden lines (dashed); dimensions are the model's own mm"}


def undo(state, to=None):
    """The project's history (history.py): the newest step, or step `to` with what builds on it."""
    return steps.undo(state, to)


def _file(ctx, name):
    files = (ctx.get("attachments") or []) + (ctx.get("files") or [])
    f = next((x for x in files if x["name"] == name), None) or \
        next((x for x in files if name.lower() in x["name"].lower()), None)
    if not f:
        raise ValueError(f"no file '{name}' (files: {[x['name'] for x in files]})")
    return f


def import_file(state, ctx, file, name=None):
    f = _file(ctx, file)
    path = Path(f["path"])
    ext = path.suffix.lower()
    before = {m["id"] for m in roots(state)}
    if ext in (".stl", ".obj", ".glb", ".gltf"):
        from engine import meshio
        V, F = meshio.load(path)
        r = lab.import_mesh(state, name or path.stem, V.ravel().tolist(), F.ravel().tolist(), size_mm=0)
    elif ext in (".step", ".stp"):
        import cad_client
        m = cad_client.call("import_step", path=str(path), timeout=45)
        r = lab.import_cad(state, m["meshes"], m["groups"], name or path.stem, m["document_id"], replace=False,
                           provenance={"source": path.name})
    else:
        raise ValueError(f"{path.name}: use build_from_drawing for drawings and photos; 3D files: glb, gltf, stl, obj, step")
    new = [m for m in roots(state) if m["id"] not in before]
    arrange(state)
    return {"imported": [m["name"] for m in new], **{k: v for k, v in (r or {}).items() if k in ("parts", "faces")}}


INTAKE = {}                  # file name -> the drawing check (intake.assess), whether the user was asked, their answers


def build_from_drawing(state, ctx, file, kind="auto", hint=None, answers=None, assume=False):
    """The gate (in code, not only in the prompt): a drawing is checked first (intake.assess). With a critical gap and
    the user not asked yet, nothing is built: the question goes to the user (ends the turn). After an answer (or
    "assume") the build runs with what the user said (a real length becomes the CAD document's decision)."""
    import intake
    f = _file(ctx, file)
    url = ctx["data_url"](f)
    rec = INTAKE.get(f["name"])
    answers = {k: v for k, v in (answers or {}).items() if v not in (None, "", 0)}
    if rec is None:
        step = ctx.get("on_step") or (lambda e: None)
        step({"stage": "tool", "tool": "check_drawing"})
        try:
            rec = INTAKE[f["name"]] = {"assessment": intake.assess(url, ctx.get("user_text", "")), "asked": False}
            step({"stage": "done", "tool": "check_drawing"})
        except Exception as e:                       # the check failed: build, and say the check could not run
            rec = INTAKE[f["name"]] = {"assessment": None, "asked": False, "error": f"{type(e).__name__}: {e}"[:200]}
            step({"stage": "done", "tool": "check_drawing", "error": rec["error"]})
    a = rec.get("assessment")
    if a and not a["ready"] and not rec["asked"] and not answers and not assume:
        q = intake.question_for(a)
        rec["asked"] = True
        return {"built": [], "checked": {"object": a["object"], "views": a["views"], "missing": a["missing"]},
                "_ask": {"question": q["question"], "options": q["options"]},
                "note": "not built yet: the user is asked for the missing information first"}
    rec["answers"] = {**(rec.get("answers") or {}), **answers}
    decisions = None
    L = rec["answers"].get("overall_length_mm")
    if L:
        decisions = {"overall_length_mm": {"value": float(L), "provenance": "user", "note": "given by the user"}}
    hint = hint or rec["answers"].get("object") or (a or {}).get("object") or ""
    if kind != "part":                                 # every drawing goes to the AI-written CAD program (no recipes)
        facts = []
        if L:
            facts.append(f"The user says the real overall length is {float(L):.0f} mm (provenance 'user').")
        for k_, v_ in rec["answers"].items():
            if k_ != "overall_length_mm":
                facts.append(f"The user says {k_}: {v_}.")
        if a:
            gaps = [g["what"] for g in a["missing"] if not (L and g["what"].lower().startswith(("size", "scale", "real", "dimension", "overall")))]
            if gaps:
                facts.append("The drawing check found these gaps; state them as unknowns or assumptions: " + "; ".join(gaps))
        out = build_cad(state, ctx, description=" ".join(x for x in [hint] + facts if x) or None, file=file, _gated=True)
        if a:
            out["drawing_check"] = {"object": a.get("object"), "views": a.get("views"), "missing": [g["what"] for g in a["missing"]]}
        return out
    measured = (a or {}).get("kind_measured")
    if START_CAD_JOB and (kind == "three_view" or (kind == "auto" and measured == "three_view")):
        # the CAD pipeline takes about 2 minutes: it runs in the background and the user keeps working meanwhile
        job = START_CAD_JOB(url, hint, decisions, f["name"])
        out = {"started_in_background": True, "model": job["model"], "takes": "about 2 minutes",
               "note": "the model appears on the desk by itself when it is done (with a message in the chat); the "
                       "user can keep working meanwhile. Do not say it is built yet."}
        if a:
            still = [g["what"] for g in a["missing"] if not (L and g["what"].lower().startswith(("size", "scale", "real", "dimension", "overall")))]
            if still:
                out["will_assume"] = still
        return out
    before = {m["id"] for m in roots(state)}
    keep = [p for p in state["parts"]]
    reply, trace, images, _ = agent.photo_to_design(state, [], url, hint, 80.0, ctx["out_dir"], ctx.get("on_step"),
                                                    "interpret", kind if kind in ("auto", "machine", "three_view", "part") else "auto",
                                                    decisions=decisions)
    # a build path that still clears the scene must not cost the user their other models: put them back
    have = {p["id"] for p in state["parts"]}
    state["parts"] = [p for p in keep if p["id"] not in have] + state["parts"]
    arrange(state)
    ctx.setdefault("images", {}).update(images)
    ctx.setdefault("trace_extra", []).extend(trace)
    new = [m for m in roots(state) if m["id"] not in before]
    for m in new:                                    # each model knows its own source drawing (Explain shows it)
        m.setdefault("eng", {})["source_file"] = f["name"]
    out = {"built": [m["name"] for m in new], "summary": (reply or "")[:1500]}
    if a:
        still = [g["what"] for g in a["missing"] if not (g["what"].lower().startswith(("size", "scale", "real", "dimension"))
                                                          and L)]
        if still:
            out["assumed_because_missing"] = still
        if L:
            out["size_from_user_mm"] = L
    return out


def explain_target(state, ctx, target=None):
    """Which model Explain is about and what it is grounded in: the named model, else the selected one, else the newest
    on the desk; its OWN source drawing (recorded when it was built), whether its real size is known, its CAD
    features. -> (sub-scene with that model only, model, image data URL or None, scale, cad feature labels)."""
    rs = roots(state)
    if not rs:
        raise ValueError("the desk is empty: there is no model to explain")
    if target and str(target).lower() not in ("selected", "it", "this", "all", "the model", "model"):
        hits = resolve(state, target, prefer_models=True)
        m = root_of(state, hits[0])
    else:
        sel = next((p for p in state["parts"] if p["id"] == state.get("selected")), None)
        m = root_of(state, sel) if sel is not None else rs[-1]
    ids = {p["id"] for p in lab.subtree(state, m["id"])}
    sub = {**state, "parts": [p for p in state["parts"] if p["id"] in ids]}
    eng = m.get("eng") or {}
    image = None
    if eng.get("source_file"):
        f = next((x for x in ctx.get("files") or [] if x["name"] == eng["source_file"]), None)
        if f and ctx.get("data_url"):
            try:
                image = ctx["data_url"](f)
            except Exception:
                image = None
    elif agent.LAST_IMAGE.get("data_url") and m["id"] == agent.LAST_IMAGE.get("model_id"):
        image = agent.LAST_IMAGE["data_url"]
    scale = {"known": False, "source": "no dimension given"}
    feats = None
    if eng.get("cad_document"):
        facts_ = refine_facts(state, m)
        feats = facts_.get("cad_features")
        try:
            import cad_client
            d = cad_client.call("document", timeout=20)
            if d.get("document_id") == eng["cad_document"]:
                L = (d.get("decisions") or {}).get("overall_length_mm") or {}
                if L.get("provenance") not in (None, "assumed"):
                    scale = {"known": True, "source": f"overall length {L.get('value')} mm given by the user"}
                else:
                    scale = {"known": False, "source": f"overall length {L.get('value')} mm assumed"}
        except Exception:
            pass
    elif agent.LAST_REPORT.get("scale_known") and m["id"] == agent.LAST_IMAGE.get("model_id"):
        scale = {"known": True, "source": agent.LAST_REPORT.get("scale_source")}
    return sub, m, image, scale, feats


def explain_machine(state, ctx, target=None):
    import explain as ex
    sub, m, image, scale, feats = explain_target(state, ctx, target)
    res = ex.explain(sub, image, on_step=ctx.get("on_step"), scale=scale, model=m, cad_features=feats)
    ctx["explain"] = res
    return {"machine": res.get("machine"), "model": m["name"], "subsystems": [x["name"] for x in res["subsystems"]],
            "steps": [x["title"] for x in res.get("steps", [])], "shown_as": "the Explain panel is open in the app"}


def _finish(spec):
    """A plain box becomes a rounded box (rbox): added and new parts get the finish of a made part, not a toy block."""
    if spec.get("type") == "box":
        pr = spec.get("params") or {}
        w, d, h = (float(pr.get(k, 10)) for k in ("w", "d", "h"))
        spec = {**spec, "type": "rbox", "params": {"w": w, "d": d, "h": h, "r": 0.14 * min(w, d, h)}}
    return spec


def _outline_size(spec):
    """The outline (width along u, height along v, mm) of a surface detail given as a part, and its shape."""
    pr = spec.get("params") or {}
    t = spec.get("type")
    if t in ("cylinder", "cone", "sphere", "tube", "torus"):
        r = float(pr.get("radius") or pr.get("outer") or pr.get("r_bottom") or 50)
        return 2 * r, 2 * r, "ellipse"
    w = float(pr.get("w") or pr.get("width") or pr.get("length") or 200)
    h = float(pr.get("d") or pr.get("height") or pr.get("h") or 100)
    nm = spec.get("name", "").lower()
    return w, h, "ellipse" if any(k in nm for k in ("round", "oval", "circle", "ellipse")) else "rect"


def add_parts(state, ctx, m, specs):
    """Parts onto an existing model, the model itself never moved or rescaled:
    - vehicle interior parts by slot (refine.slot: placed and sized from the car), shrunk to fit inside if needed;
    - surface details (lamp, plate, grille ...) as panels that follow the real surface (refine.surface_patch), and
      refused where the body already has that region (it is recoloured instead);
    - everything else by attach on the real surface (refine.place) or inside, with the shaped part types.
    Checked and pictured."""
    m = _await_details(state, ctx, m)
    made, skipped, failed, placed, inside = [], [], [], [], set()
    ids = {}
    have = {p["name"].lower() for p in lab.subtree(state, m["id"])}
    mesh = refine.model_mesh(state, m)
    regions = regions_of(state, m)
    Rg = snap.model_rotation(state, m)
    veh, used_slots = None, set()
    for spec in specs:
        spec = _finish(dict(spec))
        nm = str(spec.get("name", "")).strip()
        if nm.lower() in have:
            skipped.append(nm)                                 # already in the model: no duplicate (use modify)
            continue
        at = dict(spec.get("attach") or {})
        if at.get("side") == "inside" and not at.get("slot"):
            # a vehicle's interior part goes to its measured place, whatever fractions were guessed (seats came out one
            # behind the other, or half through the door)
            if veh is None:
                veh = refine.vehicle(state, m) or False
            sl = refine.slot_for(nm, spec.get("type")) if veh else None
            if sl and sl not in used_slots:
                at = {"slot": sl}
        if at.get("slot"):
            used_slots.add(at["slot"])
        pos, rot = spec.get("position", [0, 0, 0]), spec.get("rotation", [0, 0, 0])
        try:
            if at.get("slot"):
                if veh is None:
                    veh = refine.vehicle(state, m) or False
                P, Rm, prm, info = refine.slot(state, m, at["slot"], spec, veh or None)
                spec["params"] = prm
                pos, rot = [float(c) for c in P], refine.euler_zyx(Rm)
                placed.append({"part": nm, **info})
            elif at.get("side") in refine.SIDES and refine.is_surface_detail(nm):
                key = next((w for w in ("glass", "window", "windshield", "headlight", "tail light", "light", "lamp")
                            if w in nm.lower()), None)
                hit = match_regions(regions, key) if key else []
                # any region already made for the same thing (a grille, a plate) on the same end of the model
                words = [w for w in re.findall(r"[a-z]+", nm.lower()) if w not in ("left", "right", "front", "rear",
                                                                                 "back", "number", "the", "of", "and")]
                end = next((e for e in ("front", "rear") if e in nm.lower()), None)
                hit = hit or [r for r in regions if any(w in r for w in words) and (not end or end in r or
                                                                                    not any(e in r for e in ("front", "rear")))]
                if hit:
                    failed.append({"part": nm, "error": f"the body already has the region(s) {hit} for this: colour them "
                                                        f"with modify(target=model, region='{hit[0]}', color=...)"})
                    continue
                w, h, shape = _outline_size(spec)
                lamp = any(k in nm.lower() for k in ("light", "lamp"))
                V, F = refine.surface_patch(state, m, at["side"], float(at.get("u", 0.5)), float(at.get("v", 0.5)), w, h,
                                            shape, proud=float(at.get("proud_mm") or (4.0 if lamp else 3.0)),
                                            bulge=float(np.clip(0.06 * min(w, h), 3, 14)) if lamp else 0.0, mesh=mesh)
                spec = {**spec, "type": "mesh", "params": {"vertices": V.round(3).ravel().tolist(), "faces": F.ravel().tolist()}}
                pos, rot = [0, 0, 0], [0, 0, 0]
                placed.append({"part": nm, "side": at["side"], "as": f"surface panel {w:.0f} x {h:.0f} mm following the body"})
            elif at:
                if not at.get("side"):
                    raise ValueError("attach needs a slot (vehicles) or a side")
                pos, rot, info = refine.place(state, m, spec, mesh)
                placed.append({"part": nm, **info})
            elif len(mesh[0]):
                raise ValueError("no attach: parts of an existing model are placed with attach")
        except (ValueError, KeyError, TypeError) as e:
            failed.append({"part": nm, "error": str(e)[:300]})
            continue
        have.add(nm.lower())
        parent = ids.get(spec.get("parent")) or m["id"]
        if at and parent == m["id"] and not np.allclose(Rg, np.eye(3)):
            # placed in the upright model frame -> the model group's own frame (a turned group: drawn machines)
            pos = (Rg.T @ np.asarray(pos, float)).tolist()
            if spec["type"] == "mesh":
                Vm = np.asarray(spec["params"]["vertices"], float).reshape(-1, 3) @ Rg
                spec["params"] = {**spec["params"], "vertices": Vm.round(3).ravel().tolist()}
            else:
                rot = refine.euler_zyx(Rg.T @ geometry._rot(rot))
        try:
            r = lab.add_part(state, spec["type"], spec.get("params"), nm, pos, rot, spec.get("scale", [1, 1, 1]), parent,
                             1.0, spec.get("color"))
        except Exception as e:
            failed.append({"part": nm, "error": f"{type(e).__name__}: {e}"[:300]})
            continue
        ids[nm] = r["id"]
        if spec["type"] == "mesh":                           # a surface panel: the renderer draws it over its surface
            part = next(q for q in state["parts"] if q["id"] == r["id"])
            part["eng"] = {"kind": "surface_panel", "on": at.get("side"), "dims": {}, "joints": []}
        if at.get("side") == "inside" or (at.get("slot") and at["slot"] in refine.SLOTS):
            inside.add(r["id"])
        made.append(r["name"])
    for pid in inside:                                       # inside means inside: shrink what pokes through
        part = next(p for p in state["parts"] if p["id"] == pid)
        share, k = refine.fit_inside(state, m, part, veh or None)
        if k < 1:
            next((x for x in placed if x["part"] == part["name"]), {})["shrunk_to_fit"] = round(k, 2)
        if share < 0.9:
            next((x for x in placed if x["part"] == part["name"]), {})["inside_share"] = round(share, 2)
    state["selected"] = m["id"]
    lab._bump(state)
    issues = refine.checks(state, m, set(ids.values()), inside) if ids else []
    out = {"model": m["name"], "added": made, "placed": placed[:30]}
    if skipped:
        out.update(not_added_already_exist=skipped, hint="these names are already in the model: use modify")
    if failed:
        out["not_added"] = failed
    out["checks"] = issues or "no problems found"
    if inside:
        out["note"] = "parts inside a closed body are hidden: tell the user (section view or hiding the body shows them)"
    if ids:
        out["_look"] = refine.look(state, m, highlight=list(ids.values()), section=bool(inside))
    return out


def _outline(f, lo, hi):
    """One feature's outline (u, v on a side, as attach) -> its view and polygon in the CAD document's mm.
    front / rear: plane (y, z), u = the model's left (-y) -> right (+y); left / right: plane (x, z), u = rear (+x) ->
    front (-x); top: plane (x, y), u = rear -> front, v = left -> right."""
    side = f["side"]

    def to_plane(uu, vv):
        uu, vv = float(np.clip(uu, 0, 1)), float(np.clip(vv, 0, 1))
        if side in ("front", "rear"):
            return lo[1] + uu * (hi[1] - lo[1]), lo[2] + vv * (hi[2] - lo[2])
        x = hi[0] - uu * (hi[0] - lo[0])
        if side == "top":
            return x, lo[1] + vv * (hi[1] - lo[1])
        return x, lo[2] + vv * (hi[2] - lo[2])
    shape = f.get("shape") or "rect"
    if shape == "polygon":
        pts = f.get("points") or []
        if len(pts) < 3:
            raise ValueError(f"{f['name']}: polygon needs at least 3 [u, v] points")
        return [list(to_plane(a, b)) for a, b in pts]
    if not f.get("width_mm") or not f.get("height_mm"):
        raise ValueError(f"{f['name']}: rect / ellipse need width_mm and height_mm (real millimetres)")
    cx, cy = to_plane(f.get("u", 0.5), f.get("v", 0.5))
    w, h = float(f["width_mm"]) / 2, float(f["height_mm"]) / 2
    if shape == "ellipse":
        return [[cx + w * math.cos(t), cy + h * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
    return [[cx - w, cy - h], [cx + w, cy - h], [cx + w, cy + h], [cx - w, cy + h]]


SIDE_VIEW = {"front": "front", "rear": "rear", "left": "side", "right": "side", "top": "top"}


def cad_feature(state, ctx, model, features):
    """Imprints / pockets on a CAD model's body (cad worker add_feature, one recompute for all), outlines given like
    attach and converted here to the view planes in the CAD document's millimetres; the model is then re-imported in
    place (same model, same pose, colours kept) and the new regions get their colours."""
    hits = resolve(state, model, prefer_models=True)
    if len(hits) != 1:
        raise Ambiguous(model, [h["name"] for h in hits])
    m = root_of(state, hits[0])
    doc_id = (m.get("eng") or {}).get("cad_document")
    body = next((p for p in lab.subtree(state, m["id"]) if (p.get("eng") or {}).get("kind") == "body_shell"), None)
    if not doc_id or body is None:
        raise ValueError(f"{m['name']} is not a CAD body: use add_parts with attach")
    if snap.front_axis(m)[0] > -0.5:
        raise ValueError("cad_feature needs a CAD vehicle body (front at -x)")
    V = np.asarray(body["params"]["vertices"], float).reshape(-1, 3)      # the CAD document's own mm
    lo, hi = V.min(0), V.max(0)
    specs, bad, colors = [], [], {}
    for f in features[:12]:
        try:
            poly = _outline(f, lo, hi)
        except (ValueError, KeyError, TypeError) as e:
            bad.append({"region": f.get("name"), "error": str(e)[:300]})
            continue
        nm = str(f["name"]).strip().lower()[:40]
        specs.append({"op": f["op"], "view": SIDE_VIEW[f["side"]], "polygons": [poly], "region": nm,
                      "material": "light" if any(w in nm for w in ("lamp", "light")) else "panel",
                      "depth_mm": f.get("depth_mm")})
        if f.get("color"):
            colors[nm] = _color(f["color"])
    if not specs:
        return {"added": [], "not_added": bad}
    m = _await_details(state, ctx, m)
    r = _cad_call(ctx, "add_feature", document_id=doc_id, features=specs)
    out = {"added": [x["label"] for x in r.get("added", [])], "seconds": r.get("seconds")}
    if r.get("added"):                               # undo takes these out of the CAD document again; redo puts them back
        keep = {x["region"] for x in r["added"]}
        h = ctx.setdefault("history_extra", {"cad": {"document_id": doc_id, "features": [], "specs": []}})["cad"]
        h["features"] += [x["feature"] for x in r["added"]]
        h["specs"] += [{**sp, "region": sp["region"]} for sp in specs if sp["region"] in keep]
    if r.get("failed") or bad:
        out["not_added"] = bad + r.get("failed", [])
        out["hint"] = ("an outline that misses the body or grazes an edge cannot be built: move it (u, v) onto a flatter "
                       "part of the side, make it smaller, or add a separate part with add_parts + attach")
    if not r.get("added"):
        return out
    if any(sp["view"] == "side" for sp in specs):
        out["note"] = "left / right features are made on both sides (the body is symmetric)"
    if CAD_REIMPORT:
        CAD_REIMPORT(m["name"])
    m = next((q for q in roots(state) if (q.get("eng") or {}).get("cad_document") == doc_id), m)
    if colors:
        for q in lab.subtree(state, m["id"]):
            names = ((q.get("params") or {}).get("region_names")) or []
            got = {k: v for k, v in colors.items() if k in names}
            if got:
                q["region_colors"] = {**(q.get("region_colors") or {}), **got}
        lab._bump(state)
    sides = list(dict.fromkeys(f["side"] for f in features if f["side"] in ("front", "rear", "left", "right")))[:2]
    out["_look"] = refine.look(state, m, views=tuple(["iso"] + sides + ["iso_rear"])[:4])
    return out


START_CAD_JOB = None         # set by the server: a three-view drawing -> CAD model in the background
CAD_REIMPORT = None          # set by the server: re-import the open CAD document in place (same model, same pose)


# ------------------------------------------------------------------------------------------------ AI-written CAD programs
def _program_dir(ctx, pid, version):
    base = Path(ctx.get("exports_dir") or (ROOT / "output" / "exports")).parent / "programs" / pid / f"v{version}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _program_result(r):
    """What the model is told about a program build: per round, what was built and how it checked."""
    return {"rounds": r.get("rounds"), "plan_components": r.get("plan_components"),
            "kept": {k: (r.get("best") or {}).get(k) for k in ("round", "iou", "mean_iou", "object", "length_mm", "critic",
                                                               "critic_scores", "gates")},
            "parts": [p["name"] for p in (r.get("best") or {}).get("parts") or []], "seconds": r.get("seconds")}


def build_cad(state, ctx, description=None, file=None, name=None, rounds=3, _gated=False):
    """Muse writes a CadQuery program for the object (from an attached drawing, a description, or both), it runs in the
    sandbox, every solid is validated, and the program is revised against the drawing / its own renders. The kept
    model comes into the scene as exact B-rep parts; the program is its editable source."""
    if not description and not file:
        raise ValueError("build_cad needs a description, an attached drawing (file), or both")
    if file and not _gated:                       # a drawing is checked first: what is missing, ask if critical
        return build_from_drawing(state, ctx, file, kind="auto", hint=description)
    sheet = _file(ctx, file)["path"] if file else None
    pid = uuid.uuid4().hex[:8]
    out = _program_dir(ctx, pid, 1)
    r = _program_job(ctx, "program_build", sheet=sheet, out_dir=str(out), request=description or "",
                  rounds=int(rounds))
    if not r.get("best"):
        return {"built": False, "why": "no round produced a program whose every solid is valid", **_program_result(r)}
    nm = name or r["best"]["object"] or "CAD model"
    imp = lab.import_cad(state, r["meshes"], [], nm, f"program:{pid}",
                         provenance={"kind": "cad program", "program_id": pid, "version": 1,
                                     "program": str(out / "program.py"), "report": str(out / "report.json"),
                                     "step": str(out / "model.step"), "glb": str(out / "model.glb"), "sheet": sheet,
                                     "length_mm": r["best"]["length_mm"], "request": description or ""})
    agent._fit_to_desk(state, imp["id"])
    arrange(state)
    return {"built": True, "model": nm, "id": imp["id"], **_program_result(r), "unknowns": r.get("unknowns"),
            "source": "a CadQuery program written by Muse and run in the sandbox; every part is a valid OpenCascade solid"}


def edit_cad(state, ctx, model, instruction, rounds=3):
    """Change a program model: Muse revises its CAD program for the instruction; the new version replaces the model in
    the scene only if every solid is valid (otherwise the model stays as it was)."""
    ms = resolve(state, model, prefer_models=True)
    if len(ms) != 1:
        raise Ambiguous(model, [m["name"] for m in ms])
    g = root_of(state, ms[0]) if ms[0]["type"] != "group" else ms[0]
    e = g.get("eng") or {}
    if e.get("kind") != "cad program":
        raise ValueError(f"'{g['name']}' is not a CAD-program model (build it with build_cad first)")
    v = int(e["version"]) + 1
    out = _program_dir(ctx, e["program_id"], v)
    r = _program_job(ctx, "program_build", sheet=e.get("sheet"), out_dir=str(out), request=instruction,
                  rounds=int(rounds), base_program=Path(e["program"]).read_text(encoding="utf-8"),
                  base_length_mm=e.get("length_mm"), base_plan=str(Path(e["program"]).with_name("plan.json")))
    if not r.get("best"):
        return {"changed": False, "kept_version": e["version"], "why": "no revised program produced valid solids; the "
                "model is unchanged", **_program_result(r)}
    imp = lab.import_cad(state, r["meshes"], [], g["name"], g["eng"]["cad_document"],
                         provenance={**e, "version": v, "program": str(out / "program.py"), "report": str(out / "report.json"),
                                     "step": str(out / "model.step"), "glb": str(out / "model.glb"),
                                     "length_mm": r["best"]["length_mm"], "previous": e.get("program")})
    return {"changed": True, "model": g["name"], "version": v, **_program_result(r)}


def set_cad_param(state, ctx, model, values):
    """Correct named parameters of a CAD-program model (an engineer's correction: "the wheelbase is 2400 mm"). The same
    program is re-run with the new values, no model call; the new version replaces the model only if every solid is
    valid, and every parameter keeps its provenance (a corrected one becomes 'user')."""
    ms = resolve(state, model, prefer_models=True)
    if len(ms) != 1:
        raise Ambiguous(model, [m["name"] for m in ms])
    g = root_of(state, ms[0]) if ms[0]["type"] != "group" else ms[0]
    e = g.get("eng") or {}
    if e.get("kind") != "cad program":
        raise ValueError(f"'{g['name']}' is not a CAD-program model")
    v = int(e["version"]) + 1
    out = _program_dir(ctx, e["program_id"], v)
    r = _program_job(ctx, "program_rerun", program_dir=str(Path(e["program"]).parent), out_dir=str(out),
                  overrides={k: float(x) for k, x in values.items()}, sheet=e.get("sheet"), length_mm=e.get("length_mm"))
    if not r.get("best"):
        return {"changed": False, "kept_version": e["version"], "why": r.get("error")}
    lab.import_cad(state, r["meshes"], [], g["name"], g["eng"]["cad_document"],
                   provenance={**e, "version": v, "program": str(out / "program.py"), "report": str(out / "report.json"),
                               "step": str(out / "model.step"), "glb": str(out / "model.glb"), "previous": e.get("program")})
    return {"changed": True, "version": v, "values": values, "checks": {k: r["best"].get(k) for k in ("gates", "iou", "proportion_error")},
            "params": r["best"].get("params")}


def run_tool(state, ctx, name, args):
    if name == "set_cad_param":
        return set_cad_param(state, ctx, **args)
    if name == "build_cad":
        return build_cad(state, ctx, **args)
    if name == "edit_cad":
        return edit_cad(state, ctx, **args)
    if name == "calculate":
        return calculate(**args)
    if name == "web_search":
        r = web_search(**args)
        ctx.setdefault("sources", []).extend(r["sources"])
        return r
    if name == "inspect":
        return inspect(state, ctx, **args)
    if name == "explain_machine":
        return explain_machine(state, ctx, **args)
    if name == "create_model":
        r = lab.build_assembly(state, args["name"], [_finish(dict(x)) for x in args["parts"]], replace=False)
        arrange(state)
        return r
    if name == "add_parts":
        model = resolve(state, args["model"], prefer_models=True)
        if len(model) != 1:
            raise Ambiguous(args["model"], [m["name"] for m in model])
        m = root_of(state, model[0]) if model[0]["type"] != "group" else model[0]
        if (m.get("eng") or {}).get("kind") == "cad program":   # enforced in code: a program model is changed by its program
            raise ValueError(f"'{m['name']}' is a CAD-program model: add detail by revising its program with edit_cad "
                             "(real parts with real depth, cut into the body where they belong), not with add_parts panels")
        return add_parts(state, ctx, m, args["parts"])
    if name == "cad_feature":
        tgt = resolve(state, args.get("model", ""), prefer_models=True)
        if len(tgt) == 1 and ((root_of(state, tgt[0]).get("eng") or {}).get("kind") == "cad program"):
            raise ValueError("this is a CAD-program model: change its geometry with edit_cad")
        return cad_feature(state, ctx, **args)
    if name == "modify":
        return modify(state, **args)
    if name == "remove":
        n0 = len(roots(state))
        r = remove(state, **args)
        if len(roots(state)) < n0:                     # a whole model went: the others close up on the desk
            arrange(state)                             # (a part removed from a model never moves or resizes it)
        return r
    if name == "export_model":
        return export_model(state, ctx, **args)
    if name == "make_drawing":
        return make_drawing(state, ctx, **args)
    if name == "build_from_drawing":
        return build_from_drawing(state, ctx, **args)
    if name == "import_file":
        return import_file(state, ctx, **args)
    if name == "analyze":
        return analyze(state, **args)
    if name == "undo":
        return undo(state)
    if name == "redo":
        return steps.redo(state)
    if name == "open_panel":
        ctx.setdefault("ui", []).append({"open_panel": args["panel"]})
        return {"opened": args["panel"]}
    if name == "optimize_for_desk":
        return agent.optimize(state, on_step=ctx.get("on_step"), **args)
    if name == "export_film":                         # a download card in the chat, saved with the project's exports
        args["out_dir"] = ctx["exports_dir"]
        Path(ctx["exports_dir"]).mkdir(parents=True, exist_ok=True)
        r = compute.run(state, name, args)
        if isinstance(r, dict) and r.get("path"):
            _download(ctx, Path(r["path"]), "Print film (2400 dpi) · PNG")
        return r
    return compute.run(state, name, args)


# ------------------------------------------------------------------------------------------------ the turn
def turn(state, history, user_text, ctx):
    """One user message -> (reply, trace, images, new_history, extras). extras: changes, downloads, question, explain,
    sources, ui, notes."""
    step = ctx.get("on_step") or (lambda e: None)
    ctx["user_text"] = user_text
    before = snapshot(state)
    content = [{"type": "text", "text": user_text or "(no text)"}]
    for f in ctx.get("attachments") or []:
        if f["kind"] == "image":
            content.append({"type": "image_url", "image_url": {"url": ctx["data_url"](f)}})
    sys_msg = SYSTEM + "\n\n" + scene_summary(state, ctx)
    msgs = [{"role": "system", "content": sys_msg}] + history + [{"role": "user", "content": content}]
    trace, actions = [], []
    looks = []
    open_issues, gated = [], False                       # the latest add_parts check's objections (finish gate)
    reply = None
    stopped = ctx.get("stopped") or (lambda: False)
    for k in range(MAX_STEPS):
        # Muse Spark's default reasoning effort is high (~10-17 s per step): medium for the first step, where the
        # intent is decided, low for the tool steps after it (they follow the plan the first step made)
        effort = EFFORT_FIRST if k == 0 else EFFORT_NEXT
        if stopped():
            reply = "Stopped." + (" What was done before you stopped is listed under What changed (undo takes it back)."
                                  if diff(before, state) else "")
            break
        step({"stage": "thinking"})
        try:
            resp = _chat_call({"model": agent.MODEL, "messages": msgs, "tools": TOOL_DEFS, "reasoning_effort": effort}, stopped)
        except Stopped:
            reply = "Stopped." + (" What was done before you stopped is listed under What changed (undo takes it back)."
                                  if diff(before, state) else "")
            break
        except urllib.error.HTTPError as e:
            if e.code != 400 or not any(isinstance(x.get("content"), list) for x in msgs):
                raise
            msgs = [{**x, "content": agent._text_of(x["content"])} if isinstance(x.get("content"), list) else x for x in msgs]
            resp = _chat_call({"model": agent.MODEL, "messages": msgs, "tools": TOOL_DEFS, "reasoning_effort": effort}, stopped)
        m = resp["choices"][0]["message"]
        calls = m.get("tool_calls") or []
        msgs.append({k: v for k, v in m.items() if k in ("role", "content", "tool_calls")})
        if not calls:
            # the finish gate (once): the last check of what was added still objects -> fix it, or say so plainly
            if open_issues and not gated:
                gated = True
                msgs.append({"role": "user", "content": "Before you answer: the last check of what you added still reports "
                             + json.dumps(open_issues[:8]) + ". Fix these now (modify / remove / add again with a better "
                             "attach), or, if one is really fine, tell the user plainly which and why."})
                continue
            reply = m.get("content") or ""
            break
        stop = False
        for c in calls:
            if stopped():                                # the user pressed stop: no further tool calls this turn
                msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps({"error": "stopped by the user"})})
                continue
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments must be a JSON object")
            except (json.JSONDecodeError, ValueError) as e:
                res = {"error": f"{name}: bad arguments ({e}); send them again", "error_kind": "bad_args"}
                args = {}
            else:
                step({"stage": "tool", "tool": name})
                if name == "ask_user":
                    ctx["asked_by_model"] = True
                    ctx["question"] = {"question": args.get("question", ""), "options": list(args.get("options") or [])[:4]}
                    res = {"asked": True}
                    stop = True
                else:
                    try:
                        res = run_tool(state, ctx, name, args)
                        if isinstance(res, dict) and res.get("_ask"):
                            ctx["question"] = res.pop("_ask")
                            stop = True
                    except Ambiguous as e:
                        res = {"error": str(e), "ambiguous": e.options}
                    except Stopped:
                        res = {"error": "stopped by the user"}
                    except Exception as e:
                        res = {"error": f"{type(e).__name__}: {e}"[:600]}
                step({"stage": "done", "tool": name, "error": (res or {}).get("error")})
            if name == "add_parts" and isinstance(res, dict):
                ck = res.get("checks")
                open_issues = [x for x in ck if x.get("problem") in ("floating", "outside", "overlap", "duplicate")]                     if isinstance(ck, list) else []
            look_img = res.pop("_look", None) if isinstance(res, dict) else None
            if look_img:
                looks.append((name, look_img))
                ctx.setdefault("images", {})[f"check_{len(trace) + 1}"] = look_img
                res["picture"] = "the result is shown in the next message: look at it"
            slim = lab.for_agent(res) if isinstance(res, dict) else res
            ctx.setdefault("images", {}).update((res or {}).get("_images", {}) if isinstance(res, dict) else {})
            trace.append({"tool": name, "args": {k: v for k, v in args.items() if k != "parts"} | (
                {"parts": f"{len(args['parts'])} part(s)"} if "parts" in args else {}), "result": slim})
            actions.append(name)
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(slim, default=str)[:12000]})
        if looks:                                        # what the tools made, seen: Muse Spark checks its own work
            content = [{"type": "text", "text": "Pictures of the result (" + ", ".join(n for n, _ in looks) + "). Check them "
                        "against what the user asked: right place, right side (the views are labelled), sensible size, "
                        "nothing floating or duplicated. Fix what is wrong, then answer."}]
            content += [{"type": "image_url", "image_url": {"url": u}} for _, u in looks[-2:]]
            msgs.append({"role": "user", "content": content})
            looks = []
        if stop:
            reply = ctx["question"]["question"]
            if "build_from_drawing" in actions and not ctx.get("asked_by_model"):
                reply = "Before I build it, I need one thing from you. " + reply
            break
    if reply is None:                                    # out of steps: say what was actually done, never a dead end
        try:
            msgs.append({"role": "user", "content": "Stop using tools now. In 2-4 short sentences, in my language, tell me "
                                                    "what you did and what is left (if anything)."})
            resp = agent._post("/chat/completions", {"model": agent.MODEL, "messages": msgs}, timeout=90)
            reply = resp["choices"][0]["message"].get("content") or ""
        except Exception:
            reply = ""
        reply = reply or "I did part of it (see What changed). Tell me what to do next, or say 'undo' to go back."
    changes = diff(before, state)
    undo_id = None
    if changes and not {"undo", "redo"} & set(actions):
        e = steps.record(before, state, user_text or "assistant change", "ai", ctx.get("history_extra"))
        undo_id = e and e["id"]
    note = f" [tools used: {', '.join(dict.fromkeys(actions))}]" if actions else ""
    hist = [x for x in history] + [{"role": "user", "content": user_text},
                                   {"role": "assistant", "content": (reply or "") + note + (
                                       f" [scene changes: {'; '.join(changes[:8])}]" if changes else "")}]
    extras = {"changes": changes, "undo_id": undo_id,
              "status": ("needs_review" if open_issues else "checks_passed") if "add_parts" in actions else None, "downloads": ctx.get("downloads", []), "question": ctx.get("question"),
              "explain": ctx.get("explain"), "sources": ctx.get("sources", []), "ui": ctx.get("ui", []),
              "notes": ctx.get("notes", [])}
    return reply, trace + ctx.get("trace_extra", []), ctx.get("images", {}), hist[-16:], extras
