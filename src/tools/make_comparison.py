#!/usr/bin/env python3
"""Build local A/B datasets with identical frozen simulator validation/test views."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
from validate_dataset import validate


def build(sim,cou,dest):
    sim_report=validate(sim); cou_report=validate(cou)
    if dest.exists(): raise ValueError('Comparison destination must be new')
    dest.mkdir(parents=True); records=[]; hashes={}
    for source in [sim,cou]:
        for line in (source/'manifest.jsonl').read_text().splitlines():
            r=json.loads(line)
            if source==cou and r['split']!='train': raise ValueError('COU must remain training-only by whole sequence')
            digest=r.get('sha256') or hashlib.sha256((source/r['image']).read_bytes()).hexdigest()
            if digest in hashes:
                if hashes[digest]!=r['split']: raise ValueError('Duplicate pixels cross split boundaries')
                continue
            hashes[digest]=r['split']; original=source/r['image']; name=r['id']+original.suffix
            image=dest/'images'/r['split']/name; label=dest/'labels'/r['split']/(r['id']+'.txt')
            image.parent.mkdir(parents=True,exist_ok=True); label.parent.mkdir(parents=True,exist_ok=True)
            try: os.link(original,image)
            except OSError: shutil.copy2(original,image)
            shutil.copy2(source/'labels'/r['split']/(original.stem+'.txt'),label)
            records.append({**r,'image':str(image.relative_to(dest)),'sha256':digest})
    (dest/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    (dest/'generation.json').write_text(json.dumps({'schema':2,'target_images':len(records),'split_counts':dict(Counter(r['split'] for r in records)),
        'simulator':sim_report,'COU':cou_report,'license':'Mixed: simulator CC BY4.0, COU CC BY-SA4.0; preserve source attribution','upload_allowed':False,'real_world_generalization_claim':False},indent=2))
    (dest/'dataset.yaml').write_text('path: '+str(dest.resolve())+'\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: pipe\n')
    return validate(dest)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--sim',type=Path,default=Path('data/orientation')); p.add_argument('--cou',type=Path,default=Path('data/cou-local')); p.add_argument('--output',type=Path,default=Path('data/orientation-cou')); args=p.parse_args()
    print(json.dumps(build(args.sim,args.cou,args.output),indent=2))


if __name__=='__main__': main()
