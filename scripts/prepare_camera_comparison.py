#!/usr/bin/env python3
"""Freeze existing COLMAP, VGGT and DA3 cameras for the same loss inventories.

No camera estimation, pose interpolation, component joining, or source mutation.
Runtime source paths are not written into the public output.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from camera_review import rotation


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def calibration(camera):
    p=camera['params'];model=camera['model']
    if model=='PINHOLE':fx,fy,cx,cy=p;dist=[0.,0.,0.,0.]
    elif model in ('SIMPLE_PINHOLE','SIMPLE_RADIAL'):
        fx,cx,cy=p[:3];fy=fx;dist=[p[3] if model=='SIMPLE_RADIAL' else 0.,0.,0.,0.]
    else:raise ValueError(f'Unsupported original camera model: {model}')
    if (camera['width'],camera['height'])!=(1080,1920):raise ValueError('COLMAP source dimensions changed')
    return [[fx,0.,cx],[0.,fy,cy],[0.,0.,1.]],dist


def original_pose(p,component):
    K,dist=calibration(p['camera'])
    return dict(R=p['R'],t=p['t'],center=p['center'],K=K,dist=dist,component=component)


def raw_model(path):
    cameras={}
    for line in (path/'cameras.txt').read_text().splitlines():
        if not line or line.startswith('#'):continue
        r=line.split();cameras[int(r[0])]=dict(model=r[1],width=int(r[2]),height=int(r[3]),params=list(map(float,r[4:])))
    rows={}
    with (path/'images.txt').open() as f:
        for line in f:
            if not line.strip() or line.startswith('#'):continue
            r=line.split();next(f);R=rotation(list(map(float,r[1:5])));t=np.array(list(map(float,r[5:8])))
            rows[r[9]]=dict(R=R.tolist(),t=t.tolist(),center=(-R.T@t).tolist(),camera=cameras[int(r[8])])
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('inventory','snapshot','raw_inventory','native','vggt','da3','da3_first','output'):p.add_argument('--'+k.replace('_','-'),type=Path,required=True)
    a=p.parse_args();inv=json.loads(a.inventory.read_text())
    if sha(a.snapshot)!=inv['snapshot_sha256'] or sha(a.raw_inventory)!=inv['raw_inventory_sha256']:raise ValueError('Frozen baseline hash mismatch')
    snap=json.load(gzip.open(a.snapshot,'rt'));raw=json.loads(a.raw_inventory.read_text())
    baseline={f['name']:original_pose(f['pose'],f['pose']['component']) for f in snap['frames'] if f['pose']}
    raw_selection={};provenance=[]
    for model in raw['models']:
        path=a.native/model['label'].removeprefix('native-')
        if sha(path/'images.txt')!=model['images_sha256']:raise ValueError('Raw model changed')
        rows=raw_model(path)
        provenance.append(dict(label=model['label'],images_sha256=sha(path/'images.txt'),cameras_sha256=sha(path/'cameras.txt')))
        for name,row in rows.items():
            rank=(len(rows),model['label'])
            if name not in raw_selection or rank>raw_selection[name][0]:raw_selection[name]=(rank,original_pose(row,model['label']))
    for name,(_,row) in raw_selection.items():baseline.setdefault(name,row)
    if len(baseline)!=inv['known_frames']:raise ValueError('Original camera union changed')
    cases=[]
    for case in inv['cases']:
        frames=case['frames'];names={f['name'] for f in frames};methods={}
        methods['colmap']={n:baseline[n] for n in names if n in baseline}
        vp=a.vggt/case['id']/'poses.json';dp=a.da3/case['id']/'poses.json'
        methods['vggt']={}
        if vp.exists():
            v=json.loads(vp.read_text())
            for f in v['frames']:
                methods['vggt'][f['name']]=dict(R=f['world_to_camera_rotation'],t=f['translation'],center=f['center'],K=f['intrinsics_native'],dist=[0.,0.,0.,0.],component='vggt-local')
        else:v=None
        d=json.loads(dp.read_text());ip=(a.da3_first if case['id']=='loss-008' else dp.parent)/'intrinsic.txt'
        intrinsics=np.loadtxt(ip).reshape(-1,4)
        if len(intrinsics)!=len(d['frames']):raise ValueError('DA3 intrinsic/pose count mismatch')
        methods['da3']={}
        for f,(fx,fy,cx,cy) in zip(d['frames'],intrinsics):
            C=np.asarray(f['center']);R=np.asarray(f['camera_to_world_rotation']).T
            # Official upper_bound_resize: 1080x1920 -> 280x504; no crop.
            K=np.diag([1080/280,1920/504,1.])@np.array([[fx,0,cx],[0,fy,cy],[0,0,1.]])
            methods['da3'][f['name']]=dict(R=R.tolist(),t=(-R@C).tolist(),center=C.tolist(),K=K.tolist(),dist=[0.,0.,0.,0.],component='da3-local')
        for method,poses in methods.items():
            if not set(poses)<=names:raise ValueError('Pose outside frozen clip')
            for pose in poses.values():
                R=np.asarray(pose['R']);K=np.asarray(pose['K'])
                if not np.isfinite(R).all() or not np.allclose(R@R.T,np.eye(3),atol=1e-4) or np.linalg.det(R)<0:raise ValueError('Invalid camera rotation')
                if not np.isfinite(K).all() or K[0,0]<=0 or K[1,1]<=0:raise ValueError('Invalid camera intrinsics')
        cases.append(dict(**case,methods=methods,provenance=dict(vggt_sha256=sha(vp) if v else None,da3_sha256=sha(dp),da3_intrinsics_sha256=sha(ip)),
            execution=dict(colmap='retained baseline',vggt='completed' if v else 'failed camera decomposition',da3='completed')))
    result=dict(schema=1,source_sha256=inv['source_sha256'],inventory_sha256=sha(a.inventory),snapshot_sha256=sha(a.snapshot),
        baseline_selection='frozen reviewed snapshot first; fill absent frames from largest frozen native raw component',
        source_size=[1080,1920],methods=['colmap','vggt','da3'],raw_models=provenance,cases=cases)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.output.exists():raise FileExistsError(a.output)
    with gzip.open(a.output,'wt') as f:json.dump(result,f,separators=(',',':'))
    for c in cases:print(c['id'],{m:len(v) for m,v in c['methods'].items()},flush=True)


if __name__=='__main__':main()
