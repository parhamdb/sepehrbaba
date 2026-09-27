#!/usr/bin/env python3
"""Align separate native COLMAP components using masked cross-gap landmarks.

Gap images are never used. Split entire bipartite landmark groups before fitting;
conflicting one-to-many groups are rejected rather than leaking landmarks across
folds. Existing maps and camera calibrations remain fixed and are not ground truth.
"""
import argparse, hashlib, importlib.util, itertools, json
from pathlib import Path
import cv2
import numpy as np
from probe_gap_recovery import digest, write
from check_static_floor_bridge import project, triangulate
from triangulate_static_gap import assemble_tracks
from evaluate_local_camera_pairs import screen_pair


def similarity(x,y):
    x=np.asarray(x,float);y=np.asarray(y,float)
    cx=x.mean(0);cy=y.mean(0);u=x-cx;v=y-cy
    U,D,Vt=np.linalg.svd(v.T@u/len(x));sign=np.ones(3);sign[-1]=np.linalg.det(U@Vt)
    if D[0]<=0 or D[1]/D[0]<1e-5:raise ValueError('Collinear or coincident geometry')
    R=U@np.diag(sign)@Vt;s=float((D*sign).sum()/np.mean(np.sum(u*u,axis=1)))
    if not np.isfinite(s) or s<=0:raise ValueError('Invalid positive scale')
    return s,R,cy-s*R@cx


def apply(x,model):
    s,R,t=model;return s*np.asarray(x)@R.T+t


def unique_groups(rows):
    """Deduplicate repeated observations and discard all conflicting ID groups."""
    graph={}
    for r in rows:
        a=('a',r['id_a']);b=('b',r['id_b']);graph.setdefault(a,set()).add(b);graph.setdefault(b,set()).add(a)
    good=[];conflicts=0
    while graph:
        todo=[next(iter(graph))];component=set()
        while todo:
            n=todo.pop()
            if n in component:continue
            component.add(n);todo.extend(graph[n]-component)
        aa=[n[1] for n in component if n[0]=='a'];bb=[n[1] for n in component if n[0]=='b']
        for n in component:del graph[n]
        if len(aa)!=1 or len(bb)!=1:conflicts+=1;continue
        observations=[r for r in rows if r['id_a']==aa[0] and r['id_b']==bb[0]]
        # Entire physical landmark correspondence has one fold, across all views.
        held=int(hashlib.sha256(('a:'+str(aa[0])).encode()).hexdigest()[:8],16)%5==0
        good.append(dict(id_a=aa[0],id_b=bb[0],held=held,observations=observations))
    return good,conflicts


def screen_similarity(groups):
    train=[g for g in groups if not g['held']];held=[g for g in groups if g['held']]
    out=dict(fit_landmarks=len(train),withheld_landmarks=len(held),screen_passed=False)
    if len(train)<12 or len(held)<6:return dict(out,reason='Need 12 distinct fit and six withheld landmark groups')
    x=np.array([g['observations'][0]['xyz_a'] for g in train]);y=np.array([g['observations'][0]['xyz_b'] for g in train]);rng=np.random.default_rng(0);best=None
    # Coordinates have been normalized by each component's camera extent.
    for _ in range(2000):
        idx=rng.choice(len(x),3,replace=False)
        try:model=similarity(x[idx],y[idx])
        except ValueError:continue
        error=np.linalg.norm(apply(x,model)-y,axis=1);mask=error<.03
        score=(int(mask.sum()),-float(np.median(error[mask])) if mask.any() else -1e30)
        if best is None or score>best[0]:best=(score,mask,model)
    if best is None or best[0][0]<12:return dict(out,reason='No 12-landmark similarity consensus')
    try:model=similarity(x[best[1]],y[best[1]])
    except ValueError:return dict(out,reason='Degenerate fitting consensus')
    xh=np.array([g['observations'][0]['xyz_a'] for g in held]);yh=np.array([g['observations'][0]['xyz_b'] for g in held]);err=np.linalg.norm(apply(xh,model)-yh,axis=1)
    s,R,t=model;out.update(scale=s,rotation=R.tolist(),translation=t.tolist(),fit_inliers=int(best[1].sum()),withheld_3d_median=float(np.median(err)),withheld_3d_p90=float(np.percentile(err,90)))
    out['screen_passed']=bool(np.median(err)<.03 and np.percentile(err,90)<.06)
    out['reason']='3D screen only; requires independent pixel reprojection, spatial/view coverage and visual review'
    return out


