"""Explain this machine: an engineer's walk-through of ONE built model, grounded in that model and illustrated with
renders of that model (never an invented picture).

The explanation is structured the way an engineer teaches a machine:
  overview -> architecture (the subsystems, each a set of the model's own part ids) -> why this architecture ->
  each subsystem -> the power / load path -> interfaces between subsystems -> assembly order -> what was measured and
  what was assumed -> a short check-yourself quiz.

Grounding, enforced in code (never trusted to the prompt alone):
- facts(state) lists every part of the model with its id, name, kind, its size and place in the model (measured on
  the model's geometry), its sizes from the drawing tagged "measured" or "guessed", gear pairs with the ratio computed
  here from counted teeth, and the CAD features of a CAD body.
- validate(plan, facts) rejects a step that names a part id the model does not have, or writes a number that is not in
  the facts; subsystems with unknown ids are dropped.
- explain() retries once with the errors shown to Muse Spark; steps still invalid are dropped and counted.

Pictures (engine/snap.py): every step gets a render of the model from its camera, the step's parts highlighted
(exploded or cut open when the step says so); the architecture step colours each subsystem. The source drawing is the
model's OWN (assistant.build_from_drawing records it per model), not the last drawing built."""
import concurrent.futures as cf
import json
import re
import time

import numpy as np

import agent

CAMERAS = ["front", "top", "iso", "section", "rear", "left"]
KINDS = ["overview", "architecture", "why", "subsystem", "connection", "flow", "interfaces", "assembly", "assumptions"]
JOINT_WORDS = {"fixed": "fixed (bolted / welded: does not move)", "rigid": "fixed (does not move)",
               "revolute": "revolute (turns about an axis)", "continuous": "continuous (turns freely, e.g. a wheel)",
               "prismatic": "prismatic (slides along an axis)", "slide": "prismatic (slides along an axis)",
               "hinge": "revolute (a hinge: swings)", "ball": "ball joint (turns in every direction)",
               "gear_mesh": "gear mesh (teeth drive each other)", "root": "the base everything else is mounted on"}


def _connections(state, ids_by_name):
    """How the parts connect, from the CAD program's plan (Muse Wonder planned every component with what it is mounted
    on, the joint, and the evidence) and its constraints. Only for AI-written CAD-program models; [] otherwise."""
    import json as _json
    from pathlib import Path as _P
    out, cons = [], []
    for g in [p for p in state["parts"] if (p.get("eng") or {}).get("kind") == "cad program" and p["eng"].get("program")]:
        f = _P(g["eng"]["program"]).parent / "plan.json"
        if not f.exists():
            continue
        try:
            plan = _json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for c in plan.get("components") or []:
            a, b = ids_by_name.get(c.get("name")), ids_by_name.get(c.get("parent"))
            if a and b:
                j = str(c.get("joint") or "fixed").lower()
                out.append({"part": a, "mounted_on": b, "joint": JOINT_WORDS.get(j, j),
                            "evidence": str(c.get("evidence") or "")[:120]})
        for c in plan.get("constraints") or []:
            a, b = ids_by_name.get(c.get("a")), ids_by_name.get(c.get("b"))
            if a and b:
                cons.append({"a": a, "b": b, "type": c.get("type")})
    return out, cons
GUESSED = ("assumed", "engineer", "added", "guess", "typical", "rule")
PALETTE = ["#4cc9f0", "#f72585", "#ffd166", "#06d6a0", "#b388ff", "#ff8c42", "#90be6d", "#ef476f", "#118ab2", "#c9ada7"]

PLAN_SCHEMA = {"type": "object", "additionalProperties": False,
               "required": ["machine", "overview", "subsystems", "design_rationale", "assembly_order", "steps", "quiz"],
               "properties": {
    "machine": {"type": "string"},
    "overview": {"type": "string"},
    "subsystems": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                              "required": ["name", "role", "parts"], "properties": {
        "name": {"type": "string"}, "role": {"type": "string"}, "parts": {"type": "array", "items": {"type": "string"}}}}},
    "design_rationale": {"type": "array", "items": {"type": "string"}},
    "assembly_order": {"type": "array", "items": {"type": "string"}},
    "steps": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                         "required": ["kind", "title", "text", "parts", "camera", "explode"], "properties": {
        "kind": {"type": "string", "enum": KINDS},
        "title": {"type": "string"}, "text": {"type": "string"},
        "parts": {"type": "array", "items": {"type": "string"}},
        "camera": {"type": "string", "enum": CAMERAS}, "explode": {"type": "boolean"}}}},
    "quiz": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                        "required": ["question", "options", "answer"], "properties": {
        "question": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}},
        "answer": {"type": "integer"}}}}}}

