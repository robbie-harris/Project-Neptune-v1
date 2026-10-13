"""Pure P4c source association, selection, bounds and freshness regressions."""
from copy import deepcopy

import pytest

from neptune_perception.fusion import MODELS, MatchingCache, associate, fuse, iou


def box(xyxy=(200, 40, 280, 80), confidence=0.8, label='pipe'):
    x1, y1, x2, y2 = xyxy
    u, v = (x1+x2)/2, (y1+y2)/2
    return dict(class_name=label, confidence=confidence, xyxy=list(xyxy), center=[u, v],
                horizontal_error=(u-160)/160, vertical_error=(v-120)/120,
                orientation_valid=False, orientation_rad=None)


def status(model='inspection', observations=None, sec=100, ns=0, **patch):
    s = dict(model_id=MODELS[model], source_header=dict(stamp=dict(sec=sec, nanosec=ns), frame_id='camera'),
             image_width=320, image_height=240, observations=[box()] if observations is None else observations,
             state='READY', observation_valid=True, processing_latency_s=0.02, result_receipt_age_s=0.01)
    s.update(patch)
    return s


def test_iou_identical():
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1


def test_iou_disjoint():
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0


def test_iou_partial():
    assert iou([0, 0, 10, 10], [5, 0, 15, 10]) == pytest.approx(1/3)


def test_iou_degenerate():
    assert iou([0, 0, 0, 0], [0, 0, 0, 0]) == 0


@pytest.mark.parametrize('threshold,count', [(0.30, 1), (0.34, 2), (1/3, 1)])
def test_threshold(threshold, count):
    assert len(associate([box((0, 0, 10, 10))], [box((5, 0, 15, 10))], threshold)) == count


def test_one_to_one():
    records = associate([box(), box()], [box()])
    assert [r['state'] for r in records] == ['CONSENSUS', 'INSPECTION_ONLY']


def test_multiple_pipes():
    boxes = [box(), box((0, 0, 50, 30))]
    records = associate(boxes, list(reversed(boxes)))
    assert len(records) == 2 and all(r['iou'] == 1 for r in records)
    assert all(r['inspection_bbox'] == r['orientation_a_bbox'] for r in records)


def test_consensus_confidences_and_geometry_not_averaged():
    i, a = status(), status('orientation_a', [box((201, 40, 281, 80), 0.2)])
    result = fuse(i, a)
    t = result['selected_target']
    assert result['state'] == 'CONSENSUS' and result['source_matched']
    assert t['inspection_confidence'] == 0.8 and t['orientation_a_confidence'] == 0.2
    assert t['bbox'] == i['observations'][0]['xyxy']
    assert t['bbox_source'] == 'inspection' and t['model_provenance'] == list(MODELS.values())
    assert not result['orientation_valid'] and not t['orientation_valid']
    assert result['orientation_rad'] is None


@pytest.mark.parametrize('model,state', [('inspection', 'INSPECTION_ONLY'), ('orientation_a', 'ORIENTATION_A_ONLY')])
def test_single_model(model, state):
    result = fuse(status() if model == 'inspection' else None,
                  status('orientation_a') if model == 'orientation_a' else None)
    assert result['state'] == state and result['valid']


def test_recovery_when_semantic_detector_misses():
    result = fuse(status(observations=[]), status('orientation_a'))
    assert result['state'] == 'ORIENTATION_A_ONLY'
    assert result['selected_target']['inspection_confidence'] is None


def test_inspection_when_a1_misses():
    assert fuse(status(), status('orientation_a', []))['state'] == 'INSPECTION_ONLY'


def test_unmatched_multiple_ambiguous():
    r = fuse(status(), status('orientation_a', [box((0, 0, 10, 10))]))
    assert r['state'] == 'AMBIGUOUS' and not r['valid'] and r['selected_target'] is None


def test_tied_pairs_ambiguous():
    boxes = [box(), box((0, 0, 10, 10))]
    assert fuse(status(observations=boxes), status('orientation_a', boxes))['state'] == 'AMBIGUOUS'


def test_highest_iou_pair_selected():
    i = [box(), box((0, 0, 10, 10))]
    a = [box((201, 40, 281, 80)), box((1, 0, 11, 10))]
    r = fuse(status(observations=i), status('orientation_a', a))
    assert r['selected_target']['bbox'] == i[0]['xyxy']


def test_no_pipe():
    r = fuse(status(observations=[]), status('orientation_a', []))
    assert r['state'] == 'NO_PIPE' and not r['valid']


def test_normalized_errors():
    t = fuse(status(), None)['selected_target']
    assert t['center'] == [240, 60] and t['horizontal_error'] == 0.5 and t['vertical_error'] == -0.5


def test_semantics_pass_through_unchanged():
    observations = [box(label='valve'), box(label='flange')]
    original = deepcopy(observations)
    r = fuse(status(observations=observations), status('orientation_a', []))
    assert r['state'] == 'NO_PIPE'
    assert r['semantic_detections'] == [dict(o, model_id=MODELS['inspection']) for o in original]
    assert observations == original


