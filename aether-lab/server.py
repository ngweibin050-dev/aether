"""AETHER Lab local server. Run: python server.py  ->  open http://localhost:8765"""
import copy
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

WEB = ROOT / "ui" / "dist"  # never serve the obsolete mesh-building web client
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
STATE = lab.default_state()
# Imported meshes carry their whole geometry in params (vertices, faces, drawn lines: megabytes). The UI gets that
# geometry once from /api/meshes; the state it is sent leaves those fields out, and parts coming back from the UI
# (undo, edits) get them back from here, by part id.
HEAVY_KEYS = ("vertices", "faces", "lines", "normals")
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


HISTORY = []
PROGRESS = {"running": False, "steps": []}
LAST_STEPS = []                                  # the last finished run's steps, for the build report
# Demos: the former demos (D, C: patent machine drawings) were built as triangle meshes and their "recorded" runs
# restored whole mesh scenes. Both are disabled until a CAD machine-drawing builder exists (Phase C).
DEMOS = {}
DEMOS_NOTE = "Demos are unavailable: the machine-drawing demos were mesh reconstructions (CAD version: Phase C)."
GONE = {"/api/demo/recorded": "Recorded demo runs are removed: they restored whole mesh scenes.",
        "/api/export.glb": "Scene GLB export is removed (it exported mesh parts). Use /api/cad/export.glb (from the B-rep).",
        "/api/export.stl": "Scene STL export is removed (a triangle mesh is not CAD). Use /api/cad/export.step."}
LOCK = threading.Lock()


def on_step(e):
    """Live steps of a running Muse Spark turn, read by the UI from /api/progress."""
    s = PROGRESS["steps"]
    now = time.time()
    if e["stage"] == "thinking":
        s.append({"label": "Muse Spark", "state": "run", "t0": now})
    elif e["stage"] == "tool":
        s.append({"label": e["tool"], "state": "run", "t0": now, **({"who": e["who"]} if e.get("who") else {})})
    elif s:
        if e.get("who"):                         # the model that actually answered (a fallback is named)
            s[-1]["who"] = e["who"]
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
        if path == "/api/demos":
            return self._send(200, {"demos": [], "note": DEMOS_NOTE})
        if path in GONE:
            return self._send(410, {"error": GONE[path], "error_kind": "unavailable"})
        if path == "/api/report.html":                      # the one-page report of the last build (no geometry)
            from engine import export
            with LOCK:
                body = export.report_html(STATE, agent.LAST_REPORT, LAST_STEPS).encode()
            return self._send(200, body, "text/html; charset=utf-8")
        if path == "/api/cad/document":
            import cad_client
            try:
                return self._send(200, cad_client.call("document"))
            except Exception as e:
                return self._send(409, {"error": str(e)})
        if path in ("/api/cad/export.step", "/api/cad/export.glb", "/api/cad/export.aethercad", "/api/cad/report.json"):
            import cad_client
            kind = path.rsplit(".", 1)[-1]
            kind = {"json": "report"}.get(kind, kind)
            try:
                f = cad_client.call("export", kind=kind)["path"]
            except Exception as e:
                return self._send(409, {"error": str(e)})
            ctype = {"step": "model/step", "glb": "model/gltf-binary", "aethercad": "application/json", "report": "application/json"}[kind]
            return self._send(200, Path(f).read_bytes(), ctype)
        if path.startswith("/api/cad/image/"):
            name = Path(path).name
            f = OUT / "cad" / "current" / name
            if f.suffix == ".png" and f.is_file():
                return self._send(200, f.read_bytes(), "image/png")
            return self._send(404, {"error": "not found"})
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
        if self.path == "/api/warm":               # demo: wake the Modal GPU container (and redeploy if out of date)
            compute.warm()
            compute.prewarm()
            return self._send(200, {"warming": compute.where() == "modal", "gpu": compute.status})
        if self.path == "/api/explain":            # Muse Spark explains the built machine (explain.py), off the lock
            try:
                with LOCK:
                    snap = {"parts": [dict(p) for p in STATE["parts"]]}
                PROGRESS.update(running=True, steps=[])
                try:
                    res = explain.explain(snap, agent.LAST_IMAGE.get("data_url"), on_step=on_step,
                                          scale={"known": agent.LAST_REPORT.get("scale_known", False),
                                                 "source": agent.LAST_REPORT.get("scale_source")})
                finally:
                    PROGRESS["running"] = False
                return self._send(200, res)
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        if self.path in ("/api/cad/from_sheet", "/api/cad/param", "/api/cad/open", "/api/cad/import_step"):
            try:
                body = json.loads(raw or b"{}")
                res = cad_route(self.path, body)
                return self._send(409 if res.get("error") else 200, res)
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        try:
            body = json.loads(raw or b"{}")
            with LOCK:
                if self.path == "/api/tool":
                    args = body.get("args", {})
                    if body["name"] in lab.DISABLED:
                        return self._send(410, {"error": lab.DISABLED[body["name"]], "error_kind": "unavailable",
                                                "state": lean(STATE)})
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
                        if self.path == "/api/photo":
                            LAST_STEPS[:] = [dict(x) for x in PROGRESS["steps"]]
                    out = {"reply": reply, "trace": trace, "images": images, "state": lean(STATE), "gpu": compute.status}
                    return self._send(200, out)
                if self.path == "/api/scene":          # undo / redo / bulk edits: display + placement of existing parts only
                    try:
                        lab.apply_scene_update(STATE, body.get("parts", []), body.get("selected"), body.get("view"))
                    except ValueError as e:
                        return self._send(422, {"error": str(e), "error_kind": "geometry_rejected", "state": lean(STATE)})
                    return self._send(200, {"state": lean(STATE)})
                if self.path == "/api/reset":
                    import cad_client
                    cad_client.stop_quietly()  # reset also closes the prior worker document; no stale export
                    HEAVY.clear()
                    agent.LAST_REPORT.clear()
                    LAST_STEPS.clear()
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


