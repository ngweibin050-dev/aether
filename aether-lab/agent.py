"""Muse Spark agent: turns a request into AETHER Lab tool calls, then explains the computed result.

Meta Model API is OpenAI-compatible (https://api.meta.ai/v1, Bearer key).
The key is read from the environment variable META_API (loaded from .env by server.py).
"""
import json
import os
import urllib.error
import urllib.request

import numpy as np

import compute
import vision
from engine import geometry, lab

API = os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")
MODEL = os.environ.get("META_MODEL", "muse-spark-1.3")
VOICE_MODEL = os.environ.get("META_VOICE_MODEL", "muse-voice-transcribe-1.0")
MAX_STEPS = 10

SYSTEM = """You are AETHER, the assistant inside a holographic 3D design desk (AETHER 2.0).
You build and edit 3D scenes and run a wave-optics physics engine through tools. Rules:
- Use tools for every number. Never invent measurements; quote tool results.
- Geometry: units mm. The hologram panel is the plane z = 0 (598 x 336 mm desk panel); parts float
  in front of it at z > 0. The seated eye looks down at the desk, so the sharp zone is about -100..+75 mm
  (desk_score and window_check report the exact sharp_zone_mm for the current eye). Keep designs inside it;
  if a design is too tall, scale it uniformly - never squash one axis.
- Text-to-CAD: when asked to create an object or machine, call build_assembly with a list of
  parametric parts (types: """ + ", ".join(f"{k}({v})" for k, v in geometry.PARAM_HELP.items()) + """).
  Positions/rotations (deg, [x,y,z]) are relative to the assembly. Axis of round parts is local z.
  Aim for 6-25 parts that capture the real structure. Say it is a simplified parametric model,
  not manufacturer data.
- After building or changing the scene, call focus_sweep (what the eye sees), then make_hologram if asked, so the
  user sees the hologram. For "can the desk show it" use window_check and desk_check.
- To show what is inside (cutaway like a holographic workshop): set_view with section ("x", "y" or
  "z" plus section_mm, a world coordinate), explode (0-1, pulls nested parts apart along the axis),
  isolate (part names) or xray. The hologram is computed from this view, so recompute it after.
- If a design is not sharp on the desk (desk_score fails, or the user asks to fix it), call optimize_for_desk. It runs
  a loop where you change the design and the physics re-scores it; report the before/after numbers it returns.
- Speckle questions: speckle_compare. Hand questions: hand_check.
- Say clearly that results are simulations, not measurements of a built display.
- Answer in short, plain sentences, in the user's language."""

_DISP = {"type": "string", "enum": ["desk1d", "full2d", "screen3d"], "description": "AETHER Desk 1D hologram, full 2D hologram, or ordinary 3D screen"}
_P = {"type": "number"}
_V3 = {"type": "array", "items": _P, "minItems": 3, "maxItems": 3}
_PART = {"type": "object", "properties": {
    "name": {"type": "string"}, "type": {"type": "string", "enum": sorted(geometry.BUILDERS)},
    "params": {"type": "object"}, "position": _V3, "rotation": _V3, "scale": _V3,
    "parent": {"type": "string", "description": "name of another part in this assembly"},
    "color": {"type": "string", "description": "surface colour as hex, e.g. #b87333 copper, #c4cbd4 aluminium (used in the full-colour hologram)"}},
    "required": ["name", "type", "params"]}
