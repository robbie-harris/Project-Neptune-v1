#!/usr/bin/env python3
"""Prepare resumable MCP annotation requests and verify server split membership."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from geometry import yolo_label


def voc(record):
    if record['bbox'] is not None: raise ValueError('Positive annotations require normalized YOLO to avoid VOC origin conversion')
    root=Element('annotation'); SubElement(root,'filename').text=Path(record['image']).name
    size=SubElement(root,'size')
    for name,value in [('width',record['width']),('height',record['height']),('depth',3)]: SubElement(size,name).text=str(value)
    return tostring(root,encoding='unicode')


def prepare(records,server,project,refresh_all=False):
    if any(record.get('source')!='stonefish' for record in records): raise ValueError('Only authorized simulator records may be staged for Roboflow')
    images={}
    for image in server:
        name=image['filename']
        if name in images: raise ValueError('Duplicate server filename: '+name)
        images[name]=image
    requests=[]; counts=Counter(); already=0
    for record in records:
        name=Path(record['image']).name
        if name not in images: raise ValueError('Missing uploaded image: '+name)
        image=images.pop(name); expected='valid' if record['split']=='val' else record['split']
        if image['split']!=expected: raise ValueError('Server split differs from frozen local split: '+name)
        counts[expected]+=1
        if image.get('in_dataset') is True and not refresh_all:
            already+=1; continue
        positive=record['bbox'] is not None
        request={'project_id':project,'image_id':image['id'],'annotation_name':Path(name).with_suffix('.txt' if positive else '.xml').name,'annotation_content':yolo_label(record['bbox'],record['width'],record['height']) if positive else voc(record),'add_to_dataset':True,'overwrite':refresh_all}
        if positive: request['labelmap']={'0':'pipe'}
        requests.append(request)
    if images: raise ValueError('Unexpected server images not represented in local manifest')
    return requests,{'images':len(records),'split_counts':dict(counts),'already_in_dataset':already,'requests':len(requests),'refresh_all':refresh_all}


def main():
    p=argparse.ArgumentParser(); p.add_argument('--manifest',type=Path,required=True); p.add_argument('--server-images',type=Path,required=True); p.add_argument('--project',required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--refresh-all',action='store_true',help='Overwrite labels on every verified image, including existing Dataset members'); args=p.parse_args()
    content=args.manifest.read_text()
    records=json.loads(content) if content.lstrip().startswith('[') else [json.loads(line) for line in content.splitlines() if line.strip()]
    server=json.loads(args.server_images.read_text())
    if isinstance(server,dict): server=server['results']
    requests,report=prepare(records,server,args.project,args.refresh_all)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(''.join(json.dumps(request)+'\n' for request in requests))
    report['manifest_sha256']=hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    args.output.with_suffix('.report.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report))


if __name__=='__main__': main()
