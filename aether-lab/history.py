"""The open project's undo history: ONE history for every change of the scene (an assistant turn, an edit in the app,
a model built in the background), saved with the project.

Each step stores only the parts it changed, as they were before and after. Undoing a step puts back exactly those
parts and leaves everything else alone: undoing "add details to the car" never touches another model, and a model
built in the background meanwhile stays. A step that later steps build on (they changed the same parts, or added
parts under a model it added) is undone together with them, and the answer says so. An undone step can be redone.

    record(before, state, label, source)   after a change; before = snapshot(state) taken before it
    undo(state, to=None)                   the newest step the user made (or the step `to` and what builds on it)
    redo(state)                            the last undo, back
    listing()                              for the History panel
Sources: "ai" (assistant turn), "edit" (the app: move, delete, colour...), "build" (a model built from a drawing),
"auto" (the CAD detail pass: windows, lights). Undo without an id skips "auto" steps: the user did not make them.
"""
from __future__ import annotations

import copy
import gzip
import json
import time
import uuid
from pathlib import Path

DEPTH = 80
DONE = []                    # steps, oldest first
UNDONE = []                  # undone groups of steps (redo), newest last
ON_CHANGE = None             # set by the server: save the history with the project
HEAVY = ("vertices", "faces", "normals", "lines", "regions")     # mesh arrays: replaced on re-import, never edited in place


def _copy(p):
    """A part, copied; its mesh arrays are shared (cheap: a CAD body is megabytes)."""
    q = {k: copy.deepcopy(v) for k, v in p.items() if k != "params"}
    prm = p.get("params")
    q["params"] = {k: (v if k in HEAVY else copy.deepcopy(v)) for k, v in prm.items()} if isinstance(prm, dict) \
        else copy.deepcopy(prm)
    return q


def snapshot(state):
    return {"parts": [_copy(p) for p in state["parts"]], "selected": state.get("selected")}


def _changed():
    if ON_CHANGE:
        ON_CHANGE()


def record(before, state, label, source="ai", extra=None):
    """A step from `before` (snapshot) to the scene now: only the parts that differ. None when nothing changed."""
    b = {p["id"]: (i, p) for i, p in enumerate(before["parts"])}
    a = {p["id"]: (i, p) for i, p in enumerate(state["parts"])}
    bef, aft, pos_b, pos_a = {}, {}, {}, {}
    for pid, (i, p) in b.items():
        q = a.get(pid)
        if q is None or q[1] != p:
            bef[pid], pos_b[pid] = p, i
            aft[pid] = _copy(q[1]) if q else None
            if q:
                pos_a[pid] = q[0]
    for pid, (i, q) in a.items():
        if pid not in b:
            bef[pid], aft[pid], pos_a[pid] = None, _copy(q), i
    if not bef:
        return None
    label = (label or "change").strip()
    e = {"id": uuid.uuid4().hex[:10], "label": label if len(label) <= 80 else label[:77].rstrip() + "…",
         "source": source, "t": time.time(), "before": bef, "after": aft, "pos_before": pos_b, "pos_after": pos_a,
         "selected": [before.get("selected"), state.get("selected")], **({"extra": extra} if extra else {})}
    DONE.append(e)
    del DONE[:-DEPTH]
    UNDONE.clear()
    _changed()
    return e


