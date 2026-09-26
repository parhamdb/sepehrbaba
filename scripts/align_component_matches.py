#!/usr/bin/env python3
"""Robust B-to-A similarity from bridge candidates, with withheld landmarks.

Every fifth A point ID is excluded from fitting. Image pairs marked held-out
are also excluded from fitting. Reports geometric evidence; visual acceptance
and source-frame inspection remain required before publication.
"""
import argparse
import json
from pathlib import Path
import numpy as np


def similarity(x,y):
    mx=x.mean(0);my=y.mean(0);xx=x-mx;yy=y-my
    u,s,vh=np.linalg.svd(xx.T@yy)
    signs=np.array([1.,1.,np.linalg.det(vh.T@u.T)])
    r=(vh.T*signs)@u.T
    scale=(s*signs).sum()/np.square(xx).sum()
    return scale,r,my-scale*r@mx


def residual(x,y,model):
    s,r,t=model
    return np.linalg.norm(s*x@r.T+t-y,axis=1)


def ransac(x,y,threshold,rng,trials=1024):
    if len(x)<6:return None
    best=None;count=0
    for _ in range(trials):
        ids=rng.choice(len(x),3,replace=False)
        if np.linalg.norm(np.cross(x[ids[1]]-x[ids[0]],x[ids[2]]-x[ids[0]]))<1e-7:continue
        model=similarity(x[ids],y[ids])
        if not .02<model[0]<50:continue
        keep=residual(x,y,model)<threshold
        if keep.sum()>count:best=model;count=keep.sum()
    if count<6:return None
    for _ in range(3):
        keep=residual(x,y,best)<threshold
        if keep.sum()<6:return None
        best=similarity(x[keep],y[keep])
    return best


def project(x,camera):
    xc=x@np.array(camera['R']).T+camera['t']
    fx,fy,cx,cy=camera['params']
    return xc[:,:2]/xc[:,2,None]*[fx,fy]+[cx,cy],xc[:,2]


def unique(a,b):
    return np.unique(np.stack([a,b],axis=1),axis=0,return_index=True)[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('matches',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--threshold',type=float,default=.03)
    a=p.parse_args()
    if a.output.exists() or a.threshold<=0:raise ValueError('Fresh output and positive threshold required')
    report=json.loads((a.matches/'matches.json').read_text());pairs=[];fit=[];candidates=[];rng=np.random.default_rng(0)
    for info in report['pairs']:
        data=dict(np.load(a.matches/info['file']));pairs.append((info,data))
        keep=(data['ids_a']%5!=0)&(info['split']=='fit')
        if keep.any():
            fit.append({k:v[keep] for k,v in data.items()})
            model=ransac(data['xyz_b'][keep],data['xyz_a'][keep],a.threshold,rng)
            if model is not None:candidates.append(model)
    if not fit:raise ValueError('No fit correspondences')
    pool={k:np.concatenate([d[k] for d in fit]) for k in fit[0]}
    ids=unique(pool['ids_a'],pool['ids_b']);pool={k:v[ids] for k,v in pool.items()}
    if not candidates:
        a.output.write_text(json.dumps({'accepted_geometry':False,'reason':'No six-point pair consensus','fit_unique_pairs':len(ids)},indent=2)+'\n');return
    best=max(candidates,key=lambda m:int((residual(pool['xyz_b'],pool['xyz_a'],m)<a.threshold).sum()))
    for _ in range(5):
        keep=residual(pool['xyz_b'],pool['xyz_a'],best)<a.threshold
        best=similarity(pool['xyz_b'][keep],pool['xyz_a'][keep])
    s,r,t=best;summary=[];held=[];fit_keep=residual(pool['xyz_b'],pool['xyz_a'],best)<a.threshold
    for info,data in pairs:
        xa=data['xyz_a'];xb=data['xyz_b'];aligned=s*xb@r.T+t
        distance=residual(xb,xa,best)
        pa,za=project(aligned,report['cameras_a'][info['a']])
        pb,zb=project((xa-t)@r/s,report['cameras_b'][info['b']])
        ea=np.linalg.norm(pa-data['xy_a'],axis=1);eb=np.linalg.norm(pb-data['xy_b'],axis=1)
        good=(distance<a.threshold)&(za>0)&(zb>0)&(ea<8)&(eb<8)
        hold=good&(data['ids_a']%5==0)
        held.append({'ids_a':data['ids_a'][hold],'ids_b':data['ids_b'][hold],'errors':np.maximum(ea,eb)[hold],'distance':distance[hold]})
        summary.append({**info,'consistent_matches':int(good.sum()),'withheld_landmark_matches':int(hold.sum()),
                        'median_reprojection_px':float(np.median(np.maximum(ea,eb)[good])) if good.any() else None})
    hh={k:np.concatenate([d[k] for d in held]) for k in held[0]};ui=unique(hh['ids_a'],hh['ids_b'])
    enough_pairs=[p for p in summary if p['consistent_matches']>=15]
    held_image_pairs=[p for p in enough_pairs if p['split']=='held-out']
    checks={'fit_at_least_50_unique_pairs':int(fit_keep.sum())>=50,
            'withheld_at_least_20_unique_landmarks':len(ui)>=20,
            'at_least_three_held_out_image_pairs':len(held_image_pairs)>=3,
            'at_least_three_views_each':len({p['a'] for p in enough_pairs})>=3 and len({p['b'] for p in enough_pairs})>=3,
            'withheld_median_reprojection_below_3_5px':bool(len(ui) and np.median(hh['errors'][ui])<3.5)}
    result={'accepted_geometry':all(checks.values()),'checks':checks,'visual_acceptance':'pending',
        'mapping':'raw COLMAP B coordinates to raw COLMAP A: x_a = scale * R * x_b + translation',
        'scale':float(s),'rotation':r.tolist(),'translation':t.tolist(), 'threshold_a_scene_units':a.threshold,
        'fit_unique_pairs':len(ids),'fit_inliers':int(fit_keep.sum()),'withheld_unique_landmarks':len(ui),
        'withheld_reprojection_median_px':float(np.median(hh['errors'][ui])) if len(ui) else None,
        'withheld_distance_median':float(np.median(hh['distance'][ui])) if len(ui) else None,
        'held_out_image_pairs_with_15_inliers':len(held_image_pairs),
        'pairs':sorted(summary,key=lambda p:p['consistent_matches'],reverse=True)}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='pairs'},indent=2))
    print('Best pairs:',result['pairs'][:5])


if __name__=='__main__':main()
