"""CAD test suite (separate from tests/test_physics.py: optics passing must not imply CAD passing).

Run in the CAD environment:
    cad-worker/.venv/bin/python -m pytest tests/cad -q              # all, including the slow STEP / assembly checks
    cad-worker/.venv/bin/python -m pytest tests/cad -q -m "not slow"
The car sheet is a third-party image kept out of the repository (tests/inputs_local/car_three_view.webp); tests that
need it are skipped when it is absent. Model answers are replayed from fixtures/car_hypotheses.json (no API key)."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SHEET = ROOT / "tests" / "inputs_local" / "car_three_view.webp"
FIX = Path(__file__).parent / "fixtures" / "car_hypotheses.json"


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: STEP round trip / full assembly checks (minutes)")


need_sheet = pytest.mark.skipif(not SHEET.exists(), reason="car sheet not in this copy (tests/inputs_local/, gitignored)")


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
