"""Sensor-only pose estimate and return guidance; ground truth is comparison-only."""
import json
import time
from pathlib import Path
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock
from rclpy.clock_type import ClockType
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Imu, FluidPressure, Image
from nav_msgs.msg import Odometry
from stonefish_ros2.msg import DVL
from std_msgs.msg import String, Float64MultiArray, Bool, Float64
from .navigation import rpy, rotation, DeadReckoning, return_guidance, agreement, sensors_fresh
from .mission import InspectionMission
from .autonomous_power import validate_power,power_profile


def vector(v): return np.array([v.x,v.y,v.z])
def angles(q): return rpy([q.x,q.y,q.z,q.w])


class OperatorState(Node):
    def __init__(self):
        super().__init__('operator_state'); self.declare_parameter('rig',''); self.declare_parameter('profile','');self.declare_parameter('mission_config','')
        self.rig=json.loads(open(self.get_parameter('rig').value).read()); self.settings=json.loads(open(self.get_parameter('profile').value).read())
        self.estimate=DeadReckoning(self.rig['spawn']); self.guidance=return_guidance(self.rig['spawn'],self.settings['return'])
        mission_path=Path(self.get_parameter('mission_config').value) if self.get_parameter('mission_config').value else Path(self.get_parameter('rig').value).with_name('mission.json')
        mission_settings=json.loads(mission_path.read_text())
        self.guidance=return_guidance(self.rig['spawn'],{**self.settings['return'],**mission_settings.get('return',{})})
        self.mission=InspectionMission(mission_settings,self.rig['spawn'],self.settings['return'])
        self.power_percent=100.
        self.base_mission=mission_settings
        self.base_return=dict(self.guidance.settings)
        self.create_subscription(Float64,'/neptune/control/autonomous_power',self.power,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.truth=None; self.seen={}; self.realistic=False; self.pressure_pa=None; self.altitude=None
        self.dvl_stamp=None; self.dvl_valid=False
        self.create_subscription(Imu,'/neptune/imu',self.imu,qos_profile_sensor_data)
        self.create_subscription(FluidPressure,'/neptune/pressure',self.pressure,qos_profile_sensor_data)
        self.create_subscription(DVL,'/neptune/dvl',self.dvl,qos_profile_sensor_data)
        self.create_subscription(Odometry,'/neptune/ground_truth',self.ground_truth,qos_profile_sensor_data)
        self.create_subscription(String,'/neptune/control/request',self.request,10)
        self.create_subscription(String,'/neptune/perception/status',self.detection,10)
        self.create_subscription(Image,'/neptune/camera/left/image_color',self.camera,10)
        self.create_subscription(Bool,'/neptune/simulation/realistic',self.mode,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.state_pub=self.create_publisher(String,'/neptune/telemetry',10)
        self.auto_pub=self.create_publisher(Float64MultiArray,'/neptune/control/return_command',10)
        self.create_timer(.05,self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME)); self.last_state=0

    def power(self,msg):
        try:percent=validate_power(msg.data)
        except ValueError:return
        self.power_percent=percent
        self.mission.settings=power_profile(self.base_mission,percent)
        self.mission.returner.settings=power_profile(self.base_return,percent)
        self.guidance.settings=power_profile(self.base_return,percent)

    def imu(self,msg):
        self.estimate.attitude=angles(msg.orientation); self.estimate.gyro=vector(msg.angular_velocity); self.seen['imu']=time.monotonic()

    def pressure(self,msg):
        if not np.isfinite(msg.fluid_pressure): return
        self.pressure_pa=msg.fluid_pressure; self.estimate.position[2]=msg.fluid_pressure/9810.; self.seen['pressure']=time.monotonic()

    def dvl(self,msg):
        self.seen['dvl_stream']=time.monotonic()
        self.dvl_valid=msg.velocity_covariance[0]>=0 and np.isfinite(vector(msg.velocity)).all()
        if msg.velocity_covariance[0]<0 or not np.isfinite(vector(msg.velocity)).all(): return
        self.dvl_stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        self.estimate.dvl(vector(msg.velocity),self.dvl_stamp)
        self.altitude=msg.altitude; self.seen['dvl']=time.monotonic()

    def ground_truth(self,msg):
        # This callback never writes the estimator or guidance inputs.
        self.truth=msg; self.seen['truth']=time.monotonic()

    def fresh(self,now):
        return sensors_fresh(now,self.seen,self.get_clock().now().nanoseconds*1e-9,self.dvl_stamp,self.settings['return'])

    def request(self,msg):
        now=time.monotonic()
        if msg.data=='return':
            self.mission.cancel('Return requested')
            if self.fresh(now): self.guidance.start(now)
            else: self.guidance.cancel('Cannot start: sensors unavailable')
        elif msg.data=='inspect':
            self.guidance.cancel('Inspection requested')
            if self.fresh(now) and self.mission.ready(now):self.mission.start(self.estimate,now)
            else:self.mission.cancel('Cannot start: navigation or perception not ready')
        else:
            reason=msg.data.removeprefix('cancel:') or 'Cancelled'
            self.guidance.cancel(reason);self.mission.cancel(reason)

    def detection(self,msg):
        try:self.mission.detection(json.loads(msg.data),time.monotonic(),self.get_clock().now().nanoseconds*1e-9,self.estimate.position)
        except (ValueError,TypeError,KeyError):self.mission.detector_ready=False

    def camera(self,msg):
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        self.mission.camera(stamp,time.monotonic(),self.get_clock().now().nanoseconds*1e-9)

    def mode(self,msg):
        if self.realistic!=msg.data:
            self.guidance.cancel('Error profile changed');self.mission.cancel('Error profile changed')
        self.realistic=msg.data

    def tick(self):
        now=time.monotonic(); fresh=self.fresh(now)
        cmd=self.mission.step(self.estimate,now,fresh) if self.mission.active else self.guidance.step(self.estimate,now,fresh)
        self.auto_pub.publish(Float64MultiArray(data=cmd))
        if now-self.last_state<.1: return
        self.last_state=now
        payload={'autonomous_power_percent':self.power_percent,'ready':fresh,'realistic':self.realistic,'estimated':{'position':self.estimate.position.tolist(),'rpy_deg':np.rad2deg(self.estimate.attitude).tolist(),'velocity_world':self.estimate.velocity.tolist(),'pressure_pa':self.pressure_pa,'altitude_m':self.altitude},
                 'return':{'state':self.guidance.state,'active':self.guidance.active,'reason':self.guidance.reason},
                 'inspection':self.mission.status(),
                 'autonomy':{'active':self.mission.active or self.guidance.active},
                 'sensor_age_s':{k:now-v for k,v in self.seen.items()},'dvl_bottom_lock_valid':bool(self.dvl_valid),
                 'dvl_capture_age_sim_s':None if self.dvl_stamp is None else self.get_clock().now().nanoseconds*1e-9-self.dvl_stamp}
        if self.truth is not None and now-self.seen.get('truth',0)<.75 and fresh:
            truth_position=vector(self.truth.pose.pose.position); truth_rpy=angles(self.truth.pose.pose.orientation)
            truth_velocity=rotation(truth_rpy)@vector(self.truth.twist.twist.linear)
            payload['ground_truth']={'position':truth_position.tolist(),'rpy_deg':np.rad2deg(truth_rpy).tolist(),'velocity_world':truth_velocity.tolist(),'pressure_pa':float(truth_position[2]*9810)}
            payload['comparison']=agreement(self.estimate.position,self.estimate.attitude,truth_position,truth_rpy,self.settings['agreement'])
            payload['comparison'].update(velocity_error_m_s=float(np.linalg.norm(self.estimate.velocity-truth_velocity)),pressure_error_pa=float(self.pressure_pa-truth_position[2]*9810))
        self.state_pub.publish(String(data=json.dumps(payload,allow_nan=False)))


def main():
    rclpy.init(); node=OperatorState()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        if node.context.ok(): node.auto_pub.publish(Float64MultiArray(data=[0.,0.,0.]))
        node.destroy_node(); rclpy.try_shutdown()
