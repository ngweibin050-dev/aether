"""Exports from the validated B-rep (never from a mesh):

- STEP (AP214, XCAF): assembly structure, component names and colours, written by STEPCAFControl_Writer;
- STEP round trip: read back in a FRESH process (STEPCAFControl_Reader), re-validate every solid, compare per
  component (counts, volume, area, centre of mass, bounding box, sampled point distances both ways) against the
  originals within a STATED tolerance;
- GLB: a derived visualisation: tessellated from the B-rep (normals from the B-rep surfaces, B-rep sharp edges as a
  line primitive), one node per component, metres, Y up, provenance in node extras.
"""
from __future__ import annotations

import json
import struct
import subprocess
import sys

import numpy as np
from OCP.BRepTools import BRepTools
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool

from . import tessellate as T
from . import validate as Vd

STEP_TOL_MM = 1e-2          # stated tolerance for the round trip (max point distance, mm). STEP stores B-spline poles
                            # as decimal reals (~7 significant digits): on a 4.5 m body that is a few micrometres, so a
                            # 0.001 mm limit is below what the format represents; 0.01 mm is the stated limit.


def _rgb(hexs):
    h = (hexs or "#b9c3cf").lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def write_step(components, path):
    """components: [{"id", "name", "shape", "colour"}] (solids). Writes an AP214 STEP with one named, coloured
    product per component under one assembly."""
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    asm = st.NewShape()
    TDataStd_Name.Set_s(asm, TCollection_ExtendedString("AETHER_CAD_ASSEMBLY"))
    from OCP.TopLoc import TopLoc_Location
    for c in components:
        lab = st.AddShape(c["shape"], False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(c["id"]))
        r, g, b = _rgb(c.get("colour"))
        ct.SetColor(lab, Quantity_Color(r, g, b, Quantity_TOC_RGB), XCAFDoc_ColorSurf)
        comp = st.AddComponent(asm, lab, TopLoc_Location())
        TDataStd_Name.Set_s(comp, TCollection_ExtendedString(c["id"]))
    st.UpdateAssemblies()
    Interface_Static.SetCVal_s("write.step.schema", "AP214")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.SetColorMode(True)
    if not w.Transfer(doc, STEPControl_AsIs):
        raise RuntimeError("STEP transfer failed")
    if w.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")
    return str(path)


def read_step(path):
    """-> {name: shape} for every named leaf shape (solid) in the STEP file (XCAF reader)."""
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TDF import TDF_LabelSequence
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    r = STEPCAFControl_Reader()
    r.SetNameMode(True)
    r.SetColorMode(True)
    if r.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError("STEP read failed")
    if not r.Transfer(doc):
        raise RuntimeError("STEP transfer (read) failed")
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    seq = TDF_LabelSequence()
    st.GetShapes(seq)
    out = {}
    for i in range(1, seq.Length() + 1):
        lab = seq.Value(i)
        if st.IsAssembly_s(lab):
            continue
        name = TDataStd_Name()
        nm = None
        if lab.FindAttribute(TDataStd_Name.GetID_s(), name):
            nm = name.Get().ToExtString()
        shp = st.GetShape_s(lab)
        if nm and not shp.IsNull():
            out[nm] = shp
    return out


def _samples(shape, n=2000, seed=0):
    V, F, N, _ = T.mesh(shape, 0.3, 0.2)
    rng = np.random.default_rng(seed)
    if len(V) > n:
        V = V[rng.choice(len(V), n, replace=False)]
    return V.astype(float)


def _faces_with_boxes(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool
    out = []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        b = Bnd_Box()
        BRepBndLib.Add_s(f, b, True)
        out.append((f, np.array(b.Get()), ShapeAnalysis_Surface(BRep_Tool.Surface_s(f))))
        ex.Next()
    return out


def _dist_points_robust(points, shape, slack=2.0):
    """Point -> B-rep distance: projection onto every face surface whose box (grown by `slack` mm) contains the point,
    kept only if the projected UV lies inside the face (BRepClass_FaceClassifier). Falls back to BRepExtrema when no
    face qualifies. Returns (distances, n_fallback)."""
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON
    from OCP.gp import gp_Pnt, gp_Pnt2d
    faces = _faces_with_boxes(shape)
    out, fb = [], 0
    for p in points:
        P = gp_Pnt(*map(float, p))
        best = np.inf
        for f, bb, sas in faces:
            if np.any(p < bb[:3] - slack) or np.any(p > bb[3:] + slack):
                continue
            uv = sas.ValueOfUV(P, 1e-7)
            cl = BRepClass_FaceClassifier(f, gp_Pnt2d(uv.X(), uv.Y()), 1e-6)
            if cl.State() in (TopAbs_IN, TopAbs_ON):
                best = min(best, sas.Gap())
        ext = float(_dist_points([p], shape)[0])      # BRepExtrema: also a distance to a real point on the shape
        if not np.isfinite(best):
            fb += 1
        out.append(min(best, ext))                    # both are upper bounds of the true distance: keep the tighter
    return np.array(out), fb


def _dist_points(points, shape):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    d = []
    for p in points:
        v = BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float, p))).Vertex()
        ds = BRepExtrema_DistShapeShape(v, shape)
        ds.Perform()
        d.append(ds.Value() if ds.IsDone() else np.inf)
    return np.array(d)