@pytest.mark.parametrize('change', ['stamp', 'frame_id', 'dimensions'])
def test_mismatched_source_rejection(change):
    a = status('orientation_a')
    if change == 'stamp':
        a['source_header']['stamp']['nanosec'] = 1
    elif change == 'frame_id':
        a['source_header']['frame_id'] = 'different'
    else:
        a['image_width'] = 640
    with pytest.raises(ValueError):
        fuse(status(), a)


def test_exact_nanosecond_cache_matching():
    c = MatchingCache()
    assert c.add('inspection', status(ns=1), 0, 100.1) == []
    assert c.add('orientation_a', status('orientation_a', ns=2), 0.01, 100.1) == []
    assert len(c.pending) == 2
    outputs = c.add('orientation_a', status('orientation_a', ns=3), 0.3, 100.3)
    assert len(outputs) == 2 and all(not o['source_matched'] for o in outputs)


def test_matching_identical_sources():
    c = MatchingCache()
    c.add('inspection', status(), 0, 100.1)
    r = c.add('orientation_a', status('orientation_a'), 0.05, 100.15)
    assert len(r) == 1 and r[0]['source_matched']
    assert c.pending == {}


@pytest.mark.parametrize('patch', [dict(observation_valid=False, state='STALE'),
                                   dict(processing_latency_s=0.6), dict(result_receipt_age_s=0.6)])
def test_stale_inputs(patch):
    c = MatchingCache()
    assert c.add('inspection', status(**patch), 0, 100.1) == []
    assert c.rejected == 1 and not c.pending


@pytest.mark.parametrize('ros_now', [99.9, 100.6])
def test_source_age_rejected(ros_now):
    c = MatchingCache()
    c.add('inspection', status(), 0, ros_now)
    assert c.rejected == 1


def test_unavailable_model_fallback():
    c = MatchingCache()
    c.add('orientation_a', status('orientation_a', observation_valid=False, state='MODEL_UNAVAILABLE'), 0, 100.1)
    c.add('inspection', status(), 0, 100.1)
    r = c.flush(0.21, 100.31)[0]
    assert r['state'] == 'INSPECTION_ONLY'
    assert r['model_states']['orientation_a'] == 'MODEL_UNAVAILABLE'


def test_bounded_cache():
    c = MatchingCache(capacity=2)
    for ns in range(10):
        c.add('inspection', status(ns=ns), ns*0.001, 100.1)
        assert len(c.pending) <= 2
    assert c.evicted == 8


def test_delayed_result_never_retroactively_published():
    c = MatchingCache()
    c.add('inspection', status(), 0, 100.1)
    assert c.flush(0.21, 100.31)[0]['state'] == 'INSPECTION_ONLY'
    assert c.add('orientation_a', status('orientation_a'), 0.22, 100.32) == []
    assert not c.pending


def test_watchdog_duplicates_not_cached():
    c = MatchingCache()
    c.add('inspection', status(), 0, 100.1)
    c.add('inspection', status(), 0.1, 100.2)
    assert len(c.pending) == 1 and c.pending[(100, 0)]['first'] == 0


def test_waiting_source_expires():
    c = MatchingCache()
    c.add('inspection', status(), 0, 100.1)
    r = c.flush(0.6, 100.7)[0]
    assert r['state'] == 'STALE' and not r['valid'] and not r['pipes']


def test_frame_id_cache_rejection():
    c = MatchingCache()
    c.add('inspection', status(), 0, 100.1)
    a = status('orientation_a')
    a['source_header']['frame_id'] = 'different'
    assert c.add('orientation_a', a, 0.01, 100.11) == []
    assert c.mismatched == 1


@pytest.mark.parametrize('kwargs', [dict(threshold=0), dict(threshold=1.1), dict(window=0.5), dict(capacity=0)])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        MatchingCache(**kwargs)


def test_dimensions_cache_rejection():
    c = MatchingCache()
    c.add('inspection', status(), 0, 100.1)
    assert c.add('orientation_a', status('orientation_a', image_width=640), 0.01, 100.11) == []
    assert c.mismatched == 1


def test_newer_pair_does_not_publish_older_pending_later():
    c = MatchingCache()
    c.add('inspection', status(ns=1), 0, 100.1)
    c.add('inspection', status(ns=2), 0.01, 100.1)
    assert c.add('orientation_a', status('orientation_a', ns=2), 0.02, 100.1)[0]['source_matched']
    assert not c.pending and c.flush(0.3, 100.3) == []


@pytest.mark.parametrize('field,value', [('sec', 100.0), ('nanosec', -1), ('nanosec', 1000000000)])
def test_invalid_source_stamp(field, value):
    c = MatchingCache()
    s = status()
    s['source_header']['stamp'][field] = value
    with pytest.raises(ValueError):
        c.add('inspection', s, 0, 100.1)