SCHEMAS = [
    ("build_assembly", "Create a new assembly from parametric parts (text-to-CAD). Replaces the scene by default.",
     {"name": {"type": "string"}, "parts": {"type": "array", "items": _PART}, "position": _V3,
      "replace": {"type": "boolean"}}, ["name", "parts"]),
    ("add_part", "Add one part.", {"type": {"type": "string", "enum": sorted(geometry.BUILDERS)},
     "params": {"type": "object"}, "name": {"type": "string"}, "position": _V3, "rotation": _V3,
     "scale": _V3, "parent": {"type": "string"}, "color": {"type": "string"}}, ["type"]),
    ("update_part", "Move, rotate, scale, rename, hide or re-parameterise a part (id or name).",
     {"id": {"type": "string"}, "position": _V3, "rotation": _V3, "scale": _V3, "params": {"type": "object"},
      "name": {"type": "string"}, "visible": {"type": "boolean"}, "color": {"type": "string", "description": "hex colour"}}, ["id"]),
    ("delete_part", "Delete a part and its children.", {"id": {"type": "string"}}, ["id"]),
    ("turn_gear", "Turn a gear by some degrees; the gears it meshes with turn the other way by the tooth ratio and "
     "gears on the same pin turn with it (shows how the mechanism moves).",
     {"id": {"type": "string"}, "degrees": _P}, ["id"]),
    ("list_parts", "List all parts in the scene.", {}, []),
    ("set_display", "Change the lab hologram (pitch_um, wavelength_nm, samples, distance_mm, points, method) "
     "or AETHER Desk parameters (column_width_um, vertical_pitch_um, view_distance_mm).",
     {"preset": {"type": "string", "enum": ["lab_slm", "aether_desk"]}, "pitch_um": _P, "wavelength_nm": _P,
      "samples": {"type": "integer"}, "distance_mm": _P, "points": {"type": "integer"},
      "method": {"type": "string", "enum": ["wrp", "points", "layers"]}, "column_width_um": _P,
      "vertical_pitch_um": _P, "view_distance_mm": _P}, []),
    ("set_view", "See inside the design: section cut (axis x/y/z at section_mm, world mm; null/'off' removes it), "
     "explode (0 = assembled, 1 = fully exploded), isolate (list of part names; [] shows all), xray (see-through). "
     "Changes both the 3D view and the next hologram.",
     {"section": {"type": "string", "enum": ["x", "y", "z", "off"]}, "section_mm": _P, "section_flip": {"type": "boolean"},
      "explode": _P, "isolate": {"type": "array", "items": {"type": "string"}}, "xray": {"type": "boolean"}}, []),
    ("set_eye", "Move the viewer's eye (mm, desk frame; default 0,0,700).",
     {"x_mm": _P, "y_mm": _P, "z_mm": _P}, []),
    ("make_hologram", "Small lab-SLM demo: an 8 um phase hologram of the current view (scene shrunk ~40x to fit 8 mm) and "
     "its reconstruction. It is NOT the desk: wavelength does not shrink with the scene, so its focus and speckle differ "
     "from the desk. For the desk use desk_wave_view or eye_view.", {}, []),
    ("propagate", "Small lab-SLM demo refocused at scene height z_mm (not the desk).", {"z_mm": _P}, []),
    ("desk_wave_view", "True-scale wave simulation of the AETHER Desk panel (45 um vertical pitch, incoherent 150 um "
     "columns, real 700 mm distance): what the eye sees focused at focus_z_mm, computed from the panel's sub-holograms "
     "(not from the eye-model shortcut). Slower; use to confirm a result.",
     {"focus_z_mm": _P, "k": {"type": "integer"}, "encode": {"type": "string", "enum": ["none", "double_phase", "phase"],
      "description": "none = ideal complex modulation; double_phase / phase = one phase-only panel (experimental)"}}, []),
    ("focus_sweep", "What the seated viewer's eye sees on the desk while refocusing from the panel to the top of the design; "
     "returns images and sharpness vs a full 2D hologram per height.",
     {"steps": {"type": "integer"}, "display": _DISP, "color": {"type": "boolean", "description": "true = red/green/blue lasers (full colour, default)"}}, []),
    ("eye_view", "What the viewer's eye sees, focused at focus_z_mm above the panel (v9 wave-optics eye, Window Law, v11 speckle). "
     "which_eye left/right shifts the eye 31.5 mm (half the interpupillary distance); both = a stereo pair.",
     {"focus_z_mm": _P, "display": _DISP, "eye_x_mm": _P, "eye_y_mm": _P, "speckle": {"type": "boolean"}, "k": {"type": "integer"},
      "color": {"type": "boolean"}, "which_eye": {"type": "string", "enum": ["centre", "left", "right", "both"]}}, []),
    ("window_check", "Window Law at desk scale: % of each part the eye can see through the panel.",
     {"eye_x_mm": _P, "eye_y_mm": _P}, []),
    ("hand_check", "Check the tracked hand for occlusion depth conflicts.", {"hand_radius_mm": _P}, []),
    ("desk_check", "AETHER Desk: eye-model sharpness at heights above/below the panel (cm).",
     {"heights_cm": {"type": "array", "items": _P}, "column_width_um": _P, "view_distance_cm": _P}, []),
    ("search_column_width", "AETHER Desk: widest column keeping >= min_sharpness_pct at height_cm.",
     {"height_cm": _P, "min_sharpness_pct": _P, "view_distance_cm": _P}, []),
    ("desk_score", "Fast AETHER Desk score: per part its height, sharpness at its worst point and % visible through the panel, "
     "plus pass/fail and hints. No images.", {"target_pct": _P}, []),
    ("optimize_for_desk", "Closed design loop: score the design on the AETHER Desk, change it (move / rotate / scale), "
     "recompute, and repeat until every part is sharp and visible or max_rounds is reached. Shows before/after eye views. "
     "Use when a design fails desk_score or the user asks to make it show well on the desk.",
     {"target_pct": _P, "max_rounds": {"type": "integer"}}, []),
    ("speckle_compare", "Speckle contrast: one frame vs k^2 random frames vs k x k sparse point groups.",
     {"k": {"type": "integer"}}, []),
    ("export_film", "Printable film hologram for the laser-pointer test.",
     {"dpi": {"type": "integer"}, "film_mm": _P, "wall_distance_m": _P, "wavelength_nm": _P}, []),
]
TOOL_DEFS = [{"type": "function", "function": {
    "name": n, "description": d,
    "parameters": {"type": "object", "properties": p, "required": r}}} for n, d, p, r in SCHEMAS]


