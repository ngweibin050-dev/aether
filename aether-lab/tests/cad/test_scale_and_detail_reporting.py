"""Scale and evidence tests: all geometry here is synthetic, never a benchmark drawing."""
import copy
import math
import pytest
from cad import pipeline, planner, scale, vehicle, worker
from cad.document import Document
from cad.ops import OPS
from cad.validate import bbox


def synthetic_obs():
    return {'fit': {'length_side_px': 1000, 'ratio_side_over_top': 1.0, 'ratio_side_over_end': 1.0},
            'views': {'side': {'extent': [0, 0, 999, 200], 'ground_v': 200},
                      'top': {'extent': [0, 0, 999, 200]}},
            'top': {'v_c': 100}, 'ends': {'end_a': {'u_c': 100, 'ground_v': 200},
                                          'end_b': {'u_c': 100, 'ground_v': 200}}}


def decisions(length):
    return {'overall_length_mm': scale.length_decision(length), 'nose_left': {'value': True},
            'front_view': {'value': 'end_a'}}


def scaled_doc(length):
    d = Document.new({'file': 'synthetic'}, 'synthetic')
    d['decisions'] = decisions(length)
    d['parameters'] = {'overall_length': {'provenance': 'user_confirmed', 'value': length, 'unit': 'mm', 'range': [500, 20000]},
                       'tube_length': {'provenance': 'derived', 'unit': 'mm', 'rel': planner.scaled(450)}}
    d['features'] = [{'id':'tip', 'op':'exhaust_tip', 'inputs':[],
                      'params':{'y':0, 'z':0, 'r':10, 'wall':1, 'x0':0, 'x1':{'$p':'tube_length'}}}]
    d['components'] = [{'id':'c', 'name':'Synthetic tube', 'kind':'exhaust_tip', 'output':'tip'}]
    d['assumptions'] = [{'id':'A-01', 'text':'test', 'class':'user_confirmed', 'affects':[], 'editable_via':[]}]
    return Document(d, OPS)


@pytest.mark.parametrize('length', [500, 4500, 9000, 20000])
def test_reference_frame_and_geometry_are_scaled_once(length):
    obs = synthetic_obs()
    ref = pipeline.reference_frame(obs, decisions(length))
    actual = vehicle.frames(obs, decisions(length))
    assert ref['side']['s'] == pytest.approx(4.5)
    assert actual['side']['s'] == pytest.approx(length / 1000)
    doc = scaled_doc(length)
    assert doc.recompute()['state'] == 'ok'
    assert doc.param_values()['tube_length'] == pytest.approx(length / 10)
    bb = bbox(doc.shapes['tip'])
    assert bb[3] - bb[0] == pytest.approx(length / 10, abs=0.02)


@pytest.mark.parametrize('bad', [0, -1, 499, 20001, float('nan'), float('inf'), True, 'garbage'])
def test_bad_length_rejected_before_build(bad, tmp_path):
    with pytest.raises(ValueError, match='overall length'):
        pipeline.build('not-an-image', str(tmp_path), decisions={'overall_length_mm': {'value': bad, 'provenance':'user_confirmed'}})


def test_missing_length_is_assumed():
    d = scale.length_decision(None)
    assert d['value'] == 4500 and d['provenance'] == 'assumed'
    assert 'not automatically read' in d['note']


def test_edit_changes_actual_frame_and_invalidates_old_report(tmp_path):
    doc = scaled_doc(4500)
    assert doc.recompute(validate=worker._full_validate)['state'] == 'ok'
    old = dict(worker.STATE)
    out = tmp_path / 'current'; out.mkdir()
    for name in ('report.json','reproject_side.png'):
        (out / name).write_text('stale')
    obs = synthetic_obs()
    worker.STATE.update(doc=doc, out_dir=str(out), res={'obs': obs, 'F': vehicle.frames(obs, decisions(4500))}, sheet=None)
    try:
        result = worker.cmd_set_param({'id':'overall_length', 'value':9000})
        assert result['status']['state'] == 'ok'
        assert doc.param_values()['tube_length'] == pytest.approx(900)
        assert worker.STATE['res']['F']['side']['s'] == pytest.approx(9)
        assert doc.data['decisions']['overall_length_mm']['value'] == 9000
        assert doc.data['validation']['summary']['step_roundtrip_pass'] is None
        assert not (out / 'report.json').exists() and not (out / 'reproject_side.png').exists()
        with pytest.raises(RuntimeError, match='not been rerun'):
            worker.cmd_export({'kind':'report'})
    finally:
        worker.STATE.clear(); worker.STATE.update(old)


def test_optional_failures_and_partial_imprints_are_not_reported_built():
    class Fake:
        data = {'features': [
            {'id':'body.imprint_headlight_front', 'status':'failed_optional', 'error':'outline misses body'},
            {'id':'body.imprint_door_side', 'status':'ok'},
            {'id':'body.imprint_windscreen_top', 'status':'ok'}]}
        info = {'body.imprint_door_side': {'tolerance_budget': {'edges_left_out': 2}},
                'body.imprint_windscreen_top': {'tolerance_budget': {'edges_left_out': 0}}}
    selected = [{'region_id':kind, 'kind':kind, 'op':'imprint', 'view':view} for kind, view in
                [('headlight','front'), ('door','side'), ('windscreen','top')]]
    result = pipeline.region_execution_outcomes(Fake(), selected, [])
    assert [x['kind'] for x in result['built']] == ['windscreen']
    assert [x['kind'] for x in result['partial']] == ['door']
    assert [x['kind'] for x in result['not_built']] == ['headlight']
    assert 'misses body' in result['not_built'][0]['why']


def test_failed_scale_edit_keeps_existing_report(tmp_path):
    doc = scaled_doc(4500)
    assert doc.recompute(validate=worker._full_validate)['state'] == 'ok'
    previous = dict(worker.STATE)
    out = tmp_path/'current'; out.mkdir(); (out/'report.json').write_text('old valid report')
    worker.STATE.update(doc=doc, out_dir=str(out), res=None, sheet=None)
    try:
        result = worker.cmd_set_param({'id':'overall_length', 'value':100})
        assert result['status']['state'] != 'ok'
        assert doc.param_values()['overall_length'] == 4500
        assert (out/'report.json').read_text() == 'old valid report'
    finally:
        worker.STATE.clear(); worker.STATE.update(previous)


def test_checkpoint_rollback_restores_scale_frame_and_report(tmp_path):
    doc = scaled_doc(4500)
    assert doc.recompute(validate=worker._full_validate)['state'] == 'ok'
    previous = dict(worker.STATE)
    out = tmp_path/'current'; out.mkdir(); (out/'report.json').write_text('old valid report')
    obs = synthetic_obs()
    worker.STATE.update(doc=doc, out_dir=str(out), res={'obs':obs, 'F':vehicle.frames(obs, decisions(4500))}, sheet=None)
    try:
        worker.cmd_checkpoint({'out_dir':str(out)})
        assert worker.cmd_set_param({'id':'overall_length', 'value':9000})['status']['state'] == 'ok'
        worker.cmd_checkpoint_rollback({})
        assert worker.STATE['doc'].param_values()['overall_length'] == 4500
        assert worker.STATE['res']['F']['side']['s'] == pytest.approx(4.5)
        assert (out/'report.json').read_text() == 'old valid report'
    finally:
        if worker.CHECKPOINT is not None: worker.cmd_checkpoint_rollback({})
        worker.STATE.clear(); worker.STATE.update(previous)
