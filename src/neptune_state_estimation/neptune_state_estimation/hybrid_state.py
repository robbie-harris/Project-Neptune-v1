# ROS 2 Python library.
import rclpy

# Base class for ROS 2 nodes.
from rclpy.node import Node

# Canonical Neptune state message.
from nav_msgs.msg import Odometry

# Standard IMU message.
from sensor_msgs.msg import Imu

# Pressure-derived depth is published as Float64.
from std_msgs.msg import Float64

# Stonefish custom DVL message.
from stonefish_ros2.msg import DVL


class HybridState(Node):
    """
    Build Neptune's canonical state while progressively replacing
    simulator ground truth with onboard-style sensor measurements.

    Current state sources:

        x, y position       -> simulator ground truth
        z / depth           -> pressure sensor
        orientation         -> IMU
        angular velocity    -> IMU
        linear velocity     -> DVL

    Output:
        /state/odometry

    Only x/y position still depends on simulator ground truth.
    """

    def __init__(self):
        super().__init__('hybrid_state')

        # ---------------------------------------------------------
        # Latest sensor measurements
        # ---------------------------------------------------------

        # Latest pressure-derived vehicle depth.
        self.latest_depth = None

        # Latest IMU message.
        self.latest_imu = None

        # Latest DVL message.
        self.latest_dvl = None

        # ---------------------------------------------------------
        # DVL mounting geometry
        # ---------------------------------------------------------

        # DVL position relative to the vehicle origin, in meters.
        #
        # From the Stonefish scenario:
        #
        # xyz = (-0.75, 0.0, 0.40)
        #
        # This matters because a sensor mounted away from the vehicle
        # center experiences extra velocity when the vehicle rotates.
        self.dvl_x = -0.75
        self.dvl_y = 0.0
        self.dvl_z = 0.40

        # cos(45 deg) = sin(45 deg)
        #
        # The DVL is mounted with:
        #
        # roll = 180 deg
        # yaw  = -45 deg
        #
        # We use this value to rotate DVL-frame velocity into the
        # Girona vehicle/body frame.
        self.sqrt_half = 0.70710678118

        # ---------------------------------------------------------
        # Canonical state publisher
        # ---------------------------------------------------------

        self.state_pub = self.create_publisher(
            Odometry,
            '/state/odometry',
            10,
        )

        # ---------------------------------------------------------
        # Pressure subscriber
        # ---------------------------------------------------------

        self.depth_sub = self.create_subscription(
            Float64,
            '/estimate/depth',
            self.depth_callback,
            10,
        )

        # ---------------------------------------------------------
        # IMU subscriber
        # ---------------------------------------------------------

        self.imu_sub = self.create_subscription(
            Imu,
            '/sim/imu',
            self.imu_callback,
            10,
        )

        # ---------------------------------------------------------
        # DVL subscriber
        # ---------------------------------------------------------

        self.dvl_sub = self.create_subscription(
            DVL,
            '/sim/dvl',
            self.dvl_callback,
            10,
        )

        # ---------------------------------------------------------
        # Temporary ground-truth position subscriber
        # ---------------------------------------------------------

        # Ground truth is now used ONLY for x/y position.
        #
        # Stage 1D will remove this final dependency using
        # DVL + IMU dead reckoning.
        self.odom_sub = self.create_subscription(
            Odometry,
            '/sim/odometry',
            self.odometry_callback,
            10,
        )

        self.get_logger().info(
            'Hybrid state ready: '
            'GT x/y + pressure z + IMU orientation/rates '
            '+ DVL linear velocity -> /state/odometry'
        )

    def depth_callback(self, msg: Float64):
        """
        Save the latest pressure-derived vehicle depth.
        """
        self.latest_depth = msg.data

    def imu_callback(self, msg: Imu):
        """
        Save the latest IMU measurement.

        We currently use:
        - orientation
        - angular velocity
        """
        self.latest_imu = msg

    def dvl_callback(self, msg: DVL):
        """
        Save the latest DVL velocity measurement.
        """
        self.latest_dvl = msg

    def dvl_to_vehicle_velocity(self):
        """
        Convert the raw DVL velocity into velocity at the
        Girona vehicle origin, expressed in the vehicle frame.

        There are TWO corrections:

        1. Rotate from the DVL sensor frame into the vehicle frame.

        2. Remove velocity caused by the DVL being mounted away
           from the vehicle origin:

               v_sensor = v_origin + omega x r

           therefore:

               v_origin = v_sensor - omega x r
        """

        # Raw DVL velocity in the DVL sensor frame.
        dvl_vx = self.latest_dvl.velocity.x
        dvl_vy = self.latest_dvl.velocity.y
        dvl_vz = self.latest_dvl.velocity.z

        # ---------------------------------------------------------
        # Step 1:
        # Rotate DVL-frame velocity into vehicle/body frame.
        # ---------------------------------------------------------

        # The DVL mounting orientation is:
        #
        # roll = +180 deg
        # yaw  = -45 deg
        #
        # These equations were also validated experimentally using
        # independent surge and sway tests.
        sensor_vx = self.sqrt_half * (
            dvl_vx - dvl_vy
        )

        sensor_vy = -self.sqrt_half * (
            dvl_vx + dvl_vy
        )

        sensor_vz = -dvl_vz

        # ---------------------------------------------------------
        # Step 2:
        # Correct for DVL lever arm.
        # ---------------------------------------------------------

        # IMU angular velocity is expressed in the vehicle frame
        # because the IMU is mounted at the vehicle origin with
        # zero relative rotation.
        wx = self.latest_imu.angular_velocity.x
        wy = self.latest_imu.angular_velocity.y
        wz = self.latest_imu.angular_velocity.z

        # DVL position vector relative to vehicle origin:
        #
        # r = [rx, ry, rz]
        rx = self.dvl_x
        ry = self.dvl_y
        rz = self.dvl_z

        # Compute omega x r.
        #
        # Cross product:
        #
        # omega x r =
        #
        # [ wy*rz - wz*ry ]
        # [ wz*rx - wx*rz ]
        # [ wx*ry - wy*rx ]
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

        # Remove the velocity caused purely by the DVL's offset
        # from the center of rotation.
        vehicle_vx = sensor_vx - rotational_vx
        vehicle_vy = sensor_vy - rotational_vy
        vehicle_vz = sensor_vz - rotational_vz

        return vehicle_vx, vehicle_vy, vehicle_vz

    def odometry_callback(self, msg: Odometry):
        """
        Construct Neptune's canonical state.

        Ground truth now provides ONLY:
        - x position
        - y position

        Everything else used by the controller is sensor-derived.
        """

        # Wait until all sensor streams have produced measurements.
        if self.latest_depth is None:
            return

        if self.latest_imu is None:
            return

        if self.latest_dvl is None:
            return

        # Create a fresh canonical state message.
        state = Odometry()

        # ---------------------------------------------------------
        # Header
        # ---------------------------------------------------------

        state.header.stamp = msg.header.stamp
        state.header.frame_id = msg.header.frame_id
        state.child_frame_id = msg.child_frame_id

        # ---------------------------------------------------------
        # Position
        # ---------------------------------------------------------

        # LAST remaining ground-truth state quantities.
        state.pose.pose.position.x = msg.pose.pose.position.x
        state.pose.pose.position.y = msg.pose.pose.position.y

        # Sensor-derived depth.
        state.pose.pose.position.z = self.latest_depth

        # ---------------------------------------------------------
        # Orientation
        # ---------------------------------------------------------

        # Sensor-derived orientation from IMU.
        state.pose.pose.orientation = (
            self.latest_imu.orientation
        )

        # ---------------------------------------------------------
        # Angular velocity
        # ---------------------------------------------------------

        # Sensor-derived angular rate from IMU.
        state.twist.twist.angular = (
            self.latest_imu.angular_velocity
        )

        # ---------------------------------------------------------
        # Linear velocity
        # ---------------------------------------------------------

        # Convert DVL measurement into vehicle-origin velocity.
        vehicle_vx, vehicle_vy, vehicle_vz = (
            self.dvl_to_vehicle_velocity()
        )

        state.twist.twist.linear.x = vehicle_vx
        state.twist.twist.linear.y = vehicle_vy
        state.twist.twist.linear.z = vehicle_vz

        # ---------------------------------------------------------
        # Covariance
        # ---------------------------------------------------------

        # TEMPORARY:
        # these still come from simulator odometry.
        #
        # A real estimator will publish its own uncertainty.
        state.pose.covariance = msg.pose.covariance
        state.twist.covariance = msg.twist.covariance

        # ---------------------------------------------------------
        # Publish
        # ---------------------------------------------------------

        self.state_pub.publish(state)


def main(args=None):
    """
    ROS 2 executable entry point.
    """

    rclpy.init(args=args)

    node = HybridState()

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