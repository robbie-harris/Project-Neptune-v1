"""A1 accepts only robust pipe boxes; physical orientation is always unavailable."""

from concurrent.futures import Future
from copy import deepcopy
from io import BytesIO
import json
from threading import Event
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
import rclpy
from cv_bridge import CvBridge
from rclpy.qos import ReliabilityPolicy

from neptune_perception import inference_server
from neptune_perception.backends import LocalInference
from neptune_perception.core import (
    A1_CLASSES, A1_MODEL_ID, MODEL_ID, ModelUnavailable, SchemaError,
    parse_response, validate_classes,
)
from neptune_perception.detector import InspectionObjects, stamp_seconds
from neptune_perception.orientation_a import OrientationA
from test_gpu_adapter import fake_runtime


def response(predictions=None):
    return dict(model_id=A1_MODEL_ID, classes=['pipe'],
                image=dict(width=320, height=240),
                runtime=dict(providers=['CUDAExecutionProvider'], cuda_node_events=10),
                predictions=[] if predictions is None else predictions)


def prediction(**overrides):
    p = dict({'class': 'pipe'}, class_id=0, confidence=0.8,
             x=240, y=60, width=80, height=40)
    p.update(overrides)
    return p


def parse(payload):
    return parse_response(payload, 320, 240, A1_MODEL_ID, A1_CLASSES)


def test_exact_a1_contract_and_p4a_defaults():
    assert A1_MODEL_ID == 'projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1'
    assert A1_CLASSES == {'pipe'}
    assert OrientationA.model_id == A1_MODEL_ID
    assert InspectionObjects.model_id == MODEL_ID
    assert not InspectionObjects.reject_stale_completions
    assert InspectionObjects.inference_route == '/infer'
    with pytest.raises(SchemaError):
        parse_response(response(), 320, 240)  # P4a never accepts A1 by default
    wrong = response()
    wrong['model_id'] = MODEL_ID
    with pytest.raises(SchemaError):
        parse(wrong)


@pytest.mark.parametrize('classes', [None, [], ['valve'], ['flange'], ['pipe', 'valve'],
                                    ['pipe', 'valve', 'flange'], ['pipe', 'pipe'], {}])
def test_pipe_only_schema_rejects_other_classes(classes):
    with pytest.raises(SchemaError):
        validate_classes(classes, A1_CLASSES)
    payload = response()
    payload['classes'] = classes
    with pytest.raises(SchemaError):
        parse(payload)


@pytest.mark.parametrize('patch', [
    {'class': 'valve'}, {'class': 'flange'}, {'class': []}, {'class_id': 1},
    {'confidence': -1}, {'confidence': float('nan')}, {'confidence': True},
    {'x': '1'}, {'x': float('inf')}, {'width': 0}, {'height': -1}, {'x': -100},
])
def test_malformed_or_unexpected_predictions(patch):
    with pytest.raises(SchemaError):
        parse(response([prediction(**patch)]))


@pytest.mark.parametrize('payload', [None, [], {}, response([None]),
                                    dict(response(), predictions=None),
                                    dict(response(), image=dict(width=640, height=480))])
def test_malformed_response(payload):
    with pytest.raises(SchemaError):
        parse(payload)


def test_response_clipping_center_and_signed_normalized_errors():
    payload = response([prediction(), prediction(x=315, y=235)])
    original = deepcopy(payload)
    normal, clipped = parse(payload)
    assert normal.xyxy == (200, 40, 280, 80)
    assert normal.center == (240, 60)
    assert normal.horizontal_error == 0.5
    assert normal.vertical_error == -0.5
    assert clipped.xyxy == (275, 215, 320, 240)
    assert clipped.center == (297.5, 227.5)
    assert clipped.horizontal_error == (297.5-160)/160
    assert clipped.vertical_error == (227.5-120)/120
    assert payload == original
    assert all(o.as_dict()['orientation_valid'] is False for o in (normal, clipped))
    assert all(o.as_dict()['orientation_rad'] is None for o in (normal, clipped))


def test_empty_prediction_response():
    assert parse(response()) == []


def test_a1_backend_selects_distinct_route_full_png():
    backend = LocalInference('http://127.0.0.1:9001', 1, '/infer/orientation_a')
    requests = []

    def open_request(request, **kwargs):
        requests.append(request)
        return BytesIO(json.dumps(response()).encode())

    backend.opener.open = open_request
    assert backend.infer(b'full-frame-png') == response()
    assert requests[0].full_url == 'http://127.0.0.1:9001/infer/orientation_a'
    assert requests[0].data == b'full-frame-png'
    assert 'Authorization' not in requests[0].headers


