"""AETHER CAD jobs on Modal CPU (modal_cad.py): one container per job, so jobs never queue behind each other, and a
job can be cancelled while it runs (Stop in the chat). The lab sends the drawing, the request and the current program;
it receives the job folder (program, plan, parameters, report, STEP, GLB, renders, the kept parts' B-rep files) and the
display meshes, unpacked into the same project folder the local worker would have used.

Used when the Modal app "aether-cad" is deployed (deploy it with: modal deploy modal_cad.py; it needs the Modal
secret "aether-meta" holding META_API). AETHER_CAD_REMOTE=0 forces the local CAD worker."""
from __future__ import annotations

import io
import json
import os
import time
import zipfile
from pathlib import Path

_fn = {}
_ok = None


def available():
    """True when the cloud CAD app is deployed and reachable (checked once per server run)."""
    global _ok
    if os.environ.get("AETHER_CAD_REMOTE", "1") == "0":
        return False
    if _ok is None:
        try:
            import modal
            f = modal.Function.from_name("aether-cad", "build")
            f.hydrate()
            _fn["build"] = f
            _fn["rerun"] = modal.Function.from_name("aether-cad", "rerun")
            _ok = True
        except Exception:
            _ok = False
    return _ok


class Stopped(RuntimeError):
    pass


def _run(name, job, stopped=None, on_wait=None, on_progress=None):
    """Spawn the job and wait for it; its progress lines come back live (a Modal queue); Stop cancels it at once."""
    import modal
    with modal.Queue.ephemeral() as q:
        job = {**job, "progress": q}
        call = _fn[name].spawn(job)
        t0 = time.time()

        def drain():
            try:
                for m in q.get_many(50, block=False) or []:
                    if on_progress:
                        on_progress(m)
            except Exception:
                pass
        while True:
            try:
                res = call.get(timeout=2)
                drain()
                return res
            except TimeoutError:
                drain()
                if stopped and stopped():
                    call.cancel()
                    raise Stopped("stopped by the user: the cloud CAD job was cancelled")
                if on_wait:
                    on_wait(time.time() - t0)


def _unpack(res, out_dir):
    """The job's zip into out_dir; every path the job wrote (its /tmp folder) remapped to out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if res.get("zip"):
        zipfile.ZipFile(io.BytesIO(res.pop("zip"))).extractall(out)
    root = res.pop("root", None)
    fix = lambda p: str(out / Path(p).relative_to(root)) if (root and isinstance(p, str) and p.startswith(root)) else p
    for m in (res.get("meshes") or {}).values():
        m["brep"] = fix(m.get("brep"))
    b = res.get("best") or {}
    for k in ("program", "plan"):
        if k in b:
            b[k] = fix(b[k])
    for p in b.get("parts") or []:
        p["brep"] = fix(p.get("brep"))
    rp = out / "report.json"
    if rp.exists() and root:                          # the saved report points at the local files too
        rep = json.loads(rp.read_text(encoding="utf-8"))
        s = json.dumps(rep).replace(root.replace("\\", "/"), str(out).replace("\\", "/"))
        rp.write_text(s, encoding="utf-8")
    return res


def build(out_dir, sheet=None, request="", rounds=3, base_program=None, base_length_mm=None, base_plan=None,
          stopped=None, on_wait=None, on_progress=None):
    """Same arguments and result as the local worker's program_build."""
    job = {"sheet_png": Path(sheet).read_bytes() if sheet else None, "request": request, "rounds": rounds,
           "base_program": base_program, "base_length_mm": base_length_mm,
           "base_plan": json.loads(Path(base_plan).read_text(encoding="utf-8")) if base_plan and Path(base_plan).exists() else None}
    return _unpack(_run("build", job, stopped, on_wait, on_progress), out_dir)


def rerun(program_dir, out_dir, overrides, sheet=None, length_mm=None, stopped=None, on_wait=None):
    """Same arguments and result as the local worker's program_rerun."""
    d = Path(program_dir)
    rd = lambda f: json.loads((d / f).read_text(encoding="utf-8")) if (d / f).exists() else None
    job = {"program": (d / "program.py").read_text(encoding="utf-8"), "params": rd("params.json"), "plan": rd("plan.json"),
           "overrides": overrides, "sheet_png": Path(sheet).read_bytes() if sheet else None, "length_mm": length_mm}
    return _unpack(_run("rerun", job, stopped, on_wait), out_dir)


def program_job(cmd, stopped=None, on_wait=None, on_progress=None, **args):
    """A CAD-program job wherever it can run best: Modal CPU when deployed (parallel, cancellable), else the local
    worker. Stop works in both: the cloud job is cancelled, or the local worker is ended (it restarts on the next call).
    cmd: "program_build" or "program_rerun"; args as for the local worker."""
    if available():
        if cmd == "program_build":
            return build(args["out_dir"], sheet=args.get("sheet"), request=args.get("request") or "",
                         rounds=args.get("rounds", 3), base_program=args.get("base_program"),
                         base_length_mm=args.get("base_length_mm"), base_plan=args.get("base_plan"),
                         stopped=stopped, on_wait=on_wait, on_progress=on_progress)
        return rerun(args["program_dir"], args["out_dir"], args.get("overrides") or {}, sheet=args.get("sheet"),
                     length_mm=args.get("length_mm"), stopped=stopped, on_wait=on_wait)
    import threading
    import cad_client
    box = {}

    def go():
        try:
            box["r"] = cad_client.call(cmd, **args)
        except Exception as e:                         # noqa: BLE001 - handed to the caller below
            box["e"] = e
    th = threading.Thread(target=go, daemon=True)
    th.start()
    t0 = time.time()
    while th.is_alive():
        th.join(1.0)
        if th.is_alive() and stopped and stopped():
            cad_client.kill()
            raise Stopped("stopped by the user: the CAD job was ended (the CAD worker restarts on the next request)")
        if on_wait:
            on_wait(time.time() - t0)
    if "e" in box:
        raise box["e"]
    return box["r"]
