"""AI-planned CAD: a drawing in, an OpenCascade model out, with the model planned and WRITTEN by Meta's model.

No object-specific rules. For any sheet (a car, a machine, a part):

1. measure (code, no model): cad/observations.py finds the views and their silhouettes on the ink; their outlines become
   numeric profiles the CAD program can call (side_top(u), side_bottom(u), half_width(u), end_half_width(view, h)).
2. plan + write (Muse): the model reads the sheet and the profiles, plans the parts, and writes a CadQuery program
   (OpenCascade) that builds every part as a named, coloured solid.
3. run (sandbox): the program runs in a separate process: only `cq`, `math` and the measured profiles are in scope,
   the syntax tree is checked first (no import, no file or network access, no dunder access, no exec/eval/open), a
   time limit applies. Every part must be a valid OpenCascade solid (BRepCheck).
4. check (code): the model's silhouette in every view is compared with the drawing's (IoU per view, mirror images
   tried); overlay images show red = drawn but not built, magenta = built but not drawn.
5. revise (Muse): the model sees the overlays, the scores and any error, and rewrites the program. The round with
   the best checked score is kept (code decides, not the model's confidence).

Outputs (out_dir): program.py (the CAD program itself: editable, rerunnable), model.step, model.glb, report.json,
check_<view>.png per round.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw

from . import ai as AI

VIEWS = ("side", "top", "end_a", "end_b")
N_PROFILE = 41

# ------------------------------------------------------------------------------------------------ 1. measure


def measure(sheet):
    """The sheet's views and their silhouettes as normalised profiles (fractions of the side view's length L).
    u = 0 is the LEFT end of the side view as drawn; heights are measured up from the view's lowest ink."""
    from . import observations as O
    obs, aux = O.observe(sheet)
    sils = {v: np.asarray(aux["sils"][v]) for v in VIEWS if v in aux["sils"]}
    masks, prof = {}, {}
    for v, m in sils.items():
        ys, xs = np.nonzero(m)
        masks[v] = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    L = masks["side"].shape[1]                                 # px: the side view's length is the unit
    s = masks["side"]
    u = np.linspace(0, 1, N_PROFILE)
    cols = np.clip((u * (s.shape[1] - 1)).round().astype(int), 0, s.shape[1] - 1)
    top, bot = [], []
    for c in cols:
        r = np.nonzero(s[:, c])[0]
        top.append((s.shape[0] - r.min()) / L if len(r) else 0.0)
        bot.append((s.shape[0] - 1 - r.max()) / L if len(r) else 0.0)
    prof["side_top"], prof["side_bottom"] = top, bot
    t = masks["top"]
    kt = L / t.shape[1]                                        # plan drawn at its own scale: its length = L
    cols = np.clip((u * (t.shape[1] - 1)).round().astype(int), 0, t.shape[1] - 1)
    prof["half_width"] = [float(np.ptp(np.nonzero(t[:, c])[0]) + 1) * kt / 2 / L if t[:, c].any() else 0.0 for c in cols]
    ks = s.shape[0]                                            # end views scaled to the side view's height
    for v in ("end_a", "end_b"):
        if v not in masks:
            continue
        e = masks[v]
        k = ks / e.shape[0]
        hs = np.linspace(0, 1, 21)
        rows = np.clip(((1 - hs) * (e.shape[0] - 1)).round().astype(int), 0, e.shape[0] - 1)
        prof[v] = [float(np.ptp(np.nonzero(e[r, :])[0]) + 1) * k / 2 / L if e[r, :].any() else 0.0 for r in rows]
    dims = {"length": 1.0, "height": s.shape[0] / L, "width": t.shape[0] * kt / L}
    return {"profiles": prof, "dims": dims, "masks": masks, "obs": obs}


# ------------------------------------------------------------------------------------------------ 3. sandbox

ALLOWED_CALL_NAMES = {"range", "len", "min", "max", "abs", "float", "int", "list", "dict", "tuple", "enumerate", "zip",
                      "sorted", "sum", "round", "isinstance", "reversed", "any", "all", "map", "filter", "print", "pow",
                      "ValueError", "Exception", "bool", "str", "set", "hasattr", "TypeError", "RuntimeError"}
BANNED_NAMES = {"open", "exec", "eval", "compile", "__import__", "getattr", "setattr", "delattr", "globals", "locals",
                "vars", "input", "breakpoint", "help", "exit", "quit", "memoryview", "type", "object", "super",
                "classmethod", "staticmethod", "property"}


def strip_fence(code):
    """A program sometimes arrives wrapped in a Markdown fence (```python ... ```): keep only the source."""
    t = code.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    lines = t.splitlines()                            # prose before the program ("plan: ..."): drop it until it parses
    for k in range(min(30, len(lines))):
        try:
            ast.parse("\n".join(lines[k:]))
            return "\n".join(lines[k:])
        except SyntaxError:
            continue
    return t


