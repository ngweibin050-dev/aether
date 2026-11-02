"""Offline Phase A safety tests. CAD input is mocked; no external API calls."""
import copy
import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
import agent, cad_client, compute, server
from engine import geometry, lab


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setenv('AETHER_COMPUTE', 'local')
    server.STATE.clear(); server.STATE.update(lab.default_state())
    srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    def request(path, data=None):
        req = Request(f'http://127.0.0.1:{srv.server_port}' + path, data=None if data is None else json.dumps(data).encode(), headers={'Content-Type':'application/json'})
        try:
            with urlopen(req, timeout=10) as r: return r.status, json.loads(r.read())
        except HTTPError as e: return e.code, json.loads(e.read())
    yield request
    srv.shutdown(); srv.server_close(); t.join()


@pytest.mark.parametrize('name', sorted(lab.DISABLED))
def test_disabled_tool_paths(http, name):
    original = copy.deepcopy(server.STATE)
    assert lab.run(server.STATE, name, {})['error_kind'] == 'unavailable'
    assert compute.run(server.STATE, name, {})['error_kind'] == 'unavailable'
    status, body = http('/api/tool', {'name': name, 'args': {}})
    assert status == 410 and body['error_kind'] == 'unavailable'
    assert server.STATE == original


@pytest.mark.parametrize('kind,mode', [('machine','interpret'), ('part','interpret'), ('three_view','trace'), ('three_view','hull')])
def test_photo_unsupported_no_builder(http, monkeypatch, kind, mode):
    monkeypatch.setattr(cad_client, 'call', lambda *a, **k: pytest.fail('CAD builder invoked'))
    old = copy.deepcopy(server.STATE)
    status, r = http('/api/photo', {'image':'unused', 'kind':kind, 'mode':mode})
    assert status == 200 and r['trace'][0]['result']['error']
    assert r['trace'][0]['result']['scene_unchanged'] and server.STATE == old


def test_photo_missing_cad_no_fallback(http, monkeypatch):
    monkeypatch.setattr(cad_client, 'available', lambda: False)
    monkeypatch.setattr(agent, '_sheet_to_cad', lambda *a, **k: pytest.fail('builder invoked'))
    old = copy.deepcopy(server.STATE)
    status, r = http('/api/photo', {'image':'unused', 'kind':'three_view'})
    assert status == 200 and r['trace'][0]['result']['error'] and server.STATE == old


def test_chat_blocks_unadvertised_geometry_tool(http, monkeypatch):
    observed = []
    def fake_post(path, payload, **kwargs):
        observed.append(payload)
        if len(observed) == 1:
            return {'choices':[{'message':{'role':'assistant','tool_calls':[{'id':'1','function':{'name':'add_part','arguments':'{"type":"box"}'}}]}}]}
        return {'choices':[{'message':{'role':'assistant','content':'Unavailable'}}]}
    monkeypatch.setattr(agent, '_post', fake_post)
    status, r = http('/api/chat', {'text':'make a box'})
    assert status == 200 and r['trace'][0]['result']['error_kind'] == 'unavailable'
    assert not server.STATE['parts']
    assert not ({d['function']['name'] for d in observed[0]['tools']} & set(lab.DISABLED))


def test_scene_rejects_geometry_and_stale_undo_atomically(http):
    p = lab._part('cad', {'vertices':[0,0,0], 'faces':[]}, 'existing')
    server.STATE['parts'] = [p]
    before = copy.deepcopy(server.STATE)
    for parts in ([{'id':'new','type':'cad','params':{'vertices':[1,2,3],'faces':[0,0,0]}}],
                  [{'id':p['id'],'params':{'vertices':[0,0,0]}}],
                  [{'id':p['id'],'position':[1,2,3]}, {'id':p['id'],'position':['bad',0,0]}],
                  [{'id':p['id'],'scale':[1,2,1]}]):
        status, result = http('/api/scene', {'parts':parts})
        assert status == 422 and result['error_kind'] == 'geometry_rejected' and server.STATE == before
    status, result = http('/api/scene', {'parts':[{'id':p['id'],'position':[1,2,3]}], 'selected':p['id']})
    assert status == 200 and result['state']['parts'][0]['position'] == [1,2,3]
    assert server.STATE['parts'][0]['params'] == before['parts'][0]['params']
    http('/api/reset', {})
    status, result = http('/api/scene', {'parts':[{'id':p['id'],'position':[0,0,0]}]})
    assert status == 422 and server.STATE['parts'] == []


