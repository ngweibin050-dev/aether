"""O, B, W, C, R, V, S, P, G, T, M2, M4, M6 on the car three-view sheet (replayed model answers)."""
import copy
import json
import struct

import numpy as np
import pytest

from cad import pipeline as P
from cad import validate as Vd
from cad.document import Document
from cad.ops import OPS

from .conftest import FIX, SHEET, need_sheet

pytestmark = need_sheet


# ------------------------------------------------------------------------------------------------ O (observations)
def test_O1_four_views(obs_aux):
    obs, _ = obs_aux
    assert set(obs["views"]) == {"side", "top", "end_a", "end_b"}
    ex = obs["views"]["side"]["extent"]
    assert abs(ex[0] - 91) <= 3 and abs(ex[2] - 800) <= 3


def test_O3_scale_fit_reports_conflict(obs_aux):
    obs, _ = obs_aux
    f = obs["fit"]
    assert abs(f["ratio_side_over_top"] - 1) < 0.01            # length side vs plan within 1 %
    assert 1.02 < f["ratio_side_over_end"] < 1.07              # the ~4-5 % end-view conflict is measured, not hidden


def test_O4_wheels(obs_aux):
    obs, _ = obs_aux
    w = obs["side"]["wheels"]
    assert len(w) == 2
    assert abs(w[0]["r"] - 53) <= 2 and abs(w[1]["r"] - 57) <= 2
    assert w[0]["arch"] and w[1]["arch"]
    assert w[0]["spokes"] == 10 and w[1]["spokes"] == 10      # 5 Y-spokes = 10 arms


def test_O5_plan_mirror_removed(obs_aux):
    obs, _ = obs_aux
    assert obs["top"]["mirror"] is not None
    half = np.array(obs["top"]["half_px"])
    assert half[:, 1].max() < obs["top"]["mirror"]["half_out_px"] - 5   # the mirror is not in the body outline


def test_O6_inventory_components(built):
    doc, res, _ = built
    kinds = {c["kind"] for c in doc.data["components"]}
    assert {"body_shell", "tyre", "rim", "mirror", "exhaust_tip", "wheel_assembly"} <= kinds
    assert sum(1 for c in doc.data["components"] if c["kind"] == "exhaust_tip") == 4
    feats = {f["id"] for f in doc.data["features"]}
    for fid in ("body.imprint_side_window_side", "body.imprint_windscreen_top", "body.imprint_door_side",
                "body.imprint_headlight_front", "body.imprint_tail_light_rear", "body.pocket_air_intake_side",
                "body.pocket_licence_plate_rear", "body.pocket_louvre_top"):
        assert fid in feats, fid


# ------------------------------------------------------------------------------------------------ B / W / C
def test_B3_body_valid(built):
    doc, _, _ = built
    body = doc.component_shape("body")
    r = Vd.check_solid(body)
    assert r["valid"], r
    assert r["solids"] == 1 and r["free_edges"] == 0 and r["far_point_outside"]
    bb = r["bbox_mm"]
    assert abs(bb[1] + bb[4]) < 1e-3, "symmetric body"


