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
# Muse Wonder (Meta's most capable reasoning model, same endpoint and request format as Muse Spark; probed 2026-11-01:
# image input, strict json_schema, json_object, temperature, seed and reasoning_effort all accepted) does the
# engineer's completion (medium effort); Muse Spark reads the drawing (Muse Wonder reading raised recall but lowered
# precision on D and C: F1 B 68.9 -> 70.6, D 75.0 -> 72.8, C 76.9 -> 78.0, RESULTS.md). If a Muse Wonder call fails,
# that call is retried on Muse Spark and the step says so. Switches: META_READ_MODEL, META_READ_EFFORT, META_COMPLETE_MODEL.
READ_MODEL = os.environ.get("META_READ_MODEL", MODEL)            # owner's decision, Nov 1: Muse Spark reads (RESULTS.md)
COMPLETE_MODEL = os.environ.get("META_COMPLETE_MODEL", "muse-wonder-1.0")
COMPLETE_EFFORT = os.environ.get("META_COMPLETE_EFFORT", "medium")      # owner's decision, Nov 1
READ_EFFORT = os.environ.get("META_READ_EFFORT") or None          # Muse Wonder reading: "low" 29 s per reading, default 284 s
MODEL_NAMES = {"muse-wonder-1.0": "Muse Wonder", "muse-spark-1.3": "Muse Spark", "muse-spark-1.2": "Muse Spark 1.2"}
READ_USED = []                                   # which model answered each reading call of the current upload


def model_name(m):
    return MODEL_NAMES.get(m, m)


def who(models):
    """'Muse Wonder', or 'Muse Wonder + Muse Spark (fallback)' when some calls fell back."""
    names = []
    for m in models:
        if model_name(m) not in names:
            names.append(model_name(m))
    return " + ".join(names[:1] + [n + " (fallback)" for n in names[1:]]) or "Muse Spark"
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
    ("build_assembly", "Create a new assembly from parametric parts (text-to-CAD). Replaces the scene by default. "
                       "position [x, y, z]: z is the height of the model's LOWEST point above the display surface "
                       "(0 = standing on it; 100 = floating 10 cm above it).",
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
     {"focus_z_mm": _P, "k": {"type": "integer"}, "encode": {"type": "string", "enum": ["none", "pupil_gs", "double_phase", "phase"],
      "description": "none = ideal complex modulation; pupil_gs = one phase-only panel solved for the eye-tracked pupil "
                     "band (~2% from complex, 5% light into the band); double_phase / phase = naive phase-only (hazy)"}}, []),
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


def _post(path, body, timeout=120):
    key = os.environ.get("META_API")
    if not key:
        raise RuntimeError("META_API is not set in .env")
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class SparkError(RuntimeError):
    """A Muse Spark call that gave no usable answer (timeout, HTTP error, JSON that does not parse twice).
    Raised, never replaced by made-up data; the caller shows it in the step list."""


# Lowest-variance settings the Meta Model API accepts for muse-spark-1.3 (probed 2026-10-31: an unknown parameter is
# rejected with HTTP 400; temperature, seed and response_format json_schema are accepted).
STEADY = {"temperature": 0, "seed": 7}


def _spark_json(content, schema=None, name="answer", seed=None, timeout=90, retries=1, effort=None, model=None):
    """One Muse Spark call that must answer with a JSON object: temperature 0, a fixed seed, and a strict JSON schema
    when one is given (else json_object). Invalid JSON is retried once with the parse error shown to the model.
    effort: reasoning_effort ("low" for long structured answers: a strict schema on the engineer's completion made the
    model write 29k tokens in 144 s; json_object + low gave a valid answer in 36 s, measured 2026-10-31).
    Temperature 0 and a seed do NOT make the answer repeatable (two seeds never gave the same text), which is why
    drawings are read twice and only agreed parts are kept.
    model: another Meta model on the same endpoint (Muse Wonder); if it fails, the call is made again on Muse Spark
    and meta["model"] / meta["fallback"] say so.
    Returns (object, {"calls", "retried", "s", "model"}); raises SparkError with the reason."""
    if model and model != MODEL:
        try:
            return _spark_json_on(model, content, schema, name, seed, timeout, retries, effort)
        except SparkError as e:
            obj, meta = _spark_json_on(MODEL, content, schema, name, seed, timeout, retries, effort)
            meta["fallback"] = f"{model_name(model)} failed ({str(e)[:160]}); answered by {model_name(MODEL)}"
            return obj, meta
    return _spark_json_on(MODEL, content, schema, name, seed, timeout, retries, effort)


