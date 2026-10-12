#!/usr/bin/env python3
"""Multiclass held-out evaluation; threshold selection restricted to validation."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/neptune_perception'))
from neptune_perception.backends import RoboflowBackend
from inspection_dataset import audit,CLASSES
from geometry import iou

def summarize(rows,confidence):
    stats={c:{'targets':0,'hits':0} for c in CLASSES};slices=defaultdict(lambda:{'targets':0,'hits':0})
    small=defaultdict(lambda:{'targets':0,'hits':0});confusion=defaultdict(int);absent=fp=0
    for r in rows:
        predictions=[d for d in r['predictions'] if d['confidence']>=confidence];truth=r['boxes'];used=set()
        if not truth:absent+=1;fp+=bool(predictions)
        # Match same-class overlaps once; report wrong-class confusion separately.
        pairs=sorted([(iou(t['bbox'],d['bbox']),i,j) for i,t in enumerate(truth) for j,d in enumerate(predictions) if t['class']==d['class']],reverse=True)
        matched={}
        for overlap,i,j in pairs:
            if overlap>=.5 and i not in matched and j not in used:matched[i]=j;used.add(j)
        for i,t in enumerate(truth):
            hit=i in matched and predictions[matched[i]]['class']==t['class']
            predicted=predictions[matched[i]]['class'] if i in matched else 'miss'
            if i not in matched:
                wrong=[(iou(t['bbox'],d['bbox']),d['class']) for j,d in enumerate(predictions) if j not in used and d['class']!=t['class']]
                if wrong and max(wrong)[0]>=.5: predicted=max(wrong)[1]
            confusion[t['class']+'->'+predicted]+=1
            if not t['eligible']:
                small[t['class']]['targets']+=1;small[t['class']]['hits']+=hit;continue
            keys=[t['class']+':water:'+r['optics']['water'],t['class']+':natural:'+str(r['optics']['natural']),t['class']+':lamps:'+str(r['optics']['lamps']),t['class']+':particles:'+str(r['optics']['particles']),t['class']+':roll:'+str(int((np.degrees(r['rpy'][0])+180)//30))]
            for key in keys:slices[key]['targets']+=1;slices[key]['hits']+=hit
            if r['optics']['water'] in ('clear','moderate'):
                stats[t['class']]['targets']+=1;stats[t['class']]['hits']+=hit
    def ratios(values):return {k:{**v,'recall':v['hits']/v['targets'] if v['targets'] else None} for k,v in values.items()}
    stats=ratios(stats);fpr=fp/absent if absent else None
    return {'confidence':confidence,'per_class_clear_moderate':stats,'negative_frames':absent,'false_positive_frames':fp,'negative_frame_fpr':fpr,
            'slices':ratios(slices),'small_targets':ratios(small),'class_confusion':dict(confusion),
            'accuracy_passed':all(s['recall'] is not None and s['recall']>=.95 for s in stats.values()) and fpr is not None and fpr<=.05}

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--model-id',required=True);p.add_argument('--training-id',required=True)
    p.add_argument('--api-key-file',type=Path,default=ROOT/'.secrets/roboflow_api_key');p.add_argument('--inference-url',default='http://localhost:9001')
    p.add_argument('--split',choices=['val','test'],default='test');p.add_argument('--confidence',type=float);p.add_argument('--select-confidence',action='store_true');p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.select_confidence and args.split!='val':p.error('Select threshold on validation only')
    if not args.select_confidence and args.confidence is None:p.error('Supply frozen validation-selected confidence')
    dataset=audit(args.data,full=True);records=[json.loads(l) for l in (args.data/'manifest.jsonl').read_text().splitlines() if json.loads(l)['split']==args.split]
    model=RoboflowBackend(args.inference_url,args.model_id,str(args.api_key_file));model.load();rows=[];latencies=[]
    model.infer(cv2.imread(str(args.data/records[0]['image'])),.01)
    for r in records:
        frame=cv2.imread(str(args.data/r['image']))
        if frame is None:raise ValueError('Cannot decode capture')
        start=time.perf_counter();predictions=model.infer(frame,.01);latencies.append((time.perf_counter()-start)*1000)
        rows.append({**r,'predictions':predictions})
        if len(rows)%100==0:print(f'Evaluated {len(rows)}/{len(records)}',flush=True)
    if args.select_confidence:
        sweep=[summarize(rows,float(c)) for c in np.arange(.05,.81,.05)]
        feasible=[s for s in sweep if s['negative_frame_fpr'] is not None and s['negative_frame_fpr']<=.05]
        if not feasible:raise RuntimeError('No validation threshold satisfies negative-frame gate')
        report=max(feasible,key=lambda s:(min(v['recall'] or 0 for v in s['per_class_clear_moderate'].values()),-s['confidence']))
    else:report=summarize(rows,args.confidence)
    report.update(model_id=args.model_id,training_id=args.training_id,split=args.split,images=len(rows),dataset=dataset,
                  latency_ms_mean=float(np.mean(latencies)),latency_ms_p95=float(np.percentile(latencies,95)),inference_fps=1000/float(np.mean(latencies)),
                  hardware={'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor()},
                  promotion_complete=False,live_runtime_gate='Must be measured separately with complete simulator running')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    args.output.with_suffix('.predictions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
