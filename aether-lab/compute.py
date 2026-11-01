"""Where the physics runs: Modal GPU in the cloud. AETHER_COMPUTE=local in .env is only for offline testing.
Light tools (scene edits) always run here; heavy ones (holograms, eye views, sweeps, desk scores) run on Modal only.

Version check: Modal runs a copy of the engine frozen at the last deploy. If this computer's engine is newer, the
old copy does not know new part types or arguments (KeyError: 'inflate', TypeError: gear() got an unexpected
keyword 'module'). The server compares engine fingerprints when it starts and before heavy tools; when they differ
it redeploys Modal itself (`modal deploy modal_app.py`, the account this computer is logged in to) and then runs the
tool on Modal. The fingerprint is the ONLY reason to redeploy: arguments are checked against the tool's signature
before the call (lab.check_args), so a bad argument from the model comes back as a clear error, and a remote error
only asks Modal for its fingerprint again (one ping) - it redeploys and retries once only if that differs.
Nothing heavy ever falls back to this computer's CPU.
"""
import os
import threading
import time

from engine import lab, version

HEAVY = lab.HEAVY
LOCAL_ENGINE = version.fingerprint()
_remote = {}
status = {"backend": None, "error": None, "stale": False, "deploying": False, "local_engine": LOCAL_ENGINE, "modal_engine": None, "checked": 0.0}
_lock = threading.Lock()


def where():
    return "local" if os.environ.get("AETHER_COMPUTE", "modal").lower() == "local" else "modal"


def _fn(name):
    if name not in _remote:
        import modal
        _remote[name] = modal.Function.from_name("aether-lab", name)
    return _remote[name]


def check():
    """Ping Modal (warms the GPU container) and compare engine fingerprints."""
    try:
        r = _fn("ping").remote()
        info = r if isinstance(r, dict) else {"backend": r, "engine": None}   # a deploy older than the check
        with _lock:
            status.update(backend=info.get("backend"), modal_engine=info.get("engine"), error=None,
                          stale=info.get("engine") != LOCAL_ENGINE, checked=time.time())
        print("Modal GPU ready:", status["backend"], "| engine", status["modal_engine"], "vs local", LOCAL_ENGINE,
              "-> OUT OF DATE (redeploying)" if status["stale"] else "-> same")
    except Exception as e:
        with _lock:
            status.update(error=f"{type(e).__name__}: {e}", checked=time.time())
        print("Modal not reachable:", status["error"])


def warm():
    """Spin up the GPU container in the background when the server starts (cold start ~20-60 s); if Modal runs an
    older engine, redeploy it now so the first heavy tool already runs on the current one."""
    if where() != "modal":
        return

    def go():
        check()
        if status["stale"]:
            print("Modal engine out of date: redeploying ...")
            err = deploy()
            print("Modal redeploy:", err or "done")
    threading.Thread(target=go, daemon=True).start()


def prewarm():
    """Start the run_tool GPU container now, in the background (a tiny desk_check), so the first heavy tool of an upload
    does not wait for a cold start: the upload spends its first ~30-60 s on Muse Spark anyway. `ping` warms only its
    own container. Errors are ignored here; the real call reports them."""
    if where() != "modal":
        return

    def go():
        try:
            run(lab.default_state(), "desk_check", {"heights_cm": [5]})
        except Exception:
            pass
    threading.Thread(target=go, daemon=True).start()


_deploy_lock = threading.Lock()


def deploy():
    """Redeploy the engine to Modal (same as deploy_modal.bat); returns None or the error text."""
    import subprocess
    import sys
    with _deploy_lock:
        if status["checked"] and not status["stale"]:
            return None                                   # another request already redeployed
        status["deploying"] = True
        try:
            env = dict(os.environ, PYTHONUTF8="1")
            # Modal prints box-drawing characters: read them as UTF-8 (Windows would default to cp1252 and crash)
            p = subprocess.run([sys.executable, "-m", "modal", "deploy", "modal_app.py"], cwd=os.path.dirname(os.path.abspath(__file__)),
                               env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
            print((p.stdout or "")[-2000:], (p.stderr or "")[-2000:])
            if p.returncode:
                return ((p.stderr or "") + (p.stdout or ""))[-400:]
            # a container of the previous deploy can still answer for a short while: ask again until the new one does
            for _ in range(12):
                _remote.clear()                          # look the functions up again: they changed
                check()
                if not status["stale"]:
                    return None
                time.sleep(10)
            return (f"deployed, but after 2 minutes Modal still reports engine {status['modal_engine']} "
                    f"(this computer: {LOCAL_ENGINE})")
        except Exception as e:
            return f"{type(e).__name__}: {e}"
        finally:
            status["deploying"] = False


def _local(state, name, args):
    res = lab.run(state, name, args)
    res["_ran_on"] = "local"
    return res


def _remote_run(state, name, args):
    """(result, new_state, failure text or None). A failure is a raised exception (network, GPU, Modal) or an error
    result the tool itself returned; either way it says nothing about the engine version on its own."""
    try:
        res, new_state = _fn("run_tool").remote(state, name, args)
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"
    return res, new_state, (str(res["error"]) if res.get("error") else None)


def run(state, name, args):
    if where() != "modal" or name not in HEAVY:
        return _local(state, name, args)
    bad = lab.check_args(name, args)                 # a bad argument is the caller's error, never a reason to redeploy
    if bad:
        return {"error": bad, "error_kind": "bad_args"}
    if not status["checked"]:
        check()
    if status["stale"] and (err := deploy()):
        return {"error": f"Modal runs an older AETHER engine (fingerprint {status['modal_engine']} vs this computer's "
                         f"{LOCAL_ENGINE}) and the automatic redeploy failed: {err} Run deploy_modal.bat and try again."}
    res, new_state, fail = _remote_run(state, name, args)
    if fail:
        status["error"] = fail
        check()                                      # did someone deploy another engine meanwhile? only the fingerprint says
        if status["stale"]:
            if err := deploy():
                return {"error": f"Modal runs an older AETHER engine ({fail[:160]}) and the automatic redeploy failed: {err}"}
            res, new_state, fail = _remote_run(state, name, args)
        if res is None:
            return {"error": f"Modal GPU failed ({fail[:300]}). Check the internet connection and `modal token`, "
                             "or run deploy_modal.bat."}
        if fail:                                     # the tool ran on the current engine and reported a real error
            status["error"] = None
            return {**res, "_ran_on": "modal"}
    state.clear()
    state.update(new_state)
    res["_ran_on"] = "modal"
    status["backend"], status["error"] = res.get("_backend"), None
    return res
