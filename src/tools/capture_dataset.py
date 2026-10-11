#!/usr/bin/env python3
"""Capture real Stonefish renders after respawn; group-wise deterministic split."""
import argparse
from collections import deque
import json
import math
from pathlib import Path
import time
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CameraInfo
from nav_msgs.msg import Odometry
from std_msgs.msg import Float64MultiArray
from stonefish_ros2.srv import Respawn
from std_srvs.srv import SetBool
from geometry import rotation_rpy, pipe_surface, projected_box, yolo_label


def stamp(msg): return msg.header.stamp.sec+msg.header.stamp.nanosec/1e9


def poses(seed=42):
    rng=np.random.default_rng(seed); groups=np.arange(100); rng.shuffle(groups)
    partitions={int(g):'train' if i<70 else 'val' if i<85 else 'test' for i,g in enumerate(groups)}
    for group in range(100):
        center=np.array([rng.uniform(-3.8,2.5),rng.uniform(-1.6,1.6),rng.uniform(0.7,2.3)])
        for variant in range(10):
            xyz=center+rng.uniform([-0.12,-0.08,-0.06],[0.12,0.08,0.06])
            target=np.array([4.4,0,1.5])-xyz
            yaw=math.atan2(target[1],target[0])+rng.uniform(-0.3,0.3)
            pitch=-math.atan2(target[2],np.linalg.norm(target[:2]))+rng.uniform(-0.07,0.07)
            if variant<2: yaw+=math.pi # Negative views, away from the far pipe.
            yield group,variant,partitions[group],xyz,[0,pitch,yaw]


class Capture(Node):
    def __init__(self):
        super().__init__('neptune_capture')
        self.set_parameters([rclpy.parameter.Parameter('use_sim_time',value=True)])
        # Retain capture-time poses through delayed GPU readback and physics
        # catch-up after host scheduling gaps. This changes offline bookkeeping,
        # not simulated sensor timestamps or the dynamics.
        self.cv=CvBridge(); self.frame=None; self.info=None; self.history=deque(maxlen=20000)
        self.create_subscription(Image,'/neptune/camera/left/image_color',lambda m:setattr(self,'frame',m),10)
        self.create_subscription(CameraInfo,'/neptune/camera/left/camera_info',lambda m:setattr(self,'info',m),10)
        self.create_subscription(Odometry,'/neptune/ground_truth',lambda m:self.history.append(m),QoSProfile(depth=100,reliability=ReliabilityPolicy.BEST_EFFORT))
        self.client=self.create_client(Respawn,'/stonefish_ros2/respawn_robot')
        self.thrusters=self.create_publisher(Float64MultiArray,'/neptune/thrusters',10)

    def wait(self,predicate,timeout=30):
        start=time.monotonic()
        while time.monotonic()-start<timeout:
            self.thrusters.publish(Float64MultiArray(data=[0.0]*3))
            rclpy.spin_once(self,timeout_sec=0.05)
            if predicate(): return
        raise TimeoutError('Simulator capture timed out; inspect Stonefish logs and sensor topics.')

    def peripheral_sensors(self,enabled):
        for name in ['CameraRight','CameraDown','Sonar']:
            client=self.create_client(SetBool,'/neptune/sensors/'+name+'/set_enabled')
            if not client.wait_for_service(timeout_sec=5):
                raise RuntimeError('Sensor service absent: rebuild or use --keep-all-sensors')
            req=SetBool.Request(); req.data=enabled
            future=client.call_async(req); self.wait(future.done)
            if not future.result().success: raise RuntimeError('Cannot toggle '+name)
            self.destroy_client(client)

    def capture(self,xyz,rpy):
        started=time.monotonic(); initial_sim=stamp(self.history[-1]) if self.history else None
        req=Respawn.Request(); req.name='Neptune'
        req.origin.position.x,req.origin.position.y,req.origin.position.z=map(float,xyz)
        matrix=rotation_rpy(rpy); rv,_=cv2.Rodrigues(matrix); angle=np.linalg.norm(rv)
        q=np.r_[rv[:,0]/angle*np.sin(angle/2),np.cos(angle/2)] if angle else np.array([0.,0.,0.,1.])
        req.origin.orientation.x,req.origin.orientation.y,req.origin.orientation.z,req.origin.orientation.w=map(float,q)
        previous=stamp(self.frame) if self.frame else -1
        fut=self.client.call_async(req); self.wait(fut.done)
        if not fut.result().success: raise RuntimeError(fut.result().message)
        def settled():
            if not self.history: return False
            p=self.history[-1].pose.pose.position; qmsg=self.history[-1].pose.pose.orientation
            pos=np.array([p.x,p.y,p.z]); actual=np.array([qmsg.x,qmsg.y,qmsg.z,qmsg.w])
            return np.linalg.norm(pos-xyz)<0.03 and abs(float(actual@q))>0.999
        self.wait(settled)
        stable_after=stamp(self.history[-1])+0.25
        self.wait(lambda:self.frame is not None and stamp(self.frame)>max(previous,stable_after))
        msg=self.frame
        # Image and ground-truth callbacks can arrive in either order. Drain ROS
        # delivery before judging a valid image's capture-time pose as missing.
        self.wait(lambda:any(abs(stamp(gt)-stamp(msg))<=0.05 for gt in self.history),timeout=5)
        gt=min(self.history,key=lambda m:abs(stamp(m)-stamp(msg)))
        if abs(stamp(gt)-stamp(msg))>0.05: raise RuntimeError('No matching capture-time ground truth')
        self.last_capture_wall=time.monotonic()-started
        if initial_sim is not None and stamp(msg)-initial_sim>2*self.last_capture_wall+1:
            raise RuntimeError('Simulator clock catch-up exceeds capture pacing; reject image and inspect clock')
        return msg,gt


