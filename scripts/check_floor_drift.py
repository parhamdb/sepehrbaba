#!/usr/bin/env python3
"""Floor-only diagnostics, without changing any camera, depth or reconstruction.

Plane comparisons assume a common level floor, not verified scene identity.
Feature correspondences are image-selected; repeated tiles can still mislead.
"""
import argparse, hashlib, json, gzip
from pathlib import Path
import cv2
import numpy as np
from compare_da3_full import as_pose, frozen_baseline
from check_static_floor_bridge import matches, project
from compare_da3_full import image_metrics


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def unique_locations(pairs, first, second, radius=3.):
    """One correspondence per spatial landmark, regardless of SIFT orientation."""
    kept=[]
    for i,j in pairs:
        if any(np.linalg.norm(first[i]-first[a])<radius or np.linalg.norm(second[j]-second[b])<radius for a,b in kept):continue
        kept.append((i,j))
    return kept


def world_points(xy, depth, K, C, R):
    """Camera-z depth and camera-to-world rotation; xy in depth-image pixels."""
    rays=np.c_[xy,np.ones(len(xy))]@np.linalg.inv(K).T
    return (rays*depth[:,None])@R.T+C


def plane_fit(points, camera, tolerance, seed=0):
    if len(points)<300:return None
    rng=np.random.default_rng(seed)
    x=points[rng.choice(len(points),min(4000,len(points)),replace=False)]
    best=np.zeros(len(x),bool)
    for _ in range(160):
        a,b,c=x[rng.choice(len(x),3,replace=False)];n=np.cross(b-a,c-a);norm=np.linalg.norm(n)
        if norm<1e-10:continue
        n/=norm;keep=abs((x-a)@n)<tolerance
        if keep.sum()>best.sum():best=keep
    if best.sum()<300 or best.mean()<.65:return None
    center=x[best].mean(0);_,_,v=np.linalg.svd(x[best]-center,full_matrices=False);n=v[-1]
    if n@(camera-center)<0:n=-n
    d=-float(n@center);height=float(n@camera+d)
    if height<=tolerance:return None
    return dict(normal=n.tolist(),offset=d,centroid=center.tolist(),camera_height=height,
                inlier_fraction=float(best.mean()),median_residual=float(np.median(abs(x[best]@n+d))))


def plane_difference(reference, candidate):
    n=np.array(reference['normal']);m=np.array(candidate['normal'])
    return dict(tilt_deg=float(np.degrees(np.arccos(np.clip(n@m,-1,1)))),
                signed_offset_camera_heights=float((n@candidate['centroid']+reference['offset'])/candidate['camera_height']))


