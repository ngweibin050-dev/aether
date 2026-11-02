"""CAD test suite (separate from tests/test_physics.py: optics passing must not imply CAD passing).

Run in the CAD environment:
    cad-worker/.venv/bin/python -m pytest tests/cad -q              # all, including the slow STEP / assembly checks
    cad-worker/.venv/bin/python -m pytest tests/cad -q -m "not slow"
The original car benchmark is kept out of Git (tests/inputs_local/car_three_view.webp). Set
AETHER_CAD_TEST_IMAGE to explicitly test another local image. This does not make that image the original benchmark:
record its hash, dimensions and any preprocessing; replayed model answers are matched to the original prompt hash.
Without the chosen file the image-dependent tests are skipped. No API key is needed for replay."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SHEET = Path(os.environ.get("AETHER_CAD_TEST_IMAGE", str(ROOT / "tests" / "inputs_local" / "car_three_view.webp"))).resolve()
FIX = Path(__file__).parent / "fixtures" / "car_hypotheses.json"


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: STEP round trip / full assembly checks (minutes)")


need_sheet = pytest.mark.skipif(not SHEET.exists(), reason="CAD test sheet not found (set AETHER_CAD_TEST_IMAGE or provide the gitignored canonical sheet)")


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """(doc, res, out_dir): the car built from the sheet with replayed model answers (deterministic)."""
    if not SHEET.exists():
        pytest.skip("car sheet not in this copy")
    from cad import pipeline as P
    out = tmp_path_factory.mktemp("car")
    stored = json.loads(FIX.read_text())["hypotheses"]
    doc, res = P.build(str(SHEET), str(out), stored=stored, ai_mode="replay", log=lambda m: None)
    assert doc.data["status"]["state"] == "ok", doc.data["status"]
    return doc, res, out


@pytest.fixture(scope="session")
def obs_aux():
    if not SHEET.exists():
        pytest.skip("car sheet not in this copy")
    from cad import observations as O
    return O.observe(str(SHEET))
