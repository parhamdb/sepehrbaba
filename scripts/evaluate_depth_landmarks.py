#!/usr/bin/env python3
"""Depth-aware candidate camera checks for six human-selected correspondences.

Fits seed views only, then uses existing within-side DA3 motion for withheld
views. No interpolation across the gap and no accepted section alignment.
"""
import argparse, hashlib, json
from pathlib import Path
import cv2
import numpy as np


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def array(v):return np.asarray(v,dtype=np.float64)


def project(X,R,t,K):
    camera=X@R.T+t
    uv=camera@K.T
    return uv[:,:2]/uv[:,2:],camera[:,2]


def solve(X,xy,K):
    ok,r,t=cv2.solvePnP(X,xy,K,None,flags=cv2.SOLVEPNP_SQPNP)
    if not ok:return None
    r,t=cv2.solvePnPRefineLM(X,xy,K,None,r,t)
    R=cv2.Rodrigues(r)[0];t=t[:,0]
    uv,z=project(X,R,t,K)
    return dict(R=R.tolist(),t=t.tolist(),projected_xy=uv.tolist(),error_px=np.linalg.norm(uv-xy,axis=1).tolist(),positive_depth=(z>0).tolist())


def depths(root,frame,xy):
    p=root/'results_output'/frame['depth_file']
    if sha(p)!=frame['depth_sha256']:raise ValueError('Depth cache changed')
    rows=[]
    with np.load(p) as d:
        h,w=d['depth'].shape
        for point in xy:
            # Same coordinate scaling as DA3's exported intrinsic matrix.
            u,v=point*array([w/1080,h/1920]);x,y=int(round(u)),int(round(v))
            if not (0<=x<w and 0<=y<h):rows.append(None);continue
            patch=d['depth'][max(0,y-1):min(h,y+2),max(0,x-1):min(w,x+2)]
            conf=d['conf'][max(0,y-1):min(h,y+2),max(0,x-1):min(w,x+2)]
            good=patch[np.isfinite(patch)&(patch>0)]
            if not len(good):rows.append(None);continue
            z=float(np.median(good));mad=float(np.median(np.abs(good-z))/z)
            rows.append(dict(depth=z,relative_mad=mad,confidence_median=float(np.median(conf)),confidence_image_percentile=float(100*np.mean(d['conf']<=np.median(conf))),depth_xy=[float(u),float(v)]))
    return rows


