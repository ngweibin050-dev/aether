"""Muse Spark, Muse Wonder and SAM 3.1 in the drawing-understanding pipeline (stages S1-S8).

Rules enforced here:
- every model answer is JSON checked against a strict schema (enums, number ranges); nothing a model returns is
  executed, evaluated or used as a path / expression: it is data;
- every answer is stored (stage, key, model, seed, prompt hash, response, latency) in the document's hypotheses and
  REPLAYED on rebuild/recompute, so the geometry is reproducible and recompute never calls a model;
- a model never sets a measured value: measured curves come from the ink (cad/observations.py). Models label,
  identify, propose shape fractions inside drawing-derived bounds, and list alternatives; deterministic gates and
  the kernel decide what is used.
Same request settings as agent._spark_json (temperature 0, fixed seed, one retry with the parse error, Muse Wonder ->
Muse Spark fallback named in the record). Written as a small client here so the CAD worker (Python 3.12, no Modal /
optics imports) does not import agent.py.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

API = os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")
SPARK = os.environ.get("META_MODEL", "muse-spark-1.3")
WONDER = os.environ.get("META_COMPLETE_MODEL", "muse-wonder-1.0")
SAM = os.environ.get("META_SAM_MODEL", "sam-3.1")
NAMES = {SPARK: "Muse Spark", WONDER: "Muse Wonder", SAM: "SAM 3.1"}


class ModelUnavailable(RuntimeError):
    """No stored answer and the model could not be called (no key, network, HTTP error, invalid JSON twice)."""


def _img_url(im, fmt="JPEG", max_side=1280):
    """An image for a model call: at most max_side px on its long side (a bigger image costs upload and model time,
    not reading accuracy: the numbered regions and drawn lines stay legible at 1280 px)."""
    buf = io.BytesIO()
    im = im.convert("RGB")
    if max(im.size) > max_side:
        k = max_side / max(im.size)
        im = im.resize((round(im.size[0] * k), round(im.size[1] * k)), Image.LANCZOS)
    im.save(buf, fmt, quality=88)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


def _post(path, body, timeout):
    key = os.environ.get("META_API")
    if not key:
        raise ModelUnavailable("META_API is not set")
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _check(obj, schema, path="$"):
    """Minimal strict JSON-schema check (type, enum, required, additionalProperties false, min/max, items)."""
    t = schema.get("type")
    types = t if isinstance(t, list) else [t] if t else []
    ok_type = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool,
               "null": type(None)}
    if types and not any(isinstance(obj, ok_type[x]) and not (x in ("integer", "number") and isinstance(obj, bool))
                         for x in types):
        raise ValueError(f"{path}: expected {types}, got {type(obj).__name__}")
    if "enum" in schema and obj not in schema["enum"]:
        raise ValueError(f"{path}: {obj!r} not in {schema['enum']}")
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if not np.isfinite(obj):
            raise ValueError(f"{path}: not finite")
        if "minimum" in schema and obj < schema["minimum"]:
            raise ValueError(f"{path}: {obj} < {schema['minimum']}")
        if "maximum" in schema and obj > schema["maximum"]:
            raise ValueError(f"{path}: {obj} > {schema['maximum']}")
    if isinstance(obj, str) and len(obj) > schema.get("maxLength", 600):
        raise ValueError(f"{path}: string too long")
    if isinstance(obj, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in obj:
                raise ValueError(f"{path}: missing {k}")
        for k, v in obj.items():
            if k not in props:
                if schema.get("additionalProperties") is False:
                    raise ValueError(f"{path}: unexpected field {k}")
                continue
            _check(v, props[k], f"{path}.{k}")
    if isinstance(obj, list):
        if "maxItems" in schema and len(obj) > schema["maxItems"]:
            raise ValueError(f"{path}: too many items")
        for i, v in enumerate(obj):
            _check(v, schema.get("items", {}), f"{path}[{i}]")
    return obj


class AI:
    """mode "live": call models, store answers; "replay": only stored answers (ModelUnavailable otherwise)."""

    def __init__(self, store=None, mode="live", log=None):
        self.store = store if store is not None else []
        self.mode = mode
        self.log = log or (lambda e: None)

    def _find(self, stage, key, prompt_hash=None):
        """A stored answer is replayed only for the SAME stage, key AND prompt (text + images, hashed): if the drawing
        evidence shown to the model changed (e.g. the regions were renumbered), the old answer is not reused."""
        for h in self.store:
            if h["stage"] == stage and h["key"] == key and h.get("ok") and \
                    (prompt_hash is None or h.get("prompt_hash") == prompt_hash):
                return h
        return None

    def ask_json(self, stage, key, model, content, schema, seed=1, timeout=120, effort=None, fallback=True):
        """One strict-JSON answer (stored / replayed). Returns (obj, record)."""
        prompt_hash = hashlib.sha1(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]
        h = self._find(stage, key, prompt_hash)
        if h is not None:
            _check(h["response"], schema)
            return h["response"], {**h, "replayed": True}
        if self.mode != "live":
            raise ModelUnavailable(f"{stage}/{key}: no stored answer (replay mode)")
        rec = {"stage": stage, "key": key, "model": model, "seed": seed, "prompt_hash": prompt_hash,
               "t": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.log({"stage": stage, "key": key, "who": NAMES.get(model, model), "state": "run"})
        t0 = time.time()
        try:
            obj = self._call(model, content, schema, seed, timeout, effort)
        except ModelUnavailable as e:
            if fallback and model != SPARK:
                rec["fallback"] = f"{NAMES.get(model, model)} failed ({str(e)[:160]}); answered by Muse Spark"
                try:
                    obj = self._call(SPARK, content, schema, seed, timeout, None)
                    rec["model"] = SPARK
                except ModelUnavailable as e2:
                    rec.update(ok=False, error=str(e2)[:300], latency_s=round(time.time() - t0, 1))
                    self.store.append(rec)
                    self.log({"stage": stage, "key": key, "state": "error", "error": rec["error"]})
                    raise
            else:
                rec.update(ok=False, error=str(e)[:300], latency_s=round(time.time() - t0, 1))
                self.store.append(rec)
                self.log({"stage": stage, "key": key, "state": "error", "error": rec["error"]})
                raise
        rec.update(ok=True, response=obj, latency_s=round(time.time() - t0, 1),
                   response_hash=hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16])
        self.store.append(rec)
        self.log({"stage": stage, "key": key, "who": NAMES.get(rec["model"], rec["model"]), "state": "ok",
                  "s": rec["latency_s"]})
        return obj, rec

    def _call(self, model, content, schema, seed, timeout, effort):
        fmt = {"type": "json_schema", "json_schema": {"name": "answer", "strict": True, "schema": schema}}
        msgs = [{"role": "user", "content": content}]
        err = None
        for attempt in range(2):
            body = {"model": model, "messages": msgs, "response_format": fmt, "temperature": 0, "seed": seed,
                    **({"reasoning_effort": effort} if effort else {})}
            try:
                r = _post("/chat/completions", body, timeout)
            except urllib.error.HTTPError as e:
                raise ModelUnavailable(f"{NAMES.get(model, model)} HTTP {e.code}: {e.read().decode(errors='ignore')[:200]}")
            except ModelUnavailable:
                raise
            except Exception as e:
                raise ModelUnavailable(f"{NAMES.get(model, model)} did not answer ({type(e).__name__}: {str(e)[:120]})")
            txt = r["choices"][0]["message"].get("content") or ""
            try:
                obj = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
                return _check(obj, schema)
            except ValueError as e:
                err = str(e)[:200]
                msgs = msgs + [{"role": "assistant", "content": txt[:4000]},
                               {"role": "user", "content": f"That answer is not valid ({err}). Answer again with the JSON object only."}]
        raise ModelUnavailable(f"{NAMES.get(model, model)} answered twice without a valid object ({err})")

    def sam(self, stage, key, im, prompt, timeout=120):
        """SAM 3.1 concept segmentation on an image -> [{box, confidence, mask}] (masks kept in memory only; the
        stored record keeps boxes, confidences and mask areas, which is what the gates use)."""
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "PNG")
        prompt_hash = hashlib.sha1(prompt.encode() + buf.getvalue()).hexdigest()[:16]
        h = self._find(stage, key, prompt_hash)
        if h is not None:
            return h["response"]["objects"], {**h, "replayed": True}
        if self.mode != "live":
            raise ModelUnavailable(f"{stage}/{key}: no stored SAM answer (replay mode)")
        rec = {"stage": stage, "key": key, "model": SAM, "prompt": prompt, "prompt_hash": prompt_hash,
               "t": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.log({"stage": stage, "key": key, "who": "SAM 3.1", "state": "run"})
        t0 = time.time()
        try:
            import vision                                     # aether-lab/vision.py (SAM 3.1 + meta-sam-parser)
            objs = vision.segment(im, prompt)
        except Exception as e:
            rec.update(ok=False, error=f"{type(e).__name__}: {str(e)[:300]}", latency_s=round(time.time() - t0, 1))
            self.store.append(rec)
            self.log({"stage": stage, "key": key, "state": "error", "error": rec["error"]})
            raise ModelUnavailable(rec["error"])
        out = []
        for o in objs:
            m = o["mask"]
            ys, xs = np.nonzero(m)
            out.append({"box": [int(v) for v in o["box"]], "confidence": float(o.get("confidence") or 0),
                        "mask_area_px": int(m.sum()),
                        "mask_bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None})
            o["_summary"] = out[-1]
        rec.update(ok=True, response={"objects": out}, latency_s=round(time.time() - t0, 1))
        self.store.append(rec)
        self.log({"stage": stage, "key": key, "who": "SAM 3.1", "state": "ok", "s": rec["latency_s"]})
        return objs, rec


# ============================================================================================ stage schemas
S1_SCHEMA = {"type": "object", "additionalProperties": False,
             "required": ["object", "end_a", "end_b", "side_nose", "top_nose", "evidence"],
             "properties": {"object": {"type": "string", "maxLength": 80},
                            "end_a": {"type": "string", "enum": ["front", "rear", "unknown"]},
                            "end_b": {"type": "string", "enum": ["front", "rear", "unknown"]},
                            "side_nose": {"type": "string", "enum": ["left", "right", "unknown"]},
                            "top_nose": {"type": "string", "enum": ["left", "right", "unknown"]},
                            "evidence": {"type": "string", "maxLength": 400}}}

KINDS = ["body_panel", "bonnet", "roof", "windscreen", "side_window", "rear_window", "engine_cover", "louvre",
         "grille_mesh", "air_intake", "headlight", "tail_light", "mirror", "wheel", "tyre", "door", "door_handle",
         "licence_plate", "exhaust", "badge", "splitter", "diffuser", "sill", "pillar", "trim", "spoiler", "other"]
S3_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["regions"],
             "properties": {"regions": {"type": "array", "maxItems": 60, "items": {
                 "type": "object", "additionalProperties": False, "required": ["n", "kind", "confidence"],
                 "properties": {"n": {"type": "integer", "minimum": 0, "maximum": 59},
                                "kind": {"type": "string", "enum": KINDS},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1}}}}}}

S5_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["groups", "reasoning"],
             "properties": {"reasoning": {"type": "string", "maxLength": 600},
                            "groups": {"type": "array", "maxItems": 3, "items": {
                                "type": "object", "additionalProperties": False,
                                "required": ["group", "crown_frac", "deck_drop_frac", "sill_radius_frac",
                                             "glass_bulge_frac", "reason"],
                                "properties": {
                                    "group": {"type": "string", "enum": ["front_deck", "cabin", "rear_deck"]},
                                    "crown_frac": {"type": "number", "minimum": 0, "maximum": 0.3},
                                    "deck_drop_frac": {"type": "number", "minimum": 0, "maximum": 0.4},
                                    "sill_radius_frac": {"type": "number", "minimum": 0.02, "maximum": 0.3},
                                    "glass_bulge_frac": {"type": "number", "minimum": 0, "maximum": 0.2},
                                    "reason": {"type": "string", "maxLength": 300}}}}}}

S6_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["transitions"],
             "properties": {"transitions": {"type": "array", "maxItems": 8, "items": {
                 "type": "object", "additionalProperties": False, "required": ["where", "intent", "reason"],
                 "properties": {"where": {"type": "string", "enum": ["nose_end", "tail_end", "windscreen_base",
                                                                    "roof_to_engine_cover", "wheel_arch_lip", "sill"]},
                                "intent": {"type": "string", "enum": ["G0", "G1", "G2", "sharp_crease"]},
                                "reason": {"type": "string", "maxLength": 300}}}}}}

S7_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["ambiguities"],
             "properties": {"ambiguities": {"type": "array", "maxItems": 8, "items": {
                 "type": "object", "additionalProperties": False, "required": ["id", "options"],
                 "properties": {"id": {"type": "string", "maxLength": 40},
                                "options": {"type": "array", "maxItems": 4, "items": {
                                    "type": "object", "additionalProperties": False,
                                    "required": ["choice", "plausibility", "reason"],
                                    "properties": {"choice": {"type": "string", "maxLength": 80},
                                                   "plausibility": {"type": "number", "minimum": 0, "maximum": 1},
                                                   "reason": {"type": "string", "maxLength": 300}}}}}}}}}

S8_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["issues"],
             "properties": {"issues": {"type": "array", "maxItems": 12, "items": {
                 "type": "object", "additionalProperties": False, "required": ["view", "description", "severity"],
                 "properties": {"view": {"type": "string", "enum": ["side", "top", "front", "rear", "model"]},
                                "description": {"type": "string", "maxLength": 300},
                                "severity": {"type": "string", "enum": ["info", "minor", "major"]}}}}}}


# ============================================================================================ stages
def s1_view_roles(ai, crops, cv_nose_left):
    """S1 (Muse Spark x 2 seeds): which end view is the front, which way the nose points. Gate: both seeds agree,
    the end views get opposite roles, and the nose direction agrees with the CV evidence (lower end of the top
    profile). Returns (decision dict, evidence)."""
    content = [{"type": "text", "text": (
        "These are four orthographic views of ONE object cut from a drawing sheet: a side view, a top (plan) view and "
        "two end views called A and B. Say which end view shows the FRONT (headlights, grille, windscreen) and which "
        "the REAR (tail lights, exhausts, number plate), and in the side and top views on which side (left or right of "
        "the image) the front / nose is. Name the object in a few words. Answer with the JSON object only.")}]
    for name, im in (("side view", crops["side"]), ("top view", crops["top"]), ("end view A", crops["end_a"]),
                     ("end view B", crops["end_b"])):
        content += [{"type": "text", "text": name + ":"}, {"type": "image_url", "image_url": {"url": _img_url(im)}}]
    answers, recs = [], []

    def one(seed):
        try:
            return ai.ask_json("S1_view_roles", f"seed{seed}", SPARK, content, S1_SCHEMA, seed=seed)
        except ModelUnavailable as e:
            return None, {"error": str(e)}
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(2) as pool:                  # the two seeds are independent readings: ask at once
        for a, r in pool.map(one, (1, 2)):
            if a is not None:
                answers.append(a)
            recs.append(r)
    ev = {"answers": answers, "cv_nose_left": cv_nose_left}
    ok = (len(answers) == 2 and all(a[k] == answers[0][k] for a in answers for k in ("end_a", "end_b", "side_nose", "top_nose"))
          and {answers[0]["end_a"], answers[0]["end_b"]} == {"front", "rear"}
          and answers[0]["side_nose"] == answers[0]["top_nose"] != "unknown"
          and (answers[0]["side_nose"] == "left") == bool(cv_nose_left))
    if ok:
        a = answers[0]
        return {"front_view": {"value": "end_a" if a["end_a"] == "front" else "end_b", "provenance": "inferred",
                               "by": "Muse Spark (2 seeds agree) + CV nose check", "evidence": a["evidence"]},
                "nose_left": {"value": a["side_nose"] == "left", "provenance": "inferred",
                              "by": "Muse Spark (2 seeds agree) and CV (lower end of the top profile) agree"},
                "object": a["object"]}, ev
    ev["gate"] = "failed: the two readings disagree, are incomplete, or contradict the CV nose direction"
    return None, ev


def s2_sam_checks(ai, crops, offsets, ink, wheels_px):
    """S2 (SAM 3.1): segment the views with concept prompts; gate every mask against the drawing (its outline must
    lie on ink, wheels must agree with the measured circles). Returns accepted detections per prompt (sheet px)."""
    out = {}
    jobs = [("side", "wheel"), ("side", "side mirror"), ("top", "side mirror"), ("end_rear", "exhaust pipe"),
            ("end_front", "headlight")]
    def seg(job):
        view, prompt = job
        if crops.get(view) is None:
            return job, None, None
        try:
            return job, ai.sam("S2_sam", f"{view}:{prompt}", crops[view], prompt), None
        except ModelUnavailable as e:
            return job, None, str(e)[:200]
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(len(jobs)) as pool:          # the SAM calls are independent: all at once
        done = list(pool.map(seg, jobs))
    for (view, prompt), res, err in done:
        if err:
            out[f"{view}:{prompt}"] = {"error": err}
            continue
        if res is None:
            continue
        objs, rec = res
        ox, oy, sc = offsets[view]
        acc = []
        for o in objs:
            s = o.get("_summary", o)
            b = s["box"]
            box = [ox + b[0] / sc, oy + b[1] / sc, ox + b[2] / sc, oy + b[3] / sc]
            gate, why = True, []
            if "mask" in o:                                           # live: outline-on-ink test on the real mask
                m = o["mask"]
                from scipy import ndimage as ndi
                edge = m & ~ndi.binary_erosion(m)
                ys, xs = np.nonzero(edge)
                X = np.clip(np.round(ox + xs / sc).astype(int), 0, ink.shape[1] - 1)
                Y = np.clip(np.round(oy + ys / sc).astype(int), 0, ink.shape[0] - 1)
                near = ndi.binary_dilation(ink, iterations=2)
                on = float(near[Y, X].mean()) if len(X) else 0.0
                s["outline_on_ink"] = round(on, 3)
                if on < 0.6:
                    gate = False
                    why.append(f"outline on ink {on:.2f} < 0.60")
            if s["confidence"] < 0.5:
                gate = False
                why.append(f"confidence {s['confidence']:.2f} < 0.5")
            if prompt == "wheel" and wheels_px:
                c = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, (box[2] - box[0] + box[3] - box[1]) / 4)
                d = min((np.hypot(c[0] - w["cx"], c[1] - w["cy"]), abs(c[2] / w["r"] - 1)) for w in wheels_px)
                s["vs_measured_circle"] = {"centre_px": round(float(d[0]), 1), "radius_rel": round(float(d[1]), 3)}
                if d[0] > 6 or d[1] > 0.08:
                    gate = False
                    why.append("does not agree with a measured wheel circle")
            acc.append({"box_sheet_px": [round(v, 1) for v in box], "confidence": s["confidence"],
                        "accepted": gate, "why_rejected": why, **{k: s[k] for k in ("outline_on_ink", "vs_measured_circle") if k in s}})
        out[f"{view}:{prompt}"] = {"objects": acc, "replayed": bool(rec.get("replayed"))}
    return out


def s3_region_labels(ai, view, overlay, n_regions, object_name):
    """S3: Muse Spark labels every numbered region of one view; Muse Wonder labels them independently. A label is
    ACCEPTED when both agree; if one model is unavailable the other's label is used and marked unconfirmed; when they
    disagree the region is AMBIGUOUS (both labels kept, not used for geometry)."""
    content = [{"type": "text", "text": (
        f"This is the {view} view of a {object_name} from an orthographic line drawing. The closed areas between the "
        f"drawn lines are tinted and numbered 0..{n_regions - 1}. For EVERY number say what that area is on the object, "
        f"choosing kind from the list: {', '.join(KINDS)}. 'body_panel' = painted body surface; use 'other' only if "
        "nothing fits. Answer with the JSON object only.")},
               {"type": "image_url", "image_url": {"url": _img_url(overlay, "PNG")}}]
    res = {}

    def ask(who, model):
        # labelling numbered areas is a lookup, not a reasoning task: low effort for both models (Muse Spark's default
        # effort is high, ~90-100 s per view; the two models and the four views run in parallel)
        try:
            a, rec = ai.ask_json("S3_region_labels", f"{view}:{who}", model, content, S3_SCHEMA, seed=1,
                                 effort="low", fallback=False, timeout=180)
            res[who] = {int(r["n"]): (r["kind"], float(r["confidence"])) for r in a["regions"] if r["n"] < n_regions}
        except ModelUnavailable as e:
            res[who] = {"_error": str(e)[:200]}
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda wm: ask(*wm), (("spark", SPARK), ("wonder", WONDER))))
    labels = {}
    for n in range(n_regions):
        sp = res.get("spark", {}).get(n)
        wo = res.get("wonder", {}).get(n)
        if sp and wo:
            if sp[0] == wo[0]:
                labels[n] = {"kind": sp[0], "status": "accepted", "by": "Muse Spark + Muse Wonder agree",
                             "confidence": round(min(sp[1], wo[1]), 2)}
            else:
                labels[n] = {"kind": None, "status": "ambiguous", "options": {"Muse Spark": sp[0], "Muse Wonder": wo[0]}}
        elif sp or wo:
            k = sp or wo
            labels[n] = {"kind": k[0], "status": "unconfirmed",
                         "by": ("Muse Spark" if sp else "Muse Wonder") + " only (the other model gave no answer)",
                         "confidence": round(k[1], 2)}
        else:
            labels[n] = {"kind": None, "status": "unlabelled"}
    errs = {k: v["_error"] for k, v in res.items() if isinstance(v, dict) and "_error" in v}
    return labels, errs


def s5_section_hypotheses(ai, crops, station_table, seeds=(1, 2)):
    """S5 (Muse Wonder, >= 2 samples): shape fractions of the body sections between the MEASURED extremes. The
    numbers are bounded by the schema; the caller builds every sample and keeps the one that reprojects best."""
    content = [{"type": "text", "text": (
        "You are a senior automotive surface designer. Below are the side, top, front and rear views of a car body "
        "drawing and a table of cross-section stations measured from it (x from the nose, mm; z_top / z_bot = top and "
        "bottom of the body at that station from the side view; y_max = half-width from the top view; cabin = whether "
        "the greenhouse exists there). These measured values are FIXED. For each station group (front_deck: ahead of "
        "the windscreen, cabin, rear_deck: behind the roof) give the shape fractions a designer would use between those "
        "extremes: crown_frac (rise of the top centre above the top edge, fraction of local height), deck_drop_frac "
        "(how far below the top centre the deck edge / shoulder sits, fraction of local height), sill_radius_frac "
        "(rounding of the lower body edge, fraction of local height), glass_bulge_frac (outward bulge of the side glass, "
        "fraction of the glass height; 0 for deck groups). One reason each. JSON only.\n" + station_table)}]
    for name in ("side", "top", "end_front", "end_rear"):
        content += [{"type": "text", "text": name + ":"}, {"type": "image_url", "image_url": {"url": _img_url(crops[name])}}]
    def one(seed):
        try:
            a, rec = ai.ask_json("S5_sections", f"seed{seed}", WONDER, content, S5_SCHEMA, seed=seed, effort="low",
                                 timeout=240)
            return {"seed": seed, "answer": a, "model": rec.get("model"), "fallback": rec.get("fallback")}
        except ModelUnavailable as e:
            return {"seed": seed, "error": str(e)[:200]}
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(len(seeds)) as pool:
        return list(pool.map(one, seeds))


def s6_transitions(ai, crops):
    content = [{"type": "text", "text": (
        "These are the side, top, front and rear views of a car drawing. For each body transition listed in the enum "
        "(nose_end, tail_end, windscreen_base, roof_to_engine_cover, wheel_arch_lip, sill) say the surface continuity a "
        "designer intends there: G0 (meets at an edge), G1 (tangent), G2 (curvature continuous) or sharp_crease (a "
        "deliberate crease line drawn on the sheet). One reason each. JSON only.")}]
    for name in ("side", "top", "end_front", "end_rear"):
        content += [{"type": "text", "text": name + ":"}, {"type": "image_url", "image_url": {"url": _img_url(crops[name])}}]
    try:
        a, rec = ai.ask_json("S6_transitions", "all", WONDER, content, S6_SCHEMA, seed=1, effort="low", timeout=180)
        return a["transitions"], rec.get("model")
    except ModelUnavailable as e:
        return {"error": str(e)[:200]}, None


def s7_ambiguities(ai, crops, items):
    content = [{"type": "text", "text": (
        "A car is being rebuilt as CAD from this drawing. These questions cannot be settled by measurement alone. For "
        "each, list the plausible interpretations with a plausibility 0..1 and one reason. Do not pick one for the "
        "engineer. JSON only.\n" + "\n".join(f"- id {k}: {q}" for k, q in items))}]
    for name in ("side", "end_front", "end_rear"):
        content += [{"type": "text", "text": name + ":"}, {"type": "image_url", "image_url": {"url": _img_url(crops[name])}}]
    try:
        a, rec = ai.ask_json("S7_ambiguities", "all", WONDER, content, S7_SCHEMA, seed=1, effort="low", timeout=180)
        return a["ambiguities"], rec.get("model")
    except ModelUnavailable as e:
        return {"error": str(e)[:200]}, None


def s8_verify(ai, overlays, key):
    content = [{"type": "text", "text": (
        "Each image overlays a 3D CAD model's projection (cyan outline) on the original drawing view (grey). Red = "
        "drawn but not covered by the model, magenta = model where the drawing has nothing. List visible problems "
        "(view, description, severity). This is advisory: the pass/fail numbers are computed separately. JSON only.")}]
    for name, im in overlays.items():
        content += [{"type": "text", "text": name + ":"}, {"type": "image_url", "image_url": {"url": _img_url(im)}}]
    try:
        a, rec = ai.ask_json("S8_verify", key, SPARK, content, S8_SCHEMA, seed=1, timeout=120)
        return a["issues"]
    except ModelUnavailable as e:
        return {"error": str(e)[:200]}