PROMPT = """You are a senior engineer teaching how this machine is built and why, to a smart newcomer, while a 3D viewer
shows the model and highlights the parts you name. {image_note} The JSON below is the BUILT MODEL: every part with its id,
name, kind, its size and where it sits (size_mm, at = its centre as fractions of the model: x rear->front or along the
model, y, z bottom->top), sizes from the drawing ("src": measured or guessed), gear pairs, CAD features of a CAD body.

Answer with:
- machine: what it is (say if that is your reading).
- overview: 2-3 sentences: what it does and how, in plain words.
- subsystems: 3-7 functional subsystems (e.g. frame / body, power, transmission, running gear, controls, enclosure),
  each with its role in one sentence and the ids of ALL its parts. Every part belongs to exactly one subsystem.
- design_rationale: 2-4 short reasons WHY the machine is arranged this way (the engineering trade-offs you can see:
  load paths, packaging, symmetry, serviceability). This is your reasoning: write it as such ("likely", "so that").
- assembly_order: the subsystem names in the order they would be assembled.
- steps: 9 to 16 steps in this order of kinds: overview, architecture, why, one "subsystem" step per subsystem,
  then (when the JSON has "connections") 3-6 "connection" steps, flow (how power or load travels from input to output),
  interfaces (where subsystems connect and how), assembly (explode: true), assumptions (what was measured on the
  drawing and what was guessed, and why).
- "connection" steps teach HOW THE PARTS ARE JOINED, step by step like an engineer at the bench: start at the base (the
  part whose joint is "the base everything else is mounted on") and walk outwards along "connections". Each step takes
  one chain of 2-6 parts and says, for each link, which part is mounted on which, with which joint, and what that
  joint lets it do (fixed = carries load, revolute = turns, prismatic = slides). Use the "constraints" (coaxial,
  contact, clearance) to say what lines up with what. List exactly those parts in "parts".
- quiz: 3 questions with 3 options each and the index (0-2) of the right one, about THIS model.

Rules (checked by a program; a step that breaks one is rejected):
- "parts": 1-30 part ids from the JSON, exactly as written; the viewer highlights them. The overview / architecture
  / why steps may list the main parts.
- Every number you write must appear in the JSON (a size, a count, a tooth count, a ratio, a label). Do not convert
  units, add up or estimate. If a number is not there, describe it in words. Sizes are mm: write the unit.
- When scale.real_size_known is false, a step that gives a size in mm must say "model scale, real size unknown".
- "text": 2 to 5 plain sentences. "title": at most 7 words, no number unless it is in the JSON.
- "camera": front / rear / left / top (looking at that side of the model), iso (3/4 view) or section (cut open).
- "explode": true when parts hide each other and pulling them apart helps.
Answer with the JSON object only.

BUILT MODEL:
{facts}"""


def _src(s):
    return "guessed" if any(w in str(s).lower() for w in GUESSED) else "measured"


