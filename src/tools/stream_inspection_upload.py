#!/usr/bin/env python3
"""Upload immutable, audited complete groups while Stonefish keeps capturing.

One writer owns this checkpoint. Training/version creation remains an MCP step
after the full 9,000-image local and cloud-export audits.
"""
import argparse
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from inspection_dataset import audit, CLASSES
from roboflow_inspection import prepare, WORKSPACE, PROJECT
from roboflow_annotations import voc


def complete_records(data):
    # A concurrently appended last line may be incomplete; never stage it.
    content=(data/'manifest.jsonl').read_bytes()
    lines=content.splitlines(keepends=True)
    records=[json.loads(line) for line in lines if line.endswith(b'\n')]
    counts=Counter(r['group'] for r in records)
    return [r for r in records if counts[r['group']]==10]


def snapshot(data, records, destination):
    destination.mkdir(parents=True,exist_ok=True)
    manifest=''.join(json.dumps(r)+'\n' for r in records)
    for r in records:
        for key in ('image','label','mask'):
            target=destination/r[key]; target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():target.symlink_to((data/r[key]).resolve())
    (destination/'manifest.jsonl').write_text(manifest)
    return audit(destination,expected=len(records))


def save_checkpoint(path,state):
    temporary=path.with_suffix('.partial')
    temporary.write_text(json.dumps(state,indent=2));temporary.replace(path)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--key-file',type=Path,required=True);p.add_argument('--batch-images',type=int,default=200)
    p.add_argument('--target-images',type=int,default=9000)
    args=p.parse_args()
    if args.batch_images<10 or args.batch_images%10:p.error('Batch size must contain whole ten-image groups')
    args.output.mkdir(parents=True,exist_ok=True);checkpoint=args.output/'checkpoint.json'
    state=json.loads(checkpoint.read_text()) if checkpoint.exists() else {'project':f'{WORKSPACE}/{PROJECT}','confirmed':{},'batches':[]}
    if state['project']!=f'{WORKSPACE}/{PROJECT}':raise ValueError('Checkpoint project mismatch')
    key=args.key_file.read_text().strip()
    if not key:raise ValueError('Missing ignored credential')
    from importlib.metadata import version
    if version('roboflow')!='1.7.1':raise ValueError('Use pinned roboflow==1.7.1')
    # Capture SDK progress/errors privately: upload URLs may contain credentials.
    with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
        from roboflow import Roboflow
        workspace=Roboflow(api_key=key).workspace(WORKSPACE);project=workspace.project(PROJECT)
    if project.id!=state['project']:raise ValueError('Resolved project mismatch')
    while True:
        rows=complete_records(args.data)
        for r in rows:
            previous=state['confirmed'].get(r['id'])
            if previous and previous!=r['sha256']:raise ValueError('Previously transferred capture changed')
        pending=[r for r in rows if r['id'] not in state['confirmed']]
        if not pending:
            if len(state['confirmed'])==args.target_images:
                audit(args.data,expected=args.target_images,full=True)
                print(f'All {args.target_images} images uploaded and annotations confirmed; full cloud export audit and MCP training remain.',flush=True)
                return
            time.sleep(20);continue
        if len(pending)<args.batch_images and len(rows)<args.target_images:time.sleep(20);continue
        selected=pending[:args.batch_images]
        identity=hashlib.sha256(''.join(r['id']+r['sha256'] for r in selected).encode()).hexdigest()[:16]
        batch=args.output/identity;report=snapshot(args.data,selected,batch/'dataset')
        archive=batch/'images.zip';prepare(batch/'dataset',archive,len(selected))
        print(f'Uploading audited batch: {len(selected)} images; {len(state["confirmed"])} already confirmed.',flush=True)
        try:
            with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                marker=batch/'upload.json'
                if not marker.exists():
                    uploaded=workspace.upload_dataset(str(archive),PROJECT,batch_name='verified-inspection-'+identity,
                        annotation_overwrite=True,wait=True,project_license='CC BY 4.0',project_type='object-detection')
                    if uploaded.get('status')!='completed':raise RuntimeError('Zip processing did not complete')
                    marker.write_text(json.dumps({'status':'completed','batch':identity}))
                server={r['filename']:r for page in project.search_all(prompt='',limit=100,fields=['id','filename','split']) for r in (page['results'] if isinstance(page,dict) else page)}
            requests=[]
            for r in selected:
                image=server.get(Path(r['image']).name)
                if image is None or image['split']!=('valid' if r['split']=='val' else r['split']):raise ValueError('Uploaded image or split mismatch')
                requests.append((r,image))
            def save(pair):
                r,image=pair;positive=bool(r['boxes'])
                response,_,_=project.save_annotation(annotation_path={
                    'name':Path(r['image']).with_suffix('.txt' if positive else '.xml').name,
                    'rawText':(args.data/r['label']).read_text() if positive else voc({**r,'bbox':None})},
                    annotation_labelmap={str(i):c for i,c in enumerate(CLASSES)} if positive else None,
                    image_id=image['id'],annotation_overwrite=True,add_to_dataset=True)
                if not response.get('success'):raise RuntimeError('Annotation save failed')
                return r
            with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    for future in as_completed([pool.submit(save,r) for r in requests]):
                        r=future.result();state['confirmed'][r['id']]=r['sha256']
                        save_checkpoint(checkpoint,state)
            state['batches'].append({'batch':identity,'audit':report});save_checkpoint(checkpoint,state)
            print(f'Confirmed image/annotation pairs: {len(state["confirmed"])}/{args.target_images}.',flush=True)
        except Exception as exc:
            # Persist successes; next attempt resends only missing groups/images.
            save_checkpoint(checkpoint,state)
            locations=[Path(f.filename).name+':'+str(f.lineno) for f in traceback.extract_tb(exc.__traceback__)]
            print(f'Batch deferred: {type(exc).__name__} at {locations}; checkpoint preserved.',flush=True)
            time.sleep(30)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        raise SystemExit('Inspection transfer stopped: '+type(exc).__name__+'; credentials and SDK URLs omitted.') from None
