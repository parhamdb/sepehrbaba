#!/usr/bin/env python3
"""Independently screen static image matches and fixed-lens relative cameras.

Per-pair feature holdouts are never used for fitting H or E. Tests compare the
same withheld observations against COLMAP, full DA3 and local VGGT. Relative
pose estimates have no metric scale and planar ambiguity is not certified away.
"""
import argparse,hashlib,importlib.util,json
from pathlib import Path
import cv2,numpy as np
from probe_gap_recovery import digest,write


def line_errors(E,x,y,K1,K2):
    F=np.linalg.inv(K2).T@E@np.linalg.inv(K1);a=np.c_[x,np.ones(len(x))];b=np.c_[y,np.ones(len(y))]
    l2=a@F.T;l1=b@F;v=np.abs(np.sum(b*l2,axis=1));n1=np.linalg.norm(l1[:,:2],axis=1);n2=np.linalg.norm(l2[:,:2],axis=1)
    return np.divide(v*(1/np.maximum(n1,1e-30)+1/np.maximum(n2,1e-30)),2)


def essential_from_poses(first,second):
    R=np.asarray(second['R'])@np.asarray(first['R']).T;t=np.asarray(second['t'])-R@np.asarray(first['t']);scale=np.linalg.norm(t)
    if not np.isfinite(scale) or scale<1e-30:return None
    t=t/scale;return np.array([[0,-t[2],t[1]],[t[2],0,-t[0]],[-t[1],t[0],0]])@R


def undistort(x,K,d):
    if not np.any(d):return np.asarray(x,np.float64)
    return cv2.undistortPoints(np.asarray(x,np.float64).reshape(-1,1,2),K,np.asarray(d),P=K).reshape(-1,2)


def error_summary(errors):
    errors=np.asarray(errors);finite=errors[np.isfinite(errors)]
    return dict(count=len(errors),finite=len(finite),median_px=float(np.median(finite)) if len(finite) else None,
                p90_px=float(np.percentile(finite,90)) if len(finite) else None,under_4px_fraction=float(np.mean(finite<4)) if len(finite) else None)


def camera_errors(first,second,x,y):
    if first['component']!=second['component']:return dict(status='different-component-gauges')
    E=essential_from_poses(first,second)
    if E is None:return dict(status='zero-baseline')
    K1=np.asarray(first['K']);K2=np.asarray(second['K'])
    return dict(status='evaluated',**error_summary(line_errors(E,undistort(x,K1,first['dist']),undistort(y,K2,second['dist']),K1,K2)))


