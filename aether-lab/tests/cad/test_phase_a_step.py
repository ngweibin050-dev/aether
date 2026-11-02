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


def test_unresolved_view_preserves_previous_document_and_output(tmp_path, monkeypatch):
    from cad import pipeline
    original = dict(worker.STATE)
    class FakeDoc:
        data = {'status': {'state': 'ok'}, 'maturity': 'draft_inference',
                'decisions': {'front_view': {'value': 'end_b', 'provenance': 'unresolved'}}}
    monkeypatch.setattr(pipeline, 'build', lambda *a, **k: (FakeDoc(), {'seconds': 0}))
    def must_not_finalize(*args, **kwargs):
        pytest.fail('an unresolved draft must not be finalized')
    monkeypatch.setattr(pipeline, 'finalize', must_not_finalize)
    drawing = tmp_path / 'drawing.png'; drawing.write_bytes(b'test')
    current = tmp_path / 'current'; current.mkdir()
    marker = current / 'previous.aethercad'; marker.write_text('previous')
    r = worker.cmd_build({'sheet': str(drawing), 'out_dir': str(current)})
    assert r['status']['state'] == 'invalid' and 'unresolved' in r['status']['error']
    assert r['kept_previous_document'] and worker.STATE == original
    assert marker.read_text() == 'previous'


def test_reopening_unresolved_draft_preserves_previous_document(tmp_path, monkeypatch):
    import json
    from cad import document
    original = dict(worker.STATE)
    class FakeDoc:
        def __init__(self, data, ops):
            self.data = data
        def recompute(self, **kwargs):
            pytest.fail('an unresolved draft must not be reopened')
    monkeypatch.setattr(document, 'Document', FakeDoc)
    f = tmp_path / 'unresolved.aethercad'
    f.write_text(json.dumps({'decisions': {'front_view': {'provenance': 'unresolved'}}}))
    r = worker.cmd_open({'path': str(f)})
    assert r['status']['state'] == 'invalid' and r['kept_previous_document']
    assert worker.STATE == original


def test_downstream_scene_failure_rolls_back_worker_document(tmp_path, monkeypatch):
    """A failed scene import must restore the previous worker document and scene."""
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
    def upload(f):
        body = json.dumps({'file': base64.b64encode(f.read_bytes()).decode()}).encode()
        try:
            with urlopen(Request(f'http://127.0.0.1:{srv.server_port}/api/cad/import_step', data=body,
                                 headers={'Content-Type':'application/json'}), timeout=30) as r:
                return r.status
        except HTTPError as e:
            return e.code
    try:
        files = [tmp_path / 'old.step', tmp_path / 'new.step']
        for f, size in zip(files, (10, 20)):
            w = STEPControl_Writer()
            w.Transfer(BRepPrimAPI_MakeBox(size, size, size).Shape(), STEPControl_AsIs)
            w.Write(str(f))
        assert upload(files[0]) == 200
        old_doc = cad_client.call('document')['document_id']
        old_scene = copy.deepcopy(server.STATE)
        old_file = (server.OUT / 'cad' / 'current' / 'model.aethercad').read_bytes()
        entered, release, read_done = threading.Event(), threading.Event(), threading.Event()
        output = {}
        def fail_scene(*args, **kwargs):
            entered.set()
            assert release.wait(10)
            raise RuntimeError('injected post-worker scene failure')
        monkeypatch.setattr(server, 'cad_import_current', fail_scene)
        def do_upload(): output['upload'] = upload(files[1])
        def do_read():
            with urlopen(f'http://127.0.0.1:{srv.server_port}/api/cad/document', timeout=15) as r:
                output['document'] = json.loads(r.read())['document_id']
            read_done.set()
        uploader = threading.Thread(target=do_upload); uploader.start()
        assert entered.wait(15)
        reader = threading.Thread(target=do_read); reader.start()
        assert not read_done.wait(.3), 'concurrent reader observed an uncommitted worker document'
        release.set(); uploader.join(15); reader.join(15)
        assert output['upload'] == 500 and output['document'] == old_doc
        assert server.STATE == old_scene
        assert cad_client.call('document')['document_id'] == old_doc
        assert (server.OUT / 'cad' / 'current' / 'model.aethercad').read_bytes() == old_file
    finally:
        srv.shutdown(); srv.server_close(); thread.join(); cad_client.stop_quietly()


def test_photo_downstream_failure_rolls_back_worker_document(tmp_path, monkeypatch):
    """A post-build drawing upload failure restores the old STEP document and scene."""
    import base64, io, json, sys, threading
    from urllib.request import Request, urlopen
    from PIL import Image
    import agent, cad_client, server
    from engine import lab
    cad_client.stop_quietly()
    monkeypatch.setenv('AETHER_CAD_PYTHON', sys.executable)
    monkeypatch.setenv('AETHER_COMPUTE', 'local')
    monkeypatch.setattr(server, 'OUT', tmp_path / 'output')
    server.STATE.clear(); server.STATE.update(lab.default_state())
    srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    def post(path, data):
        req = Request(f'http://127.0.0.1:{srv.server_port}' + path, data=json.dumps(data).encode(),
                      headers={'Content-Type': 'application/json'})
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    try:
        fs = [tmp_path / 'one.step', tmp_path / 'two.step']
        for f, n in zip(fs, (10, 20)):
            w = STEPControl_Writer(); w.Transfer(BRepPrimAPI_MakeBox(n, n, n).Shape(), STEPControl_AsIs); w.Write(str(f))
        post('/api/cad/import_step', {'file': base64.b64encode(fs[0].read_bytes()).decode()})
        old_doc = cad_client.call('document')['document_id']; old = copy.deepcopy(server.STATE)
        real_call = cad_client.call
        def mock_build(cmd, **kwargs):
            if cmd == 'build':
                r = real_call('import_step', path=str(fs[1]), out_dir=kwargs['out_dir'])
                return {'status': r['status'], 'maturity': 'test', 'seconds': 0}
            return real_call(cmd, **kwargs)
        monkeypatch.setattr(cad_client, 'call', mock_build)
        def fail_fit(*args, **kwargs):
            raise RuntimeError('injected display-fit failure')
        monkeypatch.setattr(agent, '_fit_to_desk', fail_fit)
        image = io.BytesIO(); Image.new('RGB', (8, 8), 'white').save(image, format='PNG')
        r = post('/api/photo', {'image': 'data:image/png;base64,' + base64.b64encode(image.getvalue()).decode(),
                                'kind': 'three_view', 'mode': 'cad'})
        assert r['trace'][-1]['result']['error'] and server.STATE == old
        assert real_call('document')['document_id'] == old_doc
    finally:
        srv.shutdown(); srv.server_close(); t.join(); cad_client.stop_quietly()


