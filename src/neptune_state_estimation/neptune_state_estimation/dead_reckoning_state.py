# ROS 2 Python library.
import rclpy

# Base class for ROS 2 nodes.
from rclpy.node import Node

# Neptune publishes its canonical state as Odometry.
from nav_msgs.msg import Odometry

# IMU provides orientation and angular velocity.
from sensor_msgs.msg import Imu

# Pressure-derived depth is a Float64.
from std_msgs.msg import Float64

# Stonefish custom DVL message.
from stonefish_ros2.msg import DVL


class DeadReckoningState(Node):
    """
    Ground-truth-free state provider for Project Neptune.

    State sources:

        x, y position       -> integrated DVL velocity
        z / depth           -> pressure sensor
        orientation         -> IMU
        angular velocity    -> IMU
        linear velocity     -> DVL

    IMPORTANT:

    This node does NOT subscribe to /sim/odometry.

    Simulator odometry may still be used externally to evaluate
    estimation error, but it is no longer part of the estimator.
    """

    def __init__(self):
        super().__init__('dead_reckoning_state')

        # ---------------------------------------------------------
        # Latest sensor measurements
        # ---------------------------------------------------------

        self.latest_depth = None
        self.latest_imu = None

        # ---------------------------------------------------------
        # Estimated horizontal position
        # ---------------------------------------------------------

        # Dead reckoning needs an initial position.
        #
        # Neptune defines the point where this estimator starts as
        # local HOME = (0, 0).
        #
        # This is okay because our missions are relative to HOME.
        self.x = 0.0
        self.y = 0.0

        # Timestamp of the previous DVL measurement.
        #
        # We need this to calculate:
        #
        #     dt = current_time - previous_time
        #
        # for velocity integration.
        self.previous_dvl_time = None
        self.previous_world_vx = None
        self.previous_world_vy = None

        # ---------------------------------------------------------
        # DVL mounting geometry
        # ---------------------------------------------------------

        # DVL location relative to vehicle origin.
        self.dvl_x = -0.75
        self.dvl_y = 0.0
        self.dvl_z = 0.40

        # cos(45 degrees) = sin(45 degrees)
        self.sqrt_half = 0.70710678118

        # ---------------------------------------------------------
        # Canonical Neptune state publisher
        # ---------------------------------------------------------

        self.state_pub = self.create_publisher(
            Odometry,
            '/state/odometry',
            10,
        )

        # ---------------------------------------------------------
        # Sensor subscribers
        # ---------------------------------------------------------

        self.depth_sub = self.create_subscription(
            Float64,
            '/estimate/depth',
            self.depth_callback,
            10,
        )

        self.imu_sub = self.create_subscription(
            Imu,
            '/sim/imu',
            self.imu_callback,
            10,
        )

        self.dvl_sub = self.create_subscription(
            DVL,
            '/sim/dvl',
            self.dvl_callback,
            10,
        )

        self.get_logger().info(
            'Dead-reckoning state ready: '
            'DVL x/y + pressure z + IMU orientation/rates '
            '-> /state/odometry'
        )

    def depth_callback(self, msg: Float64):
        """
        Save the newest pressure-derived vehicle depth.
        """

        self.latest_depth = msg.data

    def imu_callback(self, msg: Imu):
        """
        Save the newest IMU measurement.
        """

        self.latest_imu = msg

    def stamp_to_seconds(self, stamp):
        """
        Convert a ROS timestamp into seconds.

        ROS gives us:

            seconds
            nanoseconds

        We combine them into one floating-point time value.
        """

        return (
            float(stamp.sec)
            + float(stamp.nanosec) * 1e-9
        )

    def dvl_to_vehicle_velocity(self, msg: DVL):
        """
        Convert raw DVL velocity into velocity of the vehicle origin,
        expressed in the vehicle/body frame.

        Step 1:
            rotate DVL sensor frame -> vehicle frame

        Step 2:
            remove lever-arm velocity caused by sensor offset
    .   """

        # Raw velocity measured in DVL coordinates.
        dvl_vx = msg.velocity.x
        dvl_vy = msg.velocity.y
        dvl_vz = msg.velocity.z

        # ---------------------------------------------------------
        # DVL frame -> vehicle frame
        # ---------------------------------------------------------

        sensor_vx = self.sqrt_half * (
            dvl_vx - dvl_vy
        )

        sensor_vy = -self.sqrt_half * (
            dvl_vx + dvl_vy
        )

        sensor_vz = -dvl_vz

        # ---------------------------------------------------------
        # Lever-arm correction
        # ---------------------------------------------------------

        wx = self.latest_imu.angular_velocity.x
        wy = self.latest_imu.angular_velocity.y
        wz = self.latest_imu.angular_velocity.z

        rx = self.dvl_x
        ry = self.dvl_y
        rz = self.dvl_z

        # omega x r
        rotational_vx = (
            wy * rz
            - wz * ry
        )

        rotational_vy = (
            wz * rx
            - wx * rz
        )

        rotational_vz = (
            wx * ry
            - wy * rx
        )

        # Velocity at vehicle origin.
        vehicle_vx = sensor_vx - rotational_vx
        vehicle_vy = sensor_vy - rotational_vy
        vehicle_vz = sensor_vz - rotational_vz

        return vehicle_vx, vehicle_vy, vehicle_vz

    def vehicle_to_world_velocity(
        self,
        vehicle_vx,
        vehicle_vy,
        vehicle_vz,
    ):
        """
        Rotate vehicle-frame velocity into the world frame
        using the IMU quaternion.

        The IMU orientation represents vehicle orientation
        relative to the world frame.

        We use the full quaternion rotation instead of yaw only,
        so roll and pitch are also handled correctly.
        """

        q = self.latest_imu.orientation

        qx = q.x
        qy = q.y
        qz = q.z
        qw = q.w

        # Quaternion -> 3x3 rotation matrix.
        #
        # This matrix rotates vectors:
        #
        #     vehicle frame -> world frame
        r00 = 1.0 - 2.0 * (qy * qy + qz * qz)
        r01 = 2.0 * (qx * qy - qz * qw)
        r02 = 2.0 * (qx * qz + qy * qw)

        r10 = 2.0 * (qx * qy + qz * qw)
        r11 = 1.0 - 2.0 * (qx * qx + qz * qz)
        r12 = 2.0 * (qy * qz - qx * qw)

        r20 = 2.0 * (qx * qz - qy * qw)
        r21 = 2.0 * (qy * qz + qx * qw)
        r22 = 1.0 - 2.0 * (qx * qx + qy * qy)

        world_vx = (
            r00 * vehicle_vx
            + r01 * vehicle_vy
            + r02 * vehicle_vz
        )

        world_vy = (
            r10 * vehicle_vx
            + r11 * vehicle_vy
            + r12 * vehicle_vz
        )

        world_vz = (
            r20 * vehicle_vx
            + r21 * vehicle_vy
            + r22 * vehicle_vz
        )

        return world_vx, world_vy, world_vz

    def dvl_callback(self, msg: DVL):
        """
        Main estimator update.

        Every new DVL measurement:

        1. converts DVL velocity into vehicle velocity,
        2. rotates velocity into the world frame,
        3. integrates world velocity to update x/y,
        4. publishes Neptune's complete canonical state.
        """

        # We need IMU orientation/rates and pressure depth before
        # we can build the complete state.
        if self.latest_imu is None:
            return

        if self.latest_depth is None:
            return

        # Current DVL timestamp.
        current_time = self.stamp_to_seconds(
            msg.header.stamp
        )

        # Convert DVL measurement into vehicle-origin velocity.
        vehicle_vx, vehicle_vy, vehicle_vz = (
            self.dvl_to_vehicle_velocity(msg)
        )

        # Rotate body velocity into world coordinates.
        world_vx, world_vy, world_vz = (
            self.vehicle_to_world_velocity(
                vehicle_vx,
                vehicle_vy,
                vehicle_vz,
            )
        )

                # ---------------------------------------------------------
        # Dead-reckon horizontal position
        # ---------------------------------------------------------

        if self.previous_dvl_time is not None:

            dt = current_time - self.previous_dvl_time

            # Normal DVL timing is approximately 0.05 s at 20 Hz.
            #
            # A moderate timing gap should NOT cause us to throw away
            # all vehicle motion that occurred during that interval.
            if 0.0 < dt < 2.0:

                # Log abnormal timing so we can determine whether
                # dropped / delayed DVL messages caused localization
                # error during long runs.
                if dt > 0.15:
                    self.get_logger().warning(
                        f'Large DVL timing gap: dt={dt:.3f} s'
                    )

                # Trapezoidal integration:
                #
                # average velocity =
                #     (previous velocity + current velocity) / 2
                #
                # This is more accurate than assuming the current
                # velocity existed during the entire interval.
                if (
                    self.previous_world_vx is not None
                    and self.previous_world_vy is not None
                ):
                    average_vx = 0.5 * (
                        self.previous_world_vx + world_vx
                    )

                    average_vy = 0.5 * (
                        self.previous_world_vy + world_vy
                    )

                else:
                    average_vx = world_vx
                    average_vy = world_vy

                # Integrate world-frame velocity.
                self.x += average_vx * dt
                self.y += average_vy * dt

            elif dt >= 2.0:
                # A multi-second gap is large enough that blindly
                # integrating across it is unsafe.
                self.get_logger().warning(
                    f'Skipping invalid DVL timing gap: dt={dt:.3f} s'
                )

        # Save information needed for the next DVL update.
        self.previous_dvl_time = current_time
        self.previous_world_vx = world_vx
        self.previous_world_vy = world_vy

        # ---------------------------------------------------------
        # Build canonical Neptune state
        # ---------------------------------------------------------

        state = Odometry()

        state.header.stamp = msg.header.stamp
        state.header.frame_id = 'world_ned'
        state.child_frame_id = 'base_link'

        # Dead-reckoned horizontal position.
        state.pose.pose.position.x = self.x
        state.pose.pose.position.y = self.y

        # Pressure-derived vertical position.
        state.pose.pose.position.z = self.latest_depth

        # IMU orientation.
        state.pose.pose.orientation = (
            self.latest_imu.orientation
        )

        # IMPORTANT:
        #
        # nav_msgs/Odometry twist is expressed in the child/body frame.
        #
        # Therefore we publish DVL-derived VEHICLE velocity here,
        # not world velocity.
        state.twist.twist.linear.x = vehicle_vx
        state.twist.twist.linear.y = vehicle_vy
        state.twist.twist.linear.z = vehicle_vz

        # IMU angular velocity.
        state.twist.twist.angular = (
            self.latest_imu.angular_velocity
        )

        # Covariance is left at zero temporarily.
        #
        # Our future EKF will provide meaningful uncertainty.

        self.state_pub.publish(state)


def main(args=None):
    """
    ROS 2 executable entry point.
    """

    rclpy.init(args=args)

    node = DeadReckoningState()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()