"""Publish demo readiness from pressure, IMU, DVL and canonical onboard state."""

import json
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from nav_msgs.msg import Odometry
from sensor_msgs.msg import FluidPressure, Imu
from std_msgs.msg import Bool, String
from stonefish_ros2.msg import DVL

from .readiness import DemoReadiness


def source_time(message):
    """Return the original sensor/source timestamp."""
    return message.header.stamp.sec + message.header.stamp.nanosec / 1e9


def valid_quaternion(q):
    """Require a finite near-unit attitude."""
    values = (q.x, q.y, q.z, q.w)
    return all(math.isfinite(v) for v in values) and abs(sum(v*v for v in values) - 1) < 0.02


class ReadinessNode(Node):
    """Own readiness diagnostics only; never publish movement commands."""

    def __init__(self, **options):
        super().__init__('demo_readiness', **options)
        self.gate = DemoReadiness(
            self.declare_parameter('minimum_startup_s', 15.0).value,
            self.declare_parameter('stable_window_s', 3.0).value,
        )
        self.start = time.monotonic()
        self.startup_deadline = self.declare_parameter('startup_timeout_s', 90.0).value
        qos = QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.ready_pub = self.create_publisher(Bool, '/neptune/demo/ready', qos)
        self.health_pub = self.create_publisher(String, '/neptune/demo/health', qos)
        self.create_subscription(FluidPressure, '/sim/pressure', self.pressure, 10)
        self.create_subscription(Imu, '/sim/imu', self.imu, 10)
        self.create_subscription(DVL, '/sim/dvl', self.dvl, 10)
        self.create_subscription(Odometry, '/state/odometry', self.state, 10)
        self.create_timer(0.1, self.tick)
        self.previous_reason = None

    def pressure(self, message):
        self.gate.pressure(time.monotonic(), source_time(message), message.fluid_pressure)

    def imu(self, message):
        self.gate.imu(time.monotonic(), source_time(message), message.angular_velocity.z,
                      valid_quaternion(message.orientation))

    def dvl(self, message):
        valid = all(math.isfinite(v) for v in (
            message.velocity.x, message.velocity.y, message.velocity.z,
        ))
        self.gate.observe('dvl', time.monotonic(), source_time(message), valid)

    def state(self, message):
        p = message.pose.pose.position
        valid = (all(math.isfinite(v) for v in (p.x, p.y, p.z))
                 and valid_quaternion(message.pose.pose.orientation))
        self.gate.observe('state', time.monotonic(), source_time(message), valid)

    def tick(self):
        now = time.monotonic()
        status = self.gate.snapshot(now, self.get_clock().now().nanoseconds / 1e9)
        owners = {
            '/neptune/cmd_body': 'mission_executive',
            '/sim/thruster_setpoints': 'stonefish_vehicle_adapter',
            '/state/odometry': 'dead_reckoning_state',
        }
        ownership = {}
        for topic, owner in owners.items():
            publishers = self.get_publishers_info_by_topic(topic)
            if len(publishers) > 1:
                raise RuntimeError(f'Competing publishers on {topic}; Demo V0 shutting down')
            ownership[topic] = len(publishers) == 1 and publishers[0].node_name == owner
        status['publisher_ownership'] = ownership
        if not all(ownership.values()):
            status['ready'] = False
            status['reason'] = 'Waiting for exclusive mission / adapter / onboard-state ownership'
        self.ready_pub.publish(Bool(data=status['ready']))
        self.health_pub.publish(String(data=json.dumps(status)))
        if status['reason'] != self.previous_reason:
            self.get_logger().info(status['reason'])
            self.previous_reason = status['reason']
        if not status['startup_qualified'] and now - self.start > self.startup_deadline:
            raise RuntimeError('Demo startup health/settling deadline exceeded; mission not started')


def main(args=None):
    """Run the readiness node in its own executor/process."""
    rclpy.init(args=args)
    node = ReadinessNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
