#!/usr/bin/env python3
"""Local-only COU audit/import. Never upload or silently turn unlabelled images into negatives."""
import argparse
from collections import Counter,defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
import cv2
import numpy as np
from geometry import yolo_label


def sequence(filename):
    return re.sub(r'[_-]\d+$','',Path(filename).stem)


def clipped_box(annotation,width,height):
    x,y,w,h=annotation['bbox']; x1=max(0.,float(x)); y1=max(0.,float(y))
    x2=min(float(width),float(x+w)); y2=min(float(height),float(y+h))
    if not np.isfinite([x1,y1,x2,y2]).all() or x2<=x1 or y2<=y1: raise ValueError('Invalid COCO box')
    return [x1,y1,x2,y2]


def main():
    p=argparse.ArgumentParser(); p.add_argument('--archive',type=Path,required=True); p.add_argument('--output',type=Path,default=Path('data/cou-local'))
    p.add_argument('--approved-negatives',type=Path,help='JSON list of filenames explicitly approved after reviewing contact sheets')
    p.add_argument('--include-reviewed-g18-negatives',action='store_true',help='Include the separately reviewed non-pipe G18 frames')
    args=p.parse_args(); dest=args.output; dest.mkdir(parents=True,exist_ok=True)
    if (dest/'manifest.jsonl').exists(): p.error('Refusing to overwrite existing import')
    rows={}; original_splits=defaultdict(set); categories=None
    with zipfile.ZipFile(args.archive) as z:
        for split in ['train','val','test']:
            data=json.loads(z.read('coco/coco/'+split+'_annotations.json')); categories=data['categories']
            if not any(c['id']==14 and c['name'].lower()=='pipe' for c in categories): raise ValueError('Category 14 is not Pipe')
            annotations=defaultdict(list)
            for a in data['annotations']: annotations[a['image_id']].append(a)
            for im in data['images']:
                name=im['file_name']; original_splits[sequence(name)].add(split)
                if name in rows: raise ValueError('Duplicate filename in archive: '+name)
                rows[name]={'image':im,'annotations':annotations[im['id']],'split':split}
        positives=sorted(name for name,r in rows.items() if any(a['category_id']==14 for a in r['annotations']))
        # Unknowns and elongated tools require a separate review, rather than weak negative labels.
        excluded={0,3,4,14,15,16,18,20,22}
        candidates=sorted(name for name,r in rows.items() if r['split']=='train' and sequence(name)!='G18' and r['annotations'] and not any(a['category_id'] in excluded for a in r['annotations']))
        rng=np.random.default_rng(42); rng.shuffle(candidates); candidates=candidates[:350]
        approved=json.loads(args.approved_negatives.read_text()) if args.approved_negatives else []
        if not set(approved)<=set(candidates): raise ValueError('Approved filenames are not in the reviewed candidate set')
        audit={'images':len(rows),'pipe_positive_images':len(positives),'pipe_instances':sum(a['category_id']==14 for r in rows.values() for a in r['annotations']),
               'pipe_sequences':sorted({sequence(n) for n in positives}),'original_sequence_leakage':{k:sorted(v) for k,v in original_splits.items() if len(v)>1},
               'negative_candidates':candidates,'approved_negatives':approved,'G18_nonpositive_excluded':sorted(n for n in rows if sequence(n)=='G18' and n not in positives),
               'license':'CC BY-SA 4.0','attribution':'Sattar, Mukherjee, Singh, McWilliams (2025), COU: Common Objects Underwater, DOI 10.13020/1vwe-2707',
               'upload_allowed':False,'limitation':'All pipe positives are from one sequence; cannot establish independent real-world generalization.'}
        (dest/'audit.json').write_text(json.dumps(audit,indent=2))
        # Contact sheets include every positive and every proposed negative, labelled for human review.
        review=dest/'review'; review.mkdir(exist_ok=True)
        for kind,names in [('positive',positives),('negative',candidates),('ambiguous-g18',audit['G18_nonpositive_excluded'])]:
            for start in range(0,len(names),40):
                canvas=np.full((8*150,5*260,3),235,dtype=np.uint8)
                for j,name in enumerate(names[start:start+40]):
                    r=rows[name]; raw=z.read('coco/coco/images/'+name); frame=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
                    for a in r['annotations']:
                        if a['category_id']==14:
                            b=clipped_box(a,r['image']['width'],r['image']['height']); cv2.rectangle(frame,tuple(map(int,b[:2])),tuple(map(int,b[2:])),(0,0,255),6)
                    tile=cv2.resize(frame,(260,130)); x=(j%5)*260; y=(j//5)*150; canvas[y:y+130,x:x+260]=tile
                    cv2.putText(canvas,name,(x+3,y+144),cv2.FONT_HERSHEY_SIMPLEX,.37,(0,0,0),1)
                cv2.imwrite(str(review/f'{kind}-{start//40:02d}.jpg'),canvas)
        records=[]; hashes=set()
        selected=positives+approved+(audit['G18_nonpositive_excluded'] if args.include_reviewed_g18_negatives else [])
        audit['reviewed_g18_negatives_included']=bool(args.include_reviewed_g18_negatives)
        (dest/'audit.json').write_text(json.dumps(audit,indent=2))
        for name in selected:
            r=rows[name]; im=r['image']; raw=z.read('coco/coco/images/'+name); digest=hashlib.sha256(raw).hexdigest()
            if digest in hashes: continue
            hashes.add(digest); frame=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
            if frame is None or frame.shape[:2]!=(im['height'],im['width']): raise ValueError('Corrupt image or dimensions: '+name)
            boxes=[clipped_box(a,im['width'],im['height']) for a in r['annotations'] if a['category_id']==14]
            image=dest/'images/train'/name; label=dest/'labels/train'/(Path(name).stem+'.txt'); image.parent.mkdir(parents=True,exist_ok=True); label.parent.mkdir(parents=True,exist_ok=True)
            image.write_bytes(raw); label.write_text(''.join(yolo_label(b,im['width'],im['height']) for b in boxes))
            records.append({'id':'cou-'+Path(name).stem,'source':'COU','sequence':sequence(name),'group':'cou-'+sequence(name),'split':'train','original_split':r['split'],'image':str(image.relative_to(dest)),
                            'bbox':boxes[0] if boxes else None,'boxes':boxes,'width':im['width'],'height':im['height'],'sha256':digest,'audit':'original-pipe-annotation' if boxes else 'visually-approved-negative'})
        (dest/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
        (dest/'generation.json').write_text(json.dumps({'schema':2,'target_images':len(records),'split_counts':{'train':len(records)},'source_archive':str(args.archive.resolve()),'license':audit['license'],'upload_allowed':False},indent=2))
        print(json.dumps({k:v for k,v in audit.items() if k not in ['negative_candidates','original_sequence_leakage']},indent=2))


if __name__=='__main__': main()
