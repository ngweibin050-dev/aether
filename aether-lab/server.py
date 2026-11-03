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
import assistant  # noqa: E402
import projects  # noqa: E402
import compute  # noqa: E402
import explain  # noqa: E402

WEB = ROOT / "ui" / "dist" if (ROOT / "ui" / "dist" / "index.html").exists() else ROOT / "web"
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
_PROJECT = projects.ensure(lab.default_state())
STATE = _PROJECT.get("state") or lab.default_state()
# Imported meshes carry their whole geometry in params (vertices, faces, drawn lines: megabytes). The UI gets that
# geometry once from /api/meshes; the state it is sent leaves those fields out, and parts coming back from the UI
# (undo, edits) get them back from here, by part id.
HEAVY_KEYS = ("vertices", "faces", "lines", "normals", "regions")
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
HISTORY = _PROJECT.get("history") or []
CHAT = _PROJECT.get("chat") or []              # the chat as the app shows it
PROGRESS = {"running": False, "steps": []}
LAST_STEPS = []                                  # the last finished run's steps, for the build report
# the demo inputs (public domain, docs/INPUTS.md); real sizes are not on the drawings: assumed, and labelled so
DEMOS = {"D": ("tests/inputs/US929594_fig1.png", "machine", 300, "Metal drawing press", "US Patent 929,594, Fig. 1 (public domain)"),
         "C": ("tests/inputs/heldout/US1770035_fig1.png", "machine", 300, "Speed-reduction gearbox", "US Patent 1,770,035, Fig. 1 (public domain)")}
REC = OUT / "recorded"                           # the last successful live demo runs, replayed ONLY with a "recorded" label


def _recorded(demo_id):
    f = REC / f"{demo_id}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
LOCK = threading.Lock()
DIRTY = threading.Event()
STOP = threading.Event()                          # set by /api/chat/stop, cleared when a turn starts


def _autosave():
    """Write the open project 2 s after a change (coalesced: a slider drag is one save, not one per step)."""
    while True:
        DIRTY.wait()
        time.sleep(2.0)
        DIRTY.clear()
        try:
            with LOCK:
                snap = json.loads(json.dumps(STATE, default=str))
            projects.save(snap, HISTORY, CHAT)
        except Exception as e:
            print(f"project autosave failed: {e}", flush=True)


