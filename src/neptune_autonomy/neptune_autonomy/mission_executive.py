import math
import json
import signal
import time
import rclpy

from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool, String
from std_srvs.srv import Trigger
from rclpy.qos import QoSProfile, DurabilityPolicy
from rclpy.signals import SignalHandlerOptions


def clamp(value, limit):
    return max(-limit, min(limit, value))


def wrap_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def quaternion_yaw(q):
    return math.atan2(
        2.0 * (q.w * q.z + q.x * q.y),
        1.0 - 2.0 * (q.y * q.y + q.z * q.z),
    )


class MissionExecutive(Node):

    def __init__(self, **node_options):
        super().__init__('mission_executive', **node_options)

        # Demo readiness is opt-in; ordinary Stage 1 startup is unchanged.
        self.demo_mode = self.declare_parameter('demo_mode', False).value
        self.start_requested = self.declare_parameter('auto_start', True).value
        self.state_timeout = self.declare_parameter('state_timeout_s', 0.5).value
        self.demo_ready = False
        self.readiness_received = None
        self.state_received = None
        self.mission_timed_out = False
        status_qos = QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.status_pub = self.create_publisher(String, '/neptune/mission/status', status_qos)
        if self.demo_mode:
            self.create_subscription(
                Bool, '/neptune/demo/ready', self.readiness_callback, status_qos,
            )
            self.create_service(Trigger, '/neptune/mission/start', self.start_demo)

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

        # --------------------------------------------------
        # Mission
        # --------------------------------------------------

        self.state = 'INITIALIZING' if self.demo_mode else 'WAIT_FOR_STATE'

        self.home_x = None
        self.home_y = None
        self.home_z = None

        self.pipe_x = None
        self.pipe_y = None

        self.target_depth = 3.0
        self.travel_distance = 20.0

        # Do NOT navigate to the physical center of the pipe.
        # Approach from +X and stop this far in front of it.
        self.inspection_standoff = 1.5

        self.state_start = None
        self.mission_start = None
        self.mission_end = None

        # --------------------------------------------------
        # Vehicle state
        # --------------------------------------------------

        self.x = None
        self.y = None
        self.z = None
        self.yaw = None

        self.vx = 0.0
        self.vz = 0.0
        self.wz = 0.0

        self.prev_z = None
        self.prev_time = None

        # --------------------------------------------------
        # Depth controller
        # Proven standalone values
        # --------------------------------------------------

        self.heave_trim = 0.34

        self.kp_z = 0.28
        self.ki_z = 0.04
        self.kd_z = 0.22

        self.max_heave = 0.60

        self.depth_integral = 0.0

        # --------------------------------------------------
        # Horizontal guidance
        # Proven by 20 m straight-line test
        # --------------------------------------------------

        self.kp_yaw = 1.40
        self.kd_yaw = 0.20
        self.max_yaw = 0.25

        self.max_surge = 0.55
        self.min_surge = 0.15

        self.last_status = None

        self.create_timer(
            0.05,
            self.control_loop,
        )

        self.get_logger().info(
            'Mission executive ready.'
        )
        self.create_timer(0.2, self.publish_status)
        self.publish_status()

    def readiness_current(self):
        return (self.demo_ready and self.readiness_received is not None
                and time.monotonic() - self.readiness_received < self.state_timeout)

    def state_current(self):
        return (self.state_received is not None
                and time.monotonic() - self.state_received < self.state_timeout)

    def readiness_callback(self, message):
        self.demo_ready = message.data
        self.readiness_received = time.monotonic()
        if self.state == 'INITIALIZING' and self.start_requested and self.readiness_current():
            self.transition('WAIT_FOR_STATE')

    def start_demo(self, _request, response):
        if self.state != 'INITIALIZING':
            response.success = False
            response.message = 'Mission has already started; restart the launch for a new mission.'
        elif not self.readiness_current() or not self.state_current():
            response.success = False
            response.message = 'Required sensors/state have not passed demo initialization.'
        else:
            self.start_requested = True
            self.transition('WAIT_FOR_STATE')
            response.success = True
            response.message = 'Mission armed; waiting for the next canonical state update.'
        return response

    def publish_status(self):
        finish = self.mission_end if self.mission_end is not None else self.get_clock().now()
        elapsed = (0.0 if self.mission_start is None else
                   (finish - self.mission_start).nanoseconds / 1e9)
        self.status_pub.publish(String(data=json.dumps({
            'state': self.state,
            'mission_elapsed_s': elapsed,
            'complete': self.state == 'COMPLETE' and not self.mission_timed_out,
            'outcome': 'TIMEOUT' if self.mission_timed_out else (
                'COMPLETE' if self.state == 'COMPLETE' else 'RUNNING'),
            'demo_mode': self.demo_mode,
            'ready': self.readiness_current() if self.demo_mode else self.state_current(),
            'start_requested': self.start_requested,
            'state_fresh': self.state_current(),
            'movement_authority': 'mission_executive',
        })))

    # ======================================================
    # STATE ESTIMATION INPUT
    # ======================================================

    def odom_callback(self, msg):

        if self.demo_mode:
            p, q = msg.pose.pose.position, msg.pose.pose.orientation
            values = [p.x, p.y, p.z, q.x, q.y, q.z, q.w,
                      msg.twist.twist.linear.x, msg.twist.twist.angular.z]
            if (not all(math.isfinite(value) for value in values)
                    or abs(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w - 1.0) > 0.02):
                return
        self.state_received = time.monotonic()

        now = self.get_clock().now()

        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y
        self.z = msg.pose.pose.position.z

        self.yaw = quaternion_yaw(
            msg.pose.pose.orientation
        )

        self.vx = msg.twist.twist.linear.x
        self.wz = msg.twist.twist.angular.z

        if (
            self.prev_z is not None
            and self.prev_time is not None
        ):
            dt = (
                now - self.prev_time
            ).nanoseconds / 1e9

            if dt > 0.001:
                raw_vz = (
                    self.z - self.prev_z
                ) / dt

                self.vz = (
                    0.85 * self.vz
                    + 0.15 * raw_vz
                )

        self.prev_z = self.z
        self.prev_time = now

        # First odometry message defines HOME.
        if self.state == 'WAIT_FOR_STATE' and (
                not self.demo_mode or (self.readiness_current() and self.start_requested)):

            self.home_x = self.x
            self.home_y = self.y
            self.home_z = self.z

            self.pipe_x = (
                self.home_x
                - self.travel_distance
            )

            self.pipe_y = self.home_y

            self.inspect_x = (
                self.pipe_x
                + self.inspection_standoff
            )

            self.inspect_y = self.pipe_y

            self.mission_start = now

            self.get_logger().info(
                f'HOME: '
                f'x={self.home_x:.2f}, '
                f'y={self.home_y:.2f}, '
                f'z={self.home_z:.2f}'
            )

            self.get_logger().info(
                f'PIPE CENTER: '
                f'x={self.pipe_x:.2f}, '
                f'y={self.pipe_y:.2f}'
            )

            self.get_logger().info(
                f'INSPECTION WAYPOINT: '
                f'x={self.inspect_x:.2f}, '
                f'y={self.inspect_y:.2f}, '
                f'z={self.target_depth:.2f}'
            )

            self.transition('DIVE')

    # ======================================================
    # STATE MACHINE
    # ======================================================

    def transition(self, new_state):

        self.state = new_state
        self.state_start = self.get_clock().now()
        if new_state == 'COMPLETE':
            self.mission_end = self.state_start

        self.depth_integral = 0.0

        self.get_logger().info(
            f'========== {new_state} =========='
        )
        self.publish_status()

    def state_elapsed(self):

        if self.state_start is None:
            return 0.0

        return (
            self.get_clock().now()
            - self.state_start
        ).nanoseconds / 1e9

    # ======================================================
    # DEPTH CONTROL
    # ======================================================

    def depth_command(self, target_depth):

        error = target_depth - self.z

        if abs(error) < 0.8:

            self.depth_integral += (
                error * 0.05
            )

            self.depth_integral = clamp(
                self.depth_integral,
                2.0,
            )

        heave = (
            self.heave_trim
            + self.kp_z * error
            + self.ki_z * self.depth_integral
            - self.kd_z * self.vz
        )

        return clamp(
            heave,
            self.max_heave,
        )

    # ======================================================
    # XY + HEADING GUIDANCE
    # ======================================================

    def guidance_command(
        self,
        target_x,
        target_y,
    ):

        dx = target_x - self.x
        dy = target_y - self.y

        distance = math.hypot(
            dx,
            dy,
        )

        world_bearing = math.atan2(
            dy,
            dx,
        )

        # Girona convention:
        #
        # yaw = 0 and positive surge
        # moves toward world -X.
        desired_yaw = wrap_angle(
            world_bearing
            - math.pi
        )

        yaw_error = wrap_angle(
            desired_yaw
            - self.yaw
        )

        yaw_cmd = (
            self.kp_yaw * yaw_error
            - self.kd_yaw * self.wz
        )

        yaw_cmd = clamp(
            yaw_cmd,
            self.max_yaw,
        )

        # If badly misaligned:
        # rotate first, don't surge.
        if abs(yaw_error) > math.radians(30):

            surge = 0.0

        else:

            surge = min(
                self.max_surge,
                0.10 * distance,
            )

            if distance > 0.45:

                surge = max(
                    self.min_surge,
                    surge,
                )

            else:

                surge = 0.0

        return (
            surge,
            yaw_cmd,
            distance,
            yaw_error,
            desired_yaw,
        )

    # ======================================================
    # COMMAND OUTPUT
    # ======================================================

    def publish_command(
        self,
        surge=0.0,
        heave=0.0,
        yaw=0.0,
    ):

        cmd = Twist()

        cmd.linear.x = float(surge)
        cmd.linear.z = float(heave)

        cmd.angular.z = float(yaw)

        self.cmd_pub.publish(cmd)

    # ======================================================
    # STATUS
    # ======================================================

    def print_status(
        self,
        distance=None,
        yaw_error=None,
    ):

        now = self.get_clock().now()

        if self.last_status is not None:

            elapsed = (
                now - self.last_status
            ).nanoseconds / 1e9

            if elapsed < 1.0:
                return

        self.last_status = now

        extra = ''

        if distance is not None:

            extra += (
                f' | dist={distance:.2f}'
            )

        if yaw_error is not None:

            extra += (
                f' | yaw_err='
                f'{math.degrees(yaw_error):+.1f}deg'
            )

        self.get_logger().info(
            f'{self.state:8s}'
            f' | x={self.x:7.2f}'
            f' | y={self.y:+6.2f}'
            f' | z={self.z:5.2f}'
            f' | yaw={math.degrees(self.yaw):+6.1f}'
            f'{extra}'
        )

    # ======================================================
    # CONTROL LOOP
    # ======================================================

    def control_loop(self):

        if self.demo_mode and (
                self.state in ('INITIALIZING', 'WAIT_FOR_STATE')
                or not self.readiness_current() or not self.state_current()):
            self.publish_command()
            return

        if (
            self.x is None
            or self.y is None
            or self.z is None
            or self.yaw is None
        ):
            return

        # Hard mission timeout.
        if (
            self.mission_start is not None
            and self.state != 'COMPLETE'
        ):

            elapsed = (
                self.get_clock().now()
                - self.mission_start
            ).nanoseconds / 1e9

            if elapsed > 420.0:

                self.mission_timed_out = True

                self.get_logger().error(
                    'MISSION TIMEOUT'
                )

                self.transition(
                    'COMPLETE'
                )

        # ==================================================
        # 1. DIVE
        # ==================================================

        if self.state == 'DIVE':

            heave = self.depth_command(
                self.target_depth
            )

            self.publish_command(
                surge=0.0,
                heave=heave,
                yaw=0.0,
            )

            self.print_status()

            if (
                abs(
                    self.z
                    - self.target_depth
                ) < 0.12
                and abs(self.vz) < 0.12
                and self.state_elapsed() > 3.0
            ):

                self.transition(
                    'TRANSIT'
                )

        # ==================================================
        # 2. TRANSIT TO PIPE
        # ==================================================

        elif self.state == 'TRANSIT':

            (
                surge,
                yaw_cmd,
                distance,
                yaw_error,
                _,
            ) = self.guidance_command(
                self.inspect_x,
                self.inspect_y,
            )

            heave = self.depth_command(
                self.target_depth
            )

            self.publish_command(
                surge=surge,
                heave=heave,
                yaw=yaw_cmd,
            )

            self.print_status(
                distance,
                yaw_error,
            )

            if distance < 0.50:

                self.transition(
                    'INSPECT'
                )

        # ==================================================
        # 3. INSPECT / POSITION HOLD
        # ==================================================

        elif self.state == 'INSPECT':

            (
                surge,
                yaw_cmd,
                distance,
                yaw_error,
                _,
            ) = self.guidance_command(
                self.inspect_x,
                self.inspect_y,
            )

            heave = self.depth_command(
                self.target_depth
            )

            self.publish_command(
                surge=surge,
                heave=heave,
                yaw=yaw_cmd,
            )

            self.print_status(
                distance,
                yaw_error,
            )

            if self.state_elapsed() >= 5.0:

                self.transition(
                    'RETURN'
                )

        # ==================================================
        # 4. RETURN TO HOME XY
        # ==================================================

        elif self.state == 'RETURN':

            (
                surge,
                yaw_cmd,
                distance,
                yaw_error,
                _,
            ) = self.guidance_command(
                self.home_x,
                self.home_y,
            )

            heave = self.depth_command(
                self.target_depth
            )

            self.publish_command(
                surge=surge,
                heave=heave,
                yaw=yaw_cmd,
            )

            self.print_status(
                distance,
                yaw_error,
            )

            if distance < 0.50:

                self.transition(
                    'ASCEND'
                )

        # ==================================================
        # 5. ASCEND
        # ==================================================

        elif self.state == 'ASCEND':

            # Positive buoyancy brings Girona up.
            self.publish_command(
                surge=0.0,
                heave=0.0,
                yaw=0.0,
            )

            self.print_status()

            if (
                self.z
                <= self.home_z + 0.12
            ):

                self.transition(
                    'COMPLETE'
                )

        # ==================================================
        # 6. COMPLETE
        # ==================================================

        elif self.state == 'COMPLETE':

            self.publish_command(
                surge=0.0,
                heave=0.0,
                yaw=0.0,
            )

            self.print_status()

    def stop(self):

        if rclpy.ok():

            try:

                self.publish_command(
                    surge=0.0,
                    heave=0.0,
                    yaw=0.0,
                )

            except Exception:
                pass


def main(args=None):

    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    old_handlers = {
        sig: signal.signal(sig, signal.default_int_handler)
        for sig in (signal.SIGINT, signal.SIGTERM)
    }

    node = MissionExecutive()

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
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    main()