def _spark_json_on(model, content, schema=None, name="answer", seed=None, timeout=90, retries=1, effort=None):
    """One JSON call on one model (see _spark_json)."""
    import time
    fmt = ({"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}} if schema
           else {"type": "json_object"})
    msgs = [{"role": "user", "content": content}]
    meta = {"calls": 0, "retried": False, "model": model}
    t0 = time.time()
    for attempt in range(retries + 1):
        body = {"model": model, "messages": msgs, "response_format": fmt, **STEADY,
                **({"seed": seed} if seed is not None else {}), **({"reasoning_effort": effort} if effort else {})}
        try:
            meta["calls"] += 1
            r = _post("/chat/completions", body, timeout=timeout)
        except urllib.error.HTTPError as e:
            raise SparkError(f"{model_name(model)} HTTP {e.code}: {e.read().decode(errors='ignore')[:200]}") from e
        except Exception as e:                                   # timeout, connection reset
            raise SparkError(f"{model_name(model)} did not answer ({type(e).__name__}: {str(e)[:120]}; limit {timeout} s)") from e
        txt = r["choices"][0]["message"].get("content") or ""
        try:
            obj = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
            if isinstance(obj, dict):
                meta["s"] = round(time.time() - t0, 1)
                return obj, meta
            err = "the answer is not a JSON object"
        except ValueError as e:
            err = f"{type(e).__name__}: {str(e)[:120]}"
        meta["retried"] = True
        msgs = msgs + [{"role": "assistant", "content": txt[:4000]},
                       {"role": "user", "content": f"That was not valid JSON ({err}). Answer again with the JSON object only."}]
    raise SparkError(f"{model_name(model)} answered twice without valid JSON ({err})")


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
                bad = None if isinstance(args, dict) else f"{name}: arguments must be a JSON object"
            except json.JSONDecodeError as e:
                args, bad = {}, f"{name}: the arguments are not valid JSON ({e.msg} at character {e.pos}); send them again"
            if name == "export_film":
                args["out_dir"] = out_dir
            if name == "optimize_for_desk" and not bad:
                bad = lab.check_args("desk_score", {k: v for k, v in args.items() if k == "target_pct"}) or \
                    (f"optimize_for_desk: unknown argument(s) {[k for k in args if k not in ('target_pct', 'max_rounds')]}"
                     if set(args) - {"target_pct", "max_rounds"} else None)
            step({"stage": "tool", "tool": name})
            if bad:
                res = {"error": bad, "error_kind": "bad_args"}
            elif name == "optimize_for_desk":
                res = optimize(state, on_step=step, **args)
            else:
                res = compute.run(state, name, args)
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


MACHINE_HINTS = ["gear", "wheel", "lever", "shaft", "pin", "frame"]
READ_DEADLINE_S, READ_HARD_LIMIT_S = 60, 120     # reading stage: go on with what is back / wait no longer for a whole-sheet reading
LAST_BUILD = {}
LAST_REPORT = {}                                 # the last build's checks for the one-page report (engine/export.py)
LAST_IMAGE = {}                                  # the drawing the current machine was built from (Explain shows it to Muse Spark)


def photo_to_design(state, history, data_url, prompt, size_mm=80.0, out_dir=".", on_step=None, mode="interpret",
                    kind="auto"):
    """An upload -> a 3D model, routed by what it IS:
    - "machine": one view of a machine -> Muse Spark reads it like an engineer -> 3D mechanism (_blueprint_to_design);
    - "three_view": a sheet with side / top / end views of one object -> parametric CAD (cad/, OpenCascade B-rep) when the
      CAD environment is installed; mode="hull" (or no CAD environment) -> the LEGACY visual-hull preview (not CAD);
    - "part": a phone photo of one part -> SAM 3.1 cut-out + measurements -> Muse Spark rebuilds it.
    kind "auto" measures the image (vision.upload_kind: edge density, views and their size agreement); the UI can
    also say it ("Machine drawing"). prompt is an optional hint (what the object is), not a router.
    Returns the same tuple as chat(), with the routing as the first step of the trace."""
    step = on_step or (lambda e: None)
    compute.prewarm()                            # the GPU container starts while Muse Spark reads
    kind = kind if kind in vision.KINDS else "auto"
    route = {"tool": "classify_upload", "args": {"asked": kind}, "result": {"kind": kind, "by": "the user's choice"}}
    if kind == "auto":
        step({"stage": "tool", "tool": "classify_upload"})
        kind, ev = vision.upload_kind(data_url)
        step({"stage": "done", "tool": "classify_upload"})
        route["result"] = {"kind": kind, "by": "measured on the image (no AI)", **ev}
    hints = [p.strip() for p in (prompt or "").split(",") if p.strip() and p.strip().lower() not in ("object", "drawing")]

    def first(out):
        reply, trace, images, hist = out
        return reply, [route] + trace, images, hist
    if kind == "three_view" and mode != "hull":
        import cad_client
        if cad_client.available():
            return first(_sheet_to_cad(state, history, data_url, (hints or ["object"])[0], out_dir, step))
        route["result"]["cad"] = "CAD environment not installed (cad-worker/.venv): legacy visual-hull PREVIEW used, not CAD"
    if kind == "three_view":
        out = _sheet_to_design(state, history, data_url, (hints or ["object"])[0], size_mm, out_dir, step)
        if out:
            return first(out)
        if route["result"]["by"] == "the user's choice":
            return first(("This sheet does not hold three views of one object that agree in size (side, top and front). "
                          "Choose 'Machine drawing' for one view of a machine.", [], {}, history))
        route["result"]["fallback"] = "the views did not agree in size: read as one machine view instead"
        kind = "machine"
    if kind == "machine":
        prompts = (hints + [h for h in MACHINE_HINTS if h not in hints])[:6]
        return first(_blueprint_to_design(state, history, data_url, prompts, size_mm, out_dir, step, mode))
    prompt = (hints or ["object"])[0]
    step({"stage": "tool", "tool": "sam_3_1"})
    try:
        info, images, cut = vision.photo_part(data_url, prompt, size_mm)
    except Exception as e:
        step({"stage": "done", "tool": "sam_3_1", "error": True})
        raise RuntimeError(f"SAM 3.1 failed: {type(e).__name__}: {e}")
    step({"stage": "done", "tool": "sam_3_1", "error": info.get("error")})
    sam = {"tool": "sam_3_1", "args": {"prompt": prompt, "size_mm": size_mm}, "result": info}
    if info.get("error"):
        return info["error"], [route, sam], images, history
    text = (f"This is a real {prompt}, cut out of a phone photo by SAM 3.1. Its silhouette, measured from the SAM mask "
            f"(longest side set to {size_mm} mm): {json.dumps(info)}. The photo shows one side only, so guess the depth "
            "from what the object is. Rebuild it with build_assembly from the parametric parts (use the measured radius, "
            "hole and lobe count, e.g. lobes = gear teeth or fan blades; colour it like the photo), then call focus_sweep, "
            "then desk_score. Say which numbers came from the photo and which you assumed.")
    content = [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": cut}}]
    reply, trace, more, hist = chat(state, history, content, out_dir, on_step)
    images.update(more)
    return reply, [route, sam] + trace, images, hist


def _spark_which_front(cands, name):
    """Muse Spark looks at the two end views and says which one is the front. None if it cannot tell (then only
    the side and top views' lines are put on the model, so nothing lands on the wrong end)."""
    if len(cands) != 2:
        return None
    msg = [{"type": "text", "text": f"These are two end views of the same {name} from an orthographic drawing. Which one "
                                    "shows the FRONT (e.g. headlights, grille, windscreen, the face it moves towards)? "
                                    "Answer with exactly one character: 1 or 2. If you cannot tell, answer 0."}]
    for k, (_, crop) in enumerate(cands):
        msg += [{"type": "text", "text": f"View {k + 1}:"},
                {"type": "image_url", "image_url": {"url": vision._data_url(crop.convert("RGB"), "JPEG")}}]
    msg[0]["text"] = msg[0]["text"].replace("Answer with exactly one character: 1 or 2. If you cannot tell, answer 0.",
                                            'Answer {"front": 1} or {"front": 2}; {"front": 0} if you cannot tell.')
    try:
        obj, _ = _spark_json(msg, {"type": "object", "additionalProperties": False, "required": ["front"],
                                   "properties": {"front": {"type": "integer", "enum": [0, 1, 2]}}}, "which_front", seed=1, timeout=60)
    except SparkError:
        return None                                       # unknown front: only the side and top views' lines are used
    a = obj.get("front")
    return cands[0][0] if a == 1 else cands[1][0] if a == 2 else None


def _spark_name_regions(name):
    """A namer for sheet.sheet_to_solid: Muse Spark sees each view with its regions tinted and numbered and names
    every region the way a car / product modeller would (front door, side window, air intake, headlight...)."""
    def namer(shown):
        msg = [{"type": "text", "text": (
            f"These are orthographic views of one {name} from a drawing. In each view the areas enclosed by the drawn "
            "lines are tinted and numbered. Name every numbered area as the separate part a professional 3D modeller "
            "would build (e.g. front door, side window, windscreen, roof, bonnet, front fender, rear fender, air "
            "intake, side skirt, headlight, tail light, grille, diffuser, exhaust, mirror, wheel, engine cover vent). "
            "Use 1-3 lowercase words, no left/right. Answer with one JSON object only: "
            '{"side": {"1": "...", ...}, "top": {...}, "front": {...}, "rear": {...}} (only the views shown).')}]
        for role, im, n in shown:
            msg += [{"type": "text", "text": f"{role} view, areas 1-{n}:"},
                    {"type": "image_url", "image_url": {"url": vision._data_url(im.convert("RGB"), "JPEG")}}]
        # keys vary per sheet: json_object. Low reasoning: at the default it wrote ~15k tokens in 68-120 s (one timeout)
        js, _ = _spark_json(msg, None, "region_names", seed=1, timeout=90, effort="low")
        return {role: {int(k) - 1: str(v)[:40] for k, v in (js.get(role) or {}).items() if str(k).isdigit()}
                for role, _, _ in shown}
    return namer


def _sheet_to_cad(state, history, data_url, prompt, out_dir, step):
    """A multi-view sheet -> genuine parametric CAD (cad/ package, isolated OpenCascade worker): drawing interpretation,
    Muse Spark / Muse Wonder / SAM 3.1 stages (typed JSON only), a feature-based .aethercad document, validated B-rep,
    STEP round trip, three-view reprojection. The scene receives the B-rep's tessellation for display and physics."""
    import base64
    import io
    from pathlib import Path
    import cad_client
    from PIL import Image
    out = Path(out_dir) / "cad" / "current"
    out.mkdir(parents=True, exist_ok=True)
    sheet = out / "sheet.png"
    Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[-1]))).convert("RGB").save(sheet)
    step({"stage": "tool", "tool": "cad_pipeline", "who": "AETHER CAD (Muse Spark + Muse Wonder + SAM 3.1 + OpenCascade)"})
    try:
        r = cad_client.call("build", sheet=str(sheet), out_dir=str(out))
    except Exception as e:
        step({"stage": "done", "tool": "cad_pipeline", "error": str(e)[:300]})
        return (f"The CAD reconstruction failed: {e}", [{"tool": "cad_pipeline", "args": {}, "result": {"error": str(e)}}], {}, history)
    step({"stage": "done", "tool": "cad_pipeline", "error": None if r["status"].get("state") == "ok" else r["status"].get("error")})
    m = cad_client.call("meshes")
    doc = cad_client.call("document")
    imp = lab.import_cad(state, m["meshes"], m["groups"], f"{prompt[:40]} (CAD from three views)", doc["document_id"],
                         provenance={"maturity": doc["maturity"]})
    rep = r.get("report") or {}
    LAST_REPORT.clear()
    LAST_REPORT.update({"kind": "three-view CAD", "image_data_url": data_url, "scale_known": False,
                        "scale_source": "assumed: overall length 4500 mm (no dimension on the sheet)",
                        "view_match_iou_pct": {k: round(100 * v, 1) for k, v in (rep.get("reprojection_iou") or {}).items()}})
    feats = [f for f in doc["features"]]
    text = (f"Built a parametric CAD model ({len(feats)} features, {len([c for c in doc['components'] if not c.get('group')])} "
            f"solid components) from the sheet. Maturity: {doc['maturity'].replace('_', ' ')}. All solids valid: "
            f"{rep.get('all_valid')}. STEP round trip: {'passed' if rep.get('step_all_pass') else 'not passed'}. "
            "Reprojection IoU per view: " + ", ".join(f"{k} {v:.3f}" for k, v in (rep.get("reprojection_iou") or {}).items())
            + ". Real size is assumed (4.5 m overall length) until you enter a real dimension; the cross-sections between "
              "the end views and every recess depth are inferred or assumed and labelled so in the CAD panel.")
    trace = [{"tool": "cad_pipeline", "args": {}, "result": {"build": r, "import": imp,
                                                            "document": {k: doc[k] for k in ("title", "maturity", "status")}}}]
    return text, trace, {}, history


