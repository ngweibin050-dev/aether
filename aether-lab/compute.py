"""Where the physics runs: Modal (GPU/CPU in the cloud) when deployed, else this computer.

Set AETHER_COMPUTE=modal in .env after `modal deploy modal_app.py`.
Light tools always run locally; heavy ones go to Modal and fall back to local on any error.
"""
import os

from engine import lab

HEAVY = lab.HEAVY
_remote = None


def where():
    return "modal" if os.environ.get("AETHER_COMPUTE") == "modal" else "local"


def _modal_fn():
    global _remote
    if _remote is None:
        import modal
        _remote = modal.Function.from_name("aether-lab", "run_tool")
    return _remote


def run(state, name, args):
    if where() == "modal" and name in HEAVY:
        try:
            res, new_state = _modal_fn().remote(state, name, args)
            state.clear()
            state.update(new_state)
            res["_ran_on"] = "modal"
            return res
        except Exception as e:  # keep the demo alive
            print("Modal failed, running locally:", e)
    res = lab.run(state, name, args)
    res["_ran_on"] = "local"
    return res