threading.Thread(target=_autosave, daemon=True).start()


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
            if code == 200 and not self.path.startswith(("/api/projects", "/api/transcribe", "/api/warm", "/api/files")):
                DIRTY.set()                                      # the autosaver writes the project within 2 s

    def _send_file(self, f):
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(f))[0] or "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{f.name}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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
            meshes, offsets = lab.meshes(STATE), lab.explode_offsets(STATE)
            asm_overlay(meshes, offsets)
            return self._send(200, {"version": STATE["version"], "meshes": meshes, "offsets": offsets,
                                    "brep": sorted(k for k, m in meshes.items() if m.get("brep"))})
        if path == "/api/jobs":                    # cheap: polled by the app (background jobs, scene version)
            return self._send(200, {"version": STATE.get("version"), "jobs": JOBS, "project": projects.CURRENT["slug"]})
        if path == "/api/files":
            return self._send(200, {"files": list_files()})
        if path == "/api/projects":
            return self._send(200, {"projects": projects.listing(), "current": projects.CURRENT["slug"]})
        if path == "/api/project":
            doc = projects._read(projects.CURRENT["slug"]) or {}
            return self._send(200, {"slug": projects.CURRENT["slug"], "name": doc.get("name"), "saved": doc.get("saved"),
                                    "chat": CHAT, "versions": projects.versions()})
        if path.startswith("/api/files/"):
            rel = path[len("/api/files/"):].split("/")
            if len(rel) == 2 and rel[0] in ("files", "exports"):
                import urllib.parse
                base = (projects.files_dir() if rel[0] == "files" else projects.exports_dir()).resolve()
                f = (base / urllib.parse.unquote(rel[1])).resolve()
                if str(f).startswith(str(base)) and f.is_file():
                    return self._send_file(f)
            return self._send(404, {"error": "not found"})
        if path == "/api/drawing":                 # the drawing the current machine was read from (balloon view)
            import base64
            url = agent.LAST_IMAGE.get("data_url")
            if not url:
                return self._send(404, {"error": "no drawing read in this session"})
            head, b64 = url.split(",", 1)
            return self._send(200, base64.b64decode(b64), head.split(";")[0].split(":")[-1] or "image/png")
        if path == "/api/asm/report":
            if (ASSEMBLY.get("step") or {}).get("roundtrip") == "running":     # the background STEP round trip
                import cad_client
                try:
                    ASSEMBLY["step"] = cad_client.call("asm_step_status")
                except Exception:
                    pass
            with LOCK:
                return self._send(200, asm_brief())
        if path == "/api/asm/export.step":
            f = (ASSEMBLY.get("step") or {}).get("path")
            if not f or not Path(f).is_file():
                return self._send(409, {"error": "no STEP yet: run Validate & export STEP first"})
            return self._send(200, Path(f).read_bytes(), "model/step")
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
        if self.path == "/api/chat/stop":            # stop the running turn after its current step (no lock needed)
            STOP.set()
            return self._send(200, {"stopping": True})
        if self.path == "/api/files":                # an attachment: saved to the files folder (PDF pages as images too)
            try:
                import urllib.parse
                return self._send(200, save_upload(urllib.parse.unquote(self.headers.get("X-Filename") or "file"), raw))
            except Exception as e:
                traceback.print_exc()
                return self._send(400, {"error": f"{type(e).__name__}: {e}"})
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
        if self.path.startswith("/api/projects/"):
            try:
                return self._send(200, project_route(self.path, json.loads(raw or b"{}")))
            except Exception as e:
                traceback.print_exc()
                return self._send(400, {"error": f"{type(e).__name__}: {e}"})
        if self.path in ("/api/asm/build", "/api/asm/step", "/api/asm/section"):
            try:
                return self._send(200, asm_route(self.path, json.loads(raw or b"{}")))
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
                    if body["name"] in ("import_mesh", "build_assembly") and not (res or {}).get("error"):
                        assistant.arrange(STATE)       # a new model stands on the desk, beside the others
                    return self._send(200, {"result": res, "state": lean(STATE), "gpu": compute.status})
                if self.path in ("/api/chat", "/api/photo", "/api/optimize"):
                    PROGRESS.update(running=True, steps=[])
                    try:
                        extras = {}
                        if self.path == "/api/chat":
                            STOP.clear()
                            att = body.get("attachments") or []
                            reply, trace, images, HISTORY, extras = assistant.turn(
                                STATE, HISTORY, body.get("text") or "", chat_ctx(att))
                            CHAT.append({"role": "user", "text": body.get("text") or "",
                                         "files": [{"name": n, "kind": _kind(n)} for n in att]})
                            if trace:
                                CHAT.append({"role": "steps", "trace": trace})
                            CHAT.append({"role": "ai", "text": reply, "extras": extras})
                            del CHAT[:-200]
                            if extras.get("changes"):
                                projects.snapshot(STATE, body.get("text") or "assistant change")
                        elif self.path == "/api/photo":        # phone photo -> SAM 3.1 -> Muse Spark -> physics
                            reply, trace, images, HISTORY = agent.photo_to_design(
                                STATE, HISTORY, body["image"], body.get("prompt") or "object",
                                float(body.get("size_mm") or 80), str(OUT), on_step,
                                body.get("mode") or "interpret", body.get("kind") or "auto")
                            assistant.arrange(STATE)
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
                    out = {"reply": reply, "trace": trace, "images": images, "state": lean(STATE), "gpu": compute.status,
                           **({"extras": extras} if extras else {})}
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
        assistant.arrange(STATE)                       # beside the other models, standing on the desk
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
                                ai_mode=body.get("ai_mode", "live"), stored_from=body.get("stored_from"), defer_detail=True)
        finally:
            PROGRESS["running"] = False
            PROGRESS["steps"][-1].update(state="ok", s=round(time.time() - PROGRESS["steps"][-1]["t0"], 1))
        imp, doc = cad_import_current(body.get("name") or "CAD model (three-view)")
        start_cad_detail(body.get("name") or "CAD model (three-view)")
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


# The machine's B-rep assembly (cad/assembly.py in the CAD worker): one exact solid per part. A part's B-rep mesh is
# shown while its type and parameters are unchanged (it is in the part's own frame, so moving it keeps it valid);
# validation, mates and STEP are of the poses they were computed for and are flagged stale once any part moves.
ASSEMBLY = {"report": None, "meshes": {}, "geo": {}, "pose": {}, "step": None, "built_at": None}


def _geo_key(p):
    return json.dumps([p["type"], p.get("params")], sort_keys=True, default=str)


def _pose_key(p):
    return json.dumps([p.get("position"), p.get("rotation"), p.get("scale"), p.get("parent")], default=str)


