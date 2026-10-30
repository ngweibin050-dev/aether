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


def scatter_add(a, idx, v):
    """a[idx] += v with repeated indices (np.add.at / cupyx.scatter_add)."""
    if GPU:
        import cupyx
        cupyx.scatter_add(a, idx, v)
    else:
        a += np.bincount(idx, weights=v, minlength=a.size)


def scatter_min(a, idx, v):
    if GPU:
        import cupyx
        cupyx.scatter_min(a, idx, v)
    else:
        np.minimum.at(a, idx, v)


def name():
    return "cupy-gpu" if GPU else "numpy-cpu"