def unproject(xy,z,K):return (np.c_[xy,np.ones(len(xy))]@np.linalg.inv(K).T)*z[:,None]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('experiment-dir','da3','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();root=a.experiment_dir
    if a.output.exists():p.error('Output exists; preserve the earlier run')
    cfg=read(root/'experiment.json');limit=cfg['thresholds'];sides={}
    for side,info in cfg['sides'].items():
        track=read(root/f'{side}-tracks.json');seed=read(root/f'{side}-seed.json')
        if [r['name'] for r in track['frames']]!=[r['name'] for r in info['frames']]:raise ValueError('Track/frame order mismatch')
        if track['seed_frame']!=info['seed_frame']:raise ValueError('Wrong tracker seed')
        # A forced reverse endpoint is not validation: require return to the original seed too.
        trajectory_ok=np.array([q['predicted_visible'] and q['reverse_seed_predicted_visible'] and q['cycle_error_native_px']<=limit['track_cycle_native_px'] for q in track['target_predictions']])
        rows=[]
        for frame,tr in zip(info['frames'],track['frames']):
            xy=array(tr['xy']);cycle=np.linalg.norm(xy-array(tr['reverse_xy']),axis=1)
            visible=np.array(tr['predicted_visible'])&np.array(tr['reverse_predicted_visible'])
            x0,y0,x1,y1=info['crop_xyxy']
            visible &= (xy[:,0]>=x0)&(xy[:,0]<x1)&(xy[:,1]>=y0)&(xy[:,1]<y1)
            rows.append(dict(**frame,xy=xy.tolist(),cycle_error_px=cycle.tolist(),usable_track=(trajectory_ok&visible&(cycle<=limit['track_cycle_native_px'])).tolist(),depth_samples=depths(a.da3,frame,xy)))
        sides[side]=dict(seed_index=info['seed_index'],seed_frame=info['seed_frame'],seed_xy=[[q['x'],q['y']] for q in seed['points']],frames=rows,tracker_identity=track['identity'],endpoint_cycle=track['target_predictions'])
    allK=array([r['intrinsics_native'] for s in sides.values() for r in s['frames']]);sharedK=np.median(allK,axis=0)
    fits={};cv2.setRNGSeed(20260927)
    for source,target in [('before','after'),('after','before')]:
        sf=sides[source];tf=sides[target];s0=sf['frames'][sf['seed_index']];t0=tf['frames'][tf['seed_index']]
        sxy=array(sf['seed_xy']);txy=array(tf['seed_xy'])
        # Query pixels are the exact human-reviewed detector coordinates, not a refined tracker guess.
        seed_depths=depths(a.da3,s0,sxy)
        if any(d is None for d in seed_depths):raise ValueError('Missing seed depth')
        z=array([d['depth'] for d in seed_depths]);unit=float(np.median(z))
        name=source+'_to_'+target;variants={}
        for variant in ['shared_lens','cached_lens']:
            Ks=sharedK if variant=='shared_lens' else array(s0['intrinsics_native'])
            Kt=sharedK if variant=='shared_lens' else array(t0['intrinsics_native'])
            X=unproject(sxy,z,Ks)/unit
            fit=solve(X,txy,Kt)
            held=[]
            for j in range(6):
                keep=np.arange(6)!=j;candidate=solve(X[keep],txy[keep],Kt)
                if candidate is None:held.append(None);continue
                uv,zz=project(X[j:j+1],array(candidate['R']),array(candidate['t']),Kt)
                held.append(dict(id=f'Q{j+1}',error_px=float(np.linalg.norm(uv[0]-txy[j])),positive_depth=bool(zz[0]>0)))
            variants[variant]=dict(fit=fit,held_out=held,source_points_3d=X.tolist(),source_K=Ks.tolist(),target_K=Kt.tolist(),seed_depth_samples=seed_depths,arbitrary_depth_unit=unit)
        primary=variants['shared_lens'];fit=primary['fit'];X=array(primary['source_points_3d'])
        Rs=array(s0['camera_to_world_rotation']);Cs=array(s0['center']);Rt=array(t0['camera_to_world_rotation']);Ct=array(t0['center'])
        temporal=[];local=[]
        for i,row in enumerate(tf['frames']):
            Rj=array(row['camera_to_world_rotation']);Cj=array(row['center'])
            if fit is not None:
                seed_camera=X@array(fit['R']).T+array(fit['t'])
                in_frame=seed_camera@(Rj.T@Rt).T+(Rj.T@(Ct-Cj))/unit
                uv,zz=project(in_frame,np.eye(3),np.zeros(3),sharedK)
                err=np.linalg.norm(uv-array(row['xy']),axis=1)
                samples=row['depth_samples'];relative=[float(abs(zz[j]*unit-d['depth'])/d['depth']) if d else None for j,d in enumerate(samples)]
                valid=[bool(row['usable_track'][j] and d is not None and d['relative_mad']<=limit['depth_patch_relative_mad'] and zz[j]>0) for j,d in enumerate(samples)]
                temporal.append(dict(name=row['name'],timestamp=row['timestamp'],seed_view=i==tf['seed_index'],observed_xy=row['xy'],projected_xy=uv.tolist(),positive_depth=(zz>0).tolist(),error_px=err.tolist(),usable_track=row['usable_track'],valid_for_diagnostic=valid,relative_depth_difference=relative))
        for i,row in enumerate(sf['frames']):
            Rj=array(row['camera_to_world_rotation']);Cj=array(row['center'])
            # Local consistency of depth points with the existing source camera motion.
            in_frame=X@(Rj.T@Rs).T+(Rj.T@(Cs-Cj))/unit
            uv,zz=project(in_frame,np.eye(3),np.zeros(3),sharedK)
            local.append(dict(name=row['name'],timestamp=row['timestamp'],seed_view=i==sf['seed_index'],observed_xy=row['xy'],projected_xy=uv.tolist(),positive_depth=(zz>0).tolist(),error_px=np.linalg.norm(uv-array(row['xy']),axis=1).tolist(),usable_track=row['usable_track']))
        vals=[e for row in temporal if not row['seed_view'] for e,good in zip(row['error_px'],row['valid_for_diagnostic']) if good]
        localvals=[e for row in local if not row['seed_view'] for e,good,zgood in zip(row['error_px'],row['usable_track'],row['positive_depth']) if good and zgood]
        depthvals=[d for row in temporal if not row['seed_view'] for d,good in zip(row['relative_depth_difference'],row['valid_for_diagnostic']) if good and d is not None]
        goodfit=fit is not None and all(fit['positive_depth']) and max(fit['error_px'])<=limit['reprojection_native_px']
        heldpass=all(h is not None and h['positive_depth'] and h['error_px']<=limit['reprojection_native_px'] for h in primary['held_out'])
        fits[name]=dict(source_side=source,target_side=target,variants=variants,temporal=temporal,source_local=local,summary=dict(seed_all_six_pass=goodfit,held_out_all_six_pass=heldpass,temporal_usable_samples=len(vals),temporal_median_error_px=float(np.median(vals)) if vals else None,temporal_max_error_px=float(max(vals)) if vals else None,source_local_median_error_px=float(np.median(localvals)) if localvals else None,temporal_depth_median_relative_difference=float(np.median(depthvals)) if depthvals else None,temporal_depth_samples_within_limit=sum(d<=limit['temporal_depth_relative_difference'] for d in depthvals)),accepted_connection=False)
    # Compare independently fitted forward and reverse transforms, not a forced inverse.
    f=fits['before_to_after']['variants']['shared_lens'];b=fits['after_to_before']['variants']['shared_lens']
    closure=None
    if f['fit'] and b['fit']:
        Rf=array(f['fit']['R']);Rb=array(b['fit']['R']);ratio=f['arbitrary_depth_unit']/b['arbitrary_depth_unit']
        angle=float(np.degrees(np.arccos(np.clip((np.trace(Rb@Rf)-1)/2,-1,1))))
        closure=dict(rotation_degrees=angle,translation_in_source_median_depth_units=(Rb@array(f['fit']['t'])+array(b['fit']['t'])/ratio).tolist())
    output=dict(method='Human seeds + cached DA3 depth + CoTracker3 local tracks + SQPnP/LM; diagnostic hypothesis only',shared_K=sharedK.tolist(),sides=sides,fits=fits,forward_reverse_closure=closure,opencv_version=cv2.__version__,numpy_version=np.__version__,thresholds=limit,identity=dict(script_sha256=sha(Path(__file__)),experiment_sha256=sha(root/'experiment.json')),independent_static_validation=cfg['independent_static_landmarks'],accepted_connection=False,limitations=['Cached DA3 poses/depth and temporal checks are model-dependent, not independent ground truth.','All six physical points are clustered in one flexible region. No independent static cross-gap landmark is verified.','Depth units are arbitrary. Cached confidence is a score, not probability.','Tracking cycles and visibility are model diagnostics; failed tracks remain visible as unreliable observations.','No interpolated camera path is generated inside the missing interval.'])
    save(a.output,output)
    print(json.dumps({k:v['summary'] for k,v in fits.items()}))

if __name__=='__main__':main()
