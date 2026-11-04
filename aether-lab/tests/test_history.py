"""The project's undo history (history.py): undo puts back only the parts a step changed.

    python -m tests.test_history
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import history  # noqa: E402


def part(pid, name, parent=None, **kw):
    return {"id": pid, "name": name, "type": "box", "params": {"w": 1, "d": 1, "h": 1}, "position": [0, 0, 0],
            "rotation": [0, 0, 0], "scale": [1, 1, 1], "parent": parent, **kw}


def scene():
    return {"version": 1, "selected": None, "parts": [part("car", "Car"), part("body", "Body", "car"),
                                                      part("arm", "Robot arm")]}


def step(state, label, source, fn):
    before = history.snapshot(state)
    fn(state)
    return history.record(before, state, label, source)


def test_undo_reverts_only_that_step():
    history.reset()
    st = scene()
    a = step(st, "add details", "ai", lambda s: s["parts"].append(part("lamp", "Headlight", "car")))
    step(st, "build truck", "build", lambda s: s["parts"].append(part("truck", "Truck")))
    r = history.undo(st, a["id"])
    names = [p["name"] for p in st["parts"]]
    assert r["undone"] and "Headlight" not in names
    assert "Truck" in names and "Robot arm" in names         # the later, unrelated model stays


def test_dependent_steps_go_together_and_redo():
    history.reset()
    st = scene()
    b = step(st, "build van", "build", lambda s: s["parts"].append(part("van", "Van")))
    step(st, "detail van", "ai", lambda s: s["parts"].append(part("wheel", "Wheel", "van")))
    step(st, "colour arm", "edit", lambda s: s["parts"][2].update(color="#ff0000"))
    r = history.undo(st, b["id"])
    assert r["also_undone"] == ["detail van"]
    assert not any(p["id"] in ("van", "wheel") for p in st["parts"])
    assert st["parts"][2].get("color") == "#ff0000"           # the edit of another model stays
    history.redo(st)
    assert {"van", "wheel"} <= {p["id"] for p in st["parts"]}


def test_ctrl_z_skips_automatic_steps():
    history.reset()
    st = scene()
    step(st, "move arm", "edit", lambda s: s["parts"][2].update(position=[5, 0, 0]))
    step(st, "CAD details", "auto", lambda s: s["parts"][1].update(params={"w": 2, "d": 1, "h": 1}))
    r = history.undo(st)
    assert r["reverted"] == "move arm"
    assert st["parts"][2]["position"] == [0, 0, 0] and st["parts"][1]["params"]["w"] == 2


def test_saved_and_loaded(tmp_path):
    history.reset()
    st = scene()
    e = step(st, "add lamp", "ai", lambda s: s["parts"].append(part("lamp", "Lamp", "car")))
    history.save(tmp_path)
    history.reset()
    history.load(tmp_path, st)
    assert history.undo(st, e["id"])["undone"]
    assert "lamp" not in {p["id"] for p in st["parts"]}


if __name__ == "__main__":
    import tempfile
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(Path(tempfile.mkdtemp())) if name == "test_saved_and_loaded" else fn()
            print(name, "PASS")