def _post(path, body):
    key = os.environ.get("META_API")
    if not key:
        raise RuntimeError("META_API is not set in .env")
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def chat(state, history, user_text, out_dir=".", on_step=None, tools=None):
    """Run one user turn. Returns (reply_text, trace, images, new_history).
    on_step(event) is called as the turn progresses ("thinking", a tool starting, a tool done) so the UI can show it live."""
    step = on_step or (lambda e: None)
    tools = tools or TOOL_DEFS
    msgs = [{"role": "system", "content": SYSTEM}] + history + [{"role": "user", "content": user_text}]
    trace, images = [], {}
    for _ in range(MAX_STEPS):
        step({"stage": "thinking"})
        try:
            resp = _post("/chat/completions", {"model": MODEL, "messages": msgs, "tools": tools})
        except urllib.error.HTTPError as e:
            if e.code != 400 or not any(isinstance(x.get("content"), list) for x in msgs):
                raise
            msgs = [{**x, "content": _text_of(x["content"])} if isinstance(x.get("content"), list) else x for x in msgs]
            resp = _post("/chat/completions", {"model": MODEL, "messages": msgs, "tools": tools})   # model took no image
        m = resp["choices"][0]["message"]
        calls = m.get("tool_calls") or []
        msgs.append({k: v for k, v in m.items() if k in ("role", "content", "tool_calls")})
        if not calls:
            hist = [{**x, "content": _text_of(x["content"])} for x in msgs[1:]
                    if x["role"] in ("user", "assistant") and not x.get("tool_calls")]
            return m.get("content") or "", trace, images, hist[-12:]
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if name == "export_film":
                args["out_dir"] = out_dir
            step({"stage": "tool", "tool": name})
            res = optimize(state, on_step=step, **args) if name == "optimize_for_desk" else compute.run(state, name, args)
            step({"stage": "done", "tool": name, "error": res.get("error")})
            images.update(res.get("_images", {}))
            slim = lab.for_agent(res)
            trace.append({"tool": name, "args": args, "result": slim})
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(slim)})
    return "Stopped after too many steps.", trace, images, history


def _text_of(content):
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if c.get("type") == "text")
    return content


