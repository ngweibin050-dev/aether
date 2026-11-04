"""Projects: every piece of work lives in its own folder, kept in sync with the running lab.

    output/projects/<slug>/project.json     name, created / saved times, the scene, the assistant's history, the chat
                           files/            what the user attached (drawings, PDFs and their pages, GLB / STL / STEP)
                           exports/          what the assistant made for download (GLB, STL, STEP, drawings)
                           versions/         a snapshot of the scene after every assistant turn that changed it
                           undo.json.gz      the assistant's undo stack (a reopened project or a restarted server can
                                             still undo); each mesh stored once

The server keeps one project open. Every change of the scene or the chat is saved to disk right away (save()), so the
app and the folder never disagree and reopening a project restores the scene and the conversation. Local only: the
folder can be synced by any file sync (OneDrive, Dropbox, git) because everything is plain JSON and the files.
"""
from __future__ import annotations

import copy
import gzip
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
        if d.name.startswith("_"):                       # scratch projects of tests: never listed, never opened at start
            continue
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


def save_undo(stack):
    """The assistant's undo stack -> undo.json.gz. Meshes (CAD tessellations, imports) are stored once: a part's mesh
    never changes in place (a re-import makes new parts), so the part id + its size identify it."""
    if not CURRENT["slug"]:
        return
    meshes, out = {}, []
    for e in stack:
        parts = []
        for q in e["parts"]:
            prm = q.get("params") or {}
            if q.get("type") in ("cad", "mesh") and "vertices" in prm:
                k = f"{q['id']}:{len(prm['vertices'])}:{len(prm.get('faces') or [])}"
                meshes.setdefault(k, prm)
                q = {**q, "params": {"$mesh": k}}
            parts.append(q)
        out.append({**e, "parts": parts})
    with _lock:
        f = path() / "undo.json.gz"
        tmp = f.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=3) as g:
            json.dump({"stack": out, "meshes": meshes}, g, default=str)
        tmp.replace(f)


def load_undo():
    f = path() / "undo.json.gz"
    if not CURRENT["slug"] or not f.exists():
        return []
    try:
        with gzip.open(f, "rt", encoding="utf-8") as g:
            d = json.load(g)
    except (OSError, ValueError):
        return []
    M = d.get("meshes") or {}
    return [{**e, "parts": [{**q, "params": M[q["params"]["$mesh"]]} if isinstance(q.get("params"), dict)
                            and "$mesh" in q["params"] and q["params"]["$mesh"] in M else q for q in e["parts"]]}
            for e in d.get("stack") or []]


# ------------------------------------------------------------------------------------------------ chat sessions
# A project can hold several conversations about the same scene (one scene, one undo history). The open one is the
# project's "chat" / "history" (as before); the others wait in chats.json:
#   {"current": id, "sessions": {id: {"title", "created", "updated", "chat", "history"}}}

def _chats_file():
    return path() / "chats.json"


def _chats():
    f = _chats_file()
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d.setdefault("sessions", {})
    if not d.get("current"):
        d["current"] = "c1"
    d["sessions"].setdefault(d["current"], {"title": None, "created": time.strftime("%Y-%m-%d %H:%M:%S")})
    return d


def _write_chats(d):
    f = _chats_file()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, default=str), encoding="utf-8")
    tmp.replace(f)


def _title(chat):
    t = next((m.get("text") for m in chat or [] if m.get("role") == "user" and m.get("text")), None)
    t = " ".join((t or "").split())
    return (t[:48].rstrip() + "…") if len(t) > 48 else (t or "New chat")


def chat_list(chat):
    """The project's chats, newest first; `chat`: the open chat's messages (live, in the server)."""
    d = _chats()
    out = []
    for cid, x in d["sessions"].items():
        msgs = chat if cid == d["current"] else x.get("chat") or []
        out.append({"id": cid, "title": x.get("title") or _title(msgs), "messages": len(msgs),
                    "updated": x.get("updated") or x.get("created"), "current": cid == d["current"]})
    out.sort(key=lambda r: (not r["current"], r["updated"] or ""), reverse=False)
    cur = [r for r in out if r["current"]]
    rest = sorted([r for r in out if not r["current"]], key=lambda r: r["updated"] or "", reverse=True)
    return {"current": d["current"], "chats": cur + rest}


def chat_switch(chat, hist, to=None):
    """Park the open chat (chat, hist) and open chat `to` (None: a new, empty one). Returns (id, chat, history)."""
    d = _chats()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    cur = d["sessions"].setdefault(d["current"], {"title": None, "created": now})
    cur.update(chat=chat, history=hist, updated=now if chat else cur.get("updated"))
    if to is None:
        n = 1 + max([int(k[1:]) for k in d["sessions"] if k[1:].isdigit()] or [0])
        to = f"c{n}"
        d["sessions"][to] = {"title": None, "created": now, "chat": [], "history": []}
    if to not in d["sessions"]:
        raise ValueError(f"no chat '{to}' in this project")
    d["current"] = to
    x = d["sessions"][to]
    _write_chats(d)
    return to, list(x.get("chat") or []), list(x.get("history") or [])


def chat_rename(cid, title):
    d = _chats()
    d["sessions"][cid]["title"] = (title or "").strip()[:60] or None
    _write_chats(d)
    return {"id": cid, "title": d["sessions"][cid]["title"]}


def chat_delete(cid):
    d = _chats()
    if cid == d["current"]:
        raise ValueError("open another chat before deleting this one")
    d["sessions"].pop(cid, None)
    _write_chats(d)
    return {"deleted": cid}
