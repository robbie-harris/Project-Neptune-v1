"""ROS output provenance and steady-clock validity expiry."""
import json
import time
from types import SimpleNamespace

import pytest
import rclpy
from std_msgs.msg import String

from neptune_perception.fusion_node import PipeFusion, arrays
from neptune_perception.fusion import fuse
from test_fusion import status, box


def test_ros_array_source_geometry_confidence_and_provenance():
    s = status(observations=[box(), box(label='valve'), box(label='flange')])
    pipes, semantics = arrays(fuse(s, status('orientation_a', [box(confidence=0.2)])))
    assert len(pipes.detections) == len(semantics.detections) == 2
    assert pipes.header.stamp.sec == 100 and pipes.header.frame_id == 'camera'
    assert all(d.header == pipes.header for d in pipes.detections+semantics.detections)
    assert [d.results[0].hypothesis.score for d in pipes.detections] == [0.8, 0.2]
    assert pipes.detections[0].id != pipes.detections[1].id
    assert [d.results[0].hypothesis.class_id for d in semantics.detections] == ['valve', 'flange']
    assert all(d.bbox.center.theta == 0 for d in pipes.detections)


@pytest.fixture
def node():
    rclpy.init()
    n = PipeFusion()
    messages = []
    n.status = SimpleNamespace(publish=lambda m: messages.append(json.loads(m.data)))
    try:
        yield n, messages
    finally:
        n.close()
        n.destroy_node()
        rclpy.shutdown()


def test_startup_model_unavailable(node):
    n, messages = node
    n.tick()
    assert messages[-1]['state'] == 'MODEL_UNAVAILABLE' and not messages[-1]['valid']


def test_consensus_node_and_watchdog_stale(node):
    n, messages = node
    stamp = n.get_clock().now().to_msg()
    def current(model):
        s = status(model, sec=stamp.sec, ns=stamp.nanosec)
        n.receive(model, String(data=json.dumps(s)))
    current('inspection')
    current('orientation_a')
    assert messages[-1]['state'] == 'CONSENSUS' and messages[-1]['valid']
    assert not messages[-1]['orientation_valid']
    n.last_received -= 0.6
    n.tick()
    assert messages[-1]['state'] == 'STALE' and not messages[-1]['valid']
    assert not messages[-1]['selected_target']['valid']


def test_model_unavailable_after_loss(node):
    n, messages = node
    stamp = n.get_clock().now().to_msg()
    n.receive('inspection', String(data=json.dumps(status(sec=stamp.sec, ns=stamp.nanosec))))
    n.tick()
    n.cache.flush(time.monotonic()+0.21, n.get_clock().now().nanoseconds/1e9)
    output = fuse(status(sec=stamp.sec, ns=stamp.nanosec), None)
    output.update(observation_age_s=0, receipt_age_s=0)
    n.publish_observation(output, time.monotonic()-0.6)
    n.cache.model_states = dict(inspection='MODEL_UNAVAILABLE', orientation_a='MODEL_UNAVAILABLE')
    n.tick()
    assert messages[-1]['state'] == 'MODEL_UNAVAILABLE' and not messages[-1]['valid']


def test_malformed_status_rejected(node):
    n, messages = node
    n.receive('inspection', String(data='{}'))
    n.tick()
    assert messages[-1]['schema_errors'] == 1 and not messages[-1]['valid']