def check_program(code):
    """Static safety check of a model-written program: no import, no dunder, no banned builtin. Raises ValueError."""
    tree = ast.parse(code)
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            raise ValueError(f"line {n.lineno}: import is not allowed (cq and math are already available)")
        if isinstance(n, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
            raise ValueError(f"line {n.lineno}: {type(n).__name__} is not allowed")
        if isinstance(n, ast.Attribute) and n.attr.startswith("_"):
            raise ValueError(f"line {n.lineno}: attribute '{n.attr}' is not allowed")
        if isinstance(n, ast.Name) and (n.id.startswith("__") or n.id in BANNED_NAMES):
            raise ValueError(f"line {n.lineno}: name '{n.id}' is not allowed")
    return True


CHILD = r'''
import json, math, sys, traceback
import numpy as np
import cadquery as cq
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepTools import BRepTools
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
job = json.load(open(sys.argv[1], encoding="utf-8"))
sys.path.insert(0, job["lab_root"])
from cad import sandbox_lib as SL
# a common slip: Workplane has union / cut / intersect; .fuse is the Shape name for union. Accept both.
if not hasattr(cq.Workplane, "fuse"):
    cq.Workplane.fuse = lambda self, *o, **k: self.union(*o, **k)
if not hasattr(cq.Workplane, "wrapped"):        # .wrapped is the Shape's OCP handle; on a Workplane, its first solid's
    cq.Workplane.wrapped = property(lambda self: self.val().wrapped)
P = job["profiles"]; Lmm = float(job["length_mm"]); U = np.linspace(0, 1, len(P.get("side_top") or [0, 0]))
def _f(key):
    if key not in P:
        def none(u):
            raise ValueError(f"{key}() needs a drawing; there is none for this model")
        return none
    arr = np.asarray(P[key], float) * Lmm
    return lambda u: float(np.interp(min(max(float(u), 0.0), 1.0), U, arr))
side_top, side_bottom, half_width = _f("side_top"), _f("side_bottom"), _f("half_width")
def end_half_width(view, h):
    """half-width (mm) of end view 'end_a' or 'end_b' at height h (mm above its lowest point)"""
    arr = np.asarray(P[view], float) * Lmm
    H = float(job["dims"]["height"]) * Lmm
    return float(np.interp(min(max(float(h) / H, 0.0), 1.0), np.linspace(0, 1, len(arr)), arr))
SAFE = {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k) for k in job["allowed"]}
g = {"__builtins__": SAFE, "cq": cq, "math": math, "LENGTH": Lmm, "WIDTH": float(job["dims"]["width"]) * Lmm,
     "HEIGHT": float(job["dims"]["height"]) * Lmm, "side_top": side_top, "side_bottom": side_bottom,
     "half_width": half_width, "end_half_width": end_half_width, **SL.NAMES}
OVR = job.get("overrides") or {}
USED = set()
def P(name):
    """a named parameter of the program: the user's override if there is one, else PARAMS[name]['value']"""
    USED.add(name)
    if name in OVR:
        return float(OVR[name])
    t = g.get("PARAMS") or {}
    if name not in t:
        raise KeyError(f"P('{name}'): no such parameter in PARAMS")
    return float(t[name]["value"] if isinstance(t[name], dict) else t[name])
g["P"] = P
out = {"parts": [], "error": None}
try:
    exec(compile(open(job["program"], encoding="utf-8").read(), "program.py", "exec"), g)
    parts = g.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("the program must define `parts`: a non-empty list of dicts {name, shape, colour, material}")
    for i, p in enumerate(parts):
        sh = p["shape"]
        if isinstance(sh, cq.Workplane):
            vals = [v for v in sh.vals() if isinstance(v, cq.Shape)]
            sh = vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)
        w = sh.wrapped
        ok = bool(BRepCheck_Analyzer(w).IsValid())
        repaired = False
        if not ok:                                       # OpenCascade's own shape repair before the part is given up
            from OCP.ShapeFix import ShapeFix_Shape
            fx = ShapeFix_Shape(w)
            fx.Perform()
            if BRepCheck_Analyzer(fx.Shape()).IsValid():
                w, ok, repaired = fx.Shape(), True, True
        gp = GProp_GProps(); BRepGProp.VolumeProperties_s(w, gp)
        f = f"{job['out']}/part_{i:02d}.brep"
        BRepTools.Write_s(w, f)
        out["parts"].append({"name": str(p.get("name", f"part {i}"))[:60], "colour": str(p.get("colour", "#b9c3cf"))[:9],
                             "material": str(p.get("material", "paint"))[:20], "brep": f, "valid": ok, "repaired": repaired,
                             "volume_mm3": float(gp.Mass())})
except Exception as e:
    tb = traceback.format_exc().strip().splitlines()
    out["error"] = "\n".join([l for l in tb if "program.py" in l][-3:] + tb[-1:])[:1500]
def _param_table():
    t = g.get("PARAMS") or {}
    rows = {}
    for k, v in (t.items() if isinstance(t, dict) else []):
        v = v if isinstance(v, dict) else {"value": v}
        try:
            val = float(OVR.get(k, v.get("value")))
        except (TypeError, ValueError):
            continue
        rows[str(k)[:60]] = {"value": val, "unit": str(v.get("unit", "mm"))[:10],
                             "provenance": "user" if k in OVR else str(v.get("provenance", "assumed"))[:20],
                             "evidence": str(v.get("evidence", ""))[:200], "used": k in USED}
    return rows
out["params"] = _param_table()
json.dump(out, open(job["result"], "w", encoding="utf-8"))
'''


def run_program(code, meas, length_mm, out_dir, timeout=420, overrides=None):
    """Run a checked program in a separate process. Returns {"parts": [...], "error": str|None, "seconds"}."""
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    code = strip_fence(code)
    try:
        check_program(code)
    except (ValueError, SyntaxError) as e:
        return {"parts": [], "error": f"rejected before running: {e}. The `code` field must be plain Python source "
                                      "(no Markdown fences, no prose)", "seconds": 0.0}
    prog = os.path.join(out_dir, "program.py")
    open(prog, "w", encoding="utf-8").write(code)
    child = os.path.join(out_dir, "_child.py")
    open(child, "w", encoding="utf-8").write(CHILD)
    job = os.path.join(out_dir, "_job.json")
    res = os.path.join(out_dir, "_result.json")
    json.dump({"lab_root": os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
               "profiles": meas["profiles"], "dims": meas["dims"], "length_mm": length_mm, "program": prog,
               "out": out_dir.replace("\\", "/"), "result": res, "allowed": sorted(ALLOWED_CALL_NAMES),
               "overrides": overrides or {}},
              open(job, "w", encoding="utf-8"))
    t0 = time.time()
    if os.path.exists(res):
        os.remove(res)
    try:
        cp = subprocess.run([sys.executable, child, job], cwd=out_dir, timeout=timeout, capture_output=True, text=True,
                            env={k: v for k, v in os.environ.items() if k not in ("META_API",)})
    except subprocess.TimeoutExpired:
        return {"parts": [], "error": f"the program ran longer than {timeout} s and was stopped", "seconds": timeout}
    try:
        r = json.load(open(res, encoding="utf-8"))
    except (OSError, ValueError):
        r = {"parts": [], "error": "the program crashed (the CAD kernel stopped): " + (cp.stderr or "")[-800:]}
    r["seconds"] = round(time.time() - t0, 1)
    return r


# ------------------------------------------------------------------------------------------------ 4. check


def load_parts(r):
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS_Shape
    out = []
    for p in r["parts"]:
        sh = TopoDS_Shape()
        BRepTools.Read_s(sh, p["brep"], BRep_Builder())
        out.append({**p, "shape": sh})
    return out


def _meshes(parts):
    from . import tessellate as T
    return [T.mesh(p["shape"], 2.0, 0.5)[:2] for p in parts]


AXES2 = {"side": (0, 2), "top": (0, 1), "end_a": (1, 2), "end_b": (1, 2)}


def model_masks(parts, shapes, k=None, meshes=None):
    """Silhouettes of the parts (model frame: x length, y width, z up) on canvases the size of the drawing's views.
    k = None: each view stretched to fill its canvas (shape only: the old, lenient score). k = px per mm: ONE scale for
    every view, the model centred on the canvas, nothing stretched (shape AND proportions)."""
    meshes = meshes or _meshes(parts)
    allV = np.vstack([V for V, _ in meshes if len(V)])
    out = {}
    for v, (h, w) in shapes.items():
        a, b = AXES2[v]
        lo, hi = allV[:, [a, b]].min(0), allV[:, [a, b]].max(0)
        if k is None:
            sx, sy = (w - 1) / max(hi[0] - lo[0], 1e-9), (h - 1) / max(hi[1] - lo[1], 1e-9)
            ox, oy = 0.0, 0.0
        else:
            sx = sy = k
            ox, oy = (w - 1 - (hi[0] - lo[0]) * k) / 2, (h - 1 - (hi[1] - lo[1]) * k) / 2
        im = Image.new("1", (w, h))
        dr = ImageDraw.Draw(im)
        for V, F in meshes:
            if not len(V):
                continue
            P = V[:, [a, b]]
            px = (P[:, 0] - lo[0]) * sx + ox
            py = (hi[1] - P[:, 1]) * sy + oy
            for t in F:
                dr.polygon([(px[i], py[i]) for i in t], fill=1)
        out[v] = np.asarray(im, bool)
    return out, allV.max(0) - allV.min(0)


def _best_iou(d, m):
    best, bm = -1.0, m
    for fx in (False, True):
        for fy in (False, True):
            q_ = m[:, ::-1] if fx else m
            q_ = q_[::-1, :] if fy else q_
            q = float((d & q_).sum() / max((d | q_).sum(), 1))
            if q > best:
                best, bm = q, q_
    return best, bm


def score(parts, meas, out_dir, tag):
    """Agreement with the drawing, three ways (mirror images tried: the drawing does not say which way the model faces):
    - iou: silhouette IoU per view with ONE scale for all views (px per mm from the side view's length), the model only
      centred, never stretched: shape and proportions together. This is the score that decides.
    - iou_shape: each view stretched to its drawing box (shape only; the earlier, lenient score), for reference.
    - proportions: height / length and width / length of the model vs the drawing, error in %.
    Returns (iou, overlay images, extra)."""
    dm = meas["masks"]
    meshes = _meshes(parts)
    fit, ext = model_masks(parts, {v: m.shape for v, m in dm.items()}, None, meshes)
    k = (dm["side"].shape[1] - 1) / max(float(ext[0]), 1e-9)          # the side view's length fixes the one scale
    one, _ = model_masks(parts, {v: m.shape for v, m in dm.items()}, k, meshes)
    res, shape_only, imgs = {}, {}, {}
    for v, d in dm.items():
        q, bm = _best_iou(d, one[v])
        res[v] = round(q, 4)
        shape_only[v] = round(_best_iou(d, fit[v])[0], 4)
        rgb = np.full(d.shape + (3,), 255, np.uint8)
        rgb[d & bm] = (190, 200, 210)
        rgb[d & ~bm] = (220, 50, 50)
        rgb[~d & bm] = (230, 80, 220)
        f = os.path.join(out_dir, f"check_{tag}_{v}.png")
        Image.fromarray(rgb).save(f)
        imgs[v] = f
    L, W, H = (float(x) for x in ext)
    dh = dm["side"].shape[0] / dm["side"].shape[1]
    dw = meas["dims"]["width"] / meas["dims"]["length"]
    prop = {"height_to_length_pct": round(100 * abs(H / L - dh) / dh, 1), "width_to_length_pct": round(100 * abs(W / L - dw) / dw, 1)}
    return res, imgs, {"iou_shape": shape_only, "proportion_error": prop}


# ------------------------------------------------------------------------------------------------ 2 + 5. plan, write, revise

PROMPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def _prompt(name):
    """The instruction files (prompts/*.md): the quality bar the model works to, editable without touching code."""
    with open(os.path.join(PROMPTS, name), encoding="utf-8") as f:
        return f.read()


PLAN_SCHEMA = {"type": "object", "additionalProperties": False,
               "required": ["object", "length_mm", "faces", "components", "constraints", "unknowns"],
               "properties": {"object": {"type": "string", "maxLength": 160},
                              "length_mm": {"type": "number", "minimum": 5, "maximum": 50000},
                              "faces": {"type": "string", "maxLength": 400},
                              "constraints": {"type": "array", "maxItems": 80, "items": {
                                  "type": "object", "additionalProperties": False, "required": ["type", "a", "b", "value"],
                                  "properties": {"type": {"type": "string", "enum": ["coaxial", "contact", "clearance", "meshes"]},
                                                 "a": {"type": "string", "maxLength": 60},
                                                 "b": {"type": "string", "maxLength": 60},
                                                 "value": {"type": "number", "minimum": 0, "maximum": 1000}}}},
                              "unknowns": {"type": "array", "maxItems": 30, "items": {
                                  "type": "object", "additionalProperties": False,
                                  "required": ["what", "why", "would_resolve", "critical"],
                                  "properties": {"what": {"type": "string", "maxLength": 160},
                                                 "why": {"type": "string", "maxLength": 240},
                                                 "would_resolve": {"type": "string", "maxLength": 200},
                                                 "critical": {"type": "boolean"}}}},
                              "components": {"type": "array", "maxItems": 260, "items": {
                                  "type": "object", "additionalProperties": False,
                                  "required": ["name", "parent", "joint", "evidence", "material", "colour", "method"],
                                  "properties": {"name": {"type": "string", "maxLength": 60},
                                                 "parent": {"type": "string", "maxLength": 60},
                                                 "joint": {"type": "string", "enum": ["fixed", "rotates", "slides",
                                                                                      "clearance", "root"]},
                                                 "evidence": {"type": "string", "maxLength": 120},
                                                 "material": {"type": "string", "enum": ["paint", "glass", "chrome", "metal",
                                                                                         "rubber", "plastic", "light", "leather"]},
                                                 "colour": {"type": "string", "maxLength": 9},
                                                 "method": {"type": "string", "maxLength": 200}}}}}}

CODE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["object", "plan", "length_mm", "code"],
               "properties": {"object": {"type": "string", "maxLength": 160},
                              "plan": {"type": "string", "maxLength": 3000},
                              "length_mm": {"type": "number", "minimum": 5, "maximum": 50000},
                              "code": {"type": "string", "maxLength": 90000}}}

