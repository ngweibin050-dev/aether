"""K1, D1, D2, M1, M3, M7: kernel smoke tests, document schema, persistence, AI schema gate, no code execution."""
import copy
import json
import re
from pathlib import Path

import numpy as np
import pytest

from cad import ai as AI
from cad import kernel as K
from cad import validate as Vd
from cad.document import Document, DocumentError, validate_schema
from cad.ops import OPS

ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------------------------------------ K1
def test_K1_kernel_primitives_valid():
    cyl = K.cylinder((0, 0, 0), (0, 0, 1), 10, 20)
    r = Vd.check_solid(cyl)
    assert r["valid"] and abs(r["volume_mm3"] - np.pi * 100 * 20) < 1e-3          # report rounds to 0.001 mm^3
    prof = [(5, -5), (12, -5), (12, 5), (5, 5)]
    ring = K.revolve_profile_y(prof, (0, 0, 0))
    assert Vd.check_solid(ring)["valid"]
    cut, _ = K.boolean("cut", K.cylinder((0, -10, 0), (0, 1, 0), 20, 20), ring, "t")
    assert Vd.check_solid(cut)["valid"]


def test_K1_skin_section_body_valid_and_symmetric():
    xs = np.linspace(0, 1000, 8)
    st = []
    for x in xs:
        h = 200 + 100 * np.sin(np.pi * x / 1000)
        w = 300 + 80 * np.sin(np.pi * x / 1000)
        half = [(t * w, 0.0) for t in np.linspace(0, 1, 5, endpoint=False)] + \
               [(w, h * t) for t in np.linspace(0, 1, 6, endpoint=False)] + [(w * (1 - t), h + 20 * (1 - (1 - t) ** 2)) for t in np.linspace(0, 1, 6)]
        st.append((float(x), half))
    sol, info = K.skin_body_v3(st)
    r = Vd.check_solid(sol)
    assert r["valid"], r
    bb = r["bbox_mm"]
    assert abs(bb[1] + bb[4]) < 1e-6, "body must be exactly symmetric about Y = 0"
    assert info["overshoot_pct_of_size"][1] < 3


def test_K1_skin_rejects_unordered_stations():
    half = [(0, 0), (100, 0), (100, 50), (50, 80), (0, 90)]
    with pytest.raises(K.KernelError):
        K.skin_body_v3([(0.0, half), (100.0, half), (50.0, half)])


def test_K1_section_constraints_enforced():
    k = {"x": 0, "z_bot": 100, "z_top": 300, "y_max": 400, "z_max": 350, "y_sh": 300, "z_sh": 250, "y_re": 200,
         "z_re": 280, "r_low": 20, "glass_bulge": 0}
    with pytest.raises(K.KernelError, match="out of order"):
        K.section_keypoints(k, np.array([0, 500.0]), np.array([1.0, 1.0]))


# ------------------------------------------------------------------------------------------------ D1 / D2
def _tiny_doc():
    d = Document.new({"file": "t"}, "tiny")
    d["parameters"] = {"r": {"provenance": "assumed", "unit": "mm", "value": 10.0},
                       "h": {"provenance": "derived", "unit": "mm", "rel": {"kind": "linear", "terms": [["r", 2.0]], "const": 0.0}}}
    d["features"] = [{"id": "tip", "op": "exhaust_tip", "inputs": [], "params": {"y": 0, "z": 0, "r": {"$p": "r"}, "wall": 1,
                                                                                 "x0": 0, "x1": {"$p": "h"}}}]
    d["components"] = [{"id": "c", "name": "c", "kind": "exhaust_tip", "output": "tip"}]
    return d


@pytest.mark.parametrize("mutate,match", [
    (lambda d: d.update(schema="nope"), "schema"),
    (lambda d: d["features"][0].update(op="exec_python"), "unknown operation"),
    (lambda d: d["features"][0]["params"].update(r={"$p": "missing"}), "unknown parameter"),
    (lambda d: d["features"][0]["params"].update(r={"$eval": "1+1"}), "unknown reference form"),
    (lambda d: d["parameters"]["r"].update(provenance="trust_me"), "provenance"),
    (lambda d: d["parameters"]["h"]["rel"].update(kind="python"), "rel.kind"),
    (lambda d: d["features"][0].update(inputs=["later"]), "earlier feature"),
    (lambda d: d["parameters"]["r"].update(value=float("nan")), "finite"),
])
def test_D1_schema_rejects(mutate, match):
    d = _tiny_doc()
    mutate(d)
    with pytest.raises(DocumentError, match=match):
        validate_schema(d, OPS)


