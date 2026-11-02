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

# The former mesh-built design-loop smoke test is unavailable until a CAD-backed fixture replaces it.
print("SKIPPED: CAD-backed design-loop smoke fixture not implemented")
