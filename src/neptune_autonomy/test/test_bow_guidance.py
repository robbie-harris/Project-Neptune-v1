"""Bow-facing waypoint heading and existing turn-before-surge behavior."""

import math
from types import SimpleNamespace

import pytest

from neptune_autonomy.mission_executive import MissionExecutive, wrap_angle


@pytest.mark.parametrize('bearing', [0.0, math.pi/2, math.pi, -math.pi/2])
def test_cardinal_waypoint_points_bow_at_target(bearing):
    state = SimpleNamespace(
        x=2.0, y=-3.0, yaw=bearing, wz=0.0,
        kp_yaw=1.4, kd_yaw=0.2, max_yaw=0.60,
        max_surge=0.80, min_surge=0.20,
    )
    target = (state.x + 10*math.cos(bearing), state.y + 10*math.sin(bearing))
    surge, yaw, distance, error, desired = MissionExecutive.guidance_command(state, *target)
    assert wrap_angle(desired-bearing) == pytest.approx(0)
    assert error == pytest.approx(0)
    assert yaw == pytest.approx(0)
    assert distance == pytest.approx(10)
    assert surge > 0
    assert math.cos(desired)*math.cos(bearing) + math.sin(desired)*math.sin(bearing) > 0.999


def test_negative_x_waypoint_requires_turn_before_surge():
    state = SimpleNamespace(
        x=0.0, y=0.0, yaw=0.0, wz=0.0,
        kp_yaw=1.4, kd_yaw=0.2, max_yaw=0.60,
        max_surge=0.80, min_surge=0.20,
    )
    surge, yaw, _, error, desired = MissionExecutive.guidance_command(state, -10.0, 0.0)
    assert abs(desired) == pytest.approx(math.pi)
    assert abs(error) == pytest.approx(math.pi)
    assert surge == 0.0
    assert yaw == pytest.approx(0.60)