def facts(state, scale=None, geometry_of=None, cad_features=None):
    """The built model as Muse Spark sees it, and the numbers a step may use. scale: {"known": bool, "source": str}
    (None: not known, as for any patent drawing without a dimension). geometry_of: {part id: (size_mm, at)} measured
    on the model (explain() fills it); cad_features: labels of a CAD body's features."""
    parts = [p for p in state["parts"] if p.get("type") != "group" and p.get("visible", True)]
    by_name = {p["name"]: p for p in parts}
    out, kinds = [], {}
    for p in parts:
        e = p.get("eng") or {}
        k = e.get("kind", p["type"])
        kinds[k] = kinds.get(k, 0) + 1
        dims = {}
        for d, v in (e.get("dims") or {}).items():
            val, src = (v[0], v[1]) if isinstance(v, (list, tuple)) and len(v) == 2 else (v, "")
            dims[d] = {"v": val, "src": _src(src)} if isinstance(val, (int, float)) else {"v": str(val)[:40], "src": _src(src)}
        f = {"id": p["id"], "name": p["name"], "kind": k}
        if dims:
            f["dims"] = dims
        if geometry_of and p["id"] in geometry_of:
            f["size_mm"], f["at"] = geometry_of[p["id"]]
        if e.get("reason"):
            f["added_because"] = str(e["reason"])[:160]
        j = [f"{x.get('type')} {x.get('with')}" for x in e.get("joints") or [] if x.get("with")]
        if j:
            f["joints"] = j[:4]
        out.append(f)
    pairs, seen = [], set()
    for p in parts:
        e = p.get("eng") or {}
        for x in e.get("joints") or []:
            q = by_name.get(x.get("with"))
            if x.get("type") != "gear_mesh" or not q or frozenset((p["id"], q["id"])) in seen:
                continue
            seen.add(frozenset((p["id"], q["id"])))
            ta = (e.get("dims") or {}).get("teeth") or [None, ""]
            tb = ((q.get("eng") or {}).get("dims") or {}).get("teeth") or [None, ""]
            pr = {"gear_a": p["id"], "gear_b": q["id"], "teeth_a": ta[0], "teeth_b": tb[0],
                  "pair_found_by": "guessed" if "guess" in str(x.get("source", "")) else "measured geometry",
                  "pair_reason": str(x.get("source", ""))[:160]}
            if ta[0] and tb[0] and _src(ta[1]) == _src(tb[1]) == "measured":     # ratios from counted teeth only
                pr["ratio_b_to_a"] = round(tb[0] / ta[0], 2)
                pr["ratio_a_to_b"] = round(ta[0] / tb[0], 2)
            else:
                pr["ratio"] = "unknown: tooth counts were not measured"
            pairs.append(pr)
    shafts = [f["id"] for f in out if f["kind"] in ("shaft", "axle", "rod")]
    known = bool((scale or {}).get("known"))
    sc = {"real_size_known": known, "note": (f"sizes are real mm: {scale.get('source')}" if known else
                                             "sizes are model mm only: the drawing states no scale or dimension"
                                             + (f" ({scale.get('source')})" if (scale or {}).get("source") else ""))}
    fx = {"scale": sc, "parts": out, "gear_pairs": pairs, "shafts": shafts, "count_by_kind": kinds, "parts_total": len(out)}
    conn, cons = _connections(state, {p["name"]: p["id"] for p in parts})
    if conn:
        fx["connections"] = conn[:200]
        fx["constraints"] = cons[:80]
    if cad_features:
        fx["cad_features"] = cad_features[:40]
    return fx


def _numbers_in(obj):
    """Every number in the facts (values, counts, ratios, and digits inside names / drawing labels)."""
    nums = set()

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            nums.add(float(x))
        elif isinstance(x, str):
            nums.update(float(m) for m in re.findall(r"\d+(?:\.\d+)?", x))
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(k)
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
    walk(obj)
    return nums


NUMBER = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)(?![\w])")
SIZE_MM = re.compile(r"\d(?:[.,]\d+)?\s*mm\b", re.I)


def _bad_numbers(text, allowed):
    out = []
    for m in NUMBER.findall(text):
        x = float(m.replace(",", "."))
        dec = len(m.split(".")[1]) if "." in m else 0
        if not any(abs(round(v, dec) - x) < 1e-9 for v in allowed):
            out.append(f"number {m} is not in the model data")
    return out


def validate(plan, fx):
    """Per step a list of problems (empty = valid): unknown part ids, numbers that are not in the facts, a camera that
    does not exist, text outside 2-5 sentences. A number written is accepted when some fact rounds to it at the
    precision written (25 for 25.4 is accepted, 26 is not); 1, 2 and 3 are always accepted (one of, two gears)."""
    ids = {p["id"] for p in fx["parts"]}
    allowed = _numbers_in({k: v for k, v in fx.items() if k != "scale"}) | {1.0, 2.0, 3.0}
    scale_known = (fx.get("scale") or {}).get("real_size_known", True)
    out = []
    for s in plan.get("steps") or []:
        bad = []
        unknown = [i for i in s.get("parts") or [] if i not in ids]
        if unknown:
            bad.append(f"part ids not in the model: {unknown[:5]}")
        if not s.get("parts"):
            bad.append("no part ids")
        txt = f"{s.get('title', '')} {s.get('text', '')}"
        bad += _bad_numbers(txt, allowed)
        if not scale_known and SIZE_MM.search(txt) and "model scale" not in txt.lower():
            bad.append("a size in mm without \"model scale, real size unknown\" (the drawing has no scale)")
        if s.get("camera") not in CAMERAS:
            bad.append(f"camera {s.get('camera')!r}")
        if s.get("kind") == "connection" and fx.get("connections"):
            linked = {frozenset((c["part"], c["mounted_on"])) for c in fx["connections"]}
            ps = s.get("parts") or []
            if not any(frozenset((a, b)) in linked for i, a in enumerate(ps) for b in ps[i + 1:]):
                bad.append("a connection step must name parts that are connected in the model's plan")
        n = len([x for x in re.split(r"(?<=[.!?])\s+", (s.get("text") or "").strip()) if x])
        if not 2 <= n <= 5:
            bad.append(f"{n} sentences (2-5)")
        out.append(bad)
    return out