def photo_to_design(state, history, data_url, prompt, size_mm=80.0, out_dir=".", on_step=None):
    """A phone photo of a real part -> SAM 3.1 cut-out + measurements -> Muse Spark rebuilds it as a parametric
    model -> the usual physics. Returns the same tuple as chat(), plus the SAM step in the trace."""
    step = on_step or (lambda e: None)
    prompts = [p.strip() for p in prompt.split(",") if p.strip()]
    if len(prompts) > 1:
        return _blueprint_to_design(state, history, data_url, prompts[:6], size_mm, out_dir, step)
    step({"stage": "tool", "tool": "sam_3_1"})
    try:
        info, images, cut = vision.photo_part(data_url, prompt, size_mm)
    except Exception as e:
        step({"stage": "done", "tool": "sam_3_1", "error": True})
        raise RuntimeError(f"SAM 3.1 failed: {type(e).__name__}: {e}")
    step({"stage": "done", "tool": "sam_3_1", "error": info.get("error")})
    sam = {"tool": "sam_3_1", "args": {"prompt": prompt, "size_mm": size_mm}, "result": info}
    if info.get("error"):
        return info["error"], [sam], images, history
    text = (f"This is a real {prompt}, cut out of a phone photo by SAM 3.1. Its silhouette, measured from the SAM mask "
            f"(longest side set to {size_mm} mm): {json.dumps(info)}. The photo shows one side only, so guess the depth "
            "from what the object is. Rebuild it with build_assembly from the parametric parts (use the measured radius, "
            "hole and lobe count, e.g. lobes = gear teeth or fan blades; colour it like the photo), then call focus_sweep, "
            "then desk_score. Say which numbers came from the photo and which you assumed.")
    content = [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": cut}}]
    reply, trace, more, hist = chat(state, history, content, out_dir, on_step)
    images.update(more)
    return reply, [sam] + trace, images, hist


READ_DRAWING = """You are reading a mechanical drawing ({w} x {h} px). Answer with one JSON object:
{{"view": "front" | "side" | "top" | "isometric" | "section" | "photo",
  "parts": [{{"label": "...", "type": "gear", "box": [x1, y1, x2, y2], "teeth": 24}}, ...],
  "dimensions": [{{"value_mm": 120, "p1": [x, y], "p2": [x, y]}}, ...]}}
parts: the separate mechanical components (up to 20, the most important first): gears, wheels, pulleys, levers,
links, arms, shafts, rods, pins, pistons, cylinders, springs, frames, plates, bolts. type is one of those words.
box is tight, in thousandths of the image width/height (0-1000, origin top-left). For gears give the number of
teeth if you can count them. Do NOT list watermarks, logos, text, dimension lines, centre lines, hatching or arrows.
dimensions: every dimension you can read (number with its two extension-line ends, same 0-1000 coordinates),
converted to mm (inches x 25.4). Empty list if there are none. Hints of what to look for: {hints}.
JSON only."""


def _spark_read_drawing(im, hints):
    """Muse Spark reads the drawing: view type, parts with rough boxes (pixels) and any dimensions.
    Returns None if it cannot see images."""
    W, H = im.size
    msg = [{"type": "text", "text": READ_DRAWING.format(w=W, h=H, hints=", ".join(hints))},
           {"type": "image_url", "image_url": {"url": vision._data_url(im, "JPEG")}}]
    try:
        r = _post("/chat/completions", {"model": MODEL, "messages": [{"role": "user", "content": msg}]})
    except urllib.error.HTTPError as e:
        if e.code == 400:
            return None
        raise
    text = r["choices"][0]["message"].get("content") or ""
    try:
        if text.find("{") >= 0 and (text.find("[") < 0 or text.find("{") < text.find("[")):
            obj = json.loads(text[text.find("{"):text.rfind("}") + 1])
        else:
            obj = {"parts": json.loads(text[text.find("["):text.rfind("]") + 1])}
    except json.JSONDecodeError:
        return None
    if isinstance(obj, list):
        obj = {"parts": obj}
    out = []
    for it in (obj.get("parts") or [])[:20]:
        bx = it.get("box") if isinstance(it, dict) else None
        if isinstance(bx, list) and len(bx) == 4 and all(isinstance(v, (int, float)) for v in bx):
            out.append({**it, "box": [bx[0] * W / 1000, bx[1] * H / 1000, bx[2] * W / 1000, bx[3] * H / 1000]})
    dims = []
    for d in obj.get("dimensions") or []:
        try:
            v = float(d["value_mm"])
            (x1, y1), (x2, y2) = d["p1"], d["p2"]
            px = float(np.hypot((x2 - x1) * W / 1000, (y2 - y1) * H / 1000))
            if v > 0 and px > 20:
                dims.append({"value_mm": v, "px": round(px, 1), "mm_per_px": v / px})
        except (KeyError, TypeError, ValueError):
            continue
    return {"parts": out, "view": obj.get("view"), "dimensions": dims} if out else None


def _scale_from_dims(dims):
    """mm per pixel from the dimensions Spark read: the median, if the readings agree within 15 %."""
    if not dims:
        return None, None
    v = np.array([d["mm_per_px"] for d in dims])
    med = float(np.median(v))
    agree = [d for d in dims if abs(d["mm_per_px"] / med - 1) <= 0.15]
    if len(agree) < max(1, len(dims) // 2):
        return None, None
    return med, f"read from {len(agree)} dimension(s) on the drawing: " + ", ".join(f"{d['value_mm']:g} mm" for d in agree[:4])


def _fit_to_desk(state, group_id, target_pct=80):
    """Stand the rebuilt drawing upright on the desk and fit it in the sharp zone with ONE uniform scale."""
    g = lab._find(state, group_id)
    lo, hi = geometry.bounds(state["parts"])
    zone = lab.sharp_zone(state, target_pct, ((lo[0] + hi[0]) / 2, 0.0))
    H = float(hi[2] - lo[2])
    room = 0.92 * (zone[1] - zone[0])
    s = min(1.0, room / max(H, 1e-6))
    g["scale"] = [s, s, s]
    lo, hi = geometry.bounds(state["parts"])
    H = float(hi[2] - lo[2])
    bottom = 2.0 if H <= 0.92 * zone[1] else (zone[0] + zone[1]) / 2 - H / 2
    g["position"] = [float(g["position"][0] - (lo[0] + hi[0]) / 2), float(g["position"][1] - (lo[1] + hi[1]) / 2),
                     float(g["position"][2] + bottom - lo[2])]
    lab._bump(state)
    return {"scale": round(s, 3), "sharp_zone_mm": zone, "height_mm": round(H, 1)}


def _blueprint_to_design(state, history, data_url, prompts, size_mm, out_dir, step):
    """A drawing of a whole machine -> a real 3D mechanism.
    Muse Spark reads the drawing (view, parts with rough boxes, dimensions), SAM 3.1 traces each box exactly,
    engine.rebuild turns every traced part into the solid it is (involute gears that mesh, pins through the stack,
    plates with their real holes, frame plates front and back) and stacks them in layers by constraints; the result
    stands upright on the desk, fitted to the sharp zone with one uniform scale."""
    from engine import rebuild
    im = vision.load_image(data_url, 1024)
    step({"stage": "tool", "tool": "read_drawing"})
    try:
        read = _spark_read_drawing(im, prompts)
    except Exception:
        read = None
    step({"stage": "done", "tool": "read_drawing", "error": not read})
    mmpx, src = _scale_from_dims((read or {}).get("dimensions"))
    step({"stage": "tool", "tool": "sam_3_1"})
    try:
        info, images = vision.blueprint_parts(im, prompts, size_mm, boxes=(read or {}).get("parts"), mm_per_px=mmpx, scale_source=src)
    except Exception as e:
        step({"stage": "done", "tool": "sam_3_1", "error": True})
        raise RuntimeError(f"SAM 3.1 failed: {type(e).__name__}: {e}")
    step({"stage": "done", "tool": "sam_3_1", "error": info.get("error")})
    images = {k: v for k, v in images.items() if v}
    if read:
        info["view"] = read.get("view")
    sam = {"tool": "sam_3_1", "args": {"prompt": ", ".join(prompts), "size_mm": size_mm},
           "result": {**info, "parts": [{k: v for k, v in p.items() if k != "_poly"} for p in info.get("parts", [])]}}
    if info.get("error"):
        return info["error"], [sam], images, history
    step({"stage": "tool", "tool": "rebuild_3d"})
    specs, rep = rebuild.rebuild(info["parts"], info["drawing_mm"])
    built = compute.run(state, "build_assembly", {"name": "Machine from drawing", "parts": specs,
                                                  "position": [0, 0, 0], "rotation": [90, 0, 0]})
    fit = _fit_to_desk(state, state["selected"])
    step({"stage": "done", "tool": "rebuild_3d"})
    rep.update({"scale_on_desk": fit["scale"], "real_size": info["scale_source"], "view": info.get("view")})
    trace = [sam, {"tool": "build_assembly", "args": {"parts": len(specs)}, "result": {**lab.for_agent(built), "rebuild": rep}}]
    step({"stage": "tool", "tool": "desk_score"})
    score = compute.run(state, "desk_score", {})
    step({"stage": "done", "tool": "desk_score"})
    trace.append({"tool": "desk_score", "args": {}, "result": lab.for_agent(score)})
    text = (f"I rebuilt the drawing ({info.get('view') or 'view unknown'}) as a 3D mechanism: {json.dumps(rep)}. "
            f"Scale: {info['scale_source']}; shown on the desk at {fit['scale']}x so it fits the sharp zone "
            f"{fit['sharp_zone_mm']} mm. desk_score: pass={score.get('pass')}, worst {score.get('min_sharpness_pct')}%. "
            "Do not rebuild it. Call focus_sweep once with steps=5 and color=false, then tell the user in 4-5 short "
            "sentences: what was traced from the drawing (outlines, positions, teeth), what was rebuilt from engineering "
            "rules (gear module and face width, pins through the stack, plate thickness, frame plates, layer order), "
            "which gears mesh, and what is still assumed (real size if no dimension was read, thicknesses).")
    keep = [d for d in TOOL_DEFS if d["function"]["name"] not in ("build_assembly", "add_part", "delete_part", "clear_scene")]
    reply, more_trace, more, hist = chat(state, history, text, out_dir, step, tools=keep)
    images.update(more)
    return reply, trace + more_trace, images, hist


OPT_SYSTEM = """You are the design half of a closed loop with a wave-optics simulator of the AETHER Desk
(a 1D holographic desk display; panel = plane z = 0, the seated eye is in front and above, looking down).
Each round you get desk_score: every part's height range (mm), its worst and mean sharpness (% of a full 2D
hologram, along the real line of sight), how much of it the eye sees through the panel, and sharp_zone_mm (the
heights that stay sharp from this eye). Change the design so every part passes, with the smallest changes that keep
what the object is:
- prefer moving the root group in z into sharp_zone_mm,
- then rotating it (keep its real orientation if you can: a machine stands up),
- then scaling the root group down UNIFORMLY (the same factor on x, y and z, at least 0.5); never squash one axis,
  that turns a 3D object into a flat relief,
- never delete parts or change their shapes.
Call update_part one or more times (ids from the score), then stop. Do not write any text."""

UPDATE_DEF = [d for d in TOOL_DEFS if d["function"]["name"] == "update_part"]


def _eye_shot(state, z):
    res = compute.run(state, "eye_view", {"focus_z_mm": z, "color": True})
    return res.get("_images", {}).get("eye"), res.get("sharpness_vs_full_2d_pct")


def optimize(state, target_pct=80, max_rounds=3, on_step=None):
    """Closed loop: physics score -> Muse Spark edits the design -> physics re-scores, until it passes.
    Returns every round, the before/after score and before/after eye views (top of the design, full colour)."""
    step = on_step or (lambda e: None)
    max_rounds = int(min(5, max(1, max_rounds)))
    score = compute.run(state, "desk_score", {"target_pct": target_pct})
    if score.get("error"):
        return score
    first = score
    before_img, before_sharp = _eye_shot(state, score["design_z_mm"][1])
    rounds = []
    msgs = [{"role": "system", "content": OPT_SYSTEM}]
    for i in range(max_rounds):
        if score["pass"]:
            break
        slim = {k: score[k] for k in ("pass", "parts_ok", "parts", "min_sharpness_pct", "target_pct", "design_z_mm",
                                      "sharp_zone_mm", "size_mm", "rows", "roots", "hints")}
        msgs.append({"role": "user", "content": f"Round {i + 1}. desk_score:\n" + json.dumps(slim)})
        step({"stage": "thinking"})
        m = _post("/chat/completions", {"model": MODEL, "messages": msgs, "tools": UPDATE_DEF})["choices"][0]["message"]
        calls = m.get("tool_calls") or []
        msgs.append({k: v for k, v in m.items() if k in ("role", "content", "tool_calls")})
        if not calls:
            break
        edits = []
        step({"stage": "tool", "tool": "update_part"})
        for c in calls:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if args.get("scale") is not None:                   # uniform scale only: squashing one axis fakes a pass
                sc = [float(v) for v in args["scale"]] if isinstance(args["scale"], list) else [float(args["scale"])] * 3
                args["scale"] = [float(np.prod(np.abs(sc)) ** (1 / 3))] * 3
            r = lab.run(state, "update_part", args) if c["function"]["name"] == "update_part" else {"error": "only update_part"}
            edits.append({k: v for k, v in args.items() if v is not None})
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(lab.for_agent(r))})
        step({"stage": "done", "tool": "update_part"})
        step({"stage": "tool", "tool": "desk_score"})
        score = compute.run(state, "desk_score", {"target_pct": target_pct})
        if score.get("error"):
            return score
        step({"stage": "done", "tool": "desk_score"})
        rounds.append({"round": i + 1, "edits": edits, "min_sharpness_pct": score["min_sharpness_pct"],
                       "parts_ok": score["parts_ok"], "parts": score["parts"], "pass": score["pass"],
                       "design_z_mm": score["design_z_mm"]})
    after_img, after_sharp = (before_img, before_sharp) if not rounds else _eye_shot(state, score["design_z_mm"][1])
    images = {k: v for k, v in (("opt_before", before_img), ("opt_after", after_img)) if v}
    return {"pass": score["pass"], "rounds": rounds,
            "before": {"min_sharpness_pct": first["min_sharpness_pct"], "parts_ok": first["parts_ok"],
                       "design_z_mm": first["design_z_mm"], "eye_sharpness_at_top_pct": before_sharp},
            "after": {"min_sharpness_pct": score["min_sharpness_pct"], "parts_ok": score["parts_ok"],
                      "design_z_mm": score["design_z_mm"], "eye_sharpness_at_top_pct": after_sharp},
            "parts": score["parts"], "target_pct": target_pct, "rows": score["rows"],
            "note": "Muse Spark changed the design; the wave-optics eye model scored each round. Simulation, not a measurement.",
            "_images": images}


def transcribe(audio, mime="audio/wav"):
    """Muse Voice Transcribe: 16 kHz mono WAV -> text (POST /v1/asr/transcribe, multipart: request JSON + audio)."""
    key = os.environ.get("META_API")
    if not key:
        raise RuntimeError("META_API is not set in .env")
    if not audio[:4] == b"RIFF":
        raise ValueError("Muse Voice Transcribe needs WAV audio (the UI converts the recording to 16 kHz WAV)")
    b = "----aether" + os.urandom(8).hex()
    req_json = json.dumps({"model": VOICE_MODEL, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK",
                           "languageBias": ["English", "Chinese", "Malay"]})
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"request\"\r\nContent-Type: application/json\r\n\r\n"
            f"{req_json}\r\n--{b}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"speech.wav\"\r\n"
            "Content-Type: audio/wav\r\n\r\n").encode() + audio + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(API + "/asr/transcribe", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Accept": "application/json",
                                          "Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()).get("transcript", "")
