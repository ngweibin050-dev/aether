"""Deploy the AETHER physics engine to Modal (GPU):  modal deploy modal_app.py"""
import modal

image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy", "pillow", "cupy-cuda12x")
         .add_local_python_source("engine"))
app = modal.App("aether-lab", image=image)


@app.function(gpu="T4", timeout=300)
def run_tool(state, name, args):
    from engine import backend, lab
    res = lab.run(state, name, args)
    res["_backend"] = backend.name()
    return res, state
