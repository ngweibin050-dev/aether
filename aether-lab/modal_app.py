"""Deploy the AETHER Lab physics engine to Modal:  modal deploy modal_app.py"""
import modal

image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy", "pillow")
         .add_local_python_source("engine"))
app = modal.App("aether-lab", image=image)


@app.function(cpu=8, memory=8192, timeout=300)
def run_tool(state, name, args):
    from engine import lab
    res = lab.run(state, name, args)
    return res, state