def asm_overlay(meshes, offsets):
    if not ASSEMBLY["report"]:
        return
    from engine import geometry
    import numpy as np
    by_id = {p["id"]: p for p in STATE["parts"]}
    for pid, m in ASSEMBLY["meshes"].items():
        p = by_id.get(pid)
        if p and ASSEMBLY["geo"].get(pid) == _geo_key(p):
            meshes[pid] = {**m, "brep": True}
    if asm_stale():
        return
    for pid, v in (ASSEMBLY["report"].get("explode_world") or {}).items():
        p = by_id.get(pid)
        if not p:
            continue
        par = by_id.get(p.get("parent"))
        L = geometry.world_matrix(par, by_id)[:3, :3] if par else np.eye(3)
        k = float(ASSEMBLY["report"].get("model_scale") or 1.0)          # model mm -> display mm
        offsets[pid] = np.linalg.solve(L, np.asarray(v, float) * k).round(3).tolist()   # world -> parent frame


def asm_stale():
    ids = {p["id"] for p in STATE["parts"] if p["type"] != "group"}
    if ids != set(ASSEMBLY["pose"]):
        return "parts were added or removed since the B-rep build"
    for p in STATE["parts"]:
        if p["id"] in ASSEMBLY["pose"] and (ASSEMBLY["pose"][p["id"]] != _pose_key(p) or ASSEMBLY["geo"][p["id"]] != _geo_key(p)):
            return f"{p['name']} changed since the B-rep build"
    return None


def asm_brief():
    r = ASSEMBLY["report"]
    if not r:
        return {"built": False}
    return {"built": True, "built_at": ASSEMBLY["built_at"], "stale": asm_stale(), "summary": r["summary"],
            "groups": r["groups"], "mates": r["mates"], "pairs": [p for p in r["pairs"] if p["status"] != "clear"],
            "records": r["records"], "step": ASSEMBLY["step"]}


def asm_route(path, body):
    import cad_client
    if path == "/api/asm/build":
        with LOCK:
            parts = [dict(p) for p in STATE["parts"]]
        PROGRESS.update(running=True, steps=[{"label": "brep_assembly", "state": "run", "t0": time.time(), "who": "OpenCascade"}])
        try:
            r = cad_client.call("asm_build", parts=parts, out_dir=str(OUT / "assembly"))
        finally:
            PROGRESS["running"] = False
            PROGRESS["steps"][-1].update(state="ok", s=round(time.time() - PROGRESS["steps"][-1]["t0"], 1))
        with LOCK:
            ASSEMBLY.update(report={k: v for k, v in r.items() if k != "meshes"}, meshes=r["meshes"], step=None,
                            geo={p["id"]: _geo_key(p) for p in parts if p["type"] != "group"},
                            pose={p["id"]: _pose_key(p) for p in parts if p["type"] != "group"},
                            built_at=time.strftime("%H:%M:%S"))
            STATE["version"] += 1                       # the UI refetches the meshes: now the B-rep tessellations
            return {**asm_brief(), "state": lean(STATE)}
    if not ASSEMBLY["report"]:
        raise RuntimeError("build the B-rep assembly first")
    if asm_stale() and path == "/api/asm/step":
        raise RuntimeError(f"the B-rep assembly is stale ({asm_stale()}): rebuild it before exporting")
    if path == "/api/asm/step":
        ASSEMBLY["step"] = cad_client.call("asm_step")
        return {"step": ASSEMBLY["step"]}
    if path == "/api/asm/section":
        return cad_client.call("asm_section", axis=body["axis"], offset=float(body["offset"]), flip=bool(body.get("flip")))
    raise ValueError(path)


KINDS = {"image": (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"), "pdf": (".pdf",), "mesh": (".glb", ".gltf", ".stl", ".obj"),
         "cad": (".step", ".stp")}


def _kind(name):
    ext = Path(name).suffix.lower()
    return next((k for k, v in KINDS.items() if ext in v), "other")


def save_upload(name, raw):
    """One uploaded file -> files/<name> (a unique name if taken). A PDF also becomes one PNG per page (first 12), so
    the assistant can read or build from a page."""
    import re
    FILES = projects.files_dir()
    FILES.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^\w.\- ]+", "_", Path(name).name).strip() or "file"
    f = FILES / name
    k = 1
    while f.exists():
        f = FILES / f"{Path(name).stem}_{k}{Path(name).suffix}"
        k += 1
    f.write_bytes(raw)
    out = {"name": f.name, "kind": _kind(f.name), "bytes": len(raw), "url": f"/api/files/files/{f.name}"}
    if out["kind"] == "pdf":
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(f))
        pages = []
        for i in range(min(len(pdf), 12)):
            im = pdf[i].render(scale=2.0).to_pil().convert("RGB")
            im.thumbnail((2400, 2400))
            pf = FILES / f"{f.stem}_p{i + 1}.png"
            im.save(pf)
            pages.append({"name": pf.name, "kind": "image", "bytes": pf.stat().st_size, "url": f"/api/files/files/{pf.name}"})
        out["pages"] = pages
        out["page_count"] = len(pdf)
    return out


