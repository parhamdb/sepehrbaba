#!/usr/bin/env python3
"""Independent image-flow/epipolar diagnostic, not a static-scene accuracy verdict.

Tracks corners forward and backward between estimated source frames, then tests
those image measurements against the supplied cameras. No camera is fitted here.
Moving people can violate the epipolar geometry; no automatic recovery verdict.
"""
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('poses','images','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args()
    import cv2
    import numpy as np
    cv2.setNumThreads(2)
    source=json.loads(a.poses.read_text());rows=[];previous=None
    for f in source['frames']:
        gray=cv2.imread(str(a.images/f['name']),cv2.IMREAD_GRAYSCALE)
        if gray is None:raise ValueError('Image unreadable')
        gray=cv2.resize(gray,(540,960))
        if previous:
            old,im=previous
            p0=cv2.goodFeaturesToTrack(im,500,.02,12)
            if p0 is not None:
                p1,ok,_=cv2.calcOpticalFlowPyrLK(im,gray,p0,None,winSize=(25,25),maxLevel=4)
                back,rev,_=cv2.calcOpticalFlowPyrLK(gray,im,p1,None,winSize=(25,25),maxLevel=4)
                keep=(ok.ravel()==1)&(rev.ravel()==1)&(np.linalg.norm(back-p0,axis=2).ravel()<1)
                x=p0.reshape(-1,2)[keep];y=p1.reshape(-1,2)[keep]
                R1=np.asarray(old['world_to_camera_rotation']);R2=np.asarray(f['world_to_camera_rotation'])
                t1=np.asarray(old['translation']);t2=np.asarray(f['translation'])
                R=R2@R1.T;t=t2-R@t1
                skew=np.array([[0,-t[2],t[1]],[t[2],0,-t[0]],[-t[1],t[0],0]])
                scale=np.diag([.5,.5,1.]);K1=scale@old['intrinsics_native'];K2=scale@f['intrinsics_native']
                F=np.linalg.inv(K2).T@skew@R@np.linalg.inv(K1)
                xh=np.c_[x,np.ones(len(x))];yh=np.c_[y,np.ones(len(y))]
                lines=xh@F.T;den=np.linalg.norm(lines[:,:2],axis=1)
                valid=np.isfinite(y).all(1)&(den>1e-12)&(y[:,0]>=0)&(y[:,0]<540)&(y[:,1]>=0)&(y[:,1]<960)
                distance=np.abs(np.sum(lines[valid]*yh[valid],axis=1))/den[valid]*2
                rows.append(dict(first=old['name'],second=f['name'],timestamp=f['timestamp'],
                    tracked_corners=int(len(x)),valid_epipolar_constraints=int(len(distance)),
                    median_source_pixels=float(np.median(distance)) if len(distance) else None,
                    p90_source_pixels=float(np.percentile(distance,90)) if len(distance) else None))
        previous=(f,gray)
    if a.output.exists():raise FileExistsError(a.output)
    a.output.write_text(json.dumps(dict(status='diagnostic only; corners include moving people; no static-landmark review',
        evaluation='forward-backward LK corners versus supplied-camera epipolar lines; no camera refitting',rows=rows),indent=2)+'\n')
    print(f'Checked {len(rows)} estimated-frame pairs',flush=True)


if __name__=='__main__':main()
