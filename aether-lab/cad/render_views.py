"""Renders of a model for the review loop, made the way a person sees it: the GLB in a three.js studio scene
(cad/render/render.html, the lab's own three.js), screenshotted by headless Chrome. Returns None when Chrome is not
installed (the caller then uses cad.codegen.render, the built-in software renderer)."""
from __future__ import annotations

import functools
import os
import shutil
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
VIEWS = ("iso", "iso_rear", "side", "front", "rear", "top", "cockpit")


def chrome():
    env = os.environ.get("AETHER_CHROME")
    cands = [env] if env else []
    cands += [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    cands += [shutil.which(n) for n in ("google-chrome", "chromium", "chromium-browser", "chrome")]
    return next((c for c in cands if c and os.path.exists(c)), None)


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def render(glb, out_dir, views=VIEWS, size=(1280, 720), timeout=60):
    """{view: png path} for a GLB under the lab folder, or None (no browser / the GLB is outside the lab)."""
    exe = chrome()
    glb = Path(glb).resolve()
    if not exe:
        return None
    if LAB not in glb.parents:                       # a job folder outside the lab (a cloud job's /tmp): serve a copy
        import hashlib
        tmp = LAB / "output" / "_render"
        tmp.mkdir(parents=True, exist_ok=True)
        dst = tmp / (hashlib.sha1(str(glb).encode()).hexdigest()[:12] + ".glb")
        shutil.copy2(glb, dst)
        glb = dst
    srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(LAB)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    lib = "local" if (LAB / "ui" / "node_modules" / "three" / "build" / "three.module.js").exists() else "cdn"
    rel = "/" + glb.relative_to(LAB).as_posix()
    out = {}
    os.makedirs(out_dir, exist_ok=True)
    root = os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0      # Chromium as root (a container)

    def one(v):
        f = Path(out_dir).resolve() / f"view_{v}.png"
        url = f"http://127.0.0.1:{srv.server_address[1]}/cad/render/render.html?glb={rel}&view={v}&lib={lib}"
        cmd = [exe, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
               f"--window-size={size[0]},{size[1]}", "--virtual-time-budget=25000", "--hide-scrollbars",
               f"--user-data-dir={Path(out_dir).resolve() / ('_chrome_' + v)}", f"--screenshot={f}", url]
        if root:
            cmd.insert(1, "--no-sandbox")
        try:
            subprocess.run(cmd, timeout=timeout, capture_output=True)
        except subprocess.TimeoutExpired:
            return v, None
        return v, (str(f) if f.exists() and f.stat().st_size > 5000 else None)
    try:
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(min(len(views), max(2, (os.cpu_count() or 4) // 2))) as pool:   # views in parallel
            for v, f in pool.map(one, views):
                if f:
                    out[v] = f
        for v in [v for v in views if v not in out]:      # a view Chrome shot before the model loaded: again, alone
            v, f = one(v)
            if f:
                out[v] = f
    finally:
        srv.shutdown()
    return out or None
