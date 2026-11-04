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


JOINT_WORD = {"root": "base", "fixed": "fixed", "revolute": "turns", "continuous": "turns", "prismatic": "slides",
              "slide": "slides", "hinge": "hinge", "ball": "ball"}


def _centroid(shape):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    c = g.CentreOfMass()
    return np.array([c.X(), c.Y(), c.Z()])


def _item_page(proj, ext, balloons, size, title):
    """The item view: the front view large, a numbered balloon for every part in tidy rows above and below it (sorted
    left to right), each with a leader to the part's centre; the numbers are the parts list's items."""
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    d, xv = VIEWS["front"]
    X, N = np.array(xv, float), np.array(d, float)
    Y = np.cross(N, X)
    lo, hi = ext
    w, h = hi - lo
    pts = []
    for it, shp in balloons:
        try:
            c = _centroid(shp)
        except Exception:
            continue
        pts.append((it, np.array([c @ X, c @ Y]) - lo))
    top = sorted([p for p in pts if p[1][1] >= h / 2], key=lambda p: p[1][0])
    bot = sorted([p for p in pts if p[1][1] < h / 2], key=lambda p: p[1][0])
    r = 0.011 * max(w, h)
    per_row = max(1, int(w / (2.6 * r)))
    rows_t, rows_b = -(-len(top) // per_row), -(-len(bot) // per_row)
    fig = plt.figure(figsize=(16.54, 11.69))
    ax = fig.add_axes([0.03, 0.05, 0.94, 0.86])
    ax.set_aspect("equal")
    ax.axis("off")
    fig.text(0.03, 0.95, f"ITEM VIEW · {title}", fontsize=13, weight="bold")
    fig.text(0.03, 0.935, "front view; every part numbered as in the parts list (next sheet); leaders end at the part's centre",
             fontsize=8, color="#555")
    pad = 3 * r
    ax.set_xlim(-0.05 * w, 1.05 * w)
    ax.set_ylim(-pad - rows_b * 2.6 * r - r, h + pad + rows_t * 2.6 * r + r)
    ax.add_collection(LineCollection([q - lo for q in proj["hidden"] if len(q) > 1], colors="#999", linewidths=0.3,
                                     linestyles=[(0, (4, 2))]))
    ax.add_collection(LineCollection([q - lo for q in proj["visible"] if len(q) > 1], colors="#111", linewidths=0.55))

    def place(group, y0, step):
        for k, (it, p) in enumerate(group):
            row, col = divmod(k, per_row)
            n = min(per_row, len(group) - row * per_row)
            x = (col + 0.5) * w / n
            y = y0 + step * row * 2.6 * r
            ax.plot([p[0], x], [p[1], y - np.sign(step) * r], color="#1f4fa0", lw=0.35)
            ax.add_patch(plt.Circle((x, y), r, fc="white", ec="#1f4fa0", lw=0.6, zorder=5))
            ax.text(x, y, str(it), ha="center", va="center", fontsize=6, color="#1f4fa0", zorder=6)
    place(top, h + pad, 1)
    place(bot, -pad, -1)
    return fig


def _bom_pages(rows, title):
    """The parts list as table pages (A3 landscape, up to 40 rows a page)."""
    import matplotlib.pyplot as plt
    figs = []
    cols = ["ITEM", "PART", "MATERIAL", "MOUNTED ON", "JOINT", "OPERATIONS (from the CAD program's plan)"]
    for k in range(0, max(1, len(rows)), 40):
        fig = plt.figure(figsize=(16.54, 11.69))
        ax = fig.add_axes([0.04, 0.06, 0.92, 0.86])
        ax.axis("off")
        fig.text(0.04, 0.95, f"PARTS LIST · {title}" + (f"  (page {k // 40 + 1})" if len(rows) > 40 else ""), fontsize=13, weight="bold")
        chunk = rows[k:k + 40] or [["-", "-", "-", "-", "-", "-"]]
        t = ax.table(cellText=chunk, colLabels=cols, loc="upper left", cellLoc="left",
                     colWidths=[0.05, 0.2, 0.1, 0.2, 0.08, 0.37])
        t.auto_set_font_size(False)
        t.set_fontsize(8)
        t.scale(1, 1.35)
        for (r, c), cell in t.get_celld().items():
            cell.set_edgecolor("#999")
            if r == 0:
                cell.set_facecolor("#e8eef6")
                cell.set_text_props(weight="bold")
        figs.append(fig)
    return figs


def _connection_page(nodes, title):
    """The connection diagram: a tree from the base outwards, every part a box (item + name), every link to what it
    is mounted on labelled with its joint (from the CAD program's plan)."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    kids = {}
    for n in nodes:
        kids.setdefault(n["parent"] or "", []).append(n)
    pos, row = {}, [0]

    def walk(n, d):
        ch = kids.get(n["name"], [])
        if not ch:
            pos[n["name"]] = (d, row[0])
            row[0] += 1
            return
        for c in ch:
            walk(c, d + 1)
        pos[n["name"]] = (d, (pos[ch[0]["name"]][1] + pos[ch[-1]["name"]][1]) / 2)
    for r in kids.get("", []):
        walk(r, 0)
    depth = max([p[0] for p in pos.values()] + [0])
    rows = max(row[0], 1)
    fig = plt.figure(figsize=(16.54, 11.69))
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.9])
    ax.axis("off")
    fig.text(0.03, 0.95, f"CONNECTION DIAGRAM · {title}", fontsize=13, weight="bold")
    fig.text(0.03, 0.935, "each part is mounted on the part to its left; the label is the joint (from the CAD program's plan)",
             fontsize=8, color="#555")
    W, H = 0.8, 0.6
    ax.set_xlim(-0.2, depth + 1.1)
    ax.set_ylim(rows, -1)
    fs = max(4.0, min(8.0, 260 / rows))
    item = {n["name"]: n["item"] for n in nodes}
    for n in nodes:
        if n["parent"] and n["parent"] in pos and n["name"] in pos:
            (x1, y1), (x2, y2) = pos[n["parent"]], pos[n["name"]]
            mx = x1 + W + (x2 - x1 - W) / 2
            ax.plot([x1 + W, mx, mx, x2], [y1, y1, y2, y2], color="#1f4fa0", lw=0.6)
            ax.text(mx + 0.02, y2 - 0.12, JOINT_WORD.get(n["joint"], n["joint"] or ""), fontsize=fs * 0.8, color="#1f4fa0")
    for name, (x, y) in pos.items():
        ax.add_patch(FancyBboxPatch((x, y - H / 2), W, H, boxstyle="round,pad=0.0,rounding_size=0.05", fc="#f4f7fb", ec="#555", lw=0.5))
        ax.text(x + 0.03, y, f"{item.get(name, '')}", fontsize=fs, va="center", color="#1f4fa0", weight="bold")
        ax.text(x + 0.14, y, name[:24], fontsize=fs, va="center")
    return fig


def draw(shapes, title, out_base, notes=(), balloons=None, bom=None, graph=None):
    """shapes: exact solids (model mm). Writes out_base.svg / .pdf / .png; returns paths, view extents, PNG data URL.
    An assembly drawing when balloons / bom / graph are given: balloons [(item, shape)] numbered on the front view,
    the parts list pages (bom: rows) and the connection diagram page (graph: nodes) added to the PDF."""
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
    for ext_ in ("svg", "png"):
        f = f"{out_base}.{ext_}"
        fig.savefig(f, dpi=110 if ext_ == "png" else 300)
        paths[ext_] = f
    extra = (([_item_page(proj["front"], ext["front"], balloons, size, title)] if balloons else [])
             + (_bom_pages(bom, title) if bom else []) + ([_connection_page(graph, title)] if graph else []))
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(f"{out_base}.pdf") as pdf:                # every sheet in one PDF
        pdf.savefig(fig)
        for i, fx in enumerate(extra):
            pdf.savefig(fx)
            fx.savefig(f"{out_base}_sheet{i + 2}.png", dpi=90)
            plt.close(fx)
    paths["pdf"] = f"{out_base}.pdf"
    paths["sheets"] = [f"{out_base}.png"] + [f"{out_base}_sheet{i + 2}.png" for i in range(len(extra))]
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=60)
    plt.close(fig)
    return {"svg": paths["svg"], "pdf": paths["pdf"], "png": paths["png"], "sheets": paths["sheets"],
            "png_data_url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
            "views": {v: [round(float(W[v][0]), 1), round(float(W[v][1]), 1)] for v in VIEWS},
            "size_mm": (bb[3:] - bb[:3]).round(1).tolist()}