def model_data(reader,root,names,raw):
    images={im.name:im for im in reader.read_images_binary(root/'images.bin').values()};cameras=reader.read_cameras_binary(root/'cameras.bin');points=reader.read_points3D_binary(root/'points3D.bin')
    centers=np.array([-reader.qvec2rotmat(images[n].qvec).T@images[n].tvec for n in names]);origin=np.median(centers,axis=0);extent=float(np.median(np.linalg.norm(centers-origin,axis=1)))
    if not np.isfinite(extent) or extent<1e-12:raise ValueError('Unusable component camera extent')
    poses={};landmarks={};mapping={}
    for name in names:
        im=images[name];cam=cameras[im.camera_id]
        if cam.model!='SIMPLE_RADIAL' or (cam.width,cam.height)!=(1080,1920):raise ValueError('Expected native SIMPLE_RADIAL model')
        f,cx,cy,k=cam.params;K=np.array([[f,0,cx],[0,f,cy],[0,0,1.]])
        R=reader.qvec2rotmat(im.qvec);C=(-R.T@im.tvec-origin)/extent
        poses[name]=dict(R=R.tolist(),t=(-R@C).tolist(),center=C.tolist(),K=K.tolist(),dist=[float(k),0.,0.,0.])
        ids=np.array(raw['frames'][name]['feature_ids'],int);xy=np.array(raw['frames'][name]['xy']).reshape(-1,2)
        if len(ids) and (ids.max()>=len(im.xys) or np.max(np.abs(im.xys[ids]-xy))>.01):raise ValueError('Native feature index association mismatch')
        for index,fid in enumerate(ids):
            pid=int(im.point3D_ids[fid]);point=points.get(pid)
            if point is None or point.error>2.5 or len(point.image_ids)<3:continue
            key='map:'+str(pid);landmarks[key]=((point.xyz-origin)/extent).tolist();mapping[(name,index)]=key
    return poses,landmarks,mapping,dict(origin=origin.tolist(),extent=extent)


def augmented_map(raw,names,poses,landmarks,mapping):
    edges=[];candidates={}
    for pair in raw['pairs']:
        a,b=pair['a'],pair['b']
        if a not in names or b not in names or not pair['matches']:continue
        ix=np.array(pair['matches'],int);x=np.array(raw['frames'][a]['xy'])[ix[:,0]];y=np.array(raw['frames'][b]['xy'])[ix[:,1]]
        pa={k:np.asarray(v) for k,v in poses[a].items()};pb={k:np.asarray(v) for k,v in poses[b].items()}
        xyz,keep,angles=triangulate(x,y,pa,pb)
        for j in np.flatnonzero(keep):
            na=(a,int(ix[j,0]));nb=(b,int(ix[j,1]));edges.append(dict(a=na,b=nb,angle=float(angles[j])))
            candidates[(na,nb)]=(xyz[j],float(angles[j]))
    added=0
    for nodes in assemble_tracks(edges):
        if len(nodes)<3:continue
        # Do not duplicate existing landmark IDs or merge inconsistent old-map associations.
        old={mapping[n] for n in nodes if n in mapping}
        if len(old)>1:continue
        if old:
            key=next(iter(old));point=np.array(landmarks[key])
        else:
            valid=[v for (a,b),v in candidates.items() if a in nodes and b in nodes]
            if not valid:continue
            point=max(valid,key=lambda v:v[1])[0];key='tri:'+min(n[0]+':'+str(n[1]) for n in nodes)
        okay=True
        for name,index in nodes:
            uv,z=project(point[None],poses[name]);xy=raw['frames'][name]['xy'][index]
            if z[0]<=0 or np.linalg.norm(uv[0]-xy)>=2:okay=False;break
        if not okay:continue
        if not old:landmarks[key]=point.tolist();added+=1
        for n in nodes:mapping[n]=key
    return added


def verify_cache(raw, selection):
    names={f['name'] for f in selection['samples']}
    actual=[tuple(sorted((r['a'],r['b']))) for r in raw['pairs']]
    expected=set(itertools.combinations(sorted(names),2))
    if (raw['status']!='complete-raw-matches-not-verified' or set(raw['frames'])!=names
            or len(actual)!=len(expected) or set(actual)!=expected):
        raise ValueError('Require completed all-pairs cache with exact selected frames, no missing or duplicate pairs')


