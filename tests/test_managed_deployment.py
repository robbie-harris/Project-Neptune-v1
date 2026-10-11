"""Prevent activation from incomplete, mismatched, or slow managed runs."""
import copy
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('managed', Path(__file__).parents[1] / 'src/tools/check_managed_deployment.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def reports():
    common = dict(model_id='workspace/model', images=900, confidence=.05,
                  dataset_validation=dict(manifest_sha256='frozen'))
    validation = dict(common, split='val', confidence_selection_split='val')
    test = dict(common, split='test', passed=True, recall_iou_0_5=.99, negative_frame_fpr=.01,
                slices={f'angle_bin:{i}': dict(recall=.95) for i in range(6)})
    live = dict(passed=True, detector=dict(model_id='workspace/model', state='ready', confidence_threshold=.05),
                wall_rates_hz=dict(annotated=4), gui_fresh_fps_median=4, gui_fresh_fps_samples=[4],
                sampled_inference_latency_ms=dict(p95=250))
    return validation, test, live, copy.deepcopy(live)


def test_managed_identity_and_full_reports():
    v, t, live, baseline = reports()
    assert not module.check(v, t, live, baseline)
    live['detector']['model_id'] = 'different/model'
    assert any('identity' in e for e in module.check(v, t, live, baseline))
    v['images'] = 100
    assert any('Full validation' in e for e in module.check(v, t, live, baseline))


def test_missing_gui_and_latency_regression_block_activation():
    v, t, live, baseline = reports()
    live['sampled_inference_latency_ms']['p95'] = 300
    live['gui_fresh_fps_samples'] = []
    failures = module.check(v, t, live, baseline)
    assert any('latency' in e for e in failures)
    assert any('measurements missing' in e for e in failures)
