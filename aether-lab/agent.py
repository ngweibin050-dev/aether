"""Muse Spark agent: turns a request into AETHER Lab tool calls, then explains the computed result.

Meta Model API is OpenAI-compatible (https://api.meta.ai/v1, Bearer key).
The key is read from the environment variable META_API (loaded from .env by server.py).
"""
import json
import os
import urllib.request

from engine import lab

API = os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")
MODEL = os.environ.get("META_MODEL", "muse-spark-1.3")
VOICE_MODEL = os.environ.get("META_VOICE_MODEL", "muse-voice-transcribe-1.0")
MAX_STEPS = 8

SYSTEM = """You are the AETHER Lab assistant, running a computational holography lab.
You control a 3D scene and a physics engine through tools. Rules:
- Use tools for every number. Never invent measurements; quote tool results.
- Distances: the hologram (display) is at z = 0; objects at z > 0 float in front of it.
  Scene units are mm. The full wave simulation runs on a small lab hologram (lab_slm, ~8 mm wide).
- Questions about AETHER Desk (a 27-inch eye-tracked 1D holographic desk from the user's
  pre-event physics study) use desk_check and search_column_width (eye-model simulation).
- After changing the scene, call make_hologram and then propagate or focus_sweep so the user
  sees the new result.
- Say clearly that results are simulations, not measurements of a built display.
- Answer in short, plain sentences, in the user's language."""

_P = {"type": "number"}
_V3 = {"type": "array", "items": _P, "minItems": 3, "maxItems": 3}
SCHEMAS = [
    ("set_scene", "Replace the scene with a list of gears.",
     {"objects": {"type": "array", "items": {"type": "object", "properties": {
         "type": {"type": "string", "enum": ["gear"]}, "teeth": {"type": "integer"},
         "radius_mm": _P, "rotate_deg": _V3, "position_mm": _V3}}}}, ["objects"]),
    ("move_object", "Move, rotate or reshape one object. rotate_deg is [x, y, z]; position_mm is [x, y, z].",
     {"index": {"type": "integer"}, "position_mm": _V3, "rotate_deg": _V3,
      "teeth": {"type": "integer"}, "radius_mm": _P}, []),
    ("set_display", "Change display parameters or load a preset (lab_slm or aether_desk).",
     {"preset": {"type": "string", "enum": ["lab_slm", "aether_desk"]}, "pitch_um": _P,
      "wavelength_nm": _P, "samples": {"type": "integer"}, "column_width_um": _P,
      "vertical_pitch_um": _P, "view_distance_cm": _P}, []),
    ("make_hologram", "Calculate the phase hologram for the current scene.",
     {"method": {"type": "string", "enum": ["points", "layers"]}}, []),
    ("propagate", "Show the reconstructed light at distance z_mm from the hologram.",
     {"z_mm": _P}, ["z_mm"]),
    ("focus_sweep", "Reconstruct at several depths to show which parts are sharp where.",
     {"z_start_mm": _P, "z_end_mm": _P, "steps": {"type": "integer"}}, []),
    ("desk_check", "AETHER Desk: sharpness the eye gets at heights above/below the panel (cm).",
     {"heights_cm": {"type": "array", "items": _P}, "column_width_um": _P,
      "view_distance_cm": _P}, []),
    ("search_column_width", "AETHER Desk: find the widest column that keeps an image sharp at a height.",
     {"height_cm": _P, "min_sharpness_pct": _P, "view_distance_cm": _P}, []),
    ("measure_speckle", "Measure speckle (grainy light) for one frame vs averaged frames.",
     {"frames": {"type": "integer"}}, []),
    ("export_film", "Make a printable film hologram for the laser-pointer test.",
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
            res = lab.run(state, name, args)
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
