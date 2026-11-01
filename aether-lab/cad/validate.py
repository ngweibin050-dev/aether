"""B-rep validation (OpenCascade facilities) for every component and the assembly. Results are plain dicts.

Checks per solid: BRepCheck_Analyzer validity (and which sub-shapes fail, with their status codes), closure (free
edges = 0), orientation (a far point classifies OUT), volume > 0 and finite, degenerate / tiny edges and faces, max
tolerance, Boolean-argument validity (BRepAlgoAPI_Check: self-intersection, small edges).
"""
from __future__ import annotations

import numpy as np

from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer, BRepCheck_ListOfStatus, BRepCheck_NoError
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_OUT, TopAbs_SHELL, TopAbs_SOLID, TopAbs_VERTEX, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt


def _count(shape, kind):
    n = 0
    ex = TopExp_Explorer(shape, kind)
    while ex.More():
        n += 1
        ex.Next()
    return n


def bbox(shape):
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b, True)
    x0, y0, z0, x1, y1, z1 = b.Get()
    return [x0, y0, z0, x1, y1, z1]


def mass(shape):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g, 1e-7, True)             # error-controlled integration (rel. eps 1e-7)
    c = g.CentreOfMass()
    a = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, a, 1e-7)
    return {"volume_mm3": float(g.Mass()), "area_mm2": float(a.Mass()), "centre_mm": [c.X(), c.Y(), c.Z()]}


def failing_subshapes(shape, limit=12):
    """Which sub-shapes BRepCheck rejects, with their status names."""
    an = BRepCheck_Analyzer(shape)
    out = []
    for kind, name in ((TopAbs_VERTEX, "vertex"), (TopAbs_EDGE, "edge"), (TopAbs_WIRE, "wire"), (TopAbs_FACE, "face"),
                       (TopAbs_SHELL, "shell"), (TopAbs_SOLID, "solid")):
        ex = TopExp_Explorer(shape, kind)
        i = 0
        while ex.More():
            sub = ex.Current()
            res = an.Result(sub)
            if res is not None:
                sts = [str(s).split(".")[-1] for s in res.Status() if s != BRepCheck_NoError]
                if sts:
                    out.append({"type": name, "index": i, "status": sts})
                    if len(out) >= limit:
                        return out
            i += 1
            ex.Next()
    return out


def check_solid(shape, name="solid", argument_analysis=True):
    r = {"name": name}
    an = BRepCheck_Analyzer(shape)
    r["brepcheck_valid"] = bool(an.IsValid())
    if not r["brepcheck_valid"]:
        r["brepcheck_failures"] = failing_subshapes(shape)
    r["solids"] = _count(shape, TopAbs_SOLID)
    r["shells"] = _count(shape, TopAbs_SHELL)
    r["faces"] = _count(shape, TopAbs_FACE)
    r["edges"] = _count(shape, TopAbs_EDGE)
    fb = ShapeAnalysis_FreeBounds(shape, 1e-6, False, False)
    r["free_edges"] = _count(fb.GetClosedWires(), TopAbs_EDGE) + _count(fb.GetOpenWires(), TopAbs_EDGE)
    m = mass(shape)
    r.update({k: (round(v, 3) if isinstance(v, float) else [round(c, 3) for c in v]) for k, v in m.items()})
    bb = bbox(shape)
    r["bbox_mm"] = [round(v, 3) for v in bb]
    far = gp_Pnt(bb[3] + 1e4, bb[4] + 1e4, bb[5] + 1e4)
    cl = BRepClass3d_SolidClassifier(shape, far, 1e-6)
    r["far_point_outside"] = cl.State() == TopAbs_OUT
    tol = 0.0
    for kind, getter in ((TopAbs_VERTEX, lambda s: BRep_Tool.Tolerance_s(TopoDS.Vertex_s(s))),
                         (TopAbs_EDGE, lambda s: BRep_Tool.Tolerance_s(TopoDS.Edge_s(s))),
                         (TopAbs_FACE, lambda s: BRep_Tool.Tolerance_s(TopoDS.Face_s(s)))):
        ex = TopExp_Explorer(shape, kind)
        while ex.More():
            tol = max(tol, getter(ex.Current()))
            ex.Next()
    r["max_tolerance_mm"] = round(tol, 6)
    deg = 0
    ex = TopExp_Explorer(shape, TopAbs_EDGE)
    while ex.More():
        if BRep_Tool.Degenerated_s(TopoDS.Edge_s(ex.Current())):
            deg += 1
        ex.Next()
    r["degenerated_edges"] = deg
    if argument_analysis:
        r["argument_analysis"] = _argument_analysis(shape)
    size = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
    r["valid"] = bool(r["brepcheck_valid"] and r["solids"] >= 1 and r["free_edges"] == 0 and r["far_point_outside"]
                      and r["volume_mm3"] > 0 and np.isfinite(r["volume_mm3"]) and r["max_tolerance_mm"] <= 1e-3 * size + 1e-3
                      and not r.get("argument_analysis", {}).get("faulty"))
    return r


def _argument_analysis(shape):
    """Boolean-argument validity of one shape: BRepAlgoAPI_Check with self-intersection and small-edge tests ON (the
    BOPAlgo_ArgumentAnalyzer of this OCP build exposes its mode switches without setters, so with it no test ran).
    Returns {"faulty": bool, "faults": {status: count}}."""
    import collections
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
    c = BRepAlgoAPI_Check(shape, True, True)
    cnt = collections.Counter(str(r.GetCheckStatus()).split(".")[-1] for r in c.Result())
    return {"faulty": not c.IsValid(), "faults": dict(cnt), "check": "BRepAlgoAPI_Check(self-intersection, small edges)"}