def test_B2_loft_fidelity_at_stations(built):
    """Profile fidelity: at every station the body's top and bottom on the centreline equal the station's z_top /
    z_bot parameters (the sections lie ON the surface)."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT
    from OCP.gp import gp_Pnt
    doc, _, _ = built
    PV = doc.param_values()
    skin = doc.shapes["body.skin"]
    sids = sorted({k.split(".")[0] for k in PV if k.startswith("st") and k.endswith(".z_top")})[1:-1]
    for sid in sids[::4]:
        x, zt, zb = PV[f"{sid}.x"], PV[f"{sid}.z_top"], PV[f"{sid}.z_bot"]
        st = lambda z: BRepClass3d_SolidClassifier(skin, gp_Pnt(x, 0.0, z), 1e-4).State()
        assert st(zt - 0.5) == TopAbs_IN and st(zt + 0.5) == TopAbs_OUT, sid
        assert st(zb + 0.5) == TopAbs_IN and st(zb - 0.5) == TopAbs_OUT, sid


def test_W1_wheels_are_revolved_solids(built):
    doc, _, _ = built
    PV = doc.param_values()
    for cid in ("tyre_fr", "rim_fr", "tyre_rl", "rim_rl"):
        r = Vd.check_solid(doc.component_shape(cid), argument_analysis=False)
        assert r["valid"], cid
    assert PV["r_tyre_r"] > PV["r_tyre_f"] * 1.03                  # the drawing's rear tyres are bigger: kept
    rim = Vd.check_solid(doc.component_shape("rim_fr"), argument_analysis=False)
    assert rim["faces"] > 30                                      # barrel + 5 Y-spokes + bores: not a cylinder
    ops = {f["op"] for f in doc.data["features"] if f.get("component") in ("tyre_fr", "rim_fr")}
    assert ops == {"tyre", "rim"}


def test_C1_small_components_valid(built):
    doc, _, _ = built
    for c in doc.data["components"]:
        if c["kind"] in ("mirror", "exhaust_tip"):
            assert Vd.check_solid(doc.component_shape(c["id"]), argument_analysis=False)["valid"], c["id"]


# ------------------------------------------------------------------------------------------------ T1 / M2 / M4 / M6
def test_T1_every_parameter_traceable(built):
    doc, _, _ = built
    for pid, p in doc.data["parameters"].items():
        assert p["provenance"] in ("measured", "derived", "inferred", "assumed", "unresolved", "user_confirmed")
        if p.get("unit") == "mm" and p["provenance"] == "measured":
            assert doc.data["decisions"]["overall_length_mm"]["provenance"] == "user_confirmed", \
                f"{pid}: a mm value cannot be 'measured' while the scale is assumed"
    assert doc.data["parameters"]["overall_length"]["provenance"] == "assumed"
    assert all(a["class"] in ("measured", "derived", "inferred", "assumed") for a in doc.data["assumptions"])


def test_M2_models_cannot_set_measured_extremes(built):
    """Station top / bottom / width come from the measured curves (sample relations), never from a model answer."""
    doc, _, _ = built
    for pid, p in doc.data["parameters"].items():
        if pid.startswith("st") and pid.split(".")[1] in ("z_top", "z_bot", "y_max"):
            assert p["rel"]["kind"] == "sample" and p["rel"]["obs"].startswith("obs.field.")


def test_M4_replay_is_deterministic(built, tmp_path):
    doc, _, _ = built
    stored = json.loads(FIX.read_text())["hypotheses"]
    doc2, _ = P.build(str(SHEET), str(tmp_path), stored=stored, ai_mode="replay", log=lambda m: None)
    assert doc2.data["status"]["param_hash"] == doc.data["status"]["param_hash"]
    v1 = Vd.mass(doc.component_shape("body"))["volume_mm3"]
    v2 = Vd.mass(doc2.component_shape("body"))["volume_mm3"]
    assert abs(v1 - v2) < 1e-6 * v1


def test_M6_section_hypotheses_scored_not_trusted(built):
    doc, _, _ = built
    s5 = doc.data["pipeline_report"]["S5"]
    assert "reprojection" in s5["rule"]
    scores = {c["name"]: c["score_mean_iou"] for c in s5["candidates"]}
    assert scores[s5["chosen"]] == max(scores.values())


# ------------------------------------------------------------------------------------------------ R (recompute)
def _fresh(built):
    doc, _, _ = built
    d2 = Document(copy.deepcopy(doc.data), OPS)
    d2._cache = dict(doc._cache)                       # share the B-rep cache: only changed features rebuild
    st = d2.recompute()
    assert st["state"] == "ok"
    return d2


def test_R1_wheelbase_edit_moves_dependents(built):
    d = _fresh(built)
    PV0 = d.param_values()
    v0 = Vd.mass(d.component_shape("body"))["volume_mm3"]
    xr0 = Vd.check_solid(d.component_shape("tyre_rr"), argument_analysis=False)["centre_mm"][0]
    st = d.set_param("wheelbase", PV0["wheelbase"] * 1.05, validate=P._validate_fast)
    assert st["state"] == "ok", st
    PV1 = d.param_values()
    dx = PV1["rear_axle_x"] - PV0["rear_axle_x"]
    assert dx > 100
    xr1 = Vd.check_solid(d.component_shape("tyre_rr"), argument_analysis=False)["centre_mm"][0]
    assert abs((xr1 - xr0) - dx) < 0.5                                  # the rear wheel moved with its datum
    assert Vd.mass(d.component_shape("body"))["volume_mm3"] > v0         # the body stretched between the axles
    assert st["validation"]["all_valid"]
    assert d.data["history"][-1]["dependent_features"]


def test_R2_station_override(built):
    d = _fresh(built)
    PV0 = d.param_values()
    sid = "st20"
    new = PV0[f"{sid}.z_top"] * 1.03
    st = d.set_param(f"{sid}.z_top", new, validate=P._validate_fast)
    assert st["state"] == "ok", st
    assert d.data["parameters"][f"{sid}.z_top"]["provenance"] == "user_confirmed"
    pts = d.info[f"section.{sid}"]["points_yz"]
    assert abs(pts[-1][1] - new) < 1e-3                                  # section points are stored to 1e-4 mm
    rebuilt = st["rebuilt_features"]
    assert rebuilt < len(d.data["features"])                             # only dependents were rebuilt (cache)


def test_R4_invalid_value_fails_explicitly_and_rolls_back(built):
    d = _fresh(built)
    before = d.param_values()["st20.y_max"]
    st = d.set_param("st20.y_max", -50.0, validate=P._validate_fast)
    assert st["state"] == "failed" and st["failed"] == "section.st20"
    assert "rolled_back_to" in st
    assert d.param_values()["st20.y_max"] == before
    assert d.data["status"]["state"] == "ok"                             # back to the last valid state, not stale


def test_R5_unordered_stations_fail(built):
    d = _fresh(built)
    PV = d.param_values()
    st = d.set_param("st10.x", PV["st11.x"] + 5.0, validate=P._validate_fast)
    assert st["state"] == "failed" and "body.skin" in st["failed"]


def test_R6_scale_edit_rescales_everything(built):
    d = _fresh(built)
    L0 = d.param_values()["overall_length"]
    bb0 = Vd.bbox(d.component_shape("body"))
    st = d.set_param("overall_length", L0 * 1.1, validate=P._validate_fast)
    assert st["state"] == "ok", st
    bb1 = Vd.bbox(d.component_shape("body"))
    assert abs((bb1[3] - bb1[0]) / (bb0[3] - bb0[0]) - 1.1) < 0.002
    assert d.data["parameters"]["overall_length"]["provenance"] == "user_confirmed"


def test_R7_override_then_reset_restores(built):
    d = _fresh(built)
    h0 = d.data["status"]["param_hash"]
    v0 = Vd.mass(d.component_shape("body"))["volume_mm3"]
    d.set_param("st20.z_top", d.param_values()["st20.z_top"] + 30, validate=P._validate_fast)
    st = d.set_param("st20.z_top", clear_override=True, validate=P._validate_fast)
    assert st["state"] == "ok" and st["param_hash"] == h0
    assert abs(Vd.mass(d.component_shape("body"))["volume_mm3"] - v0) < 1e-6 * v0


def test_R3_oversized_tyre_is_reported_as_interference(built):
    d = _fresh(built)
    st = d.set_param("r_tyre_f", d.param_values()["r_arch_f"] * 1.08, validate=P._validate_fast)
    assert st["state"] == "ok"                                            # each solid alone is valid ...
    val = P.assembly_validation(d, interference=True)
    bad = [i for i in val["interference"] if i["status"] == "INTERFERENCE"]
    assert bad and not val["all_valid"]                                  # ... but the assembly check fails explicitly
    assert any("tyre_f" in (i["a"] + i["b"]) for i in bad)


# ------------------------------------------------------------------------------------------------ V / S / P / G (slow)
@pytest.fixture(scope="module")
def final(built):
    doc, res, out = built
    rep = P.finalize(doc, res, str(out), log=lambda m: None, s8=False)
    return doc, rep, out


@pytest.mark.slow
def test_V1_assembly_valid_no_unintended_interference(final):
    _, rep, _ = final
    assert rep["validation"]["all_valid"]
    assert not [i for i in rep["validation"]["interference"] if i["status"] == "INTERFERENCE"]


@pytest.mark.slow
def test_S1_step_roundtrip(final):
    _, rep, _ = final
    rt = rep["step_roundtrip"]
    assert rt["all_pass"] and not rt["missing"], json.dumps(rt)[:800]
    for cid, r in rt["components"].items():
        assert r["counts"]["solids"][0] == r["counts"]["solids"][1]
        assert r["counts"]["faces"][0] == r["counts"]["faces"][1]
        assert r["volume_rel_diff"] < 1e-6


@pytest.mark.slow
def test_S2_step_blocked_when_invalid(built, tmp_path):
    d = _fresh(built)
    d.set_param("r_tyre_f", d.param_values()["r_arch_f"] * 1.08, validate=P._validate_fast)
    rep = P.finalize(d, built[1], str(tmp_path), log=lambda m: None, s8=False)
    assert "skipped" in rep["step_roundtrip"] and not (tmp_path / "model.step").exists()


@pytest.mark.slow
def test_P_reprojection_per_view(final):
    _, rep, out = final
    rp = rep["reprojection"]
    assert set(rp) == {"side", "top", "front", "rear"}
    for v, m in rp.items():
        assert m["iou"] >= 0.92, (v, m["iou"])
        assert m["alignment"]["best_shift_px"] == [0, 0], v
        assert (out / m["image"]).exists()
        assert m["boundary_px"]["p95"] < 25, v


@pytest.mark.slow
def test_G1_glb_from_brep(final):
    doc, rep, out = final
    b = (out / "model.glb").read_bytes()
    assert b[:4] == b"glTF"
    n = struct.unpack("<I", b[12:16])[0]
    js = json.loads(b[20:20 + n])
    solids = [c for c in doc.data["components"] if not c.get("group")]
    meshed = [nd for nd in js["nodes"] if "mesh" in nd]
    assert len(meshed) == len(solids)
    assert all("NORMAL" in p["attributes"] for m in js["meshes"] for p in m["primitives"] if p.get("mode", 4) == 4)
    assert "tessellated from the validated OpenCascade B-rep" in js["asset"]["generator"]
    mats = {m["name"] for m in js["materials"]}
    assert any(m.endswith(" glass") for m in mats)                       # imprinted windows carry their material


def test_optional_features_skipped_visibly(built):
    """An optional feature (an imprint) that cannot meet the validity / tolerance rules is NOT silently dropped: it is
    marked failed_optional with its reason, the body stays valid, and the tolerance stays within the budget."""
    doc, _, _ = built
    for f in doc.data["features"]:
        assert f.get("status") in ("ok", "failed_optional"), f["id"]
        if f.get("status") == "failed_optional":
            assert f.get("optional") and f.get("error")
    r = Vd.check_solid(doc.component_shape("body"))
    assert r["valid"] and r["max_tolerance_mm"] <= 0.2, r["max_tolerance_mm"]
