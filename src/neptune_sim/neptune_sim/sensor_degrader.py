"""ROS transport for the ground-truth-free sensor degradation layer."""

import rclpy
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.clock import Clock, ClockType
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import FluidPressure, Imu
from stonefish_ros2.msg import DVL

from neptune_sim.degradation import PARAMETER_DEFAULTS, SensorDegradation


class SensorDegrader(Node):
    """Subscribe to raw sensors and publish copied, optionally degraded samples."""

    def __init__(self):
        super().__init__('sensor_degrader')
        parameters = {}
        for name, default in PARAMETER_DEFAULTS.items():
            parameters[name] = self.declare_parameter(
                name, default, ParameterDescriptor(read_only=True)).value
        self.degradation = SensorDegradation(**parameters)
        self.counts = {s: dict(received=0, published=0, dropped=0)
                       for s in ('dvl', 'imu', 'pressure')}
        self.publishers_ = {}
        self.subscriptions_ = []
        for sensor, message_type in (('dvl', DVL), ('imu', Imu),
                                     ('pressure', FluidPressure)):
            # Reliable outputs match existing estimator subscriptions (depth 10).
            self.publishers_[sensor] = self.create_publisher(
                message_type, f'/degraded/{sensor}', 10)
            self.subscriptions_.append(self.create_subscription(
                message_type, f'/sim/{sensor}',
                lambda msg, s=sensor: self.receive(s, msg), qos_profile_sensor_data))
        self.timer = self.create_timer(
            5.0, self.print_diagnostics, clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.get_logger().info(
            f'Sensor degrader ready: /sim -> /degraded; seed={parameters["seed"]}; '
            'parameters are fixed at startup')

    def receive(self, sensor, message):
        """Count each received sample; dropped samples never reach the publisher."""
        counts = self.counts[sensor]
        counts['received'] += 1
        output = getattr(self.degradation, sensor)(message)
        if output is None:
            counts['dropped'] += 1
        else:
            self.publishers_[sensor].publish(output)
            counts['published'] += 1

    def print_diagnostics(self):
        """Log cumulative counters every five seconds of wall time."""
        self.get_logger().info('Sensor degradation: ' + '; '.join(
            f'{sensor} received={c["received"]} published={c["published"]} '
            f'dropped={c["dropped"]}' for sensor, c in self.counts.items()))


def main(args=None):
    """Run the sensor transport node."""
    rclpy.init(args=args)
    node = None
    try:
        node = SensorDegrader()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
