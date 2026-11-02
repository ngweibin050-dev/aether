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
LAST_STEPS = []                                  # the last finished run's steps, for the build report
# the demo inputs (public domain, docs/INPUTS.md); real sizes are not on the drawings: assumed, and labelled so
DEMOS = {"D": ("tests/inputs/US929594_fig1.png", "machine", 300, "Metal drawing press", "US Patent 929,594, Fig. 1 (public domain)"),
         "C": ("tests/inputs/heldout/US1770035_fig1.png", "machine", 300, "Speed-reduction gearbox", "US Patent 1,770,035, Fig. 1 (public domain)"),
         "G": ("tests/inputs/NASA_X-3_three_view.png", "three_view", 180, "Douglas X-3 three-view", "NASA Dryden graphic (public domain)")}
REC = OUT / "recorded"                           # the last successful live demo runs, replayed ONLY with a "recorded" label


def _recorded(demo_id):
    f = REC / f"{demo_id}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
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
            return self._send(200, {"demos": [{"id": k, "kind": v[1], "size_mm": v[2], "title": v[3], "source": v[4],
                                               "image": f"/demo/{k}.png", "recorded_at": (_recorded(k) or {}).get("recorded_at")}
                                              for k, v in DEMOS.items()]})
        if path.startswith("/demo/") and path[6:-4] in DEMOS and path.endswith(".png"):
            return self._send(200, (ROOT / DEMOS[path[6:-4]][0]).read_bytes(), "image/png")
        if path == "/api/demo/recorded":
            demo_id = self.path.split("id=")[-1][:4]
            rec = _recorded(demo_id)
            if not rec:
                return self._send(404, {"error": f"no recorded run of demo {demo_id} yet"})
            with LOCK:
                STATE.clear()
                STATE.update(rec["state"])
                STATE["version"] = int(STATE.get("version", 0)) + 1000
            return self._send(200, {**{k: v for k, v in rec.items() if k != "state"}, "state": lean(STATE)})
        if path in ("/api/export.glb", "/api/export.stl", "/api/report.html"):   # downloads of the current scene
            from engine import export
            with LOCK:
                if path.endswith(".glb"):
                    body, ctype = export.glb(STATE), "model/gltf-binary"
                elif path.endswith(".stl"):
                    body, ctype = export.stl(STATE), "model/stl"
                else:
                    body = export.report_html(STATE, agent.LAST_REPORT, LAST_STEPS).encode()
                    ctype = "text/html; charset=utf-8"
            return self._send(200, body, ctype)
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
                demo_id = json.loads(raw or b"{}").get("demo_id")
                if demo_id in DEMOS and _recorded(demo_id):            # kept with that demo's recorded run
                    rec = _recorded(demo_id)
                    rec["explain"] = res
                    (REC / f"{demo_id}.json").write_text(json.dumps(rec, default=str), encoding="utf-8")
                return self._send(200, res)
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        if self.path in ("/api/cad/from_sheet", "/api/cad/param", "/api/cad/open"):
            try:
                body = json.loads(raw or b"{}")
                res = cad_route(self.path, body)
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
                        if self.path == "/api/photo":
                            LAST_STEPS[:] = [dict(x) for x in PROGRESS["steps"]]
                    out = {"reply": reply, "trace": trace, "images": images, "state": lean(STATE), "gpu": compute.status}
                    if body.get("demo_id") in DEMOS and not any((t.get("result") or {}).get("error") for t in trace):
                        REC.mkdir(parents=True, exist_ok=True)       # a successful live demo run: kept as the fallback
                        (REC / f"{body['demo_id']}.json").write_text(json.dumps(
                            {"recorded_at": time.strftime("%Y-%m-%d %H:%M"), "reply": reply, "trace": trace, "images": images,
                             "steps": [dict(x) for x in PROGRESS["steps"]], "state": STATE}, default=str), encoding="utf-8")
                    return self._send(200, out)
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


def cad_import_current(name, status_extra=None):
    """Bring the worker's current CAD model into the scene (tessellation of the validated B-rep)."""
    import cad_client
    m = cad_client.call("meshes")
    doc = cad_client.call("document")
    with LOCK:
        res = lab.import_cad(STATE, m["meshes"], m["groups"], name, doc["document_id"],
                             provenance={"maturity": doc["maturity"], "stale": m["stale"]})
        # shown on the desk at one uniform DISPLAY scale (the CAD document keeps its real millimetres)
        res["display_fit"] = agent._fit_to_desk(STATE, res["id"])
    return res, doc


def cad_route(path, body):
    """/api/cad/from_sheet {image (data URL), decisions?, ai_mode?}: the three-view CAD pipeline (cad/), model into the
    scene. /api/cad/param {id, value | clear_override}: transactional parameter edit + recompute, model refreshed.
    /api/cad/open {path}: open a saved .aethercad (recompute with replayed model answers)."""
    import base64
    import cad_client
    out = OUT / "cad" / "current"
    if path == "/api/cad/from_sheet":
        out.mkdir(parents=True, exist_ok=True)
        raw = base64.b64decode(body["image"].split(",", 1)[-1])
        sheet = out / "sheet.png"
        from PIL import Image
        import io
        Image.open(io.BytesIO(raw)).convert("RGB").save(sheet)
        PROGRESS.update(running=True, steps=[{"label": "cad_pipeline", "state": "run", "t0": time.time(), "who": "AETHER CAD"}])
        try:
            r = cad_client.call("build", sheet=str(sheet), out_dir=str(out), decisions=body.get("decisions"),
                                ai_mode=body.get("ai_mode", "live"), stored_from=body.get("stored_from"))
        finally:
            PROGRESS["running"] = False
            PROGRESS["steps"][-1].update(state="ok", s=round(time.time() - PROGRESS["steps"][-1]["t0"], 1))
        imp, doc = cad_import_current(body.get("name") or "CAD model (three-view)")
        return {"build": r, "import": imp, "document": _doc_brief(doc), "state": lean(STATE)}
    if path == "/api/cad/param":
        r = cad_client.call("set_param", id=body["id"], value=body.get("value"), clear_override=bool(body.get("clear_override")))
        imp, doc = cad_import_current(body.get("name") or "CAD model (three-view)")
        return {"edit": r, "import": imp, "document": _doc_brief(doc), "state": lean(STATE)}
    if path == "/api/cad/open":
        r = cad_client.call("open", path=body["path"], sheet=body.get("sheet"), out_dir=body.get("out_dir"))
        imp, doc = cad_import_current(body.get("name") or "CAD model")
        return {"open": r, "import": imp, "document": _doc_brief(doc), "state": lean(STATE)}
    raise ValueError(path)


def _doc_brief(doc):
    return {k: doc[k] for k in ("title", "document_id", "maturity", "status", "stale")}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"AETHER Lab running: http://localhost:{port}  (compute: {compute.where()})")
    print("Meta key:", "found" if os.environ.get("META_API") else "MISSING (set META_API in .env)")
    compute.warm()
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
