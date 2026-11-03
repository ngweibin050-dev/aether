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
import time
import urllib.error
import uuid
from pathlib import Path

import numpy as np

import agent
import compute
from engine import geometry, lab, retina

ROOT = Path(__file__).resolve().parent
MAX_STEPS = 16
EFFORT_FIRST = os.environ.get("AETHER_CHAT_EFFORT_FIRST", "medium")
EFFORT_NEXT = os.environ.get("AETHER_CHAT_EFFORT_NEXT", "low")
UNDO_DEPTH = 30
UNDO = []                     # scene snapshots taken before each assistant turn that changed it (newest last)

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
5. Create something new ("make a car", or a drawing / photo attached with "build this"): build_from_drawing for an
   attached drawing or photo, create_model for a text request. The new model is placed BESIDE what is already there;
   nothing is removed.
6. Refine an existing model ("more detailed", "add car windows, doors, seats", "add a number plate"): call inspect on
   it ONCE to get its size and frame, then ONE add_parts call to THAT model with ALL the new parts (each with a unique
   name; positions in the model's own frame, inside its bounding box). Never rebuild it from scratch, never remove it
   or its parts to refine it (unless the user asked to remove something), and do not add a part twice: to change a
   part you added, use modify.
7. Modify ("make the window blue", "move it left", "bigger", "hide the wheels", "rename"): call modify on exactly what
   was named. Change nothing else. A CAD body's named regions (glass = windows, light = lamps) can be coloured with
   modify(target=<model>, region="glass", color=...).
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

UNITS: millimetres. The display surface is z = 0; models stand on it. Positions in add_parts are in the model's own
frame (inspect gives its bounding box in that frame). Round parts have their axis along local z.

PART TYPES and their params (use exactly these names): """ + "; ".join(f"{k}({v})" for k, v in geometry.PARAM_HELP.items())

# ------------------------------------------------------------------------------------------------ tool schemas
_P = {"type": "number"}
_V3 = {"type": "array", "items": _P, "minItems": 3, "maxItems": 3}
_TARGET = {"type": "string", "description": "a model or part: its name (as in the scene summary), id, 'selected', or 'all'"}
_PART = agent._PART

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
    ("create_model", "Create a NEW model from parametric parts (text-to-CAD). It is placed beside the existing models; "
     "nothing is removed. Aim for 6-25 parts that capture the real structure.",
     {"name": {"type": "string"}, "parts": {"type": "array", "items": _PART}}, ["name", "parts"]),
    ("add_parts", "Refine an EXISTING model: add parts to it (positions in that model's own frame; call inspect first "
     "for its bounding box).", {"model": _TARGET, "parts": {"type": "array", "items": _PART}}, ["model", "parts"]),
    ("modify", "Change exactly what is named: colour (hex or name), region colour of a CAD body ('glass', 'light'), "
     "move_by [dx,dy,dz] mm, position, rotation [deg], scale_by (uniform factor), visible, new_name, params.",
     {"target": _TARGET, "color": {"type": "string"}, "region": {"type": "string"}, "move_by": _V3, "position": _V3,
      "rotation": _V3, "scale_by": _P, "visible": {"type": "boolean"}, "new_name": {"type": "string"},
      "params": {"type": "object"}}, ["target"]),
    ("remove", "Remove a model or part (and what is under it). Only when the user asked to remove it. Undoable.",
     {"target": _TARGET}, ["target"]),
    ("export_model", "Export a model (or 'all') as a file the user downloads from the chat: glb (viewer / web), stl "
     "(3D printing), step (CAD, exact B-rep).", {"target": _TARGET, "format": {"type": "string", "enum": ["glb", "stl", "step"]}},
     ["target", "format"]),
    ("make_drawing", "Technical drawing of a model from its exact B-rep: front, top and side views with hidden lines, "
     "overall dimensions and a title block, as SVG + PDF download cards.", {"target": _TARGET, "title": {"type": "string"}},
     ["target"]),
    ("build_from_drawing", "Build a 3D model from an attached drawing, blueprint or photo (by file name). kind: auto, "
     "machine (one view of a mechanism), three_view (side/top/end sheet -> parametric CAD), part (photo of one part). "
     "The new model is placed beside the existing ones.",
     {"file": {"type": "string"}, "kind": {"type": "string", "enum": ["auto", "machine", "three_view", "part"]},
      "hint": {"type": "string", "description": "what the object is, if the user said"}}, ["file"]),
    ("import_file", "Bring an attached 3D file (glb, gltf, stl, obj) into the scene beside the existing models.",
     {"file": {"type": "string"}, "name": {"type": "string"}}, ["file"]),
    ("undo", "Undo the assistant's last change to the scene.", {}, []),
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
    if e.get("cad_document"):
        return "CAD model (exact B-rep, from a three-view sheet)"
    sub = lab.subtree(state, model["id"])
    if any((q.get("eng") or {}).get("from_drawing") for q in sub):
        return "machine rebuilt from a drawing"
    if any(q["type"] == "mesh" for q in sub):
        return "imported mesh"
    return "parametric model" if model["type"] == "group" else f"single {model['type']} part"


def _bbox(parts):
    vis = [p for p in parts if p["type"] != "group"]
    if not vis:
        return None, None
    lo, hi = geometry.bounds(vis)
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
    have = [k for k, v in (ctx.get("have") or {}).items() if v]
    if have:
        lines.append("Available results: " + ", ".join(have))
    lines.append(f"Undo steps available: {len(UNDO)}.")
    return "CURRENT SCENE\n" + "\n".join(lines)


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
    return {"parts": copy.deepcopy(state["parts"]), "selected": state.get("selected")}


def diff(before, state):
    """What actually changed in the scene (for the reply's 'What changed' list)."""
    b = {p["id"]: p for p in before["parts"]}
    a = {p["id"]: p for p in state["parts"]}
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
    for i in a:
        if i in b:
            ch = [label for k, label in fields.items() if a[i].get(k) != b[i].get(k)]
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


def inspect(state, ctx, target):
    hits = resolve(state, target, prefer_models=True)
    out = []
    for m in hits[:3]:
        sub = lab.subtree(state, m["id"])
        parts = [p for p in sub if p["type"] != "group"]
        lo, hi = _bbox(sub)
        info = {"name": m["name"], "id": m["id"], "kind": kind_of(root_of(state, m), state), "parts": len(parts),
                "desk_bbox_mm": [lo.round(1).tolist(), hi.round(1).tolist()] if lo is not None else None,
                "own_frame_bbox_mm": local_bbox(state, m) if m["type"] == "group" else None,
                "display_scale": (m.get("scale") or [1])[0], "regions": regions_of(state, m),
                "part_list": [{"name": p["name"], "type": p["type"], "color": p.get("color"),
                               "kind": (p.get("eng") or {}).get("kind")} for p in parts[:60]]}
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


def modify(state, target, color=None, region=None, move_by=None, position=None, rotation=None, scale_by=None,
           visible=None, new_name=None, params=None):
    tl = str(target).lower()
    region_key = None
    if region:
        region_key = next((k for k, w in REGION_WORDS.items() if region.lower() in w or region.lower() == k), region.lower())
    try:
        hits = resolve(state, target)
    except Ambiguous:
        raise
    except ValueError:
        # "the window" with no part of that name: a CAD body region
        region_key = region_key or next((k for k, w in REGION_WORDS.items() if any(x in tl for x in w)), None)
        if not region_key:
            raise
        hits = [m for m in roots(state) if region_key in regions_of(state, m)]
        if not hits:
            raise ValueError(f"no part named '{target}' and no model with a '{region_key}' region")
    changed = []
    for p in hits:
        if region_key and color:
            bodies = [q for q in lab.subtree(state, root_of(state, p)["id"])
                      if region_key in (((q.get("params") or {}).get("region_names")) or [])]
            if not bodies:
                raise ValueError(f"{p['name']} has no '{region_key}' region (regions: {regions_of(state, root_of(state, p))})")
            for q in bodies:
                rc = dict(q.get("region_colors") or {})
                rc[region_key] = _color(color)
                q["region_colors"] = rc
                changed.append(f"{q['name']} {region_key} -> {rc[region_key]}")
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


def _slug(s):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_")[:40] or "model"


def export_model(state, ctx, target, format):
    sub, hits = _model_state(state, target)
    name = _slug(hits[0]["name"] if len(hits) == 1 else "aether_scene")
    out = Path(ctx["exports_dir"])
    out.mkdir(parents=True, exist_ok=True)
    from engine import export as ex
    if format == "glb":
        f = out / f"{name}.glb"
        f.write_bytes(ex.glb(sub))
    elif format == "stl":
        f = out / f"{name}.stl"
        f.write_bytes(ex.stl(sub))
    elif format == "step":
        import cad_client
        f = out / f"{name}.step"
        r = cad_client.call("export_parts", parts=_with_heavy(sub["parts"], ctx), kind="step", path=str(f),
                            cad_brep_dir=str(ctx["cad_brep_dir"]), title=hits[0]["name"])
        if r.get("left_out"):
            ctx.setdefault("notes", []).append(f"not in the STEP (no exact B-rep): {[x['name'] for x in r['left_out']][:8]}")
    else:
        raise ValueError(f"unknown format {format}")
    return _download(ctx, f, f"{hits[0]['name'] if len(hits) == 1 else 'Scene'} · {format.upper()}")


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
                        cad_brep_dir=str(ctx["cad_brep_dir"]), title=title or hits[0]["name"], timeout=600)
    for f, lab_ in ((r["pdf"], "Drawing · PDF"), (r["svg"], "Drawing · SVG")):
        _download(ctx, Path(f), f"{hits[0]['name']} · {lab_}")
    ctx.setdefault("images", {})["drawing"] = r["png_data_url"]
    return {"views": r["views"], "solids": r["solids"], "left_out": r.get("left_out", []), "size_mm": r["size_mm"],
            "note": "orthographic views of the exact B-rep with hidden lines (dashed); dimensions are the model's own mm"}


def undo(state):
    if not UNDO:
        return {"undone": False, "why": "nothing to undo"}
    snap = UNDO.pop()
    state["parts"] = snap["parts"]
    state["selected"] = snap["selected"]
    lab._bump(state)
    return {"undone": True, "parts": len(state["parts"])}


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
        m = cad_client.call("import_step", path=str(path))
        r = lab.import_cad(state, m["meshes"], m["groups"], name or path.stem, m["document_id"], replace=False,
                           provenance={"source": path.name})
    else:
        raise ValueError(f"{path.name}: use build_from_drawing for drawings and photos; 3D files: glb, gltf, stl, obj, step")
    new = [m for m in roots(state) if m["id"] not in before]
    arrange(state)
    return {"imported": [m["name"] for m in new], **{k: v for k, v in (r or {}).items() if k in ("parts", "faces")}}


def build_from_drawing(state, ctx, file, kind="auto", hint=None):
    f = _file(ctx, file)
    url = ctx["data_url"](f)
    before = {m["id"] for m in roots(state)}
    keep = [p for p in state["parts"]]
    reply, trace, images, _ = agent.photo_to_design(state, [], url, hint or "", 80.0, ctx["out_dir"], ctx.get("on_step"),
                                                    "interpret", kind if kind in ("auto", "machine", "three_view", "part") else "auto")
    # a build path that still clears the scene must not cost the user their other models: put them back
    have = {p["id"] for p in state["parts"]}
    state["parts"] = [p for p in keep if p["id"] not in have] + state["parts"]
    arrange(state)
    ctx.setdefault("images", {}).update(images)
    ctx.setdefault("trace_extra", []).extend(trace)
    new = [m["name"] for m in roots(state) if m["id"] not in before]
    return {"built": new, "summary": (reply or "")[:1500]}


def explain_machine(state, ctx, target=None):
    import explain as ex
    sub, hits = _model_state(state, target or ("selected" if state.get("selected") else "all"))
    res = ex.explain(sub, agent.LAST_IMAGE.get("data_url"), on_step=ctx.get("on_step"),
                     scale={"known": agent.LAST_REPORT.get("scale_known", False), "source": agent.LAST_REPORT.get("scale_source")})
    ctx["explain"] = res
    return {"machine": res.get("machine"), "steps": [s["title"] for s in res.get("steps", [])],
            "shown_as": "the Explain player is open in the app"}


def run_tool(state, ctx, name, args):
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
        r = lab.build_assembly(state, args["name"], args["parts"], replace=False)
        arrange(state)
        return r
    if name == "add_parts":
        model = resolve(state, args["model"], prefer_models=True)
        if len(model) != 1:
            raise Ambiguous(args["model"], [m["name"] for m in model])
        m = root_of(state, model[0]) if model[0]["type"] != "group" else model[0]
        made, skipped = [], []
        ids = {}
        have = {p["name"].lower() for p in lab.subtree(state, m["id"])}
        for spec in args["parts"]:
            if str(spec.get("name", "")).lower() in have:
                skipped.append(spec.get("name"))               # already in the model: no duplicate (use modify)
                continue
            have.add(str(spec.get("name", "")).lower())
            parent = ids.get(spec.get("parent")) or m["id"]
            r = lab.add_part(state, spec["type"], spec.get("params"), spec.get("name"), spec.get("position", [0, 0, 0]),
                             spec.get("rotation", [0, 0, 0]), spec.get("scale", [1, 1, 1]), parent, 1.0, spec.get("color"))
            ids[spec.get("name")] = r["id"]
            made.append(r["name"])
        state["selected"] = m["id"]
        arrange(state)
        return {"model": m["name"], "added": made,
                **({"not_added_already_exist": skipped, "hint": "these names are already in the model: use modify"} if skipped else {})}
    if name == "modify":
        return modify(state, **args)
    if name == "remove":
        r = remove(state, **args)
        arrange(state)
        return r
    if name == "export_model":
        return export_model(state, ctx, **args)
    if name == "make_drawing":
        return make_drawing(state, ctx, **args)
    if name == "build_from_drawing":
        return build_from_drawing(state, ctx, **args)
    if name == "import_file":
        return import_file(state, ctx, **args)
    if name == "undo":
        return undo(state)
    if name == "open_panel":
        ctx.setdefault("ui", []).append({"open_panel": args["panel"]})
        return {"opened": args["panel"]}
    if name == "optimize_for_desk":
        return agent.optimize(state, on_step=ctx.get("on_step"), **args)
    if name == "export_film":
        args["out_dir"] = ctx["out_dir"]
    return compute.run(state, name, args)


# ------------------------------------------------------------------------------------------------ the turn
def turn(state, history, user_text, ctx):
    """One user message -> (reply, trace, images, new_history, extras). extras: changes, downloads, question, explain,
    sources, ui, notes."""
    step = ctx.get("on_step") or (lambda e: None)
    before = snapshot(state)
    content = [{"type": "text", "text": user_text or "(no text)"}]
    for f in ctx.get("attachments") or []:
        if f["kind"] == "image":
            content.append({"type": "image_url", "image_url": {"url": ctx["data_url"](f)}})
    sys_msg = SYSTEM + "\n\n" + scene_summary(state, ctx)
    msgs = [{"role": "system", "content": sys_msg}] + history + [{"role": "user", "content": content}]
    trace, actions = [], []
    reply = None
    stopped = ctx.get("stopped") or (lambda: False)
    for k in range(MAX_STEPS):
        # Muse Spark's default reasoning effort is high (~10-17 s per step): medium for the first step, where the
        # intent is decided, low for the tool steps after it (they follow the plan the first step made)
        effort = EFFORT_FIRST if k == 0 else EFFORT_NEXT
        if stopped():
            reply = "Stopped." + (" Done so far is listed under What changed." if diff(before, state) else "")
            break
        step({"stage": "thinking"})
        try:
            resp = agent._post("/chat/completions", {"model": agent.MODEL, "messages": msgs, "tools": TOOL_DEFS,
                                                     "reasoning_effort": effort}, timeout=180)
        except urllib.error.HTTPError as e:
            if e.code != 400 or not any(isinstance(x.get("content"), list) for x in msgs):
                raise
            msgs = [{**x, "content": agent._text_of(x["content"])} if isinstance(x.get("content"), list) else x for x in msgs]
            resp = agent._post("/chat/completions", {"model": agent.MODEL, "messages": msgs, "tools": TOOL_DEFS,
                                                     "reasoning_effort": effort}, timeout=180)
        m = resp["choices"][0]["message"]
        calls = m.get("tool_calls") or []
        msgs.append({k: v for k, v in m.items() if k in ("role", "content", "tool_calls")})
        if not calls:
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
                    ctx["question"] = {"question": args.get("question", ""), "options": list(args.get("options") or [])[:4]}
                    res = {"asked": True}
                    stop = True
                else:
                    try:
                        res = run_tool(state, ctx, name, args)
                    except Ambiguous as e:
                        res = {"error": str(e), "ambiguous": e.options}
                    except Exception as e:
                        res = {"error": f"{type(e).__name__}: {e}"[:600]}
                step({"stage": "done", "tool": name, "error": (res or {}).get("error")})
            slim = lab.for_agent(res) if isinstance(res, dict) else res
            ctx.setdefault("images", {}).update((res or {}).get("_images", {}) if isinstance(res, dict) else {})
            trace.append({"tool": name, "args": {k: v for k, v in args.items() if k != "parts"} | (
                {"parts": f"{len(args['parts'])} part(s)"} if "parts" in args else {}), "result": slim})
            actions.append(name)
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(slim, default=str)[:12000]})
        if stop:
            reply = ctx["question"]["question"]
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
    if changes and "undo" not in actions:
        UNDO.append(before)
        del UNDO[:-UNDO_DEPTH]
    note = f" [tools used: {', '.join(dict.fromkeys(actions))}]" if actions else ""
    hist = [x for x in history] + [{"role": "user", "content": user_text},
                                   {"role": "assistant", "content": (reply or "") + note + (
                                       f" [scene changes: {'; '.join(changes[:8])}]" if changes else "")}]
    extras = {"changes": changes, "downloads": ctx.get("downloads", []), "question": ctx.get("question"),
              "explain": ctx.get("explain"), "sources": ctx.get("sources", []), "ui": ctx.get("ui", []),
              "notes": ctx.get("notes", [])}
    return reply, trace + ctx.get("trace_extra", []), ctx.get("images", {}), hist[-16:], extras