def compare_shapes(a, b, n=600):
    """Original a vs re-imported b: counts, mass properties, bbox and sampled distances both ways (mm)."""
    va, vb = Vd.check_solid(a, argument_analysis=False), Vd.check_solid(b, argument_analysis=False)
    pa, pb = _samples(a, n), _samples(b, n, seed=1)
    (dab, fa), (dba, fb) = _dist_points_robust(pa, b), _dist_points_robust(pb, a)
    rel = lambda x, y: abs(x - y) / max(abs(x), 1e-12)
    out = {"reimported_valid": vb["valid"], "brepcheck_valid_reimport": vb["brepcheck_valid"],
           "counts": {"solids": [va["solids"], vb["solids"]], "faces": [va["faces"], vb["faces"]], "edges": [va["edges"], vb["edges"]]},
           "volume_rel_diff": rel(va["volume_mm3"], vb["volume_mm3"]), "area_rel_diff": rel(va["area_mm2"], vb["area_mm2"]),
           "centre_diff_mm": float(np.linalg.norm(np.subtract(va["centre_mm"], vb["centre_mm"]))),
           "bbox_diff_mm": float(np.max(np.abs(np.subtract(va["bbox_mm"], vb["bbox_mm"])))),
           "dist_orig_to_reimport_mm": {"mean": float(dab.mean()), "max": float(dab.max())},
           "dist_reimport_to_orig_mm": {"mean": float(dba.mean()), "max": float(dba.max())},
           "samples": [len(pa), len(pb)], "distance_method": "min(BRepExtrema point-shape distance, projection onto the face surfaces whose trimmed "
           f"region contains the foot point): both are distances to real points on the shape (upper bounds); {fa + fb} "
           "points had no in-face projection"}
    # the limit: STEP_TOL_MM, or the original B-rep's own maximum tolerance if larger (OCCT shapes are only defined
    # within their tolerance; Boolean / imprint intersection edges carry one). Both are reported.
    tol = max(STEP_TOL_MM, va["max_tolerance_mm"])
    out["tolerance_used_mm"] = tol
    out["original_max_tolerance_mm"] = va["max_tolerance_mm"]
    out["edge_count_note"] = ("equal" if out["counts"]["edges"][0] == out["counts"]["edges"][1] else
                              "differs: the STEP translator merges / splits collinear sub-edges; faces and solids must match")
    out["pass"] = bool(out["reimported_valid"] and out["counts"]["solids"][0] == out["counts"]["solids"][1]
                       and out["counts"]["faces"][0] == out["counts"]["faces"][1] and out["volume_rel_diff"] < 1e-6
                       and out["area_rel_diff"] < 1e-5 and out["bbox_diff_mm"] <= tol
                       and max(out["dist_orig_to_reimport_mm"]["max"], out["dist_reimport_to_orig_mm"]["max"]) <= tol)
    return out


def roundtrip(components, step_path, brep_dir):
    """Write STEP, then re-read and compare in a FRESH Python process (no shared kernel state). The originals are
    handed over as .brep files (OCCT's native exact format)."""
    write_step(components, step_path)
    names = []
    for c in components:
        p = f"{brep_dir}/{c['id']}.brep"
        BRepTools.Write_s(c["shape"], p)
        names.append(c["id"])
    code = ("import json,sys; sys.path.insert(0, %r); from cad import export as E; print(json.dumps(E._roundtrip_child(%r, %r, %r)))"
            % (str(__file__).rsplit("/cad/", 1)[0], str(step_path), str(brep_dir), names))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=1800)
    if p.returncode:
        raise RuntimeError("STEP round-trip process failed: " + (p.stderr or "")[-800:])
    res = json.loads(p.stdout.strip().splitlines()[-1])
    res["tolerance_mm"] = STEP_TOL_MM
    res["all_pass"] = all(r.get("pass") for r in res["components"].values()) and not res["missing"]
    return res


def _roundtrip_child(step_path, brep_dir, names):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Shape
    got = read_step(step_path)
    out, missing = {}, []
    for nm in names:
        if nm not in got:
            missing.append(nm)
            continue
        a = TopoDS_Shape()
        BRepTools.Read_s(a, f"{brep_dir}/{nm}.brep", BRep_Builder())
        out[nm] = compare_shapes(a, got[nm])
    return {"components": out, "missing": missing, "read_names": sorted(got)}


