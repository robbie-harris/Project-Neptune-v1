import copy
import hashlib
import pytest
from promote_model import check_candidate


def reports(tmp_path):
    weights=tmp_path/'candidate.pt'; weights.write_bytes(b'candidate weights')
    digest=hashlib.sha256(weights.read_bytes()).hexdigest()
    evaluation={'weights_sha256':digest,'passed':True,'split':'test','confidence':.3,'recall_iou_0_5':.96,'negative_frame_fpr':.02,'slices':{f'angle_bin:{i}':{'recall':.94} for i in range(6)}}
    live={'passed':True,'weights_sha256':digest,'detector':{'state':'ready','confidence_threshold':.3},'wall_rates_hz':{'annotated':3.5},'sampled_inference_latency_ms':{'p95':55}}
    baseline={'wall_rates_hz':{'annotated':3.4},'sampled_inference_latency_ms':{'p95':50},'gui_fresh_fps_median':3.4}
    live.update(gui_fresh_fps_median=3.5,gui_fresh_fps_samples=[3.4,3.5,3.6])
    evaluation['dataset_validation']={'manifest_sha256':'frozen-dataset'}
    validation={'weights_sha256':digest,'split':'val','confidence_selection_split':'val','confidence':.3,'dataset_validation':{'manifest_sha256':'frozen-dataset'}}
    return weights,evaluation,live,baseline,validation


def test_only_verified_candidate_can_be_promoted(tmp_path):
    weights,evaluation,live,baseline,validation=reports(tmp_path)
    assert check_candidate(weights,evaluation,live,baseline,validation)==evaluation['weights_sha256']
    for field,value in [('diagnostic_only',True),('split','val'),('weights_sha256','other'),('recall_iou_0_5',.94),('negative_frame_fpr',.06)]:
        modified=copy.deepcopy(evaluation); modified[field]=value
        with pytest.raises(ValueError): check_candidate(weights,modified,live,baseline,validation)
    modified=copy.deepcopy(evaluation); modified['slices']['angle_bin:5']['recall']=.89
    with pytest.raises(ValueError): check_candidate(weights,modified,live,baseline,validation)


def test_live_identity_threshold_and_runtime_gates(tmp_path):
    weights,evaluation,live,baseline,validation=reports(tmp_path)
    for section,key,value in [(None,'weights_sha256','other'),('detector','confidence_threshold',.25),('wall_rates_hz','annotated',2.9),('sampled_inference_latency_ms','p95',56),(None,'gui_fresh_fps_median',2.9),(None,'gui_fresh_fps_samples',[])]:
        modified=copy.deepcopy(live)
        if section: modified[section][key]=value
        else: modified[key]=value
        with pytest.raises(ValueError): check_candidate(weights,evaluation,modified,baseline,validation)


def test_promotion_requires_validation_only_selection(tmp_path):
    weights,evaluation,live,baseline,validation=reports(tmp_path)
    for field,value in [("split","test"),("confidence_selection_split",None),("confidence",.25),("diagnostic_only",True)]:
        modified=copy.deepcopy(validation); modified[field]=value
        with pytest.raises(ValueError): check_candidate(weights,evaluation,live,baseline,modified)
    modified=copy.deepcopy(validation); modified["dataset_validation"]["manifest_sha256"]="other dataset"
    with pytest.raises(ValueError): check_candidate(weights,evaluation,live,baseline,modified)