def view_coverage(locations):
    return {name:float(cv2.contourArea(cv2.convexHull(np.asarray(xy,np.float32)))/(1080*1920))
            if len(xy)>=3 else 0. for name,xy in locations.items()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('selection','pairs','state','reader','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--augment',action='store_true')
    a=p.parse_args();cv2.setNumThreads(2)
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True)
    selection=json.loads(a.selection.read_text());raw=json.loads(a.pairs.read_text());state=json.loads(a.state.read_text())
    verify_cache(raw,selection)
    if digest(a.selection)!=raw['identity']['selection'] or digest(a.state)!=selection['identity']['state']:raise ValueError('Input provenance mismatch')
    spec=importlib.util.spec_from_file_location('reader',a.reader);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    models={};receipts={}
    for side in ('before','after'):
        cfg=selection['sides'][side];root=Path(next(c['path'] for c in state['components'] if c['id']==cfg['component']))
        poses,landmarks,mapping,norm=model_data(reader,root,cfg['names'],raw);old=len(landmarks)
        added=augmented_map(raw,set(cfg['names']),poses,landmarks,mapping) if a.augment else 0
        models[side]=(poses,landmarks,mapping)
        receipts[side]=dict(component=cfg['component'],normalization=norm,model_sha256={n:digest(root/n) for n in ('images.bin','cameras.bin','points3D.bin')},original_landmarks=old,added_landmarks=added,landmarks=landmarks,cameras=poses)
    rows=[];pair_reports=[];pa,la,ma=models['before'];pb,lb,mb=models['after']
    for pair in raw['pairs']:
        first,second=pair['a'],pair['b']
        if first not in pa or second not in pb:continue
        matches=np.array(pair['matches'],int).reshape(-1,2);i,j=matches.T
        x=np.asarray(raw['frames'][first]['xy']).reshape(-1,2)[i];y=np.asarray(raw['frames'][second]['xy']).reshape(-1,2)[j]
        # Independent shared-lens image-geometry diagnostic, not used to filter 3D matches.
        camera=pa[first];check=screen_pair(x,y,np.asarray(raw['frames'][first]['feature_ids'])[i],np.asarray(camera['K']),np.asarray(camera['dist']))
        pair_reports.append(dict(a=first,b=second,geometry=check))
        for ai,bi in matches:
            ida=ma.get((first,int(ai)));idb=mb.get((second,int(bi)))
            if ida is None or idb is None:continue
            rows.append(dict(a=first,b=second,id_a=ida,id_b=idb,xyz_a=la[ida],xyz_b=lb[idb],xy_a=raw['frames'][first]['xy'][ai],xy_b=raw['frames'][second]['xy'][bi]))
    groups,conflicts=unique_groups(rows);result=screen_similarity(groups)
    if result['screen_passed']:
        model=(result['scale'],np.array(result['rotation']),np.array(result['translation']));s,R,t=model;pixels=[];depths=[];views_a=set();views_b=set();locations_a={};locations_b={}
        for g in groups:
            if not g['held']:continue
            errors=[]
            for row in g['observations']:
                X=np.asarray(row['xyz_a']);Y=np.asarray(row['xyz_b']);u,z=project(((Y-t)@R/s)[None],pa[row['a']]);v,w=project(apply(X[None],model),pb[row['b']])
                errors.extend([np.linalg.norm(u[0]-row['xy_a']),np.linalg.norm(v[0]-row['xy_b'])]);depths.extend([float(z[0]),float(w[0])]);views_a.add(row['a']);views_b.add(row['b']);locations_a.setdefault(row['a'],[]).append(row['xy_a']);locations_b.setdefault(row['b'],[]).append(row['xy_b'])
            pixels.append(max(errors)) # A landmark seen repeatedly cannot outweigh another landmark.
        coverage_a=view_coverage(locations_a);coverage_b=view_coverage(locations_b)
        adequate=[sum(v>=.005 for v in coverage.values()) for coverage in (coverage_a,coverage_b)]
        result.update(withheld_native_px_median=float(np.median(pixels)),withheld_native_px_p90=float(np.percentile(pixels,90)),withheld_views=[len(views_a),len(views_b)],withheld_image_coverage=dict(before=coverage_a,after=coverage_b),adequately_covered_views=adequate)
        result['screen_passed']=bool(min(depths)>0 and np.median(pixels)<3.5 and np.percentile(pixels,90)<8 and min(adequate)>=2)
    report=dict(identity={k:digest(getattr(a,k)) for k in ('selection','pairs','state','reader')},script_sha256=digest(Path(__file__)),support_sha256={n:digest(Path(__file__).with_name(n)) for n in ('evaluate_local_camera_pairs.py','check_static_floor_bridge.py','triangulate_static_gap.py')},augmented=a.augment,models=receipts,pairs=pair_reports,landmark_groups=groups,conflicting_groups=conflicts,raw_3d_correspondences=len(rows),alignment=result,accepted_connection=False,status='complete-candidate-screen-requires-visual-review')
    write(a.output/'report.json',report)
    print(json.dumps(dict(cross_pairs=len(pair_reports),image_geometry_passes=sum(r['geometry']['homography_passed'] or r['geometry']['relative_pose_screen_passed'] for r in pair_reports),landmarks={k:[v['original_landmarks'],v['added_landmarks']] for k,v in receipts.items()},groups=len(groups),alignment=result)))


if __name__=='__main__':main()