def test_parameter_scene_failure_restores_document_and_file(tmp_path, monkeypatch):
    """Failed scene transfer rolls back in-place parameter edits and saved output."""
    import json, sys, threading
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    import server, cad_client
    from engine import lab
    from cad.document import Document
    from cad.ops import OPS
    d = Document.new({'file': 'synthetic'}, 'Synthetic parameter test')
    d['parameters'] = {'r': {'provenance': 'assumed', 'unit': 'mm', 'value': 10.0},
                       'h': {'provenance': 'derived', 'unit': 'mm', 'rel': {'kind': 'linear', 'terms': [['r', 2.0]], 'const': 0.0}}}
    d['features'] = [{'id': 'tip', 'op': 'exhaust_tip', 'inputs': [], 'params': {'y': 0, 'z': 0, 'r': {'$p': 'r'}, 'wall': 1, 'x0': 0, 'x1': {'$p': 'h'}}}]
    d['components'] = [{'id': 'c', 'name': 'c', 'kind': 'exhaust_tip', 'output': 'tip'}]
    doc = Document(d, OPS); assert doc.recompute()['state'] == 'ok'
    source = tmp_path / 'source'; source.mkdir(); doc.save(source / 'model.aethercad')
    cad_client.stop_quietly()
    monkeypatch.setenv('AETHER_CAD_PYTHON', sys.executable)
    monkeypatch.setenv('AETHER_COMPUTE', 'local')
    monkeypatch.setattr(server, 'OUT', tmp_path / 'output')
    server.STATE.clear(); server.STATE.update(lab.default_state())
    srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    def post(path, body):
        req = Request(f'http://127.0.0.1:{srv.server_port}' + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=30) as r: return r.status, json.loads(r.read())
        except HTTPError as e: return e.code, json.loads(e.read())
    try:
        status, result = post('/api/cad/open', {'path': str(source / 'model.aethercad')})
        assert status == 200, result
        old_doc = cad_client.call('document'); old_meshes = cad_client.call('meshes')
        old_file = (source / 'model.aethercad').read_bytes(); old_scene = copy.deepcopy(server.STATE)
        def fail_scene(*args, **kwargs): raise RuntimeError('injected parameter scene failure')
        monkeypatch.setattr(server, 'cad_import_current', fail_scene)
        status, result = post('/api/cad/param', {'id': 'r', 'value': 12})
        assert status == 500 and result['error']
        assert cad_client.call('document') == old_doc
        assert cad_client.call('meshes') == old_meshes
        assert (source / 'model.aethercad').read_bytes() == old_file
        assert server.STATE == old_scene
    finally:
        srv.shutdown(); srv.server_close(); t.join(); cad_client.stop_quietly()


def test_worker_crash_during_scene_transfer_preserves_previous_document(tmp_path, monkeypatch):
    import base64, json, sys, threading
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    import server, cad_client
    from engine import lab
    cad_client.stop_quietly(); monkeypatch.setenv('AETHER_CAD_PYTHON', sys.executable)
    monkeypatch.setenv('AETHER_COMPUTE', 'local'); monkeypatch.setattr(server, 'OUT', tmp_path / 'output')
    server.STATE.clear(); server.STATE.update(lab.default_state())
    srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True); thread.start()
    def upload(path):
        req = Request(f'http://127.0.0.1:{srv.server_port}/api/cad/import_step', data=json.dumps({'file': base64.b64encode(path.read_bytes()).decode()}).encode(), headers={'Content-Type':'application/json'})
        try:
            with urlopen(req, timeout=30) as r: return r.status
        except HTTPError as e: return e.code
    try:
        files = [tmp_path / 'first.step', tmp_path / 'second.step']
        for path, size in zip(files, (10, 20)):
            w = STEPControl_Writer(); w.Transfer(BRepPrimAPI_MakeBox(size, size, size).Shape(), STEPControl_AsIs); w.Write(str(path))
        assert upload(files[0]) == 200
        old_doc = cad_client.call('document')['document_id']; old_scene = copy.deepcopy(server.STATE)
        old_file = (server.OUT / 'cad' / 'current' / 'model.aethercad').read_bytes()
        def crash(*a, **k):
            cad_client._proc.kill(); cad_client._proc.wait(timeout=10)
            raise RuntimeError('injected worker crash')
        monkeypatch.setattr(server, 'cad_import_current', crash)
        assert upload(files[1]) == 500 and server.STATE == old_scene
        assert (server.OUT / 'cad' / 'current' / 'model.aethercad').read_bytes() == old_file
        assert cad_client.call('document')['document_id'] == old_doc
    finally:
        srv.shutdown(); srv.server_close(); thread.join(); cad_client.stop_quietly()
