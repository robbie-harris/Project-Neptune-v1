"""Test callback pairing without constructing a ROS node or DDS transport."""

from types import SimpleNamespace

from nav_msgs.msg import Odometry

from neptune_evaluation.localization_evaluator import LocalizationEvaluator
from neptune_evaluation.localization_metrics import LocalizationMetrics


def receiver():
    return SimpleNamespace(
        metrics=LocalizationMetrics(), pending={}, last_stamp={},
        rejected=0, max_pair_skew=0.1)


def message(seconds, x=0.0):
    msg = Odometry()
    msg.header.stamp.sec = int(seconds)
    msg.header.stamp.nanosec = round((seconds - int(seconds)) * 1e9)
    msg.pose.pose.position.x = float(x)
    msg.pose.pose.orientation.w = 1.0
    return msg


def test_wait_pair_and_no_reuse():
    node = receiver()
    LocalizationEvaluator.receive(node, 'estimate', message(1, 0))
    assert node.metrics.sample_count == 0
    LocalizationEvaluator.receive(node, 'truth', message(1.05, 100))
    assert node.metrics.sample_count == 1
    LocalizationEvaluator.receive(node, 'estimate', message(2, 3))
    assert node.metrics.sample_count == 1
    LocalizationEvaluator.receive(node, 'truth', message(2, 102))
    assert node.metrics.summary()['final_horizontal_error'] == 1
    LocalizationEvaluator.receive(node, 'truth', message(2, 102))
    assert node.metrics.sample_count == 2
    assert node.rejected == 1


def test_skew_and_invalid_position():
    node = receiver()
    LocalizationEvaluator.receive(node, 'estimate', message(1))
    LocalizationEvaluator.receive(node, 'truth', message(2))
    assert node.metrics.sample_count == 0
    assert node.rejected == 1
    LocalizationEvaluator.receive(node, 'estimate', message(2, float('nan')))
    assert node.metrics.sample_count == 0
    LocalizationEvaluator.receive(node, 'estimate', message(2))
    assert node.metrics.sample_count == 1


def test_invalid_orientation_preserves_position_metrics():
    node = receiver()
    msg = message(1)
    msg.pose.pose.orientation.w = 0.0
    LocalizationEvaluator.receive(node, 'estimate', msg)
    LocalizationEvaluator.receive(node, 'truth', message(1))
    assert node.metrics.sample_count == 1
    assert node.metrics.yaw_sample_count == 0


def test_final_summary_without_samples(capsys):
    node = receiver()
    LocalizationEvaluator.print_diagnostics(node, final=True)
    assert 'Final localization summary: samples=0' in capsys.readouterr().out
