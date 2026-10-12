#!/usr/bin/env python3
"""Audited multiclass SDK import; model training is initiated through MCP.

The legacy pipe import and quarantine guard remain untouched.
"""
import argparse
from contextlib import redirect_stdout,redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import zipfile
from inspection_dataset import audit,CLASSES
from roboflow_annotations import voc

PROJECT='neptune-inspection-objects';WORKSPACE='projects-zwfft'

def prepare(data,archive,expected,full=False):
    report=audit(data,expected=expected,full=full)
    archive.parent.mkdir(parents=True,exist_ok=True)
    records=[json.loads(l) for l in (data/'manifest.jsonl').read_text().splitlines()]
    with zipfile.ZipFile(archive.with_suffix('.partial'),'w',compression=zipfile.ZIP_STORED) as output:
        output.writestr('_classes.txt','\n'.join(CLASSES)+'\n')
        output.writestr('data.yaml','train: train\nval: valid\ntest: test\nnc: 3\nnames: [pipe, valve, flange]\n')
        for r in records:
            image=data/r['image'];split='valid' if r['split']=='val' else r['split']
            output.write(image,f'{split}/{image.name}')
            if r['boxes']:
                output.writestr(f'{split}/{image.stem}.txt',(data/r['label']).read_text())
            else:
                output.writestr(f'{split}/{image.stem}.xml',voc({**r,'bbox':None}))
    archive.with_suffix('.partial').replace(archive)
    report.update(project=f'{WORKSPACE}/{PROJECT}',license='CC BY 4.0',archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),full_dataset=full)
    archive.with_suffix('.report.json').write_text(json.dumps(report,indent=2));return report

def upload(archive,key_file,result_file):
    report=json.loads(archive.with_suffix('.report.json').read_text())
    if report['project']!=f'{WORKSPACE}/{PROJECT}' or report['classes']!=list(CLASSES) or report['source']!='stonefish':raise ValueError('Unauthorized transfer schema')
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=report['archive_sha256']:raise ValueError('Archive changed')
    key=key_file.read_text().strip();captured=io.StringIO()
    if not key:raise ValueError('Configure an ignored local key file')
    try:
        with redirect_stdout(captured),redirect_stderr(captured):
            from roboflow import Roboflow
            workspace=Roboflow(api_key=key).workspace(WORKSPACE)
            project=workspace.project(PROJECT)
            if project.id!=report['project']:raise ValueError('Resolved project mismatch')
            result=workspace.upload_dataset(str(archive),PROJECT,batch_name='verified-inspection-'+('full' if report['full_dataset'] else 'pilot'),annotation_overwrite=True,wait=False,project_license='CC BY 4.0',project_type='object-detection')
        sanitized=json.loads(json.dumps(result).replace(key,'[REDACTED]'))
        result_file.write_text(json.dumps({'audit':report,'sdk_result':sanitized},indent=2))
        return {'result_file':str(result_file),'task_id':sanitized.get('task_id')}
    except Exception as exc:raise RuntimeError(str(exc).replace(key,'[REDACTED]')) from None

def annotation_requests(data,server):
    records=[json.loads(l) for l in (data/'manifest.jsonl').read_text().splitlines()]
    images={r['filename']:r for r in server['results']}
    if len(images)!=len(records) or len(images)!=len(server['results']):raise ValueError('Server count/filename uniqueness mismatch')
    audit(data,expected=len(records))
    requests=[]
    for r in records:
        name=Path(r['image']).name
        if name not in images:raise ValueError('Missing uploaded filename')
        image=images.pop(name)
        if image['split']!=('valid' if r['split']=='val' else r['split']):raise ValueError('Uploaded split mismatch')
        positive=bool(r['boxes'])
        request={'project_id':f'{WORKSPACE}/{PROJECT}','image_id':image['id'],'annotation_name':Path(name).with_suffix('.txt' if positive else '.xml').name,
                 'annotation_content':(data/r['label']).read_text() if positive else voc({**r,'bbox':None}),
                 'add_to_dataset':True,'overwrite':True}
        if positive:request['labelmap']={str(i):name for i,name in enumerate(CLASSES)}
        requests.append(request)
    return requests