def clean_extras(plan, fx):
    """Subsystems keep only real part ids (an empty one is dropped); a quiz item whose question or RIGHT answer has a
    number that is not in the model, or with a bad answer index, is dropped (wrong options may be any number)."""
    ids = {p["id"] for p in fx["parts"]}
    allowed = _numbers_in({k: v for k, v in fx.items() if k != "scale"}) | {1.0, 2.0, 3.0}
    subs = []
    for s in plan.get("subsystems") or []:
        ps = [i for i in s.get("parts") or [] if i in ids]
        if ps:
            subs.append({"name": s.get("name", "")[:60], "role": s.get("role", "")[:240], "parts": ps})
    quiz = [q for q in plan.get("quiz") or [] if len(q.get("options") or []) >= 2
            and 0 <= int(q.get("answer", -1)) < len(q["options"])
            and not _bad_numbers(q["question"] + " " + q["options"][int(q["answer"])], allowed)][:4]
    why = [w for w in plan.get("design_rationale") or [] if not _bad_numbers(w, allowed)][:5]
    return subs, quiz, why


def _spark_plan(fx, image, extra=None):
    note = ("The image is the drawing this model was built from." if image else
            "There is no source drawing for this model: work from the model data.")
    content = [{"type": "text", "text": PROMPT.replace("{image_note}", note).replace(
        "{facts}", json.dumps(fx, separators=(",", ":")))}]
    if image:
        content.append({"type": "image_url", "image_url": {"url": image}})
    if extra:
        content.append({"type": "text", "text": extra})
    return agent._spark_json(content, PLAN_SCHEMA, "explanation", timeout=150, effort="low")


# ------------------------------------------------------------------------------------------------ geometry + pictures
def measure(state, model):
    """{part id: (size_mm, at)} on the model's own geometry: each part's box size and its centre as fractions of the
    model's box (x along the model / rear->front, y, z bottom->top)."""
    from engine import snap
    ms = snap.model_meshes(state, model)
    if not ms:
        return {}
    allV = np.vstack([V for _, V, _, _ in ms])
    lo, hi = allV.min(0), allV.max(0)
    span = np.maximum(hi - lo, 1e-6)
    f = snap.front_axis(model)
    out = {}
    for p, V, _, _ in ms:
        a, b = V.min(0), V.max(0)
        c = ((a + b) / 2 - lo) / span
        if f[0] < -0.5:                                 # x as rear (0) -> front (1) for a model facing -x
            c[0] = 1 - c[0]
        out[p["id"]] = ([round(float(x)) for x in b - a], [round(float(x), 2) for x in c])
    return out


def _offsets(state, model):
    """Explode offsets accumulated down the tree (a part moves with its sub-assembly), in the model frame."""
    from engine import cutaway, lab
    sub = lab.subtree(state, model["id"])
    off = cutaway.explode_offsets(sub)
    by = {p["id"]: p for p in sub}
    tot = {}
    for p in sub:
        v, q = np.zeros(3), p
        while q is not None and q["id"] != model["id"]:
            v = v + np.asarray(off.get(q["id"], np.zeros(3)), float)
            q = by.get(q.get("parent"))
        tot[p["id"]] = v
    return tot