def _apply(state, e, side):
    """Put the parts of step e as they were ("before": undo) or became ("after": redo). Returns the parts that had
    changed since (by something not in the history), which are overwritten."""
    target, pos = e[side], e["pos_" + side]
    other = e["after" if side == "before" else "before"]
    parts = state["parts"]
    now = {p["id"]: p for p in parts}
    drifted = [now[pid]["name"] for pid, v in other.items() if pid in now and v is not None and now[pid] != v]
    gone = {pid for pid, v in target.items() if v is None}
    parts[:] = [p for p in parts if p["id"] not in gone]
    for pid, v in sorted(((k, v) for k, v in target.items() if v is not None), key=lambda kv: pos.get(kv[0], 1 << 30)):
        v = _copy(v)
        j = next((i for i, p in enumerate(parts) if p["id"] == pid), None)
        if j is None:
            parts.insert(min(pos.get(pid, len(parts)), len(parts)), v)
        else:
            parts[j] = v
    # parts under a model that this removed go with it (they cannot hang in the air on their own)
    ids = {p["id"] for p in parts}
    while True:
        orphans = {p["id"] for p in parts if p.get("parent") and p["parent"] not in ids}
        if not orphans:
            break
        parts[:] = [p for p in parts if p["id"] not in orphans]
        ids -= orphans
    sel = e["selected"][0 if side == "before" else 1]
    state["selected"] = sel if sel in ids else None
    state["version"] = int(state.get("version", 0)) + 1
    return drifted


def _touched(e):
    """The parts a step depends on: the ones it changed, and the models it added parts under."""
    out = set(e["before"])
    for side in ("before", "after"):
        out |= {v.get("parent") for v in e[side].values() if v and v.get("parent")}
    return out


def _with_dependents(k):
    """Step k and the later steps that build on it."""
    keys = set(DONE[k]["before"])
    out = [k]
    for j in range(k + 1, len(DONE)):
        if _touched(DONE[j]) & keys:
            out.append(j)
            keys |= set(DONE[j]["before"])
    return out


def describe(steps, undo=True):
    """What undoing (or redoing) these steps does, in words: 'removed headlight left, tail light bar (+7 more)'."""
    add, rem, mod = [], [], []
    for e in steps:
        a, b = (e["before"], e["after"]) if undo else (e["after"], e["before"])
        for pid in e["before"]:
            new, old = a[pid], b[pid]
            if new is None and old is not None:
                rem.append(old["name"])
            elif old is None and new is not None:
                add.append(new["name"])
            elif new is not None:
                mod.append(new["name"])

    def names(xs):
        xs = list(dict.fromkeys(xs))
        return ", ".join(xs[:6]) + (f" (+{len(xs) - 6} more)" if len(xs) > 6 else "")
    out = []
    if rem:
        out.append(f"removed {names(rem)}")
    if add:
        out.append(f"put back {names(add)}")
    if mod:
        out.append(f"restored {names(mod)}")
    return "; ".join(out) or "no visible change"


def undo(state, to=None):
    """Undo the newest step the user made (to=None: assistant turns, edits, builds; not the automatic CAD detail
    pass), or step `to` together with the later steps that build on it. Other models are never touched."""
    if to is None:
        k = next((i for i in range(len(DONE) - 1, -1, -1) if DONE[i]["source"] != "auto"), None)
        if k is None:
            return {"undone": False, "why": "nothing to undo in this project"}
    else:
        k = next((i for i, e in enumerate(DONE) if e["id"] == to), None)
        if k is None:
            return {"undone": False, "why": "that step is no longer in the undo history (it was undone already, or is older "
                                            f"than the last {DEPTH} steps)"}
    ks = _with_dependents(k)
    steps = [DONE[j] for j in ks]
    drifted = []
    for e in reversed(steps):
        drifted += _apply(state, e, "before")
    for j in sorted(ks, reverse=True):
        del DONE[j]
    UNDONE.append(steps)
    _changed()
    return {"undone": True, "reverted": steps[0]["label"], "also_undone": [e["label"] for e in steps[1:]],
            "what": describe(steps), "overwritten_edits": sorted(set(drifted))[:8],
            "cad": [e["extra"] for e in steps if (e.get("extra") or {}).get("cad")], "redo_available": True}


def redo(state):
    if not UNDONE:
        return {"redone": False, "why": "nothing to redo"}
    steps = UNDONE.pop()
    for e in steps:
        _apply(state, e, "after")
        DONE.append(e)
    _changed()
    return {"redone": True, "step": steps[0]["label"], "what": describe(steps, undo=False),
            "cad": [e["extra"] for e in steps if (e.get("extra") or {}).get("cad")]}


