"""B-rep -> triangles + normals + edge polylines (derived display data; never the source of geometry).

Normals come from the B-rep surfaces (BRepLProp_SLProps at each mesh node's UV), not from averaging triangles, so a
smooth NURBS face shades smoothly and a sharp B-rep edge stays sharp (faces do not share vertices).
"""
from __future__ import annotations

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GCPnts import GCPnts_TangentialDeflection
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS


def mesh(shape, linear=0.15, angular=0.25, relative=False, fast=False):
    """Returns (V (n,3) float32, F (m,3) int32, N (n,3) float32, face_id per triangle).
    fast: for display, silhouettes and review renders. The chord error grows with the part (a 20 m model is not meshed
    to 1 mm), any triangulation already stored in the shape is dropped, and the surface-deflection check is off: on a
    smooth loft that check alone multiplied the triangles ~30x (one 3-face fin: 72k triangles -> 2k)."""
    if not fast:
        BRepMesh_IncrementalMesh(shape, linear, relative, angular, True)
    else:
        from OCP.BRepTools import BRepTools
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        from OCP.IMeshTools import IMeshTools_Parameters
        b = Bnd_Box()
        BRepBndLib.Add_s(shape, b)
        d = 1.0 if b.IsVoid() else float(np.linalg.norm(np.subtract(b.Get()[3:], b.Get()[:3])))
        BRepTools.Clean_s(shape)
        p = IMeshTools_Parameters()
        p.Deflection = max(linear, d / 2000)
        p.Angle = angular
        p.MinSize = d / 1000
        p.ControlSurfaceDeflection = False
        p.InParallel = True
        BRepMesh_IncrementalMesh(shape, p)
    Vs, Fs, Ns, fid = [], [], [], []
    off = 0
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    k = 0
    while ex.More():
        face = TopoDS.Face_s(ex.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            n = tri.NbNodes()
            V = np.empty((n, 3))
            for i in range(1, n + 1):
                p = tri.Node(i).Transformed(trsf)
                V[i - 1] = (p.X(), p.Y(), p.Z())
            F = np.empty((tri.NbTriangles(), 3), np.int64)
            rev = face.Orientation() == TopAbs_REVERSED
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                F[i - 1] = (a - 1, c - 1, b - 1) if rev else (a - 1, b - 1, c - 1)
            N = np.zeros((n, 3))
            ok = False
            if tri.HasUVNodes():
                surf = BRepAdaptor_Surface(face)
                props = BRepLProp_SLProps(surf, 1, 1e-6)
                for i in range(1, n + 1):
                    uv = tri.UVNode(i)
                    props.SetParameters(uv.X(), uv.Y())
                    if props.IsNormalDefined():
                        d = props.Normal()
                        N[i - 1] = (d.X(), d.Y(), d.Z())
                if rev:
                    N = -N
                if not loc.IsIdentity():
                    R = np.array([[trsf.Value(r, c) for c in (1, 2, 3)] for r in (1, 2, 3)])
                    N = N @ R.T
                ok = True
            # fall back to triangle normals where the surface gave none (degenerate points)
            fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
            acc = np.zeros_like(V)
            for j in range(3):
                np.add.at(acc, F[:, j], fn)
            bad = (not ok) | (np.linalg.norm(N, axis=1) < 1e-9)
            N[bad] = acc[bad]
            N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
            # a surface normal pointing against the triangle winding: trust the winding (orientation errors)
            tn = np.zeros_like(V)
            for j in range(3):
                np.add.at(tn, F[:, j], fn)
            flip = np.einsum("ij,ij->i", N, tn) < 0
            N[flip] = -N[flip]
            Vs.append(V)
            Fs.append(F + off)
            Ns.append(N)
            fid.append(np.full(len(F), k))
            off += n
        k += 1
        ex.Next()
    if not Vs:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int32), np.zeros((0, 3), np.float32), np.zeros(0, int)
    return (np.vstack(Vs).astype(np.float32), np.vstack(Fs).astype(np.int32), np.vstack(Ns).astype(np.float32),
            np.concatenate(fid))


def edges(shape, deflection=0.2, sharp_only=True, min_angle_deg=12.0):
    """B-rep edges as line segments [[x0,y0,z0,x1,y1,z1], ...]. sharp_only drops seam edges and edges between two
    faces meeting tangentially (within min_angle_deg), which a viewer should not outline."""
    from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
    from OCP.TopExp import TopExp
    m = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, m)
    out = []
    for i in range(1, m.Extent() + 1):
        e = TopoDS.Edge_s(m.FindKey(i))
        if BRep_Tool.Degenerated_s(e):
            continue
        faces = m.FindFromIndex(i)
        if sharp_only and faces.Size() == 2:
            fl = [TopoDS.Face_s(f) for f in faces]
            if fl[0].IsSame(fl[1]):
                continue                                 # seam
            if _dihedral_deg(e, fl[0], fl[1]) < min_angle_deg:
                c0 = BRepAdaptor_Curve(e)
                mid = c0.Value((c0.FirstParameter() + c0.LastParameter()) / 2)
                if abs(mid.Y()) < 1.0:
                    continue                 # tangent seam on the symmetry plane: not a design line
                # tangent edge elsewhere = an imprinted line (window, light, panel): keep it
        c = BRepAdaptor_Curve(e)
        try:
            d = GCPnts_TangentialDeflection(c, 0.2, deflection)
            pts = [d.Value(j) for j in range(1, d.NbPoints() + 1)]
        except Exception:
            pts = [c.Value(c.FirstParameter()), c.Value(c.LastParameter())]
        P = np.array([[p.X(), p.Y(), p.Z()] for p in pts])
        for a, b in zip(P[:-1], P[1:]):
            out.append([*a, *b])
    return np.array(out, np.float32).reshape(-1, 6)


def _dihedral_deg(e, f1, f2):
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface
    c = BRepAdaptor_Curve(e)
    p = c.Value((c.FirstParameter() + c.LastParameter()) / 2)
    ns = []
    for f in (f1, f2):
        s = BRep_Tool.Surface_s(f)
        uv = ShapeAnalysis_Surface(s).ValueOfUV(p, 1e-3)
        pr = BRepLProp_SLProps(BRepAdaptor_Surface(f), uv.X(), uv.Y(), 1, 1e-6)
        if not pr.IsNormalDefined():
            return 90.0
        n = pr.Normal()
        v = np.array([n.X(), n.Y(), n.Z()])
        if f.Orientation() == TopAbs_REVERSED:
            v = -v
        ns.append(v)
    cos = float(np.clip(np.dot(ns[0], ns[1]), -1, 1))
    return float(np.degrees(np.arccos(cos)))
