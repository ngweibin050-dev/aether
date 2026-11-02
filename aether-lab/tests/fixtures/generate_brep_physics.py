"""Regenerate physics-only tessellations from validated OpenCascade solids.

Run with the CAD-worker environment from aether-lab:
    PYTHONPATH=. python tests/fixtures/generate_brep_physics.py
This is a deterministic synthetic test input, not a reconstruction benchmark.
"""
import json
from pathlib import Path
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.gp import gp_Pnt
from cad.tessellate import mesh
from cad.validate import check_solid

shapes = {
    'shell': BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 30), 30).Shape(),
    'core': BRepPrimAPI_MakeBox(gp_Pnt(-6, -6, 24), 12, 12, 12).Shape(),
    'tube': BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(40, 150).Shape(), BRepPrimAPI_MakeCylinder(36, 150).Shape()).Shape(),
    'plate': BRepPrimAPI_MakeBox(gp_Pnt(-20, -20, 0), 40, 40, 2).Shape(),
}
out = {}
for name, shape in shapes.items():
    valid = check_solid(shape, name, argument_analysis=False)
    assert valid['valid'], valid
    v, f, n, _ = mesh(shape, linear=0.3, angular=0.3)
    out[name] = {'name': name, 'kind': 'synthetic_test_solid', 'parent': None,
                 'v': v.ravel().tolist(), 'f': f.ravel().tolist(), 'n': n.ravel().tolist(), 'l': []}
Path('tests/fixtures/brep_physics.json').write_text(json.dumps(out, separators=(',', ':')) + '\n')
