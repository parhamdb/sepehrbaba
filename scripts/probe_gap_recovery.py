#!/usr/bin/env python3
"""Read-only per-gap SIFT/LightGlue lookback/lookahead and fixed-calibration PnP trials.

Uses existing COLMAP descriptors and 3D landmarks. No database/model is modified.
Checkpoint after each gap. Resume requires identical inputs, code and options.
Passing PnP is a candidate: moving-object rejection and independent join review
are deliberately required before any reconstruction can consume its output.
"""
import argparse
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import time
import numpy as np
import cv2
from inventory_camera_gaps import inventory


def write(path, data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)


def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def select_anchors(component, times, boundary, direction):
    available=[n for n in component['names'] if 0 < direction*(times[n]-boundary)<=30]
    selected=[]
    # Distinct nearest and farther views, with seconds rather than frame counts.
    for lo,hi in ((0,10),(10,30)):
        group=sorted((n for n in available if lo < direction*(times[n]-boundary)<=hi),key=times.get)
        for n in (group[:1]+group[-1:]):
            if n not in selected:selected.append(n)
    return selected


def choose_reference(components, times, boundary, direction, policy='support'):
    ranked=[]
    for c in components:
        distances=[direction*(times[n]-boundary) for n in c['names'] if 0<direction*(times[n]-boundary)<=30]
        if len(distances)<2 or len(c['names'])<4:continue
        key=(len(distances),len(c['names']),c['id']) if policy=='support' else (-min(distances),len(distances),len(c['names']),c['id'])
        ranked.append((key,c))
    return max(ranked,key=lambda row:row[0])[1] if ranked else None


def unique_correspondences(rows):
    # Score-ordered, one 3D landmark and one distinct query location per row.
    output=[];ids=set();pixels=[]
    for row in sorted(rows,key=lambda r:-r['score']):
        xy=np.asarray(row['xy'])
        if row['id'] in ids or any(np.linalg.norm(xy-p)<3 for p in pixels):continue
        output.append(row);ids.add(row['id']);pixels.append(xy)
    return output


def localize(rows, K, dist):
    rows=unique_correspondences(rows)
    result=dict(matches=len(rows),passed=False)
    if len(rows)<18:return dict(result,reason='insufficient distinct correspondences')
    xyz=np.asarray([r['xyz'] for r in rows],np.float64);xy=np.asarray([r['xy'] for r in rows],np.float64)
    hold=np.array([r['id']%5==0 for r in rows]);fit=~hold
    result.update(fit_matches=int(fit.sum()),withheld_matches=int(hold.sum()))
    if fit.sum()<12 or hold.sum()<6:return dict(result,reason='need 12 fit and 6 withheld landmarks')
    # Normalize world coordinates to avoid dependence on arbitrary component scale.
    origin=np.median(xyz[fit],axis=0);scale=float(np.median(np.linalg.norm(xyz[fit]-origin,axis=1)))
    if scale<=1e-12:return dict(result,reason='degenerate landmark spread')
    local=(xyz-origin)/scale
    cv2.setRNGSeed(0)
    ok,r,t,idx=cv2.solvePnPRansac(local[fit],xy[fit],K,dist,iterationsCount=1000,
        reprojectionError=3,confidence=.999,flags=cv2.SOLVEPNP_EPNP)
    if not ok or idx is None or len(idx)<12:return dict(result,reason='no 12-landmark PnP consensus')
    r,t=cv2.solvePnPRefineLM(local[fit][idx[:,0]],xy[fit][idx[:,0]],K,dist,r,t)
    R,_=cv2.Rodrigues(r);t=t.ravel()*scale-R@origin
    uv,_=cv2.projectPoints(xyz[hold],r,t,K,dist);err=np.linalg.norm(uv.reshape(-1,2)-xy[hold],axis=1)
    positive=bool(((xyz[hold]@R.T+t)[:,2]>0).all())
    # Require held-out evidence to cover a nontrivial region of the image.
    coverage=float(cv2.contourArea(cv2.convexHull(xy[hold].astype(np.float32)))/(1080*1920))
    result.update(fit_inliers=len(idx),withheld_median_px=float(np.median(err)),
        withheld_p90_px=float(np.percentile(err,90)),withheld_coverage=coverage,
        passed=bool(positive and np.median(err)<3.5 and np.percentile(err,90)<8 and coverage>=.005))
    if result['passed']:
        result.update(pose=dict(R=R.tolist(),t=t.tolist(),center=(-R.T@t).tolist(),K=K.tolist(),dist=dist.tolist()),
            correspondences=rows)
    result['reason']='candidate only; static correspondence and independent camera review required'
    return result


