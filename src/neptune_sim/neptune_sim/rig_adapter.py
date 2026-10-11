"""Publish ideal fixed rig transforms and pressure-derived depth; no estimator."""
import json
import math
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock
from rclpy.clock_type import ClockType
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import TransformStamped
from sensor_msgs.msg import FluidPressure
from nav_msgs.msg import Odometry
from stonefish_ros2.srv import Respawn
from std_msgs.msg import Float64
from tf2_ros import StaticTransformBroadcaster


def quaternion(rpy):
    r,p,y=(v/2 for v in rpy)
    return (math.sin(r)*math.cos(p)*math.cos(y)-math.cos(r)*math.sin(p)*math.sin(y),
            math.cos(r)*math.sin(p)*math.cos(y)+math.sin(r)*math.cos(p)*math.sin(y),
            math.cos(r)*math.cos(p)*math.sin(y)-math.sin(r)*math.sin(p)*math.cos(y),
            math.cos(r)*math.cos(p)*math.cos(y)+math.sin(r)*math.sin(p)*math.sin(y))


class RigAdapter(Node):
    def __init__(self):
        super().__init__('rig_adapter')
        self.declare_parameter('rig', '')
        self.declare_parameter('initialize_spawn', True)
        with open(self.get_parameter('rig').value) as f: rig=json.load(f)
        self.tf=StaticTransformBroadcaster(self)
        transforms=[]
        sensors=list(rig['cameras'].values()) + [
            {'frame':'Neptune/IMU','xyz':[0,0,0],'rpy':[0,0,0]},
            {'frame':'Neptune/Pressure','xyz':[0,0,0],'rpy':[0,0,0]},
            {'frame':'Neptune/DVL','xyz':[0,0,0.18],'rpy':[0,0,0]},
            {'frame':'Neptune/DVL_altitude','xyz':[0,0,0.18],'rpy':[0,0,0]},
            {'frame':'Neptune/Sonar','xyz':[0.61,0,0],'rpy':rig['cameras']['left']['rpy']},
            {'frame':'Neptune/GroundTruth','xyz':[0,0,0],'rpy':[0,0,0]}]
        for s in sensors:
            msg=TransformStamped(); msg.header.stamp=self.get_clock().now().to_msg()
            msg.header.frame_id=rig['body_frame']; msg.child_frame_id=s['frame']
            msg.transform.translation.x,msg.transform.translation.y,msg.transform.translation.z=map(float,s['xyz'])
            q=quaternion(s['rpy']); msg.transform.rotation.x,msg.transform.rotation.y,msg.transform.rotation.z,msg.transform.rotation.w=q
            transforms.append(msg)
        self.tf.sendTransform(transforms)
        self.depth=self.create_publisher(Float64,'/neptune/depth',10)
        self.create_subscription(FluidPressure,'/neptune/pressure',self.pressure,qos_profile_sensor_data)
        if self.get_parameter('initialize_spawn').value:
            self.spawn=rig['spawn']; self.spawn_future=None; self.physics_ready=False
            self.spawn_client=self.create_client(Respawn,'/stonefish_ros2/respawn_robot')
            self.spawn_subscription=self.create_subscription(Odometry,'/neptune/ground_truth',self.observe_startup,qos_profile_sensor_data)
            self.startup_clock=Clock(clock_type=ClockType.STEADY_TIME)
            self.spawn_timer=self.create_timer(.2,self.initialize_spawn,clock=self.startup_clock)

    def observe_startup(self,msg):
        self.physics_ready=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9>=.5

    def initialize_spawn(self):
        # Clear initial-condition solver transients once, using the simulator's
        # existing reset service. This never holds or controls the vehicle pose.
        if self.spawn_future is not None:
            if not self.spawn_future.done(): return
            result=self.spawn_future.result()
            if not result.success:
                self.get_logger().error('Initial spawn reset failed: '+result.message)
            else: self.get_logger().info('Startup spawn initialized; ongoing motion remains manual.')
            self.spawn_timer.cancel(); self.destroy_subscription(self.spawn_subscription)
            self.destroy_client(self.spawn_client); return
        if not self.physics_ready or not self.spawn_client.service_is_ready(): return
        request=Respawn.Request(); request.name='Neptune'
        request.origin.position.x,request.origin.position.y,request.origin.position.z=map(float,self.spawn['xyz'])
        q=quaternion(self.spawn['rpy'])
        request.origin.orientation.x,request.origin.orientation.y,request.origin.orientation.z,request.origin.orientation.w=q
        self.spawn_future=self.spawn_client.call_async(request)

    def pressure(self,msg):
        # Stonefish reports gauge pressure, not atmospheric absolute pressure.
        self.depth.publish(Float64(data=msg.fluid_pressure/(1000.0*9.81)))


def main():
    rclpy.init(); node=RigAdapter()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.shutdown()
