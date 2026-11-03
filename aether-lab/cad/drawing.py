"""Technical drawing of exact B-rep solids: front, top and right-side views (third-angle layout) with visible edges solid
and hidden edges dashed (OpenCascade hidden-line removal on the tessellated B-rep, HLRBRep_PolyAlgo), the overall
dimensions of each view, and a title block. Written as SVG, PDF and a PNG preview (matplotlib).

The views are projections of the model's own millimetres; nothing is traced or redrawn by hand."""
from __future__ import annotations

import base64
import datetime
import io

import numpy as np
from OCP.BRep import BRep_Builder
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_PolyAlgo, HLRBRep_PolyHLRToShape
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from . import validate as Vd

# view -> (direction the viewer looks from, the drawing's x axis); third-angle projection
VIEWS = {"front": ((0, -1, 0), (1, 0, 0)), "top": ((0, 0, 1), (1, 0, 0)), "right": ((1, 0, 0), (0, 1, 0))}


def compound(shapes):
    c = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(c)
    for s in shapes:
        b.Add(c, s)
    return c


def _polylines(shape, defl):
    out = []
    if shape is None or shape.IsNull():
        return out
    ex = TopExp_Explorer(shape, TopAbs_EDGE)
    while ex.More():
        e = TopoDS.Edge_s(ex.Current())
        try:
            c = BRepAdaptor_Curve(e)
            d = GCPnts_QuasiUniformDeflection(c, defl)
            pts = [d.Value(i) for i in range(1, d.NbPoints() + 1)] if d.IsDone() else \
                [c.Value(c.FirstParameter()), c.Value(c.LastParameter())]
            out.append(np.array([[p.X(), p.Y()] for p in pts]))
        except Exception:
            pass
        ex.Next()
    return out


def project(shape, view, size):
    """-> {"visible": [polyline (n,2)], "hidden": [...]} in the view's own 2D frame (mm)."""
    d, x = VIEWS[view]
    algo = HLRBRep_PolyAlgo()
    algo.Load(shape)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*d), gp_Dir(*x))))
    algo.Update()
    h = HLRBRep_PolyHLRToShape()
    h.Update(algo)
    defl = max(size / 2000, 0.01)
    vis = _polylines(h.VCompound(), defl) + _polylines(h.OutLineVCompound(), defl) + _polylines(h.Rg1LineVCompound(), defl)
    hid = _polylines(h.HCompound(), defl) + _polylines(h.OutLineHCompound(), defl)
    return {"visible": vis, "hidden": hid}


def draw(shapes, title, out_base, notes=()):
    """shapes: exact solids (model mm). Writes out_base.svg / .pdf / .png; returns paths, view extents, PNG data URL."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    shp = compound(shapes)
    bb = np.array(Vd.bbox(shp))
    size = float(np.max(bb[3:] - bb[:3]))
    BRepMesh_IncrementalMesh(shp, max(size / 800, 0.02), False, 0.3, True)
    proj = {v: project(shp, v, size) for v in VIEWS}
    ext = {}
    for v, p in proj.items():
        allp = np.vstack([q for q in p["visible"] + p["hidden"] if len(q)]) if (p["visible"] or p["hidden"]) else np.zeros((1, 2))
        ext[v] = (allp.min(0), allp.max(0))
    W = {v: ext[v][1] - ext[v][0] for v in VIEWS}
    gap = 0.18 * size
    # third angle: front lower-left, top above it, right side to its right
    off = {"front": np.array([0.0, 0.0]),
           "top": np.array([0.0, W["front"][1] + gap]),
           "right": np.array([W["front"][0] + gap, 0.0])}
    fig = plt.figure(figsize=(16.54, 11.69))                    # A3 landscape, inches
    ax = fig.add_axes([0.04, 0.12, 0.92, 0.84])
    ax.set_aspect("equal")
    ax.axis("off")
    tot = np.array([W["front"][0] + gap + W["right"][0], W["front"][1] + gap + W["top"][1]])
    ax.set_xlim(-0.12 * size, tot[0] + 0.05 * size)            # collections do not autoscale the axes
    ax.set_ylim(-0.12 * size, tot[1] + 0.08 * size)
    dim_style = dict(color="#1f4fa0", lw=0.6)
    for v, p in proj.items():
        o = off[v] - ext[v][0]
        # one collection per line style and view (tens of thousands of hidden edges: one artist each took minutes)
        ax.add_collection(LineCollection([q + o for q in p["hidden"] if len(q) > 1], colors="#555", linewidths=0.45,
                                         linestyles=[(0, (4, 2))]))
        ax.add_collection(LineCollection([q + o for q in p["visible"] if len(q) > 1], colors="#111", linewidths=0.8))
        x0, y0 = off[v]
        w, h = W[v]
        t = 0.05 * size
        ax.annotate("", (x0, y0 - t), (x0 + w, y0 - t), arrowprops=dict(arrowstyle="<->", **dim_style))
        ax.text(x0 + w / 2, y0 - t - 0.012 * size, f"{w:.1f}", ha="center", va="top", fontsize=8, color="#1f4fa0")
        ax.annotate("", (x0 - t, y0), (x0 - t, y0 + h), arrowprops=dict(arrowstyle="<->", **dim_style))
        ax.text(x0 - t - 0.012 * size, y0 + h / 2, f"{h:.1f}", ha="right", va="center", rotation=90, fontsize=8, color="#1f4fa0")
        ax.text(x0 + w / 2, y0 + h + 0.03 * size, v.upper() + " VIEW", ha="center", fontsize=9, weight="bold")
    # title block
    tb = fig.add_axes([0.62, 0.015, 0.36, 0.09])
    tb.axis("off")
    tb.add_patch(plt.Rectangle((0, 0), 1, 1, fill=False, lw=1.0, transform=tb.transAxes))
    rows = [("TITLE", title), ("UNITS", "mm (model mm)"), ("PROJECTION", "third angle"),
            ("SOURCE", "AETHER Lab · exact B-rep (OpenCascade), hidden lines dashed"),
            ("DATE", datetime.date.today().isoformat())]
    for i, (k, v) in enumerate(rows):
        y = 1 - (i + 0.5) / len(rows)
        tb.text(0.02, y, k, fontsize=7, color="#666", va="center", transform=tb.transAxes)
        tb.text(0.22, y, v, fontsize=8, va="center", transform=tb.transAxes)
    if notes:
        fig.text(0.04, 0.03, "NOTES: " + "  ".join(notes), fontsize=7, color="#444")
    paths = {}
    for ext_ in ("svg", "pdf", "png"):
        f = f"{out_base}.{ext_}"
        fig.savefig(f, dpi=110 if ext_ == "png" else 300)
        paths[ext_] = f
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=60)
    plt.close(fig)
    return {"svg": paths["svg"], "pdf": paths["pdf"], "png": paths["png"],
            "png_data_url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
            "views": {v: [round(float(W[v][0]), 1), round(float(W[v][1]), 1)] for v in VIEWS},
            "size_mm": (bb[3:] - bb[:3]).round(1).tolist()}
