"""Observation-only perception to a dedicated, sway-only control output."""

import json
import signal
import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.clock import Clock
from rclpy.clock_type import ClockType
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import String

from .pipe_centering import PipeCentering


OUTPUT_TOPIC = '/neptune/control/alignment_cmd_body'


def sway_message(sway):
    """All unowned axes retain their zero defaults."""
    message = Twist()
    message.linear.y = float(sway)
    return message


class PipeCenteringNode(Node):
    """20 Hz steady timer continues stopping even during ROS-clock stalls."""

    def __init__(self):
        super().__init__('pipe_centering')
        defaults = {'kp': 0.5, 'max_sway': 0.25, 'deadband': 0.05, 'freshness_s': 0.5,
                    'confirmation_count': 3, 'sway_sign': 0.0}
        values = {key: self.declare_parameter(key, value).value
                  for key, value in defaults.items()}
        self.controller = PipeCentering(**values)
        rate = self.declare_parameter('control_rate_hz', 20.0).value
        if not 1 <= rate <= 100:
            raise ValueError('control_rate_hz must be in [1, 100]')
        self.output = self.create_publisher(Twist, OUTPUT_TOPIC, 1)
        self.status = self.create_publisher(String, '/neptune/control/alignment_status', 1)
        self.input = self.create_subscription(
            String, '/neptune/perception/fused_status', self.receive, 1)
        self.steady_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.timer = self.create_timer(1/rate, self.tick, clock=self.steady_clock)

    def ros_now(self):
        """Source stamps use the same ROS clock as perception."""
        return self.get_clock().now().nanoseconds/1e9

    def receive(self, message):
        """Malformed JSON immediately clears eligibility."""
        try:
            self.controller.receive(json.loads(message.data), time.monotonic(), self.ros_now())
        except (ValueError, TypeError):
            self.controller.reject('INVALID_TARGET')

    def tick(self):
        """Publish bounded command and reviewable state on every control tick."""
        sway = self.controller.command(time.monotonic(), self.ros_now())
        self.output.publish(sway_message(sway))
        self.status.publish(String(data=json.dumps({
            'state': self.controller.state, 'sway_command': sway,
            'confirmation_count': self.controller.count,
            'source_stamp': self.controller.key, 'target': self.controller.target},
            allow_nan=False)))


def main(args=None):
    """Keep ROS alive for the final shutdown stop."""
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    handlers = {sig: signal.signal(sig, signal.default_int_handler)
                for sig in (signal.SIGINT, signal.SIGTERM)}
    node = PipeCenteringNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.output.publish(sway_message(0))
        node.destroy_node()
        rclpy.shutdown()
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
