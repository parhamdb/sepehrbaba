#!/usr/bin/env python3
"""Compare frozen cameras on identical observations; COLMAP is a reference, not truth.

Outputs distinguish coverage, gauge alignment and image agreement. LK corners
can lie on moving people; neither low epipolar error nor a smooth path proves
recovery. No estimated camera or original image is modified.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np

METHODS=('colmap','vggt','da3')


def rotation_angle(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R)-1)/2,-1,1))))


def align_cameras(source,target):
    """Gauge-only fit from pre-loss cameras: mean orientation, positive scale, offset."""
    if len(source)<5:return None
    A=np.mean([np.asarray(t['R']).T@np.asarray(s['R']) for s,t in zip(source,target)],axis=0)
    U,_,V=np.linalg.svd(A);Q=U@np.diag([1.,1.,np.linalg.det(U@V)])@V
    x=np.array([p['center'] for p in source]);y=np.array([p['center'] for p in target])
    xc=x-x.mean(0);yc=y-y.mean(0);den=float(np.sum(xc*xc))
    span=float(np.linalg.norm(np.ptp(y,axis=0)))
    if den<1e-14 or span<1e-8:return None
    scale=float(np.sum((xc@Q.T)*yc)/den)
    if scale<=0:return None
    offset=y.mean(0)-scale*Q@x.mean(0)
    residual=np.linalg.norm(scale*x@Q.T+offset-y,axis=1)
    return dict(rotation=Q.tolist(),scale=scale,offset=offset.tolist(),reference_span=span,
                fit_median_percent_span=float(np.median(residual)/span*100),anchor_frames=len(source))


def aligned_center(pose,alignment):
    return alignment['scale']*np.asarray(alignment['rotation'])@pose['center']+alignment['offset']


def essential(first,second):
    R1=np.asarray(first['R']);R2=np.asarray(second['R']);R=R2@R1.T
    t=np.asarray(second['t'])-R@first['t']
    norm=np.linalg.norm(t)
    if norm<1e-10:return None
    t=t/norm
    return np.array([[0,-t[2],t[1]],[t[2],0,-t[0]],[-t[1],t[0],0]])@R


def epipolar(first,second,x,y):
    """Symmetric point-to-epipolar-line distance in native undistorted pixels."""
    import cv2
    E=essential(first,second)
    if E is None:return None,None
    K1=np.asarray(first['K']);K2=np.asarray(second['K'])
    def undistort(points,K,dist):
        # OpenCV assumes zero input skew. VGGT's general projective cameras
        # have skew but no distortion, so preserve their pixel coordinates.
        if not np.any(dist):return np.asarray(points,np.float64)
        if abs(K[0,1])>1e-10:raise ValueError('Distorted skew camera requires a general calibration model')
        return cv2.undistortPoints(np.asarray(points,np.float64).reshape(-1,1,2),K,np.asarray(dist),P=K).reshape(-1,2)
    ux=undistort(x,K1,first['dist']);uy=undistort(y,K2,second['dist'])
    F=np.linalg.inv(K2).T@E@np.linalg.inv(K1)
    xh=np.c_[ux,np.ones(len(ux))];yh=np.c_[uy,np.ones(len(uy))]
    l2=xh@F.T;l1=yh@F;v=np.sum(yh*l2,axis=1)
    n1=np.linalg.norm(l1[:,:2],axis=1);n2=np.linalg.norm(l2[:,:2],axis=1)
    valid=(n1>1e-12)&(n2>1e-12)
    error=np.full(len(x),np.nan);error[valid]=abs(v[valid])*.5*(1/n1[valid]+1/n2[valid])
    foot=uy.copy();foot[valid]-=(v[valid]/n2[valid]**2)[:,None]*l2[valid,:2]
    if not np.any(second['dist']):return error,foot
    normfoot=np.c_[foot,np.ones(len(foot))]@np.linalg.inv(K2).T
    rawfoot,_=cv2.projectPoints(normfoot,np.zeros(3),np.zeros(3),K2,np.asarray(second['dist']))
    return error,rawfoot.reshape(-1,2)


def pair_schedule(case,methods):
    names=[f for f in case['frames'] if all(f['name'] in case['methods'][m] for m in methods)]
    pairs=[]
    for a,b in zip(names,names[1:]):
        if b['timestamp']-a['timestamp']>.75:continue
        if any(case['methods'][m][a['name']]['component']!=case['methods'][m][b['name']]['component'] for m in methods):continue
        pairs.append((a,b))
    return pairs


def track(images,first,second):
    import cv2
    def read(f):
        im=cv2.imread(str(images/f['name']),cv2.IMREAD_GRAYSCALE)
        if im is None:raise ValueError('Source image unreadable')
        if im.shape!=(1920,1080):raise ValueError('Native frame size changed')
        return cv2.resize(im,(540,960))
    im,jm=read(first),read(second)
    points=cv2.goodFeaturesToTrack(im,400,.02,12)
    if points is None:return np.empty((0,2)),np.empty((0,2))
    kw=dict(winSize=(25,25),maxLevel=4)
    q,ok,_=cv2.calcOpticalFlowPyrLK(im,jm,points,None,**kw)
    back,rev,_=cv2.calcOpticalFlowPyrLK(jm,im,q,None,**kw)
    keep=(ok.ravel()==1)&(rev.ravel()==1)&(np.linalg.norm(back-points,axis=2).ravel()<1)
    q=q.reshape(-1,2);points=points.reshape(-1,2)
    keep&=np.isfinite(q).all(1)&(q[:,0]>=0)&(q[:,0]<540)&(q[:,1]>=0)&(q[:,1]<960)
    return points[keep]*2,q[keep]*2


def summarize(rows,methods):
    valid=[r for r in rows if r['corners']>=20 and all(r['metrics'].get(m,{}).get('median_px') is not None for m in methods)]
    return dict(pairs=len(rows),supported_pairs=len(valid),methods={m:dict(
        median_pair_error_px=float(np.median([r['metrics'][m]['median_px'] for r in valid])) if valid else None,
        median_pair_under_4px_fraction=float(np.median([r['metrics'][m]['under_4px_fraction'] for r in valid])) if valid else None) for m in methods})


def analyze(case,images):
    methods=case['methods'];rows=[];cache={}
    # Shared triplets where possible; for the failed VGGT trial evaluate the other two.
    available=[m for m in METHODS if methods[m]]
    schedule=pair_schedule(case,available)
    # VGGT/DA3-only pairs also test the portion where COLMAP is absent, separately.
    gap_schedule=pair_schedule(case,['vggt','da3']) if methods['vggt'] else []
    chosen=[('shared',available,a,b) for a,b in schedule]
    chosen += [('gap',['vggt','da3'],a,b) for a,b in gap_schedule if a['name'] not in methods['colmap'] or b['name'] not in methods['colmap']]
    for group,participants,a,b in chosen:
        key=(a['name'],b['name'])
        if key not in cache:cache[key]=track(images,a,b)
        x,y=cache[key];metrics={};vectors={}
        for m in participants:
            if not len(x):metrics[m]=dict(median_px=None);continue
            error,foot=epipolar(methods[m][a['name']],methods[m][b['name']],x,y)
            valid=np.isfinite(error) if error is not None else np.zeros(len(x),bool)
            e=error[valid] if error is not None else []
            metrics[m]=dict(median_px=float(np.median(e)) if len(e) else None,
                            p90_px=float(np.percentile(e,90)) if len(e) else None,
                            under_4px_fraction=float(np.mean(e<4)) if len(e) else None)
            # Deterministic spatial subsample for visualization; never select by fit error.
            cells=set();sample=[]
            for i,point in enumerate(y):
                cell=tuple((point/[180,240]).astype(int))
                if not valid[i] or cell in cells:continue
                cells.add(cell);sample.append(dict(observed=point.tolist(),constraint=foot[i].tolist(),error_px=float(error[i])))
                if len(sample)==24:break
            vectors[m]=sample
        rows.append(dict(group=group,first=a['name'],second=b['name'],start=a['timestamp'],end=b['timestamp'],
                         phase='before' if b['timestamp']<case['loss_time'] else 'after-onset',corners=len(x),metrics=metrics,vectors=vectors))
    shared=[r for r in rows if r['group']=='shared'];gap=[r for r in rows if r['group']=='gap']
    anchors=[f for f in case['frames'] if f['timestamp']<case['loss_time'] and all(f['name'] in methods[m] for m in available)]
    components=Counter(methods['colmap'][f['name']]['component'] for f in anchors)
    component=components.most_common(1)[0][0] if components else None
    anchors=[f for f in anchors if methods['colmap'][f['name']]['component']==component]
    alignments={};agreement={}
    for m in METHODS:
        if m=='colmap':alignments[m]=dict(rotation=np.eye(3).tolist(),scale=1.,offset=[0.,0.,0.],reference_span=1.)
        else:alignments[m]=align_cameras([methods[m][f['name']] for f in anchors],[methods['colmap'][f['name']] for f in anchors]) if methods[m] else None
        fit=alignments[m]
        post=[f for f in case['frames'] if f['timestamp']>=case['gap_end'] and f['name'] in methods[m] and f['name'] in methods['colmap'] and methods['colmap'][f['name']]['component']==component]
        if m!='colmap' and fit and post:
            errors=[np.linalg.norm(aligned_center(methods[m][f['name']],fit)-methods['colmap'][f['name']]['center'])/fit['reference_span']*100 for f in post]
            angles=[rotation_angle(np.asarray(methods['colmap'][f['name']]['R'])@np.asarray(fit['rotation'])@np.asarray(methods[m][f['name']]['R']).T) for f in post]
            agreement[m]=dict(post_frames=len(post),median_position_percent_pre_span=float(np.median(errors)),median_orientation_deg=float(np.median(angles)))
        elif m!='colmap':agreement[m]=dict(post_frames=0,reason='No post-gap cameras in the same reference component, or insufficient pre-gap anchors')
    coverage={m:dict(total=len(methods[m]),before=sum(f['timestamp']<case['loss_time'] and f['name'] in methods[m] for f in case['frames']),
        after_onset=sum(f['timestamp']>=case['loss_time'] and f['name'] in methods[m] for f in case['frames']),
        during_baseline_gap=sum(case['loss_time']<=f['timestamp']<case['gap_end'] and f['name'] in methods[m] for f in case['frames']),
        components=len({p['component'] for p in methods[m].values()})) for m in METHODS}
    return dict(id=case['id'],start=case['start'],end=case['end'],loss_time=case['loss_time'],gap_end=case['gap_end'],
        source_frames=len(case['frames']),coverage=coverage,reference_component=component,anchor_names=[f['name'] for f in anchors],alignments=alignments,
        shared=summarize(shared,available),gap=summarize(gap,['vggt','da3']),post_gap_agreement=agreement,
        verdict='comparison only; independent static-landmark recovery verdict not established',pairs=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('inputs','images','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args()
    import cv2
    cv2.setNumThreads(2)
    data=json.load(gzip.open(a.inputs,'rt'));a.output.mkdir(parents=True,exist_ok=False);reports=[]
    for case in data['cases']:
        report=analyze(case,a.images)
        (a.output/(case['id']+'.json')).write_text(json.dumps(report,indent=2)+'\n');reports.append({k:v for k,v in report.items() if k!='pairs'})
        print(case['id'],json.dumps(report['shared']),flush=True)
    output=dict(schema=1,inputs_sha256=hashlib.sha256(a.inputs.read_bytes()).hexdigest(),methods=list(METHODS),
        limits='Identical image pairs and corners per comparison. Corners may move; COLMAP is not ground truth. No interpolated or cross-component poses.',cases=reports)
    (a.output/'report.json').write_text(json.dumps(output,indent=2)+'\n')


if __name__=='__main__':main()
