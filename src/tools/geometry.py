"""Synthetic labeling only. Detector never imports this ground-truth module."""
import cv2
import numpy as np


def rotation_rpy(rpy):
    r,p,y=rpy; cr,sr=np.cos(r),np.sin(r); cp,sp=np.cos(p),np.sin(p); cy,sy=np.cos(y),np.sin(y)
    return np.array([[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr],
                     [sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr],[-sp,cp*sr,cp*cr]])


def camera_matrix(width=640,height=480,hfov=80):
    f=width/(2*np.tan(np.radians(hfov)/2))
    return np.array([[f,0,width/2],[0,f,height/2],[0,0,1]],dtype=np.float64)


def pipe_surface(pipe):
    angles=np.linspace(0,2*np.pi,181); axial=np.linspace(-pipe['length']/2,pipe['length']/2,17)
    # The baseline pipe runs along world +y; cylinder caps share the silhouette.
    return np.array([[pipe['center'][0]+pipe['radius']*np.cos(a),pipe['center'][1]+l,
                      pipe['center'][2]+pipe['radius']*np.sin(a)] for l in axial for a in angles])


class AmbiguousProjection(ValueError):
    """A capture that must be replaced rather than labeled negative."""


def pipe_edges():
    """Edges of the sampled convex cylinder used by pipe_surface."""
    edges=[]
    for j in range(17):
        for i in range(180):
            edges.append((j*181+i,j*181+i+1))
            if j<16: edges.append((j*181+i,(j+1)*181+i))
    return np.asarray(edges,dtype=int)


def projected_geometry(points,world_camera,K,width=640,height=480,edges=None,near=0.05):
    camera=(points-world_camera[:3,3])@world_camera[:3,:3]
    empty={'bbox':None,'visible_area':0.0,'angle_deg':None,'angle_bin':None,'partial':False,'primary':False}
    if camera[:,2].max()<near: return empty
    crossing=camera[:,2].min()<near
    if crossing:
        if edges is None: raise AmbiguousProjection('Camera-plane crossing requires geometry edges')
        a,b=camera[edges[:,0]],camera[edges[:,1]]
        intersects=(a[:,2]<near)!=(b[:,2]<near)
        a,b=a[intersects],b[intersects]
        t=(near-a[:,2])/(b[:,2]-a[:,2])
        camera=np.vstack([camera[camera[:,2]>=near],a+t[:,None]*(b-a)])
    uv,_=cv2.projectPoints(camera.astype(np.float64),np.zeros(3),np.zeros(3),K,np.zeros(5))
    uv=uv.reshape(-1,2)
    # Clip the projected convex silhouette, not its enclosing rectangle:
    # off-screen vertices must not enlarge the visible object's vertical bounds.
    hull=cv2.convexHull(uv.astype(np.float32))
    viewport=np.array([[0,0],[width,0],[width,height],[0,height]],dtype=np.float32)
    area,visible=cv2.intersectConvexConvex(hull,viewport)
    if visible is None or area<=0: return empty
    visible=visible.reshape(-1,2)
    # OpenCV intersections can exceed a viewport edge by float32 epsilon.
    visible[:,0]=np.clip(visible[:,0],0,width)
    visible[:,1]=np.clip(visible[:,1],0,height)
    x1,y1=visible.min(0); x2,y2=visible.max(0)
    if x2-x1<=0 or y2-y1<=0: raise AmbiguousProjection('Degenerate visible silhouette')
    rect=cv2.minAreaRect(hull); angle=(rect[2]+(90 if rect[1][1]>rect[1][0] else 0))%180
    bbox=[float(x1),float(y1),float(x2),float(y2)]
    return {'bbox':bbox,'visible_area':float(area),'angle_deg':float(angle),'angle_bin':min(5,int(angle//30)),
            'partial':bool(crossing or area<cv2.contourArea(hull)*.99),
            'primary':bool(x2-x1>=4 and y2-y1>=4 and area>=100)}


def projected_box(points,world_camera,K,width=640,height=480,edges=None):
    return projected_geometry(points,world_camera,K,width,height,edges)['bbox']


def yolo_label(box,width=640,height=480):
    if box is None: return ''
    x1,y1,x2,y2=box
    return f'0 {(x1+x2)/(2*width):.8f} {(y1+y2)/(2*height):.8f} {(x2-x1)/width:.8f} {(y2-y1)/height:.8f}\n'


def iou(a,b):
    import torch
    from ultralytics.utils.metrics import box_iou
    return float(box_iou(torch.tensor([a],dtype=torch.float32),torch.tensor([b],dtype=torch.float32))[0,0])
