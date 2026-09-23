import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry


class GroundTruthState(Node):

    def __init__(self):
        super().__init__('ground_truth_state')

        self.state_pub = self.create_publisher(
            Odometry,
            '/state/odometry',
            10,
        )

        self.sim_sub = self.create_subscription(
            Odometry,
            '/sim/odometry',
            self.odometry_callback,
            10,
        )

        self.get_logger().info(
            'Stage 0 state adapter ready: '
            '/sim/odometry -> /state/odometry'
        )

    def odometry_callback(self, msg: Odometry):
        self.state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)

    node = GroundTruthState()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