def _sheet_to_design(state, history, data_url, prompt, size_mm, out_dir, step):
    """A sheet with three or more orthographic views of one object (a car blueprint: side, front, rear, top) ->
    one solid that matches every view (engine/sheet.py, visual hull). Returns None when the sheet is not a
    multi-view drawing of one object, so the single-view paths run instead."""
    import io
    from concurrent.futures import ThreadPoolExecutor
    from engine import sheet
    step({"stage": "tool", "tool": "read_views"})
    name = (prompt or "").split(",")[0].strip() or "object"
    import time
    tl, t0 = {}, time.time()
    im = vision.load_image(data_url, 1600)
    try:
        front = _spark_which_front(sheet.front_rear_candidates(im), name)
        tl["front_rear_s"] = round(time.time() - t0, 1)
        shown = sheet.naming_views(im, 1600, front)["shown"]          # light, here: views and numbered regions
        tl["local_views_s"] = round(time.time() - t0 - tl["front_rear_s"], 1)
    except ValueError:
        step({"stage": "done", "tool": "read_views", "error": True})
        return None
    # Muse Spark names the regions HERE (the Meta key stays on this computer) while Modal builds the solid at the
    # drawing's own resolution (1 px per voxel, decimated to ~40k triangles); the names are applied after
    pool = ThreadPoolExecutor(1)
    naming = pool.submit(_spark_name_regions(name), shown)
    pool.shutdown(wait=False)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    t1 = time.time()
    res = compute.run(state, "import_sheet", {
        "image": "data:image/png;base64," + __import__("base64").b64encode(buf.getvalue()).decode(),
        "length_mm": max(float(size_mm), 120.0), "name": f"{name[:40]} (from three views)", "front_panel": front,
        "px_per_voxel": 1.0, "decimate_to": 40000, "measure": False})
    tl["modal_build_s"] = round(time.time() - t1, 1)
    if res.get("error"):
        step({"stage": "done", "tool": "read_views", "error": res["error"][:200]})
        if "ValueError" in res["error"]:                  # not one object's views after all: try the one-view paths
            return None
        return (f"The three-view build failed: {res['error']}", [{"tool": "read_views", "args": {}, "result": res}], {}, history)
    t2 = time.time()
    try:
        names, naming_error = naming.result(), None
    except Exception as e:                                # parts keep their position names; the report says why
        names, naming_error = {}, f"{type(e).__name__}: {str(e)[:200]}"
    tl["wait_for_names_s"] = round(time.time() - t2, 1)
    t3 = time.time()
    res.update(lab.apply_sheet_names(state, res["id"], names, res.pop("_frame")))
    tl["names_and_measure_s"] = round(time.time() - t3, 1)
    res["timing_local"] = tl
    if naming_error:
        res["naming_error"] = naming_error
    chk = res.pop("_check")
    fit = _fit_to_desk(state, res["id"])
    step({"stage": "done", "tool": "read_views"})
    iou = res["view_match_iou_pct"]
    check = {"mode": "three-view", "views_found": res["views_found"], "view_match_iou_pct": iou,
             "view_match_voxel_pct": res.get("view_match_voxel_pct"), "view_match_note": res.get("view_match_note"),
             "delivered_triangles": res.get("delivered_triangles"), "mesh": res.get("mesh"),
             "timing_modal": res.get("timing"), "timing_local": res.get("timing_local"),
             "size_disagreement_pct": res["size_disagreement_pct"],
             "note": "Blue: the 3D model seen from that view. Red: drawn but not built (the views disagree there)."}
    info = {"mode": "three-view", "read_by": "AETHER three-view reader (views found and matched by size, no AI guess)"
                                     + ("; Muse Spark told front from rear" if front is not None else ""),
            "size_mm": res["size_mm"], "check": check, "note": res["note"], "precision": res["precision"],
            "parts_built": res["parts_built"], "part_names": res["part_names"], "detail": res.get("detail")}
    sam = {"tool": "read_views", "args": {"prompt": prompt, "length_mm": res["size_mm"][0]}, "result": info}
    LAST_REPORT.clear()
    LAST_REPORT.update({"kind": "three-view sheet", "view_match_iou_pct": iou, "image_data_url": data_url, "fit": fit,
                        "scale_known": False, "scale_source": f"assumed: length {res['size_mm'][0]:g} mm (no scale on the sheet)"})
    images = {"sam_check": chk}
    step({"stage": "tool", "tool": "desk_score"})
    score = compute.run(state, "desk_score", {})
    step({"stage": "done", "tool": "desk_score"})
    trace = [sam, {"tool": "desk_score", "args": {}, "result": lab.for_agent(score)}]
    text = (f"LEGACY PREVIEW, NOT CAD: I rebuilt the sheet from its side, top and front views as a visual hull, split into {res['parts_built']} separate "
            "parts the way a modeller builds it (every closed region the drawing's lines make is its own part, with its "
            f"own panel lines; wheels are tyre + rim): {json.dumps({k: v for k, v in res.items() if k not in ('note',)}, default=str)}. "
            f"It is shown on the desk at {fit['scale']}x so it fits the sharp zone {fit['sharp_zone_mm']} mm. "
            f"desk_score: pass={score.get('pass')}, worst {score.get('min_sharpness_pct')}%. Do not rebuild or change it. "
            "Tell the user in 3-4 short sentences: which views were found and used, how well the 3D model matches each "
            f"view (side {iou.get('side')}%, top {iou.get('top')}%, front {iou.get('front')}% overlap; outline error in mm: "
            f"{json.dumps(res['precision']['outline_error_mm'])}), that it is built from {res['parts_built']} separate parts "
            "(select, hide or explode any of them in the Scene panel; names and recess depths: "
            f"{json.dumps(res.get('detail'))}), and honestly what "
            "a three-view rebuild cannot recover (concave detail such as the cabin glass, intakes and wheel spokes; "
            "it is the outer shape only). No tool calls.")
    reply, more_trace, more, hist = chat(state, history, text, out_dir, step,
                                         tools=[d for d in TOOL_DEFS if d["function"]["name"] == "desk_score"])
    images.update(more)
    return reply, trace + more_trace, images, hist