_SCORE = {"type": "number", "minimum": 0, "maximum": 10}
CRITIC_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["scores", "overall", "defects"],
                 "properties": {"scores": {"type": "object", "additionalProperties": False,
                                           "required": ["fidelity", "assembly", "surfaces", "detail", "materials", "integrity"],
                                           "properties": {k: _SCORE for k in ("fidelity", "assembly", "surfaces", "detail",
                                                                              "materials", "integrity")}},
                                "overall": _SCORE,
                                "defects": {"type": "array", "maxItems": 12, "items": {
                                    "type": "object", "additionalProperties": False, "required": ["part", "problem", "fix"],
                                    "properties": {"part": {"type": "string", "maxLength": 80},
                                                   "problem": {"type": "string", "maxLength": 300},
                                                   "fix": {"type": "string", "maxLength": 300}}}}}}

PROGRAM_API = """THE PROGRAM (it is checked, then run in a sandbox):
- `cq` (cadquery) and `math` are available. Do NOT import anything. No file access, no names starting with _.
  The `code` field is plain Python source only: no Markdown fences, no prose.
- Define `parts`: a list of dicts {"name": str, "shape": a cq.Workplane or cq.Shape holding ONE closed solid,
  "colour": "#rrggbb", "material": paint | glass | chrome | metal | rubber | plastic | light | leather}.
  Use the component names of the plan EXACTLY (one part per component; split a component into several parts only
  by suffixing its name, e.g. "door_left.glass").
- Units mm. Frame: X along the object's length from its FRONT end (x = 0) to its rear (x = LENGTH); Y across
  (y = 0 the symmetry plane); Z up from the ground (z = 0).
- PARAMETERS WITH EVIDENCE: start the program with
    PARAMS = {"name": {"value": number, "unit": "mm" | "deg" | "count", "provenance": "measured" | "read" |
              "inferred" | "assumed", "evidence": "where it comes from"}, ...}
  for every key dimension of the object (overall sizes, wheelbase / pitch / centre distances, diameters, wall and
  panel thicknesses, clearances, counts). measured = from the measured outline functions, read = a dimension written
  on the drawing, inferred = engineering reasoning from what is drawn, assumed = a default because nothing shows it.
  The geometry reads them with P("name") (never repeats the number), so an engineer can correct one value and the
  whole model recomputes.
- Building blocks you can call (general CAD operations; read their behaviour here):
  smooth_loft(sections, axis="x"): sections [(t, [(a, b), ...]), ...] closed loops across the axis -> smooth solid.
  split_panels(body, lines, gap=3.5): lines [(view, [(a, b), ...]), ...] with view "side" (x, z) | "top" (x, y) |
    "front" (y, z) -> list of panels with real shut lines, sorted by centre x then z. Name each panel.
  recess(body, view, outline, depth, from_side="min") -> (body_with_opening, floor): an opening `depth` mm deep cut
    into the outer surface seen in that view ("front": (y, z) from the front, "side": (x, z) from the -y side unless
    from_side="max", "top": (x, y) from below unless "max"); put the housing / lens / plate at `floor`.
  revolve_profile(points_rh, axis_origin, axis_dir): closed profile [(r, h), ...] revolved 360 deg (tyres, rims, knobs).
  sweep_tube(points3d, r): a round tube along a smooth curve (frames, belts, arms, pipes).
  fillet_safe(obj, r, selector=None): round edges; returns the input unchanged if the kernel cannot.
"""

