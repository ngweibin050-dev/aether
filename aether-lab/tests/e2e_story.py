"""The whole AETHER story, end to end, through the app's own HTTP API (what the UI calls), timed and checked:

    python -m tests.e2e_story            # ~20-30 min, costs Meta API calls; writes docs/STORY.md + output/e2e_story/

A test server is started on port 8777 with its OWN project (output/projects/e2e-story, made fresh) and its own CAD
folder (AETHER_CAD_DIR=output/cad/e2e), so nothing of the user's work is touched.
  1. upload a three-view drawing, "build this car": the build starts, the assumed size labelled
  2. the CAD build and its detail pass finish in the background (exact B-rep)
  3. refine by chat: interior and lamps -> the result's own check must pass
  4. "cut it in half": the section view
  5. a real CAD feature by chat (a pocket in the B-rep body), the document recomputed
  6. the CAD document validated (every feature built, components valid)
  7. STEP export by chat, re-read in a FRESH OpenCascade process (cad_client import_step): valid solids
  8. the server is restarted: the project reopens with its history; the refine step is undone (only its parts go)
     and redone."""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PORT = 8777
BASE = f"http://127.0.0.1:{PORT}"
SLUG = "_e2e-story"
OUT = ROOT / "output" / "e2e_story"
CAD = ROOT / "output" / "cad" / "e2e"
DRAWING = ROOT / "output" / "cad" / "current" / "sheet.png"
STEPS = []


