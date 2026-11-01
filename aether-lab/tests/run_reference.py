"""Reference runs with the real Meta key and Modal GPU, through the same function the UI's upload calls
(server.py /api/photo -> agent.photo_to_design, fresh scene, kind "auto" so the routing is tested too).

    python -m tests.run_reference                      # every input, 3 runs each
    python -m tests.run_reference car_three_view 1     # one input, one run
    python -m tests.run_reference --summary            # only rebuild docs/RESULTS.md from saved runs

Each run is saved to output/reference/<input>/run<k>/ (result.json + every image the UI would show), and
docs/RESULTS.md is rebuilt from ALL saved runs: per run and mean / spread per input. Costs Meta API calls."""
import base64
import json
import os
import statistics
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402,F401  (loads .env, same start-up as the real server)
import agent  # noqa: E402
import compute  # noqa: E402
import vision  # noqa: E402
from engine import lab  # noqa: E402

# name: (file under tests/, prompt hint, assumed size mm, public). Public inputs are copyright-free (docs/INPUTS.md) and
# go to docs/RESULTS.md; the others are third-party images kept for internal comparison only
# (output/reference/RESULTS_internal.md, never in the repo or the README).
INPUTS = {"patent_US1699653_fig1": ("inputs/US1699653_fig1.png", "", 240, True),
          "patent_US929594_fig1": ("inputs/US929594_fig1.png", "", 240, True),
          "nasa_x3_three_view": ("inputs/NASA_X-3_three_view.png", "aircraft", 180, True),
          # held out: never used while tuning; run only at the end of a step (python -m tests.run_reference heldout_...)
          "heldout_US1770035_fig1": ("inputs/heldout/US1770035_fig1.png", "", 240, True),
          "heldout_nasa_x36_three_view": ("inputs/heldout/NASA_X-36_three_view.png", "aircraft", 180, True),
          "machine_dense": ("machine_dense.jpg", "", 240, False), "blueprint_example2": ("blueprint_example2.jpg", "", 240, False),
          "car_three_view": ("car_three_view.gif", "car", 180, False)}
OUT = ROOT / "output" / "reference"
CALLS = []
# which reading code produced a run, so before / after numbers are never mixed in one mean
from engine import interpret as _interp  # noqa: E402
PIPELINE = ("Muse Wonder reads the drawing and completes the unseen views (Part A rebuild, section gear pairs, "
            "plausibility filter)" + (f"; reading effort {agent.READ_EFFORT}" if getattr(agent, "READ_EFFORT", None) else "")
            if getattr(agent, "READ_MODEL", agent.MODEL) != agent.MODEL else
            "step 3 closing: as step 3 final + gear / wheel count as one kind in the agreement"
            if hasattr(_interp, "SAME_THING") else
            "step 3 final: two readings + agreement, outlines fitted to the ink, edge-on round parts, measured gear "
            "module, reading deadline" if hasattr(_interp, "fit_box_to_ink")
            else "two readings per image, temperature 0, strict JSON, agreement (step 3)" if hasattr(agent, "_spark_json")
            else "one reading per image (before step 3)")


def _metered(fn, kind):
    """Wrap a Meta call: count it, time it, keep its token usage (never the key or the payload)."""
    def wrap(*a, **k):
        t = time.time()
        rec = {"api": kind, "path": a[0] if a and isinstance(a[0], str) else None, "ok": False}
        try:
            r = fn(*a, **k)
            rec["ok"] = True
            if isinstance(r, dict) and r.get("usage"):
                rec["usage"] = {x: r["usage"].get(x) for x in ("prompt_tokens", "completion_tokens", "total_tokens")}
            return r
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
            raise
        finally:
            rec["s"] = round(time.time() - t, 2)
            CALLS.append(rec)
    return wrap


agent._post = _metered(agent._post, "muse-spark")
vision.segment = _metered(vision.segment, "sam-3.1")


def _save_images(images, d):
    for k, v in images.items():
        for i, u in enumerate(v if isinstance(v, list) else [v]):
            if isinstance(u, str) and u.startswith("data:image/"):
                ext = u.split(";")[0].split("/")[1].replace("jpeg", "jpg")
                (d / f"{k}{f'_{i}' if isinstance(v, list) else ''}.{ext}").write_bytes(base64.b64decode(u.split(",", 1)[1]))


