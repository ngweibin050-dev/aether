"""Array backend: CuPy on a CUDA GPU (Modal), NumPy everywhere else.

Set AETHER_GPU=0 to force NumPy. Physics code uses `xp` and calls `to_numpy` at its edges.
"""
import os

import numpy as np

xp = np
GPU = False
if os.environ.get("AETHER_GPU", "1") != "0":
    try:
        import cupy as _cp
        if _cp.cuda.runtime.getDeviceCount() > 0:
            xp, GPU = _cp, True
    except Exception:
        pass


def to_numpy(a):
    return a.get() if GPU and hasattr(a, "get") else np.asarray(a)


def name():
    return "cupy-gpu" if GPU else "numpy-cpu"