def test_a1_gpu_adapter_loads_exact_id_and_full_frame(monkeypatch, tmp_path):
    model, sessions, calls, profile = fake_runtime(monkeypatch, tmp_path, classes=['pipe'])
    import inference

    def get_model(**kwargs):
        assert kwargs == dict(model_id=A1_MODEL_ID, api_key='synthetic-test-key',
                              onnxruntime_execution_providers=['CUDAExecutionProvider'])
        return model

    monkeypatch.setattr(inference, 'get_model', get_model)
    image = np.full((240, 320, 3), (12, 34, 56), dtype=np.uint8)
    ok, png = cv2.imencode('.png', image)
    assert ok
    adapter = inference_server.GPUModel(A1_MODEL_ID, A1_CLASSES)
    result = adapter.infer(png.tobytes())
    assert result['model_id'] == A1_MODEL_ID
    assert result['classes'] == ['pipe']
    assert np.array_equal(calls[0][0], image)
    assert calls[0][1] == dict(confidence=0.05, iou_threshold=0.7, max_detections=300)
    assert result['runtime']['cuda_node_events'] == 2
    assert sessions[-1].fallback_disabled
    assert not profile.exists()


@pytest.mark.parametrize('classes', [['valve'], ['flange'], ['pipe', 'valve', 'flange']])
def test_a1_rejects_actual_loaded_model_schema(monkeypatch, tmp_path, classes):
    model, *_ = fake_runtime(monkeypatch, tmp_path, classes=classes)
    import inference
    monkeypatch.setattr(inference, 'get_model', lambda **kwargs: model)
    with pytest.raises(SchemaError):
        inference_server.GPUModel(A1_MODEL_ID, A1_CLASSES).load()


@pytest.fixture
def observer():
    rclpy.init()
    node = OrientationA()
    detections, annotated, statuses = [], [], []
    node.detections = SimpleNamespace(publish=detections.append)
    node.annotated = SimpleNamespace(publish=annotated.append)
    node.status = SimpleNamespace(publish=lambda m: statuses.append(json.loads(m.data)))
    try:
        yield node, detections, annotated, statuses
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


def image(node, value=123):
    frame = CvBridge().cv2_to_imgmsg(np.full((240, 320, 3), value, np.uint8), 'rgb8')
    frame.header.stamp = node.get_clock().now().to_msg()
    frame.header.frame_id = 'inspection_camera_optical'
    return frame


def completed(node, frame, observations, error=None, latency=0.02, receipt_delay=0):
    now = time.monotonic()
    end = now-receipt_delay
    node.freshness.camera(now)
    node.freshness.begin(stamp_seconds(frame.header), end-latency)
    node.frame = frame
    node.future = Future()
    node.future.set_result((end-latency, end, np.zeros((240, 320, 3), np.uint8),
                            observations, response()['runtime'], error))
    node.tick()


@pytest.mark.parametrize('observations,expected', [(parse(response([prediction()])), 'READY'),
                                                ([], 'NO_DETECTION')])
def test_output_headers_status_and_orientation_false(observer, observations, expected):
    node, detections, annotated, statuses = observer
    frame = image(node)
    completed(node, frame, observations)
    assert len(detections) == len(annotated) == 1
    assert detections[0].header == annotated[0].header == frame.header
    assert all(d.header == frame.header for d in detections[0].detections)
    status = statuses[-1]
    assert status['model_id'] == A1_MODEL_ID
    assert status['state'] == expected
    assert status['orientation_valid'] is False
    assert status['image_width'] == 320 and status['image_height'] == 240
    assert status['source_header']['stamp']['nanosec'] == frame.header.stamp.nanosec
    assert all(o['orientation_valid'] is False and o['orientation_rad'] is None
               for o in status['observations'])


@pytest.mark.parametrize('stale_by', ['source_age', 'latency', 'receipt_age'])
def test_stale_completion_rejected(observer, stale_by):
    node, detections, annotated, statuses = observer
    frame = image(node)
    if stale_by == 'source_age':
        frame.header.stamp.sec -= 1
    completed(node, frame, parse(response([prediction()])),
              latency=0.7 if stale_by == 'latency' else 0.02,
              receipt_delay=0.7 if stale_by == 'receipt_age' else 0)
    assert detections == annotated == []
    assert statuses[-1]['observations'] == []
    assert statuses[-1]['state'] == 'STALE'
    assert statuses[-1]['orientation_valid'] is False
    assert statuses[-1]['rejected_stale_results'] == 1
    assert node.processed == 0
    assert node.freshness.last_valid_observation is None