def cad_import_current(name, status_extra=None):
    """Bring the worker's current CAD model into the scene (tessellation of the validated B-rep). It REPLACES the scene:
    no earlier model, mesh or result stays next to it."""
    import cad_client
    m = cad_client.call("meshes")
    doc = cad_client.call("document")
    with LOCK:
        staged = copy.deepcopy(STATE)
        res = lab.import_cad(staged, m["meshes"], m["groups"], name, doc["document_id"],
                             provenance={"maturity": doc["maturity"], "stale": m["stale"], "route": doc.get("route")})
        # shown on the desk at one uniform DISPLAY scale (the CAD document keeps its real millimetres)
        res["display_fit"] = agent._fit_to_desk(staged, res["id"])
        STATE.clear()
        STATE.update(staged)
    return res, doc


def _cad_failed(stage, err, extra=None):
    """Report an error before scene import. Post-worker scene failures have a known transaction gap; see Phase 0/A report."""
    return {"error": f"{stage}: {err}", "scene_unchanged": True, "state": lean(STATE), **(extra or {})}


def _decode_upload(data_url):
    import base64
    return base64.b64decode(data_url.split(",", 1)[-1])


def cad_route(path, body):
    """/api/cad/from_sheet {image (data URL), decisions?, ai_mode?}: the three-view CAD pipeline (cad/), model into the
    scene. /api/cad/param {id, value | clear_override}: transactional parameter edit + recompute, model refreshed.
    /api/cad/open {path}: open a saved .aethercad (recompute with replayed model answers).
    /api/cad/import_step {file (data URL or base64), name?}: an external STEP file -> validated B-rep components
    (external provenance, no AETHER feature history).
    Worker-side invalid builds preserve the last document. Post-worker scene failures are not yet atomic; see Phase 0/A report."""
    import cad_client
    if not cad_client.available():
        return _cad_failed("CAD environment", "not installed (aether-lab/cad-worker/setup.ps1 or setup.sh); nothing was built")
    out = OUT / "cad" / "current"
    if path == "/api/cad/from_sheet":
        import io
        from PIL import Image
        incoming = OUT / "cad" / "incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        sheet = incoming / "sheet.png"
        Image.open(io.BytesIO(_decode_upload(body["image"]))).convert("RGB").save(sheet)
        PROGRESS.update(running=True, steps=[{"label": "cad_pipeline", "state": "run", "t0": time.time(), "who": "AETHER CAD"}])
        ok = False
        try:
            r = cad_client.call("build", sheet=str(sheet), out_dir=str(out), decisions=body.get("decisions"),
                                ai_mode=body.get("ai_mode", "live"), stored_from=body.get("stored_from"))
            ok = r["status"].get("state") == "ok"
        except Exception as e:
            r = {"error": f"{type(e).__name__}: {e}"}
        finally:
            PROGRESS["running"] = False
            PROGRESS["steps"][-1].update(state="ok" if ok else "error", s=round(time.time() - PROGRESS["steps"][-1]["t0"], 1))
        if not ok:
            return _cad_failed("CAD reconstruction failed", r.get("error") or r.get("status"), {"build": r})
        imp, doc = cad_import_current(body.get("name") or "CAD model (three-view)")
        return {"build": r, "import": imp, "document": _doc_brief(doc), "state": lean(STATE)}
    if path == "/api/cad/param":
        r = cad_client.call("set_param", id=body["id"], value=body.get("value"), clear_override=bool(body.get("clear_override")))
        if r["status"].get("state") != "ok":
            return _cad_failed("parameter edit rolled back", r["status"].get("error"), {"edit": r})
        imp, doc = cad_import_current(body.get("name") or "CAD model (three-view)")
        return {"edit": r, "import": imp, "document": _doc_brief(doc), "state": lean(STATE)}
    if path == "/api/cad/open":
        r = cad_client.call("open", path=body["path"], sheet=body.get("sheet"), out_dir=body.get("out_dir"))
        if r["status"].get("state") != "ok":
            return _cad_failed("document did not recompute", r["status"].get("error"), {"open": r})
        imp, doc = cad_import_current(body.get("name") or "CAD model")
        return {"open": r, "import": imp, "document": _doc_brief(doc), "state": lean(STATE)}
    if path == "/api/cad/import_step":
        incoming = OUT / "cad" / "incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        f = incoming / "import.step"
        f.write_bytes(_decode_upload(body["file"]))
        name = (body.get("name") or "Imported STEP")[:80]
        try:
            r = cad_client.call("import_step", path=str(f), out_dir=str(OUT / "cad" / "current"), name=name)
        except Exception as e:
            return _cad_failed("STEP import failed", f"{type(e).__name__}: {e}")
        imp, doc = cad_import_current(f"{name} (external STEP)")
        return {"import_step": r, "import": imp, "document": _doc_brief(doc), "state": lean(STATE)}
    raise ValueError(path)


def _doc_brief(doc):
    return {k: doc.get(k) for k in ("title", "document_id", "route", "maturity", "status", "stale")}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"AETHER Lab running: http://localhost:{port}  (compute: {compute.where()})")
    print("Meta key:", "found" if os.environ.get("META_API") else "MISSING (set META_API in .env)")
    compute.warm()
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
