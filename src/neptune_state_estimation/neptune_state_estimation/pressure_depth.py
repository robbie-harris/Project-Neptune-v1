# ROS 2 Python library.
import rclpy

# Base class used to create ROS 2 nodes.
from rclpy.node import Node

# Message produced by the simulated pressure sensor.
from sensor_msgs.msg import FluidPressure

# Simple message containing one floating-point number.
# We will use this to publish our estimated depth.
from std_msgs.msg import Float64


class PressureDepth(Node):
    """
    Estimate vehicle depth using only the pressure sensor.

    Input:
        /sim/pressure

    Output:
        /estimate/depth

    This is the first step toward removing simulator ground truth
    from Project Neptune's state-estimation pipeline.
    """

    def __init__(self):
        # Create a ROS node named /pressure_depth.
        super().__init__('pressure_depth')

        # -----------------------------
        # Physical constants
        # -----------------------------

        # Approximate water density in kg/m^3.
        #
        # Our calibration experiment measured about 9.8 kPa of
        # pressure increase per meter of depth, which is consistent
        # with approximately freshwater density.
        self.water_density = 997.0

        # Gravitational acceleration in m/s^2.
        self.gravity = 9.81

        # -----------------------------
        # Sensor mounting calibration
        # -----------------------------

        # The pressure sensor is mounted at z = -0.40 m relative
        # to the Girona vehicle origin.
        #
        # Our calibration experiment showed that an effective
        # vehicle-reference offset of approximately 0.33 m gives
        # the closest match to simulator odometry.
        #
        # Later, when we incorporate IMU orientation and a proper
        # frame transform, we will replace this simple constant.
        self.vehicle_depth_offset = 0.40

        # -----------------------------
        # Publisher
        # -----------------------------

        # Publish the estimated vehicle depth as one Float64.
        self.depth_pub = self.create_publisher(
            Float64,
            '/estimate/depth',
            10,
        )

        # -----------------------------
        # Subscriber
        # -----------------------------

        # Listen to Stonefish's simulated pressure sensor.
        #
        # Every time a FluidPressure message arrives,
        # pressure_callback() is automatically called.
        self.pressure_sub = self.create_subscription(
            FluidPressure,
            '/sim/pressure',
            self.pressure_callback,
            10,
        )

        self.get_logger().info(
            'Pressure depth estimator ready: '
            '/sim/pressure -> /estimate/depth'
        )

    def pressure_callback(self, msg: FluidPressure):
        """
        Convert one pressure measurement into estimated vehicle depth.
        """

        # Pressure measurement in Pascals.
        pressure = msg.fluid_pressure

        # Hydrostatic equation:
        #
        #     P = rho * g * h
        #
        # therefore:
        #
        #     h = P / (rho * g)
        #
        # This gives depth of the PRESSURE SENSOR below the
        # simulated water surface.
        sensor_depth = pressure / (
            self.water_density * self.gravity
        )

        # Convert from pressure-sensor depth to approximately the
        # Girona vehicle-reference depth used by our autonomy stack.
        vehicle_depth = (
            sensor_depth
            + self.vehicle_depth_offset
        )

        # Create the ROS message we want to publish.
        depth_msg = Float64()

        # Put our estimated depth into the message.
        depth_msg.data = vehicle_depth

        # Publish the estimate.
        self.depth_pub.publish(depth_msg)


def main(args=None):
    """
    ROS 2 executable entry point.
    """

    # Initialize ROS communication.
    rclpy.init(args=args)

    # Create our pressure-depth node.
    node = PressureDepth()

    try:
        # Keep processing pressure measurements indefinitely.
        rclpy.spin(node)

    except KeyboardInterrupt:
        # Ctrl+C is a normal shutdown.
        pass

    finally:
        # Clean up the ROS node.
        node.destroy_node()

        # Shut down ROS communication.
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
