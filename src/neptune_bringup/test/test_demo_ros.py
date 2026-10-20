"""Real ROS adapters: read-only GUI, fresh-state gating and preserved mission control."""

import json
import time

import numpy as np
import pytest
import rclpy
from rclpy.parameter import Parameter
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from std_srvs.srv import Trigger

from neptune_autonomy.mission_executive import MissionExecutive
from neptune_bringup.demo_gui import DemoGui, image_bgr


@pytest.fixture(autouse=True)
def context():
    rclpy.init()
    yield
    rclpy.shutdown()


def odometry():
    message = Odometry()
    message.pose.pose.orientation.w = 1.0
    message.pose.pose.position.z = 0.45
    return message


def test_demo_does_not_define_home_or_move_before_ready_and_armed():
    node = MissionExecutive(parameter_overrides=[
        Parameter('demo_mode', value=True), Parameter('auto_start', value=False),
    ])
    commands = []
    node.publish_command = lambda **kw: commands.append(kw)
    try:
        node.odom_callback(odometry())
        node.control_loop()
        assert node.state == 'INITIALIZING' and node.home_x is None
        assert commands == [{}]
        assert not node.start_demo(Trigger.Request(), Trigger.Response()).success
        node.readiness_callback(Bool(data=True))
        assert node.state == 'INITIALIZING'
        assert node.start_demo(Trigger.Request(), Trigger.Response()).success
        assert node.state == 'WAIT_FOR_STATE'
        node.odom_callback(odometry())
        assert node.state == 'DIVE' and node.home_z == 0.45
        node.control_loop()
        assert commands[-1]['heave'] > 0
        node.readiness_callback(Bool(data=False))
        node.control_loop()
        assert commands[-1] == {} and node.state == 'DIVE'
    finally:
        node.destroy_node()


def test_baseline_start_depth_and_route_with_faster_surge():
    node = MissionExecutive()
    try:
        assert node.state == 'WAIT_FOR_STATE'
        node.odom_callback(odometry())
        assert node.state == 'DIVE'
        assert node.heave_trim == 0.34 and node.max_surge == 0.80
        assert node.inspection_standoff == 1.5 and node.travel_distance == 20.0
    finally:
        node.destroy_node()


def test_demo_invalid_state_and_expired_readiness_do_not_command_motion():
    node = MissionExecutive(parameter_overrides=[Parameter('demo_mode', value=True)])
    commands = []
    node.publish_command = lambda **kw: commands.append(kw)
    try:
        message = odometry()
        message.pose.pose.position.z = float('nan')
        node.odom_callback(message)
        assert node.state_received is None
        node.odom_callback(odometry())
        node.readiness_callback(Bool(data=True))
        node.odom_callback(odometry())
        assert node.state == 'DIVE'
        node.readiness_received = time.monotonic() - 1
        node.control_loop()
        assert commands[-1] == {}
    finally:
        node.destroy_node()


def test_gui_has_no_application_publishers_and_keeps_only_latest_image():
    node = DemoGui()
    try:
        publishers = [name for name, _ in node.get_publisher_names_and_types_by_node(
            node.get_name(), node.get_namespace())]
        assert set(publishers) <= {'/rosout', '/parameter_events'}
        first, second = Image(), Image()
        node.camera(first)
        node.camera(second)
        assert node.snapshot()['image'] is second
        assert node.snapshot()['sequence'] == 2
        node.mission_status(type('Message', (), {'data': json.dumps({
            'state': 'TRANSIT', 'mission_elapsed_s': 42.0,
        })})())
        assert node.snapshot()['mission']['state'] == 'TRANSIT'
    finally:
        node.destroy_node()


def test_rgb_image_padding_is_honored_without_color_swap():
    message = Image(width=2, height=1, step=8, encoding='rgb8',
                    data=[255, 0, 0, 0, 255, 0, 99, 99])
    assert np.array_equal(image_bgr(message), [[[0, 0, 255], [0, 255, 0]]])
    message.encoding = 'unsupported'
    with pytest.raises(ValueError):
        image_bgr(message)


@pytest.mark.parametrize('context_alive', [True, False])
def test_pressure_depth_shutdown_handles_both_ros_signal_paths(monkeypatch, context_alive):
    from neptune_state_estimation import pressure_depth

    class FakeNode:
        destroyed = False

        def destroy_node(self):
            self.destroyed = True

    node, shutdowns = FakeNode(), []

    def interrupt(_node):
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(pressure_depth, 'PressureDepth', lambda: node)
        patch.setattr(pressure_depth.rclpy, 'init', lambda **_kw: None)
        patch.setattr(pressure_depth.rclpy, 'spin', interrupt)
        patch.setattr(pressure_depth.rclpy, 'ok', lambda: context_alive)
        patch.setattr(pressure_depth.rclpy, 'shutdown', lambda: shutdowns.append(True))
        pressure_depth.main()
    assert node.destroyed
    assert len(shutdowns) == int(context_alive)
