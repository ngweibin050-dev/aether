"""Live smoke test of the three Meta models with the key in .env (costs a few API calls).
Run from the aether-lab folder: python -m tests.smoke_meta"""
import base64
import json
import struct
import time
from pathlib import Path

import server  # noqa: F401  (loads .env)
import agent
import vision
from engine import lab

ROOT = Path(__file__).resolve().parent

# 1. SAM 3.1 on the sample photo
url = "data:image/jpeg;base64," + base64.b64encode((ROOT / "gear_photo.jpg").read_bytes()).decode()
t = time.time()
info, images, _ = vision.photo_part(url, "gear", 70)
print(f"SAM 3.1 ({time.time() - t:.1f} s):", json.dumps(info))

# 2. Muse Voice Transcribe: 1 s of silence must be accepted (empty text is fine)
pcm = b"\x00\x00" * 16000
wav = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16) \
    + b"data" + struct.pack("<I", len(pcm)) + pcm
t = time.time()
print(f"Voice ({time.time() - t:.1f} s): {agent.transcribe(wav)!r}")

# 3. Muse Spark closed loop on a design that is too tall for the desk
st = lab.default_state()
lab.build_assembly(st, "Tall motor", [
    {"name": "Housing", "type": "tube", "params": {"outer": 40, "inner": 36, "height": 90}},
    {"name": "Shaft", "type": "cylinder", "params": {"radius": 4, "height": 150}}], position=[0, 0, 110])
t = time.time()
r = agent.optimize(st, 80, 3)
r.pop("_images", None)
print(f"Design loop ({time.time() - t:.1f} s):", json.dumps({k: r[k] for k in ("pass", "before", "after", "rounds")}))