READ_DRAWING = """You are a senior mechanical engineer reading a mechanical drawing ({w} x {h} px){where}. Read it the way
you would before building the machine: EVERY separate component, not just the big ones. Answer with one JSON object:
{{"view": "front" | "side" | "top" | "isometric" | "section" | "photo",
  "parts": [{{"label": "...", "type": "gear", "box": [x1, y1, x2, y2], "teeth": 24}},
            {{"label": "...", "type": "lever", "box": [x1, y1, x2, y2], "ends": [[x, y], [x, y]]}}, ...],
  "dimensions": [{{"value_mm": 120, "p1": [x, y], "p2": [x, y]}}, ...]}}
parts: every separate mechanical component you can see (up to {max_n}): gears, wheels, pulleys, levers, links, arms,
cranks, shafts, rods, pins, pistons, cylinders, springs, frames, housings, plates, brackets, blocks, bolts, bearings,
columns, slides, guides, racks. type is one of those words. Small parts count: every pivot pin, boss, bearing block
and bracket you see is a part. A housing or frame that encloses others is one part with the box of its outline.
box is tight, in thousandths of the image width/height (0-1000, origin top-left). For gears give the number of
teeth if you can count them. For long parts (levers, links, arms, rods, shafts, pistons, cylinders, springs) also
give "ends": the centres of its two end pivots / end faces along its axis (same 0-1000 coordinates). Do NOT list watermarks, logos, text, dimension lines, centre lines, hatching or arrows.
dimensions: every dimension you can read (number with its two extension-line ends, same 0-1000 coordinates),
converted to mm (inches x 25.4). Empty list if there are none. Hints of what to look for: {hints}.
JSON only."""


