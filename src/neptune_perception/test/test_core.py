"""Focused response, observation and freshness acceptance checks."""

from copy import deepcopy
import pytest

from neptune_perception.core import (
    Freshness, LatestFrame, MODEL_ID, ModelUnavailable, SchemaError,
    parse_response, validate_classes,
)


def response(predictions=None):
    return dict(model_id=MODEL_ID, classes=['pipe', 'valve', 'flange'],
                image=dict(width=320, height=240),
                runtime=dict(providers=['CUDAExecutionProvider'], cuda_node_events=10),
                predictions=[] if predictions is None else predictions)


def prediction(**overrides):
    return dict(dict({'class': 'pipe'}, confidence=0.8, x=240, y=60, width=80, height=40),
                **overrides)


def test_bbox_center_and_signed_normalized_errors():
    observation, = parse_response(response([prediction()]), 320, 240)
    assert observation.xyxy == (200, 40, 280, 80)
    assert observation.center == (240, 60)
    assert observation.horizontal_error == 0.5
    assert observation.vertical_error == -0.5
    assert observation.as_dict()['orientation_valid'] is False
    assert observation.as_dict()['orientation_rad'] is None


def test_bbox_clipping_recomputes_center_and_errors():
    observation, = parse_response(response([prediction(x=315, y=235)]), 320, 240)
    assert observation.xyxy == (275, 215, 320, 240)
    assert observation.center == (297.5, 227.5)
    assert observation.horizontal_error == (297.5-160)/160
    assert observation.vertical_error == (227.5-120)/120


def test_empty_predictions():
    assert parse_response(response(), 320, 240) == []


@pytest.mark.parametrize('classes', [None, [], ['pipe'], ['pipe', 'valve', 'wedge'],
                                    ['pipe', 'pipe', 'flange'], {}, [[], 'pipe', 'valve']])
def test_reject_class_schema(classes):
    with pytest.raises(SchemaError):
        validate_classes(classes)


@pytest.mark.parametrize('patch', [
    {'confidence': -1}, {'confidence': float('nan')}, {'confidence': True},
    {'x': '1'}, {'x': float('inf')}, {'width': 0}, {'height': -1},
    {'x': -100}, {'class': 'wedge'}, {'class': []}, {'y': None},
    {'class_id': 1}, {'class_id': -1}, {'class_id': True},
])
def test_malformed_predictions(patch):
    p = prediction()
    p.update(patch)
    with pytest.raises(SchemaError):
        parse_response(response([p]), 320, 240)


@pytest.mark.parametrize('patch', [
    {'model_id': 'other'}, {'image': {'width': 640, 'height': 480}},
    {'predictions': None}, {'predictions': {}}, {'predictions': [None]},
    {'predictions': [prediction()]*301}, {'classes': ['pipe', 'valve', 'unknown']},
])
def test_malformed_responses(patch):
    payload = response()
    payload.update(patch)
    with pytest.raises(SchemaError):
        parse_response(payload, 320, 240)


def test_gpu_required():
    payload = response()
    payload['runtime']['providers'] = ['CPUExecutionProvider']
    with pytest.raises(ModelUnavailable):
        parse_response(payload, 320, 240)
    payload['runtime']['providers'] = ['CUDAExecutionProvider']
    payload['runtime']['cuda_node_events'] = 0
    with pytest.raises(ModelUnavailable):
        parse_response(payload, 320, 240)


def test_camera_stale_and_model_unavailable_are_explicit():
    state = Freshness(0)
    assert state.snapshot(0.1, 100)['state'] == 'MODEL_UNAVAILABLE'
    assert state.snapshot(0.6, 100)['state'] == 'CAMERA_STALE'
    state.camera(0.6)
    state.begin(100, 0.6)
    state.fail('MODEL_UNAVAILABLE', 0.7)
    assert state.snapshot(0.7, 100.1)['state'] == 'MODEL_UNAVAILABLE'
    assert state.snapshot(1.2, 100.6)['state'] == 'CAMERA_STALE'
    assert state.snapshot(1.2, 100.6)['model_state'] == 'MODEL_UNAVAILABLE'


@pytest.mark.parametrize('observations,expected', [([prediction()], 'READY'), ([], 'NO_DETECTION')])
def test_ready_and_no_detection_expire(observations, expected):
    state = Freshness(0)
    state.camera(0)
    state.begin(100, 0)
    state.finish(100, 0, 0.1, 100.1, observations)
    assert state.snapshot(0.1, 100.1)['state'] == expected
    state.camera(0.6)
    assert state.snapshot(0.6, 100.6)['state'] == 'STALE'
    assert state.snapshot(1.2, 101.2)['state'] == 'CAMERA_STALE'
    assert not state.snapshot(1.2, 101.2)['observation_valid']


@pytest.mark.parametrize('end,ros_now', [(0.7, 100.7), (0.1, 100.7), (0.1, 99.9)])
def test_stale_result_never_ready(end, ros_now):
    state = Freshness(0)
    state.camera(end)
    state.begin(100, 0)
    state.finish(100, 0, end, ros_now, [prediction()])
    assert state.snapshot(end, ros_now)['state'] == 'STALE'
    assert state.last_valid_observation is None


def test_request_does_not_relabel_previous_observation_timestamp():
    state = Freshness(0)
    state.camera(0.1)
    state.finish(100, 0, 0.1, 100.1, [prediction()])
    state.begin(100.2, 0.2)
    status = state.snapshot(0.2, 100.2)
    assert status['source_stamp_s'] == 100
    assert status['in_flight_source_stamp_s'] == 100.2
    assert status['observation_age_s'] == pytest.approx(0.2)


def test_latest_frame_replacement():
    slot = LatestFrame()
    slot.put('first')
    assert slot.take() == 'first'  # worker owns this in-flight frame
    slot.put('second')
    slot.put('third')
    assert slot.counts() == dict(received_frames=3, replaced_frames=1, pending_frames=1)
    assert slot.take() == 'third'
    assert slot.take() is None


def test_parse_does_not_mutate_response():
    payload = response([prediction()])
    original = deepcopy(payload)
    parse_response(payload, 320, 240)
    assert payload == original
