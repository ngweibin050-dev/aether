"""AETHER Lab local server. Run: python server.py  ->  open http://localhost:8765"""
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def load_env():
    for p in (ROOT / ".env", ROOT.parent / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

from engine import lab  # noqa: E402
import agent  # noqa: E402
import compute  # noqa: E402
import explain  # noqa: E402

WEB = ROOT / "ui" / "dist" if (ROOT / "ui" / "dist" / "index.html").exists() else ROOT / "web"
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
STATE = lab.default_state()
# Imported meshes carry their whole geometry in params (vertices, faces, drawn lines: megabytes). The UI gets that
# geometry once from /api/meshes; the state it is sent leaves those fields out, and parts coming back from the UI
# (undo, edits) get them back from here, by part id.
HEAVY_KEYS = ("vertices", "faces", "lines")
HEAVY = {}


def lean(state):
    out = dict(state)
    parts = []
    for p in state.get("parts", []):
        prm = p.get("params") or {}
        if any(k in prm for k in HEAVY_KEYS):
            HEAVY[p["id"]] = {k: prm[k] for k in HEAVY_KEYS if k in prm}
            p = {**p, "params": {**{k: v for k, v in prm.items() if k not in HEAVY_KEYS}, "_geometry": "server"}}
        parts.append(p)
    out["parts"] = parts
    return out


def restore(parts):
    """Parts from the UI: put the geometry back that lean() left out."""
    out = []
    for p in parts:
        prm = p.get("params") or {}
        if prm.get("_geometry") == "server" and p.get("id") in HEAVY:
            p = {**p, "params": {**{k: v for k, v in prm.items() if k != "_geometry"}, **HEAVY[p["id"]]}}
        out.append(p)
    return out
HISTORY = []
PROGRESS = {"running": False, "steps": []}
LOCK = threading.Lock()


def on_step(e):
    """Live steps of a running Muse Spark turn, read by the UI from /api/progress."""
    s = PROGRESS["steps"]
    now = time.time()
    if e["stage"] == "thinking":
        s.append({"label": "Muse Spark", "state": "run", "t0": now})
    elif e["stage"] == "tool":
        s.append({"label": e["tool"], "state": "run", "t0": now})
    elif s:
        s[-1]["state"] = "error" if e.get("error") else "ok"
        s[-1]["s"] = round(now - s[-1].get("t0", now), 1)
        if isinstance(e.get("error"), str):
            s[-1]["detail"] = e["error"][:300]
    for x in s[:-1]:
        if x["state"] == "run":                 # a step is over when the next one starts
            x["state"] = "ok"
            x.setdefault("s", round(now - x.get("t0", now), 1))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        if self.command == "POST":
            print(f"POST {self.path} {code} {len(data)} B in {time.time() - self._t0:.1f} s", flush=True)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/progress":            # live steps of the running chat turn (read without the lock)
            return self._send(200, {**PROGRESS, "now": time.time()})     # server clock, for the live step timers
        if path == "/api/state":
            return self._send(200, {"state": lean(STATE), "compute": compute.where(), "gpu": compute.status})
        if path == "/api/meshes":
            return self._send(200, {"version": STATE["version"], "meshes": lab.meshes(STATE),
                                    "offsets": lab.explode_offsets(STATE)})
        if path.startswith("/output/"):
            f = OUT / Path(path).name
        else:
            f = (WEB / path.lstrip("/")) if path != "/" else WEB / "index.html"
        f = f.resolve()
        if not (str(f).startswith(str(WEB)) or str(f).startswith(str(OUT))) or not f.is_file():
            return self._send(404, {"error": "not found"})
        self._send(200, f.read_bytes(), mimetypes.guess_type(str(f))[0] or "application/octet-stream")

    def do_POST(self):
        global HISTORY
        self._t0 = time.time()
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        print(f"POST {self.path} received {len(raw)}/{n} B", flush=True)
        if self.path == "/api/transcribe":
            try:
                text = agent.transcribe(raw, self.headers.get("Content-Type", "audio/wav"))
                return self._send(200, {"text": text})
            except Exception as e:
                detail = e.read().decode(errors="ignore")[:300] if hasattr(e, "read") else ""
                return self._send(500, {"error": f"{type(e).__name__}: {e} {detail}"})
        if self.path == "/api/explain":            # Muse Spark explains the built machine (explain.py), off the lock
            try:
                with LOCK:
                    snap = {"parts": [dict(p) for p in STATE["parts"]]}
                PROGRESS.update(running=True, steps=[])
                try:
                    res = explain.explain(snap, agent.LAST_IMAGE.get("data_url"), on_step=on_step)
                finally:
                    PROGRESS["running"] = False
                return self._send(200, res)
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        try:
            body = json.loads(raw or b"{}")
            with LOCK:
                if self.path == "/api/tool":
                    args = body.get("args", {})
                    if body["name"] == "export_film":
                        args["out_dir"] = str(OUT)
                    res = compute.run(STATE, body["name"], args)
                    return self._send(200, {"result": res, "state": lean(STATE), "gpu": compute.status})
                if self.path in ("/api/chat", "/api/photo", "/api/optimize"):
                    PROGRESS.update(running=True, steps=[])
                    try:
                        if self.path == "/api/chat":
                            reply, trace, images, HISTORY = agent.chat(STATE, HISTORY, body["text"], str(OUT), on_step)
                        elif self.path == "/api/photo":        # phone photo -> SAM 3.1 -> Muse Spark -> physics
                            reply, trace, images, HISTORY = agent.photo_to_design(
                                STATE, HISTORY, body["image"], body.get("prompt") or "object",
                                float(body.get("size_mm") or 80), str(OUT), on_step,
                                body.get("mode") or "interpret", body.get("kind") or "auto")
                        else:                                  # closed design loop on the current scene
                            res = agent.optimize(STATE, float(body.get("target_pct", 80)), int(body.get("max_rounds", 3)), on_step)
                            images = res.pop("_images", {})
                            trace = [{"tool": "optimize_for_desk", "args": {}, "result": res}]
                            reply = None
                    finally:
                        PROGRESS["running"] = False
                        for x in PROGRESS["steps"]:
                            x["state"] = "ok" if x["state"] == "run" else x["state"]
                    return self._send(200, {"reply": reply, "trace": trace, "images": images, "state": lean(STATE), "gpu": compute.status})
                if self.path == "/api/scene":          # undo / redo / bulk edits from the UI
                    STATE["parts"] = restore(body["parts"])
                    STATE["selected"] = body.get("selected")
                    if "view" in body:
                        STATE["view"] = body["view"]
                    STATE["version"] += 1
                    return self._send(200, {"state": lean(STATE)})
                if self.path == "/api/reset":
                    STATE.clear()
                    STATE.update(lab.default_state())
                    HISTORY = []
                    return self._send(200, {"state": lean(STATE)})
            self._send(404, {"error": "not found"})
        except Exception as e:
            traceback.print_exc()
            try:
                self._send(500, {"error": f"{type(e).__name__}: {e}"})
            except OSError as e2:                      # the browser already hung up
                print(f"POST {self.path}: could not send the error ({e2})", flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"AETHER Lab running: http://localhost:{port}  (compute: {compute.where()})")
    print("Meta key:", "found" if os.environ.get("META_API") else "MISSING (set META_API in .env)")
    compute.warm()
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
