"""Explain this machine: Muse Spark writes a 5-10 step explanation grounded in the BUILT model, and Muse Image draws
one concept illustration next to it.

Grounding, enforced in code (never trusted to the prompt alone):
- facts(state) lists every part of the model with its id, name, kind and sizes, each size tagged "measured" (traced,
  read or measured on the drawing) or "guessed" (assumed, or added by the engineer's completion, with its reason);
  gear pairs come from the parts' gear_mesh joints with their tooth counts, and the ratio is computed here.
- validate(plan, facts) rejects a step that names a part id the model does not have, or writes a number that is not in
  the facts (a size, a tooth count, a ratio, a count of parts, a label printed on the drawing).
- explain() retries once with the errors shown to Muse Spark; steps still invalid are dropped and counted.

Muse Image (muse-image-1.0, POST /v1/images/generations, checked on dev.meta.ai/docs 2026-11-01) is asked in parallel
for ONE illustration, labelled ILLUSTRATION_LABEL wherever it is shown; it is never the measured result. If it fails or
takes longer than IMAGE_LIMIT_S, the explanation is returned without it."""
import concurrent.futures as cf
import json
import re
import time

import agent

IMAGE_MODEL = "muse-image-1.0"
IMAGE_LIMIT_S = 30
ILLUSTRATION_LABEL = "AI illustration — concept, not the measured model"
CAMERAS = ["front", "top", "iso", "section"]
GUESSED = ("assumed", "engineer", "added", "guess", "typical", "rule")

PLAN_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["machine", "steps"], "properties": {
    "machine": {"type": "string"},
    "steps": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                         "required": ["title", "text", "parts", "camera", "explode"], "properties": {
        "title": {"type": "string"}, "text": {"type": "string"},
        "parts": {"type": "array", "items": {"type": "string"}},
        "camera": {"type": "string", "enum": CAMERAS}, "explode": {"type": "boolean"}}}}}}

PROMPT = """You are a senior mechanical engineer explaining a machine to a smart newcomer, step by step, while a 3D
viewer highlights the parts you name. The image is the drawing the model was built from. The JSON below is the BUILT
MODEL: every part with its id, kind and sizes; "src" says whether a size was measured on the drawing or guessed.

Write 5 to 10 steps in this order:
1. what the machine is (from the drawing and the parts; say if that is your reading),
2. the frame / housing that holds everything,
3. where the power comes in,
4. how the motion is passed on: the gear pairs (say if a pair was guessed, and why); give a ratio only where
   the JSON gives one, else say the ratio is unknown because the teeth were not counted,
5. the output (what moves at the end, and how),
6. last step: what was guessed and why (thicknesses, depths, parts added by the engineer).

Rules (checked by a program; a step that breaks one is rejected):
- "parts": 1-12 part ids from the JSON, exactly as written there; the viewer highlights them.
- Sizes are in mm: write the unit (e.g. "12 mm"). Every number you write must appear in the JSON (a size, a tooth
  count, a ratio, a count, a drawing label). Do not convert units, do not add up or estimate. If a number is not
  there, describe it in words.
- "scale" says whether the real size is known. When real_size_known is false (a patent drawing has no scale), prefer
  proportions ("the output wheel is about three times the pinion"); a step that gives a size in mm must say "model
  scale, real size unknown" in that step.
- "text": 2 to 4 plain sentences. "title": at most 6 words, no number unless it is in the JSON.
- "camera": front (the drawing's view), top, iso (3/4 view) or section (cut through the middle).
- "explode": true when parts hide each other and pulling them apart helps.
Answer with the JSON object only.

BUILT MODEL:
{facts}"""


def _src(s):
    return "guessed" if any(w in str(s).lower() for w in GUESSED) else "measured"


def facts(state, scale=None):
    """The built model as Muse Spark sees it, and the numbers a step may use. scale: {"known": bool, "source": str}
    (None: not known, as for any patent drawing without a dimension)."""
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
        f = {"id": p["id"], "name": p["name"], "kind": k, "dims": dims}
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
    return {"scale": sc, "parts": out, "gear_pairs": pairs, "shafts": shafts, "count_by_kind": kinds, "parts_total": len(out)}


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


def validate(plan, fx):
    """Per step a list of problems (empty = valid): unknown part ids, numbers that are not in the facts, a camera that
    does not exist, text outside 2-4 sentences. A number written is accepted when some fact rounds to it at the
    precision written (25 for 25.4 is accepted, 26 is not); 1 and 2 are always accepted (one of, two gears)."""
    ids = {p["id"] for p in fx["parts"]}
    allowed = _numbers_in({k: v for k, v in fx.items() if k != "scale"}) | {1.0, 2.0}
    scale_known = (fx.get("scale") or {}).get("real_size_known", True)
    out = []
    for s in plan.get("steps") or []:
        bad = []
        unknown = [i for i in s.get("parts") or [] if i not in ids]
        if unknown:
            bad.append(f"part ids not in the model: {unknown[:5]}")
        if not s.get("parts"):
            bad.append("no part ids")
        for m in NUMBER.findall(f"{s.get('title', '')} {s.get('text', '')}"):
            x = float(m.replace(",", "."))
            dec = len(m.split(".")[1]) if "." in m else 0
            if not any(abs(round(v, dec) - x) < 1e-9 for v in allowed):
                bad.append(f"number {m} is not in the model data")
        if not scale_known and SIZE_MM.search(f"{s.get('title', '')} {s.get('text', '')}") and \
                "model scale" not in f"{s.get('title', '')} {s.get('text', '')}".lower():
            bad.append("a size in mm without \"model scale, real size unknown\" (the drawing has no scale)")
        if s.get("camera") not in CAMERAS:
            bad.append(f"camera {s.get('camera')!r}")
        n = len([x for x in re.split(r"(?<=[.!?])\s+", (s.get("text") or "").strip()) if x])
        if not 2 <= n <= 4:
            bad.append(f"{n} sentences (2-4)")
        out.append(bad)
    return out


