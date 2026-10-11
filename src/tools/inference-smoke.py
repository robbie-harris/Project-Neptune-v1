#!/usr/bin/env python3
"""Local model smoke check; never sends camera pixels to a hosted endpoint."""
import argparse
import json
from pathlib import Path
import sys
import time
import cv2
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/neptune_perception'))
from neptune_perception.backends import RoboflowBackend, annotate

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--image',type=Path,required=True)
    p.add_argument('--model-id',default='projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t2')
    p.add_argument('--api-url',default='http://localhost:9001')
    p.add_argument('--key-file',default=str(ROOT/'.secrets/roboflow_api_key'))
    p.add_argument('--confidence',type=float,default=.25)
    p.add_argument('--output',type=Path,default=ROOT/'outputs/inference-smoke.jpg')
    a=p.parse_args(); frame=cv2.imread(str(a.image))
    if frame is None: p.error('Cannot decode input image')
    model=RoboflowBackend(a.api_url,a.model_id,a.key_file)
    model.load(); model.infer(frame,a.confidence)
    start=time.perf_counter(); detections=model.infer(frame,a.confidence)
    report={'model_id':a.model_id,'image':str(a.image),'confidence':a.confidence,'latency_ms':(time.perf_counter()-start)*1000,'detections':detections,'local_inference':True}
    a.output.parent.mkdir(parents=True,exist_ok=True); cv2.imwrite(str(a.output),annotate(frame,detections))
    a.output.with_suffix('.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