@pytest.mark.parametrize('path', ['/api/demo/recorded','/api/export.glb','/api/export.stl'])
def test_old_demos_and_scene_exports_are_gone(http,path):
    status,r = http(path); assert status == 410 and r['error']
    assert http('/api/demos')[1]['demos'] == []


def test_direct_builders_absent():
    for name in ['box','sphere','gear','BUILDERS','_MESH','decimate']:
        assert not hasattr(geometry, name)
    with pytest.raises(geometry.NotCadGeometry): geometry.local_mesh({'type':'box','params':{}})


def test_wrong_interpreter_is_not_available(monkeypatch):
    cad_client.stop_quietly()
    monkeypatch.setenv('AETHER_CAD_PYTHON', '/does/not/exist')
    assert not cad_client.available()


def test_update_part_geometry_rejected(http):
    p = lab._part('cad', {'vertices':[0,0,0], 'faces':[]}, 'existing')
    server.STATE['parts'] = [p]
    before = copy.deepcopy(server.STATE)
    status, r = http('/api/tool', {'name':'update_part', 'args':{'id':p['id'],'params':{'vertices':[1,2,3]}}})
    assert status == 200 and r['result']['error_kind'] == 'bad_args' and server.STATE == before
    status, r = http('/api/scene', {'parts':[], 'view':{'vertices':[1,2,3]}})
    assert status == 422 and server.STATE == before


def test_modal_rejects_geometry_tool_before_remote(monkeypatch):
    monkeypatch.setenv('AETHER_COMPUTE', 'modal')
    monkeypatch.setattr(compute, '_fn', lambda *a: pytest.fail('Modal was contacted for a disabled builder'))
    st = lab.default_state(); old = copy.deepcopy(st)
    for name in lab.DISABLED:
        assert compute.run(st, name, {})['error_kind'] == 'unavailable'
    assert st == old


@pytest.mark.parametrize('classified', ['machine', 'part'])
def test_auto_unavailable_does_not_invoke_cad_or_modify_scene(http, monkeypatch, classified):
    import vision
    p = lab._part('cad', {'vertices': [0, 0, 0], 'faces': []}, 'existing')
    server.STATE['parts'] = [p]
    original = copy.deepcopy(server.STATE)
    monkeypatch.setattr(vision, 'upload_kind', lambda image: (classified, {'evidence': 'test classification'}))
    monkeypatch.setattr(agent, '_sheet_to_cad', lambda *a, **k: pytest.fail('wrong builder invoked'))
    status, r = http('/api/photo', {'image': 'test', 'kind': 'auto'})
    assert status == 200 and r['trace'][0]['result']['kind'] == classified
    assert r['trace'][0]['result']['error'] and r['trace'][0]['result']['scene_unchanged']
    assert server.STATE == original


def test_auto_three_view_dispatches_only_to_cad(http, monkeypatch):
    import vision
    calls = []
    monkeypatch.setattr(vision, 'upload_kind', lambda image: ('three_view', {'evidence': 'test classification'}))
    monkeypatch.setattr(cad_client, 'available', lambda: True)
    monkeypatch.setattr(compute, 'prewarm', lambda: None)
    def fail_build(state, history, *args):
        calls.append('cad')
        return 'failed', [{'tool': 'cad_pipeline', 'result': {'error': 'test failure', 'scene_unchanged': True}}], {}, history
    monkeypatch.setattr(agent, '_sheet_to_cad', fail_build)
    before = copy.deepcopy(server.STATE)
    status, r = http('/api/photo', {'image': 'test', 'kind': 'auto'})
    assert status == 200 and calls == ['cad'] and r['trace'][1]['result']['error']
    assert server.STATE == before


def test_modal_result_cannot_replace_local_geometry(monkeypatch):
    monkeypatch.setenv('AETHER_COMPUTE', 'modal')
    monkeypatch.setitem(compute.status, 'checked', 1)
    monkeypatch.setitem(compute.status, 'stale', False)
    st = lab.default_state()
    p = lab._part('cad', {'vertices': [0, 0, 0], 'faces': []}, 'existing')
    st['parts'] = [p]; st['selected'] = p['id']
    old = copy.deepcopy(st['parts'])
    remote = copy.deepcopy(st)
    remote['parts'] = [lab._part('cad', {'vertices': [5, 5, 5], 'faces': []}, 'injected')]
    remote['selected'] = remote['parts'][0]['id']
    monkeypatch.setattr(compute, '_remote_run', lambda *args: ({'_backend': 'mock'}, remote, None))
    r = compute.run(st, 'desk_score', {})
    assert r['_ran_on'] == 'modal' and st['parts'] == old and st['selected'] == p['id']
