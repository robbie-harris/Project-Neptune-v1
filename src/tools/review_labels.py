#!/usr/bin/env python3
"""Contact sheet for human verification of geometry-derived labels."""
import argparse
from pathlib import Path
import cv2
import numpy as np

def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,default=Path('data/pipe')); p.add_argument('--output',type=Path,default=Path('outputs/label-review.jpg')); p.add_argument('--count',type=int,default=12); p.add_argument('--prefix',default=''); args=p.parse_args()
    images=sorted(path for path in (args.data/'images').rglob('*') if path.suffix.lower() in {'.png','.jpg','.jpeg'} and path.stem.startswith(args.prefix))
    if not images: p.error('No captured images')
    indices=np.linspace(0,len(images)-1,min(args.count,len(images)),dtype=int); tiles=[]
    for i in indices:
        path=images[i]; frame=cv2.imread(str(path)); h,w=frame.shape[:2]
        label=(args.data/'labels'/path.relative_to(args.data/'images')).with_suffix('.txt').read_text().strip()
        for line in label.splitlines():
            _,cx,cy,bw,bh=map(float,line.split()); a=(round((cx-bw/2)*w),round((cy-bh/2)*h)); b=(round((cx+bw/2)*w),round((cy+bh/2)*h))
            cv2.rectangle(frame,a,b,(0,255,0),2)
        frame=cv2.resize(frame,(320,240)); cv2.putText(frame,path.stem+(' pipe' if label else ' negative'),(5,20),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1)
        tiles.append(frame)
    while len(tiles)%3: tiles.append(np.zeros_like(tiles[0]))
    sheet=np.vstack([np.hstack(tiles[i:i+3]) for i in range(0,len(tiles),3)])
    args.output.parent.mkdir(parents=True,exist_ok=True); cv2.imwrite(str(args.output),sheet)

if __name__=='__main__': main()
