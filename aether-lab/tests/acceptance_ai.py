"""The 14 acceptance tests of the AI-orchestration directive (docs/AI_ORCHESTRATION_AUDIT.md), through the app's own
chat API (what the UI calls), on a test server with its own project.

    python -m tests.acceptance_ai           # ~45-90 min, costs Meta API calls; writes docs/ACCEPTANCE.md + output/acceptance/

Every test records: the request, the tools the AI chose (the trace), each call's result, the artifacts, and the check
that decides pass / fail. A check reads what EXECUTED (tool results, files on disk, the scene), never the reply text,
except where the right answer is an honest "this cannot be computed" (tests 6, 13), which is recorded for review."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests import e2e_story as E  # noqa: E402  (server start / stop, http, chat helpers)

E.SLUG = "_acceptance-ai"
E.PORT = 8778                                                      # its own port
E.BASE = f"http://127.0.0.1:{E.PORT}"
E.OUT = ROOT / "output" / "acceptance"
E.CAD = ROOT / "output" / "cad" / "acceptance"
DRAWING = ROOT / "tests" / "inputs" / "NASA_X-3_three_view.png"      # an aircraft: no dedicated construction code
RESULTS = []


def tools(r):
    return [t["tool"] for t in r.get("trace") or []]


def calls(r, name):
    return [t for t in r.get("trace") or [] if t["tool"] == name]


def program_model(state):
    return [p for p in state["parts"] if not p.get("parent") and (p.get("eng") or {}).get("kind") == "cad program"]


def record(n, title, request, r, ok, check, artifacts=()):
    tr = [{"tool": t["tool"], "args": t.get("args"), "result": (json.dumps(t.get("result"), default=str)[:600])}
          for t in r.get("trace") or []] if isinstance(r, dict) else []
    RESULTS.append({"n": n, "test": title, "request": request, "pass": bool(ok), "check": check,
                    "tools": [t["tool"] for t in tr], "calls": tr, "reply": (r.get("reply") or "")[:1200] if isinstance(r, dict) else "",
                    "artifacts": [str(a) for a in artifacts]})
    print(f"{'PASS' if ok else 'FAIL'} {n}. {title}: {check}  tools={[t['tool'] for t in tr]}", flush=True)


def run(n, title, request, check_fn, attachments=()):
    t0 = time.time()
    try:
        r = E.chat(request, attachments)
        ok, check, arts = check_fn(r)
    except Exception as e:                                       # noqa: BLE001
        r, ok, check, arts = {}, False, f"{type(e).__name__}: {str(e)[:300]}", []
    record(n, title, request, r, ok, check, arts)
    RESULTS[-1]["seconds"] = round(time.time() - t0, 1)
    return r


def downloads(r):
    return [d for d in ((r.get("extras") or {}).get("downloads") or [])]


def main():
    E.OUT.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(ROOT / "output" / "projects" / E.SLUG, ignore_errors=True)
    shutil.rmtree(E.CAD, ignore_errors=True)
    import projects
    from engine import lab
    st0 = lab.default_state()
    st0["parts"] = []
    projects.create(E.SLUG, st0)
    if projects.CURRENT["slug"] != E.SLUG:
        shutil.move(str(ROOT / "output" / "projects" / projects.CURRENT["slug"]), str(ROOT / "output" / "projects" / E.SLUG))
    srv = E.start_server()
    files_dir = ROOT / "output" / "projects" / E.SLUG
    try:
        up = E.http("/api/files", raw=DRAWING.read_bytes(), headers={"X-Filename": "x3_three_view.png"})
        fname = up.get("name") or "x3_three_view.png"

        def t1(r):
            b = [t for t in r.get("trace") or [] if t["tool"] in ("build_cad", "build_from_drawing")]
            built = [t for t in b if (t.get("result") or {}).get("built")]
            ms = program_model(E.http("/api/state")["state"])
            return bool(built and ms), (f"{len(b)} build call(s), {len(built)} built (a failed first attempt the AI retried "
                                        f"counts only if the retry built); program models in scene={len(ms)}; kept="
                                        f"{(built[-1]['result'] if built else {}).get('kept')}"), []
        run(1, "Unfamiliar drawing -> 3D model", "Create a 3D model from this engineering drawing.", t1, [fname])

        def t2(r):
            e = calls(r, "edit_cad")
            res = (e[-1]["result"] if e else {}) or {}
            return bool(e and res.get("changed")), f"edit_cad changed={res.get('changed')} version={res.get('version')}", []
        run(2, "Modify the model in natural language", "Make the wings thicker and add more detail to the cockpit canopy.", t2)

        def t3(r):
            d = calls(r, "make_drawing")
            fs = [x for x in downloads(r) if str(x.get("name", x.get("url", ""))).lower().endswith((".pdf", ".svg"))]
            return bool(d and not (d[-1].get("result") or {}).get("error") and fs), f"make_drawing called, {len(fs)} drawing files", fs
        run(3, "Blueprint from the current model", "Generate an engineering blueprint from the current 3D model.", t3)

        def t4(r):
            ex = calls(r, "explain_machine")
            steps = ((r.get("extras") or {}).get("explain") or {}).get("steps") or []
            return bool(ex and steps), f"explain_machine called, {len(steps)} steps in the Explain panel", []
        run(4, "Explain the machine", "Explain how this machine works.", t4)

        st = E.http("/api/state")["state"]
        pm = program_model(st)
        part = next((p["name"] for p in st["parts"] if pm and p.get("parent") == pm[0]["id"]), "the first part")

        def t5(r):
            used = [t for t in r.get("trace") or [] if t["tool"] in ("inspect", "explain_machine", "list_parts")]
            return bool(pm and used and r.get("reply")), f"tools {[t['tool'] for t in used]} on '{part}' (program model: {bool(pm)})", []
        run(5, "Explain one component", f"Explain the function of the component called '{part}'.", t5)

        def t6(r):
            sim = [t for t in r.get("trace") or [] if t["tool"] in ("turn_gear", "set_view", "analyze")]
            honest = any(w in (r.get("reply") or "").lower() for w in ("cannot", "can't", "not able", "no solver", "not available",
                                                                         "does not have", "doesn't have", "missing"))
            return bool(sim or honest), ("ran " + str([t["tool"] for t in sim]) if sim else "") + (" + said what cannot be simulated" if honest else ""), []
        run(6, "Simulate the assembly", "Simulate the movement of the current assembly.", t6)

        def t7(r):
            h = calls(r, "make_hologram")
            res = (h[-1]["result"] if h else {}) or {}
            return bool(h and not res.get("error")), f"make_hologram ran: {json.dumps(res, default=str)[:200]}", []
        r7 = run(7, "Hologram of the current model", "Calculate a hologram of this 3D model.", t7)

        def t8(r):
            h = [t for t in r.get("trace") or [] if t["tool"] in ("make_hologram", "propagate", "focus_sweep", "eye_view", "set_eye")]
            return bool(h and not any((t.get("result") or {}).get("error") for t in h if isinstance(t.get("result"), dict))), \
                f"recalculated with {[(t['tool'], t.get('args')) for t in h]}", []
        run(8, "Change a holography parameter and recalculate", "Calculate it again with a larger viewing distance.", t8)

        def t9(r):
            a = calls(r, "analyze")
            res = (a[-1]["result"] if a else {}) or {}
            return bool(a and json.dumps(res).find("volume") >= 0), f"analyze: {json.dumps(res, default=str)[:200]}", []
        run(9, "Measure and analyse", "What is the volume, surface area and centre of mass of this model?", t9)

        def t10(r):
            ex = calls(r, "export_model")
            fmts = sorted({(t.get("args") or {}).get("format") for t in ex})
            fs = downloads(r)
            return len(fmts) >= 2 and len(fs) >= 2, f"export_model formats {fmts}, {len(fs)} files", fs
        run(10, "Export in different formats", "Export this model as STEP and as STL.", t10)

        def t11(r):
            ts = set(tools(r))
            need = {"modify", "export_model", "make_drawing"}
            return need <= ts, f"tools used {sorted(ts)}; needed {sorted(need)}", downloads(r)
        run(11, "Several operations in one request", "Paint it dark red, then export it as GLB and give me its blueprint.", t11)

        def t12(r):
            ex = calls(r, "export_model")
            tgt = [(t.get("args") or {}).get("target") for t in ex]
            return bool(ex and downloads(r)), f"'it' resolved to {tgt}", downloads(r)
        run(12, "Follow-up that refers to earlier results", "Now export it as 3MF too.", t12)

        before = E.http("/api/state")["state"]
        v0 = [(p.get("eng") or {}).get("version") for p in program_model(before)]

        def t13(r):
            after = E.http("/api/state")["state"]
            v1 = [(p.get("eng") or {}).get("version") for p in program_model(after)]
            n0, n1 = len(before["parts"]), len(after["parts"])
            return bool(v0) and v0 == v1 and n1 == n0, f"program versions {v0} -> {v1}, parts {n0} -> {n1} (last valid state kept)", []
        run(13, "An invalid operation does not corrupt the model", "Change the model so that its overall length is a negative number: -500 mm.", t13)

        def t14(r):
            b = calls(r, "build_cad")
            res = (b[-1]["result"] if b else {}) or {}
            return bool(b and res.get("built") and not (b[-1].get("args") or {}).get("file")), \
                f"build_cad from a description only: built={res.get('built')}, parts={len(res.get('parts') or [])}", []
        run(14, "An object category with no construction code", "Create a mechanical clamp with an adjustable screw and two "
            "gripping jaws.", t14)
    finally:
        E.stop_server(srv)
        json.dump(RESULTS, open(E.OUT / "results.json", "w", encoding="utf-8"), indent=1, default=str)
        write_md()


def write_md():
    L = ["# AETHER Lab: AI-orchestration acceptance tests", "",
         f"`python -m tests.acceptance_ai`, {time.strftime('%Y-%m-%d %H:%M')}: a test server with its own project, driven "
         "through the chat API (what the UI calls). Each check reads what executed (tool results, files, the scene).", "",
         f"**{sum(r['pass'] for r in RESULTS)} / {len(RESULTS)} pass.**", "",
         "| # | test | request | tools the AI called | check | result | s |", "|---|---|---|---|---|---|---|"]
    for r in RESULTS:
        L.append(f"| {r['n']} | {r['test']} | {r['request']} | {', '.join(r['tools']) or '-'} | {r['check'][:220].replace('|', '/')} | "
                 f"{'PASS' if r['pass'] else 'FAIL'} | {r.get('seconds', '')} |")
    L += ["", "Full calls, results and replies: `output/acceptance/results.json`."]
    (ROOT / "docs" / "ACCEPTANCE.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