MEASURED_API = """MEASURED data from the drawing are functions in the program (mm; use them, do not guess what they give):
  LENGTH, WIDTH, HEIGHT; side_top(u), side_bottom(u): the side view's upper / lower outline at u = x / LENGTH measured
  from the LEFT end of the side view AS DRAWN (if the drawn front is on the right, use u = 1 - x / LENGTH);
  half_width(u): the plan view's half-width at the same u; end_half_width("end_a" | "end_b", h): an end view's
  half-width at height h.
"""



# the full instruction text for a drawing / no drawing (the engineer file + the program's interface)
RULES = _prompt("cad_engineer.md") + "\n" + PROGRAM_API + "\n" + MEASURED_API
RULES_NO_DRAWING = _prompt("cad_engineer.md") + "\n" + PROGRAM_API


def _prof_text(meas):
    p = meas["profiles"]
    rows = [f"u={u:.3f}: side_top {a:.4f}  side_bottom {b:.4f}  half_width {c:.4f}"
            for u, a, b, c in zip(np.linspace(0, 1, N_PROFILE), p["side_top"], p["side_bottom"], p["half_width"])][::2]
    ends = "\n".join(f"{v} half-width at h/H = 0, .05 .. 1: " + " ".join(f"{x:.4f}" for x in p[v]) for v in ("end_a", "end_b") if v in p)
    d = meas["dims"]
    return (f"Measured outline (fractions of the length L; the functions in the program return mm):\n"
            f"height/L = {d['height']:.4f}, width/L = {d['width']:.4f}\n" + "\n".join(rows) + "\n" + ends)


