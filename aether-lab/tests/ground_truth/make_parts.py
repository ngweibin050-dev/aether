"""Ground-truth parts for the CAD reconstruction benchmark: three mechanical parts with KNOWN dimensions, built here in
CadQuery, and their third-angle drawings (cad/drawing.py: hidden lines dashed, overall sizes dimensioned).
AETHER sees only the drawing PNG; tests/ground_truth/score.py compares what it builds with these solids.

    cad-worker/.venv/Scripts/python tests/ground_truth/make_parts.py   -> tests/ground_truth/<part>/{truth.brep, drawing.png, truth.json}

These are synthetic ground truth (a drawing made from a known model), the same kind of check as a CAD model of a known
part drawn on paper: it measures how well the drawing -> CAD step recovers sizes, not how well a scanner or camera works."""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import cadquery as cq                                   # noqa: E402
from OCP.BRepTools import BRepTools                     # noqa: E402

from cad import drawing                                 # noqa: E402


def pillow_block():
    """Bearing housing on a base plate: shaft axis along Y."""
    L, W, T = 140.0, 40.0, 14.0          # base plate
    hole_d, hole_pitch = 12.0, 110.0     # two mounting holes
    ctr_h, od, bore = 42.0, 56.0, 30.0   # shaft centre height, housing OD, bore
    web_w = 70.0
    base = cq.Workplane("XY").box(L, W, T).translate((0, 0, T / 2))
    web = cq.Workplane("XY").box(web_w, W, ctr_h - T).translate((0, 0, T + (ctr_h - T) / 2))
    boss = cq.Workplane("XZ").circle(od / 2).extrude(W / 2, both=True).translate((0, 0, ctr_h))
    body = base.union(web).union(boss)
    body = body.cut(cq.Workplane("XZ").circle(bore / 2).extrude(W, both=True).translate((0, 0, ctr_h)))
    for x in (-hole_pitch / 2, hole_pitch / 2):
        body = body.cut(cq.Workplane("XY").circle(hole_d / 2).extrude(T * 3).translate((x, 0, -T)))
    dims = {"overall_length": L, "overall_width": W, "overall_height": ctr_h + od / 2, "base_thickness": T,
            "mounting_hole_diameter": hole_d, "mounting_hole_spacing": hole_pitch, "shaft_centre_height": ctr_h,
            "housing_outer_diameter": od, "bore_diameter": bore}
    return body.val(), dims, {"diameters": [bore, hole_d, hole_d, od]}


def flanged_hub():
    """Round flange with a hub and a bolt circle: axis along Z."""
    fd, ft = 120.0, 12.0                 # flange
    hd, hh = 60.0, 50.0                  # hub above the flange
    bore = 25.0
    n, bolt_d, pcd = 6, 10.0, 90.0
    body = cq.Workplane("XY").circle(fd / 2).extrude(ft)
    body = body.union(cq.Workplane("XY").circle(hd / 2).extrude(hh).translate((0, 0, ft)))
    body = body.cut(cq.Workplane("XY").circle(bore / 2).extrude(ft + hh + 10).translate((0, 0, -5)))
    for i in range(n):
        a = 2 * math.pi * i / n
        body = body.cut(cq.Workplane("XY").circle(bolt_d / 2).extrude(ft + 10)
                        .translate((pcd / 2 * math.cos(a), pcd / 2 * math.sin(a), -5)))
    dims = {"flange_diameter": fd, "flange_thickness": ft, "hub_diameter": hd, "overall_height": ft + hh,
            "bore_diameter": bore, "bolt_hole_count": n, "bolt_hole_diameter": bolt_d, "bolt_circle_diameter": pcd}
    return body.val(), dims, {"diameters": [fd, hd, bore] + [bolt_d] * n}


def gusset_bracket():
    """L bracket: a base plate and an upright plate joined by a triangular gusset, two holes in each plate."""
    L, D, T, H = 100.0, 60.0, 8.0, 70.0  # length (X), base depth (Y), plate thickness, upright height
    hole_d, hole_pitch = 9.0, 60.0
    base = cq.Workplane("XY").box(L, D, T).translate((0, D / 2, T / 2))
    up = cq.Workplane("XY").box(L, T, H).translate((0, T / 2, H / 2))
    g = (cq.Workplane("YZ").polyline([(T, T), (D - 6, T), (T, H - 6)]).close().extrude(T / 2, both=True))
    body = base.union(up).union(g)
    for x in (-hole_pitch / 2, hole_pitch / 2):
        body = body.cut(cq.Workplane("XY").circle(hole_d / 2).extrude(T * 3).translate((x, D * 0.65, -T)))
        body = body.cut(cq.Workplane("XZ").circle(hole_d / 2).extrude(-T * 3).translate((x, -T, H * 0.65)))
    dims = {"overall_length": L, "base_depth": D, "plate_thickness": T, "overall_height": H,
            "hole_diameter": hole_d, "hole_spacing": hole_pitch}
    return body.val(), dims, {"diameters": [hole_d] * 4}


PARTS = {"pillow_block": (pillow_block, "Pillow block bearing housing"),
         "flanged_hub": (flanged_hub, "Flanged hub"),
         "gusset_bracket": (gusset_bracket, "Gusseted angle bracket")}

if __name__ == "__main__":
    for name, (fn, title) in PARTS.items():
        shape, dims, feats = fn()
        d = os.path.join(HERE, name)
        os.makedirs(d, exist_ok=True)
        BRepTools.Write_s(shape.wrapped, os.path.join(d, "truth.brep"))
        r = drawing.draw([shape.wrapped], title, os.path.join(d, "drawing"), notes=("All dimensions in mm.",))
        json.dump({"title": title, "dims_mm": dims, "features": feats, "volume_mm3": shape.Volume(),
                   "drawing_views_mm": r["views"], "size_mm": r["size_mm"]}, open(os.path.join(d, "truth.json"), "w"), indent=1)
        for f in ("drawing.svg", "drawing.pdf"):
            if os.path.exists(os.path.join(d, f)):
                os.remove(os.path.join(d, f))
        print(name, r["size_mm"], round(shape.Volume()))
