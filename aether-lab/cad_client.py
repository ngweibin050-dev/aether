"""AETHER Lab server side of the CAD worker (runs in the lab's own Python; never imports OpenCascade).

The CAD kernel lives in an isolated, pinned Python 3.12 environment (aether-lab/cad-worker/.venv: CadQuery 2.8 / OCP).
This module starts `python -m cad.worker` in that environment once and talks to it with one JSON line per request
(see cad/worker.py). The worker keeps the open document and its B-rep cache, so parameter edits recompute only the
features that depend on them.

Environment variable AETHER_CAD_PYTHON overrides the interpreter path.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_proc = None
_lock = threading.Lock()
_n = 0


def python_path():
    env = os.environ.get("AETHER_CAD_PYTHON")
    if env:
        return env
    venv = ROOT / "cad-worker" / ".venv"
    for p in (venv / "bin" / "python", venv / "Scripts" / "python.exe"):
        if p.exists():
            return str(p)
    raise RuntimeError("CAD worker environment not found: create it with cad-worker/setup (Python 3.12 + CadQuery), "
                       "or set AETHER_CAD_PYTHON")


def _start():
    global _proc
    if _proc is not None and _proc.poll() is None:
        return _proc
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUNBUFFERED="1", PYTHONUTF8="1")
    log = open(ROOT / "output" / "cad_worker.log", "a", encoding="utf-8") if (ROOT / "output").exists() else subprocess.DEVNULL
    _proc = subprocess.Popen([python_path(), "-m", "cad.worker"], cwd=str(ROOT), env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=log, text=True, encoding="utf-8", bufsize=1)
    return _proc


def call(cmd, timeout=None, **args):
    """One request to the worker. Raises RuntimeError with the worker's error text."""
    global _n
    with _lock:
        p = _start()
        _n += 1
        p.stdin.write(json.dumps({"id": _n, "cmd": cmd, "args": args}) + "\n")
        p.stdin.flush()
        while True:
            line = p.stdout.readline()
            if not line:
                raise RuntimeError("the CAD worker stopped (see output/cad_worker.log)")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue                         # not a protocol line
            if isinstance(msg, dict) and msg.get("id") == _n:
                break
    if not msg.get("ok"):
        raise RuntimeError(msg.get("error") or "CAD worker error")
    return msg["result"]


LAST_CHECK = {}


def available():
    """True only when the CAD worker actually answers: the interpreter exists AND it imports OpenCascade / CadQuery
    (a ping). A path that merely exists is not enough (a wrong AETHER_CAD_PYTHON used to report True)."""
    try:
        exe = python_path()
    except RuntimeError as e:
        LAST_CHECK.clear()
        LAST_CHECK.update(ok=False, why=str(e))
        return False
    if not Path(exe).exists():
        LAST_CHECK.clear()
        LAST_CHECK.update(ok=False, why=f"CAD interpreter {exe} does not exist")
        return False
    if LAST_CHECK.get("ok") and _proc is not None and _proc.poll() is None:
        return True
    try:
        info = call("ping")
    except Exception as e:                      # interpreter does not start, or has no OCP / CadQuery
        stop_quietly()
        LAST_CHECK.clear()
        LAST_CHECK.update(ok=False, why=f"CAD worker did not answer: {type(e).__name__}: {str(e)[:200]}")
        return False
    LAST_CHECK.clear()
    LAST_CHECK.update(ok=True, **info)
    return True


def stop_quietly():
    global _proc
    try:
        if _proc is not None and _proc.poll() is None:
            _proc.kill()
    except Exception:
        pass
    _proc = None


def stop():
    global _proc
    if _proc is not None and _proc.poll() is None:
        _proc.stdin.close()
        _proc.wait(timeout=10)
    _proc = None
