import math
import time

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def clamp(v, limit):
    return max(-limit, min(limit, v))


def quat_yaw(q):
    return math.atan2(
        2.0 * (q.w * q.z + q.x * q.y),
        1.0 - 2.0 * (q.y * q.y + q.z * q.z),
    )


class HeadingTest(Node):

    def __init__(self):
        super().__init__('heading_test')

        self.pub = self.create_publisher(
            Twist,
            '/neptune/cmd_body',
            10,
        )

        self.create_subscription(
            Odometry,
            '/state/odometry',
            self.odom_cb,
            10,
        )

        self.x = None
        self.y = None
        self.yaw = None
        self.wz = 0.0

        self.target_x = None
        self.target_y = None

        self.started = time.monotonic()
        self.last_print = 0.0
        self.done = False

        self.create_timer(0.05, self.control)

    def odom_cb(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y
        self.yaw = quat_yaw(msg.pose.pose.orientation)
        self.wz = msg.twist.twist.angular.z

        if self.target_x is None:
            self.target_x = self.x - 5.0
            self.target_y = self.y

            self.get_logger().info(
                f'START x={self.x:.2f}, y={self.y:.2f}, '
                f'yaw={math.degrees(self.yaw):.1f} deg'
            )

            self.get_logger().info(
                f'TARGET x={self.target_x:.2f}, '
                f'y={self.target_y:.2f}'
            )

    def stop(self):
        self.pub.publish(Twist())

    def control(self):
        if self.x is None or self.target_x is None:
            return

        dx = self.target_x - self.x
        dy = self.target_y - self.y
        distance = math.hypot(dx, dy)

        # World direction toward target.
        world_bearing = math.atan2(dy, dx)

        # Girona convention:
        # positive body surge at yaw=0 travels world -X.
        desired_yaw = wrap(world_bearing - math.pi)

        yaw_error = wrap(desired_yaw - self.yaw)

        yaw_cmd = clamp(
            1.4 * yaw_error - 0.20 * self.wz,
            0.25,
        )

        # Turn first if badly misaligned.
        if abs(yaw_error) > math.radians(30):
            surge = 0.0
        else:
            surge = min(0.35, 0.12 * distance)

            if distance > 0.30:
                surge = max(0.12, surge)

        cmd = Twist()
        cmd.linear.x = surge
        cmd.angular.z = yaw_cmd

        self.pub.publish(cmd)

        now = time.monotonic()

        if now - self.last_print >= 1.0:
            self.last_print = now

            print(
                f'x={self.x:6.2f}  '
                f'y={self.y:+6.2f}  '
                f'dist={distance:5.2f}  '
                f'yaw={math.degrees(self.yaw):+6.1f}°  '
                f'target_yaw={math.degrees(desired_yaw):+6.1f}°  '
                f'err={math.degrees(yaw_error):+5.1f}°  '
                f'surge={surge:.2f}  '
                f'yaw_cmd={yaw_cmd:+.2f}',
                flush=True,
            )

        if distance < 0.25:
            self.stop()
            self.get_logger().info('5 m TARGET REACHED — ZERO THRUST')
            self.done = True

        if now - self.started > 40.0:
            self.stop()
            self.get_logger().error('TEST TIMEOUT — ZERO THRUST')
            self.done = True


def main():
    rclpy.init()
    node = HeadingTest()

    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        node.stop()
        time.sleep(0.25)
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
