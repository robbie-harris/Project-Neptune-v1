"""Regression checks for legacy and perception allocation and stop paths."""
from types import SimpleNamespace
from pathlib import Path
import math
import xml.etree.ElementTree as ET

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
    ((0.4, 0.2, 0.3, 0.1), [-0.5, -0.3, -0.3, -0.3, 0.2]),
    ((0.0, -0.4, 0.0, 0.0), [0.0, 0.0, 0.0, 0.0, -0.4]),
    ((0.8, 2.0, -2.0, 0.5), [-1.0, -0.3, 1.0, 1.0, 1.0]),
    ((-0.8, -2.0, 2.0, -0.5), [1.0, 0.3, -1.0, -1.0, -1.0]),
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


def test_bounded_allocation_and_unchanged_heave_sway(vehicle):
    node, sent = vehicle
    for surge in (-2.0, -0.3, 0.0, 0.8, 2.0):
        for yaw in (-0.7, 0.0, 0.4):
            node.publish_thrusters(surge, 0.34, -0.25, yaw)
            expected = [adapter.clamp(-surge-yaw), adapter.clamp(-surge+yaw),
                   adapter.clamp(-0.34), adapter.clamp(-0.34), adapter.clamp(-0.25)]
            assert list(sent[-1][:5]) == expected
            assert all(abs(value) <= 1.0 for value in sent[-1])


def surge_forces(setpoints):
    """Static-water FD thrust from actual mounts, inversion and handedness.

    Common positive density/diameter/rate factors are omitted; this checks
    force and yaw signs, not dynamic displacement or rotor transients.
    """
    scene = Path(__file__).resolve().parents[2] / 'neptune_sim/scenarios'
    robot = ET.parse(scene / 'neptune_girona_perception.scn').find('robot')
    forces = []
    for name, command in zip(('ThrusterSurgePort', 'ThrusterSurgeStarboard'), setpoints):
        motor = robot.find(f"actuator[@name='{name}']")
        r, p, y = map(float, motor.find('origin').get('rpy').split())
        axis = (math.cos(y)*math.cos(p), math.sin(y)*math.cos(p), -math.sin(p))
        assert axis == pytest.approx((1, 0, 0))
        assert motor.find('thrust_model').get('type') == 'fluid_dynamics'
        rotor = -command if motor.find('specs').get('inverted_setpoint') == 'true' else command
        axial = rotor * abs(rotor)
        if motor.find('propeller').get('right') != 'true':
            axial = -axial
        coefficient = motor.find('thrust_model/thrust_coeff')
        axial *= float(coefficient.get('forward' if axial >= 0 else 'reverse'))
        position = tuple(map(float, motor.find('origin').get('xyz').split()))
        forces.append((position, tuple(axial*a for a in axis)))
    return forces


def test_positive_surge_propels_geometric_bow(vehicle):
    node, sent = vehicle
    node.publish_thrusters(0.2, 0.0, 0.0, 0.0)
    assert all(force[0] > 0 for _, force in surge_forces(sent[-1][:2]))


def test_pure_yaw_preserves_historical_allocation_and_moment(vehicle):
    node, sent = vehicle
    node.publish_thrusters(0.0, 0.0, 0.0, 0.1)
    historical = [-0.1, 0.1]
    assert list(sent[-1][:2]) == historical
    forces = surge_forces(sent[-1][:2])
    assert sum(force[0] for _, force in forces) == pytest.approx(0)
    # r cross F: positive public yaw retains positive body-Z moment.
    assert sum(pos[0]*force[1] - pos[1]*force[0] for pos, force in forces) > 0


def test_unsaturated_mixed_surge_yaw_common_and_differential(vehicle):
    node, sent = vehicle
    node.publish_thrusters(0.3, 0.0, 0.0, 0.1)
    port, starboard = sent[-1][:2]
    assert (port + starboard)/2 == pytest.approx(-0.3)
    assert (starboard - port)/2 == pytest.approx(0.1)


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