def mask_indices(features, indices, distance):
    """Keep entire conservative descriptor support inside a proposed static region."""
    xy=features['kp'][indices,:2];h,w=distance.shape
    inside=(xy[:,0]>=0)&(xy[:,0]<w)&(xy[:,1]>=0)&(xy[:,1]<h)
    safe=indices[inside];pixels=features['kp'][safe,:2].astype(int)
    radius=np.maximum(8.,12.*features['scales'][safe])
    return safe[distance[pixels[:,1],pixels[:,0]]>=radius]


def verify_models(report, components):
    paths={c['id']:Path(c['path']) for c in components}
    checked={}
    for gap in report['gaps']:
        for cid,expected in gap.get('model_sha256',{}).items():
            if cid not in checked:checked[cid]={name:digest(paths[cid]/name) for name in expected}
            if checked[cid]!=expected:raise ValueError('Reference model changed; preserve this campaign and start a new output')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('state','frames','database','reader','lightglue','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--selection',type=Path,help='Frozen explicit anchors and query frames')
    p.add_argument('--masks',type=Path,help='SAM static-region masks for every selected image')
    p.add_argument('--descriptor',choices=['sift','aliked-at-sift'],default='sift')
    p.add_argument('--images',type=Path,help='Native images; required for ALIKED descriptors at existing SIFT locations')
    p.add_argument('--reference-policy',choices=['support','nearest'],default='support')
    p.add_argument('--gap-ids',nargs='*');p.add_argument('--max-keypoints',type=int,default=2048)
    a=p.parse_args()
    if a.masks and not a.selection:p.error('--masks requires --selection')
    if a.descriptor!='sift' and a.images is None:p.error('--images required for ALIKED')
    a.output.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(a.output/'.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    import torch
    cv2.setNumThreads(2);torch.set_num_threads(4)
    def module(name,path):
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    reader=module('colmap_reader',a.reader)
    import subprocess
    pin='eb42fee2d71449efb0aa5c10549752b5d75384d8'
    if subprocess.check_output(['git','-C',str(a.lightglue),'rev-parse','HEAD'],text=True).strip()!=pin:
        raise ValueError('Unexpected LightGlue revision')
    lg=module('gap_lightglue',a.lightglue/'lightglue/lightglue.py')
    matcher=lg.LightGlue(features='sift' if a.descriptor=='sift' else 'aliked',depth_confidence=-1,width_confidence=-1).eval().cuda()
    extractor=None
    if a.descriptor!='sift':
        import sys
        sys.path.insert(0,str(a.lightglue))
        from lightglue import ALIKED
        from lightglue.utils import load_image
        extractor=ALIKED(max_num_keypoints=a.max_keypoints).eval().cpu()
    state=json.loads(a.state.read_text());frames=json.loads(a.frames.read_text());times={f['name']:f['timestamp'] for f in frames}
    selection=json.loads(a.selection.read_text()) if a.selection else None
    inv=inventory(state,frames);wanted=a.gap_ids or (list(selection['cases']) if selection else inv['experiment_gap_ids'])
    if not set(wanted)<=set(inv['experiment_gap_ids']):raise ValueError('Unknown experiment gap')
    gaps=[g for g in inv['gaps'] if g['id'] in wanted]
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True)
    # Fingerprint content once for provenance; main database must be quiescent.
    if Path(str(a.database)+'-wal').exists() and Path(str(a.database)+'-wal').stat().st_size:
        raise ValueError('Use a checkpointed read-only database snapshot, not a nonempty WAL')
    identity={k:digest(getattr(a,k)) for k in ('state','frames','database','reader')}
    identity.update(script=digest(Path(__file__)),inventory_script=digest(Path(__file__).with_name('inventory_camera_gaps.py')),
                    lightglue=pin,max_keypoints=a.max_keypoints,gap_ids=wanted,reference_policy=a.reference_policy,descriptor=a.descriptor)
    if selection:
        if any(selection['identity'][k]!=identity[k] for k in ('state','frames')):raise ValueError('Selection input identity mismatch')
        identity['selection']=digest(a.selection)
        if not set(wanted)<=selection['cases'].keys():raise ValueError('Selection missing requested gaps')
    if a.masks:
        mask_manifest=json.loads((a.masks/'selection.json').read_text())
        if mask_manifest['selection_sha256']!=identity['selection']:raise ValueError('Masks from different selection')
        identity['mask_manifest']=digest(a.masks/'selection.json')
        identity['masks']={}
        for sample in selection['samples']:
            name=sample['name'];meta=json.loads((a.masks/(name+'.json')).read_text());actual=digest(a.masks/(name+'.png'))
            if meta['mask_sha256']!=actual or meta['source_sha256']!=selection['image_sha256'][name]:raise ValueError('Mask/source identity mismatch')
            identity['masks'][name]=actual
    path=a.output/'report.json'
    report=json.loads(path.read_text()) if path.exists() else dict(identity=identity,status='running',gaps=[],
        limitations=['Existing map landmarks may include moving people. No automatic joins.',
        'One shared calibration within each reference component; cross-component calibration is untested.',
        'Explicit boundary/midpoint queries when selection is supplied, otherwise midpoint and first return; not dense recovery.',
        'Masks are semantic proposals, not independently certified static geometry; landmark triangulation itself remains from the original map.'],started=time.time())
    if report['identity']!=identity:raise ValueError('Changed campaign inputs; use another output')
    verify_models(report,state['components'])
    for name,expected in report.get('image_sha256',{}).items():
        if digest(a.images/name)!=expected:raise ValueError('Source image changed')
    image_ids=dict(db.execute('select name,image_id from images'))
    @lru_cache(maxsize=32)
    def features(name):
        iid=image_ids[name]
        def array(table,dtype):
            row=db.execute(f'SELECT rows,cols,data FROM {table} WHERE image_id=?',(iid,)).fetchone()
            if row is None:return None
            nr,nc,blob=row;return np.frombuffer(blob,dtype).reshape(nr,nc)
        kp=array('keypoints',np.float32);d=array('descriptors',np.uint8)
        if kp is None or d is None:return None
        if len(kp)!=len(d):raise ValueError('Feature length mismatch')
        if kp.shape[1]==6:
            scales=(np.hypot(kp[:,2],kp[:,4])+np.hypot(kp[:,3],kp[:,5]))/2;oris=np.arctan2(kp[:,4],kp[:,2])
        elif kp.shape[1]==4:scales,oris=kp[:,2],kp[:,3]
        else:raise ValueError('Unsupported feature convention')
        d=d.astype(np.float32);d/=np.maximum(np.linalg.norm(d,axis=1,keepdims=True),1e-8)
        return dict(kp=kp,d=d,scales=scales,oris=oris)
    @lru_cache(maxsize=16)
    def mask_distance(name):
        path=a.masks/(name+'.png')
        if digest(path)!=identity['masks'][name]:raise ValueError('Mask changed during run')
        mask=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
        if mask is None or mask.shape!=(1920,1080):raise ValueError('Expected native static mask')
        # Pad zero to treat the image edge as an invalid descriptor boundary.
        return cv2.distanceTransform(np.pad((mask>0).astype(np.uint8),1),cv2.DIST_L2,5)[1:-1,1:-1]
    @lru_cache(maxsize=32)
    def learned_descriptors(name,indices):
        f=features(name);idx=np.asarray(indices,dtype=int)
        report.setdefault('image_sha256',{})[name]=digest(a.images/name)
        with torch.inference_mode():
            xy=torch.tensor(f['kp'][idx,:2].copy(),dtype=torch.float32)[None]
            image=load_image(a.images/name)
            if tuple(image.shape[-2:])!=(1920,1080):raise ValueError('Expected native portrait image')
            return extractor.describe(xy,image,resize=1920)[0].cpu().numpy()
    def feature_tensor(f,idx,name):
        desc=f['d'][idx] if extractor is None else learned_descriptors(name,tuple(idx.tolist()))
        values=dict(keypoints=f['kp'][idx,:2],descriptors=desc,scales=f['scales'][idx],oris=f['oris'][idx],image_size=np.array([1080,1920]))
        return {k:torch.tensor(v,dtype=torch.float32,device='cuda')[None] for k,v in values.items()}
    @lru_cache(maxsize=2)
    def model(cid):
        component=next(c for c in state['components'] if c['id']==cid);root=Path(component['path'])
        ims=reader.read_images_binary(root/'images.bin');points=reader.read_points3D_binary(root/'points3D.bin');cams=reader.read_cameras_binary(root/'cameras.bin')
        if len(cams)!=1:raise ValueError('This experiment requires shared intrinsics within each model')
        cam=next(iter(cams.values()))
        if cam.model!='SIMPLE_RADIAL' or (cam.width,cam.height)!=(1080,1920):raise ValueError('Expected native SIMPLE_RADIAL cameras')
        f,cx,cy,k=cam.params;K=np.array([[f,0,cx],[0,f,cy],[0,0,1.]])
        return ims,points,K,np.array([k,0.,0.,0.]),{name:digest(root/name) for name in ('cameras.bin','images.bin','points3D.bin')}
    completed={g['id'] for g in report['gaps']}
    for gap in gaps:
        if gap['id'] in completed:continue
        row=dict(id=gap['id'],midpoint=gap['midpoint'],after=gap['after'],trials=[],pair_counts=[])
        for direction,label,boundary in ((-1,'lookback',gap['first']['timestamp']),(1,'lookahead',gap['last']['timestamp'])):
            explicit=selection['cases'][gap['id']]['directions'].get(label) if selection else None
            component=(next(c for c in state['components'] if c['id']==explicit['component']) if explicit else None) if selection else choose_reference(state['components'],times,boundary,direction,a.reference_policy)
            if component is None:
                row['trials'].append(dict(direction=label,status='unsupported',reason='no four-view map with two reference cameras within 30 seconds'));continue
            cid=component['id']
            ims,points,K,dist,hashes=model(cid);anchors=explicit['anchors'] if explicit else select_anchors(component,times,boundary,direction)
            if any(n not in component['names'] or not 0<direction*(times[n]-boundary)<=30 for n in anchors):raise ValueError('Anchor violates component or time boundary')
            row.setdefault('model_sha256',{})[cid]=hashes
            controls=[n for n in component['names'] if n not in anchors and 0<direction*(times[n]-boundary)<=10]
            control=explicit['control'] if explicit else (min(controls,key=lambda n:abs(times[n]-boundary)) if controls else None)
            queries=[(q,q['kind']) for q in selection['cases'][gap['id']]['queries']] if selection else [(gap['midpoint'],'missing-midpoint')]+([(gap['after'],'registered-return')] if gap['after'] else [])
            if control and all(q['name']!=control for q,_ in queries):queries.append((dict(name=control,timestamp=times[control]),'positive-control'))
            for query,query_kind in queries:
                qname=query['name'];qf=features(qname)
                if qf is None:
                    row['trials'].append(dict(query=qname,direction=label,status='unsupported',reason='missing cached features'));continue
                qi=np.arange(len(qf['kp']))
                if a.masks:qi=mask_indices(qf,qi,mask_distance(qname))
                qi=qi[np.argsort(qf['scales'][qi],kind='stable')[-a.max_keypoints:]]
                if len(qi)<2:
                    row['trials'].append(dict(query=qname,query_kind=query_kind,direction=label,status='unsupported',reason='fewer than two features inside static descriptor support'));continue
                qt=feature_tensor(qf,qi,qname);ratio_method='sift' if extractor is None else 'aliked-ratio'
                collected={m:[] for m in (ratio_method,'lightglue')}
                for anchor in anchors:
                    if anchor==qname:continue
                    af=features(anchor);im=ims[image_ids[anchor]]
                    if af is None:continue
                    if len(im.point3D_ids)!=len(af['kp']) or np.max(np.abs(im.xys-af['kp'][:,:2]),initial=0)>.01:
                        raise ValueError('Map observation and database feature indices disagree')
                    ai=np.array([i for i,pid in enumerate(im.point3D_ids) if pid>=0 and pid in points and points[pid].error<=2.5 and len(points[pid].image_ids)>=3 and len(set(points[pid].image_ids)-{image_ids[qname]})>=3],int)
                    if a.masks:ai=mask_indices(af,ai,mask_distance(anchor))
                    ai=ai[np.argsort(af['scales'][ai],kind='stable')[-a.max_keypoints:]]
                    if len(ai)<2 or len(qi)<2:continue
                    at=feature_tensor(af,ai,anchor)
                    ad=at['descriptors'][0].cpu().numpy();qd=qt['descriptors'][0].cpu().numpy()
                    bf=cv2.BFMatcher();forward=bf.knnMatch(ad,qd,k=2);back=bf.knnMatch(qd,ad,k=2)
                    reverse={p[0].queryIdx:p[0].trainIdx for p in back if len(p)==2 and p[0].distance<.7*p[1].distance}
                    sift=[(p[0].queryIdx,p[0].trainIdx,1.-p[0].distance) for p in forward if len(p)==2 and p[0].distance<.7*p[1].distance and reverse.get(p[0].trainIdx)==p[0].queryIdx]
                    with torch.inference_mode():out=matcher(dict(image0=at,image1=qt))
                    pairs=out['matches'][0].cpu().numpy();scores=out['scores'][0].cpu().numpy()
                    for method,matched in ((ratio_method,sift),('lightglue',[(int(i),int(j),float(s)) for (i,j),s in zip(pairs,scores)])):
                        row['pair_counts'].append(dict(query=qname,anchor=anchor,method=method,matches=len(matched),direction=label))
                        for i,j,score in matched:
                            pid=int(im.point3D_ids[ai[i]])
                            collected[method].append(dict(id=pid,xyz=points[pid].xyz.tolist(),xy=qf['kp'][qi[j],:2].tolist(),
                                anchor=anchor,anchor_xy=im.xys[ai[i]].tolist(),score=float(score),seconds_from_boundary=abs(times[anchor]-boundary)))
                for method,rows in collected.items():
                    for window in (10,30):
                        result=localize([r for r in rows if r['seconds_from_boundary']<=window],K,dist)
                        row['trials'].append(dict(query=qname,query_kind=query_kind,
                            direction=label,method=method,window_seconds=window,component=cid,
                            query_in_reference_model=qname in component['names'],
                            evidence_role='control' if qname in component['names'] else 'recovery-candidate',**result))
        report['gaps'].append(row);report.update(updated=time.time(),status='running',completed_gaps=len(report['gaps']),total_gaps=len(gaps))
        write(path,report)
        print(f"{len(report['gaps'])}/{len(gaps)} {gap['id']} new_candidates={sum(t.get('passed',False) and t.get('evidence_role')=='recovery-candidate' for t in row['trials'])}",flush=True)
    verify_models(report,state['components'])
    if a.masks:
        for name,expected in identity['masks'].items():
            if digest(a.masks/(name+'.png'))!=expected:raise ValueError('Mask changed during experiment')
    for name,expected in report.get('image_sha256',{}).items():
        if digest(a.images/name)!=expected:raise ValueError('Source image changed during experiment')
    report.update(status='complete-candidates-not-certified',finished=time.time());write(path,report);db.close()


if __name__=='__main__':main()
