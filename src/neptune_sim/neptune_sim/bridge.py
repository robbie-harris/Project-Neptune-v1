"""ROS-to-Tkinter newline JSON bridge adapted from ros2-docker.

Commands and freshness use monotonic wall time so pausing simulation never
prevents the one-second safety stop. Camera/detection headers retain sim time.
"""
import base64
import json
import math
import socket
import threading
import time
import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.clock import Clock
from rclpy.clock_type import ClockType
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
from sensor_msgs.msg import Image, Imu, FluidPressure
from stonefish_ros2.msg import DVL
from std_msgs.msg import Float64MultiArray, String, Bool, Float64
from .protocol import command, active_command
from .autonomous_power import validate_power
from .optics import DEFAULTS, validate_profile, native_request, applied_profile
from .views import DEFAULTS as VIEW_DEFAULTS,validate_views,view_rates


class Bridge(Node):
    def __init__(self):
        super().__init__('neptune_bridge')
        self.declare_parameter('port',9090)
        self.declare_parameter('preview_fps',10.0)
        self.declare_parameter('realistic',False)
        self.declare_parameter('lateral_enabled',False)
        self.lateral_enabled=bool(self.get_parameter('lateral_enabled').value)
        self.declare_parameter('manual_scale',1.0)
        self.manual_scale=max(0.,min(1.,float(self.get_parameter('manual_scale').value)))
        self.preview_interval=1.0/max(1.0,min(30.0,self.get_parameter('preview_fps').value))
        self.lock=threading.Lock(); self.stop=threading.Event(); self.gui_clients=[]
        self.cmd=[0.0]*3; self.cmd_t=0.0; self.frames={}; self.preview='annotated'
        self.detector={'state':'unavailable','reason':'Waiting for detector'}; self.det_t=0.0
        self.seen={}; self.last_sent=None; self.overview_sent=None; self.frame_versions={}; self.cv=CvBridge()
        self.telemetry={}; self.telemetry_t=0.; self.auto_cmd=[0.]*3; self.auto_t=0.; self.auto_requested=False; self.auto_seen=False; self.request_t=0.
        self.optics_id=0; self.optics_t=0.; self.optics_seen=0.
        self.optics={'state':'pending','requested':dict(DEFAULTS),'applied':None}
        self.views={'state':'pending','requested':dict(VIEW_DEFAULTS),'applied':None}
        self.views_id=0;self.views_t=time.monotonic()
        self.views_pub=self.create_publisher(Float64MultiArray,'/neptune/views/request',10)
        self.create_subscription(Float64MultiArray,'/neptune/views/applied',self.views_message,10)
        self.optics_pub=self.create_publisher(Float64MultiArray,'/neptune/optics/request',10)
        self.create_subscription(Float64MultiArray,'/neptune/optics/applied',self.optics_message,10)
        self.realistic=self.get_parameter('realistic').value
        self.mode_pub=self.create_publisher(Bool,'/neptune/simulation/realistic',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.power_pub=self.create_publisher(Float64,'/neptune/control/autonomous_power',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.power_pub.publish(Float64(data=100.))
        self.mission_pub=self.create_publisher(String,'/neptune/control/request',10)
        self.mode_pub.publish(Bool(data=self.realistic))
        self.create_subscription(String,'/neptune/telemetry',self.telemetry_message,10)
        self.create_subscription(Float64MultiArray,'/neptune/control/return_command',self.return_command,10)
        self.pub=self.create_publisher(Float64MultiArray,'/neptune/thrusters',10)
        for kind,topic in [('raw','/neptune/camera/left/image_color'),('annotated','/neptune/perception/annotated'),('overview','/neptune/overview/image_color')]:
            self.create_subscription(Image,topic,lambda msg,k=kind:self.image(msg,k),10)
        self.create_subscription(String,'/neptune/perception/status',self.status,10)
        for name,topic,typ in [('right','/neptune/camera/right/image_color',Image),('down','/neptune/camera/down/image_color',Image),('sonar','/neptune/sonar/image',Image),('imu','/neptune/imu',Imu),('pressure','/neptune/pressure',FluidPressure),('dvl','/neptune/dvl',DVL)]:
            self.create_subscription(typ,topic,lambda m,k=name:self.mark(k),10 if typ is Image else qos_profile_sensor_data)
        self.server=socket.socket(); self.server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.server.bind(('0.0.0.0',self.get_parameter('port').value)); self.server.listen(4); self.server.settimeout(0.2)
        threading.Thread(target=self.serve,daemon=True).start(); self.wall_clock=Clock(clock_type=ClockType.STEADY_TIME); self.create_timer(0.05,self.tick,clock=self.wall_clock); self.create_timer(self.preview_interval,self.send_image,clock=self.wall_clock)

    def mark(self,key):
        with self.lock: self.seen[key]=time.monotonic()

    def views_message(self,msg):
        with self.lock:
            if len(msg.data)!=4 or msg.data[0]!=self.views_id:return
            if msg.data[3]!=1:
                self.views={**self.views,'state':'error','reason':'Native view priority update failed'};return
            profile={'camera':bool(msg.data[1]),'overview':bool(msg.data[2])}
            if profile!=self.views['requested']:return
            self.views={'state':'applied','requested':profile,'applied':profile,'requested_rates_hz':view_rates(profile)}

    def optics_message(self,msg):
        with self.lock:
            self.optics_seen=time.monotonic()
            if len(msg.data)!=6: return
            if msg.data[0]!=self.optics_id:
                if self.optics['state']=='pending' and self.optics_t: return
                self.optics_id=int(msg.data[0])
                try: self.optics['requested']=applied_profile(msg.data)
                except ValueError: return
            try:
                applied=applied_profile(msg.data)
                if applied!=self.optics['requested']: raise ValueError('Applied profile mismatch')
                self.optics={'state':'applied','requested':applied,'applied':applied}
            except ValueError as exc:
                self.optics={**self.optics,'state':'error','reason':str(exc)}

    def telemetry_message(self,msg):
        try: payload=json.loads(msg.data)
        except ValueError: return
        with self.lock: self.telemetry=payload; self.telemetry_t=time.monotonic()

    def return_command(self,msg):
        try:
            raw=list(msg.data)
            if len(raw) != (4 if self.lateral_enabled else 3):return
            values=command({'cmd':raw[:3]})
            if self.lateral_enabled:
                if not math.isfinite(raw[3]) or abs(raw[3])>1:return
                values.append(float(raw[3]))
        except (ValueError,TypeError): return
        with self.lock: self.auto_cmd=values; self.auto_t=time.monotonic()

    def cancel_return(self,reason):
        self.auto_requested=False; self.auto_seen=False
        self.mission_pub.publish(String(data='cancel:'+reason))

    def image(self,msg,kind):
        with self.lock:
            self.seen[kind]=time.monotonic()
            if not self.views['requested']['overview' if kind=='overview' else 'camera']:return
        frame=self.cv.imgmsg_to_cv2(msg,desired_encoding='bgr8')
        with self.lock:
            self.frames[kind]=frame; self.seen[kind]=time.monotonic()
            self.frame_versions[kind]=self.frame_versions.get(kind,0)+1

    def status(self,msg):
        try: st=json.loads(msg.data)
        except ValueError: return
        with self.lock: self.detector=st; self.det_t=time.monotonic()

    def serve(self):
        while not self.stop.is_set():
            try: conn,_=self.server.accept()
            except socket.timeout: continue
            except OSError: break
            conn.settimeout(0.5)
            with self.lock: self.gui_clients.append(conn)
            threading.Thread(target=self.read,args=(conn,),daemon=True).start()

    def drop(self,conn):
        with self.lock:
            if conn in self.gui_clients: self.gui_clients.remove(conn)
            self.cmd=[0.0]*3; self.cmd_t=0.0
            self.cancel_return('GUI disconnected')
        try: conn.close()
        except OSError: pass

    def read(self,conn):
        buf=b''
        try:
            while not self.stop.is_set():
                try: chunk=conn.recv(4096)
                except socket.timeout: continue
                if not chunk: break
                buf+=chunk
                if len(buf)>65536: break
                while b'\n' in buf:
                    line,buf=buf.split(b'\n',1)
                    try:
                        payload=json.loads(line)
                        if 'cmd' in payload:
                            values=command(payload)
                            with self.lock:
                                if any(abs(v)>1e-6 for v in values) and self.auto_requested: self.cancel_return('Manual override')
                                self.cmd=values; self.cmd_t=time.monotonic()
                        if isinstance(payload.get('realistic'),bool):
                            with self.lock:
                                self.cancel_return('Error profile changed'); self.cmd=[0.]*3; self.cmd_t=time.monotonic(); self.realistic=payload['realistic']
                                self.mode_pub.publish(Bool(data=self.realistic))
                        if 'optics' in payload:
                            profile=validate_profile(payload['optics'])
                            with self.lock:
                                if self.auto_requested:self.cancel_return('Optical settings changed')
                                self.optics_id+=1; self.optics_t=time.monotonic()
                                self.optics={**self.optics,'state':'pending','requested':profile}
                                self.optics.pop('reason',None)
                                self.optics_pub.publish(Float64MultiArray(data=native_request(profile,self.optics_id)))
                        if 'autonomous_power_percent' in payload:
                            percent=validate_power(payload['autonomous_power_percent'])
                            self.power_pub.publish(Float64(data=percent))
                        if payload.get('mission') in ('return','inspect','cancel'):
                            with self.lock:
                                if payload['mission'] in ('return','inspect'):
                                    self.cmd=[0.]*3; self.cmd_t=time.monotonic(); self.auto_requested=True; self.auto_seen=False; self.request_t=time.monotonic()
                                    self.mission_pub.publish(String(data=payload['mission']))
                                else:
                                    self.cmd=[0.]*3;self.cmd_t=time.monotonic();self.cancel_return('Operator stop')
                        if payload.get('preview') in ('raw','annotated'):
                            with self.lock: self.preview=payload['preview']
                        if 'views' in payload:
                            profile=validate_views(payload['views'])
                            with self.lock:
                                self.views_id+=1;self.views_t=time.monotonic()
                                self.views={'state':'pending','requested':profile,'applied':self.views.get('applied')}
                                self.last_sent=None;self.overview_sent=None
                                for kind in ('raw','annotated','overview'):
                                    if not profile['overview' if kind=='overview' else 'camera']:self.frames.pop(kind,None)
                                self.views_pub.publish(Float64MultiArray(data=[float(self.views_id),float(profile['camera']),float(profile['overview'])]))
                    except (ValueError,TypeError,AttributeError): pass
        except OSError: pass
        finally: self.drop(conn)

    def send(self,payload):
        encoded=(json.dumps(payload)+'\n').encode()
        with self.lock: clients=list(self.gui_clients)
        for conn in clients:
            try: conn.sendall(encoded)
            except (OSError,socket.timeout): self.drop(conn)

    def tick(self):
        now=time.monotonic()
        with self.lock:
            cmd=active_command(self.cmd,self.cmd_t,now);cmd[:2]=[v*self.manual_scale for v in cmd[:2]];det=dict(self.detector)
            telemetry=dict(self.telemetry) if now-self.telemetry_t<1 else {'ready':False,'reason':'Telemetry stale'}
            if self.auto_requested:
                if now-self.cmd_t>=1: self.cancel_return('GUI heartbeat timed out')
                elif now-self.telemetry_t>=1 or now-self.auto_t>=.5: self.cancel_return('Controller unavailable')
                elif telemetry.get('autonomy',telemetry.get('return',{})).get('active'):
                    self.auto_seen=True; cmd=list(self.auto_cmd)
                elif self.auto_seen or now-self.request_t>1:
                    self.auto_requested=False
            if now-self.det_t>2: det={'state':'unavailable','reason':'Detector status stale','detections':[]}
            if now-self.seen.get('raw',0)>2: det={**det,'detections':[],'camera_stale':True}
            health={key:now-t<2 for key,t in self.seen.items()}
            optics=dict(self.optics)
            if self.optics_seen and now-self.optics_seen>2:
                optics={**optics,'state':'error','reason':'Native optical status stale'}
            elif optics['state']=='pending' and self.optics_t and now-self.optics_t>5:
                optics={**optics,'state':'error','reason':'Native optical update timed out'}
            views=dict(self.views)
            if views['state']=='pending' and now-self.views_t>5:views={**views,'state':'error','reason':'Native view update timed out'}
        actuators=cmd[:3]+([cmd[3],cmd[3]] if len(cmd)==4 else [0.,0.]) if self.lateral_enabled else cmd
        self.pub.publish(Float64MultiArray(data=actuators))
        self.send({'state':{'thrusters':cmd[:3],'sway':cmd[3] if len(cmd)==4 else 0.,'detector':det,'sensors':health,'telemetry':telemetry,'realistic':self.realistic,'optics':optics,'views':views}})

    def send_image(self):
        now=time.monotonic()
        with self.lock:
            actual_preview=self.preview; frame=self.frames.get(actual_preview)
            if frame is None or now-self.seen.get(actual_preview,0)>2:
                actual_preview='raw'; frame=self.frames.get('raw')
            version=(actual_preview,self.frame_versions.get(actual_preview,0))
            camera_enabled=self.views['requested']['camera']
        if camera_enabled and frame is not None and version!=self.last_sent:
            preview=frame if frame.shape[:2]==(480,640) else cv2.resize(frame,(640,480))
            ok,png=cv2.imencode('.png',preview,[cv2.IMWRITE_PNG_COMPRESSION,1])
            if ok:
                self.send({'img':base64.b64encode(png.tobytes()).decode(),'preview':actual_preview})
                self.last_sent=version
        with self.lock:
            overview=self.frames.get('overview'); version=self.frame_versions.get('overview',0)
            fresh=now-self.seen.get('overview',0)<2
            overview_enabled=self.views['requested']['overview']
        if overview_enabled and overview is not None and fresh and version!=self.overview_sent:
            preview=overview if overview.shape[:2]==(240,640) else cv2.resize(overview,(640,240))
            ok,png=cv2.imencode('.png',preview,[cv2.IMWRITE_PNG_COMPRESSION,1])
            if ok:
                self.send({'overview':base64.b64encode(png.tobytes()).decode()})
                self.overview_sent=version

    def destroy_node(self):
        self.stop.set(); self.server.close()
        for conn in list(self.gui_clients): self.drop(conn)
        if self.context.ok(): self.pub.publish(Float64MultiArray(data=[0.0]*3))
        return super().destroy_node()


def main():
    rclpy.init(); node=Bridge()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.try_shutdown()
