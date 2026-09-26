#!/usr/bin/env python3
"""Independent floor-only sparse localization trial with fixed reference cameras.

Build a small floor map from manually reviewed pre-gap polygons. Match it into
source frames without using a learned camera to select correspondences. Withhold
every fifth map landmark from PnP. Candidate results never certify a whole join.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from compare_camera_tracks import align_cameras, aligned_center


def project(xyz, pose):
    R=np.asarray(pose['R']);t=np.asarray(pose['t']);K=np.asarray(pose['K'])
    if not np.any(pose['dist']):
        camera=xyz@R.T+t;h=camera@K.T
        with np.errstate(divide='ignore',invalid='ignore'):
            return h[:,:2]/h[:,2,None],camera[:,2]
    if abs(K[0,1])>1e-10:raise ValueError('Distorted skew camera unsupported')
    r,_=cv2.Rodrigues(R)
    pixels,_=cv2.projectPoints(xyz,r,t,K,np.asarray(pose['dist']))
    return pixels.reshape(-1,2), (xyz@R.T+t)[:,2]


def triangulate(x,y,a,b):
    def rays(p,K,d):
        return cv2.undistortPoints(np.asarray(p,np.float64).reshape(-1,1,2),np.asarray(K),np.asarray(d)).reshape(-1,2)
    u=rays(x,a['K'],a['dist']);v=rays(y,b['K'],b['dist'])
    P=np.c_[a['R'],a['t']];Q=np.c_[b['R'],b['t']]
    h=cv2.triangulatePoints(P,Q,u.T,v.T).T
    with np.errstate(divide='ignore',invalid='ignore'):xyz=h[:,:3]/h[:,3,None]
    if not np.isfinite(xyz).all():
        xyz=np.nan_to_num(xyz,nan=1e15,posinf=1e15,neginf=-1e15)
    px,z=project(xyz,a);py,w=project(xyz,b)
    va=xyz-a['center'];vb=xyz-b['center']
    denom=np.linalg.norm(va,axis=1)*np.linalg.norm(vb,axis=1)
    angles=np.degrees(np.arccos(np.clip(np.sum(va*vb,axis=1)/np.maximum(denom,1e-30),-1,1)))
    keep=(z>0)&(w>0)&(angles>=1)&(np.linalg.norm(px-x,axis=1)<2)&(np.linalg.norm(py-y,axis=1)<2)
    return xyz,keep,angles


def matches(a,b):
    if a is None or b is None or len(a)<2 or len(b)<2:return []
    bf=cv2.BFMatcher()
    f=[p[0] for p in bf.knnMatch(a,b,k=2) if len(p)==2 and p[0].distance<.7*p[1].distance]
    r={p[0].queryIdx:p[0].trainIdx for p in bf.knnMatch(b,a,k=2) if len(p)==2 and p[0].distance<.7*p[1].distance}
    return [(m.queryIdx,m.trainIdx) for m in f if r.get(m.trainIdx)==m.queryIdx]


def localize(xyz,xy,ids,calibration):
    fit=ids%5!=0;hold=~fit
    result=dict(fit_matches=int(fit.sum()),withheld_matches=int(hold.sum()),passed=False)
    if fit.sum()<12 or hold.sum()<6:
        return dict(**result,reason='Need 12 fitting and six withheld floor landmarks')
    K=np.asarray(calibration['K']);dist=np.asarray(calibration['dist'])
    cv2.setRNGSeed(0)
    ok,r,t,inliers=cv2.solvePnPRansac(xyz[fit],xy[fit],K,dist,iterationsCount=1000,reprojectionError=3.,confidence=.999,flags=cv2.SOLVEPNP_EPNP)
    if not ok or inliers is None or len(inliers)<12:
        return dict(**result,reason='No 12-landmark PnP consensus')
    idx=inliers.ravel();r,t=cv2.solvePnPRefineLM(xyz[fit][idx],xy[fit][idx],K,dist,r,t)
    R,_=cv2.Rodrigues(r);t=t.ravel();pose=dict(R=R.tolist(),t=t.tolist(),center=(-R.T@t).tolist(),K=K.tolist(),dist=dist.tolist())
    uv,z=project(xyz[hold],pose);errors=np.linalg.norm(uv-xy[hold],axis=1)
    result.update(pose=pose,fit_inliers=len(idx),withheld_median_px=float(np.median(errors)),withheld_p90_px=float(np.percentile(errors,90)))
    result['passed']=bool((z>0).all() and np.median(errors)<3.5 and np.percentile(errors,90)<8)
    result['reason']='Experimental withheld-landmark screen; visual correspondence review still required'
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','selection','images','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    cv2.setNumThreads(2);cv2.setRNGSeed(0)
    data=json.load(gzip.open(a.inputs,'rt'));selection=json.loads(a.selection.read_text())
    case=next(c for c in data['cases'] if c['id']==selection['case']);ref=case['methods']['colmap']
    a.output.mkdir(parents=True)
    sift=cv2.SIFT_create(nfeatures=5000)
    image_hashes={}
    def features(name,polygon=None):
        im=cv2.imread(str(a.images/name),cv2.IMREAD_GRAYSCALE)
        if im is None or im.shape!=(1920,1080):raise ValueError('Missing native source image')
        image_hashes[name]=hashlib.sha256((a.images/name).read_bytes()).hexdigest()
        mask=None
        if polygon:
            mask=np.zeros(im.shape,np.uint8);cv2.fillPoly(mask,[np.asarray(polygon,np.int32)],255)
            # Exclude descriptor support near polygon boundaries.
            mask=cv2.erode(mask,np.ones((41,41),np.uint8))
            preview=cv2.cvtColor(im,cv2.COLOR_GRAY2BGR);cv2.polylines(preview,[np.asarray(polygon,np.int32)],True,(0,255,255),5)
            cv2.imwrite(str(a.output/(name.removesuffix('.jpg')+'-region.jpg')),cv2.resize(preview,(540,960)))
        keys,desc=sift.detectAndCompute(im,mask)
        return np.asarray([k.pt for k in keys]).reshape(-1,2),desc
    first,second=selection['anchors'];pa,pb=ref[first['name']],ref[second['name']]
    if pa['component']!=pb['component']:raise ValueError('Anchor gauge mismatch')
    if any(next(f['timestamp'] for f in case['frames'] if f['name']==s['name'])>=case['loss_time'] for s in (first,second)):
        raise ValueError('Map anchors must precede loss')
    x,d=features(first['name'],first['polygon']);y,e=features(second['name'],second['polygon'])
    pairs=matches(d,e);ia=np.array([i for i,j in pairs],int);ib=np.array([j for i,j in pairs],int)
    xyz,keep,angles=triangulate(x[ia],y[ib],pa,pb) if pairs else (np.empty((0,3)),np.zeros(0,bool),np.empty(0))
    xyz=xyz[keep];mapdesc=d[ia[keep]] if len(ia) else None
    ids=ia[keep] # Stable seed feature IDs, chosen before PnP or camera residuals.
    maps=dict(first_features=len(x),second_features=len(y),anchor_matches=len(pairs),landmarks=len(xyz),xyz=xyz.tolist(),ids=ids.tolist(),
              anchor_xy=x[ia[keep]].tolist(),second_xy=y[ib[keep]].tolist(),parallax_degrees=angles[keep].tolist())
    before=[f for f in case['frames'] if f['timestamp']<case['loss_time'] and f['name'] in ref and ref[f['name']]['component']==pa['component']]
    fits={m:align_cameras([case['methods'][m][f['name']] for f in before if f['name'] in case['methods'][m]],
                         [ref[f['name']] for f in before if f['name'] in case['methods'][m]]) for m in ('da3','vggt')}
    rows=[]
    # All gap frames plus one registered positive control after each map anchor.
    wanted=[f for f in case['frames'] if case['loss_time']<=f['timestamp']<case['gap_end'] or f['name'] in selection['controls']]
    for frame in wanted:
        if len(xyz):
            xy,desc=features(frame['name'])
        else:
            image_hashes[frame['name']]=hashlib.sha256((a.images/frame['name']).read_bytes()).hexdigest()
            xy,desc=np.empty((0,2)),None
        pairs=matches(mapdesc,desc);ii=np.array([i for i,j in pairs],int);jj=np.array([j for i,j in pairs],int)
        observations=xy[jj];world=xyz[ii];landmark_ids=ids[ii]
        row=dict(**frame,status='evaluated' if len(xyz) else 'blocked-no-floor-map',matches=len(pairs),landmark_ids=landmark_ids.tolist(),observations=observations.tolist(),
                 localization=localize(world,observations,landmark_ids,pa),learned_reprojection={})
        for m in ('da3','vggt'):
            pose=case['methods'][m].get(frame['name']);fit=fits[m]
            if not pose or not fit or not pairs:continue
            # Express the NN camera in COLMAP's gauge; retain its own calibration.
            R=np.asarray(pose['R'])@np.asarray(fit['rotation']).T;C=aligned_center(pose,fit)
            q=dict(pose,R=R.tolist(),t=(-R@C).tolist(),center=C.tolist())
            uv,z=project(world,q);errors=np.linalg.norm(uv-observations,axis=1)
            row['learned_reprojection'][m]=dict(median_px=float(np.median(errors)),positive_depth=int((z>0).sum()),matches=len(pairs),scope='Floor descriptor candidates, not manually certified correspondences')
        rows.append(row)
    report=dict(schema=1,case=case['id'],accepted_connection=False,
        inputs_sha256=hashlib.sha256(a.inputs.read_bytes()).hexdigest(),selection_sha256=hashlib.sha256(a.selection.read_bytes()).hexdigest(),
        image_sha256=image_hashes,versions=dict(numpy=np.__version__,opencv=cv2.__version__),map=maps,frames=rows,
        thresholds=dict(ratio=.7,min_parallax_deg=1.,max_anchor_reprojection_px=2.,min_fit=12,min_withheld=6,withheld_median_px=3.5,withheld_p90_px=8.),
        limits='Floor geometry uses fixed pre-gap COLMAP cameras. Descriptor correspondences may be wrong. PnP screening alone cannot certify continuity, planar pose ambiguity or absolute scale.')
    (a.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(map_landmarks=len(xyz),frames=len(rows),screen_passes=sum(r['localization']['passed'] for r in rows))))


if __name__=='__main__':main()
