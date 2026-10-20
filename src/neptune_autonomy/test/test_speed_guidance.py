"""Motion scheduling, allocation authority and unchanged mission boundaries."""

import math
from types import SimpleNamespace

import pytest
import rclpy

from neptune_autonomy.mission_executive import MissionExecutive
from neptune_vehicle.stonefish_adapter import StonefishVehicleAdapter


@pytest.fixture
def executive():
    rclpy.init(args=[])
    node = MissionExecutive()
    node.x = node.y = node.yaw = node.wz = 0.0
    node.z = 3.0
    yield node
    node.destroy_node()
    rclpy.shutdown()


@pytest.mark.parametrize('distance,expected', [
    (10.0, 0.80), (5.0, 0.80), (3.0, 0.48), (1.5, 0.24),
    (1.0, 0.20), (0.50, 0.20), (0.450001, 0.20), (0.45, 0.0), (0.0, 0.0),
])
def test_distance_schedule(executive, distance, expected):
    assert executive.guidance_command(distance, 0.0)[0] == pytest.approx(expected)


def test_gains_and_yaw_saturation(executive):
    assert (executive.kp_yaw, executive.kd_yaw) == (1.40, 0.20)
    assert executive.max_yaw == 0.60
    for sign in (-1, 1):
        executive.yaw = -sign * math.pi/2
        assert executive.guidance_command(10.0, 0.0)[1] == pytest.approx(sign*0.60)
    executive.yaw, executive.wz = -0.1, 0.2
    assert executive.guidance_command(10.0, 0.0)[1] == pytest.approx(0.10)


def test_turn_gate(executive):
    executive.yaw = math.radians(30.001)
    assert executive.guidance_command(10.0, 0.0)[0] == 0.0
    executive.yaw = math.radians(30.0)
    assert executive.guidance_command(10.0, 0.0)[0] > 0.0


@pytest.mark.parametrize('motor_count', [5, 7])
def test_authority_before_actual_adapter_mixing(executive, motor_count, monkeypatch):
    from neptune_vehicle import stonefish_adapter
    # Fail if the adapter needs to clip either scheduled surge motor.
    def checked_clamp(value):
        assert abs(value) <= 1.0 + 1e-12
        return value
    monkeypatch.setattr(stonefish_adapter, 'clamp', checked_clamp)
    sent = []
    vehicle = SimpleNamespace(motor_count=motor_count,
                              thruster_pub=SimpleNamespace(publish=sent.append))
    for degrees in range(-180, 181):
        executive.yaw = math.radians(degrees)
        for distance in (0.0, 0.45, 0.46, 1.0, 3.0, 20.0):
            surge, turn, *_ = executive.guidance_command(distance, 0.0)
            assert surge + abs(turn) <= 1.0 + 1e-12
            StonefishVehicleAdapter.publish_thrusters(vehicle, surge, 0.34, 0.0, turn)
            port, starboard = sent[-1].data[:2]
            assert (port+starboard)/2 == pytest.approx(-surge)
            assert (starboard-port)/2 == pytest.approx(turn)
    executive.yaw = math.radians(25)
    assert executive.guidance_command(20.0, 0.0)[0] == pytest.approx(0.40)


def test_mission_boundaries_and_dwell(executive):
    assert executive.travel_distance == 20.0
    assert executive.inspection_standoff == 1.5
    assert executive.target_depth == 3.0
    assert (executive.heave_trim, executive.kp_z, executive.ki_z,
            executive.kd_z, executive.max_heave) == (0.34, 0.28, 0.04, 0.22, 0.60)
    executive.publish_command = lambda **kw: None
    executive.print_status = lambda *args: None
    executive.home_x = executive.home_y = 0.0
    executive.home_z = 0.45
    executive.inspect_x, executive.inspect_y = -18.5, 0.0
    executive.state_elapsed = lambda: 4.99
    executive.vz = 0.0
    executive.state = 'DIVE'
    executive.control_loop()
    assert executive.state == 'TRANSIT'
    executive.x = -18.0
    executive.control_loop()
    assert executive.state == 'TRANSIT'  # exactly 0.50 is not arrival
    executive.x = -18.001
    executive.control_loop()
    assert executive.state == 'INSPECT'
    executive.control_loop()
    assert executive.state == 'INSPECT'
    executive.state_elapsed = lambda: 5.0
    executive.control_loop()
    assert executive.state == 'RETURN'
    executive.x = -0.50
    executive.control_loop()
    assert executive.state == 'RETURN'
    executive.x = -0.499
    executive.control_loop()
    assert executive.state == 'ASCEND'
    executive.z = 0.57
    executive.control_loop()
    assert executive.state == 'COMPLETE'