def grid_mask(shape,K,C,R,reference):
    h,w=shape;y,x=np.indices(shape);xy=np.c_[x.ravel(),y.ravel()]
    rays=(np.c_[xy,np.ones(len(xy))]@np.linalg.inv(K).T)@R.T
    n=np.array(reference['normal']);origin=np.array(reference['centroid'])
    u=np.cross(n,[1,0,0] if abs(n[0])<.8 else [0,1,0]);u/=np.linalg.norm(u);v=np.cross(n,u)
    denominator=rays@n
    with np.errstate(divide='ignore',invalid='ignore'):distance=-(n@C+reference['offset'])/denominator
    points=C+np.nan_to_num(distance,nan=0,posinf=0,neginf=0)[:,None]*rays
    spacing=reference['camera_height']/2
    a=((points-origin)@u/spacing).reshape(h,w);b=((points-origin)@v/spacing).reshape(h,w)
    da=np.minimum(abs(a-np.round(a)),abs(b-np.round(b)))
    return (da<.015)&(distance.reshape(h,w)>0)&np.isfinite(distance.reshape(h,w))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('images','masks','inference','comparison','snapshot','native','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    cv2.setNumThreads(2);cv2.setRNGSeed(0)
    selection=json.loads((a.masks/'selection.json').read_text());data=json.loads((a.inference/'poses.json').read_text())
    baseline,_=frozen_baseline(a.snapshot,json.load(gzip.open(a.comparison,'rt')),a.native)
    sif=cv2.SIFT_create(nfeatures=2000);rows=[];cache={};reference=None
    for f in selection['samples']:
        i=f['index'];pose=data['frames'][i]
        assert pose['name']==f['name'] and pose['timestamp']==f['timestamp']
        image=cv2.imread(str(a.images/f['name']));mask=cv2.imread(str(a.masks/(f['name']+'.png')),0)
        if image is None or mask is None or image.shape[:2]!=mask.shape:raise ValueError('Missing image/mask')
        meta=json.loads((a.masks/(f['name']+'.json')).read_text());assert sha(a.images/f['name'])==meta['source_sha256']
        view=cv2.resize(image,(540,960));fm=cv2.erode(cv2.resize(mask,(540,960),interpolation=cv2.INTER_NEAREST),np.ones((15,15),np.uint8))
        npz=a.inference/'results_output'/f'frame_{i}.npz';z=np.load(npz)
        depth=z['depth'];K=z['intrinsics'];h,w=depth.shape
        assert (h,w)==(504,280)
        expected=np.diag([w/1080,h/1920,1])@np.asarray(pose['intrinsics_native'])
        if not np.allclose(K,expected,rtol=1e-4,atol=1e-3):raise ValueError('Depth/pose calibration mismatch')
        C=np.asarray(pose['center']);R=np.asarray(pose['camera_to_world_rotation'])
        small=cv2.erode(cv2.resize(mask,(w,h),interpolation=cv2.INTER_NEAREST),np.ones((7,7),np.uint8))>0
        valid=small&np.isfinite(depth)&(depth>0)&np.isfinite(z['conf'])
        if valid.any():valid &= z['conf']>=np.median(z['conf'][valid])
        yy,xx=np.where(valid);xyz=world_points(np.c_[xx,yy],depth[yy,xx],K,C,R)
        fit=plane_fit(xyz,C,float(np.median(depth[valid]))*.015,seed=i) if len(xyz) else None
        row=dict(**f,floor_fraction=meta['floor_fraction'],mask_sha256=sha(a.masks/(f['name']+'.png')),source_sha256=meta['source_sha256'],depth_sha256=sha(npz),
                 usable_depth_pixels=len(xyz),plane=fit,status='plane-proposal' if fit else 'insufficient-floor-plane',review_required=True)
        if fit and reference is None:reference=fit;reference_frame=f['name']
        if fit:row.update(plane_difference(reference,fit))
        keys,desc=sif.detectAndCompute(cv2.cvtColor(view,cv2.COLOR_BGR2GRAY),fm)
        xy=np.array([k.pt for k in keys]).reshape(-1,2)
        cache[i]=dict(view=view,xy=xy,desc=desc,depth=depth,K=K,C=C,R=R,pose=as_pose(pose),mask=fm)
        overlay=view.copy();visible=fm>0;overlay[visible]=(overlay[visible]*.7+np.array([220,180,0])*.3).astype('uint8')
        if reference:
            grid=grid_mask((h,w),K,C,R,reference)&small
            overlay[cv2.resize(grid.astype('uint8'),(540,960),interpolation=cv2.INTER_NEAREST)>0]=(0,255,255)
        cv2.rectangle(overlay,(0,0),(540,92),(0,0,0),-1)
        cv2.putText(overlay,f"{f['timestamp']:.2f}s | FLOOR PROPOSAL",(8,24),0,.65,(255,255,255),1)
        text=f"tilt {row['tilt_deg']:.1f}deg | offset {row['signed_offset_camera_heights']:.2f} heights" if fit else 'No supported plane: floor hidden / uncertain'
        cv2.putText(overlay,text,(8,51),0,.5,(255,255,255),1)
        cv2.putText(overlay,'Yellow: ONE fixed reference grid; not a correction',(8,77),0,.48,(255,255,255),1)
        row['image']=f'sample-{i}.jpg';cv2.imwrite(str(a.output/row['image']),overlay)
        rows.append(row)
    if reference is None:raise ValueError('No floor reference: inspect masks')
    lookup={r['index']:r for r in rows};anchor_ids=[pair[0] for pair in selection['pairs']]
    schedules=[(x,y,'nearby') for x,y in selection['pairs']]
    schedules += [(x,y,'across-segments') for n,x in enumerate(anchor_ids) for y in anchor_ids[n+1:] if lookup[y]['timestamp']-lookup[x]['timestamp']>=15]
    pairs=[];candidates=[]
    for first,second,kind in schedules:
        A=cache[first];B=cache[second];raw=matches(A['desc'],B['desc']);m=unique_locations(raw,A['xy'],B['xy'])
        result=dict(first=first,second=second,kind=kind,seconds_apart=lookup[second]['timestamp']-lookup[first]['timestamp'],raw_descriptor_matches=len(raw),matches=len(m),status='insufficient-matches',accepted_connection=False)
        if len(m)>=20:
            ids=np.array([j for j,k in m]);x=A['xy'][ids];y=B['xy'][[k for j,k in m]]
            hold=ids%5==0;train=~hold
            if train.sum()>=12 and hold.sum()>=4:
                H,ins=cv2.findHomography(x[train],y[train],cv2.RANSAC,3.,maxIters=2000,confidence=.999)
                if H is not None:
                    pred=cv2.perspectiveTransform(x[hold].astype('float32')[None],H)[0];err=np.linalg.norm(pred-y[hold],axis=1)
                    count=int(ins.sum());coverage=float(cv2.contourArea(cv2.convexHull(x[train][ins.ravel()>0].astype('float32')))/(540*960))
                    result.update(fit_matches=int(train.sum()),withheld_matches=int(hold.sum()),homography_inliers=count,homography_withheld_median_px=float(np.median(err)),homography_withheld_p90_px=float(np.percentile(err,90)),image_coverage=coverage,status='homography-rejected')
                    supported=count>=12 and coverage>=.005 and np.median(err)<3 and np.percentile(err,90)<8
                    if supported:
                        result['status']='image-consistent-proposal'
                        xy=x[hold];observed=y[hold];processed=xy*np.array([280/540,504/960]);ij=np.round(processed).astype(int);ij[:,0]=np.clip(ij[:,0],0,279);ij[:,1]=np.clip(ij[:,1],0,503)
                        depths=A['depth'][ij[:,1],ij[:,0]];ok=np.isfinite(depths)&(depths>0)
                        world=world_points(processed[ok],depths[ok],A['K'],A['C'],A['R'])
                        projection,zcam=project(world,B['pose']);projection/=2
                        residual=np.linalg.norm(projection-observed[ok],axis=1);front=zcam>0
                        result.update(da3_visible_withheld=int(front.sum()),da3_withheld_points=int(ok.sum()),da3_depth_reprojection_median_px=float(np.median(residual[front])) if front.any() else None)
                        result['epipolar']={'da3':image_metrics(A['pose'],B['pose'],x[hold]*2,y[hold]*2)}
                        na,nb=lookup[first]['name'],lookup[second]['name']
                        if na in baseline and nb in baseline and baseline[na]['component']==baseline[nb]['component']:
                            result['epipolar']['colmap']=image_metrics(baseline[na],baseline[nb],x[hold]*2,y[hold]*2)
                        candidates.append((result,x[hold],y[hold],projection,ok,front))
        pairs.append(result)
    # Render all nearby supported pairs, and the strongest 20 distant proposals.
    distant=sorted([c for c in candidates if c[0]['kind']=='across-segments'],key=lambda c:(-c[0]['homography_inliers'],c[0]['first'],c[0]['second']))[:20]
    chosen=[c for c in candidates if c[0]['kind']=='nearby']+distant
    for row,x,y,pred,ok,front in chosen:
        A=cache[row['first']];B=cache[row['second']];canvas=np.concatenate([A['view'],B['view']],axis=1)
        for n,(a1,b1) in enumerate(zip(x,y)):
            color=tuple(int(t) for t in np.random.default_rng(n).integers(80,255,3));cv2.circle(canvas,tuple(a1.astype(int)),4,color,2);cv2.circle(canvas,tuple((b1+[540,0]).astype(int)),4,color,2)
        for observed,estimated,visible in zip(y[ok],pred,front):
            if visible and np.isfinite(estimated).all() and np.max(abs(estimated))<10000:
                cv2.line(canvas,tuple((observed+[540,0]).astype(int)),tuple((estimated+[540,0]).astype(int)),(0,0,255),2)
        cv2.rectangle(canvas,(0,0),(1080,82),(0,0,0),-1)
        cv2.putText(canvas,f"{lookup[row['first']]['timestamp']:.2f}s -> {lookup[row['second']]['timestamp']:.2f}s | UNVERIFIED FLOOR MATCHES",(10,27),0,.65,(255,255,255),1)
        cv2.putText(canvas,'Dots: observed matches. Red lines: DA3 depth + camera prediction error.',(10,56),0,.65,(255,255,255),1)
        row['image']=f"pair-{row['first']}-{row['second']}.jpg";cv2.imwrite(str(a.output/row['image']),canvas)
    report=dict(schema=1,source_sha256=data['source_sha256'],poses_sha256=sha(a.inference/'poses.json'),selection_sha256=sha(a.masks/'selection.json'),
                mask_model=selection['method'],mask_checkpoint_sha256=selection['checkpoint_sha256'],reference_frame=reference_frame,samples=rows,pairs=pairs,
                summary=dict(samples=len(rows),plane_proposals=sum(r['plane'] is not None for r in rows),scheduled_pairs=len(pairs),nearby_proposals=sum(r['status']=='image-consistent-proposal' and r['kind']=='nearby' for r in pairs),distant_proposals=sum(r['status']=='image-consistent-proposal' and r['kind']=='across-segments' for r in pairs)),
                accepted_connections=0,limits='Masks and matches are proposals. Reference plane assumes one level floor; actual steps/slopes or bad depth can also cause disagreement. Plane checks cannot detect in-plane translation/yaw or absolute scale. Depth reprojection mixes camera and depth errors. Repeated tiles can produce false homographies. Epipolar errors are native pixels; homography and depth errors are at 540x960. No cameras or scenes corrected.')
    (a.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps(report['summary']),flush=True)


if __name__=='__main__':main()
