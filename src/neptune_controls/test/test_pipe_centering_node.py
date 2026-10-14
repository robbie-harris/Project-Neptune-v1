"""ROS command ownership, axes and adapter safety tests."""
from neptune_controls.pipe_centering_node import OUTPUT_TOPIC, PipeCenteringNode, sway_message
import pytest
import rclpy
from std_msgs.msg import String
from test_pipe_centering import observation


@pytest.fixture
def node():
    rclpy.init()
    n = PipeCenteringNode()
    yield n
    n.destroy_node()
    rclpy.shutdown()


def test_default_output_is_dedicated(node):
    assert node.output.topic_name == OUTPUT_TOPIC
    assert node.output.topic_name != '/neptune/cmd_body'
    assert [s.topic_name for s in node.subscriptions] == ['/neptune/perception/fused_status']


@pytest.mark.parametrize('sway', [-0.25, 0, 0.25])
def test_only_sway(sway):
    m = sway_message(sway)
    assert m.linear.y == sway
    assert [m.linear.x, m.linear.z, m.angular.x, m.angular.y, m.angular.z] == [0]*5


def test_invalid_json_clears_target(node):
    now = node.ros_now()
    s = observation(sec=int(now))
    node.controller.receive(s, 0, int(now)+0.1)
    assert node.controller.target is not None
    node.receive(String(data='{'))
    assert node.controller.target is None
    assert node.controller.state == 'INVALID_TARGET'


def test_null_json_fails_closed(node):
    node.receive(String(data='null'))
    assert node.controller.target is None
    node.tick()
