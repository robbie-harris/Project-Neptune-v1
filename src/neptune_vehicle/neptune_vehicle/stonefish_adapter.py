import signal

import rclpy
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions

from geometry_msgs.msg import Twist
from std_msgs.msg import Float64MultiArray
from rcl_interfaces.msg import ParameterDescriptor


def clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


class StonefishVehicleAdapter(Node):

    def __init__(self):
        super().__init__('stonefish_vehicle_adapter')

        # Startup-only mode: pair with the matching five/seven-motor scenario.
        self.declare_parameter(
            'motor_count', 5, ParameterDescriptor(read_only=True),
        )
        self.motor_count = self.get_parameter('motor_count').value
        if self.motor_count not in (5, 7):
            raise ValueError('motor_count must be 5 (legacy) or 7 (perception)')

        self.thruster_pub = self.create_publisher(
            Float64MultiArray,
            '/sim/thruster_setpoints',
            10,
        )

        self.cmd_sub = self.create_subscription(
            Twist,
            '/neptune/cmd_body',
            self.command_callback,
            10,
        )

        self.last_command_time = None
        self.watchdog_timeout = 0.5

        self.create_timer(0.1, self.watchdog_callback)

        self.get_logger().info(
            'Stonefish adapter ready: /neptune/cmd_body -> '
            '/sim/thruster_setpoints'
        )

    def publish_thrusters(
        self,
        surge: float,
        heave: float,
        sway: float,
        yaw: float = 0.0,
    ):
        msg = Float64MultiArray()

        # Girona 500 actuator order:
        # 0 SurgePort
        # 1 SurgeStarboard
        # 2 HeaveBow
        # 3 HeaveStern
        # 4 Sway
        # 5 SwayFront (perception mode only)
        # 6 SwayRear (perception mode only)
        # Native surge motors invert setpoints: negate surge for body +X bow
        # propulsion, retaining the existing differential public yaw convention.
        msg.data = [
            clamp(-surge - yaw),
            clamp(-surge + yaw),
            clamp(-heave),
            clamp(-heave),
            clamp(sway),
        ]
        if self.motor_count == 7:
            # Matched +Y force axes and opposing propeller reaction torques.
            # Mounts have equal fore/aft CG moment arms. Motor 4 is preserved.
            msg.data.extend([clamp(sway), clamp(sway)])

        self.thruster_pub.publish(msg)

    def command_callback(self, msg: Twist):
        self.last_command_time = self.get_clock().now()

        self.publish_thrusters(
            surge=msg.linear.x,
            heave=msg.linear.z,
            sway=msg.linear.y,
            yaw=msg.angular.z,
        )

    def watchdog_callback(self):
        if self.last_command_time is None:
            return

        elapsed = (
            self.get_clock().now() - self.last_command_time
        ).nanoseconds / 1e9

        if elapsed > self.watchdog_timeout:
            self.publish_thrusters(0.0, 0.0, 0.0, 0.0)
            self.last_command_time = None


def main(args=None):
    # Keep the ROS context alive until the final zero array is published.
    # rclpy's default signal handler shuts it down before the finally block.
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    old_handlers = {
        sig: signal.signal(sig, signal.default_int_handler)
        for sig in (signal.SIGINT, signal.SIGTERM)
    }

    node = StonefishVehicleAdapter()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.publish_thrusters(0.0, 0.0, 0.0)
        node.destroy_node()
        rclpy.shutdown()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    main()
