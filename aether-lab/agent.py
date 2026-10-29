"""Muse Spark agent: turns a request into AETHER Lab tool calls, then explains the computed result.

Meta Model API is OpenAI-compatible (https://api.meta.ai/v1, Bearer key).
The key is read from the environment variable META_API (loaded from .env by server.py).
"""
import json
import os
import urllib.request

import compute
from engine import geometry, lab

API = os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")
MODEL = os.environ.get("META_MODEL", "muse-spark-1.3")
VOICE_MODEL = os.environ.get("META_VOICE_MODEL", "muse-voice-transcribe-1.0")
MAX_STEPS = 10

SYSTEM = """You are AETHER, the assistant inside a holographic 3D design desk (AETHER 2.0).
You build and edit 3D scenes and run a wave-optics physics engine through tools. Rules:
- Use tools for every number. Never invent measurements; quote tool results.
- Geometry: units mm. The hologram panel is the plane z = 0 (598 x 336 mm desk panel); parts float
  in front of it at z > 0. Keep designs within about 0-120 mm height: the physics study says the
  AETHER Desk is sharp within about +-100 mm of the panel.
- Text-to-CAD: when asked to create an object or machine, call build_assembly with a list of
  parametric parts (types: """ + ", ".join(f"{k}({v})" for k, v in geometry.PARAM_HELP.items()) + """).
  Positions/rotations (deg, [x,y,z]) are relative to the assembly. Axis of round parts is local z.
  Aim for 6-25 parts that capture the real structure. Say it is a simplified parametric model,
  not manufacturer data.
- After building or changing the scene, call make_hologram, then focus_sweep or eye_view so the
  user sees the hologram. For "can the desk show it" use window_check and desk_check.
- Speckle questions: speckle_compare. Hand questions: hand_check.
- Say clearly that results are simulations, not measurements of a built display.
- Answer in short, plain sentences, in the user's language."""

_P = {"type": "number"}
_V3 = {"type": "array", "items": _P, "minItems": 3, "maxItems": 3}
_PART = {"type": "object", "properties": {
    "name": {"type": "string"}, "type": {"type": "string", "enum": sorted(geometry.BUILDERS)},
    "params": {"type": "object"}, "position": _V3, "rotation": _V3, "scale": _V3,
    "parent": {"type": "string", "description": "name of another part in this assembly"}},
    "required": ["name", "type", "params"]}
SCHEMAS = [
    ("build_assembly", "Create a new assembly from parametric parts (text-to-CAD). Replaces the scene by default.",
     {"name": {"type": "string"}, "parts": {"type": "array", "items": _PART}, "position": _V3,
      "replace": {"type": "boolean"}}, ["name", "parts"]),
    ("add_part", "Add one part.", {"type": {"type": "string", "enum": sorted(geometry.BUILDERS)},
     "params": {"type": "object"}, "name": {"type": "string"}, "position": _V3, "rotation": _V3,
     "scale": _V3, "parent": {"type": "string"}}, ["type"]),
    ("update_part", "Move, rotate, scale, rename, hide or re-parameterise a part (id or name).",
     {"id": {"type": "string"}, "position": _V3, "rotation": _V3, "scale": _V3, "params": {"type": "object"},
      "name": {"type": "string"}, "visible": {"type": "boolean"}}, ["id"]),
    ("delete_part", "Delete a part and its children.", {"id": {"type": "string"}}, ["id"]),
    ("list_parts", "List all parts in the scene.", {}, []),
    ("set_display", "Change the lab hologram (pitch_um, wavelength_nm, samples, distance_mm, points, method) "
     "or AETHER Desk parameters (column_width_um, vertical_pitch_um, view_distance_mm).",
     {"preset": {"type": "string", "enum": ["lab_slm", "aether_desk"]}, "pitch_um": _P, "wavelength_nm": _P,
      "samples": {"type": "integer"}, "distance_mm": _P, "points": {"type": "integer"},
      "method": {"type": "string", "enum": ["wrp", "points", "layers"]}, "column_width_um": _P,
      "vertical_pitch_um": _P, "view_distance_mm": _P}, []),
    ("set_eye", "Move the viewer's eye (mm, desk frame; default 0,0,700).",
     {"x_mm": _P, "y_mm": _P, "z_mm": _P}, []),
    ("make_hologram", "Calculate the phase hologram of the current scene (hidden surfaces removed).", {}, []),
    ("propagate", "Reconstructed light at scene depth z_mm.", {"z_mm": _P}, []),
    ("focus_sweep", "Reconstruct at several depths through the object.", {"steps": {"type": "integer"}}, []),
    ("eye_view", "What an eye at (eye_x_mm, eye_y_mm) sees through its pupil, focused at focus_z_mm.",
     {"eye_x_mm": _P, "eye_y_mm": _P, "focus_z_mm": _P}, []),
    ("window_check", "Window Law at desk scale: % of each part the eye can see through the panel.",
     {"eye_x_mm": _P, "eye_y_mm": _P}, []),
    ("hand_check", "Check the tracked hand for occlusion depth conflicts.", {"hand_radius_mm": _P}, []),
    ("desk_check", "AETHER Desk: eye-model sharpness at heights above/below the panel (cm).",
     {"heights_cm": {"type": "array", "items": _P}, "column_width_um": _P, "view_distance_cm": _P}, []),
    ("search_column_width", "AETHER Desk: widest column keeping >= min_sharpness_pct at height_cm.",
     {"height_cm": _P, "min_sharpness_pct": _P, "view_distance_cm": _P}, []),
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


def chat(state, history, user_text, out_dir="."):
    """Run one user turn. Returns (reply_text, trace, images, new_history)."""
    msgs = [{"role": "system", "content": SYSTEM}] + history + [{"role": "user", "content": user_text}]
    trace, images = [], {}
    for _ in range(MAX_STEPS):
        resp = _post("/chat/completions", {"model": MODEL, "messages": msgs, "tools": TOOL_DEFS})
        m = resp["choices"][0]["message"]
        calls = m.get("tool_calls") or []
        msgs.append({k: v for k, v in m.items() if k in ("role", "content", "tool_calls")})
        if not calls:
            hist = [x for x in msgs[1:] if x["role"] in ("user", "assistant") and not x.get("tool_calls")]
            return m.get("content") or "", trace, images, hist[-12:]
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if name == "export_film":
                args["out_dir"] = out_dir
            res = compute.run(state, name, args)
            images.update(res.get("_images", {}))
            slim = lab.for_agent(res)
            trace.append({"tool": name, "args": args, "result": slim})
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(slim)})
    return "Stopped after too many steps.", trace, images, history


def transcribe(audio, mime="audio/webm"):
    """Muse Voice Transcribe: speech -> text (OpenAI-style multipart upload)."""
    key = os.environ.get("META_API")
    if not key:
        raise RuntimeError("META_API is not set in .env")
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/wav": "wav"}.get(mime.split(";")[0], "webm")
    b = "----aether" + os.urandom(8).hex()
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{VOICE_MODEL}\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"speech.{ext}\"\r\n"
            f"Content-Type: {mime.split(';')[0]}\r\n\r\n").encode() + audio + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(API + "/audio/transcriptions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()).get("text", "")