PART_TYPES = ["gear", "wheel", "pulley", "lever", "link", "arm", "crank", "shaft", "rod", "pin", "piston", "cylinder",
              "spring", "frame", "housing", "plate", "bracket", "block", "bolt", "bearing", "column", "slide", "guide", "rack"]
_NUMS = {"type": "array", "items": {"type": "number"}}
READ_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["view", "parts", "dimensions"], "properties": {
    "view": {"type": "string", "enum": ["front", "side", "top", "isometric", "section", "photo"]},
    "parts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                         "required": ["label", "type", "box", "teeth", "ends"], "properties": {
        "label": {"type": "string"}, "type": {"type": "string", "enum": PART_TYPES}, "box": _NUMS,
        "teeth": {"type": ["integer", "null"]}, "ends": {"type": ["array", "null"], "items": _NUMS}}}},
    "dimensions": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                              "required": ["value_mm", "p1", "p2"], "properties": {
        "value_mm": {"type": "number"}, "p1": _NUMS, "p2": _NUMS}}}}}


def _spark_read_drawing(im, hints, where="", max_n=40, seed=None):
    """Muse Spark reads the drawing: view type, parts with rough boxes (pixels) and any dimensions, as strict JSON.
    Returns None if the model cannot take images (HTTP 400) or reads no part; raises SparkError on a failed call."""
    W, H = im.size
    msg = [{"type": "text", "text": READ_DRAWING.format(w=W, h=H, hints=", ".join(hints), where=where, max_n=max_n)
            + " teeth and ends are null when they do not apply."},
           {"type": "image_url", "image_url": {"url": vision._data_url(im, "JPEG")}}]
    try:
        obj, meta = _spark_json(msg, READ_SCHEMA, "drawing_reading", seed=seed, model=READ_MODEL, effort=READ_EFFORT)
        READ_USED.append(meta["model"])
    except SparkError as e:
        if isinstance(e.__cause__, urllib.error.HTTPError) and e.__cause__.code == 400:
            return None
        raise
    out = []
    for it in (obj.get("parts") or [])[:max_n]:
        bx = it.get("box") if isinstance(it, dict) else None
        if isinstance(bx, list) and len(bx) == 4 and all(isinstance(v, (int, float)) for v in bx):
            q = {**it, "box": [bx[0] * W / 1000, bx[1] * H / 1000, bx[2] * W / 1000, bx[3] * H / 1000]}
            e = it.get("ends")
            if isinstance(e, list) and len(e) == 2 and all(isinstance(v, list) and len(v) == 2 and
                                                           all(isinstance(c, (int, float)) for c in v) for v in e):
                q["ends"] = [[v[0] * W / 1000, v[1] * H / 1000] for v in e]
            else:
                q.pop("ends", None)
            if q.get("teeth") is None:
                q.pop("teeth", None)
            out.append(q)
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


