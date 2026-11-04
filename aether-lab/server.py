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

import numpy as np

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
import assistant
import history  # noqa: E402
import projects  # noqa: E402
import compute  # noqa: E402
import explain  # noqa: E402

WEB = ROOT / "ui" / "dist" if (ROOT / "ui" / "dist" / "index.html").exists() else ROOT / "web"
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
# the project opened at start: AETHER_PROJECT (a test server on a copy), else the most recently saved one. IMPORTED
# (tests import this module for its set-up) it opens a scratch project instead: the module saves the undo history and
# the scene to the open project, and an eval run must never write into the user's work (it did: an eval's "Sports car"
# ended up in a real project's undo history)
_SCRATCH = "_imported-by-tests"


def _start_project():
    if os.environ.get("AETHER_PROJECT"):
        return projects.open_(os.environ["AETHER_PROJECT"])
    if __name__ != "__main__":
        if not (projects.ROOT / _SCRATCH / "project.json").exists():
            st = lab.default_state()
            st["parts"] = []
            projects.create(_SCRATCH, st)
        return projects.open_(_SCRATCH)
    return projects.ensure(lab.default_state())


_PROJECT = _start_project()
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
    # a duplicate made in the app has a new id: it takes the geometry of the part it was copied from (the same CAD
    # component / B-rep file); without this it was saved with no mesh and the project could not be opened again
    src = {}
    for q in STATE["parts"]:
        e = q.get("eng") or {}
        if q["id"] in HEAVY:
            if e.get("brep"):
                src.setdefault(e["brep"], q["id"])
            if e.get("cad_component"):
                src.setdefault((e.get("cad_document"), e["cad_component"]), q["id"])
    for p in parts:
        prm = p.get("params") or {}
        if prm.get("_geometry") == "server":
            e = p.get("eng") or {}
            sid = p.get("id") if p.get("id") in HEAVY else (
                src.get(e.get("brep")) or src.get((e.get("cad_document"), e.get("cad_component"))))
            if sid:
                p = {**p, "params": {**{k: v for k, v in prm.items() if k != "_geometry"}, **HEAVY[sid]}}
        out.append(p)
    return out
HISTORY = _PROJECT.get("history") or []
CHAT = _PROJECT.get("chat") or []              # the chat as the app shows it
PROGRESS = {"running": False, "steps": []}
LAST_STEPS = []                                  # the last finished run's steps, for the build report
# the demo inputs (public domain, docs/INPUTS.md); real sizes are not on the drawings: assumed, and labelled so
DEMOS = {"D": ("tests/inputs/US929594_fig1.png", "machine", 300, "Metal drawing press", "US Patent 929,594, Fig. 1 (public domain)"),
         "C": ("tests/inputs/heldout/US1770035_fig1.png", "machine", 300, "Speed-reduction gearbox", "US Patent 1,770,035, Fig. 1 (public domain)"),
         "CAR": ("tests/inputs/heldout/CC0_Cobra_four_view.png", "three_view", 4000, "Roadster four-view sheet → CAD written by Muse",
                 "Shelby Cobra blueprint, Igor Križanovskij, CC0 (Wikimedia Commons)")}
DEMOS["P"] = ("tests/inputs/US929594_fig1.png", "machine", 1100, "1909 patent, one view → CAD with its unknowns",
              "US Patent 929,594, Fig. 1 (public domain)")
DEMOS = {"P": DEMOS.pop("P"), "CAR": DEMOS.pop("CAR"), **DEMOS}       # the CAD-program demos first
REC = OUT / "recorded"                           # the last successful live demo runs, replayed ONLY with a "recorded" label
CAD_FILES = ("model.aethercad", "sheet.png", "report.json", "model.step", "model.glb")   # a recorded CAD run's folder


def _recorded(demo_id):
    f = REC / f"{demo_id}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def _record_cad(demo_id, reply, steps):
    """A successful live CAD demo: keep the CAD folder (document, sheet, report, STEP, overlays) as its recorded run."""
    import shutil
    d = REC / demo_id
    d.mkdir(parents=True, exist_ok=True)
    for f in list(CAD_FILES) + [f.name for f in CAD_DIR.glob("reproject_*.png")]:
        if (CAD_DIR / f).exists():
            shutil.copy2(CAD_DIR / f, d / f)
    (REC / f"{demo_id}.json").write_text(json.dumps({"recorded_at": time.strftime("%Y-%m-%d %H:%M"), "reply": reply,
                                                       "steps": steps, "cad_dir": demo_id}, default=str), encoding="utf-8")


def _play_cad(demo_id, rec):
    """Replay a recorded CAD run: its folder becomes the open CAD document (recomputed from the stored model answers,
    no model call) and the model is added to the scene as one undo step."""
    import shutil
    import cad_client
    src = REC / rec["cad_dir"]
    CAD_DIR.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        shutil.copy2(f, CAD_DIR / f.name)
    cad_client.call("open", path=str(CAD_DIR / "model.aethercad"), sheet=str(CAD_DIR / "sheet.png"), out_dir=str(CAD_DIR))
    with LOCK:
        before = history.snapshot(STATE)
        imp, doc = _cad_import(f"{DEMOS[demo_id][3]} (recorded)")
        _record(before, f"demo: {DEMOS[demo_id][3]} (recorded run)", "build")
    DIRTY.set()
    return {**{k: v for k, v in rec.items() if k != "cad_dir"}, "document": _doc_brief(doc), "state": lean(STATE)}


