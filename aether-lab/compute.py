"""Where the physics runs. Default: Modal GPU in the cloud (deploy once with `modal deploy modal_app.py`).

AETHER_COMPUTE=local in .env runs everything on this computer instead.
Light tools (scene edits) always run locally; heavy ones (holograms, eye views, sweeps) go to Modal.
If Modal fails, the tool returns an error saying why; it does not fall back to the CPU unless
AETHER_FALLBACK=local is set.
"""
import os
import threading

from engine import lab

HEAVY = lab.HEAVY
_remote = {}
status = {"backend": None, "error": None}


def where():
    return "local" if os.environ.get("AETHER_COMPUTE", "modal").lower() == "local" else "modal"


def _fn(name):
    if name not in _remote:
        import modal
        _remote[name] = modal.Function.from_name("aether-lab", name)
    return _remote[name]


def warm():
    """Spin up the GPU container in the background when the server starts (cold start ~20-60 s)."""
    if where() != "modal":
        return

    def go():
        try:
            status["backend"] = _fn("ping").remote()
            status["error"] = None
            print("Modal GPU ready:", status["backend"])
        except Exception as e:
            status["error"] = f"{type(e).__name__}: {e}"
            print("Modal not reachable:", status["error"])
    threading.Thread(target=go, daemon=True).start()


def run(state, name, args):
    if where() == "modal" and name in HEAVY:
        try:
            res, new_state = _fn("run_tool").remote(state, name, args)
            state.clear()
            state.update(new_state)
            res["_ran_on"] = "modal"
            status["backend"], status["error"] = res.get("_backend"), None
            return res
        except Exception as e:
            status["error"] = f"{type(e).__name__}: {e}"
            if os.environ.get("AETHER_FALLBACK") != "local":
                return {"error": f"Modal GPU failed ({status['error'][:300]}). Run `modal deploy modal_app.py`, "
                                 "or set AETHER_COMPUTE=local in .env to use this computer."}
            print("Modal failed, running locally:", e)
    res = lab.run(state, name, args)
    res["_ran_on"] = "local"
    return res