def _read_machine(data_url, hints, step):
    """Read a whole machine drawing like an engineer with a magnifier: Muse Spark reads the whole sheet AND four
    overlapping close-ups at twice the resolution, each TWICE (seeds 1 and 2, temperature 0, strict JSON), all ten
    calls in parallel while every circle drawn on the sheet is measured (engine/circles.py). Per image, a part is kept
    only when both readings agree on it (interpret.agree) or a measured circle confirms it; what was dropped is logged.
    The agreed readings are merged without duplicates, round parts snap to their measured centre and radius, and
    circles nobody listed are added as the pivots, bosses and discs they are.
    Returns (im, read): the 1024 px image and the reading in its pixels (None if Spark cannot take images).
    Raises SparkError when both whole-sheet readings fail (shown in the step list; nothing is made up)."""
    from concurrent.futures import ThreadPoolExecutor
    from engine import circles, interpret
    im = vision.load_image(data_url, 1024)
    hi = vision.load_image(data_url, 2048)
    W, H = im.size
    f = W / hi.width
    Wh, Hh = hi.size
    tw, th = int(Wh * 0.62), int(Hh * 0.62)               # 2 x 2 tiles, ~24 % overlap
    tiles = [(x0, y0, x0 + tw, y0 + th) for y0 in (0, Hh - th) for x0 in (0, Wh - tw)]
    names = ["top left", "top right", "bottom left", "bottom right"]
    READ_USED.clear()
    step({"stage": "tool", "tool": "read_drawing", "who": model_name(READ_MODEL)})

    def whole(seed):
        return _spark_read_drawing(im, hints, "", 40, seed=seed)

    def tile(i, seed):
        x0, y0, x1, y1 = tiles[i]
        crop = hi.crop(tiles[i])
        r = _spark_read_drawing(crop, hints, f" (a close-up of the {names[i]} part of a larger sheet; list every part "
                                             "you see in it, a part cut by the edge too)", 40, seed=seed)
        if not r:
            return None
        out = []
        for it in r["parts"]:
            b = it["box"]
            m = 0.012 * max(tw, th)                       # cut by an inner edge of the close-up: another one has it whole
            if (b[0] < m and x0 > 0) or (b[1] < m and y0 > 0) or (b[2] > tw - m and x1 < Wh) or (b[3] > th - m and y1 < Hh):
                continue
            q = {**it, "box": [(b[0] + x0) * f, (b[1] + y0) * f, (b[2] + x0) * f, (b[3] + y0) * f]}
            if q.get("ends"):
                q["ends"] = [[(e[0] + x0) * f, (e[1] + y0) * f] for e in q["ends"]]
            out.append(q)
        return out

    def get(fu):
        if not fu.done():
            return None, f"Muse Spark was still reading after {READ_DEADLINE_S} s; not waited for"
        try:
            return fu.result(), None
        except SparkError as e:
            return None, str(e)

    # a total deadline for the reading stage: on 2026-10-31 the API once answered all ten calls in 77-88 s instead of
    # ~25 s. The upload goes on with what has come back; a straggler is logged, never waited on (the pool is not joined)
    from concurrent.futures import FIRST_COMPLETED, wait
    ex = ThreadPoolExecutor(11)
    fc = ex.submit(circles.find, im)
    fw = [ex.submit(whole, s) for s in (1, 2)]
    ft = [[ex.submit(tile, i, s) for s in (1, 2)] for i in range(4)]
    wait(fw + [x for pair in ft for x in pair], timeout=READ_DEADLINE_S)
    if not any(f.done() for f in fw):                      # no whole-sheet reading yet: wait for the first one only
        wait(fw, timeout=READ_HARD_LIMIT_S - READ_DEADLINE_S, return_when=FIRST_COMPLETED)
    (wa, ea), (wb, eb) = get(fw[0]), get(fw[1])
    tl = [[get(x) for x in pair] for pair in ft]
    circ = fc.result()
    ex.shutdown(wait=False)
    ink = circles.ink_mask(im)[0]                       # boxes of every reading are in im pixels
    failed = [e for e in (ea, eb) + tuple(e for pair in tl for _, e in pair) if e]
    if wa is None and wb is None:
        step({"stage": "done", "tool": "read_drawing", "error": failed[0] if failed else "no part read"})
        if ea or eb:
            raise SparkError(f"Muse Spark could not read the drawing: {ea or eb}")
        return im, None                                   # the model takes no images (HTTP 400) or read nothing
    read = dict(wa or wb)
    log = {"whole_sheet_readings": [len((x or {}).get("parts") or []) for x in (wa, wb)]}
    if wa and wb:
        parts, drop = interpret.agree(wa["parts"], wb["parts"], circ, ink=ink)
        read["dimensions"] = wa.get("dimensions") or wb.get("dimensions") or []
    else:
        parts, drop = read["parts"], []
        log["unconfirmed"] = "one whole-sheet reading failed, the other is used without a second opinion: " + (ea or eb)
    dropped = [{**d, "from": "whole sheet"} for d in drop]
    close = []
    for i, ((ra, _), (rb, _)) in enumerate(tl):
        if ra is not None and rb is not None:
            k, d = interpret.agree(ra, rb, circ, ink=ink)
            dropped += [{**x, "from": f"close-up {names[i]}"} for x in d]
        else:
            k = ra or rb or []
        close.append((k, f"close-up {names[i]}"))
    step({"stage": "done", "tool": "read_drawing", "error": "; ".join(failed)[:300] if failed else None,
          "who": who(READ_USED)})
    n_whole = len(parts)
    merged = interpret.merge_reads([(parts, "whole sheet")] + close, W, H)
    step({"stage": "tool", "tool": "measure_circles"})
    merged, snap = interpret.snap_circles(merged, circ, W, H)
    step({"stage": "done", "tool": "measure_circles"})
    read["parts"] = merged
    # every single reading as it came back (im px), so other agreement rules can be compared offline
    read["_raw"] = {"whole": [(x or {}).get("parts") for x in (wa, wb)], "tiles": [[x for x, _ in pair] for pair in tl],
                    "circles": circ}
    read["reading"] = {**log, "settings": "temperature 0, seeds 1 and 2, strict JSON schema; each image read twice",
                       "whole_sheet_parts_agreed": n_whole, "close_up_parts_agreed": sum(len(c[0]) for c in close),
                       "dropped_not_confirmed": len(dropped), "dropped": dropped,
                       "failed_calls": failed, "after_merge": len(merged) - snap["added"], "circles_measured": len(circ),
                       "round_parts_snapped_to_measured_circle": snap["snapped"],
                       "parts_added_from_measured_circles": snap["added"], "total_parts": len(merged)}
    return im, read


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
    ids = {group_id}
    for _ in range(8):                               # the group and everything under it, not the rest of the scene
        ids |= {p["id"] for p in state["parts"] if p.get("parent") in ids}
    mine = [p for p in state["parts"] if p["id"] in ids]
    lo, hi = geometry.bounds(mine)
    zone = lab.sharp_zone(state, target_pct, ((lo[0] + hi[0]) / 2, 0.0))
    H = float(hi[2] - lo[2])
    room = 0.92 * (zone[1] - zone[0])
    s = min(1.0, room / max(H, 1e-6))
    g["scale"] = [s, s, s]
    lo, hi = geometry.bounds(mine)
    H = float(hi[2] - lo[2])
    # on the display surface when it fits above it; a model taller than the sharp zone above the surface is centred in
    # the zone, which reaches behind the surface (an AETHER Desk image may sit behind the display) - said in the note
    bottom = 0.0 if H <= 0.92 * zone[1] else (zone[0] + zone[1]) / 2 - H / 2
    g["position"] = [float(g["position"][0] - (lo[0] + hi[0]) / 2), float(g["position"][1] - (lo[1] + hi[1]) / 2),
                     float(g["position"][2] + bottom - lo[2])]
    lab._bump(state)
    out = {"scale": round(s, 3), "sharp_zone_mm": zone, "height_mm": round(H, 1), "bottom_z_mm": round(bottom, 1)}
    if bottom < 0:
        out["note"] = (f"The model is {H:.0f} mm tall, more than the sharp zone above the display ({zone[1]:.0f} mm), so it is "
                       f"centred in the sharp zone: its lowest {-bottom:.0f} mm are behind the display surface, where a "
                       "hologram can also be shown sharply.")
    return out