def render_steps(state, model, steps, subsystems, size=440):
    """One picture per step (data URLs, JPEG) and the architecture picture (subsystems coloured)."""
    from engine import snap
    f = snap.front_axis(model)
    plain = snap.model_meshes(state, model)
    if not plain:
        return [None] * len(steps), None
    exploded = snap.model_meshes(state, model, offsets=_offsets(state, model))
    allV = np.vstack([V for _, V, _, _ in plain])
    mid = (allV.min(0) + allV.max(0)) / 2
    side = snap.sides(f)["left"]
    tint = {pid: PALETTE[k % len(PALETTE)] for k, s in enumerate(subsystems) for pid in s["parts"]}
    n_parts = len(plain)

    def one(s):
        cam = s.get("camera", "iso")
        view = {"section": "iso", "front": "front", "rear": "rear", "left": "left", "top": "top"}.get(cam, "iso")
        ms = exploded if s.get("explode") else plain
        clip = (side, float(mid @ side)) if cam == "section" else None
        t = tint if s.get("kind") == "architecture" else None
        hl = s.get("parts")
        if t or len(set(hl or [])) >= 0.7 * n_parts:      # a step about (nearly) the whole model: its own colours
            hl = None
        im = snap.render(ms, view, f, size, highlight=hl, tint=t, clip=clip)
        return snap.png_data_url(im, "JPEG")
    with cf.ThreadPoolExecutor(4) as pool:
        imgs = list(pool.map(one, steps))
        arch = pool.submit(lambda: snap.png_data_url(snap.render(exploded, "iso", f, 520, tint=tint), "JPEG")).result() \
            if subsystems else None
    return imgs, arch


# ------------------------------------------------------------------------------------------------ the explanation
def explain(state, image=None, on_step=None, scale=None, model=None, cad_features=None, render=True):
    """-> {"machine", "overview", "subsystems" (+ colour), "design_rationale", "assembly_order", "steps" (+ image),
    "architecture_image", "quiz", "rejected_steps", "retried", "timing", "scale", "facts_summary"}.
    state: the scene (or a sub-scene holding one model); model: the model's root group (its own frame is used for
    the geometry and the pictures). image: the model's own source drawing (data URL) or None. Raises agent.SparkError
    when Muse Spark gives no usable explanation (fewer than 5 valid steps after one retry)."""
    step = on_step or (lambda e: None)
    t0 = time.time()
    geo = measure(state, model) if (model is not None and render) else None
    fx = facts(state, scale, geo, cad_features)
    if not fx["parts"]:
        raise ValueError("there is no model to explain")
    step({"stage": "tool", "tool": "explain · Muse Spark"})
    plan, meta = _spark_plan(fx, image)
    errs = validate(plan, fx)
    retried = False
    if any(errs) or not 5 <= len(plan.get("steps") or []) <= 14:
        retried = True
        problems = "; ".join(f"step {i + 1}: {', '.join(e)}" for i, e in enumerate(errs) if e) or \
            f"{len(plan.get('steps') or [])} steps (7-12 needed)"
        plan2, meta2 = _spark_plan(fx, image, "Your previous answer broke the rules: " + problems +
                                   ". Previous answer: " + json.dumps(plan)[:8000] + " Answer again, fixing them.")
        meta["calls"] += meta2["calls"]
        plan, errs = plan2, validate(plan2, fx)
    keep = [s for s, e in zip(plan.get("steps") or [], errs) if not e][:14]
    rejected = [{"title": s.get("title"), "why": e} for s, e in zip(plan.get("steps") or [], errs) if e]
    step({"stage": "done", "tool": "explain · Muse Spark",
          "error": None if len(keep) >= 5 else f"only {len(keep)} valid steps"})
    if len(keep) < 5:
        raise agent.SparkError(f"Muse Spark's explanation had only {len(keep)} valid steps after one retry: {rejected[:3]}")
    subs, quiz, why = clean_extras(plan, fx)
    for k, s in enumerate(subs):
        s["color"] = PALETTE[k % len(PALETTE)]
    t_spark = round(time.time() - t0, 1)
    arch = None
    if render and model is not None:
        step({"stage": "tool", "tool": "pictures of the model"})
        try:
            imgs, arch = render_steps(state, model, keep, subs)
            for s, im in zip(keep, imgs):
                s["image"] = im
            step({"stage": "done", "tool": "pictures of the model"})
        except Exception as e:
            step({"stage": "done", "tool": "pictures of the model", "error": f"{type(e).__name__}: {e}"[:200]})
    return {"machine": plan.get("machine", ""), "overview": plan.get("overview", ""), "subsystems": subs,
            "design_rationale": why, "assembly_order": [a for a in plan.get("assembly_order") or [] if a in {s["name"] for s in subs}],
            "steps": keep, "architecture_image": arch, "quiz": quiz, "rejected_steps": rejected, "retried": retried,
            "spark_calls": meta["calls"], "timing": {"spark_s": t_spark, "total_s": round(time.time() - t0, 1)},
            "model": {"id": model["id"], "name": model["name"]} if model is not None else None,
            "source_image": image, "scale": fx["scale"],
            "facts_summary": {"parts": fx["parts_total"], "gear_pairs": len(fx["gear_pairs"]), "count_by_kind": fx["count_by_kind"]}}