def _spark_plan(fx, image, extra=None):
    content = [{"type": "text", "text": PROMPT.replace("{facts}", json.dumps(fx, separators=(",", ":")))}]
    if image:
        content.append({"type": "image_url", "image_url": {"url": image}})
    if extra:
        content.append({"type": "text", "text": extra})
    return agent._spark_json(content, PLAN_SCHEMA, "explanation", timeout=120, effort="low")


def illustration_prompt(fx):
    k = fx["count_by_kind"]
    main = ", ".join(f"{n} {kind}{'s' if n > 1 else ''}" for kind, n in sorted(k.items(), key=lambda kv: -kv[1])
                     if kind not in ("pin", "hub", "added", "group"))[:300]
    return ("Clean technical concept illustration of a mechanical machine, three-quarter view, soft studio light, "
            f"brushed metal on a dark blue background, no text, no labels, no people. It contains: {main}.")


def illustrate(prompt, limit_s=IMAGE_LIMIT_S):
    """One Muse Image illustration -> (data URL, seconds). Raises on HTTP error or after limit_s."""
    t0 = time.time()
    r = agent._post("/images/generations", {"model": IMAGE_MODEL, "prompt": prompt, "n": 1,
                                             "output_format": "jpeg", "response_format": "b64_json"}, timeout=limit_s)
    d = (r.get("data") or [{}])[0]
    s = round(time.time() - t0, 1)
    if not d.get("b64_json"):
        raise RuntimeError("Muse Image returned no image")
    if s > limit_s:                          # the socket timeout is per read, not for the whole call
        raise TimeoutError(f"Muse Image took {s} s (limit {limit_s} s)")
    return "data:image/jpeg;base64," + d["b64_json"], s


def explain(state, image=None, with_illustration=True, on_step=None, scale=None):
    """-> {"machine", "steps", "rejected_steps", "retried", "timing", "illustration", "facts_summary"}.
    image: the drawing (data URL) the model was built from, shown to Muse Spark. Raises agent.SparkError when Muse
    Spark gives no usable explanation (fewer than 5 valid steps after one retry)."""
    step = on_step or (lambda e: None)
    t0 = time.time()
    fx = facts(state, scale)
    if not fx["parts"]:
        raise ValueError("there is no model to explain")
    pool = cf.ThreadPoolExecutor(2)
    img = pool.submit(illustrate, illustration_prompt(fx)) if with_illustration else None
    step({"stage": "tool", "tool": "explain · Muse Spark"})
    plan, meta = _spark_plan(fx, image)
    errs = validate(plan, fx)
    retried = False
    if any(errs) or not 5 <= len(plan.get("steps") or []) <= 10:
        retried = True
        problems = "; ".join(f"step {i + 1}: {', '.join(e)}" for i, e in enumerate(errs) if e) or \
            f"{len(plan.get('steps') or [])} steps (5-10 needed)"
        plan2, meta2 = _spark_plan(fx, image, "Your previous answer broke the rules: " + problems +
                                   ". Previous answer: " + json.dumps(plan)[:6000] + " Answer again, fixing them.")
        meta["calls"] += meta2["calls"]
        plan, errs = plan2, validate(plan2, fx)
    keep = [s for s, e in zip(plan.get("steps") or [], errs) if not e][:10]
    rejected = [{"title": s.get("title"), "why": e} for s, e in zip(plan.get("steps") or [], errs) if e]
    step({"stage": "done", "tool": "explain · Muse Spark",
          "error": None if len(keep) >= 5 else f"only {len(keep)} valid steps"})
    if len(keep) < 5:
        pool.shutdown(wait=False, cancel_futures=True)
        raise agent.SparkError(f"Muse Spark's explanation had only {len(keep)} valid steps after one retry: {rejected[:3]}")
    t_spark = round(time.time() - t0, 1)
    ill = None
    if img is not None:
        step({"stage": "tool", "tool": "illustration · Muse Image"})
        try:
            url, s = img.result(timeout=max(0.1, IMAGE_LIMIT_S - (time.time() - t0)))
            ill = {"data_url": url, "label": ILLUSTRATION_LABEL, "model": IMAGE_MODEL, "s": s}
            step({"stage": "done", "tool": "illustration · Muse Image"})
        except Exception as e:
            reason = (f"took longer than {IMAGE_LIMIT_S} s" if isinstance(e, cf.TimeoutError) and not str(e)
                      else f"{type(e).__name__}: {str(e)[:160]}")
            ill = {"data_url": None, "label": ILLUSTRATION_LABEL, "model": IMAGE_MODEL, "error": reason}
            step({"stage": "done", "tool": "illustration · Muse Image", "error": reason})
    pool.shutdown(wait=False, cancel_futures=True)
    return {"machine": plan.get("machine", ""), "steps": keep, "rejected_steps": rejected, "retried": retried,
            "spark_calls": meta["calls"], "timing": {"spark_s": t_spark, "total_s": round(time.time() - t0, 1)},
            "illustration": ill, "scale": fx["scale"], "facts_summary": {"parts": fx["parts_total"], "gear_pairs": len(fx["gear_pairs"]),
                                                   "count_by_kind": fx["count_by_kind"]}}
