"""A1-A5: the machine's parts as an exact B-rep assembly (cad/assembly.py): exact solids per part type, inferred bores
where a pin passes through a plate, measured mates, a display scale that never leaks into the model, STEP round trip."""
import math

import numpy as np
import pytest

from cad import assembly as A


def _part(pid, typ, params, pos=(0, 0, 0), rot=(0, 0, 0), parent="g", eng=None, name=None):
    return {"id": pid, "name": name or pid, "type": typ, "params": params, "position": list(pos), "rotation": list(rot),
            "scale": [1, 1, 1], "parent": parent, "visible": True, "eng": eng or {"kind": typ}}


def _machine(scale=1.0):
    square = [[-20, -20], [20, -20], [20, 20], [-20, 20]]
    return [
        {"id": "g", "name": "machine", "type": "group", "params": {}, "position": [0, 0, 0], "rotation": [90, 0, 0],
         "scale": [scale] * 3, "parent": None, "visible": True},
        _part("plate", "outline", {"polygons": [{"outer": square, "holes": []}], "thickness": 6.0}, eng={"kind": "plate"}),
        _part("pin", "cylinder", {"radius": 3.0, "height": 30.0}, pos=(8, 0, 0), name="pivot pin 1",
              eng={"kind": "pin", "joints": [{"type": "pivot", "with": "plate"}]}),
        _part("g1", "gear", {"teeth": 20, "module": 1.0, "thickness": 6.0}, pos=(0, 0, 20), eng={"kind": "gear"}),
        _part("g2", "gear", {"teeth": 30, "module": 1.0, "thickness": 6.0}, pos=(25, 0, 20),
              eng={"kind": "gear", "joints": [{"type": "gear_mesh", "with": "g1"}]}),
        _part("spring", "coil", {"radius": 4.0, "wire": 0.6, "turns": 5, "pitch": 2.5}, pos=(-40, 0, 0),
              eng={"kind": "spring"}),
    ]


@pytest.fixture(scope="module")
def built():
    return A.analyse(_machine(), log=lambda m: None)


def test_A1_every_part_is_a_valid_exact_solid(built):
    _, _, rep = built
    s = rep["summary"]
    assert s["built"] == s["valid_solids"] == 5 and s["not_built"] == 0
    g = rep["records"]["g1"]
    assert "involute" in g["exact"] and g["gear"]["teeth"] == 20
    assert "helix" in rep["records"]["spring"]["exact"]


def test_A2_pin_through_plate_gets_an_inferred_bore_and_a_satisfied_mate(built):
    _, _, rep = built
    plate = rep["records"]["plate"]
    bores = [f for f in plate.get("features", []) if f["op"] == "bore"]
    assert len(bores) == 1 and bores[0]["through"] and "inferred" in bores[0]["provenance"]
    assert abs(bores[0]["diameter_mm"] - (6.0 + A.BORE_CLEARANCE_MM)) < 1e-6
    m = [m for m in rep["mates"] if m["type"].startswith("Concentric") and {m["a"], m["b"]} == {"pin", "plate"}]
    assert m and m[0]["satisfied"] and m[0]["source"] == "declared by the rebuild"
    assert not [p for p in rep["pairs"] if {p["a"], p["b"]} == {"pin", "plate"} and p["status"] == "interference"]


def test_A3_gear_mesh_is_measured(built):
    _, _, rep = built
    m = [m for m in rep["mates"] if m["type"] == "Gear mesh"]
    assert len(m) == 1 and m[0]["satisfied"] and m[0]["ideal_mm"] == 25.0 and m[0]["contact_ratio"] >= 1.2


def test_A4_display_scale_is_not_part_of_the_model():
    _, _, rep = A.analyse(_machine(scale=0.5), log=lambda m: None)
    assert rep["model_scale"] == pytest.approx(0.5)
    vol = rep["records"]["pin"]["validation"]["volume_mm3"]
    assert vol == pytest.approx(math.pi * 9 * 30, rel=1e-6)                       # model mm, not display mm
    m = [m for m in rep["mates"] if m["type"] == "Gear mesh"]
    assert m and m[0]["satisfied"]


@pytest.mark.slow
def test_A5_step_round_trip(built, tmp_path):
    shapes, _, rep = built
    comps = {i: {"name": rep["records"][i]["name"], "shape": s, "colour": None} for i, s in shapes.items()}
    rt = A.step_roundtrip(comps, rep["groups"], tmp_path / "a.step", tmp_path / "brep")
    assert rt["all_pass"] and not rt["missing"] and len(rt["components"]) == 5
