#!/usr/bin/env python3
"""ROS smoke verification, writes observed rates and ideal stereo checks."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, Imu, FluidPressure, CameraInfo
from stonefish_ros2.msg import DVL
from std_msgs.msg import String
from rosgraph_msgs.msg import Clock
from vision_msgs.msg import Detection2DArray
from tf2_ros import Buffer, TransformListener
from rclpy.time import Time


def main():
    p=argparse.ArgumentParser(); p.add_argument('--seconds',type=float,default=20); p.add_argument('--output',default='/workspace/outputs/runtime.json'); p.add_argument('--require-model',action='store_true'); args=p.parse_args()
    rclpy.init(); node=Node('neptune_verify'); samples=defaultdict(list); headers={}; status={}; errors=[]; latencies={}; clock_values=[]
    tf_buffer=Buffer(); tf_listener=TransformListener(tf_buffer,node)
    def recv(key,msg):
        samples[key].append(time.monotonic())
        if key=='clock': clock_values.append(msg.clock.sec+msg.clock.nanosec*1e-9)
        if hasattr(msg,'header'):
            headers.setdefault(key,set()).add((msg.header.stamp.sec,msg.header.stamp.nanosec))
        if isinstance(msg,Image) and key in ['left','right','down'] and (msg.width,msg.height)!=(640,480): errors.append('Camera resolution mismatch')
        if key=='status':
            status.update(json.loads(msg.data))
            capture=status.get('stamp'); latency=status.get('latency_ms')
            if capture and latency is not None: latencies[(capture['sec'],capture['nanosec'])]=latency
    entries=[('left','/neptune/camera/left/image_color',Image),('right','/neptune/camera/right/image_color',Image),('down','/neptune/camera/down/image_color',Image),('left_info','/neptune/camera/left/camera_info',CameraInfo),('imu','/neptune/imu',Imu),('pressure','/neptune/pressure',FluidPressure),('dvl','/neptune/dvl',DVL),('sonar','/neptune/sonar/image',Image),('clock','/clock',Clock),('status','/neptune/perception/status',String),('detections','/neptune/perception/pipe_detections',Detection2DArray),('annotated','/neptune/perception/annotated',Image)]
    # Give the measurement observer enough history to survive brief CPU stalls.
    for key,topic,typ in entries:
        node.create_subscription(typ,topic,lambda m,k=key:recv(k,m),qos_profile_sensor_data if typ in (Imu,FluidPressure,DVL) else 10 if typ in [Image,CameraInfo] else 1000)
    start=time.monotonic()
    while time.monotonic()-start<args.seconds: rclpy.spin_once(node,timeout_sec=.1)
    required=['left','right','down','left_info','imu','pressure','dvl','sonar','clock','status']
    for k in required:
        if not samples[k]: errors.append('Missing topic: '+k)
    left=headers.get('left',set()); right=headers.get('right',set())
    common=left&right
    # Permit boundary samples delivered outside this observation window.
    interior=sorted(left)[1:-1]
    if not common or any(t not in right for t in interior): errors.append('Stereo capture timestamps differ')
    if args.require_model and (status.get('state')!='ready' or not samples['detections']): errors.append('Trained detector not running')
    transforms={}; world_to_body=None
    try:
        transform=tf_buffer.lookup_transform('world_ned','Neptune/base_link',Time())
        t=transform.transform.translation; world_to_body=[t.x,t.y,t.z]
    except Exception as exc: errors.append('Missing world-to-body transform: '+str(exc))
    for frame in ['CameraLeft','CameraRight','CameraDown','IMU','Pressure','DVL','Sonar']:
        try:
            transform=tf_buffer.lookup_transform('Neptune/base_link','Neptune/'+frame,Time())
            t=transform.transform.translation; transforms[frame]=[t.x,t.y,t.z]
        except Exception as exc: errors.append('Missing transform '+frame+': '+str(exc))
    if 'CameraLeft' in transforms and 'CameraRight' in transforms:
        baseline=sum((a-b)**2 for a,b in zip(transforms['CameraLeft'],transforms['CameraRight']))**.5
        if abs(baseline-.12)>1e-6: errors.append('Stereo TF baseline mismatch')
    if args.require_model:
        # Inference may begin before this observation window; check interior outputs.
        for key in ['detections','annotated']:
            outputs=sorted(headers.get(key,set()))[1:-1]
            if not outputs: errors.append('Missing timestamped output: '+key)
            elif any(t not in left for t in outputs): errors.append('Input timestamps not preserved: '+key)
    if samples['clock'] and left and max(t[0] for t in left)>1_000_000: errors.append('Wall-clock sensor timestamp')
    real_time_factor=None
    if len(clock_values)>1:
        real_time_factor=(clock_values[-1]-clock_values[0])/(samples['clock'][-1]-samples['clock'][0])
        if any(b<a for a,b in zip(clock_values,clock_values[1:])): errors.append('Simulation clock moved backwards')
        if real_time_factor>1.2: errors.append('Simulation clock catch-up exceeds wall-time pacing')
    report={'weights_sha256':status.get('weights_sha256'),'passed':not errors,'errors':errors,'counts':{k:len(v) for k,v in samples.items()},'wall_rates_hz':{k:(len(v)-1)/(v[-1]-v[0]) if len(v)>1 else 0 for k,v in samples.items()},'stereo_common_stamps':len(common),'transforms_body_to_sensor':transforms,'world_to_body_xyz':world_to_body,'sampled_inference_latency_ms':{'samples':len(latencies),'mean':float(np.mean(list(latencies.values()))) if latencies else None,'p95':float(np.percentile(list(latencies.values()),95)) if latencies else None},'detector':status}
    report['simulation_real_time_factor']=real_time_factor
    dest=Path(args.output); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
    node.destroy_node(); rclpy.shutdown(); raise SystemExit(bool(errors))

if __name__=='__main__': main()