def _image(path_or_im, max_side=1280):
    im = Image.open(path_or_im) if isinstance(path_or_im, str) else path_or_im
    return {"type": "image_url", "image_url": {"url": AI._img_url(im, max_side=max_side)}}


def render(parts, path, size=(960, 540), view="iso"):
    """A shaded picture of the parts (flat Lambert shading, painter's order) for the model's own review: silhouettes
    cannot show detail (seats, a steering wheel), a picture can. Model frame: x length, y width, z up."""
    from . import tessellate as T
    W, H = size
    d = {"iso": np.array([-0.62, -0.62, 0.48]), "rear_iso": np.array([0.62, 0.62, 0.5]),
         "top": np.array([0.0, -0.05, 1.0]), "side": np.array([0.0, -1.0, 0.0]),
         "front": np.array([-1.0, 0.0, 0.0])}[view]
    d = d / np.linalg.norm(d)
    up = np.array([0.0, 0.0, 1.0]) if view != "top" else np.array([1.0, 0.0, 0.0])
    r = np.cross(up, d)
    r /= np.linalg.norm(r)
    u = np.cross(d, r)
    light = np.array([-0.3, -0.5, 0.8])
    light /= np.linalg.norm(light)
    tris, cols, depth = [], [], []
    for p in parts:
        V, F, N = T.mesh(p["shape"], 3.0, 0.4)[:3]
        if not len(F):
            continue
        h = (p.get("colour") or "#b9c3cf").lstrip("#")
        try:
            base = np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)
        except ValueError:
            base = np.array([185.0, 195.0, 207.0])
        P = V[F]
        n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        shade = 0.35 + 0.65 * np.abs(n @ light)
        tris.append(P)
        cols.append(np.clip(base[None] * shade[:, None], 0, 255))
        depth.append(P.mean(1) @ d)
    im = Image.new("RGB", size, (11, 18, 32))
    if tris:
        P, Cc, D = np.vstack(tris), np.vstack(cols), np.concatenate(depth)
        X, Y = P @ r, P @ u
        k = 0.9 * min(W / max(np.ptp(X), 1e-9), H / max(np.ptp(Y), 1e-9))
        cx, cy = (X.min() + X.max()) / 2, (Y.min() + Y.max()) / 2
        dr = ImageDraw.Draw(im)
        for i in np.argsort(D):                                      # far first (d points towards the viewer)
            pts = [(W / 2 + (X[i, j] - cx) * k, H / 2 - (Y[i, j] - cy) * k) for j in range(3)]
            dr.polygon(pts, fill=tuple(int(c) for c in Cc[i]))
    im.save(path)
    return path


def _comps(parts):
    return [{"id": f"p{i:03d}_" + "".join(ch if ch.isalnum() else "_" for ch in p["name"])[:40], "name": p["name"],
             "shape": p["shape"], "colour": p.get("colour"), "material": p.get("material"), "parent": None, "extras": {}}
            for i, p in enumerate(parts)]


def review_renders(parts, rdir, tag, log=print):
    """Renders for the critic and the writer: the real viewer (headless Chrome + three.js) when available, the
    built-in software renderer otherwise."""
    from . import export as EX
    from . import render_views as RV
    glb = os.path.join(rdir, "model.glb")
    with open(glb, "wb") as f:
        f.write(EX.glb(_comps(parts)))
    pics = None
    try:
        pics = RV.render(glb, rdir, views=("iso", "iso_rear", "side", "front", "rear", "cockpit"))
    except Exception as e:                                   # noqa: BLE001 - fall back, say so
        log(f"real renders failed ({type(e).__name__}: {e}); software renderer used")
    if not pics:
        pics = {v: render(parts, os.path.join(rdir, f"soft_{tag}_{v}.png"), view=v) for v in ("iso", "rear_iso", "side", "front", "top")}
    return pics


def critique(ai, k, sheet, plan, pics, gate, iou, log=print):
    """The critic (Muse Spark, a separate reviewer from the writer): rubric scores 0-10 and named defects with fixes."""
    content = [{"type": "text", "text": _prompt("cad_critic.md")
                + "\n\nThe component list it was meant to implement: " + ", ".join(c["name"] for c in plan["components"])[:6000]
                + f"\nCode-checked facts: {gate['summary']}. Floating: {gate['floating'][:15]}. Stickers/slivers: "
                  f"{gate['slivers'][:15]}. Box-like: {gate['box_like'][:20]}. Wrong overlaps: {gate['overlaps'][:10]}. "
                  f"Planned but missing: {gate['missing_from_plan'][:20]}."
                + (f" Silhouette IoU per view vs the drawing: {iou}." if iou else "")
                + "\nAnswer with the JSON object only."}]
    if sheet:
        content += [{"type": "text", "text": "The drawing:"}, _image(Image.open(sheet), 1100)]
    for v, f in pics.items():
        content += [{"type": "text", "text": f"Render, view {v}:"}, _image(f, 1000)]
    try:
        ans, _ = ai.ask_json("C2_critic", f"round{k}", AI.SPARK, content, CRITIC_SCHEMA, seed=k, timeout=240)
        return ans
    except AI.ModelUnavailable as e:
        log(f"critic unavailable: {e}")
        return None


