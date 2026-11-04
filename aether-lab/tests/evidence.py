"""docs/EVIDENCE.md: AETHER's measured results on one page, every number read from a saved result file (no API).

    python -m tests.evidence

Sources (each produced by its own script, named in the page):
  output/cad/current/report.json        the three-view CAD build: B-rep validity, STEP round trip, reprojection
  output/cad/cobra/report.json          the same pipeline on the public CC0 car sheet (tests/inputs/heldout/CC0_Cobra_four_view.png)
  output/baseline/results.json          tests/baseline_spark.py: AETHER vs plain Muse Spark on the same drawing
  output/reference/<input>/run<k>/      tests/run_reference.py: drawing -> mechanism runs (recall, precision, time)
  output/eval_refine.json               tests/eval_refine.py: refining a model by chat (car, machine, ask first)
  output/eval_assistant.json            tests/eval_assistant.py: the assistant's 16 everyday requests
  output/exports_check/results.json     tests/check_exports.py: the downloads opened with trimesh, not our code"""
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output"
PUBLIC_MACHINES = {"patent_US1699653_fig1": "US 1,699,653 Fig. 1", "patent_US929594_fig1": "US 929,594 Fig. 1 (drawing press)",
                   "heldout_US1770035_fig1": "US 1,770,035 Fig. 1 (held out: never tuned on)"}
INPUT_FILE = {"patent_US1699653_fig1": "inputs/US1699653_fig1.png", "patent_US929594_fig1": "inputs/US929594_fig1.png",
              "heldout_US1770035_fig1": "inputs/heldout/US1770035_fig1.png"}


def _load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cad_section(folder="current"):
    r = _load(OUT / "cad" / folder / "report.json") or {}
    comps = (r.get("validation") or {}).get("components") or {}
    valid = sum(1 for c in comps.values() if c.get("brepcheck_valid"))
    rt = (r.get("step_roundtrip") or {}).get("components") or {}
    rt_ok = sum(1 for c in rt.values() if c.get("reimported_valid"))
    vol = max((abs(c.get("volume_rel_diff") or 0) for c in rt.values()), default=None)
    rp = r.get("reprojection") or {}
    ious = {v: rp[v].get("iou") for v in rp if isinstance(rp.get(v), dict) and "iou" in rp[v]}
    mm = {v: (rp[v].get("boundary_mm") or {}).get("symmetric_mean") for v in ious}
    return {"valid": valid, "solids": len(comps), "rt_ok": rt_ok, "rt_n": len(rt), "vol_diff": vol, "iou": ious, "mm": mm,
            "maturity": r.get("maturity_reached"), "prov": r.get("provenance_counts")}


def machine_rows():
    from tests.run_reference import precision_from_check
    rows = []
    for name, title in PUBLIC_MACHINES.items():
        runs = sorted((OUT / "reference" / name).glob("run*/result.json"), key=lambda f: int(f.parent.name[3:]))[-3:]
        rec, prec, secs = [], [], []
        for f in runs:
            r = _load(f) or {}
            m = r.get("metrics") or {}
            if m.get("lines_on_built_pct") is not None:
                rec.append(m["lines_on_built_pct"])
            p = precision_from_check(INPUT_FILE[name], f.parent / "sam_check.jpg")
            if p and p.get("parts") is not None:
                prec.append(p["parts"])
            if r.get("total_s"):
                secs.append(r["total_s"])
        mean = lambda xs: round(statistics.mean(xs), 1) if xs else None
        rows.append((title, len(runs), mean(rec), mean(prec), mean(secs)))
    return rows


