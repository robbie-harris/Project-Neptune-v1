import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Float64


def clamp(value, limit):
    return max(-limit, min(limit, value))


class DepthHold(Node):

    def __init__(self):
        super().__init__('depth_hold')

        self.target_depth = None
        self.current_depth = None
        self.previous_depth = None
        self.previous_time = None

        self.vertical_velocity = 0.0
        self.integral = 0.0

        # Depth controller tuning.
        #
        # world_ned:
        #   +Z = deeper
        #
        # Neptune vehicle convention:
        #   +linear.z = dive
        #
        # Girona is positively buoyant, so a constant downward
        # command is required to hold depth.
        self.heave_trim = 0.34

        self.kp = 0.28
        self.ki = 0.04
        self.kd = 0.22

        self.max_heave = 0.60
        self.integral_limit = 2.0

        self.depth_tolerance = 0.05
        self.velocity_tolerance = 0.04

        self.cmd_pub = self.create_publisher(
            Twist,
            '/neptune/cmd_body',
            10,
        )

        self.create_subscription(
            Odometry,
            '/state/odometry',
            self.odom_callback,
            10,
        )

        self.create_subscription(
            Float64,
            '/control/target_depth',
            self.target_callback,
            10,
        )

        self.create_timer(
            0.05,
            self.control_loop,
        )

        self.get_logger().info(
            'Depth controller ready: '
            '/control/target_depth -> /neptune/cmd_body'
        )

    def target_callback(self, msg):
        self.target_depth = msg.data

        # Don't carry integral error between missions/targets.
        self.integral = 0.0

        self.get_logger().info(
            f'Target depth set to {self.target_depth:.2f} m'
        )

    def odom_callback(self, msg):
        now = self.get_clock().now()
        depth = msg.pose.pose.position.z

        if (
            self.previous_depth is not None
            and self.previous_time is not None
        ):
            dt = (
                now - self.previous_time
            ).nanoseconds / 1e9

            if dt > 0.001:
                raw_velocity = (
                    depth - self.previous_depth
                ) / dt

                # Low-pass derivative estimate.
                self.vertical_velocity = (
                    0.85 * self.vertical_velocity
                    + 0.15 * raw_velocity
                )

        self.previous_depth = depth
        self.previous_time = now
        self.current_depth = depth

    def control_loop(self):
        if (
            self.target_depth is None
            or self.current_depth is None
        ):
            return

        error = (
            self.target_depth
            - self.current_depth
        )

        # Only build integral near the target.
        # This prevents huge wind-up during the initial dive.
        if abs(error) < 0.8:
            self.integral += error * 0.05
            self.integral = clamp(
                self.integral,
                self.integral_limit,
            )

        # Feed-forward buoyancy compensation + PID correction.
        heave = (
            self.heave_trim
            + self.kp * error
            + self.ki * self.integral
            - self.kd * self.vertical_velocity
        )

        heave = clamp(
            heave,
            self.max_heave,
        )

        cmd = Twist()
        cmd.linear.z = heave

        self.cmd_pub.publish(cmd)

    def stop(self):
        if rclpy.ok():
            try:
                self.cmd_pub.publish(Twist())
            except Exception:
                pass


def main(args=None):
    rclpy.init(args=args)

    node = DepthHold()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.stop()

        try:
            node.destroy_node()
        except Exception:
            pass

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
