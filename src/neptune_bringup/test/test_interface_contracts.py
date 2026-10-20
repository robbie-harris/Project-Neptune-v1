"""Public typed ROS boundaries without a simulator or running executors."""

import pytest
import rclpy
from rclpy.parameter import Parameter

from neptune_autonomy.mission_executive import MissionExecutive
from neptune_state_estimation.dead_reckoning_state import DeadReckoningState
from neptune_vehicle.stonefish_adapter import StonefishVehicleAdapter


@pytest.fixture
def nodes():
    rclpy.init(args=[])
    created = []
    try:
        created.extend([
            MissionExecutive(parameter_overrides=[Parameter('demo_mode', value=True)]),
            DeadReckoningState(),
            StonefishVehicleAdapter(),
        ])
        yield created
    finally:
        for node in reversed(created):
            node.destroy_node()
        rclpy.shutdown()


def endpoints(objects):
    return {item.topic_name: item.msg_type for item in objects}


def test_canonical_estimate_and_truth_isolation(nodes):
    from nav_msgs.msg import Odometry
    mission, estimator, _ = nodes
    assert endpoints(mission.subscriptions)['/state/odometry'] is Odometry
    assert endpoints(estimator.publishers)['/state/odometry'] is Odometry
    for node in nodes:
        assert '/sim/odometry' not in endpoints(node.subscriptions)


def test_exclusive_command_and_actuator_boundaries(nodes):
    from geometry_msgs.msg import Twist
    from std_msgs.msg import Float64MultiArray
    mission, estimator, vehicle = nodes
    assert endpoints(mission.publishers)['/neptune/cmd_body'] is Twist
    assert endpoints(vehicle.subscriptions)['/neptune/cmd_body'] is Twist
    assert endpoints(vehicle.publishers)['/sim/thruster_setpoints'] is Float64MultiArray
    assert '/neptune/cmd_body' not in endpoints(estimator.publishers)
    assert '/neptune/cmd_body' not in endpoints(vehicle.publishers)
    assert '/sim/thruster_setpoints' not in endpoints(mission.publishers)
    assert '/sim/thruster_setpoints' not in endpoints(estimator.publishers)


def test_estimator_sensor_contracts(nodes):
    from sensor_msgs.msg import Imu
    from std_msgs.msg import Float64
    from stonefish_ros2.msg import DVL
    _, estimator, _ = nodes
    inputs = endpoints(estimator.subscriptions)
    assert inputs == {
        '/estimate/depth': Float64,
        '/sim/imu': Imu,
        '/sim/dvl': DVL,
    }