def run_once(name, k):
    fname, prompt, size, _ = INPUTS[name]
    url = "data:image/x;base64," + base64.b64encode((ROOT / "tests" / fname).read_bytes()).decode()
    d = OUT / name / f"run{k}"
    d.mkdir(parents=True, exist_ok=True)
    CALLS.clear()
    events = []
    st = lab.default_state()
    t0 = time.time()
    rec = {"input": fname, "run": k, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "kind_asked": "auto",
           "pipeline": PIPELINE}
    try:
        reply, trace, images, _ = agent.photo_to_design(st, [], url, prompt, size, str(d), lambda e: events.append({**e, "t": time.time() - t0}),
                                                        "interpret", "auto")
        _save_images(images, d)
        rec.update(reply=reply, ok=True)
    except Exception as e:
        trace, rec["ok"] = [], False
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()[-2000:]
    rec["total_s"] = round(time.time() - t0, 1)
    # time per stage, from the same step events the UI shows
    stages, open_ = [], {}
    for e in events:
        if e["stage"] == "tool":
            open_[e["tool"]] = e["t"]
        elif e["stage"] == "done" and e.get("tool") in open_:
            stages.append({"stage": e["tool"], "s": round(e["t"] - open_.pop(e["tool"]), 1), "error": bool(e.get("error"))})
    rec["stages"] = stages
    # the whole timeline, each segment named by the event that started it (Muse Spark "thinking" turns included)
    ev = sorted(events, key=lambda e: e["t"]) + [{"stage": "end", "t": rec["total_s"]}]
    seg = {}
    for a, b in zip(ev, ev[1:]):
        name_ = "spark_chat_turn" if a["stage"] == "thinking" else a.get("tool") if a["stage"] == "tool" else "between_steps"
        seg[name_] = round(seg.get(name_, 0) + b["t"] - a["t"], 1)
    rec["timeline_s"] = {"before_first_step": round(ev[0]["t"], 1), **seg}
    if agent.LAST_BUILD:
        (d / "replay.json").write_text(json.dumps(agent.LAST_BUILD, default=str), encoding="utf-8")
        agent.LAST_BUILD.clear()
    rec["meta_calls"] = list(CALLS)
    rec["trace"] = trace
    rec["metrics"] = metrics(trace, st)
    # what the UI downloads for this model (/api/meshes: every part's mesh and panel lines, JSON)
    rec["metrics"]["ui_payload_mb"] = round(len(json.dumps({"meshes": lab.meshes(st)}).encode()) / 1e6, 2)
    (d / "result.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    m = rec["metrics"]
    print(f"{name} run{k}: {'ok' if rec['ok'] else 'FAILED'} in {rec['total_s']} s; " + json.dumps({x: m.get(x) for x in
          ("route", "parts_built", "lines_on_built_pct", "view_iou_pct", "gear_pairs", "spark_calls", "spark_tokens", "errors")}), flush=True)
    return rec


def metrics(trace, st):
    by = {t["tool"]: t["result"] for t in trace}
    route = by.get("classify_upload", {})
    m = {"route": route.get("kind"), "errors": [f"{t['tool']}: {t['result']['error']}" for t in trace if isinstance(t.get("result"), dict) and t["result"].get("error")]}
    built = [p for p in st["parts"] if p["type"] != "group"]
    m["parts_built"] = len(built)
    if "sam_3_1" in by:                                   # machine drawing (interpret) path
        r = by["sam_3_1"]
        m["parts_read"] = len(r.get("parts") or [])
        m["reading"] = r.get("reading")
        m["lines_on_built_pct"] = (r.get("check") or {}).get("drawing_lines_on_built_parts_pct")
        m["outline_on_ink_pct"] = (r.get("check") or {}).get("outline_on_ink_pct")       # engine, vector (new runs)
        m["scale_source"] = r.get("scale_source")
        rb = (by.get("build_assembly") or {}).get("rebuild") or {}
        m["gear_pairs"] = len(rb.get("gear_pairs") or [])
        m["hidden_parts_added"] = len(rb.get("added_by_engineer") or [])
        m["engineer_completion"] = bool(rb.get("engineer_completion"))
        m["machine_depth_mm"] = rb.get("machine_depth_mm")
    if "read_views" in by:                                # three-view path
        r = by["read_views"]
        m["view_iou_pct"] = (r.get("check") or {}).get("view_match_iou_pct")             # official: delivered mesh
        m["view_iou_voxel_pct"] = (r.get("check") or {}).get("view_match_voxel_pct")     # reference: voxel field
        m["delivered_triangles"] = (r.get("check") or {}).get("delivered_triangles")
        m["parts_named"] = sum(1 for n in (r.get("part_names") or []) if not any(w in n for w in ("panel", "skin", "face")))
        m["size_mm"] = r.get("size_mm")
    ds = by.get("desk_score") or {}
    m["desk_pass"], m["desk_min_sharpness_pct"] = ds.get("pass"), ds.get("min_sharpness_pct")
    spark = [c for c in CALLS if c["api"] == "muse-spark"]
    m["spark_calls"] = len(spark)
    m["spark_failed_calls"] = sum(1 for c in spark if not c["ok"])
    m["spark_tokens"] = sum((c.get("usage") or {}).get("total_tokens") or 0 for c in spark)
    m["sam_calls"] = sum(1 for c in CALLS if c["api"] == "sam-3.1")
    return m


def precision_from_check(input_file, check_file):
    """Precision measured the same way for every run, old or new, from what each run saved: the check image's
    outline colours (built part = blue (0, 150, 230), frame = amber (235, 150, 30), drawn 3 px wide on the 1 mm
    silhouette grid) against the input drawing's ink (Otsu, at the same 1024 px size), within 2 px.
    Returns {"parts": %, "frames": %} or None. Coarser than the engine's own outline_on_ink_pct (vector outlines)."""
    import numpy as np
    from PIL import Image
    from engine import circles
    if not check_file.exists():
        return None
    chk = np.asarray(Image.open(check_file).convert("RGB"), float)
    im = vision.load_image("data:x;base64," + base64.b64encode((ROOT / "tests" / input_file).read_bytes()).decode(), 1024)
    if im.size != (chk.shape[1], chk.shape[0]):
        im = im.resize((chk.shape[1], chk.shape[0]))
    ink, _ = circles.ink_mask(im)
    near = ink.copy()
    for _ in range(2):
        n = near.copy()
        n[1:] |= near[:-1]; n[:-1] |= near[1:]; n[:, 1:] |= near[:, :-1]; n[:, :-1] |= near[:, 1:]
        n[1:, 1:] |= near[:-1, :-1]; n[:-1, :-1] |= near[1:, 1:]; n[1:, :-1] |= near[:-1, 1:]; n[:-1, 1:] |= near[1:, :-1]
        near = n
    out = {}
    for k, col in (("parts", (0, 150, 230)), ("frames", (235, 150, 30))):
        e = np.linalg.norm(chk - np.array(col), axis=2) < 60
        out[k] = round(100 * float((e & near).sum()) / e.sum(), 1) if e.sum() > 50 else None
    return out


def _stat(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    if not xs:
        return "—"
    if len(xs) == 1:
        return f"{xs[0]:g}"
    mu = statistics.mean(xs)
    return f"{mu:.1f} (min {min(xs):g}, max {max(xs):g}, spread {100 * (max(xs) - min(xs)) / mu:.0f} %)" if mu else f"{mu:g}"


NOTES_MARK = "<!-- Hand-written notes below; tests/run_reference.py keeps them when it rewrites the tables above. -->"


def summary():
    """docs/RESULTS.md from the saved runs of the public inputs, output/reference/RESULTS_internal.md from the
    third-party ones (numbers only from result.json files)."""
    for public, path in ((True, ROOT / "docs" / "RESULTS.md"), (False, OUT / "RESULTS_internal.md")):
        _summary([n for n, v in INPUTS.items() if v[3] == public], path, public)


def _summary(names, p, public):
    per = {}
    for name in names:
        for f in sorted((OUT / name).glob("run*/result.json"), key=lambda f: int(f.parent.name[3:])):
            r = json.loads(f.read_text(encoding="utf-8"))
            if r["metrics"].get("route") == "machine":
                r["metrics"]["precision_check_img"] = precision_from_check(r["input"], f.parent / "sam_check.jpg")
            per.setdefault(name, []).append(r)
    out = ["# AETHER Lab — measured results" + ("" if public else " (INTERNAL: third-party inputs, not for the repo)"), "",
           "Inputs and their sources: `docs/INPUTS.md`." if public else "", "",
           "Every number below comes from a saved run (`output/reference/<input>/run<k>/result.json`), produced by "
           "`python -m tests.run_reference` with the real Meta key (Muse Spark 1.3, SAM 3.1) and the Modal GPU, through "
           "the same function the UI's upload calls (`agent.photo_to_design`, route chosen automatically). "
           "All optics are simulations; no holographic display has been built.", ""]
    groups = {}
    for name, runs in per.items():
        for r in runs:
            groups.setdefault((name, r.get("pipeline") or "one reading per image (before step 3)"), []).append(r)
    for (name, pipe), runs in groups.items():
        pp = lambda d, k: (d or {}).get(k, "—") if d else "—"
        out += [f"## {name} ({runs[0]['input']}) — {pipe}", "",
                "| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | "
                "view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | "
                "Spark calls (failed) | Spark tokens | total s (target 90) | errors |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in runs:
            m = r["metrics"]
            iou = m.get("view_iou_pct")
            pc, pe = m.get("precision_check_img"), m.get("outline_on_ink_pct")
            over = r["total_s"] - 90
            out.append(f"| {r['run']} | {r['started']} | {'yes' if r['ok'] else 'NO'} | {m.get('route')} | {m.get('parts_read', '—')} | {m.get('parts_built')} | "
                       f"{m.get('lines_on_built_pct', '—')} | {pp(pc, 'parts')} / {pp(pc, 'frames')} | "
                       f"{'/'.join(str(iou.get(k)) for k in ('side', 'top', 'front')) if iou else '—'} | "
                       f"{m.get('gear_pairs', '—')} | {m.get('hidden_parts_added', '—')} | {m.get('desk_pass')} ({m.get('desk_min_sharpness_pct')}) | "
                       f"{m.get('spark_calls')} ({m.get('spark_failed_calls')}) | {m.get('spark_tokens') or '—'} | "
                       f"{r['total_s']} ({'+' if over > 0 else ''}{over:.0f}) | {'; '.join(m.get('errors') or []) or r.get('error') or '—'} |")
        ms = [r["metrics"] for r in runs]
        out += ["", f"Mean and spread over {len(runs)} runs (spread = (max − min) / mean):", "",
                f"- parts read (after agreement, merge and the circle check): {_stat([m.get('parts_read') for m in ms])}" if any(m.get('parts_read') is not None for m in ms) else "",
                f"- parts built: {_stat([m.get('parts_built') for m in ms])}",
                f"- recall, drawing lines on built parts %: {_stat([m.get('lines_on_built_pct') for m in ms])}" if any(m.get('lines_on_built_pct') is not None for m in ms) else "",
                f"- precision, parts %: {_stat([(m.get('precision_check_img') or {}).get('parts') for m in ms])}; "
                f"frames %: {_stat([(m.get('precision_check_img') or {}).get('frames') for m in ms])}" if any(m.get('precision_check_img') for m in ms) else "",
                f"- gear pairs: {_stat([m.get('gear_pairs') for m in ms])}" if any(m.get('gear_pairs') is not None for m in ms) else "",
                f"- view IoU % (min of the three views): {_stat([min(m['view_iou_pct'].values()) for m in ms if m.get('view_iou_pct')])}" if any(m.get('view_iou_pct') for m in ms) else "",
                f"- total time s: {_stat([r['total_s'] for r in runs])} (target 90 s: "
                f"{sum(r['total_s'] <= 90 for r in runs)}/{len(runs)} runs within it)",
                f"- Spark calls: {_stat([m.get('spark_calls') for m in ms])}; tokens: {_stat([m.get('spark_tokens') for m in ms])}", ""]
        st = {}
        for r in runs:
            for s in r["stages"]:
                st.setdefault(s["stage"], []).append(s["s"])
        out += ["Time per stage (s, mean over runs): " + ", ".join(f"{k} {statistics.mean(v):.1f}" for k, v in st.items()), ""]
    if public:                                   # the hand-written notes below the marker are kept as they are
        old = p.read_text(encoding="utf-8") if p.exists() else ""
        notes = old.split(NOTES_MARK, 1)[1].split("## How to read these numbers", 1)[0].strip("\n") if NOTES_MARK in old else ""
        out += [NOTES_MARK, "", notes, ""]
        out += ["## How to read these numbers", "",
                "- **Recall** (`drawing_lines_on_built_parts_pct`): share of the drawing's lines (inside the machine's area) "
                "that lie on a built part or frame, front view. A big housing can inflate it, so it is always shown with precision.",
                "- **Precision** (official method): share of the OUTER edge of the built silhouette (front view; all parts "
                "merged, frames separately) that lies within 2 px of the drawing's ink; an outline where the drawing has no "
                "line was invented. Measured for every run, old or new, on the run's saved check image (its outlines are "
                "the silhouette's edge, 3 px wide, on the 1 mm silhouette grid), so before / after compare the same thing. "
                "Why this one: each part's own outline (the engine's earlier number) also counts edges lying inside other "
                "parts; on B run 7 those were 61 % of the outline pixels and 74 % of them sit on some line of a dense section, "
                "so it read 68.9 % where the outer edge reads 56.4 %. Line width (1 px 56.4 %, 3 px 56.8 %) and JPEG (57.1 %) "
                "do not explain the gap. Hatching and text count as ink, so precision is an upper bound on dense sheets. "
                "Frame outlines are traced on the 1 mm grid, so frame precision is a lower bound, and the 3 mm running "
                "clearance cut around every part counts as invented on purpose.",
                "- **Parts read**: parts kept after the reading(s), duplicate merge and the circle check (before hubs and frame "
                "plates are added). Its spread across runs is the stability target (≤ 15 %).",
                "- **Total s**: wall time of the whole upload (routing, reading, completion, rebuild, desk score, focus sweep) "
                "on Modal T4; the target is 90 s; the number in brackets is how far over or under it is.",
                "- **Ground-line rule** (three-view sheets): the line an object is drawn standing on is not part of the object. "
                "A straight horizontal line in the lowest 15 % of a view's ink, at least 40 % of the view's width and at most "
                "5 px thick, is erased before the view is filled, but ONLY if it runs past the object's own outline (measured "
                "in the band just above it) on at least one side; a part's own flat bottom edge stays. Where a wheel stands on "
                "it, the line's pixels stay. Both cases are test 25. Separate outlines (a nose wheel drawn apart from the "
                "fuselage) are kept if they lie inside the main outline's box (+15 %) and do not touch the view's crop edge "
                "(a neighbouring view reaching into the crop does).",
                "- **NASA X-3 view match** (86–93 % vs ≥ 95 % on the car sheet): the red areas in its check image are the tips of "
                "the horizontal tail and the wings, and the nose wheel. These are surfaces only a few pixels thick in one view: "
                "filling each view's outline closes 2 px gaps and erodes back, which removes a thin surface from that view, "
                "and a visual hull keeps only what every view shows, so it disappears from the solid. The nose wheel is not "
                "connected to the body in the side view, and only the largest connected outline per view is kept. (Before "
                "Nov 1; fixed since by the 1-px build without blur and the detached-parts rule: 100 / 99.5 / 98.9 %.)",
                ""]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(x for x in out if x is not None) + "\n", encoding="utf-8")
    print("wrote", p)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] != ["--summary"]:
        # default: the public inputs that are not held out
        names = [args[0]] if args else [n for n, v in INPUTS.items() if v[3] and not n.startswith("heldout_")]
        n = int(args[1]) if len(args) > 1 else 3
        for name in names:
            have = len(list((OUT / name).glob("run*"))) if (OUT / name).exists() else 0
            for k in range(have + 1, have + n + 1):
                run_once(name, k)
    summary()