def listing():
    def row(e, undone=False):
        n = len(e["before"])
        return {"id": e["id"], "label": e["label"], "source": e["source"], "t": e["t"], "parts": n, "undone": undone}
    return {"steps": [row(e) for e in DONE][::-1], "redo": [row(g[0], True) for g in UNDONE][::-1],
            "can_undo": any(e["source"] != "auto" for e in DONE), "can_redo": bool(UNDONE)}


def reset(done=(), undone=()):
    DONE[:] = list(done)
    UNDONE[:] = list(undone)


def heavy_cad_parts(min_faces):
    """Every CAD-program part version in the history whose display mesh has more than min_faces face indices."""
    out = []
    for e in DONE + [x for g in UNDONE for x in g]:
        for p in _parts_of(e):
            prm = p.get("params")
            if p.get("type") == "cad" and (p.get("eng") or {}).get("brep") and isinstance(prm, dict) \
                    and len(prm.get("faces") or []) > min_faces:
                out.append(p)
    return out


# ------------------------------------------------------------------------------------------------ saved with the project
def _parts_of(e):
    for side in ("before", "after"):
        for v in e[side].values():
            if v is not None:
                yield v


def save(folder):
    """-> folder/undo.json.gz. A mesh is stored once (the same CAD body appears in many steps)."""
    meshes = {}

    def lean(p):
        prm = p.get("params")
        if p.get("type") in ("cad", "mesh") and isinstance(prm, dict) and "vertices" in prm:
            k = f"{p['id']}:{len(prm['vertices'])}:{len(prm.get('faces') or [])}"
            meshes.setdefault(k, prm)
            return {**p, "params": {"$mesh": k}}
        return p

    def pack(e):
        return {**e, "before": {k: v and lean(v) for k, v in e["before"].items()},
                "after": {k: v and lean(v) for k, v in e["after"].items()}}
    data = {"format": 2, "done": [pack(e) for e in DONE], "undone": [[pack(e) for e in g] for g in UNDONE],
            "meshes": meshes}
    f = Path(folder) / "undo.json.gz"
    tmp = f.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=3) as g:
        json.dump(data, g, default=str)
    tmp.replace(f)


def load(folder, state=None):
    """The history saved with a project. An older project's undo.json.gz (whole-scene snapshots) is turned into steps:
    each snapshot to the next one (the last one to the scene as it is now)."""
    f = Path(folder) / "undo.json.gz"
    reset()
    if not f.exists():
        return
    try:
        with gzip.open(f, "rt", encoding="utf-8") as g:
            d = json.load(g)
    except (OSError, ValueError):
        return
    M = d.get("meshes") or {}

    def fat(p):
        if p and isinstance(p.get("params"), dict) and p["params"].get("$mesh") in M:
            return {**p, "params": M[p["params"]["$mesh"]]}
        return p

    def unpack(e):
        return {**e, "before": {k: fat(v) for k, v in e["before"].items()}, "after": {k: fat(v) for k, v in e["after"].items()}}
    if d.get("format") == 2:
        reset([unpack(e) for e in d["done"]], [[unpack(e) for e in g] for g in d["undone"]])
        return
    stack = [{**e, "parts": [fat(p) for p in e["parts"]]} for e in d.get("stack") or []]
    if not stack or state is None:
        return
    for i, e in enumerate(stack):
        nxt = stack[i + 1] if i + 1 < len(stack) else state
        x = record({"parts": e["parts"], "selected": e.get("selected")}, nxt, e.get("label") or "assistant change",
                   "build" if (e.get("label") or "").startswith("build ") else "ai")
        if x:
            x["id"] = e.get("id") or x["id"]      # the chat's "undo this" buttons keep working
    UNDONE.clear()
