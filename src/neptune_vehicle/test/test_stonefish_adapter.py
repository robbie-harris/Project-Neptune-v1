"""Regression checks for legacy and perception allocation and stop paths."""
from types import SimpleNamespace

import pytest
import rclpy
from geometry_msgs.msg import Twist
from rclpy.parameter import Parameter

from neptune_vehicle import stonefish_adapter as adapter


def test_default_is_legacy():
    rclpy.init(args=[])
    node = adapter.StonefishVehicleAdapter()
    try:
        assert node.motor_count == 5
    finally:
        node.destroy_node()
        rclpy.shutdown()


@pytest.fixture(params=[5, 7])
def vehicle(request, monkeypatch):
    rclpy.init(args=['--ros-args', '-p', f'motor_count:={request.param}'])
    node = adapter.StonefishVehicleAdapter()
    sent = []
    monkeypatch.setattr(node.thruster_pub, 'publish', lambda msg: sent.append(msg.data))
    try:
        yield node, sent
    finally:
        node.destroy_node()
        rclpy.shutdown()


@pytest.mark.parametrize('body,expected', [
    ((0.4, 0.2, 0.3, 0.1), [0.3, 0.5, -0.3, -0.3, 0.2]),
    ((0.0, -0.4, 0.0, 0.0), [0.0, 0.0, 0.0, 0.0, -0.4]),
    ((0.8, 2.0, -2.0, 0.5), [0.3, 1.0, 1.0, 1.0, 1.0]),
    ((-0.8, -2.0, 2.0, -0.5), [-0.3, -1.0, -1.0, -1.0, -1.0]),
])
def test_body_mapping(vehicle, body, expected):
    node, sent = vehicle
    msg = Twist()
    msg.linear.x, msg.linear.y, msg.linear.z, msg.angular.z = body
    node.command_callback(msg)
    assert list(sent[-1][:5]) == pytest.approx(expected)
    assert len(sent[-1]) == node.motor_count
    if node.motor_count == 7:
        assert list(sent[-1][5:]) == [expected[4], expected[4]]


def test_exact_historical_output(vehicle):
    node, sent = vehicle
    for surge in (-2.0, -0.3, 0.0, 0.8, 2.0):
        for yaw in (-0.7, 0.0, 0.4):
            node.publish_thrusters(surge, 0.34, -0.25, yaw)
            old = [adapter.clamp(surge-yaw), adapter.clamp(surge+yaw),
                   adapter.clamp(-0.34), adapter.clamp(-0.34), adapter.clamp(-0.25)]
            assert list(sent[-1][:5]) == old


def test_watchdog_stops_every_motor(vehicle, monkeypatch):
    node, sent = vehicle
    now = [0]
    class Time:
        def __init__(self, ns):
            self.nanoseconds = ns

        def __sub__(self, other):
            return Time(self.nanoseconds-other.nanoseconds)

    monkeypatch.setattr(node, 'get_clock', lambda: SimpleNamespace(now=lambda: Time(now[0])))
    msg = Twist()
    msg.linear.y = 0.4
    node.command_callback(msg)
    now[0] = 500_000_000
    node.watchdog_callback()
    assert len(sent) == 1  # Preserve historical >0.5 second timeout boundary.
    now[0] += 1
    node.watchdog_callback()
    assert list(sent[-1]) == [0.0]*node.motor_count
    assert node.last_command_time is None
    node.watchdog_callback()
    assert len(sent) == 2


def test_main_shutdown_stops_every_motor(vehicle, monkeypatch):
    node, sent = vehicle
    def interrupt(unused):
        raise KeyboardInterrupt
    with monkeypatch.context() as patch:
        patch.setattr(adapter.rclpy, 'init', lambda **kw: None)
        patch.setattr(adapter.rclpy, 'shutdown', lambda: None)
        patch.setattr(adapter, 'StonefishVehicleAdapter', lambda: node)
        patch.setattr(node, 'destroy_node', lambda: None)
        patch.setattr(adapter.rclpy, 'spin', interrupt)
        adapter.main()
    assert list(sent[-1]) == [0.0]*node.motor_count


def test_mode_is_read_only(vehicle):
    node, _ = vehicle
    result = node.set_parameters([Parameter('motor_count', value=7 if node.motor_count == 5 else 5)])
    assert not result[0].successful
