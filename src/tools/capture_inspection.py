#!/usr/bin/env python3
"""Native RGB/instance-mask capture. No projected boxes or geometry in inference."""
import argparse
from collections import deque
import hashlib
import json
import math
import time
from pathlib import Path
import uuid
import cv2
import numpy as np
import rclpy
from rclpy.qos import QoSProfile,DurabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String,Float64MultiArray
from std_srvs.srv import SetBool
from capture_dataset import Capture,stamp
from inspection_dataset import boxes_from_mask,labels,audit,CLASSES,viewpoints
from geometry import rotation_rpy

PRESETS={'clear':.02,'moderate':.25,'turbid':.65}



def optical_variants(group):
    # 3 illumination combinations x 3 Jerlov presets x particles, cycled between groups.
    combinations=[{'natural':n,'lamps':l,'water':w,'particles':p} for n,l in ((True,True),(True,False),(False,True)) for w in PRESETS for p in (False,True)]
    return [combinations[(group*10+i)%len(combinations)] for i in range(10)]

class InspectionCapture(Capture):
    def __init__(self):
        super().__init__(); self.masks=deque(maxlen=50);self.rgb=deque(maxlen=50);self.instance_map=None;self.applied=None;self.request_id=int(uuid.uuid4().hex[:9],16)*10000
        self.create_subscription(Image,'/neptune/camera/left/image_color',lambda m:self.rgb.append(m),10)
        self.create_subscription(Image,'/neptune/capture/instances/image_raw',lambda m:self.masks.append(m),10)
        self.create_subscription(String,'/neptune/capture/instance_map',self.mapping,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(Float64MultiArray,'/neptune/optics/applied',lambda m:setattr(self,'applied',m.data),10)
        self.optics=self.create_publisher(Float64MultiArray,'/neptune/optics/request',10)
        self.mask_service=self.create_client(SetBool,'/neptune/capture/instances/set_enabled')
    def mapping(self,msg):
        self.instance_map=json.loads(msg.data)
        if len(self.instance_map)!=3: raise RuntimeError('Scene does not contain three distinct target instances')
    def enable_masks(self,enabled):
        if not self.mask_service.wait_for_service(timeout_sec=20): raise RuntimeError('Capture-only instance camera unavailable')
        req=SetBool.Request();req.data=enabled;f=self.mask_service.call_async(req);self.wait(f.done)
        if not f.result().success: raise RuntimeError('Cannot enable instance camera')
    def profile(self,p):
        self.request_id+=1; values=[float(self.request_id),float(p['natural']),float(p['lamps']),PRESETS[p['water']],float(p['particles'])]
        self.optics.publish(Float64MultiArray(data=values));self.wait(lambda:self.applied is not None and self.applied[0]==self.request_id,10)
        if list(self.applied)!=values+[1.]: raise RuntimeError('Native optical update failed')
        after=stamp(self.frame)+.3
        self.wait(lambda:stamp(self.frame)>after)
    def overview(self,enabled):
        client=self.create_client(SetBool,'/neptune/sensors/TankOverview/set_enabled')
        if not client.wait_for_service(timeout_sec=20):raise RuntimeError('Overview enable service unavailable')
        req=SetBool.Request();req.data=enabled;future=client.call_async(req);self.wait(future.done)
        if not future.result().success:raise RuntimeError('Cannot toggle overview')
        self.destroy_client(client)
    def pose_matches(self,gt,xyz,rpy):
        p=gt.pose.pose.position;q=gt.pose.pose.orientation
        rv,_=cv2.Rodrigues(rotation_rpy(rpy));angle=np.linalg.norm(rv)
        requested=np.r_[rv[:,0]/angle*np.sin(angle/2),np.cos(angle/2)] if angle else np.array([0.,0.,0.,1.])
        return np.linalg.norm(np.array([p.x,p.y,p.z])-xyz)<.03 and abs(float(np.array([q.x,q.y,q.z,q.w])@requested))>.999
    def capture(self,xyz,rpy,reuse=False):
        started=time.monotonic();self.last_capture_mode='respawn'
        if reuse and self.history and self.pose_matches(self.history[-1],xyz,rpy):
            first=self.frame;self.last_capture_mode='reuse'
        else:first,_=super().capture(xyz,rpy)
        def matches():
            times={stamp(m) for m in self.masks}
            return [m for m in self.rgb if stamp(m)>=stamp(first) and stamp(m) in times]
        self.wait(lambda:bool(matches()),10)
        msg=matches()[0]
        self.wait(lambda:any(abs(stamp(gt)-stamp(msg))<=.05 for gt in self.history),5)
        gt=min(self.history,key=lambda m:abs(stamp(m)-stamp(msg)))
        if self.last_capture_mode=='reuse' and not self.pose_matches(gt,xyz,rpy):
            return self.capture(xyz,rpy,reuse=False)
        self.last_capture_wall=time.monotonic()-started
        return msg,gt
    def pair(self,msg):
        self.wait(lambda:any(m.header.stamp==msg.header.stamp for m in self.masks),10)
        return next(m for m in self.masks if m.header.stamp==msg.header.stamp)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('/workspace/data/inspection-pilot'))
    p.add_argument('--limit',type=int);p.add_argument('--groups',type=int,default=900);p.add_argument('--seed',type=int,default=42);p.add_argument('--resume',action='store_true')
    p.add_argument('--partition-scenes',action='store_true');p.add_argument('--scene-variant',type=int,default=0);p.add_argument('--group-start',type=int,default=0);p.add_argument('--group-end',type=int)
    p.add_argument('--group-ids',help='Comma-separated preselected whole viewpoint groups')
    p.add_argument('--reuse-settled-pose',action='store_true');p.add_argument('--disable-overview',action='store_true')
    args=p.parse_args();selected_groups=set(map(int,args.group_ids.split(','))) if args.group_ids else None
    dest=args.output;dest.mkdir(parents=True,exist_ok=True);manifest=dest/'manifest.jsonl'
    if (dest/'sealed_dataset.json').exists():p.error('Dataset is sealed; capture new experiments in a separate directory')
    if manifest.exists() and not args.resume: p.error('Dataset exists; use --resume')
    records=[json.loads(l) for l in manifest.read_text().splitlines()] if manifest.exists() else []
    existing_scenes={}
    for record in records:
        if record['group'] in existing_scenes and existing_scenes[record['group']]!=record['scene_variant']:raise ValueError('Scene variation leaked inside a group')
        existing_scenes[record['group']]=record['scene_variant']
    done={r['id'] for r in records};hashes={r['sha256'] for r in records};session=uuid.uuid4().hex
    settings={'schema':'inspection-v1','groups':args.groups,'seed':args.seed,'classes':list(CLASSES),'sensor_errors':False,'instance_labels':'visible native uint16 masks','optical_presets':PRESETS,'asset_sources':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__).resolve().parents[2]/'Simulation/assets').glob('*.obj') if f.name in ('valve.obj','flange.obj')},'scene_sources':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__).resolve().parents[2]/'Simulation/scenarios').glob('inspection*.scn')}}
    generation=dest/'generation.json'
    if generation.exists() and json.loads(generation.read_text())!=settings: p.error('Generation settings changed')
    generation.write_text(json.dumps(settings,indent=2))
    rclpy.init();node=InspectionCapture()
    try:
        node.wait(lambda:node.info is not None and node.frame is not None and bool(node.history) and node.instance_map is not None,90)
        node.enable_masks(True);node.peripheral_sensors(False)
        if args.disable_overview:node.overview(False)
        for view in viewpoints(args.groups,args.seed):
            g=view['group']
            if selected_groups is not None and g not in selected_groups:continue
            if args.partition_scenes and existing_scenes.get(g,(g//4)%4)!=args.scene_variant: continue
            if g<args.group_start or (args.group_end is not None and g>=args.group_end):continue
            group_xyz=np.array(view['xyz']);group_rpy=np.array(view['rpy'])
            # A group owns one scene variant; never distribute variants across splits.
            for variant,optics in enumerate(optical_variants(g)):
                if args.limit and len(done)>=args.limit:
                    (dest/'dataset.yaml').write_text(f'path: {dest.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames: [pipe, valve, flange]\n')
                    report=audit(dest);(dest/'audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
                    return
                key=f'i{g:04d}_v{variant:02d}'
                if key in done: continue
                profile_started=time.monotonic();node.profile(optics);profile_seconds=time.monotonic()-profile_started
                capture_started=time.monotonic()
                for attempt in range(12):
                    xyz=group_xyz.copy();rpy=group_rpy.copy()
                    if attempt:
                        # Replacement view remains in the original group/split.
                        xyz[0]-=min(.15*attempt,1.)
                        target=np.array([4.4,0,1.5])-xyz
                        rpy[1]=-math.atan2(target[2],np.linalg.norm(target[:2]));rpy[2]=math.atan2(target[1],target[0])+(math.pi if view['negative'] else 0)
                    try:
                        msg,gt=node.capture(xyz,rpy,reuse=args.reuse_settled_pose and variant>0 and attempt==0);mask_msg=node.pair(msg)
                        mask=node.cv.imgmsg_to_cv2(mask_msg,desired_encoding='passthrough')
                        boxes=boxes_from_mask(mask,node.instance_map)
                        if view['negative'] != (not boxes): continue
                        if view['coverage_target'] and view['coverage_target'] not in {b['class'] for b in boxes}: continue
                        if boxes and not all(b['eligible'] for b in boxes): continue
                        frame=node.cv.imgmsg_to_cv2(msg,desired_encoding='bgr8')
                        # Completely dark/ambiguous frames are diagnostic, never negatives.
                        if frame.mean()<1 or (boxes and max(float(frame[b['bbox'][1]:b['bbox'][3],b['bbox'][0]:b['bbox'][2]].std()) for b in boxes)<1):
                            diagnostic=dest/'diagnostics';diagnostic.mkdir(exist_ok=True);cv2.imwrite(str(diagnostic/(key+f'-a{attempt}.png')),frame);continue
                        ok,png=cv2.imencode('.png',frame);ok_mask,png_mask=cv2.imencode('.png',mask)
                        if not(ok and ok_mask):raise IOError('Cannot encode images')
                        digest=hashlib.sha256(png.tobytes()).hexdigest()
                        if digest in hashes:continue
                        break
                    except (TimeoutError,RuntimeError) as exc:
                        print(f'Replacing {key} attempt {attempt}: {exc}',flush=True)
                else: raise RuntimeError('Repeated invalid captures: '+key)
                group_xyz=xyz.copy();group_rpy=rpy.copy()
                paths={kind:dest/kind/view['split']/(key+ext) for kind,ext in [('images','.png'),('labels','.txt'),('masks','.png')]}
                for path in paths.values():path.parent.mkdir(parents=True,exist_ok=True)
                paths['images'].write_bytes(png.tobytes());paths['masks'].write_bytes(png_mask.tobytes())
                paths['labels'].write_text(labels(boxes,msg.width,msg.height))
                record={**view,'id':key,'schema':'inspection-v1','source':'stonefish','sequence':g,'scene_variant':args.scene_variant,
                        'scene':f'inspection_variant_{args.scene_variant}' if args.partition_scenes else 'inspection_tank','scene_sources':settings['scene_sources'],'asset_sources':settings['asset_sources'],'capture_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'capture_session':session,'optics':optics,'instance_map':node.instance_map,'boxes':boxes,
                        'stamp':stamp(msg),'mask_stamp':stamp(mask_msg),'pose_stamp':stamp(gt),
                        'ground_truth_xyz':[gt.pose.pose.position.x,gt.pose.pose.position.y,gt.pose.pose.position.z],
                        'ground_truth_quaternion':[gt.pose.pose.orientation.x,gt.pose.pose.orientation.y,gt.pose.pose.orientation.z,gt.pose.pose.orientation.w],
                        'width':msg.width,'height':msg.height,
                        'image':str(paths['images'].relative_to(dest)),'label':str(paths['labels'].relative_to(dest)),
                        'mask':str(paths['masks'].relative_to(dest)),'sha256':digest,'mask_sha256':hashlib.sha256(png_mask.tobytes()).hexdigest(),
                        'actual_requested_xyz':xyz.tolist(),'actual_requested_rpy':rpy.tolist(),'capture_wall_seconds':node.last_capture_wall,'capture_mode':node.last_capture_mode,'profile_wall_seconds':profile_seconds,'attempts':attempt+1,'acceptance_wall_seconds':time.monotonic()-capture_started,'overview_disabled':args.disable_overview}
                with manifest.open('a') as f:f.write(json.dumps(record)+'\n')
                done.add(key);hashes.add(digest)
                print(f'Captured {len(done)}/{args.groups*10}: {key} '+','.join(b['class'] for b in boxes),flush=True)
        (dest/'dataset.yaml').write_text(f'path: {dest.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames: [pipe, valve, flange]\n')
        report=audit(dest);(dest/'audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    finally:
        try:
            node.enable_masks(False);node.peripheral_sensors(True)
            if args.disable_overview:node.overview(True)
        finally:node.destroy_node();rclpy.try_shutdown()

if __name__=='__main__': main()
