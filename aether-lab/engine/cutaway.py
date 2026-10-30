"""Seeing inside a design: exploded view, section cut, isolate and X-ray.

The same view settings drive the 3D viewport and the hologram, so the hologram shows exactly
what the designer sees: cut parts are cut in the light field too, exploded parts float apart.

state["view"] = {"explode": 0..1, "section": None | "x" | "y" | "z", "section_mm": float,
                 "section_flip": bool, "isolate": [part ids], "xray": bool}
"""
import copy

import numpy as np

from . import geometry

DEFAULT_VIEW = {"explode": 0.0, "section": None, "section_mm": 0.0, "section_flip": False,
                "isolate": [], "xray": False}
AXES = {"x": 0, "y": 1, "z": 2}


def view_of(state):
    return {**DEFAULT_VIEW, **(state.get("view") or {})}


def _subtree_box(pid, kids, by_id):
    """Bounding box of a part and all its descendants, in that part's parent frame."""
    p = by_id[pid]
    V, _ = geometry.local_mesh(p)
    pts = [V] if len(V) else []
    for c in kids.get(pid, []):
        lo, hi = _subtree_box(c, kids, by_id)
        if lo is not None:
            corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
            pts.append(corners)
    if not pts:
        return None, None
    P = np.vstack(pts)
    M = geometry.matrix(p)
    P = P @ M[:3, :3].T + M[:3, 3]
    return P.min(0), P.max(0)


def _main_axis(children, by_id):
    """Axis most children are built along (their local z mapped into the group frame)."""
    votes = np.zeros(3)
    for c in children:
        z = geometry.matrix(by_id[c])[:3, 2]
        votes[int(np.argmax(np.abs(z)))] += 1
    a = np.zeros(3)
    a[int(np.argmax(votes))] = 1.0
    return a


def explode_offsets(parts, gap=6.0):
    """Offset of every part (in its parent frame) at explode = 1. Linear in the explode factor.

    Coaxial parts (shells, shafts, rotors) are restacked along the assembly axis in their original
    order, each one its own slot, so nested parts slide out of each other. Off-axis parts (coils,
    magnets, bolts) ride with the coaxial part they sit in and also move outward radially.
    """
    by_id = {p["id"]: p for p in parts}
    kids = {}
    for p in parts:
        if p.get("parent") in by_id:
            kids.setdefault(p["parent"], []).append(p["id"])
    out = {p["id"]: np.zeros(3) for p in parts}
    for gid, children in kids.items():
        if len(children) < 2:
            continue
        boxes = {c: _subtree_box(c, kids, by_id) for c in children}
        boxes = {c: b for c, b in boxes.items() if b[0] is not None}
        if len(boxes) < 2:
            continue
        lo = np.min([b[0] for b in boxes.values()], 0)
        hi = np.max([b[1] for b in boxes.values()], 0)
        C = (lo + hi) / 2
        a = _main_axis(list(boxes), by_id)
        R = float(np.max(np.abs((hi - lo) * (1 - a)))) / 2 or 1.0
        info = {}
        for c, (blo, bhi) in boxes.items():
            cen = (blo + bhi) / 2 - C
            s = float(cen @ a)
            r = cen - s * a
            size = (bhi - blo) * (1 - a)
            info[c] = {"s": s, "r": r, "h": float((bhi - blo) @ a), "rad": float(np.max(size)) / 2,
                       "lo": float(blo @ a - C @ a), "hi": float(bhi @ a - C @ a)}
        coax = [c for c in info if np.linalg.norm(info[c]["r"]) < 0.25 * R]
        if not coax:
            coax = list(info)
        # stack coaxial parts along the axis in their current order (outer shells first on ties)
        order = sorted(coax, key=lambda c: (round(info[c]["s"], 1), -info[c]["rad"]))
        total = sum(info[c]["h"] for c in order) + gap * (len(order) - 1)
        z = -total / 2
        for c in order:
            target = z + info[c]["h"] / 2
            out[c] = a * (target - info[c]["s"])
            z += info[c]["h"] + gap
        for c in info:
            if c in coax:
                continue
            # host: coaxial part overlapping it along the axis, smallest one that reaches it radially
            d = np.linalg.norm(info[c]["r"])
            hosts = [h for h in coax if min(info[h]["hi"], info[c]["hi"]) - max(info[h]["lo"], info[c]["lo"]) > 0]
            hosts.sort(key=lambda h: (info[h]["rad"] < 0.8 * d, info[h]["rad"]))
            ride = out[hosts[0]] if hosts else np.zeros(3)
            out[c] = ride + info[c]["r"] / max(d, 1e-9) * 0.6 * R
    return {k: v.tolist() for k, v in out.items()}


def _isolated(parts, ids):
    """Ids to show when isolating: the chosen parts, their descendants and their ancestors."""
    by_id = {p["id"]: p for p in parts}
    keep = set(i for i in ids if i in by_id)
    changed = True
    while changed:
        changed = False
        for p in parts:
            if p.get("parent") in keep and p["id"] not in keep:
                keep.add(p["id"])
                changed = True
    for i in list(keep):
        q = by_id[i].get("parent")
        while q in by_id:
            keep.add(q)
            q = by_id[q].get("parent")
    return keep


def view_parts(state):
    """Parts as shown: exploded and isolated. Used for sampling the hologram and all checks."""
    v = view_of(state)
    parts = state["parts"]
    if not v["explode"] and not v["isolate"]:
        return parts
    parts = copy.deepcopy(parts)
    if v["explode"]:
        off = explode_offsets(parts)
        for p in parts:
            p["position"] = [a + v["explode"] * b for a, b in zip(p["position"], off[p["id"]])]
    if v["isolate"]:
        keep = _isolated(parts, v["isolate"])
        for p in parts:
            if p["id"] not in keep:
                p["visible"] = False
    return parts


def section_mask(P, state):
    """True for points kept by the section cut (world mm)."""
    v = view_of(state)
    if not v["section"] or len(P) == 0:
        return np.ones(len(P), bool)
    d = P[:, AXES[v["section"]]] - v["section_mm"]
    return d >= 0 if v["section_flip"] else d <= 0