def _interpret_read(im, read, size_mm, mmpx, src):
    """Engineer's interpretation (engine/interpret.py): clean standard parts from Muse Spark's reading of the sheet
    (types, boxes, axis ends, teeth) instead of traced pixels. Returns (info, images) like vision.blueprint_parts."""
    from PIL import ImageDraw
    from engine import circles, interpret
    W, H = im.size
    if not mmpx:
        mmpx, src = float(size_mm) / max(W, H), f"assumed: longest side of the drawing = {size_mm:g} mm"
    parts = interpret.parts_from_read(read["parts"], W, H, mmpx, ink=circles.ink_mask(im)[0])
    ov = im.convert("RGB").copy()
    d = ImageDraw.Draw(ov)
    for it in read["parts"]:
        d.rectangle(it["box"], outline=(56, 217, 255), width=2)
        if it.get("ends"):
            d.line([tuple(it["ends"][0]), tuple(it["ends"][1])], fill=(255, 190, 90), width=3)
    info = {"mode": "interpret", "read_by": "Muse Spark (engineer's interpretation: clean standard parts, no tracing)",
            "found": {k: sum(1 for p in parts if p["label"] == k) for k in dict.fromkeys(p["label"] for p in parts)}, "drawing_mm": [round(W * mmpx, 1), round(H * mmpx, 1)],
            "mm_per_px": round(mmpx, 4), "scale_source": src, "photo_px": [W, H], "view": read.get("view"),
            "parts": parts}
    return info, {"sam_overlay": vision._data_url(ov, "JPEG")}


COMPLETE = """You are a senior mechanical design engineer (aerospace / SpaceX standard). The drawing shows ONE view of
a machine; the other two views do not exist. Complete them in your head the way an expert would, so the machine can
be built and would actually work. The parts already read from the drawing (drawing frame: mm, x right, y up, origin
at the drawing centre; z = depth towards the viewer, 0 = back of the machine):
{parts}
Decide, from what each part is and how machines like this are built:
- machine_depth_mm: the overall depth (front to back) of the machine.
- for EVERY part n: z_mm (its centre depth) and thickness_mm (its size along z). Gears that mesh share one plane;
  parts that overlap in the drawing but do not touch sit in different planes; levers and links sit in front of what
  they drive; the housing / frame spans the whole depth.
- added: the hidden parts the drawing does not show but the machine needs (max 12): a shaft along z through every
  gear / wheel / pulley centre that has none (type "shaft", at_mm [x, y], radius_mm, z_from_mm, z_to_mm reaching
  the housing walls), bearings where shafts pass the walls (type "bearing"), spacers between stacked parts, a base
  plate or feet if it would not stand (type "block", box_mm [x1, y1, x2, y2], z_from_mm, z_to_mm).
- gear_pairs: every pair of gears that mesh, by part number n (in a section the gears are cut edge-on: a sun meshing
  with its planets, a planet with the ring), with a one-line reason. List only pairs you can see meshing.
No two solids may intersect except a shaft through its bore. For every added part give "reason": one line an
engineer would write, naming the part numbers it serves (e.g. "shaft: gear 3 has no axle", "bearing: shaft 12 passes
the housing wall"). Fields that do not apply are null. Answer with one JSON object only:
{{"machine_depth_mm": 0, "parts": [{{"n": 1, "z_mm": 0, "thickness_mm": 0}}], "added": [],
 "gear_pairs": [{{"a": 1, "b": 2, "reason": "one line"}}], "reasoning": "one sentence"}}"""

_ADDED = {"type": "object", "additionalProperties": False,
          "required": ["type", "label", "reason", "at_mm", "radius_mm", "box_mm", "z_from_mm", "z_to_mm"], "properties": {
              "type": {"type": "string", "enum": ["shaft", "pin", "axle", "bearing", "bushing", "spacer", "block", "foot"]},
              "label": {"type": "string"}, "reason": {"type": "string"},
              "at_mm": {"type": ["array", "null"], "items": {"type": "number"}}, "radius_mm": {"type": ["number", "null"]},
              "box_mm": {"type": ["array", "null"], "items": {"type": "number"}},
              "z_from_mm": {"type": "number"}, "z_to_mm": {"type": "number"}}}
COMPLETE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["machine_depth_mm", "parts", "added", "reasoning"],
                   "properties": {"machine_depth_mm": {"type": "number"}, "reasoning": {"type": "string"},
                                  "parts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                                       "required": ["n", "z_mm", "thickness_mm"], "properties": {
                                      "n": {"type": "integer"}, "z_mm": {"type": "number"}, "thickness_mm": {"type": "number"}}}},
                                  "added": {"type": "array", "items": _ADDED}}}


def _spark_complete(im, parts):
    """Muse Spark completes the two views a one-view drawing does not show (depth, planes, hidden parts), as strict
    JSON. Returns (completion or None, error text or None): on failure the rebuild uses its own stated rules."""
    rows = "\n".join(f"{p['n']}. {p['label']} ({p.get('kind', '')}): centre {p['centre_mm']}, "
                     f"{p['length_mm']} x {p['width_mm']} mm" + (f", radius {p['radius_mm']}" if p.get("radius_mm") else "")
                     for p in parts)
    msg = [{"type": "text", "text": COMPLETE.format(parts=rows)},
           {"type": "image_url", "image_url": {"url": vision._data_url(im.convert("RGB"), "JPEG")}}]
    try:
        out, meta = _spark_json(msg, None, "engineer_completion", seed=1, timeout=150, effort=COMPLETE_EFFORT, model=COMPLETE_MODEL)
    except SparkError as e:
        return None, str(e)
    # json_object, not the strict schema (too slow, see _spark_json): check the shape here, keep only usable entries
    if not isinstance(out.get("parts"), list) or not isinstance(out.get("added", []), list):
        return None, f"Muse Spark's completion has no parts list (keys: {sorted(out)[:8]})"
    out["parts"] = [p for p in out["parts"] if isinstance(p, dict) and str(p.get("n", "")).isdigit()]
    out["added"] = [a for a in out.get("added") or [] if isinstance(a, dict) and isinstance(a.get("z_from_mm", 0), (int, float))
                    and isinstance(a.get("z_to_mm", 0), (int, float))]
    out["gear_pairs"] = [g for g in out.get("gear_pairs") or [] if isinstance(g, dict) and isinstance(g.get("a"), int)
                         and isinstance(g.get("b"), int)]
    out["_model"] = meta["model"]
    return out, None


