#!/usr/bin/env python3
"""Preserve suspect renders outside the active dataset before recapturing groups."""
import argparse
import json
from pathlib import Path
import shutil


def quarantine(data,destination,from_group):
    if destination.exists(): raise ValueError('Quarantine destination must be new')
    records=[json.loads(line) for line in (data/'manifest.jsonl').read_text().splitlines()]
    if any(r.get('source')!='stonefish' for r in records): raise ValueError('Only simulator captures are supported')
    selected=[r for r in records if int(r['group'].removeprefix('sim-o'))>=from_group]
    retained=[r for r in records if int(r['group'].removeprefix('sim-o'))<from_group]
    # Preflight every move before altering the dataset.
    moves=[]
    for r in selected:
        image=Path(r['image']); label=Path('labels')/r['split']/(image.stem+'.txt')
        for relative in [image,label]:
            source=data/relative
            if not source.is_file(): raise ValueError('Missing suspect artifact: '+str(source))
            moves.append((source,destination/relative))
    destination.mkdir(parents=True)
    (destination/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selected))
    shutil.copy2(data/'generation.json',destination/'original-generation.json')
    for source,target in moves:
        target.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(source),str(target))
    temporary=data/'manifest.repaired.jsonl'; temporary.write_text(''.join(json.dumps(r)+'\n' for r in retained)); temporary.replace(data/'manifest.jsonl')
    report={'retained':len(retained),'quarantined':len(selected),'from_group':from_group,'reason':'Repeated rendered pixels with conflicting positive/negative geometry labels; simulator clock/render investigation'}
    (destination/'quarantine.json').write_text(json.dumps(report,indent=2)); return report


def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,required=True); p.add_argument('--destination',type=Path,required=True); p.add_argument('--from-group',type=int,required=True); args=p.parse_args()
    print(json.dumps(quarantine(args.data,args.destination,args.from_group)))


if __name__=='__main__': main()
