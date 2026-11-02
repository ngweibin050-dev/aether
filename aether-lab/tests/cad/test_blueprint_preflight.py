"""View detection is evidence only: it never constructs aircraft geometry."""
from pathlib import Path
import numpy as np
import pytest
from cad import observations as O

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('path', [ROOT/'tests/inputs/NASA_X-3_three_view.png',
                                  ROOT/'tests/inputs/heldout/NASA_X-36_three_view.png'])
def test_three_nasa_views_detected_but_aircraft_builder_not_claimed(path):
    gray, _ = O.load(path)
    views = O.find_views(gray, O.ink_of(gray))
    assert len(views) == 3
    with pytest.raises(ValueError, match='Aircraft and general three-view CAD reconstruction are not implemented'):
        O.observe(path)


def test_edge_touching_view_is_not_discarded_but_edge_strip_is():
    ink = np.zeros((200, 300), dtype=bool)
    ink[50:125, :60] = True  # large view genuinely touching the left edge
    ink[10:180, 295:300] = True  # edge-dominated strip
    views = O.find_views((~ink).astype(float)*255, ink)
    assert len(views) == 1 and views[0]['box'][0] == 0
