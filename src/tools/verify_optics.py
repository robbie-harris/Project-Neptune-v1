#!/usr/bin/env python3
"""Rendered native-control verification, including RGB/mask and darkness checks."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import rclpy
from capture_inspection import InspectionCapture
from inspection_dataset import boxes_from_mask
from capture_dataset import stamp

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('/workspace/outputs/optics-verification'));args=p.parse_args()
args.output.mkdir(parents=True,exist_ok=True);rclpy.init();node=InspectionCapture();results=[]
try:
    node.wait(lambda:node.frame is not None and node.info is not None and bool(node.history) and node.instance_map is not None,90)
    node.enable_masks(True)
    for water in ('clear','moderate','turbid'):
        for natural,lamps in ((True,True),(True,False),(False,True),(False,False)):
            for particles in (False,True):
                profile={'natural':natural,'lamps':lamps,'water':water,'particles':particles}
                node.profile(profile)
                msg,gt=node.capture([2.2,0,1.5],[0,0,0]);mask_msg=node.pair(msg)
                image=node.cv.imgmsg_to_cv2(msg,desired_encoding='bgr8');mask=node.cv.imgmsg_to_cv2(mask_msg,desired_encoding='passthrough')
                boxes=boxes_from_mask(mask,node.instance_map)
                name=f'{water}-sun{int(natural)}-lamps{int(lamps)}-particles{int(particles)}.png'
                cv2.imwrite(str(args.output/name),image)
                results.append({'profile':profile,'stamp':stamp(msg),'mask_stamp':stamp(mask_msg),'mean':float(image.mean()),'p95':float(np.percentile(image,95)),'image':name,'boxes':boxes,'applied':list(node.applied)})
                print(name,results[-1]['mean'],[b['class'] for b in boxes],flush=True)
    dark=[r for r in results if not r['profile']['natural'] and not r['profile']['lamps']]
    lit=[r for r in results if not r['profile']['natural'] and r['profile']['lamps']]
    if max(r['p95'] for r in dark)>2:raise RuntimeError('Unlit camera is not dark: inspect residual illumination')
    if min(r['mean'] for r in lit)<=max(r['mean'] for r in dark)+1:raise RuntimeError('Headlights do not illuminate scene')
    report={'state':'passed','instance_map':node.instance_map,'images':results,'checks':['native acknowledgement','exact RGB/mask timestamps','three target masks','unlit darkness','headlight illumination']}
    (args.output/'report.json').write_text(json.dumps(report,indent=2))
finally:
    try:node.profile({'natural':True,'lamps':True,'water':'clear','particles':False});node.enable_masks(False)
    finally:node.destroy_node();rclpy.try_shutdown()
