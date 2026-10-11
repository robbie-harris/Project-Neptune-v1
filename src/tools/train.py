#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import platform
import shutil
import hashlib
import sys
import time
import os
os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(__file__).resolve().parents[2]/"outputs/ultralytics"))
import torch
import yaml
from ultralytics import YOLO
from validate_dataset import validate

ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,default=ROOT/'data/orientation'); p.add_argument('--device',default='auto'); p.add_argument('--epochs',type=int)
    p.add_argument('--seed',type=int,default=42); p.add_argument('--name',default='orientation-A-42'); p.add_argument('--config',type=Path,default=ROOT/'config/training.yaml'); args=p.parse_args()
    if Path(args.name).name!=args.name: p.error('Candidate name must be a single directory name')
    dataset=args.data.resolve()
    dataset_report=validate(dataset)
    for split in ['train','val','test']:
        if not any(x.suffix.lower() in ['.png','.jpg','.jpeg'] for x in (dataset/'images'/split).glob('*')): p.error(f'No {split} images: generate the complete dataset first')
    cfg=yaml.safe_load(args.config.read_text()); cfg['seed']=args.seed
    if args.epochs is not None: cfg['epochs']=args.epochs
    device=('mps' if torch.backends.mps.is_available() else 'cpu') if args.device=='auto' else args.device
    if device not in ['mps','cpu'] and not torch.cuda.is_available(): p.error('Requested CUDA device unavailable')
    model_name=cfg.pop('model'); target=ROOT/'models/candidates'/args.name
    if target.exists(): p.error('Candidate already exists; choose a new name')
    target.mkdir(parents=True)
    # Resolve portable data paths on this host, irrespective of container mount.
    local_yaml=target/'dataset-host.yaml'
    local_yaml.write_text(yaml.safe_dump({'path':str(dataset),'train':'images/train','val':'images/val','test':'images/test','names':{0:'pipe'}}))
    pretrained=ROOT/'models/pretrained'; pretrained.mkdir(parents=True,exist_ok=True)
    start=time.time(); model=YOLO(str(pretrained/model_name))
    model.train(data=str(local_yaml),device=device,project=str(ROOT/'outputs/training'),name=args.name,exist_ok=False,**cfg)
    best=Path(model.trainer.best)
    if not best.is_file(): raise RuntimeError('Training did not produce best.pt')
    shutil.copy2(best,target/'best.pt')
    import ultralytics, cv2, numpy
    record={'device':device,'platform':platform.platform(),'machine':platform.machine(),'python':sys.version,'torch':torch.__version__,'ultralytics':ultralytics.__version__,'opencv':cv2.__version__,'numpy':numpy.__version__,'seconds':time.time()-start,'settings':cfg,'model':model_name,'dataset':str(dataset),'weights':str(target/'best.pt'),'dataset_validation':dataset_report,'resolved_training_arguments':vars(model.trainer.args),
        'weights_sha256':hashlib.sha256((target/'best.pt').read_bytes()).hexdigest(),
        'optimizer_class':type(model.trainer.optimizer).__name__}
    # Ultralytics keeps the complete resolved argument set with the run artifacts.
    shutil.copy2(Path(model.trainer.save_dir)/'args.yaml',target/'resolved-training.yaml')
    (target/'training.json').write_text(json.dumps(record,indent=2)); print(json.dumps(record,indent=2))

if __name__=='__main__': main()
