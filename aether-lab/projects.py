"""Projects: every piece of work lives in its own folder, kept in sync with the running lab.

    output/projects/<slug>/project.json     name, created / saved times, the scene, the assistant's history, the chat
                           files/            what the user attached (drawings, PDFs and their pages, GLB / STL / STEP)
                           exports/          what the assistant made for download (GLB, STL, STEP, drawings)
                           versions/         a snapshot of the scene after every assistant turn that changed it

The server keeps one project open. Every change of the scene or the chat is saved to disk right away (save()), so the
app and the folder never disagree and reopening a project restores the scene and the conversation. Local only: the
folder can be synced by any file sync (OneDrive, Dropbox, git) because everything is plain JSON and the files.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "output" / "projects"
_lock = threading.Lock()
CURRENT = {"slug": None}


def slug(name):
    s = re.sub(r"[^\w\- ]+", "", str(name), flags=re.UNICODE).strip().replace(" ", "-").lower()
    return s[:48] or "project"


def path(sl=None):
    return ROOT / (sl or CURRENT["slug"])


def files_dir():
    return path() / "files"


def exports_dir():
    return path() / "exports"


def _read(sl):
    f = ROOT / sl / "project.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def listing():
    ROOT.mkdir(parents=True, exist_ok=True)
    out = []
    for d in ROOT.iterdir():
        meta = d / "project.json"
        if d.is_dir() and meta.exists():
            try:
                j = json.loads(meta.read_text(encoding="utf-8"))
            except ValueError:
                continue
            out.append({"slug": d.name, "name": j.get("name", d.name), "saved": j.get("saved"), "created": j.get("created"),
                        "models": len([p for p in j.get("state", {}).get("parts", []) if not p.get("parent")]),
                        "versions": len(list((d / "versions").glob("*.json"))) if (d / "versions").exists() else 0})
    return sorted(out, key=lambda x: x.get("saved") or "", reverse=True)


def create(name, state):
    sl = slug(name)
    k = 2
    while (ROOT / sl).exists():
        sl = f"{slug(name)}-{k}"
        k += 1
    for sub in ("files", "exports", "versions"):
        (ROOT / sl / sub).mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    doc = {"name": name, "created": now, "saved": now, "state": state, "history": [], "chat": []}
    (ROOT / sl / "project.json").write_text(json.dumps(doc, default=str), encoding="utf-8")
    CURRENT["slug"] = sl
    return {"slug": sl, "name": name}


def open_(sl):
    doc = _read(sl)
    if doc is None:
        raise ValueError(f"no project '{sl}'")
    for sub in ("files", "exports", "versions"):
        (ROOT / sl / sub).mkdir(parents=True, exist_ok=True)
    CURRENT["slug"] = sl
    return doc


def save(state, history=None, chat=None):
    """Write the open project (scene + assistant history + chat). Cheap enough to call after every change."""
    if not CURRENT["slug"]:
        return None
    with _lock:
        f = path() / "project.json"
        doc = _read(CURRENT["slug"]) or {"name": CURRENT["slug"], "created": time.strftime("%Y-%m-%d %H:%M:%S")}
        doc["state"] = state
        if history is not None:
            doc["history"] = history
        if chat is not None:
            doc["chat"] = chat
        doc["saved"] = time.strftime("%Y-%m-%d %H:%M:%S")
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, default=str), encoding="utf-8")
        tmp.replace(f)                                   # atomic: a crash never leaves half a project
        return doc["saved"]


def snapshot(state, label):
    """A version of the scene (after an assistant turn that changed it, or on request)."""
    if not CURRENT["slug"]:
        return None
    d = path() / "versions"
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.glob("*.json"))) + 1
    v = {"n": n, "label": label[:120], "t": time.strftime("%Y-%m-%d %H:%M:%S"), "state": copy.deepcopy(state)}
    (d / f"v{n:04d}.json").write_text(json.dumps(v, default=str), encoding="utf-8")
    return n


def versions():
    d = path() / "versions"
    out = []
    for f in sorted(d.glob("v*.json")) if d.exists() else []:
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            out.append({"n": j["n"], "label": j["label"], "t": j["t"],
                        "models": len([p for p in j["state"]["parts"] if not p.get("parent")])})
        except (ValueError, KeyError):
            continue
    return out[::-1]


def version_state(n):
    f = path() / "versions" / f"v{int(n):04d}.json"
    return json.loads(f.read_text(encoding="utf-8"))["state"]


def rename(name):
    doc = _read(CURRENT["slug"])
    doc["name"] = name
    (path() / "project.json").write_text(json.dumps(doc, default=str), encoding="utf-8")
    return {"slug": CURRENT["slug"], "name": name}


def delete(sl):
    if sl == CURRENT["slug"]:
        raise ValueError("close the project before deleting it")
    shutil.rmtree(ROOT / sl)
    return {"deleted": sl}


def ensure(default_state):
    """The project the lab opens with: the most recently saved one, else a new 'Untitled project'."""
    ls = listing()
    if ls:
        return open_(ls[0]["slug"])
    create("Untitled project", default_state)
    return _read(CURRENT["slug"])
