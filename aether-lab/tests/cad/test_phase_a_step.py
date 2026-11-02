"""Offline STEP import tests; the generated box is synthetic and not a benchmark drawing."""
import copy
import hashlib
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from cad import worker


def test_step_import_and_failed_import_keep_document(tmp_path):
    worker.STATE.update(doc=None, res=None, out_dir=None, sheet=None)
    f = tmp_path / 'box.step'
    w = STEPControl_Writer()
    w.Transfer(BRepPrimAPI_MakeBox(10, 20, 30).Shape(), STEPControl_AsIs)
    w.Write(str(f))
    r = worker.cmd_import_step({'path': str(f), 'out_dir': str(tmp_path / 'current'), 'name': 'Box'})
    assert r['route'] == 'step_import' and r['solids'] == 1
    d = worker.cmd_document({})
    assert d['source']['sha256'] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert d['features'][0]['op'] == 'external_brep'
    assert not d['parameters']
    assert len(worker.cmd_meshes({})['meshes']) == 1
    old = copy.deepcopy(d)
    bad = tmp_path / 'bad.step'; bad.write_text('not a STEP file')
    with pytest.raises(Exception):
        worker.cmd_import_step({'path': str(bad), 'out_dir': str(tmp_path / 'current')})
    assert worker.cmd_document({}) == old
    reopened = worker.cmd_open({'path': str(tmp_path / 'current' / 'model.aethercad')})
    assert reopened['status']['state'] == 'ok'
    assert worker.cmd_document({})['document_id'] == old['document_id']


def test_step_api_and_reset(tmp_path, monkeypatch):
    import base64, json, sys, threading
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    import server, cad_client
    from engine import lab
    cad_client.stop_quietly()
    monkeypatch.setenv('AETHER_CAD_PYTHON', sys.executable)
    monkeypatch.setenv('AETHER_COMPUTE', 'local')
    monkeypatch.setattr(server, 'OUT', tmp_path / 'output')
    server.STATE.clear(); server.STATE.update(lab.default_state())
    srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True); thread.start()
    def request(path, body=None):
        req = Request(f'http://127.0.0.1:{srv.server_port}' + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=30) as r: return r.status, json.loads(r.read())
        except HTTPError as e: return e.code, json.loads(e.read())
    try:
        f = tmp_path / 'api-box.step'
        w = STEPControl_Writer(); w.Transfer(BRepPrimAPI_MakeBox(10,20,30).Shape(), STEPControl_AsIs); w.Write(str(f))
        encoded = base64.b64encode(f.read_bytes()).decode()
        status, r = request('/api/cad/import_step', {'file':encoded,'name':'Synthetic box'})
        assert status == 200, r
        assert r['document']['route'] == 'step_import'
        assert any(p['type'] == 'cad' for p in r['state']['parts'])
        old = copy.deepcopy(server.STATE)
        status, r = request('/api/cad/import_step', {'file':base64.b64encode(b'invalid').decode()})
        assert status == 409 and r['error'] and server.STATE == old
        assert request('/api/cad/document')[1]['document_id'] == old['parts'][0]['eng']['cad_document']
        status, r = request('/api/reset', {})
        assert status == 200 and not r['state']['parts']
        status, r = request('/api/cad/document')
        assert status == 409 and r['error']
    finally:
        srv.shutdown(); srv.server_close(); thread.join(); cad_client.stop_quietly()


def test_failed_final_validation_preserves_worker(tmp_path, monkeypatch):
    from cad import pipeline
    original = dict(worker.STATE)
    class FakeDoc:
        data = {'status': {'state': 'ok'}, 'maturity': 'draft_inference'}
    monkeypatch.setattr(pipeline, 'build', lambda *a, **k: (FakeDoc(), {'seconds': 0}))
    monkeypatch.setattr(pipeline, 'finalize', lambda *a, **k: {'validation': {'all_valid': False}})
    f = tmp_path / 'drawing.png'; f.write_bytes(b'test')
    r = worker.cmd_build({'sheet': str(f), 'out_dir': str(tmp_path / 'current')})
    assert r['status']['state'] == 'invalid' and r['kept_previous_document']
    assert worker.STATE == original


def test_surface_only_step_rejected(tmp_path):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Pln, gp_Pnt, gp_Dir
    f = tmp_path / 'face.step'
    face = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(0,0,0), gp_Dir(0,0,1)), 0, 10, 0, 10).Face()
    w = STEPControl_Writer(); w.Transfer(face, STEPControl_AsIs); w.Write(str(f))
    old = dict(worker.STATE)
    with pytest.raises(RuntimeError, match='no solid'):
        worker.cmd_import_step({'path': str(f), 'out_dir': str(tmp_path / 'current')})
    assert worker.STATE == old
