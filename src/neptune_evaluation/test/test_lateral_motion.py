"""Evaluate lateral truth displacement without exposing it as controller state."""
from nav_msgs.msg import Odometry
from neptune_evaluation.lateral_motion import LateralMotionEvaluation
import pytest


class FakeNode:
    def create_subscription(self, message_type, topic, callback, depth):
        assert message_type is Odometry and topic == '/sim/odometry'


def test_missing_truth():
    e = LateralMotionEvaluation(FakeNode())
    assert e.begin() is None
    assert e.summary() == {'available': False}


def test_initial_body_axis():
    e = LateralMotionEvaluation(FakeNode())
    a = Odometry()
    a.pose.pose.orientation.z = 1.0
    a.pose.pose.orientation.w = 0.0
    e.receive(a)
    assert e.begin() is None
    b = Odometry()
    b.pose.pose.position.x = 0.1
    b.pose.pose.position.y = -0.2
    b.pose.pose.position.z = -0.3
    e.receive(b)
    assert e.summary()['body_lateral_displacement_m'] == pytest.approx(0.2)


def test_armed_start_excludes_previous_process():
    e = LateralMotionEvaluation(FakeNode())
    old = Odometry()
    old.pose.pose.position.z = 1.0
    e.receive(old)
    e.arm()
    new = Odometry()
    new.pose.pose.position.z = 3.0
    e.receive(new)
    end = Odometry()
    end.pose.pose.position.z = 2.9
    e.receive(end)
    assert e.summary()['world_displacement_m'][2] == pytest.approx(-0.1)
    assert len(e.receipts) == 3


def test_continuous_truth_history_is_a_snapshot():
    e = LateralMotionEvaluation(FakeNode())
    sample = Odometry()
    sample.pose.pose.position.z = 3.0
    sample.twist.twist.angular.z = 0.02
    e.receive(sample)
    sample.pose.pose.position.z = 2.0
    assert e.history[0]['depth'] == 3.0
    assert e.history[0]['angular_velocity'][2] == 0.02
    assert e.history[0]['receipt'] == e.receipts[0]