def list_files():
    FILES = projects.files_dir()
    if not FILES.exists():
        return []
    return [{"name": f.name, "kind": _kind(f.name), "path": str(f), "bytes": f.stat().st_size}
            for f in sorted(FILES.iterdir(), key=lambda x: x.stat().st_mtime) if f.is_file()]


def _data_url(f):
    import base64
    b = Path(f["path"]).read_bytes()
    mime = mimetypes.guess_type(f["path"])[0] or "image/png"
    if f["kind"] == "image" and len(b) > 3_000_000:              # big photos: shrink before they go to a model
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(b)).convert("RGB")
        im.thumbnail((2000, 2000))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        b, mime = buf.getvalue(), "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(b).decode()


def chat_ctx(attachment_names):
    files = list_files()
    att = [f for f in files if f["name"] in set(attachment_names)]
    for a in list(att):                                   # a PDF brings its page images with it
        if a["kind"] == "pdf":
            att += [f for f in files if f["name"].startswith(Path(a["name"]).stem + "_p") and f["kind"] == "image"]
    return {"out_dir": str(OUT), "exports_dir": str(projects.exports_dir()), "cad_brep_dir": str(OUT / "cad" / "current" / "brep"),
            "files": files, "attachments": att, "data_url": _data_url, "on_step": on_step, "stopped": STOP.is_set,
            "asm": ASSEMBLY.get("report"),
            "have": {"B-rep assembly check": bool(ASSEMBLY.get("report")), "drawing reading (balloons)": bool(agent.LAST_IMAGE),
                     "build report": bool(agent.LAST_REPORT)}}


def _switch(doc):
    """Make doc (a project read from disk) the lab's scene, history and chat; per-project caches are cleared."""
    global HISTORY, CHAT
    with LOCK:
        STATE.clear()
        STATE.update(doc.get("state") or lab.default_state())
        STATE["version"] = int(STATE.get("version", 0)) + 1
        HISTORY = doc.get("history") or []
        CHAT = doc.get("chat") or []
        assistant.UNDO.clear()
        ASSEMBLY.update(report=None, meshes={}, geo={}, pose={}, step=None, built_at=None)
        agent.LAST_IMAGE.clear()
        agent.LAST_REPORT.clear()


def project_route(path, body):
    if path == "/api/projects/new":
        projects.save(STATE, HISTORY, CHAT)
        info = projects.create(body.get("name") or "Untitled project", lab.default_state())
        _switch(projects._read(info["slug"]))
        STATE["parts"] = []                                # a new project starts with an empty desk
        projects.save(STATE, HISTORY, CHAT)
        return {**info, "state": lean(STATE)}
    if path == "/api/projects/open":
        projects.save(STATE, HISTORY, CHAT)
        doc = projects.open_(body["slug"])
        _switch(doc)
        return {"slug": body["slug"], "name": doc.get("name"), "state": lean(STATE), "chat": CHAT}
    if path == "/api/projects/rename":
        return projects.rename(body["name"])
    if path == "/api/projects/delete":
        return projects.delete(body["slug"])
    if path == "/api/projects/snapshot":
        return {"version": projects.snapshot(STATE, body.get("label") or "saved by you")}
    if path == "/api/projects/restore":
        st = projects.version_state(body["n"])
        projects.snapshot(STATE, f"before restoring version {body['n']}")
        with LOCK:
            STATE["parts"] = st["parts"]
            STATE["selected"] = st.get("selected")
            STATE["version"] += 1
        projects.save(STATE, HISTORY, CHAT)
        return {"restored": body["n"], "state": lean(STATE)}
    raise ValueError(path)


JOBS = {}                                         # background work the app shows (e.g. the CAD detail pass)


def start_cad_detail(name):
    """The second pass of a progressive CAD build (pockets, imprints) in the background; the model is re-imported in
    place (same document: its placement on the desk is kept) when it is done."""
    import cad_client

    def run():
        JOBS["cad_detail"] = {"label": "CAD details (pockets, imprints)", "state": "running", "t0": time.time()}
        try:
            r = cad_client.call("detail")
            cad_import_current(name)
            JOBS["cad_detail"].update(state="done", s=round(time.time() - JOBS["cad_detail"]["t0"], 1),
                                      details=r.get("details"))
            DIRTY.set()
        except Exception as e:
            JOBS["cad_detail"].update(state="error", error=str(e)[:300])
    threading.Thread(target=run, daemon=True).start()


agent.ON_CAD_DETAIL = start_cad_detail


def _doc_brief(doc):
    return {k: doc[k] for k in ("title", "document_id", "maturity", "status", "stale")}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"AETHER Lab running: http://localhost:{port}  (compute: {compute.where()})")
    print("Meta key:", "found" if os.environ.get("META_API") else "MISSING (set META_API in .env)")
    compute.warm()
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
