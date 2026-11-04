"""Score a reconstruction against its ground-truth solid (run in the CAD worker's Python):
    cad-worker/.venv/Scripts/python tests/ground_truth/score.py        -> tests/ground_truth/scores.json + a table

For each part and each result (aether = the full loop's kept round; baseline = one-shot):
- orientation: the result may lie differently, so the best of the 24 axis-aligned rotations is used (by silhouette IoU);
- overall size error per axis (mm) in that orientation;
- feature diameters: every cylinder diameter of the truth (bore, holes, flange...) matched to the nearest one in the
  result, error in mm; distinct holes counted (cylinders grouped by axis and radius);
- volume error (%), parts fused first;
- silhouette IoU of the front / top / side projections at ONE scale (2 px per mm, centred, never stretched);
- parameters: how many the geometry reads (an engineer can correct only those)."""
import itertools
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from OCP.BRep import BRep_Builder  # noqa: E402
from OCP.BRepAdaptor import BRepAdaptor_Surface  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse  # noqa: E402
from OCP.BRepBndLib import BRepBndLib  # noqa: E402
from OCP.BRepGProp import BRepGProp  # noqa: E402
from OCP.BRepTools import BRepTools  # noqa: E402
from OCP.Bnd import Bnd_Box  # noqa: E402
from OCP.GeomAbs import GeomAbs_Cylinder  # noqa: E402
from OCP.GProp import GProp_GProps  # noqa: E402
from OCP.TopAbs import TopAbs_FACE  # noqa: E402
from OCP.TopExp import TopExp_Explorer  # noqa: E402
from OCP.TopoDS import TopoDS, TopoDS_Shape  # noqa: E402

from cad import tessellate as T  # noqa: E402

PX = 2.0                                                    # px per mm


def read(f):
    s = TopoDS_Shape()
    BRepTools.Read_s(s, f, BRep_Builder())
    return s


