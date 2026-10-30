"""Deploy the AETHER physics engine to Modal (GPU):  modal deploy modal_app.py

Every heavy tool (eye focus sweep, eye view, lab hologram, desk checks) runs here on an NVIDIA T4.
The engine uses CuPy on the GPU (engine/backend.py); the same code runs on NumPy anywhere else.
One warm container keeps the rendered view in memory, so a focus sweep right after an eye view
does not render the design again.
"""
import inspect

import modal

image = (modal.Image.from_registry("nvidia/cuda:12.4.1-runtime-ubuntu22.04", add_python="3.12")
         .pip_install("numpy", "pillow", "cupy-cuda12x[ctk]")   # [ctk]: CUDA headers, so CuPy can compile its kernels
         .env({"CUPY_CACHE_DIR": "/cache/cupy"})
         .add_local_python_source("engine")
         # precomputed eye-model table (non-.py files are not copied by add_local_python_source)
         .add_local_file("engine/sharpness_table.json", "/root/engine/sharpness_table.json"))
app = modal.App("aether-lab", image=image)
# CuPy compiles its GPU kernels on first use (~10 s); keep the compiled kernels across containers
cache = modal.Volume.from_name("aether-cupy-cache", create_if_missing=True)

# keep one container warm for 10 minutes after the last call (parameter names changed across Modal versions)
_opts = {"gpu": "T4", "timeout": 600, "volumes": {"/cache": cache}}
_sig = inspect.signature(app.function).parameters
for new, old, value in (("scaledown_window", "container_idle_timeout", 600), ("max_containers", "concurrency_limit", 1)):
    if new in _sig:
        _opts[new] = value
    elif old in _sig:
        _opts[old] = value


@app.function(**_opts)
def run_tool(state, name, args):
    from engine import backend, lab
    try:
        res = lab.run(state, name, args)
        if "error" in res and backend.GPU and "cupy" in res["error"].lower():
            raise RuntimeError(res["error"])
        res["_backend"] = backend.name()
    except Exception as e:                       # a GPU-only failure: rerun the same tool on the container's CPU
        import numpy as np
        backend.xp, backend.GPU = np, False
        res = lab.run(state, name, args)
        res["_backend"] = f"numpy-cpu (GPU error: {type(e).__name__}: {str(e)[:120]})"
    _save_kernels()
    return res, state


_saved = {"n": -1}


def _save_kernels():
    """Commit newly compiled CuPy kernels to the volume (only when the cache grew)."""
    import os
    n = sum(len(f) for _, _, f in os.walk("/cache/cupy")) if os.path.isdir("/cache/cupy") else 0
    if n != _saved["n"]:
        try:
            cache.commit()
            _saved["n"] = n
        except Exception as e:
            print("cache commit failed:", e)


@app.function(**_opts)
def ping():
    """Start (warm up) the GPU container; returns the backend in use."""
    from engine import backend, retina
    if backend.GPU:                              # compile the main kernels now, not on the user's first click
        import numpy as np
        retina.psf(0.6, 0.6, 0.6, 3e-4, 96, xp=backend.xp, col_blur=1e-4)
        backend.xp.fft.irfft2(backend.xp.fft.rfft2(backend.xp.ones((64, 64))))
        backend.scatter_add(backend.xp.zeros(8), backend.xp.arange(4), backend.xp.ones(4))
        backend.scatter_min(backend.xp.zeros(8, dtype=backend.xp.float32), backend.xp.arange(4), backend.xp.ones(4, dtype=backend.xp.float32))
        _save_kernels()
    return backend.name()