def _fresh_ids(parts, taken):
    """Copies of parts whose ids are not in `taken` (a recorded model added twice), parents following."""
    import uuid
    new = {p["id"]: (uuid.uuid4().hex[:8] if p["id"] in taken else p["id"]) for p in parts}
    return [{**p, "id": new[p["id"]], "parent": new.get(p.get("parent"), p.get("parent"))} for p in parts]
# the open CAD document's folder (model.aethercad, brep/, sheet.png); a test server sets AETHER_CAD_DIR to its own
CAD_DIR = Path(os.environ.get("AETHER_CAD_DIR") or OUT / "cad" / "current")
LOCK = threading.Lock()


class _unlocked:
    """Inside a chat turn (which holds LOCK): let go of the scene while a long job runs elsewhere (a CAD build on Modal
    takes 10-20 min), so hide / move / delete / undo in the app are not stuck behind it; the turn takes it back after."""
    def __enter__(self):
        LOCK.release()

    def __exit__(self, *exc):
        LOCK.acquire()
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


EXPORTS = {"key": None, "files": {}}
EXPORT_LOCK = threading.Lock()


def _scene_export(path):
    """A download of the whole scene, built ONCE per scene version (clicking Export again, or five times quickly, gets
    the same bytes) and outside the scene lock: only a copy of the scene is taken under it, so a running AI turn or
    another download never queues behind the export."""
    from engine import export
    with EXPORT_LOCK:                                   # one build at a time; the others wait and reuse it
        with LOCK:
            key = STATE.get("version")
            if EXPORTS["key"] != key:
                EXPORTS.update(key=key, files={})
            hit = EXPORTS["files"].get(path)
            if hit:
                return hit
            snap = {**STATE, "parts": list(STATE["parts"])}
        if path.endswith(".glb"):
            out = export.glb(snap), "model/gltf-binary"
        elif path.endswith(".stl"):
            out = export.stl(snap), "model/stl"
        else:
            out = export.report_html(snap, agent.LAST_REPORT, LAST_STEPS).encode(), "text/html; charset=utf-8"
        EXPORTS["files"][path] = out
        return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # the browser hung up (a download clicked again, a tab closed, a poll cancelled): nothing to answer
            return
        if self.command == "POST":
            print(f"POST {self.path} {code} {len(data)} B in {time.time() - self._t0:.1f} s", flush=True)
            if code == 200 and not self.path.startswith(("/api/projects", "/api/transcribe", "/api/warm", "/api/files")):
                DIRTY.set()                                      # the autosaver writes the project within 2 s

    def _send_file(self, f):
        data = f.read_bytes()
        inline = "inline=1" in self.path                 # the chat's preview shows a PDF in the page
        try:
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(f))[0] or "application/octet-stream")
            self.send_header("Content-Disposition", f'{"inline" if inline else "attachment"}; filename="{f.name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            return

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/progress":            # live steps of the running chat turn (read without the lock)
            return self._send(200, {**PROGRESS, "now": time.time()})     # server clock, for the live step timers
        if path == "/api/history":
            with LOCK:
                return self._send(200, history.listing())
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
            if rec.get("program_report"):                # a recorded CAD-program run: its kept parts, as exact B-rep
                try:
                    import cad_client
                    ms = cad_client.call("program_meshes", report=rec["program_report"])["meshes"]
                    with LOCK:
                        before = history.snapshot(STATE)
                        imp = lab.import_cad(STATE, ms, [], f"{DEMOS[demo_id][3]} (recorded)", f"program:recorded-{demo_id}",
                                             provenance={"kind": "cad program", **rec["provenance"]})
                        agent._fit_to_desk(STATE, imp["id"])
                        assistant.arrange(STATE)
                        _record(before, f"demo: {DEMOS[demo_id][3]} (recorded run)", "build")
                    DIRTY.set()
                    return self._send(200, {**{k: v for k, v in rec.items() if k not in ("provenance",)}, "state": lean(STATE)})
                except Exception as e:
                    traceback.print_exc()
                    return self._send(500, {"error": f"recorded CAD-program run could not be opened: {type(e).__name__}: {e}"})
            if rec.get("cad_dir"):
                try:
                    return self._send(200, _play_cad(demo_id, rec))
                except Exception as e:
                    traceback.print_exc()
                    return self._send(500, {"error": f"recorded CAD run could not be opened: {type(e).__name__}: {e}"})
            # the recorded machine is ADDED beside the user's models (replacing the scene wiped their work, with no undo),
            # standing on the desk, as one undo step
            with LOCK:
                before = history.snapshot(STATE)
                STATE["parts"] += _fresh_ids(rec["state"]["parts"], {p["id"] for p in STATE["parts"]})
                assistant.arrange(STATE)
                STATE["version"] = int(STATE.get("version", 0)) + 1
                _record(before, f"demo: {DEMOS[demo_id][3]} (recorded run)", "build")
            DIRTY.set()
            return self._send(200, {**{k: v for k, v in rec.items() if k != "state"}, "state": lean(STATE)})
        if path in ("/api/export.glb", "/api/export.stl", "/api/report.html"):   # downloads of the current scene
            body, ctype = _scene_export(path)
            return self._send(200, body, ctype)
        if path == "/api/cad/document":
            sel = (self.path.split("sel=")[1].split("&")[0] if "sel=" in self.path else "")
            g = _program_model(sel) if sel else None
            if g:                                          # the selected model is an AI-written CAD program
                return self._send(200, _program_doc(g))
            import cad_client
            try:
                return self._send(200, cad_client.call("document", timeout=5))
            except Exception as e:
                g = _program_model()
                if g:                                      # no feature-tree document: the newest CAD program
                    return self._send(200, _program_doc(g))
                return self._send(409, {"error": str(e)})
        if path == "/api/cad/program_file":
            q = dict(x.split("=", 1) for x in self.path.split("?", 1)[-1].split("&") if "=" in x)
            g = _program_model(q.get("id", ""))
            name = q.get("f", "")
            if g and name in ("model.step", "model.glb", "report.json", "program.py", "params.json", "plan.json", "sheet.png"):
                f = Path(g["eng"]["program"]).parent / name
                if name == "sheet.png" and not f.is_file() and g["eng"].get("sheet"):
                    f = Path(g["eng"]["sheet"])          # a local build keeps the drawing where it was uploaded
                if f.is_file():
                    ctype = {"step": "model/step", "glb": "model/gltf-binary", "json": "application/json"}.get(f.suffix[1:], "text/plain")
                    return self._send(200, f.read_bytes(), ctype)
            return self._send(404, {"error": "not found"})
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
            f = CAD_DIR / name
            if f.suffix == ".png" and f.is_file():
                return self._send(200, f.read_bytes(), "image/png")
            return self._send(404, {"error": "not found"})
        if path == "/api/meshes":
            meshes, offsets = lab.meshes(STATE), lab.explode_offsets(STATE)
            asm_overlay(meshes, offsets)
            return self._send(200, {"version": STATE["version"], "meshes": meshes, "offsets": offsets,
                                    "brep": sorted(k for k, m in meshes.items() if m.get("brep"))})
        if path == "/api/jobs":                    # cheap: polled by the app (background jobs, scene version, project, Modal)
            return self._send(200, {"version": STATE.get("version"), "jobs": JOBS, "project": projects.CURRENT["slug"],
                                    "project_name": projects.meta().get("name"),
                                    "gpu": {"stale": bool(compute.status.get("stale")), "deploying": bool(compute.status.get("deploying")),
                                            "backend": compute.status.get("backend")}})
        if path == "/api/files":
            return self._send(200, {"files": list_files()})
        if path == "/api/projects":
            return self._send(200, {"projects": projects.listing(), "current": projects.CURRENT["slug"]})
        if path == "/api/chats":
            return self._send(200, projects.chat_list(CHAT))
        if path == "/api/project":
            doc = projects.meta()
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
        if path == "/api/brep/topology":
            pid = self.path.split("id=")[1].split("&")[0] if "id=" in self.path else ""
            p = next((x for x in STATE["parts"] if x["id"] == pid), None)
            f = ((p or {}).get("eng") or {}).get("brep")
            if not p:
                return self._send(404, {"error": "select a part first"})
            if p["type"] == "group":
                return self._send(404, {"error": "a group has no B-rep of its own: select one of its parts"})
            if not f or not Path(f).is_file():
                return self._send(404, {"error": f"'{p['name']}' has no exact B-rep file (only AI-written CAD parts carry one)"})
            import cad_client
            try:
                return self._send(200, {"part": p["name"], **cad_client.call("topology", brep=f, timeout=3)})
            except cad_client.Busy:
                return self._send(409, {"busy": True, "error": "The CAD worker is busy (a B-rep assembly or CAD build is "
                                                               "running): the topology appears as soon as it is free."})
            except Exception as e:
                return self._send(409, {"error": str(e)[:300]})
        if path == "/api/asm/connections":
            sel = (self.path.split("sel=")[1].split("&")[0] if "sel=" in self.path else "")
            g = _program_model(sel) if sel else None
            g = g or _program_model()
            if not g:
                return self._send(404, {"error": "no AI-written CAD model in the scene"})
            with LOCK:
                return self._send(200, connection_graph(g))
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
                    snap = {**STATE, "parts": [dict(p) for p in STATE["parts"]]}
                req = json.loads(raw or b"{}")
                PROGRESS.update(running=True, steps=[])
                try:
                    sub, m, image, scale, feats = assistant.explain_target(snap, chat_ctx([]), req.get("target"))
                    res = explain.explain(sub, image, on_step=on_step, scale=scale, model=m, cad_features=feats)
                finally:
                    PROGRESS["running"] = False
                demo_id = req.get("demo_id")
                if demo_id in DEMOS and _recorded(demo_id):            # kept with that demo's recorded run
                    rec = _recorded(demo_id)
                    rec["explain"] = res
                    (REC / f"{demo_id}.json").write_text(json.dumps(rec, default=str), encoding="utf-8")
                return self._send(200, res)
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        if self.path.startswith("/api/chats/"):
            try:
                return self._send(200, chat_route(self.path, json.loads(raw or b"{}")))
            except Exception as e:
                return self._send(400, {"error": f"{type(e).__name__}: {e}"})
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
                    if body["name"] == "export_film":     # into the project's exports: downloadable like any export
                        args["out_dir"] = str(projects.exports_dir())
                    before = history.snapshot(STATE)
                    res = compute.run(STATE, body["name"], args)
                    if body["name"] == "export_film" and isinstance(res, dict) and res.get("path"):
                        fp = Path(res["path"])
                        res.update(url=f"/api/files/{fp.parent.name}/{fp.name}", name=fp.name, bytes=fp.stat().st_size)
                    if body["name"] in ("import_mesh", "build_assembly") and not (res or {}).get("error"):
                        assistant.arrange(STATE)       # a new model stands on the desk, beside the others
                    if body.get("label", "") is not None:     # None: an animation or a live input (turning gears, hands)
                        _record(before, body.get("label") or TOOL_LABEL.get(body["name"], body["name"].replace("_", " ")))
                    return self._send(200, {"result": res, "state": lean(STATE), "gpu": compute.status})
                if self.path in ("/api/chat", "/api/photo", "/api/optimize"):
                    PROGRESS.update(running=True, steps=[])
                    try:
                        extras = {}
                        if self.path == "/api/chat":
                            STOP.clear()
                            att = body.get("attachments") or []
                            ctx = chat_ctx(att)
                            ctx["unlocked"] = _unlocked        # a long CAD job lets the app keep editing meanwhile
                            ctx["asm_build"] = lambda: asm_route("/api/asm/build", {}, own_progress=False)
                            reply, trace, images, HISTORY, extras = assistant.turn(STATE, HISTORY, body.get("text") or "", ctx)
                            CHAT.append({"role": "user", "text": body.get("text") or "",
                                         "files": [{"name": n, "kind": _kind(n), "url": f"/api/files/files/{n}"} for n in att]})
                            if trace:
                                CHAT.append({"role": "steps", "trace": trace})
                            CHAT.append({"role": "ai", "text": reply, "extras": extras})
                            del CHAT[:-200]
                            if extras.get("changes"):
                                projects.snapshot(STATE, body.get("text") or "assistant change")
                        elif self.path == "/api/photo":        # phone photo -> SAM 3.1 -> Muse Spark -> physics
                            before = history.snapshot(STATE)
                            reply, trace, images, HISTORY = agent.photo_to_design(
                                STATE, HISTORY, body["image"], body.get("prompt") or "object",
                                float(body.get("size_mm") or 80), str(OUT), on_step,
                                body.get("mode") or "interpret", body.get("kind") or "auto")
                            assistant.arrange(STATE)
                            _record(before, "build from " + (body.get("prompt") or "a drawing / photo"), "build")
                        else:                                  # closed design loop on the current scene
                            before = history.snapshot(STATE)
                            res = agent.optimize(STATE, float(body.get("target_pct", 80)), int(body.get("max_rounds", 3)), on_step)
                            _record(before, "make it sharp on the desk", "edit")
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
                    if (body.get("demo_id") in DEMOS and DEMOS[body["demo_id"]][1] == "three_view"
                            and not any((t.get("result") or {}).get("error") for t in trace)):
                        _record_cad(body["demo_id"], reply, [dict(x) for x in PROGRESS["steps"]])
                    elif body.get("demo_id") in DEMOS and not any((t.get("result") or {}).get("error") for t in trace):
                        REC.mkdir(parents=True, exist_ok=True)       # a successful live demo run: kept as the fallback
                        (REC / f"{body['demo_id']}.json").write_text(json.dumps(
                            {"recorded_at": time.strftime("%Y-%m-%d %H:%M"), "reply": reply, "trace": trace, "images": images,
                             "steps": [dict(x) for x in PROGRESS["steps"]], "state": STATE}, default=str), encoding="utf-8")
                    return self._send(200, out)
                if self.path == "/api/scene":          # bulk edits from the UI (delete, duplicate, colour, hide...)
                    before = history.snapshot(STATE)
                    new = restore(body["parts"])
                    # every move from the app is kept, also all of a model's parts at once (box-select + G); a model
                    # whose parts all carry the same transform is folded into its group at load (lab.fold_cad_leaves)
                    moved = lab.moved_program_parts(STATE["parts"], new)
                    STATE["parts"] = new
                    STATE["selected"] = body.get("selected")
                    if "view" in body:
                        STATE["view"] = body["view"]
                    STATE["version"] += 1
                    _record(before, body.get("label") or "edit in the app")
                    note = None
                    if moved:
                        note = (f"Moved {', '.join(moved[:3])}{' …' if len(moved) > 3 else ''} in the scene. The CAD program "
                                "and its STEP keep the original placement: ask Muse Spark to change the program to make it permanent.")
                    return self._send(200, {"state": lean(STATE), **({"note": note} if note else {})})
                if self.path in ("/api/undo", "/api/history/undo"):   # Ctrl+Z, the History panel, "undo this" in the chat
                    r = history.undo(STATE, body.get("id"))
                    if r.get("undone") and body.get("id") and self.path == "/api/undo":
                        CHAT.append({"role": "ai", "text": f"Undone: {r['reverted']} ({r['what']}).", "extras": {}})
                    _after_undo(r)
                    DIRTY.set()
                    return self._send(200, {"result": r, "state": lean(STATE), "history": history.listing()})
                if self.path == "/api/history/redo":
                    r = history.redo(STATE)
                    _after_undo(r)
                    DIRTY.set()
                    return self._send(200, {"result": r, "state": lean(STATE), "history": history.listing()})
                if self.path == "/api/reset":
                    before = history.snapshot(STATE)
                    STATE.clear()
                    STATE.update(lab.default_state())
                    HISTORY = []
                    _record(before, "reset the scene")
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
    with LOCK:
        return _cad_import(name)


def _cad_import(name):
    """cad_import_current without taking the lock (the caller holds it: an assistant turn adding a CAD feature). A
    re-import of the same document keeps the model where it is, at its size: only a new model is fitted and placed."""
    import cad_client
    m = cad_client.call("meshes")
    doc = cad_client.call("document")
    res = lab.import_cad(STATE, m["meshes"], m["groups"], name, doc["document_id"],
                         provenance={"maturity": doc["maturity"], "stale": m["stale"]})
    if not res.get("kept_placement"):
        # shown on the desk at one uniform DISPLAY scale (the CAD document keeps its real millimetres)
        res["display_fit"] = agent._fit_to_desk(STATE, res["id"])
        assistant.arrange(STATE)                       # beside the other models, standing on the desk
    return res, doc


assistant.CAD_REIMPORT = lambda name: _cad_import(name)[0]


def cad_route(path, body):
    """/api/cad/from_sheet {image (data URL), decisions?, ai_mode?}: the three-view CAD pipeline (cad/), model into the
    scene. /api/cad/param {id, value | clear_override}: transactional parameter edit + recompute, model refreshed.
    /api/cad/open {path}: open a saved .aethercad (recompute with replayed model answers)."""
    import base64
    import cad_client
    out = CAD_DIR
    if path == "/api/cad/from_sheet":            # retired: the rule-based car pipeline (cad/vehicle.py) is not used
        raise ValueError("retired: every drawing is now built as an AI-written CAD program; upload it in the chat")
    if path == "/api/cad/from_sheet_legacy":     # kept unreachable from the app, for the archived evidence only
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
    if path == "/api/cad/param" and body.get("program"):     # an AI-written CAD program: the same program re-run
        g = _program_model(body["program"])
        if not g:
            raise ValueError("that CAD-program model is no longer in the scene")
        with LOCK:
            before = history.snapshot(STATE)
        r = assistant.set_cad_param(STATE, chat_ctx([]), g["name"], {body["id"]: float(body["value"])})
        with LOCK:
            if r.get("changed"):
                _record(before, f"CAD parameter {body['id']} = {body['value']}", "edit")
        DIRTY.set()
        ok = bool(r.get("changed"))
        return {"edit": {"status": {"state": "ok" if ok else "failed", "rebuilt_features": "all", "failed": body["id"],
                                    "error": r.get("why")}, "seconds": None}, "state": lean(STATE)}
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


def asm_route(path, body, own_progress=True):
    """own_progress=False when a chat turn runs the build (its own steps show it)."""
    import cad_client
    if path == "/api/asm/build":
        with LOCK:
            parts = [dict(p) for p in STATE["parts"]]
        if own_progress:
            PROGRESS.update(running=True, steps=[{"label": "brep_assembly", "state": "run", "t0": time.time(), "who": "OpenCascade"}])
        try:
            r = cad_client.call("asm_build", parts=parts, out_dir=str(OUT / "assembly"))
        finally:
            if own_progress:
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
    return {"out_dir": str(OUT), "exports_dir": str(projects.exports_dir()), "cad_brep_dir": str(CAD_DIR / "brep"),
            "files": files, "attachments": att, "data_url": _data_url, "on_step": on_step, "stopped": STOP.is_set,
            "asm": ASSEMBLY.get("report"), "jobs": JOBS,
            "have": {"B-rep assembly check": bool(ASSEMBLY.get("report")), "drawing reading (balloons)": bool(agent.LAST_IMAGE),
                     "build report": bool(agent.LAST_REPORT)}}


def _after_load():
    """A project just loaded (at start-up or opened): its undo stack, and repairs of scenes saved by older versions:
    CAD components carrying a transform of their own, and models left metres off the desk (the old _bbox bug)."""
    history.load(projects.path(), STATE)
    assistant.INTAKE.clear()
    fixed = lab.fold_cad_leaves(STATE)
    if fixed:
        print(f"project: repaired CAD component transforms of {fixed}", flush=True)
    far = []
    for m in assistant.roots(STATE):
        lo, hi = assistant._bbox(lab.subtree(STATE, m["id"]))
        if lo is not None and np.abs((lo + hi) / 2)[:2].max() > 3000:
            far.append(m["name"])
    if far:
        assistant.arrange(STATE)
        print(f"project: brought back to the desk: {far}", flush=True)
    if fixed or far:
        STATE["version"] = int(STATE.get("version", 0)) + 1
        DIRTY.set()
    _reopen_cad()
    threading.Thread(target=_slim_meshes, daemon=True).start()


SLIM_TRIS = 8000                                    # a saved display mesh above this is re-made from its B-rep


def _slim_meshes():
    """Projects saved before the display meshing was size-relative carry meshes up to 30x too fine (a 20 m jet: 1.3 M
    triangles, a 100 MB project, a laggy view). Re-mesh those parts from their own .brep files once, in the background;
    the B-rep is unchanged, only the display mesh is lighter."""
    with LOCK:
        heavy = [p for p in STATE["parts"] if p.get("type") == "cad"
                 and (p.get("eng") or {}).get("brep") and len((p.get("params") or {}).get("faces") or []) > 3 * SLIM_TRIS]
        heavy += history.heavy_cad_parts(3 * SLIM_TRIS)      # the undo steps hold the same parts' old meshes
        items = {p["eng"]["brep"]: p["eng"]["brep"] for p in heavy}
    if not items:
        return
    import cad_client
    try:
        t = time.time()
        ms = cad_client.call("remesh_breps", items=items)["meshes"]
    except Exception as e:                       # noqa: BLE001 - the old meshes still work, only heavier
        print(f"display meshes not slimmed: {e}", flush=True)
        return
    with LOCK:
        n = 0
        for p in heavy:                              # the scene's parts and the undo steps' copies (same .brep, same solid)
            m = ms.get(p["eng"]["brep"])
            if m and m["f"]:
                p["params"] = {**p["params"], "vertices": m["v"], "faces": m["f"], "normals": m["n"], "lines": m["l"]}
                n += 1
        if n:
            STATE["version"] = int(STATE.get("version", 0)) + 1
    if n:
        DIRTY.set()
        _save_undo()
        print(f"display meshes: {n} CAD parts re-meshed lighter in {time.time() - t:.0f} s", flush=True)


def _reopen_cad():
    """After a restart the CAD worker has no document open, so a CAD model on the desk could not take CAD features
    (refining it) or be edited in the CAD panel. If the saved document belongs to a model of this project, it is opened
    again in the background (a full recompute: a few minutes); the app shows it as a job."""
    f = CAD_DIR / "model.aethercad"
    if not f.exists():
        return
    try:
        doc_id = json.loads(f.read_text(encoding="utf-8")).get("document_id")
    except (OSError, ValueError):
        return
    if not any((m.get("eng") or {}).get("cad_document") == doc_id for m in assistant.roots(STATE)):
        return
    sheet = f.parent / "sheet.png"

    def run():
        import cad_client
        JOBS["cad_open"] = {"label": "Opening the car's CAD document (for CAD edits)", "state": "running", "t0": time.time()}
        try:
            d = cad_client.call("document", timeout=5)
            if d.get("document_id") == doc_id:          # already open (the worker kept running)
                JOBS["cad_open"].update(state="done", s=0.0)
                return
        except Exception:
            pass
        try:
            cad_client.call("open", path=str(f), sheet=str(sheet) if sheet.exists() else None, out_dir=str(f.parent))
            JOBS["cad_open"].update(state="done", s=round(time.time() - JOBS["cad_open"]["t0"], 1))
        except Exception as e:
            JOBS["cad_open"].update(state="error", error=str(e)[:300])
    threading.Thread(target=run, daemon=True).start()


def _switch(doc):
    """Make doc (a project read from disk) the lab's scene, history and chat; per-project caches are cleared."""
    global HISTORY, CHAT
    with LOCK:
        STATE.clear()
        STATE.update(doc.get("state") or lab.default_state())
        STATE["version"] = int(STATE.get("version", 0)) + 1
        HISTORY = doc.get("history") or []
        CHAT = doc.get("chat") or []
        _after_load()
        ASSEMBLY.update(report=None, meshes={}, geo={}, pose={}, step=None, built_at=None)
        agent.LAST_IMAGE.clear()
        agent.LAST_REPORT.clear()


def chat_route(path, body):
    """Chats of the open project: several conversations about the same scene (the scene and its undo history are
    shared). /api/chats/new, /open {id}, /rename {id, title}, /delete {id}."""
    global HISTORY, CHAT
    if path in ("/api/chats/new", "/api/chats/open"):
        if PROGRESS.get("running"):
            raise ValueError("the AI is still answering in this chat: stop it or wait, then switch")
        with LOCK:
            cid, CHAT, HISTORY = projects.chat_switch(CHAT, HISTORY, body.get("id") if path.endswith("open") else None)
            assistant.INTAKE.clear()
        projects.save(STATE, HISTORY, CHAT)
        return {"id": cid, "chat": CHAT, **projects.chat_list(CHAT)}
    if path == "/api/chats/rename":
        return projects.chat_rename(body["id"], body.get("title"))
    if path == "/api/chats/delete":
        return projects.chat_delete(body["id"])
    raise ValueError(path)


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
        r = projects.rename(body["name"])
        DIRTY.set()                                      # written by the autosaver within 2 s
        return r
    if path == "/api/projects/delete":
        return projects.delete(body["slug"])
    if path == "/api/projects/snapshot":
        return {"version": projects.snapshot(STATE, body.get("label") or "saved by you")}
    if path == "/api/projects/restore":
        st = projects.version_state(body["n"])
        projects.snapshot(STATE, f"before restoring version {body['n']}")
        with LOCK:
            before = history.snapshot(STATE)
            STATE["parts"] = st["parts"]
            STATE["selected"] = st.get("selected")
            STATE["version"] += 1
            _record(before, f"restore version {body['n']}")
        projects.save(STATE, HISTORY, CHAT)
        return {"restored": body["n"], "state": lean(STATE)}
    raise ValueError(path)


JOBS = {}                                         # background work the app shows (e.g. the CAD detail pass)


UNDO_SAVE = threading.Lock()


def _save_undo():
    """The project's undo history to disk, off the request (a CAD body makes it megabytes)."""
    folder = projects.path()

    def run():
        with UNDO_SAVE:
            if projects.path() == folder:
                history.save(folder)
    threading.Thread(target=run, daemon=True).start()


history.ON_CHANGE = _save_undo


def _record(before, label, source="edit", extra=None):
    """A change of the scene made outside an assistant turn (an edit in the app, a background build) as a step of the
    project's undo history. The caller holds LOCK."""
    return history.record(before, STATE, label, source, extra)


TOOL_LABEL = {"update_part": "move / edit a part", "add_part": "add a part", "delete_part": "delete a part",
              "import_mesh": "import a 3D file", "place_on_base": "stand on the desk", "turn_gear": "turn the gears",
              "build_assembly": "build a machine"}


def _after_undo(r):
    """Undo / redo of a step that changed a CAD document (CAD features the assistant added): the document follows in the
    background (a recompute), the scene already shows the step's parts as they were."""
    for x in r.get("cad") or []:
        c = x["cad"]
        threading.Thread(target=_cad_follow, args=(c, bool(r.get("undone"))), daemon=True).start()


def _cad_follow(c, undone):
    import cad_client
    jid = "cad_history"
    JOBS[jid] = {"label": ("Taking the undone CAD features out of the CAD document" if undone
                           else "Putting the redone CAD features back into the CAD document"), "state": "running", "t0": time.time()}
    try:
        if undone:
            cad_client.call("remove_features", document_id=c["document_id"], ids=c["features"], timeout=None)
        else:
            cad_client.call("add_feature", document_id=c["document_id"], features=c["specs"], timeout=None)
        JOBS[jid].update(state="done", s=round(time.time() - JOBS[jid]["t0"], 1))
    except Exception as e:
        JOBS[jid].update(state="error", error=str(e)[:300])


def start_cad_detail(name):
    """The second pass of a progressive CAD build (pockets, imprints) in the background; the model is re-imported in
    place (same document: its placement on the desk is kept) when it is done."""
    import cad_client

    def run():
        JOBS["cad_detail"] = {"label": "CAD details (pockets, imprints)", "state": "running", "t0": time.time()}
        try:
            r = cad_client.call("detail")
            with LOCK:
                before = history.snapshot(STATE)
                _cad_import(name)
                _record(before, f"CAD details of {name} (windows, lights, grille)", "auto")
            JOBS["cad_detail"].update(state="done", s=round(time.time() - JOBS["cad_detail"]["t0"], 1),
                                      details=r.get("details"))
            DIRTY.set()
        except Exception as e:
            JOBS["cad_detail"].update(state="error", error=str(e)[:300])
    threading.Thread(target=run, daemon=True).start()


agent.ON_CAD_DETAIL = start_cad_detail




def _program_model(sel=""):
    """The AI-written CAD-program model for the CAD document panel: the selected part's model, else the newest one."""
    progs = [p for p in STATE["parts"] if (p.get("eng") or {}).get("kind") == "cad program" and p["eng"].get("program")]
    if sel:
        p = next((x for x in STATE["parts"] if x["id"] == sel), None)
        if p:
            r = assistant.root_of(STATE, p) if p.get("type") != "group" else p
            if r in progs:
                return r
        return None
    return progs[-1] if progs else None


def _ops(method):
    from feature_ops import ops_of                  # shared with the CAD worker's drawing (parts list)
    return ops_of(method)


def connection_graph(g):
    """A CAD-program model as an engineer's connection diagram: every part (item number, material), what it is mounted
    on with which joint and the evidence (Muse Wonder's plan), the plan's constraints, and for each connection what the
    B-rep assembly check found (contact / interference / clear) when it has been built for these parts."""
    e = g["eng"]
    d = Path(e["program"]).parent
    try:
        plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        plan = {}
    sub = lab.subtree(STATE, g["id"])
    by_name = {p["name"]: p for p in sub if p["type"] == "cad"}
    comps = [c for c in plan.get("components") or [] if c.get("name") in by_name]
    item = {c["name"]: i + 1 for i, c in enumerate(comps)}
    pairs = {}
    rep = ASSEMBLY.get("report") or {}
    for pr in rep.get("pairs") or []:
        pairs[frozenset((pr["a"], pr["b"]))] = pr["status"]
    checked = bool(rep) and any(p["id"] in (rep.get("records") or {}) for p in by_name.values())
    nodes, edges = [], []
    for c in comps:
        p = by_name[c["name"]]
        nodes.append({"id": p["id"], "item": item[c["name"]], "name": c["name"], "material": c.get("material"),
                      "parent": by_name[c["parent"]]["id"] if c.get("parent") in by_name else None,
                      "joint": c.get("joint") or ("root" if c.get("parent") in (None, "-", "") else "fixed"),
                      "ops": _ops(c.get("method")), "evidence": (c.get("evidence") or "")[:160]})
        q = by_name.get(c.get("parent"))
        if q is not None:
            st = pairs.get(frozenset((p["id"], q["id"]))) if checked else None
            edges.append({"a": p["id"], "b": q["id"], "joint": c.get("joint") or "fixed",
                          "brep": st or ("clear" if checked else "not checked"), "evidence": (c.get("evidence") or "")[:160]})
    cons = []
    for c in plan.get("constraints") or []:
        a, b = by_name.get(c.get("a")), by_name.get(c.get("b"))
        if a and b:
            cons.append({"a": a["id"], "b": b["id"], "type": c.get("type"), "value": c.get("value")})
    return {"model": g["name"], "model_id": g["id"], "nodes": nodes, "edges": edges, "constraints": cons,
            "brep_checked": checked, "unknowns": plan.get("unknowns") or []}


def _program_doc(g):
    """A CAD-program model in the CAD document panel's shape: its parameters with provenance (editable when the
    geometry reads them), the plan's components as the feature tree, the unknowns, and the checks of the kept round."""
    e = g["eng"]
    d = Path(e["program"]).parent
    rd = lambda f: (json.loads((d / f).read_text(encoding="utf-8")) if (d / f).exists() else {})
    params, plan, rep = rd("params.json"), rd("plan.json"), rd("report.json")
    stale = False                                  # saved with its own P(): the "unused" flags were wrong, not real
    try:
        import ast
        stale = any(isinstance(n, ast.FunctionDef) and n.name == "P"
                    for n in ast.parse((d / "program.py").read_text(encoding="utf-8")).body)
    except (OSError, SyntaxError):
        pass
    best = rep.get("best") or {}
    built = {p.get("name") for p in best.get("parts") or []}
    prov = {"user": "user_confirmed"}
    gates = best.get("gates")
    return {
        "kind": "program", "program_model": g["id"], "document_id": f"program:{e.get('program_id')}",
        "title": f"{g['name']} · AI-written CAD program v{e.get('version', 1)}",
        "maturity": "ai_written_program", "stale": False,
        "status": {"state": "ok", "seconds": rep.get("seconds"), "param_hash": f"{e.get('program_id')}-{e.get('version')}"},
        "parameters": [{"id": k, "value": v.get("value"), "unit": v.get("unit"), "provenance": prov.get(v.get("provenance"), v.get("provenance")),
                        "kind": "parameter" if (v.get("used", True) or stale) else "not read by the geometry",
                        "locked": v.get("used") is False and not stale,
                        "note": v.get("evidence")} for k, v in params.items() if isinstance(v, dict)],
        "features": [{"id": c["name"], "label": c["name"], "op": c.get("method") or "", "ops": _ops(c.get("method")),
                      "parent": c.get("parent") if c.get("parent") not in (None, "-", "") else None,
                      "joint": c.get("joint"),
                      "inputs": [c["parent"]] if c.get("parent") not in (None, "-", "") else [],
                      "params": [], "status": "ok" if c["name"] in built else "failed_optional", "evidence": c.get("evidence"),
                      "material": c.get("material")} for c in plan.get("components") or []],
        "assumptions": [{"id": f"U{i + 1}", "class": "unresolved" if u.get("critical") else "assumed",
                         "text": f"{u.get('what')}: {u.get('why')}", "editable_via": [u["would_resolve"]] if u.get("would_resolve") else []}
                        for i, u in enumerate(plan.get("unknowns") or [])],
        "decisions": {},
        "checks": {"gates": gates if isinstance(gates, str) else (gates or {}).get("summary"), "critic": best.get("critic"),
                   "iou": best.get("iou"), "proportion_error": best.get("proportion_error"),
                   "constraints": (plan.get("constraints") or [])[:40]},
        "sheet_url": (f"/api/cad/program_file?id={g['id']}&f=sheet.png"
                      if (d / "sheet.png").is_file() or (e.get("sheet") and Path(e["sheet"]).is_file()) else None),
        "object": plan.get("object"),
        "exports": [[t, f"/api/cad/program_file?id={g['id']}&f={f}", f] for t, f in
                    (("STEP", "model.step"), ("GLB", "model.glb"), ("Program", "program.py"), ("Report", "report.json"))],
    }


def _doc_brief(doc):
    return {k: doc[k] for k in ("title", "document_id", "maturity", "status", "stale")}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"AETHER Lab running: http://localhost:{port}  (compute: {compute.where()})")
    print("Meta key:", "found" if os.environ.get("META_API") else "MISSING (set META_API in .env)")
    compute.warm()
    _after_load()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if os.environ.get("AETHER_OPEN_BROWSER") == "1":   # start.bat: the page opens once the lab is ready to answer it
        import webbrowser
        threading.Timer(0.3, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    print(f"AETHER Lab ready: http://localhost:{port}", flush=True)
    httpd.serve_forever()
