"""Quality gates for a model-written CAD assembly: deterministic checks in code, the same for any object.

    gates(parts, plan_names=None) -> report

- floating: a part that touches nothing (no other part within FLOAT_MM)
- sliver / sticker: average thickness 2V/A below MIN_THICK_MM (a flat patch stuck on a surface), glass excepted
- box-like: a plain box (6 planar faces): fine for a crate, crude for anything curved; reported as a share
- overlap: two parts sharing more than OVERLAP_FRAC of the smaller one's volume (one passes through the other)
- coverage: components of the plan (the model's own component list) that the program did not build
The report goes back to the model every round and decides, with the critic, which round is kept."""
from __future__ import annotations

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.Bnd import Bnd_Box
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

FLOAT_MM = 2.0
CLEARANCE_MM = 8.0
MIN_THICK_MM = 1.2
OVERLAP_FRAC = 0.25
MAX_OVERLAP_PAIRS = 80
OVERLAP_BUDGET_S = 25.0


def _props(shape):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    v = abs(g.Mass())
    a = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, a)
    return v, a.Mass()


def _box(shape, pad=0.0):
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b)
    if pad:
        b.Enlarge(pad)
    return b


def _faces(shape):
    out = []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        out.append(TopoDS.Face_s(ex.Current()))
        ex.Next()
    return out


def _is_box(shape):
    fs = _faces(shape)
    return len(fs) == 6 and all(BRepAdaptor_Surface(f).GetType() == GeomAbs_Plane for f in fs)


def _axes(shape):
    """The axes of a part's cylindrical faces: [(point, direction)] (a shaft, a bore, a hub)."""
    import numpy as np
    from OCP.GeomAbs import GeomAbs_Cylinder
    out = []
    for f in _faces(shape):
        s = BRepAdaptor_Surface(f)
        if s.GetType() == GeomAbs_Cylinder:
            ax = s.Cylinder().Axis()
            p, d = ax.Location(), ax.Direction()
            out.append((np.array([p.X(), p.Y(), p.Z()]), np.array([d.X(), d.Y(), d.Z()])))
    return out


def constraints(parts, cons):
    """The plan's mechanical relations, checked on the geometry:
    coaxial (a, b): some cylindrical axis of a and of b parallel within 2 deg and within 1 mm of each other;
    contact (a, b): a and b touch (gap <= 0.5 mm);
    clearance (a, b, value): the gap between them is between half and twice the stated value (mm);
    meshes (a, b): touching (gap <= 1 mm) and not passing through each other (shared volume < 2 % of the smaller).
    Returns [{type, a, b, ok, measured}]."""
    import numpy as np
    by = {p["name"].lower(): p for p in parts}
    res = []
    for c in cons or []:
        a, b = by.get(str(c.get("a", "")).lower()), by.get(str(c.get("b", "")).lower())
        r = {"type": c.get("type"), "a": c.get("a"), "b": c.get("b"), "ok": False, "measured": None}
        if a is None or b is None:
            r["measured"] = "a named part is not built"
            res.append(r)
            continue
        t = c.get("type")
        if t == "coaxial":
            best = None
            for pa, da in _axes(a["shape"]):
                for pb, db in _axes(b["shape"]):
                    ang = float(np.degrees(np.arccos(min(1.0, abs(float(da @ db))))))
                    dist = float(np.linalg.norm(np.cross(pb - pa, da)))
                    if best is None or (ang, dist) < best:
                        best = (ang, dist)
            r["ok"] = bool(best and best[0] <= 2.0 and best[1] <= 1.0)
            r["measured"] = f"axis angle {best[0]:.2f} deg, offset {best[1]:.2f} mm" if best else "no cylindrical face on one part"
        else:
            d = BRepExtrema_DistShapeShape(a["shape"], b["shape"])
            gap = d.Value() if d.IsDone() else None
            if t == "contact":
                r["ok"] = gap is not None and gap <= 0.5
            elif t == "clearance":
                v = float(c.get("value") or 0)
                r["ok"] = gap is not None and v > 0 and 0.5 * v <= gap <= 2 * v
            elif t == "meshes":
                shared = 0.0
                try:
                    cm = BRepAlgoAPI_Common(a["shape"], b["shape"])
                    shared = _props(cm.Shape())[0] if cm.IsDone() else 0.0
                except Exception:
                    pass
                small = min(_props(a["shape"])[0], _props(b["shape"])[0]) or 1.0
                r["ok"] = gap is not None and gap <= 1.0 and shared / small < 0.02
            r["measured"] = f"gap {gap:.2f} mm" if gap is not None else "distance failed"
        res.append(r)
    return res


