#!/usr/bin/env python3
"""Client-side signed PUT and image-only zip staging for Roboflow MCP."""
import argparse
import json
from pathlib import Path
import shutil
from urllib.parse import urlparse
import urllib.request
import zipfile


def pack(data,output,limit=None,offset=0):
    records=[json.loads(s) for s in (data/'manifest.jsonl').read_text().splitlines()]
    records=records[offset:offset+limit if limit else None]
    if not records or len(records)>10000: raise ValueError('Zip must contain 1..10000 images')
    if any(r.get('source')!='stonefish' for r in records): raise ValueError('Only explicitly authorized simulator data may be uploaded')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as z:
        for r in records:
            split='valid' if r['split']=='val' else r['split']; p=data/r['image']
            z.write(p,split+'/'+p.name)
    if output.stat().st_size>2_000_000_000: raise ValueError('Zip exceeds 2GB')
    sidecar=output.with_suffix('.manifest.json'); sidecar.write_text(json.dumps(records))
    return {'images':len(records),'bytes':output.stat().st_size,'zip':str(output),'manifest':str(sidecar)}


def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('pack'); a.add_argument('--data',type=Path,required=True); a.add_argument('--output',type=Path,required=True); a.add_argument('--limit',type=int); a.add_argument('--offset',type=int,default=0)
    b=sub.add_parser('put'); b.add_argument('--zip',type=Path,required=True); b.add_argument('--credentials',type=Path,required=True)
    c=sub.add_parser('get'); c.add_argument('--output',type=Path,required=True); c.add_argument('--credentials',type=Path,required=True)
    args=p.parse_args()
    if args.command=='pack': print(json.dumps(pack(args.data,args.output,args.limit,args.offset)))
    elif args.command=='get':
        credentials=json.loads(args.credentials.read_text()); url=credentials['link']; parsed=urlparse(url)
        if parsed.scheme!='https' or not (parsed.hostname=='storage.googleapis.com' or (parsed.hostname or '').endswith('.roboflow.com')): raise ValueError('Unexpected export destination')
        args.output.parent.mkdir(parents=True,exist_ok=True); staged=args.output.with_suffix('.partial')
        try:
            with urllib.request.urlopen(url,timeout=300) as response, staged.open('wb') as f: shutil.copyfileobj(response,f)
            with zipfile.ZipFile(staged) as z:
                if z.testzip() is not None: raise ValueError('Corrupt export archive')
            staged.replace(args.output); print(json.dumps({'bytes':args.output.stat().st_size,'archive':str(args.output)}))
        finally: args.credentials.unlink(missing_ok=True)
    else:
        credentials=json.loads(args.credentials.read_text()); url=credentials['signedUrl']
        if not url.startswith('https://storage.googleapis.com/roboflow-platform-upload/'): raise ValueError('Unexpected upload destination')
        req=urllib.request.Request(url,data=args.zip.read_bytes(),method='PUT',headers={'Content-Type':'application/zip'})
        try:
            with urllib.request.urlopen(req,timeout=300) as response: print(json.dumps({'status':response.status,'taskId':credentials['taskId']}))
        finally: args.credentials.unlink(missing_ok=True)


if __name__=='__main__': main()
