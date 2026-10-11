#!/usr/bin/env python3
"""Fail closed on incomplete datasets or split leakage before training."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


def validate(directory,expected=None):
    directory=Path(directory); path=directory/'manifest.jsonl'
    records=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    generation=directory/'generation.json'
    settings=json.loads(generation.read_text()) if generation.exists() else {}
    if expected is None: expected=settings.get('target_images',1000)
    ids=[r['id'] for r in records]
    if len(records)!=expected or len(set(ids))!=expected: raise ValueError(f'Expected {expected} unique captures, got {len(records)} records / {len(set(ids))} IDs')
    groups=defaultdict(set); hashes=defaultdict(set); counts=Counter(); negatives=Counter(); bins=defaultdict(Counter)
    for r in records:
        groups[(r.get('source','stonefish'),str(r['group']))].add(r['split']); counts[r['split']]+=1
        image=directory/r['image']; label=directory/'labels'/r['split']/(image.stem+'.txt')
        if not image.is_file() or not label.is_file(): raise ValueError(f'Missing image/label for {r["id"]}')
        content=label.read_text().strip()
        if content:
            for line in content.splitlines():
                values=list(map(float,line.split()))
                if len(values)!=5 or values[0]!=0 or not all(math.isfinite(v) and 0<=v<=1 for v in values[1:]) or min(values[3:])<=0: raise ValueError('Invalid YOLO label: '+str(label))
                _,cx,cy,w,h=values
                if cx-w/2<-.0000001 or cy-h/2<-.0000001 or cx+w/2>1.0000001 or cy+h/2>1.0000001: raise ValueError('Box exceeds image: '+str(label))
            if r['bbox'] is None: raise ValueError('Manifest/label disagreement')
        else:
            negatives[r['split']]+=1
            if r['bbox'] is not None: raise ValueError('Empty label for visible target')
        digest=hashlib.sha256(image.read_bytes()).hexdigest()
        if r.get('sha256',digest)!=digest: raise ValueError('Image hash mismatch: '+str(image))
        hashes[digest].add(r['split'])
        if r.get('angle_bin') is not None: bins[r['split']][r['angle_bin']]+=1
    if any(len(splits)!=1 for splits in groups.values()): raise ValueError('Viewpoint group leaks between splits')
    if any(len(s)>1 for s in hashes.values()): raise ValueError('Duplicate image leaks between splits')
    required=settings.get('split_counts',{'train':700,'val':150,'test':150} if expected==1000 else None)
    if required and dict(counts)!=required: raise ValueError(f'Wrong split counts: {dict(counts)}')
    if any(negatives[k]==0 or negatives[k]==counts[k] for k in counts): raise ValueError('Each split needs positive and negative frames')
    return {'images':len(records),'groups':len(groups),'split_counts':dict(counts),'negative_counts':dict(negatives),'angle_bins':{k:dict(v) for k,v in bins.items()},'duplicate_images':len(records)-len(hashes),'manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,default=Path('data/pipe')); args=p.parse_args()
    result=validate(args.data); (args.data/'validation.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))

if __name__=='__main__': main()