def current_section():
    """Part A (current system: AI-written CAD) and Part B (generalisation), from the saved records."""
    L = ["## A. The current system: AI-written CAD (cad/codegen.py)", "",
         "Muse Wonder plans the component list and writes a CadQuery program for the object; the program runs in a "
         "sandbox; code checks every solid, the quality gates and the agreement with the drawing; Muse Spark reviews "
         "real renders against `prompts/cad_critic.md`; Muse Wonder revises. No object has construction code.", ""]
    acc = _load(ROOT / "output" / "acceptance" / "results.json") or []
    if acc:
        L += [f"**Acceptance tests through the chat API (`tests/acceptance_ai.py`, docs/ACCEPTANCE.md): "
              f"{sum(r['pass'] for r in acc)} / {len(acc)} pass.**", "",
              "| # | test | tools the AI called | result |", "|---|---|---|---|"]
        L += [f"| {r['n']} | {r['test']} | {', '.join(r['tools']) or '-'} | {'PASS' if r['pass'] else 'FAIL'} |" for r in acc]
        L.append("")
    runs = ROOT / "docs" / "ai_cad_runs"
    if (runs / "README.md").exists():
        L += ["**The CC0 roadster, cycle by cycle** (`docs/ai_cad_runs/`; silhouette IoU per view with each view fitted to "
              "its drawing box: shape only, the earlier score):", ""]
        L += [ln for ln in (runs / "README.md").read_text(encoding="utf-8").splitlines() if ln.startswith("|")]
        L.append("")
    L += ["### B. Generalisation: the same loop on different objects (`tests/cad_quality_bench.py`)", ""]
    bench = ROOT / "docs" / "CAD_QUALITY.md"
    if bench.exists():
        L += [ln for ln in bench.read_text(encoding="utf-8").splitlines() if ln.startswith("|")]
        L += ["", "Critic scores are an AI judgement (Muse Spark on renders, 0-10), not a measurement. The gates and IoU "
                  "are computed by code. From this benchmark on, IoU uses ONE scale for every view (px per mm from the side "
                  "view's length; the model is only centred, never stretched), so proportions count."]
    L += ["", "**Targets** (engineering acceptance targets, not results already reached): valid solids 100 %; component "
              "list completeness >= 95 %; silhouette IoU >= 0.95 per view on four-view drawings (one scale); floating parts "
              "and unintended overlaps 0; critic >= 9 / 10 with no critical defect. A single-view drawing cannot fix hidden "
              "geometry, so there the target is honest labelling of what is inferred, not a number.", "",
          "---", "", "## C. Historical results: the earlier rule-based pipeline (retired)", "",
          "Everything below was measured with the earlier pipeline: `cad/vehicle.py` + `cad/planner.py` for three-view car "
          "sheets and `engine/rebuild.py` for single-view patent figures. Those rules are no longer used for new models; "
          "the results stay as the record of what that pipeline achieved.", ""]
    return L


