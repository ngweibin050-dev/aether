"""Portable CAD packages: synthetic B-rep, not a drawing accuracy benchmark."""
import copy
import hashlib
import io
import json
import zipfile

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from cad import package, worker


def box(tmp_path):
    f = tmp_path / 'box.step'
    w = STEPControl_Writer()
    w.Transfer(BRepPrimAPI_MakeBox(10, 20, 30).Shape(), STEPControl_AsIs)
    w.Write(str(f))
    worker.cmd_import_step({'path': str(f), 'out_dir': str(tmp_path / 'old')})
    return worker.cmd_export({'kind': 'package'})['path']


def rewrite(source, target, change):
    with zipfile.ZipFile(source) as z:
        members = {i.filename: z.read(i) for i in z.infolist()}
    change(members)
    with zipfile.ZipFile(target, 'w') as z:
        for n, b in members.items(): z.writestr(n, b)


def test_external_step_package_roundtrip(tmp_path):
    p = box(tmp_path)
    with zipfile.ZipFile(p) as z:
        assert set(z.namelist()) == {'manifest.json', 'model.aethercad', 'external/solid_1.brep'}
    before = worker.cmd_document({})
    r = worker.cmd_import_package({'path': p, 'out_dir': str(tmp_path / 'new')})
    after = worker.cmd_document({})
    assert r['status']['state'] == 'ok' and not r['source_sheet_included']
    assert after['document_id'] == before['document_id']
    assert after['features'][0]['op'] == 'external_brep' and not after['parameters']
    assert len(worker.cmd_meshes({})['meshes']) == 1
    assert worker.cmd_export({'kind':'step'})['path'].endswith('model.step')


@pytest.mark.parametrize('change', [
    lambda m: m.update({'../escape': b'bad'}),
    lambda m: m.update({'external/solid_1.brep': b'corrupted'}),
    lambda m: m.pop('external/solid_1.brep'),
])
def test_bad_package_preserves_document(tmp_path, change):
    p = box(tmp_path)
    old = copy.deepcopy(worker.cmd_document({}))
    corrupt = tmp_path / 'bad.zip'; rewrite(p, corrupt, change)
    with pytest.raises(Exception): worker.cmd_import_package({'path':str(corrupt), 'out_dir':str(tmp_path / 'old')})
    assert worker.cmd_document({}) == old
    assert not (tmp_path / 'escape').exists()
    assert worker.cmd_export({'kind':'step'})['path'].endswith('model.step')


def test_external_path_cannot_escape_even_with_valid_manifest(tmp_path):
    p = box(tmp_path); bad = tmp_path / 'bad.zip'
    def mutate(m):
        data = json.loads(m['model.aethercad'])
        data['features'][0]['params']['brep_file'] = '../secret.brep'
        m['model.aethercad'] = json.dumps(data).encode()
        manifest = json.loads(m['manifest.json'])
        manifest['files']['model.aethercad'] = hashlib.sha256(m['model.aethercad']).hexdigest()
        m['manifest.json'] = json.dumps(manifest).encode()
    rewrite(p, bad, mutate)
    old = copy.deepcopy(worker.cmd_document({}))
    with pytest.raises(ValueError, match='unsafe'): worker.cmd_import_package({'path':str(bad), 'out_dir':str(tmp_path / 'old')})
    assert worker.cmd_document({}) == old


def test_duplicate_zip_member_rejected(tmp_path):
    p = box(tmp_path); bad = tmp_path / 'duplicate.zip'
    with zipfile.ZipFile(p) as src, zipfile.ZipFile(bad, 'w') as dst:
        for i in src.infolist(): dst.writestr(i.filename, src.read(i))
        with pytest.warns(UserWarning): dst.writestr('model.aethercad', b'{}')
    with pytest.raises(ValueError, match='duplicate'): package.read(bad, tmp_path / 'unpacked')


def test_parametric_document_reopens_and_recomputes_edit(tmp_path):
    from cad.document import Document
    from cad.ops import OPS
    from tests.cad.test_kernel_document import _tiny_doc
    from cad import validate
    out = tmp_path / 'param'; out.mkdir()
    data = _tiny_doc()
    data['parameters']['overall_length'] = {'provenance':'assumed', 'unit':'mm', 'value':4500.0}
    data['decisions']['overall_length_mm'] = {'value':4500.0, 'provenance':'assumed'}
    doc = Document(data, OPS); doc.base_dir = str(out)
    assert doc.recompute(validate=worker._full_validate)['state'] == 'ok'
    worker.STATE.update(doc=doc, res=None, sheet=None, out_dir=str(out))
    p = worker.cmd_export({'kind': 'package'})['path']
    assert worker.cmd_import_package({'path':p, 'out_dir':str(tmp_path / 'restored')})['status']['state'] == 'ok'
    before = validate.mass(worker.STATE['doc'].shapes['tip'])['volume_mm3']
    edit = worker.cmd_set_param({'id':'r', 'value':12.0})
    assert edit['status']['state'] == 'ok'
    assert validate.mass(worker.STATE['doc'].shapes['tip'])['volume_mm3'] != before
    assert worker.cmd_document({})['parameters'][0]['value'] == 12.0


def test_package_http_roundtrip_and_invalid_keeps_scene(tmp_path, monkeypatch):
    import base64, sys, threading
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
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    def request(path, body=None, binary=False):
        req = Request(f'http://127.0.0.1:{srv.server_port}' + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'})
        try:
            with urlopen(req, timeout=60) as r: return r.status, r.read() if binary else json.loads(r.read())
        except HTTPError as e: return e.code, json.loads(e.read())
    try:
        f = tmp_path / 'api.step'; w = STEPControl_Writer()
        w.Transfer(BRepPrimAPI_MakeBox(10, 20, 30).Shape(), STEPControl_AsIs); w.Write(str(f))
        status, r = request('/api/cad/import_step', {'file':base64.b64encode(f.read_bytes()).decode()})
        assert status == 200, r
        doc_id = r['document']['document_id']
        status, blob = request('/api/cad/export.package', binary=True)
        assert status == 200 and zipfile.is_zipfile(io.BytesIO(blob))
        assert request('/api/reset', {})[0] == 200
        status, r = request('/api/cad/import_package', {'file':base64.b64encode(blob).decode()})
        assert status == 200, r
        assert r['document']['document_id'] == doc_id
        before = copy.deepcopy(server.STATE)
        status, r = request('/api/cad/import_package', {'file':base64.b64encode(b'not zip').decode()})
        assert status == 409 and r['scene_unchanged'] and server.STATE == before
        assert request('/api/cad/document')[1]['document_id'] == doc_id
    finally:
        srv.shutdown(); srv.server_close(); t.join(); cad_client.stop_quietly()


def test_source_sheet_packaged_and_hash_checked(tmp_path):
    from cad.document import Document
    from cad.ops import OPS
    from tests.cad.test_kernel_document import _tiny_doc
    sheet = tmp_path / 'drawing.png'; sheet.write_bytes(b'synthetic sheet bytes')
    data = _tiny_doc()
    data['source'] = {'file': 'drawing.png', 'sha256': hashlib.sha256(sheet.read_bytes()).hexdigest()}
    doc = Document(data, OPS); doc.base_dir = str(tmp_path)
    out = tmp_path / 'sheet.aether.zip'; package.write(doc, str(sheet), out)
    d, p = package.read(out, tmp_path / 'unpacked')
    assert d['source'] == data['source'] and open(p, 'rb').read() == sheet.read_bytes()
    sheet.write_bytes(b'changed')
    with pytest.raises(ValueError, match='no longer matches'): package.write(doc, str(sheet), out)