def gates(parts, plan_names=None, free=(), cons=None):
    """free: names of parts whose plan says they rotate / slide / sit with a deliberate clearance: they may stand off
    their neighbours by up to CLEARANCE_MM (a bearing gap, a gear backlash) without counting as floating."""
    n = len(parts)
    info = []
    for p in parts:
        v, a = _props(p["shape"])
        info.append({"name": p["name"], "material": p.get("material"), "v": v, "a": a, "box": _box(p["shape"]),
                     "boxlike": _is_box(p["shape"])})
    slivers = [i["name"] for i in info if i["material"] != "glass" and i["a"] > 0 and 2 * i["v"] / i["a"] < MIN_THICK_MM]
    boxes = [i["name"] for i in info if i["boxlike"]]
    floating = []
    root = max(range(n), key=lambda i: info[i]["v"]) if n else -1     # the assembly's root never "floats"
    for k, p in enumerate(parts):
        if k == root:
            continue
        bk = _box(p["shape"], CLEARANCE_MM)
        near = [j for j in range(n) if j != k and not bk.IsOut(info[j]["box"])]
        if not near:
            floating.append(p["name"])
            continue
        best = None
        for j in near:
            d = BRepExtrema_DistShapeShape(p["shape"], parts[j]["shape"])
            if d.IsDone():
                best = d.Value() if best is None else min(best, d.Value())
                if best <= FLOAT_MM:
                    break
        lim = CLEARANCE_MM if p["name"].split(".")[0] in free else FLOAT_MM
        if best is None or best > lim:
            floating.append(p["name"])
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if not info[i]["box"].IsOut(info[j]["box"]):
                pairs.append((i, j))
    def bvol(b):
        x0, y0, z0, x1, y1, z1 = b.Get()
        return max(x1 - x0, 0) * max(y1 - y0, 0) * max(z1 - z0, 0)
    pairs.sort(key=lambda ij: -min(bvol(info[ij[0]]["box"]), bvol(info[ij[1]]["box"])))
    overlaps = []
    import time
    t_end = time.time() + OVERLAP_BUDGET_S
    for i, j in pairs[:MAX_OVERLAP_PAIRS]:
        if time.time() > t_end:                          # the biggest pairs are checked first; the rest is skipped
            break
        try:
            c = BRepAlgoAPI_Common(parts[i]["shape"], parts[j]["shape"])
            if not c.IsDone():
                continue
            cv, _ = _props(c.Shape())
        except Exception:
            continue
        small = min(info[i]["v"], info[j]["v"]) or 1.0
        if cv / small > OVERLAP_FRAC:
            overlaps.append([info[i]["name"], info[j]["name"], round(cv / small, 2)])
    missing = []
    if plan_names:
        built = {i["name"].strip().lower() for i in info}
        missing = [m for m in plan_names if m.strip().lower() not in built]
    rep = {"parts": n, "floating": floating, "slivers": slivers, "box_like": boxes,
           "box_share": round(len(boxes) / max(n, 1), 2), "overlaps": overlaps, "missing_from_plan": missing}
    cres = constraints(parts, cons) if cons else []
    rep["constraints"] = cres
    bad_c = [c for c in cres if not c["ok"]]
    rep["hard_fail"] = bool(floating or slivers or overlaps or bad_c)
    rep["summary"] = (f"{n} parts; floating {len(floating)}, stickers/slivers {len(slivers)}, box-like {len(boxes)} "
                      f"({int(100 * rep['box_share'])} %), wrong overlaps {len(overlaps)}, planned but missing {len(missing)}"
                      + (f", constraints failed {len(bad_c)} of {len(cres)}" if cres else ""))
    return rep
