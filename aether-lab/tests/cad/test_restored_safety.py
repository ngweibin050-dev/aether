"""Fail-closed export and truthful CAD quality reporting on synthetic B-reps."""
import json, struct
from pathlib import Path
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from cad import worker, pipeline, export

@pytest.fixture
def box_doc(tmp_path):
    old = dict(worker.STATE)
    f = tmp_path / 'box.step'
    w = STEPControl_Writer(); w.Transfer(BRepPrimAPI_MakeBox(10,20,30).Shape(), STEPControl_AsIs); w.Write(str(f))
    worker.cmd_import_step({'path':str(f),'out_dir':str(tmp_path/'current')})
    try: yield worker.STATE['doc']
    finally: worker.STATE.clear(); worker.STATE.update(old)

def test_empty_assembly_fails():
    class D: data={'components':[],'joints':[]}; shapes={}
    assert pipeline.assembly_validation(D())['all_valid'] is False

@pytest.mark.parametrize('kind',['step','glb','blender_glb'])
def test_invalid_assembly_blocks_export_and_preserves_file(box_doc,monkeypatch,kind):
    name={'step':'model.step','glb':'model.glb','blender_glb':'model-blender.glb'}[kind]
    p=Path(worker.STATE['out_dir'])/name; p.write_bytes(b'previous')
    monkeypatch.setattr(pipeline,'assembly_validation',lambda *a,**k:{'all_valid':False})
    with pytest.raises(RuntimeError,match='validation failed'):worker.cmd_export({'kind':kind})
    assert p.read_bytes()==b'previous'

def test_blender_glb_is_derived_and_has_no_line_overlay(box_doc):
    p=Path(worker.cmd_export({'kind':'blender_glb'})['path']); data=p.read_bytes()
    n=struct.unpack_from('<I',data,12)[0]; g=json.loads(data[20:20+n])
    assert all(pr.get('mode',4)==4 for m in g['meshes'] for pr in m['primitives'])
    assert g['scenes'][0]['extras']['document_id']==box_doc.data['document_id']

def test_failed_roundtrip_preserves_previous_exports(box_doc,monkeypatch,tmp_path):
    step=tmp_path/'model.step'; glb=tmp_path/'model.glb'; step.write_bytes(b'old STEP'); glb.write_bytes(b'old GLB')
    def failed(comps,path,brep): Path(path).write_bytes(b'invalid'); return {'all_pass':False}
    monkeypatch.setattr(export,'roundtrip',failed)
    report=pipeline.finalize(box_doc,{},str(tmp_path),log=lambda *a:None,s8=False)
    assert 'blocked' in report['exports'] and step.read_bytes()==b'old STEP' and glb.read_bytes()==b'old GLB'

def test_high_iou_is_not_accuracy_or_production_certification():
    q=pipeline.quality_assessment({k:{'iou':.99} for k in ('side','top','front','rear')})
    assert q['silhouette_threshold_0_9_met'] and q['dimensional_accuracy']=='not verified'
    assert q['drawing_detail_fidelity']=='not verified' and q['blender_production_readiness']=='not verified'

def test_validation_cannot_be_disabled(tmp_path):
    with pytest.raises(RuntimeError,match='cannot be disabled'):
        worker.cmd_build({'sheet':'none','out_dir':str(tmp_path/'none'),'finalize':False})