def _blueprint_to_design(state, history, data_url, prompts, size_mm, out_dir, step, mode="interpret"):
    """A drawing of a whole machine -> a real 3D mechanism.
    Muse Spark reads the drawing (view, parts with rough boxes, axis ends, dimensions). mode "interpret" (default):
    each part is drawn as a clean standard part from that reading (engine/interpret.py). mode "trace": SAM 3.1
    traces each box exactly and the traced outline is used.
    engine.rebuild turns every traced part into the solid it is (involute gears that mesh, pins through the stack,
    plates with their real holes, frame plates front and back) and stacks them in layers by constraints; the result
    stands upright on the desk, fitted to the sharp zone with one uniform scale."""
    from engine import rebuild
    try:
        if mode == "interpret":
            im, read = _read_machine(data_url, prompts, step)
        else:
            im = vision.load_image(data_url, 1024)
            step({"stage": "tool", "tool": "read_drawing"})
            read = _spark_read_drawing(im, prompts, seed=1)
            step({"stage": "done", "tool": "read_drawing", "error": None if read else "no part read"})
    except SparkError as e:
        step({"stage": "done", "tool": "read_drawing", "error": str(e)})
        fail = {"tool": "read_drawing", "args": {"mode": mode}, "result": {"error": str(e)}}
        return (f"{e}. Nothing was built from this drawing; try again, or check the connection to the Meta Model API.",
                [fail], {}, history)
    mmpx, src = _scale_from_dims((read or {}).get("dimensions"))
    info = None
    if mode == "interpret" and read and len(read.get("parts") or []) >= 2:
        info, images = _interpret_read(im, read, size_mm, mmpx, src)
    else:                                        # trace mode (or Spark could not read the sheet): SAM 3.1 outlines
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
        if read.get("reading"):
            info["reading"] = read["reading"]
    sam = {"tool": "sam_3_1", "args": {"prompt": ", ".join(prompts), "size_mm": size_mm},
           "result": {**info, "parts": [{k: v for k, v in p.items() if k != "_poly"} for p in info.get("parts", [])]}}
    if info.get("error"):
        return info["error"], [sam], images, history
    completion, c_err = None, None
    if info.get("mode") == "interpret":          # one view: the expert completes the other two
        step({"stage": "tool", "tool": "complete_views", "who": model_name(COMPLETE_MODEL)})
        completion, c_err = _spark_complete(im, info["parts"])
        step({"stage": "done", "tool": "complete_views", "error": c_err,
              "who": who([(completion or {}).get("_model") or COMPLETE_MODEL])})
    LAST_BUILD.clear()                           # what the rebuild got, so a run can be replayed offline (tests/run_reference)
    LAST_IMAGE.clear()
    LAST_IMAGE["data_url"] = data_url
    LAST_BUILD.update({"raw_readings": (read or {}).get("_raw"), "read_parts_px": (read or {}).get("parts"), "image_px": list(im.size), "mm_per_px": info["mm_per_px"],
                       "scale_source": info.get("scale_source"), "drawing_mm": info["drawing_mm"], "completion": completion,
                       "mode": info.get("mode")})
    step({"stage": "tool", "tool": "rebuild_3d"})
    specs, rep = rebuild.rebuild(info["parts"], info["drawing_mm"], completion, frame_cell_mm=info["mm_per_px"])
    if completion:
        rep["engineer_completion"] = {"by": "Muse Spark", "reasoning": str(completion.get("reasoning", ""))[:300],
                                      "parts_placed": len(completion.get("parts") or []),
                                      "hidden_parts_added": rep.get("added_by_engineer", [])}
    elif c_err:
        rep["engineer_completion"] = {"by": None, "error": c_err,
                                      "note": "Muse Spark's completion failed: depths, thicknesses and hidden parts follow the "
                                              "rebuild's own rules and are all assumed"}
    from engine import interpret
    check, check_img = interpret.drawing_check(im, rep.pop("_silhouette"), info["mm_per_px"])
    check["frame_part_overlap_mm2"] = rep["checks"]["frame_part_overlap_mm2"]
    # edge quality of what is built: pixel staircase on every part's outline in the drawing's view, and how far the
    # vectorised frame outlines are from their trace (engine/quality.py)
    from engine import quality
    flat = lab.default_state()
    lab.build_assembly(flat, "edge check", specs, position=[0, 0, 0], rotation=[0, 0, 0])
    st_len = st_steps = 0.0
    for p_, V_, F_ in geometry.scene_meshes(flat["parts"]):
        if p_["type"] != "group" and len(F_):
            _, l_, s_ = quality.part_staircase(V_, F_, info["mm_per_px"])
            st_len, st_steps = st_len + l_, st_steps + s_
    check["staircase_pct"] = round(100 * st_steps / max(st_len, 1e-9), 2)
    check["frame_outline_max_dev_px"] = round(rep["checks"].get("frame_outline_max_dev_mm", 0.0) / info["mm_per_px"], 2)
    LAST_REPORT.clear()
    LAST_REPORT.update({"kind": "machine drawing", "check": check, "gear_pairs": rep.get("gear_pairs"),
                        "implausible": rep.get("implausible"), "image_data_url": data_url,
                        # a patent drawing has no scale: sizes are model mm unless a dimension on it was read
                        "scale_known": str(info.get("scale_source", "")).startswith("read from"),
                        "scale_source": info.get("scale_source")})
    sam["result"]["check"] = check
    images["sam_check"] = vision._data_url(check_img, "JPEG")
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
            "sentences: what was " + ("read from the drawing (part types, positions, sizes, axis ends, teeth) and drawn as "
                                      "clean standard parts" if info.get("mode") == "interpret" else
                                      "traced from the drawing (outlines, positions, teeth)") + ", what was rebuilt from engineering "
            "rules or by your engineer's completion of the unseen views (depths, planes, added shafts and bearings), "
            "which gears mesh, what is still assumed (real size if no dimension was read, thicknesses), and the "
            f"front-view check: {check['drawing_lines_on_built_parts_pct']}% of the drawing's lines lie on a built part "
            "(red lines in the check image were not built). Say plainly that this is an interpretation of one view, "
            "not a measured model.")
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
            **({"below_surface_note": f"The design now reaches {-score['design_z_mm'][0]:.0f} mm behind the display surface on "
                                      "purpose: the desk's sharp zone extends behind it, and an AETHER Desk hologram may be "
                                      "shown there (it is still seen through the panel)."}
               if score["design_z_mm"][0] < -0.1 else {}),
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
