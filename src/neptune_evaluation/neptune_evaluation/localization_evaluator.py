"""Read-only runtime comparison of onboard odometry and simulator truth."""

import math

from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from neptune_evaluation.dvl_benchmark import write_result
from neptune_evaluation.localization_metrics import LocalizationMetrics, quaternion_yaw


class LocalizationEvaluator(Node):
    """Compare fresh timestamp-compatible pairs without exporting truth."""

    def __init__(self):
        super().__init__('localization_evaluator')
        self.declare_parameter('result_path', '')
        self.result_path = self.get_parameter('result_path').value
        self.declare_parameter('diagnostic_period', 5.0)
        self.declare_parameter('max_pair_skew', 0.1)
        period = float(self.get_parameter('diagnostic_period').value)
        self.max_pair_skew = float(self.get_parameter('max_pair_skew').value)
        if not math.isfinite(period) or period <= 0:
            raise ValueError('diagnostic_period must be finite and positive')
        if not math.isfinite(self.max_pair_skew) or self.max_pair_skew < 0:
            raise ValueError('max_pair_skew must be finite and nonnegative')
        self.metrics = LocalizationMetrics()
        self.pending = {}
        self.last_stamp = {}
        self.rejected = 0
        self.subscriptions_ = [
            self.create_subscription(
                Odometry, topic,
                lambda msg, stream=stream: self.receive(stream, msg),
                qos_profile_sensor_data)
            for stream, topic in (
                ('estimate', '/state/odometry'), ('truth', '/sim/odometry'))
        ]
        self.timer = self.create_timer(period, self.print_diagnostics)
        self.get_logger().info(
            'Evaluation only: waiting for /state/odometry and /sim/odometry; '
            f'max pair skew={self.max_pair_skew:.3f}s')

    def receive(self, stream, msg):
        """Reject invalid/repeated samples and pair each message at most once."""
        position = msg.pose.pose.position
        values = (position.x, position.y, position.z)
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if (not all(math.isfinite(value) for value in values)
                or stamp <= self.last_stamp.get(stream, -math.inf)):
            self.rejected += 1
            return
        orientation = msg.pose.pose.orientation
        try:
            yaw = quaternion_yaw(
                orientation.x, orientation.y, orientation.z, orientation.w)
        except ValueError:
            yaw = None  # Position metrics remain useful without valid orientation.
        self.last_stamp[stream] = stamp
        self.pending[stream] = (stamp, values, yaw)
        if len(self.pending) != 2:
            return
        estimate, truth = self.pending['estimate'], self.pending['truth']
        if abs(estimate[0] - truth[0]) > self.max_pair_skew:
            del self.pending['estimate' if estimate[0] < truth[0] else 'truth']
            self.rejected += 1
            return
        yaws = (estimate[2], truth[2])
        if None in yaws:
            yaws = (None, None)
        self.metrics.add_sample(estimate[1], truth[1], *yaws)
        self.pending.clear()

    def print_diagnostics(self, final=False):
        """Print all metrics with explicit position and yaw units."""
        label = 'Final localization summary' if final else 'Localization'
        metrics = self.metrics.summary()
        if not metrics['sample_count']:
            message = f'{label}: samples=0; waiting for valid paired odometry'
        else:
            fields = ', '.join(
                f'{key}={value:.4f}' if isinstance(value, float)
                else f'{key}={value}' for key, value in metrics.items())
            message = f'{label} (position=m, yaw=rad): {fields}'
        message += f'; rejected={self.rejected}'
        if final:
            # stdout remains available after ROS signal handling shuts its context down.
            print(message, flush=True)
        else:
            self.get_logger().info(message)


def main(args=None):
    """Run the evaluator and print its final summary on clean shutdown."""
    rclpy.init(args=args)
    node = None
    try:
        node = LocalizationEvaluator()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.print_diagnostics(final=True)
            if node.result_path:
                write_result(node.result_path, node.metrics.summary(), node.rejected)
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