def make_plan(ai, model, sheet, meas, measured, why_not, request, base_plan, log=print):
    """C0: the component list (the model's own bill of materials) before any code."""
    text = _prompt("cad_engineer.md") + ("\n\nSTEP 1 of 2: plan the model. List EVERY component you will build (an "
                                         "assembly of real parts, as the instructions above describe), each with its parent "
                                         "(the part it is mounted on; '-' for the root), its joint to the parent (fixed, "
                                         "rotates, slides, clearance = deliberately not touching, root), its evidence (which "
                                         "drawn views show it, or 'estimate'), material, colour and the CAD method "
                                         "(which operation, from which measured outline or estimate). Also say which way the "
                                         "object faces in each drawn view (`faces`) and its real overall length. List "
                                         "the mechanical `constraints` code will verify on your geometry (coaxial: a shaft and its bearing / hub; "
                                         "contact: a part and what it sits on; clearance with its value in mm; meshes: two "
                                         "gears), using component names exactly; value 0 where it has none. List "
                                         "the `unknowns`: what the evidence CANNOT determine (hidden geometry, missing "
                                         "dimensions, ambiguous views), why, what would resolve it (a dimension, another "
                                         "view, a photo), and whether it is critical to the result. Do not hide an "
                                         "unknown behind a confident guess.")
    if request:
        text += "\nThe user asked: " + request
    if measured:
        text += "\n\n" + _prof_text(meas)
    elif sheet:
        text += f"\n\nA drawing is attached; its views could not be measured automatically ({why_not}). Read it yourself."
    if base_plan:
        text += ("\n\nThe CURRENT component list of the model is below. Revise it for what the user asked (add, split, "
                 "refine components; keep what is right):\n" + json.dumps(base_plan["components"])[:30000])
    content = [{"type": "text", "text": text}] + ([_image(Image.open(sheet))] if sheet else [])
    ans, _ = ai.ask_json("C0_plan", "plan", model, content, PLAN_SCHEMA, seed=1, timeout=400, effort="medium")
    log(f"plan: {ans['object']}, {len(ans['components'])} components")
    return ans