def http(path, body=None, raw=None, headers=None, timeout=900):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method="POST" if data is not None else "GET",
                                 headers=headers or {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def start_server():
    # AETHER_COMPUTE=local: the test server never touches the Modal GPU deployment (it would redeploy the engine)
    env = {**os.environ, "PORT": str(PORT), "AETHER_PROJECT": SLUG, "AETHER_CAD_DIR": str(CAD), "PYTHONIOENCODING": "utf-8",
           "AETHER_COMPUTE": "local"}
    log = open(OUT / "server.log", "a", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "server.py"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(240):
        try:
            http("/api/state", timeout=5)
            return p
        except Exception:
            time.sleep(1)
    raise RuntimeError("the test server did not start (output/e2e_story/server.log)")


def stop_server(p):
    p.terminate()
    try:
        p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill()


def step(n, title, fn):
    t0 = time.time()
    try:
        ok, detail = fn()
    except Exception as e:                               # noqa: BLE001 - a step that throws is a failed step
        ok, detail = False, f"{type(e).__name__}: {str(e)[:300]}"
    STEPS.append({"n": n, "step": title, "pass": bool(ok), "seconds": round(time.time() - t0, 1), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} {n}. {title} ({STEPS[-1]['seconds']} s): {str(detail)[:200]}", flush=True)
    return ok


def chat(text, attachments=()):
    r = http("/api/chat", {"text": text, "attachments": list(attachments)}, timeout=1200)
    for k, url in (r.get("images") or {}).items():
        if isinstance(url, str) and url.startswith("data:image"):
            (OUT / f"{len(STEPS) + 1}_{k}.jpg").write_bytes(base64.b64decode(url.split(",", 1)[1]))
    return r


def model(state):
    return next((p for p in state["parts"] if not p.get("parent") and (p.get("eng") or {}).get("cad_document")), None)


def wait_jobs(kinds, limit=2400):
    t0 = time.time()
    while time.time() - t0 < limit:
        jobs = http("/api/jobs")["jobs"]
        done = {k: v for k, v in jobs.items() if any(k.startswith(x) for x in kinds)}
        if done and all(v["state"] != "running" for v in done.values()) and all(any(k.startswith(x) for k in done) for x in kinds):
            return done
        time.sleep(5)
    raise TimeoutError(f"jobs {kinds} still running after {limit} s")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.jpg"):
        f.unlink()
    shutil.rmtree(ROOT / "output" / "projects" / SLUG, ignore_errors=True)
    shutil.rmtree(CAD, ignore_errors=True)
    import projects
    from engine import lab
    st0 = lab.default_state()
    st0["parts"] = []
    projects.create(SLUG, st0)
    if projects.CURRENT["slug"] != SLUG:                 # create() names the folder from the title: make it ours
        shutil.move(str(ROOT / "output" / "projects" / projects.CURRENT["slug"]), str(ROOT / "output" / "projects" / SLUG))
    srv = start_server()
    ctx = {}
    try:
        def s1():
            # a complete four-view sheet: AETHER builds at once and labels the size it assumed (the sheet has no
            # dimension); it asks first only when something critical is missing (half a sheet: tests/eval_refine.py)
            up = http("/api/files", raw=DRAWING.read_bytes(), headers={"X-Filename": "car_three_view.png"})
            r = chat("build this car from my drawing", [up.get("name") or "car_three_view.png"])
            b = next((t for t in r.get("trace") or [] if t["tool"] == "build_from_drawing"), None)
            res = (b or {}).get("result") or {}
            q = (r.get("extras") or {}).get("question")
            if q:                                          # it asked: answer with the size, then it builds
                r = chat("It is 4.5 m long (4500 mm).", [up.get("name") or "car_three_view.png"])
                b = next((t for t in r.get("trace") or [] if t["tool"] == "build_from_drawing"), None)
                res = (b or {}).get("result") or {}
            return bool(res.get("started_in_background")),                 f"asked first: {bool(q)}; build started in the background; assumed {res.get('will_assume')}"
        if not step(1, "Upload a three-view drawing; the CAD build starts (assumptions labelled)", s1):
            return
        def s2():
            jobs = wait_jobs(["cad_", "cad_detail"])
            st = http("/api/state")["state"]
            m = model(st)
            regions = sorted({r for p in st["parts"] for r in ((p.get("params") or {}).get("region_names") or [])})
            return m is not None and all(v["state"] == "done" for v in jobs.values()), \
                f"jobs {[(k, v['state'], v.get('s')) for k, v in jobs.items()]}; model {m and m['name']}; regions {regions}"
        if not step(2, "CAD build + detail pass in the background (exact B-rep)", s2):
            return
        def s3():
            r = chat("make the car more detailed: driver and passenger seats with seat belts, a dashboard, a steering "
                     "wheel, the engine, yellow headlights, red tail lights and white number plates")
            x = r.get("extras") or {}
            ctx["refine_undo"] = x.get("undo_id")
            ctx["refine_changes"] = x.get("changes") or []
            return x.get("status") == "checks_passed" and bool(ctx["refine_changes"]), \
                f"status {x.get('status')}; {len(ctx['refine_changes'])} changes; tools {[t['tool'] for t in r.get('trace') or []]}"
        step(3, "Refine by chat; the result's own check passes", s3)
        def s4():
            r = chat("cut it in half so I can see inside")
            v = http("/api/state")["state"].get("view") or {}
            return bool(v.get("section")), f"section {v.get('section')} at {v.get('section_mm')} mm"
        step(4, "Section view by chat", s4)
        def s5():
            r = chat("add a real CAD feature: a pocket for a front air intake, about 600 x 120 mm and 20 mm deep, centred "
                     "low on the front")
            cf = [t for t in r.get("trace") or [] if t["tool"] == "cad_feature"]
            added = [x for t in cf for x in ((t.get("result") or {}).get("added") or [])]
            return bool(added), f"cad_feature added {added}"
        step(5, "A real B-rep feature by chat (pocket), document recomputed", s5)
        def s6():
            d = http("/api/cad/document")
            feats = d.get("features") or []
            bad = [f["id"] for f in feats if f.get("status") not in ("ok", None, "failed_optional", "deferred")]
            return d.get("status", {}).get("state", "ok") == "ok" and not bad, \
                f"{len(feats)} features, status {d.get('status')}, not built {bad}"
        step(6, "CAD document validated", s6)
        def s7():
            r = chat("export the car as STEP")
            dl = [d for d in (r.get("extras") or {}).get("downloads") or [] if d["name"].lower().endswith(".step")]
            if not dl:
                return False, "no STEP download"
            f = ROOT / "output" / "projects" / SLUG / "exports" / dl[0]["name"]
            import cad_client                               # a fresh OpenCascade process of its own
            m = cad_client.call("import_step", path=str(f), timeout=None)
            cad_client.stop()
            solids = m.get("solids") or m.get("parts") or m.get("meshes")
            n = len(solids) if hasattr(solids, "__len__") else solids
            return bool(n), f"{f.name}: {f.stat().st_size} bytes, re-read: {n} solid(s) {str({k: v for k, v in m.items() if k not in ('meshes',)})[:200]}"
        step(7, "STEP export by chat, re-read in a fresh OpenCascade process", s7)
        def s8():
            nonlocal srv
            before = len(http("/api/state")["state"]["parts"])
            stop_server(srv)
            srv = start_server()
            h = http("/api/history")
            st = http("/api/state")["state"]
            if len(st["parts"]) != before:
                return False, f"reopened with {len(st['parts'])} parts, had {before}"
            if not ctx.get("refine_undo"):
                return False, "no refine step to undo"
            u = http("/api/history/undo", {"id": ctx["refine_undo"]})["result"]
            after_undo = len(http("/api/state")["state"]["parts"])
            r = http("/api/history/redo", {})["result"]
            after_redo = len(http("/api/state")["state"]["parts"])
            return u.get("undone") and r.get("redone") and after_redo == before and after_undo < before, \
                (f"reopened: {before} parts, {len(h['steps'])} history steps; undo '{u.get('reverted')}' -> {after_undo} parts "
                 f"({u.get('what')}; also {u.get('also_undone')}); redo -> {after_redo}")
        step(8, "Restart: the project reopens with its history; undo / redo of the refine step", s8)
    finally:
        stop_server(srv)
        (OUT / "story.json").write_text(json.dumps(STEPS, indent=1), encoding="utf-8")
        L = ["# AETHER Lab — one workflow, end to end", "",
             f"`python -m tests.e2e_story`, {time.strftime('%Y-%m-%d %H:%M')}: a test server and project of its own, driven "
             "through the app's HTTP API (what the UI calls), Muse Spark 1.3 + SAM 3.1 + OpenCascade.", "",
             f"**{sum(s['pass'] for s in STEPS)} / {len(STEPS)} steps pass, {round(sum(s['seconds'] for s in STEPS) / 60, 1)} min.**", "",
             "| # | step | result | seconds | what happened |", "|---|---|---|---|---|"]
        L += [f"| {s['n']} | {s['step']} | {'PASS' if s['pass'] else 'FAIL'} | {s['seconds']} | {str(s['detail']).replace('|', '/')[:400]} |"
              for s in STEPS]
        (ROOT / "docs" / "STORY.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
