"""Three-class visible-instance labels and group-wise dataset integrity checks."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
CLASSES=('pipe','valve','flange')
ENTITIES={'Pipeline':'pipe','InspectionValve':'valve','InspectionFlange':'flange'}

def boxes_from_mask(mask, instance_map):
    if mask.ndim!=2 or mask.dtype!=np.uint16: raise ValueError('Expected native uint16 instance mask')
    if set(instance_map.values())!=set(ENTITIES): raise ValueError('Missing or unexpected target instance IDs')
    if len(instance_map)!=3 or len(set(instance_map))!=3: raise ValueError('Targets must have distinct instance IDs')
    boxes=[]
    for instance,name in instance_map.items():
        ys,xs=np.where(mask==int(instance))
        if not len(xs): continue
        box=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]
        eligible=box[2]-box[0]>=4 and box[3]-box[1]>=4 and len(xs)>=100
        boxes.append({'class':ENTITIES[name],'class_id':CLASSES.index(ENTITIES[name]),'instance_id':int(instance),
                      'bbox':box,'visible_pixels':int(len(xs)),'eligible':bool(eligible)})
    return boxes

def labels(boxes,width,height):
    return ''.join(f"{b['class_id']} {(b['bbox'][0]+b['bbox'][2])/(2*width):.8f} {(b['bbox'][1]+b['bbox'][3])/(2*height):.8f} {(b['bbox'][2]-b['bbox'][0])/width:.8f} {(b['bbox'][3]-b['bbox'][1])/height:.8f}\n" for b in boxes)

def audit(data,expected=None,full=False):
    data=Path(data); manifest=data/'manifest.jsonl'
    records=[json.loads(l) for l in manifest.read_text().splitlines()]
    if expected is not None and len(records)!=expected: raise ValueError('Unexpected image count')
    ids=set(); hashes=set(); group_splits={}; group_scenes={}; counts=dict.fromkeys(CLASSES,0); splits=dict.fromkeys(('train','val','test'),0); absent=0
    for r in records:
        if r['id'] in ids or r['sha256'] in hashes: raise ValueError('Duplicate capture')
        ids.add(r['id']); hashes.add(r['sha256'])
        if r['source']!='stonefish' or r.get('schema')!='inspection-v1': raise ValueError('Unapproved source/schema')
        if group_splits.setdefault(r['group'],r['split'])!=r['split']: raise ValueError('Group leakage')
        if group_scenes.setdefault(r['group'],r['scene'])!=r['scene']: raise ValueError('Scene changed inside viewpoint group')
        if r['stamp']!=r['mask_stamp']: raise ValueError('RGB/mask timestamp mismatch')
        image=data/r['image']; label=data/r['label']; mask=data/r['mask']
        if hashlib.sha256(image.read_bytes()).hexdigest()!=r['sha256']: raise ValueError('Changed image')
        if hashlib.sha256(mask.read_bytes()).hexdigest()!=r['mask_sha256']: raise ValueError('Changed mask')
        if label.read_text()!=labels(r['boxes'],r['width'],r['height']): raise ValueError('Changed annotation')
        if r['optics']['natural'] is False and r['optics']['lamps'] is False: raise ValueError('Unlit diagnostics cannot enter training')
        splits[r['split']]+=1; absent+=not r['boxes']
        for b in r['boxes']:
            if b['eligible']: counts[b['class']]+=1
    report={'images':len(records),'groups':len(group_splits),'splits':splits,'eligible_instances':counts,'target_absent':absent,
            'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'classes':list(CLASSES),'source':'stonefish'}
    if full:
        sealed=data/'sealed_dataset.json'
        if sealed.exists():
            contract=json.loads(sealed.read_text())
            validate_sealed(report,contract)
            if any(sum(r['group']==g for r in records)!=10 for g in group_splits):raise ValueError('Incomplete viewpoint group')
            if {r['scene_variant'] for r in records}!={0,1,2,3}:raise ValueError('Missing fixture variant')
            if len({json.dumps(r['optics'],sort_keys=True) for r in records})!=18:raise ValueError('Missing optical profile')
            if len({int((math.degrees(r['rpy'][0])+180)//30) for r in records})!=12:raise ValueError('Missing roll bin')
            report['sealed_contract']=contract
        elif len(records)!=9000 or len(group_splits)!=900 or splits!={'train':6300,'val':1350,'test':1350} or absent!=2250:
            raise ValueError('Full dataset split/count requirement failed')
        if min(counts.values())<2250: raise ValueError('Class coverage requirement failed')
    return report


def validate_sealed(report,contract):
    for field in ('images','groups','splits','target_absent','manifest_sha256'):
        if report[field]!=contract[field]:raise ValueError('Sealed dataset differs: '+field)
    if contract.get('authorization')!='User-approved reduced simulator dataset':raise ValueError('Unapproved reduced dataset contract')
    if abs(report['target_absent']/report['images']-.25)>.01:raise ValueError('Negative coverage changed')
    if any(abs(report['splits'][s]/report['images']-fraction)>.01 for s,fraction in (('train',.7),('val',.15),('test',.15))):raise ValueError('Split balance changed')


def viewpoints(groups=900,seed=42):
    rng=np.random.default_rng(seed); order=rng.permutation(groups)
    split={int(g):'train' if i<int(groups*.7) else 'val' if i<int(groups*.85) else 'test' for i,g in enumerate(order)}
    # Rotation/scene/viewpoint groups remain together across all optical variants.
    for g in range(groups):
        xyz=np.array([rng.uniform(-3.7,3.2),rng.uniform(-1.7,1.7),rng.uniform(.7,2.3)])
        target=np.array([4.4,(-.85,0,.85)[g%3],1.4])
        delta=target-xyz; yaw=math.atan2(delta[1],delta[0]); pitch=-math.atan2(delta[2],np.linalg.norm(delta[:2]))
        roll=rng.uniform(-math.pi,math.pi); yaw+=rng.uniform(-math.pi/2,math.pi/2);pitch+=rng.uniform(-math.pi/4,math.pi/4)
        negative=g%4==0
        if negative:
            yaw=math.atan2(delta[1],delta[0])+math.pi+rng.uniform(-.2,.2)
            pitch=-math.atan2(delta[2],np.linalg.norm(delta[:2]))
        yield {'group':g,'split':split[g],'xyz':xyz.tolist(),'rpy':[roll,pitch,yaw],'negative':negative,'coverage_target':None if negative else ('valve','pipe','flange')[g%3]}