def fuse(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        f = BRepAlgoAPI_Fuse(out, s)
        if f.IsDone():
            out = f.Shape()
    return out


def volume(s):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(s, g)
    return g.Mass()


def cylinders(s):
    """[(diameter, axis point, axis dir)] of every cylindrical face."""
    out = []
    ex = TopExp_Explorer(s, TopAbs_FACE)
    while ex.More():
        a = BRepAdaptor_Surface(TopoDS.Face_s(ex.Current()))
        if a.GetType() == GeomAbs_Cylinder:
            c = a.Cylinder()
            p, d = c.Location(), c.Axis().Direction()
            out.append((2 * c.Radius(), np.array([p.X(), p.Y(), p.Z()]), np.array([d.X(), d.Y(), d.Z()])))
        ex.Next()
    return out


def holes(cyls, d, tol=0.15):
    """Distinct cylinders of about diameter d (one hole can be split into several faces)."""
    axes = []
    for dia, p, v in cyls:
        if abs(dia - d) > tol * d:
            continue
        v = v / np.linalg.norm(v)
        q = p - v * np.dot(p, v)                           # the axis line's point nearest the origin
        if not any(np.linalg.norm(q - q2) < 0.5 and abs(abs(np.dot(v, v2)) - 1) < 1e-3 for q2, v2 in axes):
            axes.append((q, v))
    return len(axes)


def rotations():
    """The 24 proper rotations that map axes onto axes."""
    out = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            R = np.zeros((3, 3))
            for i, j in enumerate(perm):
                R[i, j] = signs[i]
            if np.linalg.det(R) > 0:
                out.append(R)
    return out


def masks(V, F, size):
    """Front (x, z), top (x, y), side (y, z) silhouettes, centred on the bbox, 1/PX mm per px, canvas `size` mm."""
    c = (V.min(0) + V.max(0)) / 2
    P = (V - c) * PX + size * PX / 2
    out = []
    for a, b in ((0, 2), (0, 1), (1, 2)):
        im = Image.new("1", (int(size * PX), int(size * PX)), 0)
        d = ImageDraw.Draw(im)
        for t in F:
            d.polygon([(P[i, a], P[i, b]) for i in t], fill=1)
        out.append(np.asarray(im, bool))
    return out


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def score(truth_dir, result_breps, params):
    tj = json.load(open(os.path.join(truth_dir, "truth.json")))
    truth = read(os.path.join(truth_dir, "truth.brep"))
    res = fuse([read(f) for f in result_breps])
    Vt, Ft, _, _ = T.mesh(truth, 0.3, 0.3)
    Vr, Fr, _, _ = T.mesh(res, 0.3, 0.3, fast=True)
    size = 1.3 * max(np.ptp(Vt, 0).max(), np.ptp(Vr, 0).max())
    mt = masks(Vt, Ft, size)
    best = None
    for R in rotations():
        m = masks(Vr @ R.T, Fr, size)
        ious = [iou(a, b) for a, b in zip(mt, m)]
        if best is None or np.mean(ious) > np.mean(best[1]):
            best = (R, ious)
    R, ious = best
    ext_t, ext_r = np.ptp(Vt, 0), np.ptp(Vr @ R.T, 0)
    ct, cr = cylinders(truth), cylinders(res)
    rd = sorted(c[0] for c in cr)
    feats = []
    used = set()
    for d in sorted(set(tj["features"]["diameters"]), reverse=True):
        cand = [(abs(x - d), i) for i, x in enumerate(rd) if i not in used]
        if cand:
            e, i = min(cand)
            used.add(i)
            feats.append({"diameter_mm": d, "found_mm": round(rd[i], 2), "error_mm": round(rd[i] - d, 2),
                          "count_truth": holes(ct, d), "count_found": holes(cr, d)})
        else:
            feats.append({"diameter_mm": d, "found_mm": None, "error_mm": None, "count_truth": holes(ct, d), "count_found": 0})
    vt, vr = volume(truth), volume(res)
    ps = [v for v in (params or {}).values() if isinstance(v, dict)]
    return {"size_truth_mm": ext_t.round(1).tolist(), "size_found_mm": ext_r.round(1).tolist(),
            "size_error_mm": (ext_r - ext_t).round(1).tolist(), "max_size_error_mm": round(float(np.abs(ext_r - ext_t).max()), 1),
            "iou_front_top_side": [round(x, 3) for x in ious], "iou_mean": round(float(np.mean(ious)), 3),
            "volume_error_pct": round(100 * (vr - vt) / vt, 1), "features": feats,
            "params_total": len(ps), "params_read": sum(1 for v in ps if v.get("used"))}


def result_breps(part_dir, kind):
    if kind in ("aether", "corrected"):
        rep = json.load(open(os.path.join(part_dir, kind, "report.json"), encoding="utf-8"))
        b = rep.get("best") or {}
        return [p["brep"] for p in b.get("parts") or []], b.get("params"), {
            "round": b.get("round"), "critic": b.get("critic"), "gates": b.get("gates"), "seconds": rep.get("seconds"),
            "rounds": [{"round": r.get("round"), "error": (r.get("error") or "")[:80] or None,
                        "critic": (r.get("critic") or {}).get("overall"), "gates": (r.get("gates") or {}).get("summary")}
                       for r in rep.get("rounds") or []]}
    r = json.load(open(os.path.join(part_dir, kind, "result.json"), encoding="utf-8"))
    return [p["brep"] for p in r.get("parts") or [] if p.get("valid", True)], r.get("params"), {
        "error": r.get("error"), "seconds": r.get("seconds")}


if __name__ == "__main__":
    kinds = ["baseline", "aether"] + [k for k in sys.argv[1:] if k not in ("baseline", "aether")]
    out = {}
    for part in ("pillow_block", "flanged_hub", "gusset_bracket"):
        d = os.path.join(HERE, part)
        for kind in kinds:
            try:
                breps, params, info = result_breps(d, kind)
            except (OSError, ValueError) as e:
                out[f"{part}/{kind}"] = {"missing": str(e)[:120]}
                continue
            if not breps:
                out[f"{part}/{kind}"] = {"no_solid": True, **info}
                continue
            out[f"{part}/{kind}"] = {**score(d, breps, params), **info}
            s = out[f"{part}/{kind}"]
            print(f"{part:15s} {kind:9s} size err {s['size_error_mm']} mm | IoU {s['iou_mean']} | vol {s['volume_error_pct']} % | "
                  f"diam errs {[f['error_mm'] for f in s['features']]} | holes {[(f['count_found'], f['count_truth']) for f in s['features']]} "
                  f"| params read {s['params_read']}/{s['params_total']}", flush=True)
    json.dump(out, open(os.path.join(HERE, "scores.json"), "w"), indent=1, default=str)