# ------------------------------------------------------------------------------------------------ GLB
def glb(components, extras_doc=None, linear=0.4, angular=0.3):
    """components: [{"id", "name", "shape", "colour", "parent", "extras"}]; groups: {"id", "name", "group": True}.
    Returns GLB bytes: one node per component (child nodes under their group), metres, Y up; vertex normals from the
    B-rep surfaces; sharp B-rep edges as a LINES primitive."""
    buf = bytearray()
    views, accs, meshes, nodes, mats = [], [], [], [], []

    def add(arr, target, comp, typ, minmax=False):
        a = np.ascontiguousarray(arr)
        while len(buf) % 4:
            buf.append(0)
        views.append({"buffer": 0, "byteOffset": len(buf), "byteLength": a.nbytes, **({"target": target} if target else {})})
        buf.extend(a.tobytes())
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": int(len(a)), "type": typ}
        if minmax:
            acc["min"], acc["max"] = a.min(0).tolist(), a.max(0).tolist()
        accs.append(acc)
        return len(accs) - 1

    conv = lambda P: (np.c_[P[:, 0], P[:, 2], -P[:, 1]] / 1000.0).astype(np.float32)
    idx = {}
    for c in components:
        node = {"name": c["name"] if not c.get("group") else c["name"], "extras": c.get("extras", {})}
        if not c.get("group"):
            V, F, N, _ = T.mesh(c["shape"], linear, angular)
            E = T.edges(c["shape"])
            pos = add(conv(V), 34962, 5126, "VEC3", True)
            nrm = add(np.c_[N[:, 0], N[:, 2], -N[:, 1]].astype(np.float32), 34962, 5126, "VEC3")
            ind = add(F.astype(np.uint32).ravel(), 34963, 5125, "SCALAR")
            mats.append({"name": c["id"], "pbrMetallicRoughness": {"baseColorFactor": _rgb(c.get("colour")) + [1.0],
                                                                   "metallicFactor": 0.35 if c.get("material") == "metal" else 0.1,
                                                                   "roughnessFactor": 0.85 if c.get("material") == "rubber" else 0.35}})
            fm = c.get("face_materials")
            base_mi = len(mats) - 1
            if fm:                                          # one primitive per material group (glass, lights, paint)
                from cad.pipeline import MATERIALS
                _, _, _, fid = T.mesh(c["shape"], linear, angular)
                tri_mat = np.array([fm[i] or "" for i in fid])
                prims = []
                for m in sorted(set(tri_mat)):
                    sel = F[tri_mat == m]
                    mi = base_mi
                    if m:
                        mats.append({"name": f"{c['id']} {m}", "pbrMetallicRoughness": {
                            "baseColorFactor": _rgb(MATERIALS[m]) + [1.0], "metallicFactor": 0.0 if m == "glass" else 0.05,
                            "roughnessFactor": 0.08 if m == "glass" else 0.3}})
                        mi = len(mats) - 1
                    prims.append({"attributes": {"POSITION": pos, "NORMAL": nrm},
                                  "indices": add(sel.astype(np.uint32).ravel(), 34963, 5125, "SCALAR"), "material": mi})
            else:
                prims = [{"attributes": {"POSITION": pos, "NORMAL": nrm}, "indices": ind, "material": len(mats) - 1}]
            if len(E):
                ep = add(conv(E.reshape(-1, 3)), 34962, 5126, "VEC3", True)
                mats.append({"name": c["id"] + " edges", "pbrMetallicRoughness": {"baseColorFactor": [0.08, 0.1, 0.13, 1.0],
                                                                                  "metallicFactor": 0, "roughnessFactor": 1}})
                prims.append({"attributes": {"POSITION": ep}, "mode": 1, "material": len(mats) - 1})
            meshes.append({"name": c["id"], "primitives": prims})
            node["mesh"] = len(meshes) - 1
        idx[c["id"]] = len(nodes)
        nodes.append(node)
    roots = []
    for c in components:
        par = c.get("parent")
        if par and par in idx:
            nodes[idx[par]].setdefault("children", []).append(idx[c["id"]])
        else:
            roots.append(idx[c["id"]])
    doc = {"asset": {"version": "2.0", "generator": "AETHER Lab CAD (tessellated from the validated OpenCascade B-rep; "
                                                     "the .aethercad document and STEP are authoritative)"},
           "scene": 0, "scenes": [{"nodes": roots, "extras": extras_doc or {}}], "nodes": nodes, "meshes": meshes,
           "materials": mats, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(buf)}]}
    js = json.dumps(doc, separators=(",", ":"), default=str).encode()
    js += b" " * (-len(js) % 4)
    while len(buf) % 4:
        buf.append(0)
    body = struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(buf), b"BIN\x00") + bytes(buf)
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body