def test_D1_relation_cycle_rejected():
    d = _tiny_doc()
    d["parameters"]["r"] = {"provenance": "derived", "unit": "mm", "rel": {"kind": "linear", "terms": [["h", 1.0]], "const": 0}}
    doc = Document(d, OPS)
    with pytest.raises(DocumentError, match="cycle"):
        doc.param_values()


def test_D2_save_reopen_identical(tmp_path):
    doc = Document(_tiny_doc(), OPS)
    st = doc.recompute()
    assert st["state"] == "ok"
    doc.save(tmp_path / "t.aethercad")
    doc2 = Document.load(tmp_path / "t.aethercad", OPS)
    st2 = doc2.recompute()
    assert st2["param_hash"] == st["param_hash"]
    assert abs(Vd.mass(doc2.shapes["tip"])["volume_mm3"] - Vd.mass(doc.shapes["tip"])["volume_mm3"]) < 1e-9


def test_D2_failed_edit_rolls_back(tmp_path):
    doc = Document(_tiny_doc(), OPS)
    doc.recompute()
    before = Vd.mass(doc.shapes["tip"])["volume_mm3"]
    st = doc.set_param("r", 0.5)                      # wall 1 mm > radius 0.5 mm: the tube cannot be built
    assert st["state"] == "failed" and st.get("rolled_back_to") == "ok"
    assert doc.data["parameters"]["r"]["value"] == 10.0
    assert abs(Vd.mass(doc.shapes["tip"])["volume_mm3"] - before) < 1e-9
    assert doc.data["history"][-1]["rolled_back"] is True


# ------------------------------------------------------------------------------------------------ M1 / M3
@pytest.mark.parametrize("bad", [
    {"regions": [{"n": 0, "kind": "window", "confidence": 0.9}]},                       # not in the enum
    {"regions": [{"n": 0, "kind": "roof", "confidence": 1.7}]},                          # out of range
    {"regions": [{"n": 0, "kind": "roof", "confidence": 0.9, "code": "import os"}]},     # extra field
    {"regions": [{"n": 99, "kind": "roof", "confidence": 0.9}]},                         # index out of range
    {"regions": "__import__('os')"},                                                     # wrong type
])
def test_M1_schema_gate_rejects(bad):
    with pytest.raises(ValueError):
        AI._check(bad, AI.S3_SCHEMA)


def test_M1_schema_gate_accepts_valid():
    AI._check({"regions": [{"n": 3, "kind": "side_window", "confidence": 0.8}]}, AI.S3_SCHEMA)


def test_M3_no_stored_answer_in_replay_is_explicit():
    ai = AI.AI([], mode="replay")
    with pytest.raises(AI.ModelUnavailable):
        ai.ask_json("S3_region_labels", "x", AI.SPARK, [{"type": "text", "text": "q"}], AI.S3_SCHEMA)


def test_M3_replay_only_for_identical_prompt():
    rec = {"stage": "S", "key": "k", "ok": True, "prompt_hash": "aaaa", "response": {"regions": []}}
    ai = AI.AI([rec], mode="replay")
    with pytest.raises(AI.ModelUnavailable):           # same stage and key, different prompt -> not reused
        ai.ask_json("S", "k", AI.SPARK, [{"type": "text", "text": "a different question"}], AI.S3_SCHEMA)


def test_M3_s1_gate_failure_degrades_to_unresolved():
    dec, ev = AI.s1_view_roles(AI.AI([], mode="replay"), {k: __import__("PIL.Image", fromlist=["new"]).new("RGB", (8, 8))
                                                         for k in ("side", "top", "end_a", "end_b")}, True)
    assert dec is None and "gate" in ev


# ------------------------------------------------------------------------------------------------ M7
def test_M7_no_code_execution_of_model_output():
    """Static check: no eval / exec / compile in the CAD package or agent.py; subprocess only in the STEP round trip
    (a fixed command) and nowhere that touches model output."""
    files = list((ROOT / "cad").glob("*.py")) + [ROOT / "agent.py"]
    for f in files:
        src = f.read_text(encoding="utf-8")
        for pat in (r"(?<![\w.])eval\(", r"(?<![\w.])exec\(", r"(?<![\w.])compile\(", r"__import__\(\s*[a-z_]+\s*\)"):
            assert not re.search(pat, src), f"{f.name}: {pat}"
    for f in (ROOT / "cad").glob("*.py"):
        if "subprocess" in f.read_text(encoding="utf-8"):
            assert f.name in ("export.py",), f"subprocess used in {f.name}"
