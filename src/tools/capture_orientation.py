#!/usr/bin/env python3
"""Capture the expanded benchmark from real Stonefish camera messages."""
import argparse
import hashlib
import json
import uuid
from pathlib import Path
import cv2
import numpy as np
import rclpy
from capture_dataset import Capture,stamp
from geometry import pipe_surface,pipe_edges,projected_geometry,yolo_label
from orientation_views import orientation_views,camera_transform,replacement_view


def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,default=Path('/workspace/data/orientation'))
    p.add_argument('--rig',type=Path,default=Path('/opt/neptune/Simulation/config/rig.json'))
    p.add_argument('--groups',type=int,default=600); p.add_argument('--seed',type=int,default=42)
    p.add_argument('--limit',type=int); p.add_argument('--resume',action='store_true'); args=p.parse_args()
    dest=args.output; dest.mkdir(parents=True,exist_ok=True); manifest=dest/'manifest.jsonl'
    if manifest.exists() and not args.resume: p.error('Dataset exists; use --resume')
    existing=[json.loads(x) for x in manifest.read_text().splitlines()] if manifest.exists() else []
    done={record['id'] for record in existing}; seen_hashes={record['sha256'] for record in existing}
    rig=json.loads(args.rig.read_text()); points=pipe_surface(rig['pipe']); edges=pipe_edges()
    settings={'schema':2,'seed':args.seed,'target_images':args.groups*10,'groups':args.groups,'split_counts':{'train':args.groups*7,'val':args.groups*1.5,'test':args.groups*1.5},'negative_fraction':.25,'roll_degrees':[-180,180],'yaw_offset_degrees':[-90,90],'pitch_offset_degrees':[-45,45],'sensor_noise':0,'sensor_bias':0,'rig':rig}
    previous=dest/'generation.json'
    if previous.exists() and json.loads(previous.read_text())!=settings: p.error('Resume settings differ from existing dataset')
    previous.write_text(json.dumps(settings,indent=2))
    session=uuid.uuid4().hex
    rclpy.init(); node=Capture()
    try:
        if not node.client.wait_for_service(timeout_sec=30): raise RuntimeError('Respawn unavailable')
        node.wait(lambda:node.info is not None and node.frame is not None and bool(node.history),90)
        node.peripheral_sensors(False); K=np.asarray(node.info.k).reshape(3,3)
        for index,v in enumerate(orientation_views(rig,args.groups,args.seed)):
            if args.limit and index>=args.limit: break
            if v['id'] in done: continue
            for attempt in range(20):
                if attempt: v=replacement_view(v,rig,attempt)
                try: msg,gt=node.capture(v['xyz'],v['rpy'])
                except (TimeoutError,RuntimeError) as exc:
                    print('Replacing unsettled capture '+v['id']+': '+str(exc),flush=True); continue
                pose=gt.pose.pose; q=pose.orientation
                qv=np.array([q.x,q.y,q.z]); norm=np.linalg.norm(qv); angle=2*np.arctan2(norm,q.w)
                rot=cv2.Rodrigues(qv*angle/norm if norm else np.zeros(3))[0]
                body=np.eye(4); body[:3,:3]=rot; body[:3,3]=[pose.position.x,pose.position.y,pose.position.z]
                sensor=camera_transform([0,0,0],[0,0,0],rig['cameras']['left']); world_camera=body@sensor
                geom=projected_geometry(points,world_camera,K,msg.width,msg.height,edges)
                if v['positive']==(geom['bbox'] is not None) and (not v['positive'] or (geom['primary'] and geom['angle_bin']==v['angle_bin'])):
                    ok,png=cv2.imencode('.png',node.cv.imgmsg_to_cv2(msg,desired_encoding='bgr8'))
                    if not ok: raise IOError('Cannot encode capture')
                    digest=hashlib.sha256(png.tobytes()).hexdigest()
                    if digest in seen_hashes:
                        print('Replacing repeated rendered image '+v['id'],flush=True); continue
                    break
                print('Replacing ambiguous label '+v['id'],flush=True)
            else: raise RuntimeError('Repeated invalid captures; preserve checkpoint and inspect simulator: '+v['id'])
            image=dest/'images'/v['split']/(v['id']+'.png'); label=dest/'labels'/v['split']/(v['id']+'.txt')
            image.parent.mkdir(parents=True,exist_ok=True); label.parent.mkdir(parents=True,exist_ok=True)
            image.write_bytes(png.tobytes())
            label.write_text(yolo_label(geom['bbox'],msg.width,msg.height))
            record={**v,**geom,'source':'stonefish','sequence':v['group'],'capture_session':session,'stamp':stamp(msg),'pose_stamp':stamp(gt),'pose_time_error_s':abs(stamp(gt)-stamp(msg)),'capture_wall_seconds':node.last_capture_wall,'width':msg.width,'height':msg.height,'requested_xyz':v['xyz'],'requested_rpy':v['rpy'],'world_camera':world_camera.tolist(),'image':str(image.relative_to(dest)),'sha256':digest}
            with manifest.open('a') as f: f.write(json.dumps(record)+'\n')
            done.add(v['id']); seen_hashes.add(digest)
            if len(done)%25==0 or len(done)==1: print(f'Captured {len(done)}/{args.groups*10}',flush=True)
        (dest/'dataset.yaml').write_text('path: '+str(dest.resolve())+'\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: pipe\n')
    finally:
        try:
            if rclpy.ok(): node.peripheral_sensors(True)
        finally: node.destroy_node(); rclpy.try_shutdown()


if __name__=='__main__': main()
