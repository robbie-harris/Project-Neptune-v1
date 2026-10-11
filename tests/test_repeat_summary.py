import copy
import pytest
from summarize_repeats import summarize


def reports():
    tests = [{'training_id': f'job-{i}', 'weights_sha256': f'run-{i}', 'split': 'test', 'images': 900, 'confidence': .25,
              'dataset_validation': {'manifest_sha256': 'frozen'}, 'recall_iou_0_5': .94 + .01*i,
              'negative_frame_fpr': .02, 'latency_ms_mean': 15, 'latency_ms_p95': 22, 'passed': i > 0,
              'slices': {f'angle_bin:{j}': {'targets': 100, 'recall': .94 + .01*i} for j in range(6)}} for i in range(3)]
    validations = [{'training_id': r['training_id'], 'weights_sha256': r['weights_sha256'], 'split': 'val', 'images': 900,
                    'confidence_selection_split': 'val', 'confidence': .25,
                    'dataset_validation': {'manifest_sha256': 'frozen'}} for r in tests]
    return tests, validations


def test_summary_reports_variability_and_failures():
    result = summarize(*reports())
    assert result['metrics']['recall_iou_0_5']['mean'] == pytest.approx(.95)
    assert result['metrics']['recall_iou_0_5']['sample_std'] == pytest.approx(.01)
    assert not result['all_accuracy_targets_passed']


def test_summary_rejects_reused_training_job_and_changed_distribution():
    for field, value in [('training_id', 'job-0'), ('dataset_validation', {'manifest_sha256': 'other'}), ('split', 'val')]:
        tests, validations = reports()
        tests[1][field] = value
        if field == 'training_id': validations[1][field] = value
        with pytest.raises(ValueError): summarize(tests, validations)


def test_deterministic_managed_repeats_can_have_identical_weights():
    tests, validations = reports()
    for report in tests + validations: report['weights_sha256'] = 'same-weights'
    assert summarize(tests, validations)['distinct_weight_hashes'] == 1


def test_roboflow_repeats_use_model_ids_without_claiming_weight_hashes():
    tests, validations = reports()
    for i,(test,validation) in enumerate(zip(tests,validations)):
        for report in (test,validation):
            report.update(backend='roboflow',weights_sha256=None,model_id=f'workspace/run-{i}')
    result=summarize(tests,validations)
    assert result['distinct_model_ids']==3
    assert result['distinct_weight_hashes'] is None
    tests[1]['model_id']='different-model'
    with pytest.raises(ValueError): summarize(tests,validations)
