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
- Geometry: you can NOT create or reshape geometry. Models enter the scene only as genuine OpenCascade B-rep CAD: a
  three-view drawing uploaded to the assistant (parametric CAD reconstruction) or Import STEP. If asked to create an
  object from text, say that text-to-CAD is not available yet; never imitate it with other tools. You may move,
  rotate, uniformly scale (display scale only), hide, rename and recolour existing parts with update_part. CAD
  parameters are edited in the CAD panel, not by you.
- After changing the scene, call focus_sweep (what the eye sees), then make_hologram if asked, so the
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
SCHEMAS = [
    ("update_part", "Move, rotate, uniformly scale (display only), rename, hide or recolour a part (id or name). "
     "Geometry can not be changed here.",
     {"id": {"type": "string"}, "position": _V3, "rotation": _V3,
      "scale": {**_V3, "description": "uniform: the same factor three times"},
      "name": {"type": "string"}, "visible": {"type": "boolean"}, "color": {"type": "string", "description": "hex colour"}}, ["id"]),
    ("delete_part", "Remove a whole model (root group) from the scene; hide components instead.", {"id": {"type": "string"}}, ["id"]),
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


LAST_BUILD = {}
LAST_REPORT = {}                                 # the last build's checks for the one-page report (engine/export.py)
LAST_IMAGE = {}                                  # the drawing the current machine was built from (Explain shows it to Muse Spark)


UNAVAILABLE = {
    "machine": ("This looks like a machine drawing. Machine-drawing reconstruction is unavailable: it used to build a triangle "
                "mesh, and its genuine B-rep CAD builder is not implemented yet (Phase C). Nothing was built and the scene "
                "is unchanged."),
    "part": ("This looks like a photo of one part. Part-photo reconstruction is unavailable: it used to build primitive "
             "meshes, and its genuine B-rep CAD builder is not implemented yet (Phase D). Nothing was built and the scene "
             "is unchanged."),
}


def photo_to_design(state, history, data_url, prompt, size_mm=None, out_dir=".", on_step=None, mode="interpret",
                    kind="auto"):
    """An upload -> genuine CAD, routed by what it IS (vision.upload_kind measures it, or the UI says it):
    - "three_view": a sheet with side / plan / end views of one object -> parametric CAD (cad/ package, OpenCascade
      B-rep, isolated worker). There is no mesh fallback: without the CAD environment it stops with an explicit error;
    - "machine" / "part": their B-rep builders do not exist yet (Phase C / D): an explicit error, nothing is built.
    The modes "trace" and "hull" (mask extrusion / visual hull) are removed. On every failure the scene is unchanged.
    Returns the same tuple as chat(), with the routing as the first step of the trace."""
    step = on_step or (lambda e: None)
    route = {"tool": "classify_upload", "args": {"asked": kind, "mode": mode}, "result": {"kind": kind, "by": "the user's choice"}}
    if mode not in (None, "", "interpret", "cad"):
        msg = (f"Mode {mode!r} is removed: it built a triangle mesh (SAM mask extrusion or a visual hull), not CAD. "
               "Nothing was built and the scene is unchanged.")
        route["result"].update(error=msg, scene_unchanged=True)
        return msg, [route], {}, history
    kind = kind if kind in vision.KINDS else "auto"
    if kind == "auto":
        step({"stage": "tool", "tool": "classify_upload"})
        kind, ev = vision.upload_kind(data_url)
        step({"stage": "done", "tool": "classify_upload"})
        route["result"] = {"kind": kind, "by": "measured on the image (no AI)", **ev}
    if kind in UNAVAILABLE:
        route["result"].update(error=UNAVAILABLE[kind], scene_unchanged=True, builder="unavailable")
        return UNAVAILABLE[kind], [route], {}, history
    from cad.scale import length_decision
    try:
        scale = length_decision(size_mm)
    except ValueError as e:
        route["result"].update(error=str(e), scene_unchanged=True)
        return str(e), [route], {}, history
    hints = [p.strip() for p in (prompt or "").split(",") if p.strip() and p.strip().lower() not in ("object", "drawing")]
    import cad_client
    if not cad_client.available():
        why = cad_client.LAST_CHECK.get("why", "CAD environment missing")
        route["result"].update(cad="CAD environment not ready", why=why, error=why, scene_unchanged=True)
        return ("This is a multi-view sheet. It is rebuilt as parametric CAD, which needs the CAD environment "
                f"(once: aether-lab/cad-worker/setup.ps1 on Windows, setup.sh on Linux/macOS; {why}). Nothing was built and "
                "the scene is unchanged.", [route], {}, history)
    compute.prewarm()
    reply, trace, images, hist = _sheet_to_cad(state, history, data_url, (hints or ["object"])[0], out_dir, step, scale)
    return reply, [route] + trace, images, hist


def _sheet_to_cad(state, history, data_url, prompt, out_dir, step, scale=None):
    """A multi-view sheet -> genuine parametric CAD (cad/ package, isolated OpenCascade worker): drawing interpretation,
    Muse Spark / Muse Wonder / SAM 3.1 stages (typed JSON only), a feature-based .aethercad document, validated B-rep,
    STEP round trip, three-view reprojection. The scene receives the B-rep's tessellation for display and physics, and
    ONLY after worker validation. A checkpoint rolls back ordinary scene-import exceptions; worker-crash and disk-failure
    recovery remain unverified. See the Phase 0/A report."""
    import base64
    import io
    from pathlib import Path
    import cad_client
    from PIL import Image
    out = Path(out_dir) / "cad" / "current"
    incoming = Path(out_dir) / "cad" / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    sheet = incoming / "sheet.png"
    Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[-1]))).convert("RGB").save(sheet)
    step({"stage": "tool", "tool": "cad_pipeline", "who": "AETHER CAD (Muse Spark + Muse Wonder + SAM 3.1 + OpenCascade)"})
    try:
        with cad_client.Transaction(out) as tx:
            r = cad_client.call("build", timeout=1200, sheet=str(sheet), out_dir=str(out),
                                decisions={"overall_length_mm": scale} if scale else None)
            if r["status"].get("state") != "ok":
                err = r["status"].get("error") or r["status"].get("state")
                step({"stage": "done", "tool": "cad_pipeline", "error": str(err)[:300]})
                return (f"The CAD reconstruction failed ({err}). The last valid CAD document is kept and the scene is unchanged.",
                        [{"tool": "cad_pipeline", "args": {}, "result": {"error": str(err), "build": r, "scene_unchanged": True}}],
                        {}, history)
            m = cad_client.call("meshes")
            doc = cad_client.call("document")
            import copy
            staged = copy.deepcopy(state)
            imp = lab.import_cad(staged, m["meshes"], m["groups"], f"{prompt[:40]} (CAD from three views)", doc["document_id"],
                                 provenance={"maturity": doc["maturity"], "route": doc.get("route")})
            imp["display_fit"] = _fit_to_desk(staged, imp["id"])
            tx.accept()
    except Exception as e:
        step({"stage": "done", "tool": "cad_pipeline", "error": str(e)[:300]})
        return (f"The CAD reconstruction failed: {e}. The scene was not replaced; check the worker transaction status.",
                [{"tool": "cad_pipeline", "args": {}, "result": {"error": str(e), "scene_unchanged": True}}], {}, history)
    state.clear()
    state.update(staged)
    step({"stage": "done", "tool": "cad_pipeline", "error": None})
    rep = r.get("report") or {}
    LAST_REPORT.clear()
    from cad.scale import length_decision
    scale = scale or length_decision(None)
    is_user_scale = scale["provenance"] == "user_confirmed"
    scale_text = (f"User-supplied reference overall length {scale['value']:g} mm; the final dimensions are not independently verified."
                  if is_user_scale else f"Reference overall length {scale['value']:g} mm is assumed; drawing dimensions are not automatically read.")
    LAST_REPORT.update({"kind": "three-view CAD", "image_data_url": data_url, "scale_known": is_user_scale,
                        "scale_source": scale_text,
                        "view_match_iou_pct": {k: round(100 * v, 1) for k, v in (rep.get("reprojection_iou") or {}).items()}})
    feats = [f for f in doc["features"]]
    text = (f"Built a parametric CAD model ({len(feats)} features, {len([c for c in doc['components'] if not c.get('group')])} "
            f"solid components) from the sheet. Maturity: {doc['maturity'].replace('_', ' ')}. All solids valid: "
            f"{rep.get('all_valid')}. STEP round trip: {'passed' if rep.get('step_all_pass') else 'not passed'}. "
            "Reprojection IoU per view: " + ", ".join(f"{k} {v:.3f}" for k, v in (rep.get("reprojection_iou") or {}).items())
            + ". " + scale_text + " The cross-sections between the end views and every recess depth are inferred or "
              "assumed and labelled so in the CAD panel.")
    trace = [{"tool": "cad_pipeline", "args": {}, "result": {"build": r, "import": imp,
                                                            "document": {k: doc.get(k) for k in ("title", "route", "maturity", "status")}}}]
    return text, trace, {}, history


# ---- Machine-drawing understanding (Muse Spark reading, Muse Wonder completion), kept for the Phase C CAD builder.
# These only call the models and return validated JSON; they build no geometry. In Phase A nothing calls them (the
# mesh pipeline that consumed them, engine/interpret.py + engine/rebuild.py, was removed).
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
