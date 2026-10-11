"""Keep Stonefish ideal topics private; inject switchable errors upstream of consumers."""
import copy
import heapq
import json
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import cv2
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock
from rclpy.clock_type import ClockType
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Image, Imu, FluidPressure, CameraInfo, Range
from std_msgs.msg import Bool
from stonefish_ros2.msg import DVL
from cv_bridge import CvBridge
from .navigation import rpy, quat
from .error_model import ErrorModel


def seconds(stamp): return stamp.sec+stamp.nanosec*1e-9
def set_stamp(stamp, value):
    nanoseconds=max(0,round(value*1e9)); stamp.sec=nanoseconds//10**9; stamp.nanosec=nanoseconds%10**9


class ErrorAdapter(Node):
    def __init__(self):
        super().__init__('error_adapter'); self.declare_parameter('profile','')
        self.settings=json.loads(open(self.get_parameter('profile').value).read())
        cv2.setNumThreads(1)
        self.model=ErrorModel(self.settings); self.realistic=False; self.started=0; self.pending=[]; self.serial=0; self.cv=CvBridge()
        self.angular_speed=0.; self.dvl_lost_until=0.
        self.image_worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='sensor-images')
        self.image_jobs={}; self.generation=0
        self.create_subscription(Bool,'/neptune/simulation/realistic',self.mode,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.output_publishers={}
        entries=[('left','camera/left/image_color',Image),('right','camera/right/image_color',Image),('down','camera/down/image_color',Image),
                 ('imu','imu',Imu),('pressure','pressure',FluidPressure),('dvl','dvl',DVL),('sonar','sonar/image',Image),('altitude','altitude',Range)]
        entries += [(name+'_info','camera/'+name+'/camera_info',CameraInfo) for name in ['left','right','down']]
        for name,path,typ in entries:
            qos=qos_profile_sensor_data if typ in (Imu,FluidPressure,DVL,Range) else 10
            self.output_publishers[name]=self.create_publisher(typ,'/neptune/'+path,qos)
            self.create_subscription(typ,'/neptune/ideal/'+path,lambda msg,n=name:self.receive(n,msg),qos)
        self.create_timer(.005,self.flush,clock=Clock(clock_type=ClockType.STEADY_TIME))

    def mode(self,msg):
        if msg.data!=self.realistic:
            self.realistic=msg.data; self.pending.clear(); self.started=self.get_clock().now().nanoseconds*1e-9
            self.model=ErrorModel(self.settings)
            self.generation+=1
            self.dvl_lost_until=0.
            self.get_logger().info('Sensor errors '+('enabled' if self.realistic else 'disabled'))

    def receive(self,name,msg):
        if isinstance(msg,Imu): self.angular_speed=float(np.linalg.norm([msg.angular_velocity.x,msg.angular_velocity.y,msg.angular_velocity.z]))
        if not self.realistic:
            self.output_publishers[name].publish(msg); return
        stream=name.removesuffix('_info'); cfg=self.settings.get(stream,self.settings['camera'] if stream in ['left','right','down'] else {})
        if not name.endswith('_info') and self.model.rng.random()<cfg.get('dropout',0): return
        if isinstance(msg,Image):
            # Rendering/corruption must not block high-rate navigation callbacks.
            # At most one outstanding frame per stream; never accumulate stale video.
            if name not in self.image_jobs:
                self.image_jobs[name]=(self.generation,self.image_worker.submit(self.image,name,msg,self.model,self.angular_speed))
            return
        out=copy.deepcopy(msg); stamp=seconds(msg.header.stamp)
        set_stamp(out.header.stamp,stamp+self.model.stamp_offset(stream,stamp))
        if isinstance(out,Imu):
            cfg=self.settings['imu']; angles=rpy([msg.orientation.x,msg.orientation.y,msg.orientation.z,msg.orientation.w])
            angles+=np.deg2rad(np.array(cfg['angle_bias_deg'])+self.model.rng.normal(0,cfg['angle_sigma_deg'],3))
            angles[2]+=np.deg2rad(cfg['yaw_drift_deg_min'])*max(0,stamp-self.started)/60
            out.orientation.x,out.orientation.y,out.orientation.z,out.orientation.w=map(float,quat(angles))
            for field,sigma,bias in [('angular_velocity',cfg['gyro_sigma_rad_s'],cfg['gyro_bias_rad_s']),('linear_acceleration',cfg['accel_sigma_m_s2'],cfg['accel_bias_m_s2'])]:
                vector=getattr(out,field); values=np.array([vector.x,vector.y,vector.z])+np.asarray(bias)+self.model.rng.normal(0,sigma,3)
                vector.x,vector.y,vector.z=map(float,values)
            for field,variance in [('orientation_covariance',np.deg2rad(cfg['angle_sigma_deg'])**2),('angular_velocity_covariance',cfg['gyro_sigma_rad_s']**2),('linear_acceleration_covariance',cfg['accel_sigma_m_s2']**2)]:
                values=[0.]*9
                for i in [0,4,8]: values[i]=float(variance)
                setattr(out,field,values)
        elif isinstance(out,FluidPressure):
            cfg=self.settings['pressure']; out.fluid_pressure+=cfg['bias_pa']+self.model.rng.normal(0,cfg['sigma_pa']); out.variance=cfg['sigma_pa']**2
        elif isinstance(out,DVL):
            cfg=self.settings['dvl']; values=np.array([out.velocity.x,out.velocity.y,out.velocity.z])*(1+cfg['scale_error'])+cfg['bias_m_s']+self.model.rng.normal(0,cfg['sigma_m_s'],3)
            out.velocity.x,out.velocity.y,out.velocity.z=map(float,values)
            out.velocity_covariance=[cfg['sigma_m_s']**2 if i in [0,4,8] else 0. for i in range(9)]
            if out.altitude>=0: out.altitude=max(0.,out.altitude+self.model.rng.normal(0,cfg['altitude_sigma_m']))
            if self.model.rng.random()<cfg['bottom_lock_loss_probability']: self.dvl_lost_until=stamp+cfg['bottom_lock_loss_duration_s']
            if stamp<self.dvl_lost_until:
                out.velocity_covariance=[-1.]+[0.]*8; out.altitude=-1.
        elif isinstance(out,Range):
            out.range=max(0.,out.range+self.model.rng.normal(0,self.settings['dvl']['altitude_sigma_m']))
        self.enqueue(name,out)

    def image(self,name,msg,model,angular_speed):
        stamp=seconds(msg.header.stamp)
        if name=='sonar':
            frame=model.sonar(self.cv.imgmsg_to_cv2(msg,desired_encoding='passthrough'))
            converted=self.cv.cv2_to_imgmsg(frame,encoding=msg.encoding)
        else:
            frame=model.camera(self.cv.imgmsg_to_cv2(msg,desired_encoding='bgr8'),stamp,name,angular_speed)
            converted=self.cv.cv2_to_imgmsg(frame,encoding='bgr8')
        converted.header=copy.deepcopy(msg.header)
        set_stamp(converted.header.stamp,stamp+model.stamp_offset(name,stamp))
        return converted

    def enqueue(self,name,out):
        timing=self.settings['timing']; delay=max(0,timing['delivery_delay_s']+self.model.rng.uniform(-timing['delivery_jitter_s'],timing['delivery_jitter_s']))
        self.serial+=1
        heapq.heappush(self.pending,(self.get_clock().now().nanoseconds*1e-9+delay,self.serial,name,out))
        # Bound memory even if simulation pauses after receiving queued data.
        if len(self.pending)>500: heapq.heappop(self.pending)

    def flush(self):
        for name,(generation,job) in list(self.image_jobs.items()):
            if job.done():
                del self.image_jobs[name]
                try:
                    image=job.result()
                    if generation==self.generation: self.enqueue(name,image)
                except Exception as exc:
                    self.get_logger().error('Image error adapter: '+str(exc))
        now=self.get_clock().now().nanoseconds*1e-9
        while self.pending and self.pending[0][0]<=now:
            _,_,name,msg=heapq.heappop(self.pending); self.output_publishers[name].publish(msg)

    def destroy_node(self):
        self.image_worker.shutdown(wait=True,cancel_futures=True)
        return super().destroy_node()


def main():
    rclpy.init(); node=ErrorAdapter()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.try_shutdown()
