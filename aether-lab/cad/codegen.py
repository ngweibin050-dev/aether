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
                      "ValueError", "Exception", "bool", "str", "set"}
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
     "half_width": half_width, "end_half_width": end_half_width}
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
        gp = GProp_GProps(); BRepGProp.VolumeProperties_s(w, gp)
        f = f"{job['out']}/part_{i:02d}.brep"
        BRepTools.Write_s(w, f)
        out["parts"].append({"name": str(p.get("name", f"part {i}"))[:60], "colour": str(p.get("colour", "#b9c3cf"))[:9],
                             "material": str(p.get("material", "paint"))[:20], "brep": f, "valid": ok,
                             "volume_mm3": float(gp.Mass())})
except Exception as e:
    tb = traceback.format_exc().strip().splitlines()
    out["error"] = "\n".join([l for l in tb if "program.py" in l][-3:] + tb[-1:])[:1500]
json.dump(out, open(job["result"], "w", encoding="utf-8"))
'''


def run_program(code, meas, length_mm, out_dir, timeout=240):
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
    json.dump({"profiles": meas["profiles"], "dims": meas["dims"], "length_mm": length_mm, "program": prog,
               "out": out_dir.replace("\\", "/"), "result": res, "allowed": sorted(ALLOWED_CALL_NAMES)},
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


def model_masks(parts, shapes):
    """Silhouettes of the parts (model frame: x length, y width, z up) at the drawing views' pixel sizes."""
    from . import tessellate as T
    meshes = [T.mesh(p["shape"], 2.0, 0.5)[:2] for p in parts]
    allV = np.vstack([V for V, _ in meshes if len(V)])
    axes = {"side": (0, 2), "top": (0, 1), "end_a": (1, 2), "end_b": (1, 2)}
    out = {}
    for v, (h, w) in shapes.items():
        a, b = axes[v]
        lo, hi = allV[:, [a, b]].min(0), allV[:, [a, b]].max(0)
        im = Image.new("1", (w, h))
        dr = ImageDraw.Draw(im)
        for V, F in meshes:
            if not len(V):
                continue
            P = V[:, [a, b]]
            px = (P[:, 0] - lo[0]) / max(hi[0] - lo[0], 1e-9) * (w - 1)
            py = (hi[1] - P[:, 1]) / max(hi[1] - lo[1], 1e-9) * (h - 1)
            for t in F:
                dr.polygon([(px[i], py[i]) for i in t], fill=1)
        out[v] = np.asarray(im, bool)
    return out


def score(parts, meas, out_dir, tag):
    """IoU per view (mirror images tried, as the drawing does not say which way the model faces) + overlay images."""
    dm = meas["masks"]
    mm = model_masks(parts, {v: m.shape for v, m in dm.items()})
    res, imgs = {}, {}
    for v, d in dm.items():
        best, bm = -1.0, None
        for fx in (False, True):
            for fy in (False, True):
                m = mm[v][:, ::-1] if fx else mm[v]
                m = m[::-1, :] if fy else m
                q = float((d & m).sum() / max((d | m).sum(), 1))
                if q > best:
                    best, bm = q, m
        res[v] = round(best, 4)
        rgb = np.full(d.shape + (3,), 255, np.uint8)
        rgb[d & bm] = (190, 200, 210)
        rgb[d & ~bm] = (220, 50, 50)
        rgb[~d & bm] = (230, 80, 220)
        f = os.path.join(out_dir, f"check_{tag}_{v}.png")
        Image.fromarray(rgb).save(f)
        imgs[v] = f
    return res, imgs


# ------------------------------------------------------------------------------------------------ 2 + 5. plan, write, revise

CODE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["object", "plan", "length_mm", "code"],
               "properties": {"object": {"type": "string", "maxLength": 120},
                              "plan": {"type": "string", "maxLength": 3000},
                              "length_mm": {"type": "number", "minimum": 10, "maximum": 50000},
                              "code": {"type": "string", "maxLength": 60000}}}

RULES = """You are AETHER's CAD engineer. Build the object on this drawing as a CadQuery (OpenCascade) program.

Program rules (it is checked, then run in a sandbox):
- `cq` (cadquery) and `math` are already available. Do NOT import anything. No file access, no names starting with _.
- Define `parts`: a list of dicts {"name": str, "shape": a cq.Workplane or cq.Shape holding ONE closed solid,
  "colour": "#rrggbb", "material": one of paint, glass, chrome, metal, rubber, plastic, light, leather}.
- Units mm. Frame: X along the object's length from its FRONT end (x = 0) to its rear end (x = LENGTH); Y across
  (y = 0 the symmetry plane); Z up from the ground (z = 0).
- MEASURED data from the drawing are given as functions (all in mm, use them, do not guess what they give):
  LENGTH, WIDTH, HEIGHT; side_top(u), side_bottom(u): the side view's upper and lower outline at u = x / LENGTH
  measured from the LEFT end of the side view AS DRAWN (if the drawn front is on the right, use u = 1 - x / LENGTH);
  half_width(u): the plan view's half-width at the same u (plan drawn with the same left/right as the side view);
  end_half_width("end_a" | "end_b", h): an end view's half-width at height h.
- Build the main body from these profiles (e.g. loft through cross-sections whose width and height follow them; keep
  sections convex and well-formed so the loft is valid), then add EVERY visible feature as its own part, at the
  place the drawing shows it: wheels (tyre + rim), windscreen frame and glass, roll bar, seats, steering wheel,
  lights, grille, bumpers, mirrors, exhaust, handles ... whatever THIS drawing shows. Open things stay open (a
  cockpit is a hollow cut into the body, not covered).
- Prefer robust operations: box, cylinder, sphere, extrude, revolve, loft of a few wires, sweep of a circle along a
  spline, union/cut, fillet with small radii only where it is safe. Every part must be a valid solid.

- QUALITY (the model is judged on renders next to the drawing, like a product designer would):
  * Smooth surfaces: build curved bodies by lofting SMOOTH section wires (spline / ellipse / rounded wires, made with
    cq.Workplane(...).spline(...) or .ellipse(...)) with ruled=False, about 8-14 sections; never polyline sections or
    ruled lofts (they show facets). Fillet edges a real object would have rounded (small radii, where safe).
  * Real shapes, not blocks: round things are revolved profiles with rounded edges; thin things (glass, frames, panels)
    are thin and follow the surface they sit on; openings are cut into the parent (a recess, a cavity), not painted on.
  * Everything attached, nothing floating: each part touches or slightly overlaps the part it is mounted on.
  * Sizes and positions come from the measured outlines wherever the drawing shows them; check every part against
    each view (side, top, end views) before answering.
"""

RULES_NO_DRAWING = RULES.split("- MEASURED data")[0].replace("Build the object on this drawing", "Design the object the "
    "user describes") + """- There is no drawing: use real engineering sizes and proportions for this kind of object
  (say in the plan where each comes from). Model every part the real object has, each as its own part.
- Prefer robust operations: box, cylinder, sphere, extrude, revolve, loft of a few wires, sweep of a circle along a
  spline, union/cut, fillet with small radii only where it is safe. Every part must be a valid solid.

- QUALITY (the model is judged on renders next to the drawing, like a product designer would):
  * Smooth surfaces: build curved bodies by lofting SMOOTH section wires (spline / ellipse / rounded wires, made with
    cq.Workplane(...).spline(...) or .ellipse(...)) with ruled=False, about 8-14 sections; never polyline sections or
    ruled lofts (they show facets). Fillet edges a real object would have rounded (small radii, where safe).
  * Real shapes, not blocks: round things are revolved profiles with rounded edges; thin things (glass, frames, panels)
    are thin and follow the surface they sit on; openings are cut into the parent (a recess, a cavity), not painted on.
  * Everything attached, nothing floating: each part touches or slightly overlaps the part it is mounted on.
  * Sizes and positions come from the measured outlines wherever the drawing shows them; check every part against
    each view (side, top, end views) before answering.
"""


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


def build(sheet, out_dir, request="", rounds=5, model=None, stored=None, ai_mode="live", log=print, target=0.95,
          base_program=None, base_length_mm=None):
    """The loop for any request: a drawing (sheet), a description (request), or a change to an existing program
    (base_program + request). Returns the report; writes program.py, model.step, model.glb, report.json.
    Kept: with a drawing, the valid round with the best mean IoU; without one, or when editing, the newest valid round
    (an edit may rightly change the outline). A round that fails never replaces a valid one."""
    from . import export as EX
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    none = {"profiles": {}, "dims": {"length": 1.0, "height": 0.0, "width": 0.0}, "masks": {}}
    measured, why_not = False, None
    meas = none
    if sheet:
        try:                                     # the outlines are measured where the sheet has the 4 standard views
            meas, measured = measure(sheet), True
            log(f"measured {len(meas['masks'])} views")
        except Exception as e:                   # any other sheet: the model reads it from the picture, renders check it
            why_not = f"{type(e).__name__}: {e}"[:200]
            log(f"views not measured automatically ({why_not}); the model reads the drawing from the image")
    ai = AI.AI(list(stored or []), ai_mode, log=lambda e: log(f"    {e.get('who', '')} {e['stage']} {e['key']} {e['state']}"
                                                                  + (f" {e.get('s')} s" if e.get("s") else "")))
    model = model or AI.WONDER
    text = RULES if measured else RULES_NO_DRAWING
    if request:
        text += "\nThe user asked: " + request
    if measured:
        text += "\n\n" + _prof_text(meas)
    elif sheet:
        text += ("\n\nA DRAWING IS ATTACHED, but its views could not be measured automatically (" + str(why_not) + "): the "
                 "profile functions are not available. Read the views, proportions and any dimensions from the drawing "
                 "image yourself and say in the plan which sizes you read and which you estimated.")
    if base_program:
        text += ("\n\nThis is the CURRENT program of the model (it built a valid model). Change it to do what the user "
                 f"asked, keep everything else, and answer with the whole revised program. length_mm was {base_length_mm}."
                 f"\n```python\n{base_program[:40000]}\n```")
    text += ("\n\nFirst write `plan`: what the object is, " + ("which way it faces in each view, " if sheet else "")
             + "and every part you will build with where its size comes from (measured, or your engineering estimate). "
               "Then `code`. Give `length_mm`: the real overall length you assume.")
    content = [{"type": "text", "text": text}] + ([_image(Image.open(sheet))] if sheet else [])
    rounds_log, best, history, valid = [], None, [], []
    keep_newest = (not measured) or bool(base_program)
    for k in range(1, rounds + 1):
        msg = content if k == 1 else content + history
        t = time.time()
        try:
            ans, rec = ai.ask_json("C1_cad_program", f"round{k}", model, msg, CODE_SCHEMA, seed=k, timeout=400,
                                   effort="medium")
        except AI.ModelUnavailable as e:
            rounds_log.append({"round": k, "error": f"model: {e}"[:400]})
            break
        t_model = round(time.time() - t, 1)
        rdir = os.path.join(out_dir, f"round{k}")
        r = run_program(ans["code"], meas, float(ans["length_mm"]), rdir)
        entry = {"round": k, "model": rec.get("model"), "model_s": t_model, "run_s": r["seconds"],
                 "object": ans["object"], "plan": ans["plan"], "length_mm": ans["length_mm"], "error": r["error"],
                 "parts": [{k2: p[k2] for k2 in ("name", "material", "valid", "volume_mm3")} for p in r["parts"]]}
        fb = []
        if r["error"] is None:
            parts = load_parts(r)
            bad = [p["name"] for p in parts if not p["valid"] or p["volume_mm3"] <= 0]
            iou, imgs = score(parts, meas, out_dir, f"r{k}") if measured else ({}, {})
            pics = {v: render(parts, os.path.join(out_dir, f"render_r{k}_{v}.png"), view=v)
                    for v in ("iso", "rear_iso", "side", "front", "top")}
            entry.update(iou=iou, mean_iou=round(float(np.mean(list(iou.values()))), 4) if iou else None, invalid=bad,
                         renders=pics)
            log(f"round {k}: {len(parts)} parts, invalid {len(bad)}, IoU {iou}")
            ok = not bad
            if ok:
                top = max([v["entry"]["mean_iou"] for v in valid] + [entry["mean_iou"] or 0.0]) if iou else None
                valid.append({"entry": entry, "parts": parts, "code": ans["code"], "dir": rdir})
                if not iou:                                  # no drawing: the newest valid round
                    best = valid[-1]
                elif keep_newest:                            # an edit: the newest valid round unless it regressed > 0.03
                    best = max((v for v in valid if v["entry"]["mean_iou"] >= top - 0.03), key=lambda v: v["entry"]["round"])
                else:                                        # a build from the drawing: the best checked round
                    best = max(valid, key=lambda v: v["entry"]["mean_iou"])
            fb = [{"type": "text", "text": (
                f"Round {k} result, checked by code: {len(parts)} parts built"
                + (f"; INVALID solids (must be fixed): {bad}" if bad else "")
                + (f". Silhouette IoU vs the drawing per view: {iou} (1.0 = identical). In each overlay: grey = drawn and "
                   "built, RED = drawn but NOT built (missing), MAGENTA = built but NOT drawn (wrong / too big)" if iou else "")
                + ". Parts: " + ", ".join(p["name"] for p in parts)
                + ". Below: shaded renders of YOUR model. Judge it like a demanding design reviewer: shapes, proportions, "
                  "missing details, anything crude, floating or intersecting wrongly. Fix it, keep what is right, add the "
                  "detail the object should have. Answer with the whole revised program.")}]
            for v, f in imgs.items():
                fb += [{"type": "text", "text": f"{v} overlay:"}, _image(f, 900)]
            for v, f in pics.items():
                fb += [{"type": "text", "text": f"render {v}:"}, _image(f, 900)]
            if ok and iou and entry["mean_iou"] >= target and k >= 2:
                rounds_log.append(entry)
                break
        else:
            log(f"round {k}: error: {r['error'][:200]}")
            fb = [{"type": "text", "text": f"Round {k}: the program failed: {r['error']}\nFix it and answer with the whole "
                                           "revised program."}]
        rounds_log.append(entry)
        history = [{"type": "text", "text": f"Your round {k} program:\n```python\n{ans['code'][:40000]}\n```"}] + fb
    rep = {"sheet": sheet, "measured": measured, "not_measured_why": why_not, "request": request,
           "edit": bool(base_program), "rounds": rounds_log,
           "seconds": round(time.time() - t0, 1), "hypotheses": ai.store}
    if best:
        comps = [{"id": f"p{i:02d}_" + "".join(ch if ch.isalnum() else "_" for ch in p["name"])[:40], "name": p["name"],
                  "shape": p["shape"], "colour": p["colour"], "material": p["material"], "parent": None, "extras": {}}
                 for i, p in enumerate(best["parts"])]
        open(os.path.join(out_dir, "program.py"), "w", encoding="utf-8").write(strip_fence(best["code"]))
        EX.write_step(comps, os.path.join(out_dir, "model.step"))
        open(os.path.join(out_dir, "model.glb"), "wb").write(EX.glb(comps))
        rep["best"] = {k2: best["entry"][k2] for k2 in ("round", "iou", "mean_iou", "object", "length_mm")}
        rep["best"]["parts"] = [{"id": c["id"], "name": c["name"], "colour": c["colour"], "material": c["material"],
                                 "brep": p["brep"]} for c, p in zip(comps, best["parts"])]
        rep["best"]["program"] = os.path.join(out_dir, "program.py")
    json.dump(rep, open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8"), indent=1, default=str)
    return rep


if __name__ == "__main__":
    # python -m cad.codegen <sheet> <out_dir> [rounds]
    import pathlib
    for line in open(pathlib.Path(__file__).resolve().parents[2] / ".env", encoding="utf-8"):
        if "=" in line and not line.strip().startswith("#"):
            k_, v_ = line.strip().split("=", 1)
            os.environ.setdefault(k_.strip(), v_.strip().strip('"'))
    r = build(sys.argv[1], sys.argv[2], rounds=int(sys.argv[3]) if len(sys.argv) > 3 else 5)
    print(json.dumps({k: r[k] for k in ("seconds", "best") if k in r}, indent=1, default=str))