def screen_pair(x,y,feature_ids,K,dist):
    x=np.asarray(x,np.float64);y=np.asarray(y,np.float64);ids=np.asarray(feature_ids,np.int64)
    hold=ids%5==0;fit=~hold
    result=dict(matches=len(x),fit=int(fit.sum()),withheld=int(hold.sum()),homography_passed=False,relative_pose_screen_passed=False,pose_accepted=False,withheld_indices=np.flatnonzero(hold).tolist())
    if fit.sum()<12 or hold.sum()<6:return dict(result,status='insufficient-independent-matches')
    hull=lambda v:float(cv2.contourArea(cv2.convexHull(v.astype(np.float32)))/(1080*1920))
    coverage=min(hull(x[hold]),hull(y[hold]));result['withheld_coverage']=coverage
    u=undistort(x,K,dist);v=undistort(y,K,dist);cv2.setRNGSeed(0)
    H,mask=cv2.findHomography(u[fit],v[fit],cv2.RANSAC,3.,maxIters=2000,confidence=.999)
    if H is not None and mask is not None and int(mask.sum())>=12 and abs(np.linalg.det(H))>1e-12:
        forward=cv2.perspectiveTransform(u[hold,None,:],H).reshape(-1,2);back=cv2.perspectiveTransform(v[hold,None,:],np.linalg.inv(H)).reshape(-1,2)
        err=.5*(np.linalg.norm(forward-v[hold],axis=1)+np.linalg.norm(back-u[hold],axis=1));summary=error_summary(err)
        passed=summary['finite']==len(err) and summary['median_px']<3.5 and summary['p90_px']<8 and coverage>=.005
        result.update(homography=H.tolist(),homography_fit_inliers=int(mask.sum()),homography_withheld=summary,homography_passed=bool(passed))
    E,mask=cv2.findEssentialMat(u[fit],v[fit],K,method=cv2.RANSAC,prob=.999,threshold=3.,maxIters=2000)
    if E is not None and mask is not None:
        candidates=[]
        for offset in range(0,E.shape[0],3):
            e=E[offset:offset+3]
            if e.shape!=(3,3):continue
            count,R,t,cheirality=cv2.recoverPose(e,u[fit],v[fit],K,mask=mask.copy())
            candidates.append((count,R,t,e))
        if candidates:
            count,R,t,e=max(candidates,key=lambda c:c[0]);summary=error_summary(line_errors(e,u[hold],v[hold],K,K))
            passed=count>=12 and summary['finite']==int(hold.sum()) and summary['median_px']<3.5 and summary['p90_px']<8 and coverage>=.005
            result.update(relative_pose=dict(R=R.tolist(),translation_direction=t.ravel().tolist()),essential=e.tolist(),pose_fit_positive_depth=int(count),pose_withheld=summary,relative_pose_screen_passed=bool(passed))
    result.update(status='evaluated',planar_explanation_supported=result['homography_passed'],limitation='Per-pair fits and holdouts, not an independently accepted multi-view trajectory. A supported homography makes planar pose ambiguity material; low epipolar error alone does not resolve it.')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('pairs','state','selection','reader','da3','vggt','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();cv2.setNumThreads(2)
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True)
    data=json.loads(a.pairs.read_text());selection=json.loads(a.selection.read_text());state=json.loads(a.state.read_text())
    if data['identity']['selection']!=digest(a.selection) or selection['identity']['state']!=digest(a.state):raise ValueError('Input identity mismatch')
    spec=importlib.util.spec_from_file_location('reader',a.reader);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    case=selection['cases']['gap-098'];methods={k:{} for k in ('colmap','da3','vggt')};calibrations={};models={}
    for direction,cfg in case['directions'].items():
        cid=cfg['component'];root=Path(next(c['path'] for c in state['components'] if c['id']==cid));images=reader.read_images_binary(root/'images.bin');cams=reader.read_cameras_binary(root/'cameras.bin')
        if len(cams)!=1:raise ValueError('One reference calibration required')
        cam=next(iter(cams.values()))
        if cam.model!='SIMPLE_RADIAL':raise ValueError('Expected SIMPLE_RADIAL')
        f,cx,cy,k=cam.params;K=np.array([[f,0,cx],[0,f,cy],[0,0,1.]]);dist=np.array([k,0.,0.,0.]);calibrations[direction]=dict(K=K.tolist(),dist=dist.tolist())
        models[cid]={name:digest(root/name) for name in ('images.bin','cameras.bin')}
        for im in images.values():
            if im.name not in data['frames']:continue
            R=reader.qvec2rotmat(im.qvec);methods['colmap'].setdefault(im.name,dict(R=R.tolist(),t=im.tvec.tolist(),K=K.tolist(),dist=dist.tolist(),component=cid))
    for method,path in (('da3',a.da3),('vggt',a.vggt)):
        for f in json.loads(path.read_text())['frames']:
            if f['name'] not in data['frames']:continue
            R=np.asarray(f['camera_to_world_rotation']).T;C=np.asarray(f['center'])
            methods[method][f['name']]=dict(R=R.tolist(),t=(-R@C).tolist(),K=f['intrinsics_native'],dist=[0.,0.,0.,0.],component=method)
    report=dict(identity={k:digest(getattr(a,k)) for k in ('pairs','state','selection','reader','da3','vggt')},model_sha256=models,script_sha256=digest(Path(__file__)),calibrations=calibrations,camera_counts={k:len(v) for k,v in methods.items()},pairs=[],status='running',accepted_poses=0)
    for pair in data['pairs']:
        first,second=pair['a'],pair['b'];matches=np.asarray(pair['matches'],int).reshape(-1,2);aidx,bidx=matches.T
        x=np.asarray(data['frames'][first]['xy']).reshape(-1,2)[aidx];y=np.asarray(data['frames'][second]['xy']).reshape(-1,2)[bidx];fids=np.asarray(data['frames'][first]['feature_ids'])[aidx]
        row=dict(a=first,b=second,variants={},existing={})
        for label,cal in calibrations.items():row['variants'][label]=screen_pair(x,y,fids,np.asarray(cal['K']),np.asarray(cal['dist']))
        hold=fids%5==0
        for method,poses in methods.items():
            row['existing'][method]=camera_errors(poses[first],poses[second],x[hold],y[hold]) if first in poses and second in poses and hold.any() else dict(status='unavailable')
        report['pairs'].append(row)
    report['status']='complete-pair-diagnostics-not-trajectory';write(a.output/'report.json',report)
    print(json.dumps(dict(camera_counts=report['camera_counts'],pairs=len(report['pairs']),homography_passes=sum(r['variants']['lookback']['homography_passed'] for r in report['pairs']),relative_pose_passes=sum(r['variants']['lookback']['relative_pose_screen_passed'] for r in report['pairs']))))


if __name__=='__main__':main()
