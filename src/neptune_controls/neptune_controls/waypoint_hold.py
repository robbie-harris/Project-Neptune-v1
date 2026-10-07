import rclpy
from rclpy.node import Node

from geometry_msgs.msg import PointStamped, Twist
from nav_msgs.msg import Odometry


def clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


class WaypointHold(Node):

    def __init__(self):
        super().__init__('waypoint_hold')

        self.declare_parameter('kp_x', 0.5)
        self.declare_parameter('max_surge', 0.6)
        self.declare_parameter('max_heave', 0.8)
        self.declare_parameter('x_tolerance', 0.10)
        self.declare_parameter('z_tolerance', 0.05)

        self.kp_x = float(self.get_parameter('kp_x').value)
        self.max_surge = float(self.get_parameter('max_surge').value)
        self.max_heave = float(self.get_parameter('max_heave').value)
        self.x_tolerance = float(self.get_parameter('x_tolerance').value)
        self.z_tolerance = float(self.get_parameter('z_tolerance').value)

        self.current_x = None
        self.current_z = None
        self.target_x = None
        self.target_z = None

        self.cmd_pub = self.create_publisher(
            Twist,
            '/neptune/cmd_body',
            10,
        )

        self.state_sub = self.create_subscription(
            Odometry,
            '/state/odometry',
            self.state_callback,
            10,
        )

        self.target_sub = self.create_subscription(
            PointStamped,
            '/control/target_position',
            self.target_callback,
            10,
        )

        self.create_timer(0.05, self.control_loop)

        self.get_logger().info(
            'Waypoint hold ready: /control/target_position -> /neptune/cmd_body'
        )

    def state_callback(self, msg: Odometry):
        self.current_x = msg.pose.pose.position.x
        self.current_z = msg.pose.pose.position.z

    def target_callback(self, msg: PointStamped):
        self.target_x = msg.point.x
        self.target_z = msg.point.z

        self.get_logger().info(
            f'New waypoint: x={self.target_x:.2f}, z={self.target_z:.2f}'
        )

    def control_loop(self):
        if (
            self.current_x is None
            or self.current_z is None
            or self.target_x is None
            or self.target_z is None
        ):
            return

        ex = self.target_x - self.current_x
        ez = self.target_z - self.current_z

        # Girona calibration:
        # positive surge command produced decreasing world-NED X.
        if abs(ex) < self.x_tolerance:
            surge = 0.0
        else:
            surge = clamp(-self.kp_x * ex, self.max_surge)

        # world_ned: +Z is downward.
        if abs(ez) < self.z_tolerance:
            heave = 0.0
        elif ez > 0.0:
            heave = self.max_heave
        else:
            heave = -self.max_heave

        cmd = Twist()
        cmd.linear.x = surge
        cmd.linear.z = heave

        self.cmd_pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = WaypointHold()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cmd_pub.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