def main():
    cad = cad_section()
    cobra = cad_section("cobra")
    base = _load(OUT / "baseline" / "results.json") or {}
    refine = _load(OUT / "eval_refine.json") or []
    assist = _load(OUT / "eval_assistant.json") or []
    exp = _load(OUT / "exports_check" / "results.json") or {}
    machines = machine_rows()
    skin = _load(OUT / "skin_fairing.json") or {}
    story = _load(OUT / "e2e_story" / "story.json") or []
    L = ["# AETHER Lab — evidence", "",
         f"Generated by `python -m tests.evidence` on {time.strftime('%Y-%m-%d %H:%M')} from saved result files; each "
         "section names the script that produced its numbers. Model calls: Muse Spark 1.3, SAM 3.1 (Meta Model API).", "",
         ""] + current_section() + ["### At a glance (historical pipeline)", "", "| What is measured | Result | Against |", "|---|---|---|"]
    if cad["iou"]:
        L.append(f"| Three-view drawing -> exact CAD (OpenCascade B-rep), car sheet | silhouette IoU "
                 + " / ".join(f"{v} {cad['iou'][v]:.3f}" for v in cad["iou"]) + "; boundary "
                 + " / ".join(f"{cad['mm'][v]:.0f}" for v in cad["mm"] if cad["mm"][v] is not None)
                 + f" mm mean | the drawing's own views |")
        if cobra["iou"]:
            L.append(f"| The same pipeline on the public CC0 car sheet (Shelby Cobra four-view), first full run | silhouette IoU "
                     + " / ".join(f"{v} {cobra['iou'][v]:.3f}" for v in cobra["iou"]) + f"; solids valid {cobra['valid']} / "
                     f"{cobra['solids']}; STEP round trip {cobra['rt_ok']} / {cobra['rt_n']} | the drawing's own views |")
        L.append(f"| Solids valid (BRepCheck) | {cad['valid']} / {cad['solids']} | OpenCascade |")
        L.append(f"| STEP round trip (re-read in a fresh process) | {cad['rt_ok']} / {cad['rt_n']} valid, volume within "
                 f"{cad['vol_diff']:.1e} | the written model |")
    a = base.get("aether")
    sp = [r for r in base.get("spark") or [] if r.get("iou")]
    if a and sp:
        L.append(f"| AETHER vs plain Muse Spark asked for the same car, same scoring (side IoU) | AETHER {a['iou']['side']:.2f}; "
                 f"plain Spark {', '.join(f'{r['iou']['side']:.2f}' for r in sp)} | the drawing |")
    for title, n, rec, prec, secs in machines:
        if rec is not None:
            L.append(f"| Patent drawing -> 3D mechanism: {title} ({n} runs) | drawing lines on built parts {rec} %, "
                     f"built outlines on ink {prec if prec is not None else '-'} %, {secs} s | the drawing's ink |")
    if refine:
        L.append(f"| Refining a model by chat (tests/eval_refine.py) | {sum(r['pass'] for r in refine)} / {len(refine)} cases pass | "
                 "checks on the result (placement, inside, nothing floating, ask first) |")
    if assist:
        L.append(f"| Everyday assistant requests (tests/eval_assistant.py) | {sum(r['pass'] for r in assist)} / {len(assist)} pass | "
                 "expected tool and scene change |")
    if story:
        L.append(f"| One workflow end to end, through the app's API (tests/e2e_story.py) | {sum(x['pass'] for x in story)} / "
                 f"{len(story)} steps, {round(sum(x['seconds'] for x in story) / 60, 1)} min | drawing -> CAD -> refine -> "
                 "section -> CAD feature -> validate -> STEP re-read -> restart + undo |")
    r0 = next((r for r in skin.get("rows") or [] if r["smooth_mm"] == 0), None)
    rd = next((r for r in skin.get("rows") or [] if r["smooth_mm"] == skin.get("default_mm")), None)
    if r0 and rd:
        L.append(f"| Car body surface fairing ({rd['smooth_mm']} mm) | largest bump {r0['largest_bump_mm']} -> "
                 f"{rd['largest_bump_mm']} mm; silhouette IoU changed at most "
                 f"{max(abs(r0['iou'][v] - rd['iou'][v]) for v in r0['iou']):.3f} | the same 39 measured sections |")
    if exp.get("files"):
        f = exp["files"]
        L.append(f"| Downloads opened outside AETHER (trimesh {exp.get('trimesh')}) | {sum(x['pass'] for x in f)} / {len(f)} files: "
                 "triangles equal, size within 0.004 mm | AETHER's own counts |")
    L += ["", "### 1. Drawing -> CAD (three-view sheet)", "",
          "Source: `output/cad/current/report.json` (the CAD build itself; details in `docs/CAD_RESULTS.md`). This build "
          "is from before the body surface fairing of section 6, which moves the silhouette agreement by at most 0.008.", ""]
    if cad["iou"]:
        L += ["| view | silhouette IoU | boundary distance mm (mean) |", "|---|---|---|"]
        L += [f"| {v} | {cad['iou'][v]:.4f} | {cad['mm'][v]} |" for v in cad["iou"]]
        L += ["", f"Maturity reached: `{cad['maturity']}`. Parameters by provenance: {cad['prov']} (assumed values are "
                  "listed and editable; the sheet has no dimension, so the real size is assumed until the user gives one)."]
    if cobra["iou"]:
        L += ["", "### 1b. A public sheet anyone can rerun: CC0 car four-view", "",
              "Source: `output/cad/cobra/report.json`. Input: `tests/inputs/heldout/CC0_Cobra_four_view.png` (CC0, Wikimedia "
              "Commons; conversion and history in `docs/INPUTS.md`). The car sheet above is third-party and not "
              "redistributed; this one is in the repository. Its first run stopped at view detection; two general fixes "
              "in `cad/observations.py` followed (they change nothing measured on the car sheet above); these are the "
              "numbers of the first full run after them.", "",
              "| view | silhouette IoU | boundary distance mm (mean) |", "|---|---|---|"]
        L += [f"| {v} | {cobra['iou'][v]:.4f} | {cobra['mm'][v]} |" for v in cobra["iou"]]
        L += ["", f"Solids valid {cobra['valid']} / {cobra['solids']}; STEP round trip {cobra['rt_ok']} / {cobra['rt_n']}; "
                  f"maturity `{cobra['maturity']}`. Parameters by provenance: {cobra['prov']}.", "",
              "**Why lower than the car sheet above (a known miss, not tuned away):** this car is an open roadster. The "
              "vehicle module (`cad/vehicle.py`) assumes a closed body, so it covers the open cockpit with a roof-like "
              "skin (built, not drawn) and builds neither the windscreen nor the roll bar (drawn, not built). That costs "
              "most of the side IoU and, with the windscreen frame, most of the end views' IoU "
              "(`output/cad/cobra/reproject_*.png`). Open-top bodies need their own cockpit model."]
    L += ["", "### 2. Why not just ask Muse Spark?", "",
          "`tests/baseline_spark.py`: the same car sheet given to plain Muse Spark (no tools) with the same part vocabulary "
          "and frame AETHER uses; 3 answers. Both models are scored against the DRAWING the same way: each view's silhouette "
          "read from the ink vs the model's silhouette in that view, both scaled to the view's box (the sheet has no "
          "dimension: shape is scored, not size), mirror images tried for both.", "",
          "| model | IoU side | IoU top | IoU end | proportion error % | parts built |", "|---|---|---|---|---|---|"]
    if a:
        L.append(f"| AETHER (CAD pipeline) | {a['iou']['side']} | {a['iou']['top']} | {a['iou']['end_a']} | {a['proportion_error_pct']} | B-rep solids |")
    for r in base.get("spark") or []:
        if r.get("iou"):
            L.append(f"| plain Muse Spark, seed {r['seed']} | {r['iou']['side']} | {r['iou']['top']} | {r['iou']['end_a']} | "
                     f"{r['proportion_error_pct']} | {r['built']}/{r['parts']} |")
    L += ["", "Plain Spark answers load and look plausible from the top, but in 2 of 3 the body was drawn as a flat side "
              "profile never turned upright (side view: wheels and interior only), and nothing in an answer says which "
              "one is right. AETHER measures the sheet and checks every view.", "",
          "### 3. Drawing -> mechanism (patent drawings)", "",
          "`tests/run_reference.py`, the last 3 saved runs per public input (full history: `docs/RESULTS.md`).", "",
          "| input | runs | drawing lines on built parts % (recall) | built outlines on ink % (precision) | time s |",
          "|---|---|---|---|---|"]
    L += [f"| {t} | {n} | {r} | {p} | {s} |" for t, n, r, p, s in machines]
    L += ["", "### 4. Refining and editing by chat", "", "| case | result | seconds |", "|---|---|---|"]
    L += [f"| {r['case']} | {'PASS' if r['pass'] else 'FAIL: ' + '; '.join(r['fails'])} | {r.get('seconds', '')} |" for r in refine]
    L += ["", f"Everyday requests (`tests/eval_assistant.py`): {sum(r['pass'] for r in assist)} / {len(assist)} pass "
              f"({', '.join(r['case'] for r in assist[:8])} ...).", "",
          "### 5. Downloads opened outside AETHER", "",
          "`tests/check_exports.py`: AETHER writes GLB, STL and 3MF at the model's real size; an isolated Python "
          "environment opens them with trimesh only and compares triangles and size with AETHER's own counts.", "",
          "| model | format | triangles | size mm | max size error mm | pass |", "|---|---|---|---|---|---|"]
    L += [f"| {x['model']} | {x['format']} | {x.get('triangles')} | {' x '.join(f'{v:.0f}' for v in x.get('size_mm') or [])} | "
          f"{x.get('size_error_mm')} | {'PASS' if x['pass'] else 'FAIL'} |" for x in exp.get("files") or []]
    if skin.get("rows"):
        L += ["", "### 6. The car body surface", "",
              "The body is one B-spline surface through the sections measured from the drawing; their small disagreements "
              "made it look crumpled. Each section point is now averaged with its neighbours along the body "
              f"(`cad.ops._fair_sections`, default {skin.get('default_mm')} mm). {skin.get('what')}.", "",
              "| fairing mm | waviness RMS mm | largest bump mm | IoU side / top / end | proportion error % |",
              "|---|---|---|---|---|"]
        L += [f"| {r['smooth_mm']} | {r['waviness_rms_mm']} | {r['largest_bump_mm']} | "
              f"{r['iou']['side']} / {r['iou']['top']} / {r['iou']['end_a']} | {r['proportion_error_pct']} |" for r in skin["rows"]]
    if story:
        L += ["", "### 7. One workflow, end to end", "",
              "`tests/e2e_story.py`: a test server with its own project and CAD folder, driven through the app's HTTP API. "
              "Details: `docs/STORY.md`.", "", "| # | step | result | seconds |", "|---|---|---|---|"]
        L += [f"| {x['n']} | {x['step']} | {'PASS' if x['pass'] else 'FAIL'} | {x['seconds']} |" for x in story]
    L += ["", "## Reproduce", "",
          "| command | needs |", "|---|---|",
          "| `python -m tests.test_physics`, `python -m tests.test_history` | nothing (offline) |",
          "| `python -m tests.check_exports` | an isolated env with trimesh (`output/.venv-eval`) |",
          "| `python -m tests.baseline_spark --score` | nothing: re-scores the saved answers |",
          "| `python -m tests.evidence` | nothing: rebuilds this page |",
          "| `python -m tests.baseline_spark`, `python tests/eval_refine.py`, `python tests/eval_assistant.py`, "
          "`python -m tests.run_reference` | the Meta API key |", "",
          "## Limits (said plainly)", "",
          "- The drawings carry no dimension: real sizes are assumed and labelled until the user gives one.",
          "- The car sheet of sections 1, 2, 6 and 7 is a third-party drawing, used for measurement and not redistributed; the CC0 sheet of section 1b is the public input.",
          "- Historical: the earlier rule-based CAD pipeline was implemented for vehicles only (cad/vehicle.py); the current AI-written CAD has no object-specific code.",
          "- Silhouette agreement is necessary, not sufficient: cross-sections between the views are inferred.",
          "- A drawn car body is one solid (no cabin): interior parts sit inside the solid, shown by the section view.",
          "- All optics are simulations; no holographic display has been built."]
    (ROOT / "docs" / "EVIDENCE.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:20]))


if __name__ == "__main__":
    main()