def confirm_membership(data,key_file,result_file,workers=8):
    """Verified per-image official SDK saves, without the MCP per-call overhead."""
    from concurrent.futures import ThreadPoolExecutor,as_completed
    report=audit(data,full=True)
    key=key_file.read_text().strip();captured=io.StringIO()
    if not key:raise ValueError('Configure an ignored local key file')
    outcomes=[]
    try:
        with redirect_stdout(captured),redirect_stderr(captured):
            from roboflow import Roboflow
            from importlib.metadata import version
            if version('roboflow')!='1.7.1':raise ValueError('Use pinned roboflow==1.7.1')
            project=Roboflow(api_key=key).workspace(WORKSPACE).project(PROJECT)
            if project.id!=f'{WORKSPACE}/{PROJECT}':raise ValueError('Resolved project mismatch')
            server={'results':[image for page in project.search_all(prompt='',limit=100,fields=['id','filename','split']) for image in (page['results'] if isinstance(page,dict) else page)]}
            requests=annotation_requests(data,server)
            if result_file.exists():
                previous=json.loads(result_file.read_text())
                if previous['manifest_sha256']!=report['manifest_sha256']:raise ValueError('Checkpoint belongs to another manifest')
                outcomes=previous['outcomes']
            done={r['image_id'] for r in outcomes if r['success']}
            def save(r):
                response,_,_=project.save_annotation(annotation_path={'name':r['annotation_name'],'rawText':r['annotation_content']},
                    annotation_labelmap=r.get('labelmap'),image_id=r['image_id'],annotation_overwrite=True,add_to_dataset=True)
                if not response.get('success'):raise RuntimeError('Annotation save was not successful')
                return {'image_id':r['image_id'],'success':True}
            with ThreadPoolExecutor(max_workers=max(1,min(16,workers))) as pool:
                futures={pool.submit(save,r):r for r in requests if r['image_id'] not in done}
                for future in as_completed(futures):
                    try:outcomes.append(future.result())
                    except Exception as exc:
                        outcomes.append({'image_id':futures[future]['image_id'],'success':False,'error_type':type(exc).__name__})
                    if len(outcomes)%100==0:
                        result_file.write_text(json.dumps({'manifest_sha256':report['manifest_sha256'],'outcomes':outcomes},indent=2))
            result_file.write_text(json.dumps({'manifest_sha256':report['manifest_sha256'],'outcomes':outcomes},indent=2))
        successful={r['image_id'] for r in outcomes if r['success']}
        if len(successful)!=report['images']:raise RuntimeError('Some annotation saves failed; inspect sanitized checkpoint and resume')
        return {'confirmed_dataset_images':len(successful),'result_file':str(result_file)}
    except Exception as exc:raise RuntimeError(str(exc).replace(key,'[REDACTED]')) from None

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare');a.add_argument('--data',type=Path,required=True);a.add_argument('--archive',type=Path,required=True);a.add_argument('--expected',type=int,required=True);a.add_argument('--full',action='store_true')
    a=sub.add_parser('upload');a.add_argument('--archive',type=Path,required=True);a.add_argument('--key-file',type=Path,required=True);a.add_argument('--result',type=Path,required=True)
    a=sub.add_parser('annotations');a.add_argument('--data',type=Path,required=True);a.add_argument('--server',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('confirm');a.add_argument('--data',type=Path,required=True);a.add_argument('--key-file',type=Path,required=True);a.add_argument('--result',type=Path,required=True);a.add_argument('--workers',type=int,default=8)
    args=p.parse_args()
    if args.action=='confirm':
        print(json.dumps(confirm_membership(args.data,args.key_file,args.result,args.workers)));raise SystemExit(0)
    if args.action=='annotations':
        requests=annotation_requests(args.data,json.loads(args.server.read_text()))
        args.output.write_text(json.dumps(requests));print(json.dumps({'requests':len(requests),'output':str(args.output)}));raise SystemExit(0)
    print(json.dumps(prepare(args.data,args.archive,args.expected,args.full) if args.action=='prepare' else upload(args.archive,args.key_file,args.result),indent=2))
