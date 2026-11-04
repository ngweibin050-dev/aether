"""Intake: before a drawing or photo is built, find out what is MISSING for a reliable 3D model, so the assistant asks
the user instead of silently assuming (and assumes only when the user cannot say).

assess(data_url, user_text) combines
- a measurement (vision.upload_kind: how many separate views the sheet holds, whether their sizes agree), and
- Muse Spark reading the image like an engineer taking a job: what the object is, which views are there, whether any
  dimension or scale is given, what is cut off or hidden, and for each gap whether it is critical (the 3D shape would
  be a guess) and the one short question that closes it, with 2-3 concrete answers.

The gate is in code (assistant.build_from_drawing): a drawing with a critical gap is built only after the user has
been asked once (ask_user); the user's answer, or "assume", is what lets the build go ahead. What the user answered
(e.g. a real length) goes into the build; what was still assumed is listed with the result."""
import json

import agent

ASSUME = "I don't have it, assume"

SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["object", "kind", "views", "has_dimension", "complete_enough", "missing"],
          "properties": {
              "object": {"type": "string"},
              "kind": {"type": "string", "enum": ["three_view", "machine", "part", "unclear"]},
              "views": {"type": "array", "items": {"type": "string", "enum": [
                  "side", "top", "front", "rear", "isometric", "section", "detail", "photo"]}},
              "has_dimension": {"type": "boolean"},
              "complete_enough": {"type": "boolean"},
              "missing": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                     "required": ["what", "why", "critical", "question", "options"],
                                                     "properties": {
                                                         "what": {"type": "string"}, "why": {"type": "string"},
                                                         "critical": {"type": "boolean"},
                                                         "question": {"type": "string"},
                                                         "options": {"type": "array", "items": {"type": "string"}}}}}}}

PROMPT = """You are the engineer who takes in a job before a 3D model is built from this image. The user wrote:
"{text}"
A measurement of the sheet found {views} separate view(s){agree}.

Decide what is MISSING for a reliable 3D model, the way you would ask a client before starting:
- views: a 3D model of one object from drawings needs at least a side view and a top view and an end view (front or
  rear). One view of a machine (a patent figure) is enough for a mechanism, not for its exact 3D shape.
- size: is there any dimension, scale bar or known size? Without one, every size is a guess.
- identity: is it clear what the object is? Is the drawing cut off, or only PART of something bigger?
- hidden: is something important hidden or not drawn (inside, the back)?
For each gap: critical = true only if without it the 3D shape itself would be a guess (a missing view, part of the
object cut off); a missing real size is critical = false when the shape is fully drawn (the model can be scaled
later). Write ONE short question (max 20 words) per gap, and 2-3 concrete answers the user can click (e.g. a typical
size: "about 4.5 m long (typical car)"). complete_enough: true when nothing critical is missing.
Answer with the JSON object only."""


def assess(data_url, user_text=""):
    import vision
    kind, ev = vision.upload_kind(data_url)
    n = ev.get("views_found", 1 if kind != "part" else 0)
    agree = f", sizes agreeing within {ev['size_disagreement_pct']} %" if "size_disagreement_pct" in ev else ""
    content = [{"type": "text", "text": PROMPT.format(text=(user_text or "")[:400], views=n, agree=agree)},
               {"type": "image_url", "image_url": {"url": data_url}}]
    obj, meta = agent._spark_json(content, SCHEMA, "intake", timeout=90, effort="low")
    miss = [m for m in obj.get("missing") or [] if m.get("question")][:4]
    # the measurement overrules the reading: a "three-view" sheet with fewer than 3 separate views lacks a view
    if obj.get("kind") == "three_view" and n < 3 and not any("view" in m["what"].lower() for m in miss):
        miss.insert(0, {"what": "a view", "why": f"only {n} separate view(s) found on the sheet; a 3D shape needs side, top "
                        "and an end view", "critical": True,
                        "question": "Can you add the missing view (side, top or front)?",
                        "options": ["I'll upload it", "Build from what is there"]})
    for m in miss:
        m["options"] = [o for o in (m.get("options") or [])][:3]
        if ASSUME not in m["options"]:
            m["options"].append(ASSUME)
    critical = [m for m in miss if m.get("critical")]
    return {"object": obj.get("object"), "kind_read": obj.get("kind"), "kind_measured": kind, "views": obj.get("views"),
            "views_found": n, "has_dimension": obj.get("has_dimension"), "missing": miss,
            "critical_missing": len(critical), "ready": not critical, "seconds": meta.get("s")}


def question_for(a):
    """The one question to put to the user (ask_user): the critical gaps first, at most two in one message."""
    gaps = sorted(a["missing"], key=lambda m: not m.get("critical"))[:2]
    if not gaps:
        return None
    q = " ".join(g["question"] for g in gaps)
    opts = []
    for g in gaps:
        for o in g["options"]:
            if o not in opts:
                opts.append(o)
    opts = [o for o in opts if o != ASSUME][:3] + [ASSUME]
    return {"question": q, "options": opts, "gaps": [{"what": g["what"], "why": g["why"]} for g in gaps]}


def dumps(a):
    return json.dumps(a, default=str)