def build(sheet, out_dir, request="", rounds=5, model=None, stored=None, ai_mode="live", log=print, target=8.5,
          base_program=None, base_length_mm=None, base_plan=None):
    """The loop for any request: a drawing (sheet), a description (request), or a change to an existing program
    (base_program [+ base_plan] + request).

    C0 plan (Muse Wonder: the component list) -> per round: C1 write the program (Muse Wonder) -> run it in the sandbox
    -> code checks (valid solids, quality gates, coverage of the plan, IoU per view) -> real renders -> C2 critic (Muse
    Spark, rubric) -> feedback for the next round.
    Kept: the valid round with the best critic score that passes the hard gates (no floating parts, no stickers, no
    wrong overlaps) if any round does, and whose mean IoU is within 0.03 of the best checked round's (with a drawing).
    A round that fails never replaces a valid one. Stops early at critic overall >= target with clean gates."""
    from . import export as EX
    from . import quality as Q
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    meas = {"profiles": {}, "dims": {"length": 1.0, "height": 0.0, "width": 0.0}, "masks": {}}
    measured, why_not = False, None
    if sheet:
        try:
            meas, measured = measure(sheet), True
            log(f"measured {len(meas['masks'])} views")
        except Exception as e:                   # any other sheet: the model reads it from the picture, renders check it
            why_not = f"{type(e).__name__}: {e}"[:200]
            log(f"views not measured automatically ({why_not}); the model reads the drawing from the image")
    ai = AI.AI(list(stored or []), ai_mode, log=lambda e: log(f"    {e.get('who', '')} {e['stage']} {e['key']} {e['state']}"
                                                                  + (f" {e.get('s')} s" if e.get("s") else "")))
    model = model or AI.WONDER
    rep = {"sheet": sheet, "measured": measured, "not_measured_why": why_not, "request": request,
           "edit": bool(base_program), "rounds": []}
    try:
        plan = make_plan(ai, model, sheet, meas, measured, why_not, request, base_plan, log)
    except AI.ModelUnavailable as e:
        rep.update(error=f"plan: {e}"[:400], seconds=round(time.time() - t0, 1), hypotheses=ai.store)
        return rep
    rep["plan"] = plan
    names = [c["name"] for c in plan["components"]]
    text = (_prompt("cad_engineer.md") + "\n\n" + PROGRAM_API + ("\n" + MEASURED_API if measured else "")
            + "\nSTEP 2 of 2: write the program that builds EVERY component of this plan (names exactly as listed):\n"
            + json.dumps(plan)[:40000])
    if request:
        text += "\nThe user asked: " + request
    if measured:
        text += "\n\n" + _prof_text(meas)
    elif sheet:
        text += f"\n\nA drawing is attached; its views could not be measured automatically ({why_not}): read sizes from it."
    if base_program:
        text += ("\n\nThe CURRENT program of the model (it built a valid model): revise it to implement the plan, keep "
                 f"what is right. length_mm was {base_length_mm}.\n```python\n{base_program[:40000]}\n```")
    text += "\n\nAnswer with `object`, a short `plan` (what changed / how), `length_mm` and `code`."
    content = [{"type": "text", "text": text}] + ([_image(Image.open(sheet))] if sheet else [])
    valid, best, history = [], None, []
    for k in range(1, rounds + 1):
        msg = content if k == 1 else content + history
        t = time.time()
        try:
            ans, rec = ai.ask_json("C1_cad_program", f"round{k}", model, msg, CODE_SCHEMA, seed=k, timeout=500,
                                   effort="medium")
        except AI.ModelUnavailable as e:
            rep["rounds"].append({"round": k, "error": f"model: {e}"[:400]})
            break
        t_model = round(time.time() - t, 1)
        rdir = os.path.join(out_dir, f"round{k}")
        r = run_program(ans["code"], meas, float(ans["length_mm"]), rdir)
        entry = {"round": k, "model": rec.get("model"), "model_s": t_model, "run_s": r["seconds"],
                 "object": ans["object"], "plan": ans["plan"], "length_mm": ans["length_mm"], "error": r["error"],
                 "parts": [{k2: p[k2] for k2 in ("name", "material", "valid", "volume_mm3")} for p in r["parts"]],
                 "params": r.get("params") or {}}
        if r["error"] is not None:
            log(f"round {k}: error: {r['error'][:200]}")
            fb = [{"type": "text", "text": f"Round {k}: the program failed: {r['error']}\nFix it and answer with the whole "
                                           "revised program."}]
            if best:                                     # do not let errors snowball: show the best working program too
                fb.append({"type": "text", "text": (
                    f"For reference, your best WORKING program so far (round {best['entry']['round']}, critic "
                    f"{(best['entry'].get('critic') or {}).get('overall')}). If the failing change is hard to fix, start "
                    f"again from it and change less at once:\n```python\n{strip_fence(best['code'])[:50000]}\n```")})
        else:
            allp = load_parts(r)
            bad = [p["name"] for p in allp if not p["valid"] or p["volume_mm3"] <= 0]
            parts = [p for p in allp if p["name"] not in bad]        # an invalid part is left out, and reported
            t = time.time()
            gate = Q.gates(parts, names, free={c["name"] for c in plan["components"]
                                              if c.get("joint") in ("rotates", "clearance", "slides", "root")},
                           cons=plan.get("constraints"))
            if bad:
                gate["invalid_left_out"] = bad
                gate["hard_fail"] = True
                gate["summary"] += f"; INVALID solids left out: {len(bad)}"
            iou, imgs, extra = score(parts, meas, out_dir, f"r{k}") if measured else ({}, {}, {})
            pics = review_renders(parts, rdir, f"r{k}", log)
            crit = critique(ai, k, sheet, plan, pics, gate, iou, log)
            entry.update(iou=iou, mean_iou=round(float(np.mean(list(iou.values()))), 4) if iou else None, invalid=bad, **extra,
                         gates=gate, critic=crit, renders=pics, check_s=round(time.time() - t, 1))
            log(f"round {k}: {len(parts)} parts, invalid {len(bad)}, {gate['summary']}, IoU {iou}, critic "
                f"{(crit or {}).get('overall')}")
            if parts:                                    # a candidate: only valid solids; _pick prefers clean rounds
                valid.append({"entry": entry, "parts": parts, "code": ans["code"], "dir": rdir})
                best = _pick(valid)
            fb = [{"type": "text", "text": (
                f"Round {k} result, checked by code: {len(parts)} parts"
                + (f"; INVALID solids (must be fixed): {bad}" if bad else "")
                + f". Quality gates: {gate['summary']}. Floating (must touch what holds them): {gate['floating'][:20]}. "
                  f"Stickers/slivers (must be real parts with depth): {gate['slivers'][:20]}. Box-like parts (replace by "
                  f"real shapes where the object is curved): {gate['box_like'][:30]}. Wrong overlaps (one passes through "
                  f"the other): {gate['overlaps'][:12]}. Planned but missing: {gate['missing_from_plan'][:30]}. "
                  f"Constraints that FAILED on the geometry: {[c for c in gate.get('constraints', []) if not c['ok']][:15]}. "
                  f"PARAMS declared but NOT read by the geometry (a correction to them would change nothing: use P(name) "
                  f"where the value matters, or remove them): {[k for k, v in (r.get('params') or {}).items() if not v.get('used')][:20]}."
                + (f" Silhouette IoU per view vs the drawing, ONE scale for all views (proportions count): {iou}; "
                   f"proportion errors: {extra.get('proportion_error')} (grey = drawn and built, RED = drawn not built, "
                   "MAGENTA = built not drawn)." if iou else "")
                + (f"\nThe critic's scores: {crit['scores']}, overall {crit['overall']}. Its defects, worst first: "
                   + json.dumps(crit["defects"]) if crit else "")
                + "\nFix every defect and every gate failure, keep what is right, and answer with the whole revised program.")}]
            for v, f in imgs.items():
                fb += [{"type": "text", "text": f"{v} overlay:"}, _image(f, 900)]
            for v, f in list(pics.items())[:4]:
                fb += [{"type": "text", "text": f"render {v}:"}, _image(f, 900)]
            rep["rounds"].append(entry)
            if crit and crit["overall"] >= target and not gate["hard_fail"] and k >= 2:
                log(f"round {k}: critic {crit['overall']} >= {target} with clean gates: done")
                history = []
                break
            history = [{"type": "text", "text": f"Your round {k} program:\n```python\n{ans['code'][:60000]}\n```"}] + fb
            continue
        rep["rounds"].append(entry)
        history = [{"type": "text", "text": f"Your round {k} program:\n```python\n{ans['code'][:60000]}\n```"}] + fb
    rep.update(seconds=round(time.time() - t0, 1), hypotheses=ai.store)
    if best:
        comps = _comps(best["parts"])
        open(os.path.join(out_dir, "program.py"), "w", encoding="utf-8").write(strip_fence(best["code"]))
        json.dump(plan, open(os.path.join(out_dir, "plan.json"), "w", encoding="utf-8"), indent=1)
        EX.write_step(comps, os.path.join(out_dir, "model.step"))
        open(os.path.join(out_dir, "model.glb"), "wb").write(EX.glb(comps))
        e = best["entry"]
        par = {c["name"]: c.get("parent") for c in plan["components"]}
        json.dump(e.get("params") or {}, open(os.path.join(out_dir, "params.json"), "w", encoding="utf-8"), indent=1)
        rep["best"] = {"params": e.get("params") or {}, "round": e["round"], "iou": e.get("iou"), "mean_iou": e.get("mean_iou"), "iou_shape": e.get("iou_shape"),
                       "proportion_error": e.get("proportion_error"), "object": e["object"],
                       "length_mm": e["length_mm"], "critic": (e.get("critic") or {}).get("overall"),
                       "critic_scores": (e.get("critic") or {}).get("scores"), "gates": e["gates"]["summary"],
                       "parts": [{"id": c["id"], "name": c["name"], "colour": c["colour"], "material": c["material"],
                                  "brep": p["brep"], "assembly_parent": par.get(c["name"].split(".")[0])}
                                 for c, p in zip(comps, best["parts"])],
                       "program": os.path.join(out_dir, "program.py"), "plan": os.path.join(out_dir, "plan.json")}
    json.dump(rep, open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8"), indent=1, default=str)
    return rep


def rerun(program_dir, out_dir, overrides, sheet=None, length_mm=None, log=print):
    """A parameter correction: the SAME program re-run with the user's values (no model call), checked like a round
    (valid solids, quality gates, IoU with a drawing). Written as a new version only if every solid is valid; the
    previous version is never touched. Returns the report (best = None when the correction broke the model)."""
    from . import export as EX
    from . import quality as Q
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    code = open(os.path.join(program_dir, "program.py"), encoding="utf-8").read()
    old = {}
    if os.path.exists(os.path.join(program_dir, "params.json")):
        old = json.load(open(os.path.join(program_dir, "params.json"), encoding="utf-8"))
    ovr = {**{k: v["value"] for k, v in old.items() if v.get("provenance") == "user"}, **overrides}
    unknown = [k for k in overrides if k not in old]
    if unknown:
        return {"best": None, "error": f"no such parameter: {unknown}; the model has {sorted(old)}"}
    unused = [k for k in overrides if not old[k].get("used", True)]
    if unused:
        return {"best": None, "error": f"the geometry does not read {unused} (declared but unused), so changing it would "
                                       f"change nothing; parameters that drive the geometry: "
                                       f"{sorted(k for k, v in old.items() if v.get('used', True))}. Use edit_cad to make it drive the model."}
    meas = {"profiles": {}, "dims": {"length": 1.0, "height": 0.0, "width": 0.0}, "masks": {}}
    measured = False
    if sheet:
        try:
            meas, measured = measure(sheet), True
        except Exception:
            pass
    r = run_program(code, meas, float(length_mm or 1000.0), os.path.join(out_dir, "run"), overrides=ovr)
    rep = {"overrides": ovr, "error": r["error"], "best": None}
    if r["error"]:
        return rep
    parts = load_parts(r)
    bad = [p["name"] for p in parts if not p["valid"]]
    if bad:
        rep["error"] = f"the corrected values make invalid solids: {bad}; the model is unchanged"
        return rep
    gate = Q.gates(parts)
    iou, _, extra = score(parts, meas, out_dir, "rerun") if measured else ({}, {}, {})
    comps = _comps(parts)
    open(os.path.join(out_dir, "program.py"), "w", encoding="utf-8").write(code)
    for f in ("plan.json",):
        if os.path.exists(os.path.join(program_dir, f)):
            open(os.path.join(out_dir, f), "w", encoding="utf-8").write(open(os.path.join(program_dir, f), encoding="utf-8").read())
    json.dump(r.get("params") or {}, open(os.path.join(out_dir, "params.json"), "w", encoding="utf-8"), indent=1)
    EX.write_step(comps, os.path.join(out_dir, "model.step"))
    open(os.path.join(out_dir, "model.glb"), "wb").write(EX.glb(comps))
    plan = {}
    if os.path.exists(os.path.join(out_dir, "plan.json")):
        plan = json.load(open(os.path.join(out_dir, "plan.json"), encoding="utf-8"))
    par = {c["name"]: c.get("parent") for c in plan.get("components") or []}
    rep["best"] = {"params": r.get("params") or {}, "round": 0, "iou": iou, "mean_iou": round(float(np.mean(list(iou.values()))), 4) if iou else None,
                   **extra, "object": "", "length_mm": length_mm, "gates": gate["summary"],
                   "parts": [{"id": c["id"], "name": c["name"], "colour": c["colour"], "material": c["material"],
                              "brep": p["brep"], "assembly_parent": par.get(c["name"].split(".")[0])} for c, p in zip(comps, parts)],
                   "program": os.path.join(out_dir, "program.py"), "plan": os.path.join(out_dir, "plan.json")}
    json.dump(rep, open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8"), indent=1, default=str)
    return rep


def _pick(valid):
    """Which valid round to keep: clean hard gates first; among those, mean IoU within 0.03 of the best checked IoU
    (with a drawing); then the best critic score (IoU as the tie-break). The model's own confidence never counts."""
    clean = [v for v in valid if not v["entry"]["gates"]["hard_fail"]] or valid
    ious = [v["entry"]["mean_iou"] for v in clean if v["entry"].get("mean_iou") is not None]
    if ious:
        clean = [v for v in clean if v["entry"].get("mean_iou") is None or v["entry"]["mean_iou"] >= max(ious) - 0.03]
    return max(clean, key=lambda v: ((v["entry"].get("critic") or {}).get("overall", -1), v["entry"].get("mean_iou") or 0,
                                     v["entry"]["round"]))


if __name__ == "__main__":
    # python -m cad.codegen <sheet> <out_dir> [rounds]
    import pathlib
    for line in open(pathlib.Path(__file__).resolve().parents[2] / ".env", encoding="utf-8"):
        if "=" in line and not line.strip().startswith("#"):
            k_, v_ = line.strip().split("=", 1)
            os.environ.setdefault(k_.strip(), v_.strip().strip('"'))
    r = build(sys.argv[1], sys.argv[2], rounds=int(sys.argv[3]) if len(sys.argv) > 3 else 5)
    print(json.dumps({k: r[k] for k in ("seconds", "best") if k in r}, indent=1, default=str))
