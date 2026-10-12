#!/usr/bin/env python3
"""Freeze the explicitly approved reduced dataset after its last whole group."""
import argparse
import json
from pathlib import Path
import time
from inspection_dataset import audit


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True)
    p.add_argument('--selection',type=Path,required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--wait',action='store_true')
    args=p.parse_args();selection=json.loads(args.selection.read_text());target=selection['target_images']
    while True:
        lines=(args.data/'manifest.jsonl').read_bytes().splitlines(keepends=True)
        count=sum(line.endswith(b'\n') for line in lines)
        if count>target:raise ValueError('Capture exceeded approved reduced target')
        if count==target:break
        if not args.wait:raise ValueError('Capture not complete')
        time.sleep(5)
    report=audit(args.data,expected=target)
    expected_splits={s:g*10 for s,g in selection['final_group_splits'].items()}
    if report['splits']!=expected_splits:raise ValueError('Frozen split selection changed')
    if report['target_absent']!=round(target/10*.25)*10:raise ValueError('Negative group selection changed')
    rows=[json.loads(l) for l in (args.data/'manifest.jsonl').read_text().splitlines()]
    for group in selection['selected_groups']:
        chosen=[r for r in rows if r['group']==group]
        if len(chosen)!=10 or any(r['scene_variant']!=3 for r in chosen):raise ValueError('Fourth-variant selection not complete')
    contract={k:report[k] for k in ('images','groups','splits','target_absent','manifest_sha256')}
    contract.update(authorization='User-approved reduced simulator dataset',original_target_images=9000,
                    generation_space_groups=900,seed=42,selection=selection,
                    acceptance='Unchanged recall, false-positive and latency gates; minimum 2250 eligible instances per class')
    path=args.data/'sealed_dataset.json';temporary=path.with_suffix('.partial')
    temporary.write_text(json.dumps(contract,indent=2));temporary.replace(path)
    verified=audit(args.data,expected=target,full=True)
    config=json.loads(args.config.read_text());config.update(dataset_images=target,dataset_groups=target//10,
        split_groups=[expected_splits[s]//10 for s in ('train','val','test')],
        split_images=[expected_splits[s] for s in ('train','val','test')],
        original_dataset_target=9000,manifest_sha256=report['manifest_sha256'])
    args.config.write_text(json.dumps(config,indent=2))
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(verified,indent=2))
    print(json.dumps(verified,indent=2))


if __name__=='__main__':main()
