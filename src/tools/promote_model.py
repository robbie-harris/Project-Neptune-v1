#!/usr/bin/env python3
"""Promote a verified offline checkpoint; preserve the previous active model."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import yaml

ROOT=Path(__file__).resolve().parents[2]


def check_candidate(weights,evaluation,live,baseline,validation):
    digest=hashlib.sha256(weights.read_bytes()).hexdigest()
    if validation.get('weights_sha256')!=digest or validation.get('split')!='val' or validation.get('confidence_selection_split')!='val' or validation.get('diagnostic_only'):
        raise ValueError('Candidate requires confidence selected on full validation data for these exact weights')
    if validation.get('confidence')!=evaluation.get('confidence'):
        raise ValueError('Test confidence differs from validation selection')
    dataset_hash=validation.get('dataset_validation',{}).get('manifest_sha256')
    if not dataset_hash or dataset_hash!=evaluation.get('dataset_validation',{}).get('manifest_sha256'):
        raise ValueError('Validation and test reports must share the frozen dataset manifest')
    if evaluation.get('weights_sha256')!=digest or not evaluation.get('passed') or evaluation.get('diagnostic_only') or evaluation.get('split')!='test': raise ValueError('Candidate requires a passing held-out test report for these exact weights')
    if evaluation.get('recall_iou_0_5',0)<.95 or evaluation.get('negative_frame_fpr',1)>.05: raise ValueError('Acceptance targets failed')
    if not all(f'angle_bin:{i}' in evaluation.get('slices',{}) and evaluation['slices'][f'angle_bin:{i}']['recall']>=.9 for i in range(6)): raise ValueError('All six angle bins require >=90% recall')
    if not live.get('passed') or live.get('detector',{}).get('state')!='ready': raise ValueError('Candidate has not passed live ROS verification')
    if live.get('weights_sha256')!=digest: raise ValueError('Live report is not bound to these exact weights')
    if live.get('detector',{}).get('confidence_threshold')!=evaluation.get('confidence'): raise ValueError('Live and evaluated confidence thresholds differ')
    old=baseline.get('wall_rates_hz',{}).get('annotated',0); new=live.get('wall_rates_hz',{}).get('annotated',0)
    if old<=0 or new<old*.9: raise ValueError('Live annotated frame rate regressed by more than10%')
    if live.get('sampled_inference_latency_ms',{}).get('p95',float('inf'))>baseline.get('sampled_inference_latency_ms',{}).get('p95',0)*1.1: raise ValueError('Live p95 latency regressed by more than10%')
    old_gui=baseline.get('gui_fresh_fps_median',0); new_gui=live.get('gui_fresh_fps_median',0)
    if old_gui<=0 or new_gui<old_gui*.9 or not live.get('gui_fresh_fps_samples'):
        raise ValueError('Measured fresh GUI FPS is missing or regressed by more than10%')
    return digest


def main():
    p=argparse.ArgumentParser(); p.add_argument('--weights',type=Path,required=True); p.add_argument('--validation',type=Path,required=True); p.add_argument('--evaluation',type=Path,required=True); p.add_argument('--live',type=Path,required=True); p.add_argument('--baseline-live',type=Path,required=True); args=p.parse_args()
    evaluation=json.loads(args.evaluation.read_text()); live=json.loads(args.live.read_text()); baseline=json.loads(args.baseline_live.read_text())
    validation=json.loads(args.validation.read_text())
    digest=check_candidate(args.weights,evaluation,live,baseline,validation)
    from ultralytics import YOLO
    if YOLO(str(args.weights)).names!={0:'pipe'}: raise ValueError('Wrong checkpoint classes')
    active=ROOT/'models/pipe/best.pt'; rollback=ROOT/'models/rollback'/f'previous-{int(time.time())}.pt'; rollback.parent.mkdir(parents=True,exist_ok=True)
    if active.exists(): shutil.copy2(active,rollback)
    staged=active.with_suffix('.tmp'); shutil.copy2(args.weights,staged); staged.replace(active)
    config=ROOT/'config/detector.yaml'; values=yaml.safe_load(config.read_text()); values['pipe_detector']['ros__parameters']['confidence']=evaluation['confidence']; config.write_text(yaml.safe_dump(values,sort_keys=False))
    (active.parent/'promotion.json').write_text(json.dumps({'weights_sha256':digest,'candidate':str(args.weights),'validation':str(args.validation),'evaluation':str(args.evaluation),'live':str(args.live),'baseline_live':str(args.baseline_live),'rollback':str(rollback),'confidence':evaluation['confidence']},indent=2))
    print('Verified candidate promoted. Rebuild/restart simulator to apply configuration.')


if __name__=='__main__': main()
