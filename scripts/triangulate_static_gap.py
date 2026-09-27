#!/usr/bin/env python3
"""Triangulate unused masked features with fixed anchor poses, then screen gap PnP.

No source camera/model is modified. Query images are excluded from map building.
Tracks with conflicting observations, insufficient parallax or poor reprojection
are rejected. Pose screens are candidates; fixed anchor poses are not ground truth.
"""
import argparse,hashlib,importlib.util,json,sqlite3,subprocess
from pathlib import Path
import cv2,numpy as np
from probe_gap_recovery import digest,mask_indices,localize,write
from check_static_floor_bridge import project,triangulate,matches


def independent_features(kp,indices,radius=3.):
    kept=[]
    for i in indices:
        if all(np.linalg.norm(kp[i,:2]-kp[j,:2])>=radius for j in kept):kept.append(int(i))
    return np.asarray(kept,int)


def assemble_tracks(edges):
    """Join only tracks with at most one feature per image; prefer larger parallax."""
    groups={};owner={}
    for edge in sorted(edges,key=lambda e:-e['angle']):
        a,b=edge['a'],edge['b']
        ga=owner.get(a,a);gb=owner.get(b,b)
        nodes=groups.get(ga,{a})|groups.get(gb,{b})
        if len({n[0] for n in nodes})!=len(nodes):continue
        if ga!=gb:
            groups.pop(ga,None);groups.pop(gb,None)
        groups[ga]=nodes
        for node in nodes:owner[node]=ga
    return list(groups.values())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('state','selection','database','reader','masks','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--matching',choices=['sift','lightglue'],default='sift');p.add_argument('--lightglue',type=Path)
    a=p.parse_args();cv2.setNumThreads(2)
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True)
    def module(name,path):
        spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
    reader=module('reader',a.reader);state=json.loads(a.state.read_text());selection=json.loads(a.selection.read_text())
    if digest(a.state)!=selection['identity']['state']:raise ValueError('State differs from frozen selection')
    manifest=json.loads((a.masks/'selection.json').read_text())
    if manifest['selection_sha256']!=digest(a.selection):raise ValueError('Wrong masks')
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True);ids=dict(db.execute('select name,image_id from images'))
    identity={k:digest(getattr(a,k)) for k in ('state','selection','database','reader')}
    identity.update(script=digest(Path(__file__)),pnp_script=digest(Path(__file__).with_name('probe_gap_recovery.py')),
        geometry_script=digest(Path(__file__).with_name('check_static_floor_bridge.py')),mask_manifest=digest(a.masks/'selection.json'),matching=a.matching)
    matcher=None
    if a.matching=='lightglue':
        import torch
        torch.set_num_threads(4)
        pin='eb42fee2d71449efb0aa5c10549752b5d75384d8'
        if not a.lightglue or subprocess.check_output(['git','-C',str(a.lightglue),'rev-parse','HEAD'],text=True).strip()!=pin:raise ValueError('Pinned LightGlue required')
        matcher=module('static_lg',a.lightglue/'lightglue/lightglue.py').LightGlue(features='sift',depth_confidence=-1,width_confidence=-1).eval().cuda();identity['lightglue']=pin
    features={};mask_hashes={}
    for sample in selection['samples']:
        name=sample['name'];iid=ids[name]
        def array(table,dtype):
            nr,nc,blob=db.execute(f'select rows,cols,data from {table} where image_id=?',(iid,)).fetchone();return np.frombuffer(blob,dtype).reshape(nr,nc)
        kp=array('keypoints',np.float32);d=array('descriptors',np.uint8).astype(np.float32);d/=np.maximum(np.linalg.norm(d,axis=1,keepdims=True),1e-8)
        if kp.shape[1]!=6:raise ValueError('Expected affine SIFT features')
        scales=(np.hypot(kp[:,2],kp[:,4])+np.hypot(kp[:,3],kp[:,5]))/2;ori=np.arctan2(kp[:,4],kp[:,2])
        mask_path=a.masks/(name+'.png');meta=json.loads((a.masks/(name+'.json')).read_text());mask_hashes[name]=digest(mask_path)
        if mask_hashes[name]!=meta['mask_sha256'] or meta['source_sha256']!=selection['image_sha256'][name]:raise ValueError('Mask identity mismatch')
        mask=cv2.imread(str(mask_path),cv2.IMREAD_GRAYSCALE)
        if mask.shape!=(1920,1080):raise ValueError('Native mask required')
        distance=cv2.distanceTransform(np.pad((mask>0).astype(np.uint8),1),cv2.DIST_L2,5)[1:-1,1:-1]
        indices=independent_features(kp,mask_indices(dict(kp=kp,scales=scales),np.arange(len(kp)),distance))
        f=dict(xy=kp[indices,:2],d=d[indices],indices=indices,scales=scales[indices],oris=ori[indices]);features[name]=f
        if matcher is not None:
            values=dict(keypoints=f['xy'],descriptors=f['d'],scales=f['scales'],oris=f['oris'],image_size=np.array([1080,1920]))
            f['tensor']={k:torch.tensor(v,dtype=torch.float32,device='cuda')[None] for k,v in values.items()}
    def match(x,y):
        if len(features[x]['xy'])<2 or len(features[y]['xy'])<2:return []
        if matcher is None:return matches(features[x]['d'],features[y]['d'])
        with torch.inference_mode():out=matcher(dict(image0=features[x]['tensor'],image1=features[y]['tensor']))
        return out['matches'][0].cpu().numpy().tolist()
    report=dict(identity=identity,mask_sha256=mask_hashes,status='running',maps=[],accepted_poses=0,accepted_joins=0,
        limitation='Static masks and existing anchor cameras are provisional. Added points use two or more distinct anchor views; pose screens require independent review, not automatic acceptance.')
    for gid,case in selection['cases'].items():
        for direction,cfg in case['directions'].items():
            cid=cfg['component'];root=Path(next(c['path'] for c in state['components'] if c['id']==cid));images=reader.read_images_binary(root/'images.bin');cameras=reader.read_cameras_binary(root/'cameras.bin')
            camera=next(iter(cameras.values()))
            if len(cameras)!=1 or camera.model!='SIMPLE_RADIAL' or (camera.width,camera.height)!=(1080,1920):raise ValueError('One native SIMPLE_RADIAL camera required')
            f,cx,cy,k=camera.params;K=np.array([[f,0,cx],[0,f,cy],[0,0,1.]]);dist=np.array([k,0.,0.,0.]);poses={}
            anchors=cfg['anchors'];queries=list(case['queries'])
            if cfg['control']:queries.append(dict(name=cfg['control'],kind='positive-control'))
            if set(anchors)&{q['name'] for q in queries}:raise ValueError('Query leaked into map anchors')
            for name in anchors:
                im=images[ids[name]];R=reader.qvec2rotmat(im.qvec);t=im.tvec;poses[name]=dict(R=R,t=t,center=-R.T@t,K=K,dist=dist)
            edges=[];pair_rows=[]
            for i,x in enumerate(anchors):
                for y in anchors[i+1:]:
                    pairs=match(x,y);pair_row=dict(a=x,b=y,matches=len(pairs),triangulated=0);pair_rows.append(pair_row)
                    if not pairs:continue
                    indices=np.asarray(pairs,int);xyp=features[x]['xy'][indices[:,0]];xyq=features[y]['xy'][indices[:,1]]
                    xyz,keep,angle=triangulate(xyp,xyq,poses[x],poses[y]);uv,z=project(xyz,poses[x]);vq,w=project(xyz,poses[y])
                    reprojection=(np.linalg.norm(uv-xyp,axis=1)<2)&(np.linalg.norm(vq-xyq,axis=1)<2)
                    pair_row.update(triangulated=int(keep.sum()),positive_both=int(((z>0)&(w>0)).sum()),
                        parallax_ge_one_degree=int((angle>=1).sum()),reprojection_both_under_two_px=int(reprojection.sum()))
                    for pair,point,good,deg in zip(pairs,xyz,keep,angle):
                        if good:edges.append(dict(a=(x,int(pair[0])),b=(y,int(pair[1])),xyz=point,angle=float(deg)))
            tracks=assemble_tracks(edges);landmarks=[];node_landmark={}
            for nodes in tracks:
                candidates=[e for e in edges if e['a'] in nodes and e['b'] in nodes]
                best=max(candidates,key=lambda e:e['angle']);point=best['xyz'];valid=True
                for name,index in nodes:
                    uv,z=project(point[None],poses[name])
                    if z[0]<=0 or np.linalg.norm(uv[0]-features[name]['xy'][index])>=2:valid=False;break
                if not valid:continue
                key='|'.join(f'{n}:{int(features[n]["indices"][i])}' for n,i in sorted(nodes));lid=int(hashlib.sha256(key.encode()).hexdigest()[:12],16)
                existing_ids=sorted({int(images[ids[n]].point3D_ids[features[n]['indices'][i]]) for n,i in nodes if images[ids[n]].point3D_ids[features[n]['indices'][i]]>=0})
                landmark=dict(id=lid,xyz=point.tolist(),parallax_degrees=best['angle'],original_point_ids=existing_ids,
                    origin='previously-unmapped-observations' if not existing_ids else 'includes-existing-map-observations',
                    observations=[dict(name=n,feature=int(features[n]['indices'][i]),xy=features[n]['xy'][i].tolist()) for n,i in sorted(nodes)])
                landmarks.append(landmark)
                for node in nodes:node_landmark[node]=landmark
            row=dict(gap=gid,direction=direction,component=cid,model_sha256={n:digest(root/n) for n in ('cameras.bin','images.bin')},pairs=pair_rows,landmarks=landmarks,trials=[])
            for query in queries:
                name=query['name'];correspondences=[]
                for anchor in anchors:
                    for i,j in match(anchor,name):
                        lm=node_landmark.get((anchor,int(i)))
                        if lm:correspondences.append(dict(id=lm['id'],xyz=lm['xyz'],xy=features[name]['xy'][j].tolist(),score=1.,anchor=anchor,anchor_xy=features[anchor]['xy'][i].tolist()))
                result=localize(correspondences,K,dist)
                row['trials'].append(dict(query=name,query_kind=query['kind'],evidence_role='control' if ids[name] in images else 'recovery-candidate',**result))
            report['maps'].append(row);write(a.output/'report.json',report)
            print(gid,direction,'static_points',len(landmarks),'new_pnp_passes',sum(t['passed'] and t['evidence_role']=='recovery-candidate' for t in row['trials']),flush=True)
    for name,h in mask_hashes.items():
        if digest(a.masks/(name+'.png'))!=h:raise ValueError('Mask changed during run')
    for m in report['maps']:
        root=Path(next(c['path'] for c in state['components'] if c['id']==m['component']))
        if any(digest(root/n)!=h for n,h in m['model_sha256'].items()):raise ValueError('Model changed during run')
    report['status']='complete-candidates-not-certified';write(a.output/'report.json',report);db.close()


if __name__=='__main__':main()