def test_p4a_stale_diagnostic_publication_contract_preserved(observer):
    # Additive regression: P4a's pre-existing tests and behavior stay unchanged.
    p4a = InspectionObjects()
    detections, annotated, statuses = [], [], []
    p4a.detections = SimpleNamespace(publish=detections.append)
    p4a.annotated = SimpleNamespace(publish=annotated.append)
    p4a.status = SimpleNamespace(publish=lambda m: statuses.append(json.loads(m.data)))
    try:
        frame = image(p4a)
        completed(p4a, frame, parse(response([prediction()])), latency=0.7)
        assert len(detections) == len(annotated) == 1
        assert detections[0].header == annotated[0].header == frame.header
        assert statuses[-1]['model_id'] == MODEL_ID
        assert statuses[-1]['state'] == 'STALE'
        assert not statuses[-1]['observation_valid']
        assert statuses[-1]['observations']
        assert 'rejected_stale_results' not in statuses[-1]
    finally:
        p4a.close()
        p4a.destroy_node()


@pytest.mark.parametrize('error', ['MODEL_UNAVAILABLE', 'SCHEMA_ERROR'])
def test_model_or_schema_failure_then_camera_stale(observer, error):
    node, detections, annotated, statuses = observer
    completed(node, image(node), [], error=error)
    assert detections == annotated == []
    assert statuses[-1]['state'] == error
    node.freshness.camera_received = time.monotonic()-0.6
    node.tick()
    assert statuses[-1]['state'] == 'CAMERA_STALE'
    assert statuses[-1]['model_state'] == error
    assert statuses[-1]['orientation_valid'] is False


@pytest.mark.parametrize('failure,expected', [(ModelUnavailable, 'MODEL_UNAVAILABLE'),
                                            (SchemaError, 'SCHEMA_ERROR')])
def test_real_worker_maps_failure_to_fixed_state(observer, failure, expected):
    node, *_ = observer

    def fail(_png):
        raise failure('untrusted upstream detail')

    node.backend.infer = fail
    result = node.infer(image(node))
    assert result[-1] == expected
    assert result[2:5] == (None, [], None)


def test_every_fresh_frame_latest_replacement_and_no_parallel_requests(observer):
    node, detections, annotated, statuses = observer
    qos = node.subscription.qos_profile
    assert qos.depth == 1 and qos.reliability == ReliabilityPolicy.BEST_EFFORT
    assert node.detection_topic == '/neptune/perception/orientation_a_detections'
    assert node.annotated_topic == '/neptune/perception/orientation_a_annotated'
    assert node.status_topic == '/neptune/perception/orientation_a_status'
    entered, release = Event(), Event()
    requests = []

    def infer(png):
        requests.append(png)
        entered.set()
        assert release.wait(1)
        return response([prediction()])

    node.backend.infer = infer
    first, second, third = image(node, 10), image(node, 20), image(node, 30)
    try:
        node.receive(first)
        node.tick()
        assert entered.wait(1)
        node.receive(second)
        node.receive(third)
        node.tick()
        assert len(requests) == 1
        assert statuses[-1]['pending_frames'] == statuses[-1]['in_flight'] == 1
        release.set()
        deadline = time.monotonic()+1
        while len(annotated) < 2 and time.monotonic() < deadline:
            node.tick()
            time.sleep(0.005)
        assert len(requests) == len(detections) == len(annotated) == 2
        assert annotated[0].header == first.header and annotated[1].header == third.header
        assert statuses[-1]['replaced_frames'] == 1
        # A1 alone also immediately processes the next fresh frame; no N=2 policy.
        fourth = image(node, 40)
        node.receive(fourth)
        node.tick()
        while len(annotated) < 3 and time.monotonic() < deadline:
            node.tick()
            time.sleep(0.005)
        assert len(requests) == len(annotated) == 3
        node.freshness.camera_received = time.monotonic()-0.6
        node.tick()
        assert statuses[-1]['state'] == 'CAMERA_STALE'
    finally:
        release.set()
