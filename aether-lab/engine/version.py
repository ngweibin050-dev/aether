"""Engine fingerprint: a short hash of every engine source file and data table.

The Modal GPU app runs a COPY of the engine, frozen when `modal deploy` ran. When this computer's engine changes
and Modal is not redeployed, the two disagree: a new part type ("outline") or a new argument ("module") is unknown
to the old copy and the tool fails with KeyError / TypeError. compute.py compares the two fingerprints and
redeploys Modal when they differ.
"""
import hashlib
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def fingerprint():
    h = hashlib.sha256()
    for name in sorted(os.listdir(_HERE)):
        if name.endswith(".py") or name.endswith(".json"):
            with open(os.path.join(_HERE, name), "rb") as f:
                data = f.read().replace(b"\r\n", b"\n")       # same hash on Windows and on Modal's Linux
            h.update(name.encode() + b"\0" + data + b"\0")
    return h.hexdigest()[:12]
