"""AETHER CAD on Modal CPU: the whole AI-written CAD loop (cad/codegen.py) in a cloud container, one container per job.

    modal deploy modal_cad.py          (server.py / cad_remote.py call it; deploy_modal_cad.bat does this)

Every build or parameter re-run is its own container with 8 CPU cores, so jobs never queue behind each other and a
running job can be cancelled (FunctionCall.cancel). Inside a job the review renders run in parallel (Chromium in the
image). The laptop only sends the job (the drawing, the request, the current program) and receives the results: the
program, plan, parameters, report, STEP, GLB, the kept parts' B-rep files and their display meshes, as one zip.

The Meta key comes from the Modal secret "aether-meta" (META_API), never from the arguments."""
import io
import json
import os
import zipfile

import modal

LAB = os.path.dirname(os.path.abspath(__file__))
NO_SECRET = os.environ.get("AETHER_CAD_NO_SECRET") == "1"
image = (modal.Image.debian_slim(python_version="3.12")
         .apt_install("chromium", "fonts-dejavu-core", "libgl1", "libglib2.0-0")
         .pip_install_from_requirements(os.path.join(LAB, "cad-worker", "requirements.txt")))   # the same pins as local
if NO_SECRET:                                   # baked into the image, so the container decides the same way
    image = image.env({"AETHER_CAD_NO_SECRET": "1"})
image = (image.add_local_python_source("cad")
         .add_local_dir(os.path.join(LAB, "prompts"), "/root/prompts")
         .add_local_dir(os.path.join(LAB, "cad", "render"), "/root/cad/render")
         .add_local_dir(os.path.join(LAB, "ui", "node_modules", "three", "build"), "/root/ui/node_modules/three/build")
         .add_local_dir(os.path.join(LAB, "ui", "node_modules", "three", "examples", "jsm"),
                        "/root/ui/node_modules/three/examples/jsm"))
app = modal.App("aether-cad", image=image)
# the Meta key for Muse calls: the Modal secret "aether-meta" (create it once: modal secret create aether-meta META_API=...).
# AETHER_CAD_NO_SECRET=1 deploys without it (parameter re-runs work; builds then fail at the first Muse call).
OPTS = dict(cpu=8.0, memory=16384, timeout=3600,
            secrets=[] if NO_SECRET else [modal.Secret.from_name("aether-meta")])


def _clean_key():
    """The secret's value as the lab reads .env: without surrounding quotes or spaces (a copied line keeps them)."""
    k = os.environ.get("META_API")
    if k:
        os.environ["META_API"] = k.strip().strip('"').strip("'").strip().lstrip('<').rstrip('>').strip()   # a typed <placeholder> too


def _pack(out_dir):
    """The job folder as zip bytes (renders, checks, program, plan, params, report, STEP, GLB, the kept parts' B-rep)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(out_dir):
            for f in files:
                if f.startswith("_") and f != "_result.json":      # the sandbox's own job files
                    continue
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, out_dir))
    return buf.getvalue()


def _meshes(report_path):
    import sys
    sys.path.insert(0, "/root")
    from cad import worker as W
    return W.cmd_program_meshes({"report": report_path})["meshes"]


def _summary(rep):
    out = {k: rep.get(k) for k in ("seconds", "best", "edit", "error")}
    out["plan_components"] = len((rep.get("plan") or {}).get("components") or [])
    out["unknowns"] = (rep.get("plan") or {}).get("unknowns") or []
    out["rounds"] = [{k: r.get(k) for k in ("round", "error", "iou", "mean_iou", "invalid", "object", "model_s", "run_s")}
                     | {"parts": len(r.get("parts") or []), "gates": (r.get("gates") or {}).get("summary"),
                        "critic": (r.get("critic") or {}).get("overall"),
                        "critic_defects": [d["part"] + ": " + d["problem"] for d in (r.get("critic") or {}).get("defects") or []][:6]}
                     for r in rep.get("rounds") or []]
    return out


@app.function(**OPTS)
def key_check():
    """Which shape the Meta key has in the container (never the key itself): length, and whether quotes were stored."""
    k = os.environ.get("META_API") or ""
    return {"present": bool(k), "length": len(k), "quoted": k[:1] in "\"'" if k else False, "spaces": k != k.strip()}


@app.function(**OPTS)
def build(job):
    """job: {sheet_png: bytes | None, request, rounds, base_program, base_length_mm, base_plan}"""
    _clean_key()
    import sys
    sys.path.insert(0, "/root")
    from cad import codegen as G
    out = "/tmp/job"
    os.makedirs(out, exist_ok=True)
    sheet = None
    if job.get("sheet_png"):
        sheet = os.path.join(out, "sheet.png")
        open(sheet, "wb").write(job["sheet_png"])
    rep = G.build(sheet, out, request=job.get("request") or "", rounds=int(job.get("rounds", 3)),
                  base_program=job.get("base_program"), base_length_mm=job.get("base_length_mm"),
                  base_plan=job.get("base_plan"), log=print)
    res = _summary(rep)
    res["root"] = out
    if rep.get("best"):
        res["meshes"] = _meshes(os.path.join(out, "report.json"))
    res["zip"] = _pack(out)
    return res


@app.function(**OPTS)
def rerun(job):
    """job: {program, params, plan, overrides, sheet_png, length_mm}: a parameter correction, no model call."""
    _clean_key()
    import sys
    sys.path.insert(0, "/root")
    from cad import codegen as G
    src, out = "/tmp/src", "/tmp/job"
    os.makedirs(src, exist_ok=True)
    open(os.path.join(src, "program.py"), "w", encoding="utf-8").write(job["program"])
    json.dump(job.get("params") or {}, open(os.path.join(src, "params.json"), "w", encoding="utf-8"))
    if job.get("plan"):
        json.dump(job["plan"], open(os.path.join(src, "plan.json"), "w", encoding="utf-8"))
    sheet = None
    if job.get("sheet_png"):
        sheet = os.path.join(src, "sheet.png")
        open(sheet, "wb").write(job["sheet_png"])
    rep = G.rerun(src, out, job.get("overrides") or {}, sheet=sheet, length_mm=job.get("length_mm"), log=print)
    res = {k: rep.get(k) for k in ("error", "overrides")}
    res["best"] = {k: v for k, v in (rep.get("best") or {}).items() if k != "parts"} if rep.get("best") else None
    res["root"] = out
    if rep.get("best"):
        res["meshes"] = _meshes(os.path.join(out, "report.json"))
        res["zip"] = _pack(out)
    return res
