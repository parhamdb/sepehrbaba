#!/usr/bin/env python3
"""Train independent, explicitly experimental splats from retained DA3 gap poses.

No global alignment, gap certification, masking, or source-data mutation.
All native frames in each planned window are eligible; every tenth view is held
out from Brush and depth seeding, but DA3 itself previously saw all input images.
"""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial.transform import Rotation
from video_to_splat import validate_splat


def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def save(p,data):
    temp=p.with_suffix(p.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');temp.replace(p)


def plan_windows(frames,catalog,width=10,stride=8):
    covered=set().union(*(set(s['frame_names']) for s in catalog['sections']))
    wanted={f['name'] for f in frames}-covered
    rows=[]
    for anchor in range(0,math.ceil(catalog['duration']),stride):
        start=max(0,anchor-1);end=min(anchor+width-1,catalog['duration'])
        selected=[(i,f) for i,f in enumerate(frames) if start<=f['timestamp']<end]
        missing=[f['name'] for _,f in selected if f['name'] in wanted]
        if missing:rows.append({'id':f'da3-gap-{anchor:06d}','start':selected[0][1]['timestamp'],
            'end':selected[-1][1]['timestamp'],'indices':[i for i,_ in selected],
            'missing_frames':len(missing),'frames':len(selected)})
    if not rows:return []
    represented={frames[i]['name'] for row in rows for i in row['indices']}
    if not wanted<=represented:raise ValueError('Gap plan omits missing source frames')
    # First sizeable high-gap window in time order, then greatest missing coverage.
    pilots=[r for r in rows if r['frames']>=80 and r['missing_frames']/r['frames']>.8]
    first=min(pilots,key=lambda r:r['start']) if pilots else rows[0]
    return [first]+sorted((r for r in rows if r is not first),key=lambda r:(-r['missing_frames'],r['start']))


def normalize_camera(row,origin,orientation,scale):
    C=orientation.T@(np.array(row['center'])-origin)/scale
    R=orientation.T@np.array(row['camera_to_world_rotation'])
    return C,R


def write_model(dataset,frames,cameras,points,colors):
    sparse=dataset/'sparse';sparse.mkdir()
    with (sparse/'cameras.bin').open('wb') as f:
        f.write(struct.pack('<Q',len(frames)))
        for i,(K,_,_) in enumerate(cameras,1):
            f.write(struct.pack('<iiQQdddd',i,1,1080,1920,K[0,0],K[1,1],K[0,2],K[1,2]))
    with (sparse/'images.bin').open('wb') as f:
        f.write(struct.pack('<Q',len(frames)))
        for i,(row,(_,C,R)) in enumerate(zip(frames,cameras),1):
            q=Rotation.from_matrix(R.T).as_quat();t=-R.T@C
            f.write(struct.pack('<i4d3di',i,q[3],q[0],q[1],q[2],*t,i));f.write(row['name'].encode()+b'\0');f.write(struct.pack('<Q',0))
    with (sparse/'points3D.bin').open('wb') as f:
        f.write(struct.pack('<Q',len(points)))
        for i,(xyz,rgb) in enumerate(zip(points,colors),1):
            # Empty tracks: these are predicted depth seeds, NOT triangulated points.
            f.write(struct.pack('<Q3d3BdQ',i,*xyz,*map(int,rgb),0.,0))


def prepare(a,row,frames,hashes):
    root=a.output/row['id'];dataset=root/'dataset';dataset.mkdir(parents=True)
    (dataset/'images').mkdir();selected=[frames[i] for i in row['indices']]
    middle=selected[len(selected)//2];origin=np.array(middle['center']);orientation=np.array(middle['camera_to_world_rotation'])
    mid_depth=np.load(a.inference/'results_output'/f"frame_{row['indices'][len(selected)//2]}.npz")['depth']
    positive=mid_depth[np.isfinite(mid_depth)&(mid_depth>0)]
    if not len(positive):raise ValueError('No positive reference depth')
    scale=float(np.median(positive));points=[];colors=[];cameras=[];receipts=[];depth_medians=[]
    for j,(index,f) in enumerate(zip(row['indices'],selected)):
        src=a.images/f['name']
        if digest(src)!=hashes[f['name']]:raise ValueError('Native image differs from DA3 input')
        shutil.copyfile(src,dataset/'images'/f['name'])
        p=a.inference/'results_output'/f'frame_{index}.npz'
        with np.load(p) as d:
            depth=d['depth'];conf=d['conf'];K=d['intrinsics'];image=d['image']
            native=np.diag([1080/280,1920/504,1.])@K
            if depth.shape!=(504,280) or image.shape!=(504,280,3) or not np.allclose(native,f['intrinsics_native'],atol=.02):raise ValueError('Depth/native camera mismatch')
            if j in {0,len(selected)//2,len(selected)-1}:
                import cv2
                original=cv2.cvtColor(cv2.imread(str(src)),cv2.COLOR_BGR2RGB)
                small=cv2.resize(cv2.resize(original,(284,504),interpolation=cv2.INTER_AREA),(280,504),interpolation=cv2.INTER_AREA)
                if np.abs(small.astype(float)-image.astype(float)).mean()>2:raise ValueError('Depth image/source association mismatch')
            C,R=normalize_camera(f,origin,orientation,scale)
            if not np.allclose(R.T@R,np.eye(3),atol=1e-4) or np.linalg.det(R)<0:raise ValueError('Invalid local rotation')
            cameras.append((native,C,R))
            valid=np.isfinite(depth)&(depth>0)&np.isfinite(conf)
            if not valid.any():raise ValueError('Empty depth map')
            depth_medians.append(float(np.median(depth[valid])/scale))
            if j%8==1 and j%10!=0:
                y,x=np.mgrid[4:504:8,4:280:8];z=depth[y,x];keep=valid[y,x]&(conf[y,x]>=np.median(conf[valid]))
                y=y[keep];x=x[keep];z=z[keep]/scale
                local=(np.c_[x,y,np.ones(len(x))]@np.linalg.inv(K).T)*z[:,None]
                xyz=local@R.T+C
                points.extend(xyz.tolist());colors.extend(image[y,x].tolist())
            receipts.append({'name':f['name'],'timestamp':f['timestamp'],'image_sha256':hashes[f['name']],
                'depth_sha256':digest(p),'split':'held-out' if j%10==0 else 'train'})
    points=np.array(points);colors=np.array(colors)
    if len(points)<100 or not np.isfinite(points).all():raise ValueError('Insufficient finite depth seeds')
    write_model(dataset,selected,cameras,points,colors)
    D=np.diag([-1.,-1.,1.]);K,C,R=cameras[len(cameras)//2]
    placement={'seed':middle['name'],'position':(-D@R.T@C).tolist(),'rotation_matrix':(D@R.T@D).tolist(),'scale':1.,'meaning':'Independent seed-camera normalization, not a cross-section connection.'}
    receipt={'method':'DA3 full-recording cached cameras and globally scaled depth, locally normalized',
        'normalization_scale':scale,'frame_inputs':receipts,'depth_seed_points':len(points),
        'depth_seed_method':'8-pixel grid on every eighth eligible training view; upper half of depth confidence; no held-out depth/color seeds',
        'mask_method':'No exclusion masks. People and bodies retained; moving-person ghosts may remain.',
        'source_warning':'DA3 estimates and local geometry are unverified. Coordinate normalization does not repair within-window drift.',
        'relative_depth_median_min':min(depth_medians),'relative_depth_median_max':max(depth_medians),'placement':placement}
    save(root/'preparation.json',receipt)
    return receipt


def evaluate(root,selected,steps):
    renders=root/'splats'/f'eval_{steps}';expected=[f for j,f in enumerate(selected) if j%10==0]
    if {p.stem for p in renders.glob('*.png')}!={Path(f['name']).stem for f in expected}:raise ValueError('Incomplete held-out render inventory')
    total=0.;count=0;rows=[]
    for f in expected:
        name=Path(f['name']).stem
        with Image.open(root/'dataset/images'/f['name']) as source,Image.open(renders/(name+'.png')) as render:
            if source.size!=render.size:raise ValueError('Render resolution mismatch')
            err=(np.asarray(source.convert('RGB'),float)-np.asarray(render.convert('RGB'),float))/255
            mse=float(np.mean(err**2));rows.append({'name':f['name'],'psnr_db':float(-10*np.log10(max(mse,1e-12))) });total+=mse;count+=1
    contact=Image.new('RGB',(1080,504),'#121817');draw=ImageDraw.Draw(contact)
    for k,f in enumerate([expected[0],expected[len(expected)//2]]):
        for j,p in enumerate([root/'dataset/images'/f['name'],renders/(Path(f['name']).stem+'.png')]):
            with Image.open(p) as im:
                im=im.convert('RGB');im.thumbnail((270,480));contact.paste(im,((k*2+j)*270,24));draw.text(((k*2+j)*270+3,4),'Source' if j==0 else 'DA3 splat',fill='white')
    contact.save(root/'comparison.jpg',quality=90)
    report={'held_out_views':count,'full_image_psnr_db':float(-10*np.log10(max(total/count,1e-12))),'views':rows,
        'scope':'Brush appearance holdout only; DA3 inferred cameras from all views. Unmasked moving objects included. Not geometric validation.'}
    save(root/'evaluation.json',report);return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['inference','images','catalog','output','brush']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--steps',type=int,default=8000);p.add_argument('--resume',action='store_true');p.add_argument('--limit',type=int)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    lock=(a.output/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    frames=json.loads((a.inference/'poses.json').read_text())['frames'];catalog=json.loads(a.catalog.read_text())
    hashes={r['name']:r['sha256'] for r in json.loads((a.inference/'image-hashes.json').read_text())}
    plan=plan_windows(frames,catalog)
    config={'steps':a.steps,'poses_sha256':digest(a.inference/'poses.json'),'catalog_sha256':digest(a.catalog),
        'script_sha256':digest(__file__),'validator_sha256':digest(Path(__file__).with_name('video_to_splat.py')),'brush_sha256':digest(a.brush)}
    statepath=a.output/'progress.json'
    if statepath.exists():
        if not a.resume:raise ValueError('Existing campaign requires explicit --resume')
        state=json.loads(statepath.read_text())
        if state['config']!=config:raise ValueError('Campaign inputs or scripts changed')
    else:
        state={'config':config,'started':time.time(),'status':'running','sections':[dict(r,status='pending') for r in plan]}
        save(a.output/'plan.json',plan)
    save(statepath,state)
    count=0;consecutive_failures=[]
    for row in state['sections']:
        if a.limit is not None and count>=a.limit:break
        root=a.output/row['id'];ply=root/'splats/scene.ply'
        if row['status']=='complete':
            if digest(ply)!=row['ply_sha256']:raise ValueError('Completed PLY changed')
            continue
        if row['status']=='failed':continue
        if row['status']=='running':raise ValueError('Interrupted section; inspect retained logs and recover explicitly in a fresh campaign')
        if shutil.disk_usage(a.output).free<24*1024**3:raise RuntimeError('Less than 24 GiB disk reserve; stopped with completed outputs preserved')
        available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
        if available<8*1024**2:raise RuntimeError('Less than 8 GiB available memory; completed outputs preserved')
        row.update(status='running',started=time.time(),stage='prepare');save(statepath,state)
        try:
            prep=prepare(a,row,frames,hashes);row['stage']='train';save(statepath,state)
            export=root/'splats';export.mkdir();candidate=export/'candidate.ply'
            command=[str(a.brush),str(root/'dataset'),'--total-steps',str(a.steps),'--max-resolution','1920',
                '--max-splats','500000','--growth-stop-iter',str(a.steps//2),'--export-every',str(a.steps),
                '--export-path',str(export),'--export-name','candidate.ply','--eval-split-every','10','--eval-every',str(a.steps),'--eval-save-to-disk']
            with (root/'train.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,env=dict(os.environ,OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='2'))
            validate_splat(candidate);candidate.rename(ply);row['stage']='evaluate';save(statepath,state)
            report=evaluate(root,[frames[i] for i in row['indices']],a.steps)
            row.update(status='complete',finished=time.time(),ply_sha256=digest(ply),held_out_views=report['held_out_views'],full_image_psnr_db=report['full_image_psnr_db'])
        except Exception as error:
            row.update(status='failed',finished=time.time(),failure_type=type(error).__name__)
            with (root/'failure.txt').open('w') as f:f.write(str(error)+'\n')
        state['updated']=time.time();save(statepath,state);count+=1;print(row['id'],row['status'],flush=True)
        consecutive_failures=consecutive_failures+[(row['stage'],row.get('failure_type'))] if row['status']=='failed' else []
        if len(consecutive_failures)>=3 and len(set(consecutive_failures[-3:]))==1:
            state['status']='stopped-repeated-failure';save(statepath,state);raise RuntimeError('Three consecutive failures at the same stage; inspect retained logs before more work')
    state['status']='finished' if not any(r['status']=='pending' for r in state['sections']) else 'paused-after-limit'
    state['updated']=time.time();save(statepath,state)


if __name__=='__main__':main()
