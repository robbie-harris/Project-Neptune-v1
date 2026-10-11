"""Deterministic viewpoint sampling and split assignment; no ROS imports."""
import math
import hashlib
import numpy as np
from geometry import rotation_rpy, pipe_surface, pipe_edges, projected_geometry, camera_matrix


def camera_transform(xyz,rpy,camera):
    body=np.eye(4); body[:3,:3]=rotation_rpy(rpy); body[:3,3]=xyz
    sensor=np.eye(4); sensor[:3,:3]=rotation_rpy(camera['rpy']); sensor[:3,3]=camera['xyz']
    return body@sensor


def orientation_views(rig,groups=600,seed=42):
    if groups%40: raise ValueError('groups must be a multiple of 40 for exact 70/15/15 splits and negative quotas')
    rng=np.random.default_rng(seed)
    # Equal even/odd groups per split keeps the 2/3-negative alternating quota exact.
    partitions={}
    for parity in [0,1]:
        ids=np.arange(parity,groups,2); rng.shuffle(ids)
        for i,g in enumerate(ids): partitions[int(g)]='train' if i<len(ids)*.7 else 'val' if i<len(ids)*.85 else 'test'
    points=pipe_surface(rig['pipe']); edges=pipe_edges(); K=camera_matrix()
    for group in range(groups):
        center=rng.uniform([-3.8,-1.8,.7],[3.1,1.8,2.3])
        negative_count=2+group%2
        for variant in range(10):
            positive=variant>=negative_count
            # Balance six projected-angle bins independently in each split.
            desired_bin=(group+variant)%6
            for attempt in range(20000):
                xyz=center+rng.uniform([-.12,-.08,-.06],[.12,.08,.06])
                target=np.asarray(rig['pipe']['center'])-xyz
                heading=math.atan2(target[1],target[0]); pitch=-math.atan2(target[2],np.linalg.norm(target[:2]))
                yaw=heading+(rng.uniform(-math.pi/2,math.pi/2) if positive else math.pi+rng.uniform(-.3,.3))
                rpy=[rng.uniform(-math.pi,math.pi),np.clip(pitch+rng.uniform(-math.pi/4,math.pi/4),-math.pi/2+.05,math.pi/2-.05),yaw]
                geom=projected_geometry(points,camera_transform(xyz,rpy,rig['cameras']['left']),K,edges=edges)
                if positive and geom['primary'] and geom['angle_bin']==desired_bin: break
                if not positive and geom['bbox'] is None: break
            else: raise RuntimeError(f'Cannot sample group {group}, variant {variant}')
            yield {'id':f'o{group:03d}_v{variant:02d}','group':f'sim-o{group:03d}',
                   'split':partitions[group],'xyz':xyz.tolist(),'rpy':rpy,'positive':positive,'angle_bin':desired_bin if positive else None}


def replacement_view(view,rig,attempt):
    """Replace an ambiguous actual capture while preserving its group and quota."""
    seed=int.from_bytes(hashlib.sha256((view['id']+str(attempt)).encode()).digest()[:8],'little')
    rng=np.random.default_rng(seed); points=pipe_surface(rig['pipe']); edges=pipe_edges()
    for _ in range(20000):
        xyz=np.asarray(view['xyz'])+rng.uniform(-.02,.02,3); target=np.asarray(rig['pipe']['center'])-xyz
        rpy=[rng.uniform(-math.pi,math.pi),np.clip(-math.atan2(target[2],np.linalg.norm(target[:2]))+rng.uniform(-math.pi/4,math.pi/4),-math.pi/2+.05,math.pi/2-.05),math.atan2(target[1],target[0])+(rng.uniform(-math.pi/2,math.pi/2) if view['positive'] else math.pi)]
        geom=projected_geometry(points,camera_transform(xyz,rpy,rig['cameras']['left']),camera_matrix(),edges=edges)
        if view['positive'] and geom['primary'] and geom['angle_bin']==view['angle_bin']: return {**view,'xyz':xyz.tolist(),'rpy':rpy}
        if not view['positive'] and geom['bbox'] is None: return {**view,'xyz':xyz.tolist(),'rpy':rpy}
    raise RuntimeError('No replacement viewpoint for '+view['id'])
