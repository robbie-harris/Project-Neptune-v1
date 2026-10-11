#!/usr/bin/env python3
"""Frozen-viewpoint evaluation; confidence is selected on validation only."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import platform
import time
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/neptune_perception'))
from neptune_perception.backends import RoboflowBackend
os.environ.setdefault('YOLO_CONFIG_DIR',str(ROOT/'outputs/ultralytics'))
import cv2
import numpy as np
import torch
import ultralytics
from ultralytics import YOLO
from geometry import iou
from validate_dataset import validate


def summarize(rows,confidence,orientation=True):
    groups=defaultdict(lambda:{'targets':0,'hits':0}); negatives=false_frames=targets=hits=small=small_hits=0
    for r in rows:
        boxes=[b for b,s in zip(r['predicted_boxes'],r['scores']) if s>=confidence]; truth=r['truth_boxes']
        if not truth:
            negatives+=1; false_frames+=bool(boxes); continue
        available=set(range(len(boxes))); matched=0
        for gt in truth:
            candidates=[(iou(gt,boxes[j]),j) for j in available]
            if candidates and max(candidates)[0]>=.5:
                available.remove(max(candidates)[1]); matched+=1
        if not r['primary']:
            small+=len(truth); small_hits+=matched; continue
        targets+=len(truth); hits+=matched
        for key in ['angle_bin','partial','distance_bin']:
            value=r.get(key)
            if value is not None:
                g=groups[f'{key}:{value}']; g['targets']+=len(truth); g['hits']+=matched
    recall=hits/targets if targets else None; fpr=false_frames/negatives if negatives else None
    slices={k:{**v,'recall':v['hits']/v['targets']} for k,v in sorted(groups.items())}
    angle_ok=all(v['recall']>=.9 for k,v in slices.items() if k.startswith('angle_bin:'))
    passed=recall is not None and recall>=(.95 if orientation else .9) and fpr is not None and fpr<=.05 and angle_ok
    latency=[r['latency_ms'] for r in rows]
    return {'confidence':confidence,'targets':targets,'hits':hits,'positive_frames':sum(bool(r['truth_boxes']) and r['primary'] for r in rows),'negative_frames':negatives,'false_positive_frames':false_frames,'recall_iou_0_5':recall,'negative_frame_fpr':fpr,'slices':slices,'small_targets':{'targets':small,'hits':small_hits,'recall':small_hits/small if small else None},'latency_ms_mean':float(np.mean(latency)),'latency_ms_p95':float(np.percentile(latency,95)),'inference_fps':1000/float(np.mean(latency)),'passed':passed}


def predictions(model,data,records,device):
    rows=[]
    for r in records:
        path=data/r['image']; label=data/'labels'/r['split']/(path.stem+'.txt'); frame=cv2.imread(str(path))
        if frame is None: raise ValueError('Cannot decode '+str(path))
        height,width=frame.shape[:2]; truths=[]
        for line in label.read_text().splitlines():
            if not line.strip(): continue
            cls,cx,cy,w,h=map(float,line.split())
            if cls!=0: raise ValueError('Unexpected class')
            truths.append([(cx-w/2)*width,(cy-h/2)*height,(cx+w/2)*width,(cy+h/2)*height])
        start=time.perf_counter()
        if isinstance(model,RoboflowBackend):
            items=model.infer(frame,.01); boxes=[d['bbox'] for d in items]; scores=[d['confidence'] for d in items]
        else:
            result=model.predict(frame,imgsz=640,conf=.01,device=device,verbose=False)[0]
            boxes=result.boxes.xyxy.cpu().tolist(); scores=result.boxes.conf.cpu().tolist()
            if device.type=='mps': torch.mps.synchronize()
        latency=(time.perf_counter()-start)*1000; xyz=r.get('requested_xyz')
        distance=float(np.linalg.norm(np.asarray(xyz)-[4.4,0,1.5])) if xyz is not None else None
        rows.append({'id':r['id'],'source':r.get('source','stonefish'),'image':r['image'],'primary':r.get('primary',True),'angle_bin':r.get('angle_bin'),'partial':r.get('partial'),'distance_bin':('near' if distance<3 else 'mid' if distance<6 else 'far') if distance is not None else None,'truth_boxes':truths,'predicted_boxes':boxes,'scores':scores,'latency_ms':latency})
        if len(rows)%100==0: print(f'Evaluated {len(rows)}/{len(records)} frames',flush=True)
    return rows


def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,default=ROOT/'data/orientation'); p.add_argument('--weights',type=Path,default=ROOT/'models/pipe/best.pt'); p.add_argument('--device',default='cpu'); p.add_argument('--threads',type=int,default=2); p.add_argument('--training-id',help='Actual Roboflow training job ID for repeat reports'); p.add_argument('--split',choices=['train','val','test'],default='test'); p.add_argument('--confidence',type=float,default=.25); p.add_argument('--select-confidence',action='store_true'); p.add_argument('--diagnostic',action='store_true'); p.add_argument('--output',type=Path,default=ROOT/'outputs/evaluation.json')
    p.add_argument('--backend',choices=['ultralytics','roboflow'],default='ultralytics'); p.add_argument('--inference-url',default='http://localhost:9001'); p.add_argument('--model-id'); p.add_argument('--api-key-file',default=str(ROOT/'.secrets/roboflow_api_key')); args=p.parse_args()
    if args.select_confidence and args.split!='val': p.error('Confidence selection must use val, never test')
    settings=json.loads((args.data/'generation.json').read_text()) if (args.data/'generation.json').exists() else {}
    dataset_report=validate(args.data) if not args.diagnostic else {'diagnostic_only':True,'generalization_claim':False}
    records=[json.loads(s) for s in (args.data/'manifest.jsonl').read_text().splitlines() if json.loads(s)['split']==args.split]
    if not records: p.error('No images in requested split')
    device=torch.device(args.device)
    if device.type=='cpu': torch.set_num_threads(max(1,args.threads))
    if args.backend=='roboflow':
        if not args.model_id: p.error('--model-id is required for Roboflow')
        model=RoboflowBackend(args.inference_url,args.model_id,args.api_key_file); model.load()
        model.infer(cv2.imread(str(args.data/records[0]['image'])),.01)
    else:
        model=YOLO(str(args.weights))
        if model.names!={0:'pipe'}: p.error('Expected single pipe class')
        model.predict(str(args.data/records[0]['image']),device=device,imgsz=640,verbose=False)
    rows=predictions(model,args.data,records,device); confidence=args.confidence; orientation=any(record.get('angle_bin') is not None for record in records)
    if args.select_confidence:
        sweep=[summarize(rows,float(c),orientation) for c in np.arange(.05,.81,.05)]
        feasible=[r for r in sweep if r['negative_frame_fpr'] is not None and r['negative_frame_fpr']<=.05]
        if not feasible: raise RuntimeError('No validation confidence meets <=5% false-positive frames')
        best=max(feasible,key=lambda r:(r['recall_iou_0_5'] or 0,-r['confidence'])); confidence=best['confidence']
    report=summarize(rows,confidence,orientation)
    report.update({'split':args.split,'training_id':args.training_id,'platform':platform.platform(),'device':str(device),'cpu_threads':torch.get_num_threads(),'backend':args.backend,'model_id':args.model_id if args.backend=='roboflow' else None,'weights':str(args.weights) if args.backend=='ultralytics' else None,'weights_sha256':hashlib.sha256(args.weights.read_bytes()).hexdigest() if args.backend=='ultralytics' else None,'images':len(rows),'dataset_validation':dataset_report,'diagnostic_only':args.diagnostic,'confidence_selection_split':'val' if args.select_confidence else None,'versions':{'torch':torch.__version__,'ultralytics':ultralytics.__version__,'opencv':cv2.__version__,'numpy':np.__version__},'timing_scope':'Warm pixel inference, preprocessing, NMS and device synchronization; disk loading and initial warmup excluded.' if args.backend=='ultralytics' else 'Warm local HTTP round trip including lossless PNG encoding, transport, server inference and decoding; file loading and initial model download excluded.'})
    if args.select_confidence: report['confidence_sweep']=sweep
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2)); args.output.with_suffix('.frames.json').write_text(json.dumps(rows)); print(json.dumps(report,indent=2)); raise SystemExit(0 if args.diagnostic or report['passed'] else 1)


if __name__=='__main__': main()
