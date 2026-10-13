"""Use real Jazzy ROS messages and the actual single-worker observer."""

import json
from threading import Event
import time
from types import SimpleNamespace

import numpy as np
import rclpy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image

from neptune_perception.core import parse_response
from neptune_perception.detector import InspectionObjects, detection_message
from test_core import response, prediction


def test_detection_header_preserved_and_owned():
    source = Image()
    source.header.stamp.sec = 100
    source.header.stamp.nanosec = 123456789
    source.header.frame_id = 'camera_optical'
    observations = parse_response(response([prediction()]), 320, 240)
    message = detection_message(source.header, observations)
    assert message.header == source.header
    assert message.detections[0].header == source.header
    assert message.detections[0].bbox.center.position.x == 240
    assert message.detections[0].bbox.center.position.y == 60
    assert message.detections[0].results[0].hypothesis.class_id == 'pipe'
    source.header.frame_id = 'changed'
    assert message.header.frame_id == 'camera_optical'


def test_node_single_request_latest_replacement_headers_and_status():
    rclpy.init()
    node = InspectionObjects()
    entered, release = Event(), Event()
    requests, detections, annotated, statuses = [], [], [], []
    try:
        def infer(png):
            requests.append(png)
            entered.set()
            assert release.wait(2)
            return response([prediction()])
        node.backend.infer = infer
        node.detections = SimpleNamespace(publish=detections.append)
        node.annotated = SimpleNamespace(publish=annotated.append)
        node.status = SimpleNamespace(publish=lambda m: statuses.append(json.loads(m.data)))
        bridge = CvBridge()

        def image(value):
            message = bridge.cv2_to_imgmsg(np.full((240, 320, 3), value, np.uint8), 'rgb8')
            message.header.stamp = node.get_clock().now().to_msg()
            message.header.frame_id = 'inspection_camera'
            return message

        first, second, third = image(10), image(20), image(30)
        node.receive(first)
        node.tick()
        assert entered.wait(1)
        node.receive(second)
        node.receive(third)
        node.tick()
        assert len(requests) == 1
        assert statuses[-1]['in_flight'] == 1
        assert statuses[-1]['pending_frames'] == 1
        assert statuses[-1]['replaced_frames'] == 1
        release.set()
        deadline = time.monotonic()+2
        while len(annotated) < 2 and time.monotonic() < deadline:
            node.tick()
            time.sleep(0.005)
        assert len(requests) == len(detections) == len(annotated) == 2
        assert detections[0].header == annotated[0].header == first.header
        assert detections[1].header == annotated[1].header == third.header
        assert statuses[-1]['source_header']['stamp']['nanosec'] == third.header.stamp.nanosec
        assert statuses[-1]['orientation_valid'] is False
        assert statuses[-1]['pending_frames'] == statuses[-1]['in_flight'] == 0
        assert statuses[-1]['state'] == 'READY'
        # Silence must expire READY without any additional inference response.
        node.freshness.camera_received = time.monotonic()-0.6
        node.tick()
        assert statuses[-1]['state'] == 'CAMERA_STALE'
        assert not statuses[-1]['observation_valid']
    finally:
        release.set()
        node.close()
        node.destroy_node()
        rclpy.shutdown()
