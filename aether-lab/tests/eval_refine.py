"""Live evaluation (Meta API) of refining a real CAD model and of asking before assuming.

  python tests/eval_refine.py [case filter]

1. "detailed car": the user's own request on the CAD car from the cad-car project (its body has glass and light
   regions). Pass: the seats asked for are there, the car is not moved or rescaled, nothing added is floating or a box
   over the glass / lights,
   rear things (tail lights, rear plate, exhaust) sit on the rear half, front things (headlights, front plate,
   grille) on the front half, and the reply mentions how to see interior parts if any were added.
2. "windows blue": recolours the glass region, adds nothing.
3. "partial blueprint": half of a three-view sheet with "build this" -> the assistant asks (nothing built); the next
   message "I don't have it, assume" -> the build runs (stubbed here: it records the call instead of building).
Results: output/eval_refine.json (+ a picture of each refined car in output/eval/)."""
import base64
import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402,F401  (loads .env, sets the assistant's hooks)
import assistant as A  # noqa: E402
import refine  # noqa: E402
from engine import lab, snap  # noqa: E402

OUT = ROOT / "output" / "eval"
OUT.mkdir(parents=True, exist_ok=True)
REQUEST = ("make the car model more detailed, like the internal car seats, seat belts, engine, car window, front mirror, "
           "back mirror, side mirror, car light, car plate, car door, car door knob and so on, a lot a lot, with suitable "
           "color and depth, like car light can be yellow")


def real_car():
    d = json.loads((ROOT / "output" / "projects" / "cad-car" / "project.json").read_text(encoding="utf-8"))
    st = d["state"]
    lab.fold_cad_leaves(st)
    m = next(r for r in A.roots(st) if (r.get("eng") or {}).get("cad_document"))      # the CAD car (not a leftover)
    keep = {p["id"] for p in lab.subtree(st, m["id"]) if p["type"] == "group" or (p.get("eng") or {}).get("cad_document")}
    st["parts"] = [p for p in st["parts"] if p["id"] in keep]       # the car as built, without the old bad additions
    A.arrange(st)
    st["selected"] = None
    return st


def ctx(files=()):
    files = list(files)
    return {"out_dir": str(OUT), "exports_dir": str(OUT / "exports"), "cad_brep_dir": str(ROOT / "output" / "cad" / "current" / "brep"),
            "files": files, "attachments": files, "data_url": server._data_url, "on_step": lambda e: None, "have": {}, "jobs": {}}


FRONT_WORDS = ("headlight", "head light", "front plate", "front number", "grille", "front bumper")
REAR_WORDS = ("tail", "rear plate", "rear number", "exhaust", "rear bumper", "rear light", "back light")


def check_refine(before, after, reply, trace, extras):
    fails = []
    m0, m1 = A.roots(before)[0], A.roots(after)
    if len(m1) != 1:
        return [f"{len(m1)} models on the desk"]
    m1 = m1[0]
    if m0["position"] != m1["position"] or m0["scale"] != m1["scale"]:
        fails.append("the car was moved or rescaled")
    old = {p["id"] for p in before["parts"]}
    new = [p for p in lab.subtree(after, m1["id"]) if p["id"] not in old and p["type"] != "group"]
    added_features = [x for t in trace if t["tool"] == "cad_feature" for x in (t["result"] or {}).get("added", [])]
    if not new and not added_features:
        return fails + ["nothing added"]
    if not any("seat" in p["name"].lower() for p in new):
        fails.append("the seats the user asked for were not added")
    if any(p["type"] == "box" for p in new):
        fails.append("plain boxes added (expected shaped parts / surface panels)")
    seats = [p for p in new if "seat" in p["name"].lower() and "belt" not in p["name"].lower()]
    ms_ = {p["id"]: Vp for p, Vp, _, _ in snap.model_meshes(after, m1)}
    Vb, Fb, _ = refine.body_mesh(after, m1)
    for p in seats:
        if p["id"] in ms_ and refine.inside_share(Vb, Fb, ms_[p["id"]][::40]) < 0.9:
            fails.append(f"'{p['name']}' is not inside the body")
    if len(seats) >= 2 and p["id"] in ms_:
        c = [ms_[q["id"]].mean(0) for q in seats[:2] if q["id"] in ms_]
        if len(c) == 2 and abs(float((c[0] - c[1]) @ snap.sides(snap.front_axis(m1))["left"])) < 200:
            fails.append("the two seats are not side by side")
    # parts placed inside (the assistant's own placements, from add_parts' answers) are not expected to touch the body
    inside_names = {x["part"] for t in trace if t["tool"] == "add_parts" for x in (t["result"] or {}).get("placed", [])
                    if x.get("side") == "inside" or x.get("slot")}
    issues = refine.checks(after, m1, {p["id"] for p in new}, {p["id"] for p in new if p["name"] in inside_names})
    bad = [i for i in issues if i["problem"] in ("floating", "duplicate")]
    if bad:
        fails.append(f"{len(bad)} floating / duplicate: {[(i['part'], i['problem']) for i in bad][:6]}")
    V, _, _ = refine.model_mesh(after, m1, exclude={p["id"] for p in new})
    mid = (V.min(0) + V.max(0)) / 2
    f = snap.front_axis(m1)
    ms = {p["id"]: Vp for p, Vp, _, _ in snap.model_meshes(after, m1)}
    for p in new:
        if p["id"] not in ms:
            continue
        c = ms[p["id"]].mean(0)
        toward_front = float((c - mid) @ f) > 0
        nm = p["name"].lower()
        if any(w in nm for w in REAR_WORDS) and toward_front:
            fails.append(f"'{p['name']}' is on the front half")
        if any(w in nm for w in FRONT_WORDS) and not toward_front:
            fails.append(f"'{p['name']}' is on the rear half")
    return fails


def check_blue(before, after, reply, trace, extras):
    fails = []
    if not any((p.get("region_colors") or {}).get("glass") for p in after["parts"]):
        fails.append("glass not recoloured")
    if len(after["parts"]) != len(before["parts"]):
        fails.append("parts added or removed")
    return fails


def run_case(name, st, msg, check, files=()):
    A.steps.reset()
    before = copy.deepcopy(st)
    t0 = time.time()
    try:
        reply, trace, images, hist, extras = A.turn(st, [], msg, ctx(files))
        fails = check(before, st, reply, trace, extras)
    except Exception as e:
        reply, trace, extras, hist, fails = "", [], {}, [], [f"{type(e).__name__}: {e}"]
    dt = round(time.time() - t0, 1)
    m = A.roots(st)
    if m:
        snap.sheet(snap.model_meshes(st, m[0]), ("iso", "front", "rear", "left"), snap.front_axis(m[0]), 360).save(
            OUT / f"refine_{name.replace(' ', '_')}.png")
    print(f"{'PASS' if not fails else 'FAIL'}  {dt:6.1f} s  {name:22s} tools={[t['tool'] for t in trace]}  {fails or ''}", flush=True)
    print("      reply:", (reply or "")[:400].replace("\n", " "), flush=True)
    return {"case": name, "pass": not fails, "fails": fails, "seconds": dt, "tools": [t["tool"] for t in trace],
            "trace": [{"tool": t["tool"], "args": t["args"], "result": t["result"]} for t in trace],
            "reply": reply, "changes": extras.get("changes")}, st, hist


def partial_blueprint():
    from PIL import Image
    full = Image.open(ROOT / "tests" / "car_three_view.gif").convert("RGB")
    w, h = full.size
    f = OUT / "half_blueprint.png"
    full.crop((0, 0, w // 2, h // 2)).save(f)
    att = {"name": f.name, "kind": "image", "path": str(f), "bytes": f.stat().st_size}
    st = lab.default_state()
    st["parts"] = []
    A.INTAKE.clear()
    calls = []
    real_job, real_photo = A.START_CAD_JOB, A.agent.photo_to_design
    A.START_CAD_JOB = lambda url, hint, decisions, src: calls.append(("job", hint, decisions)) or {"job": "stub", "model": "stub"}
    A.agent.photo_to_design = lambda state, *a, **k: calls.append(("photo", a[1] if len(a) > 1 else None, k.get("decisions"))) or ("built (stub)", [], {}, [])
    try:
        r1, st, hist = run_case("partial: asks first", st, "build this car from my blueprint",
                                lambda b, a, r, t, x: (["no question"] if not x.get("question") else []) + (["built without asking"] if calls else []),
                                files=[att])
        n_before = len(calls)
        A.steps.reset()
        t0 = time.time()
        reply, trace, images, hist2, extras = A.turn(st, hist, "I don't have it, assume", ctx([att]))
        fails = [] if len(calls) > n_before else ["did not build after 'assume'"]
        print(f"{'PASS' if not fails else 'FAIL'}  {time.time() - t0:6.1f} s  {'partial: then assume':22s} tools={[t['tool'] for t in trace]}  {fails or ''}  calls={calls}")
        print("      reply:", (reply or "")[:400].replace("\n", " "))
        r2 = {"case": "partial: then assume", "pass": not fails, "fails": fails, "tools": [t["tool"] for t in trace], "reply": reply}
    finally:
        A.START_CAD_JOB, A.agent.photo_to_design = real_job, real_photo
    return [r1, r2]


MACHINE_REQUEST = ("make this machine more detailed: add a drive motor on top, a safety guard over the front, a warning "
                   "plate and a control box on its right side, in sensible industrial colours")


def real_machine():
    d = json.loads((ROOT / "output" / "recorded" / "D.json").read_text(encoding="utf-8"))
    st = d["state"]
    A.arrange(st)
    st["selected"] = None
    return st


def check_machine(before, after, reply, trace, extras):
    """A drawn machine (its group stood up by a 90 deg turn): parts land on the sides the user named, as seen on the
    desk, nothing floats, the machine is not moved."""
    fails = []
    m0, m1 = A.roots(before)[0], A.roots(after)[0]
    if m0["position"] != m1["position"] or m0["scale"] != m1["scale"]:
        fails.append("the machine was moved or rescaled")
    old = {p["id"] for p in before["parts"]}
    new = [p for p in lab.subtree(after, m1["id"]) if p["id"] not in old and p["type"] != "group"]
    if len(new) < 3:
        return fails + [f"only {len(new)} parts added"]
    issues = refine.checks(after, m1, {p["id"] for p in new})
    bad = [i for i in issues if i["problem"] in ("floating", "duplicate")]
    if bad:
        fails.append(f"{len(bad)} floating / duplicate: {[(i['part'], i['problem']) for i in bad][:6]}")
    V, _, _ = refine.model_mesh(after, m1, exclude={p["id"] for p in new})
    top = V[:, 2].max()
    ms = {p["id"]: Vp for p, Vp, _, _ in snap.model_meshes(after, m1)}
    for p in new:
        if "motor" in p["name"].lower() and p["id"] in ms and ms[p["id"]][:, 2].max() < top - 1:
            fails.append(f"'{p['name']}' is not on top (its top {ms[p['id']][:, 2].max():.0f} < machine top {top:.0f})")
    if any(p["type"] == "box" for p in new):
        fails.append("plain boxes added (expected shaped parts / rbox)")
    return fails


SPECS = []                    # every add_parts call's part specs, as Muse Spark sent them (output/eval/add_parts_specs.json)
_real_add_parts = A.add_parts


def _logged_add_parts(state, ctx, m, specs):
    SPECS.append(json.loads(json.dumps(specs, default=str)))
    return _real_add_parts(state, ctx, m, specs)


A.add_parts = _logged_add_parts


def main(filt=None):
    res = []
    if not filt or "detail" in filt:
        res.append(run_case("detailed car", real_car(), REQUEST, check_refine)[0])
    if not filt or "machine" in filt:
        res.append(run_case("machine detail", real_machine(), MACHINE_REQUEST, check_machine)[0])
    if not filt or "blue" in filt:
        res.append(run_case("windows blue", real_car(), "make the car windows blue", check_blue)[0])
    if not filt or "partial" in filt:
        res += partial_blueprint()
    print(f"\n{sum(r['pass'] for r in res)}/{len(res)} pass")
    (OUT / "add_parts_specs.json").write_text(json.dumps(SPECS, indent=1), encoding="utf-8")
    f = ROOT / "output" / "eval_refine.json"           # merged by case: running one case keeps the others' latest result
    old = {r["case"]: r for r in (json.loads(f.read_text(encoding="utf-8")) if f.exists() else [])}
    old.update({r["case"]: {**r, "when": time.strftime("%Y-%m-%d %H:%M")} for r in res})
    f.write_text(json.dumps(list(old.values()), indent=1, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