def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',default='/workspace/data/pipe'); p.add_argument('--rig',default='/opt/neptune/Simulation/config/rig.json'); p.add_argument('--limit',type=int,default=1000); p.add_argument('--resume',action='store_true'); p.add_argument('--keep-all-sensors',action='store_true'); args=p.parse_args()
    if not 1<=args.limit<=1000: p.error('--limit must be 1..1000')
    dest=Path(args.output); dest.mkdir(parents=True,exist_ok=True)
    if (dest/'manifest.jsonl').exists() and not args.resume: p.error('Dataset exists; use --resume or a new output directory')
    existing_ids={json.loads(line)['id'] for line in (dest/'manifest.jsonl').read_text().splitlines() if line.strip()} if (dest/'manifest.jsonl').exists() else set()
    rig=json.loads(Path(args.rig).read_text()); camera=rig['cameras']['left']; surface=pipe_surface(rig['pipe'])
    rclpy.init(); node=Capture()
    try:
        if not node.client.wait_for_service(timeout_sec=30): raise RuntimeError('Respawn service unavailable')
        node.wait(lambda:node.info is not None and node.frame is not None and bool(node.history),timeout=90)
        if not args.keep_all_sensors: node.peripheral_sensors(False)
        K=np.array(node.info.k).reshape(3,3)
        captured=0
        for index,(group,variant,split,xyz,rpy) in enumerate(poses()):
            if index>=args.limit: break
            key=f'g{group:03d}_v{variant:02d}'; image_dir=dest/'images'/split; label_dir=dest/'labels'/split
            image_dir.mkdir(parents=True,exist_ok=True); label_dir.mkdir(parents=True,exist_ok=True)
            if args.resume and key in existing_ids and (image_dir/(key+'.png')).exists() and (label_dir/(key+'.txt')).exists(): continue
            msg,gt=node.capture(xyz,rpy); pose=gt.pose.pose
            q=pose.orientation; norm=np.linalg.norm([q.x,q.y,q.z]); angle=2*np.arctan2(norm,q.w)
            rv=np.array([q.x,q.y,q.z])*angle/norm if norm else np.zeros(3)
            world_body=np.eye(4); world_body[:3,:3]=cv2.Rodrigues(rv)[0]; world_body[:3,3]=[pose.position.x,pose.position.y,pose.position.z]
            body_cam=np.eye(4); body_cam[:3,:3]=rotation_rpy(camera['rpy']); body_cam[:3,3]=camera['xyz']
            box=projected_box(surface,world_body@body_cam,K,msg.width,msg.height)
            frame=node.cv.imgmsg_to_cv2(msg,desired_encoding='bgr8')
            if not cv2.imwrite(str(image_dir/(key+'.png')),frame): raise IOError('Image write failed')
            (label_dir/(key+'.txt')).write_text(yolo_label(box,msg.width,msg.height))
            record={'id':key,'group':group,'split':split,'bbox':box,'stamp':stamp(msg),'requested_xyz':xyz.tolist(),'requested_rpy':rpy,'world_camera':(world_body@body_cam).tolist(),'image':str((image_dir/(key+'.png')).relative_to(dest))}
            with (dest/'manifest.jsonl').open('a') as f: f.write(json.dumps(record)+'\n')
            captured+=1
            if captured==1 or captured%25==0: print(f'Captured {captured} new frames; processed {index+1}/{args.limit}',flush=True)
        (dest/'dataset.yaml').write_text('path: '+str(dest.resolve())+'\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: pipe\n')
        (dest/'generation.json').write_text(json.dumps({'seed':42,'target_images':1000,'limit':args.limit,'split_groups':[70,15,15],'camera_k':K.tolist(),'rig':rig},indent=2))
    finally:
        if rclpy.ok() and not args.keep_all_sensors:
            try: node.peripheral_sensors(True)
            except Exception as exc: print('Could not restore sensors:',exc)
        if rclpy.ok(): node.thrusters.publish(Float64MultiArray(data=[0.0]*3))
        node.destroy_node(); rclpy.try_shutdown()

if __name__=='__main__': main()
