#!/usr/bin/env python3
"""Match static, already reconstructed RootSIFT points with pinned LightGlue.

Reads the COLMAP database without writing it. The TXT models must be undistorted
exports of datasets whose feature indices still match that database. Outputs
candidate correspondences, not an accepted connection. Needs Torch, NumPy, Pillow.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import time

import numpy as np
from PIL import Image
import torch
from clean_static_geometry import rotation


def read_subset(path, names):
    images = {}
    with (path/'images.txt').open() as f:
        for line in f:
            if not line.strip() or line.startswith('#'): continue
            row = line.split(); obs = next(f)
            if row[9] in names:
                images[row[9]] = {'row':row, 'obs':np.fromstring(obs,sep=' ').reshape(-1,3)}
    points = {}
    with (path/'points3D.txt').open() as f:
        for line in f:
            if not line.strip() or line.startswith('#'): continue
            row = line.split()
            points[int(row[0])] = (np.array(row[1:4],float),float(row[7]),(len(row)-8)//2)
    cameras = {}
    for line in (path/'cameras.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        row=line.split()
        if row[1]!='PINHOLE':raise ValueError('Undistorted PINHOLE model required')
        cameras[int(row[0])] = {'size':list(map(int,row[2:4])), 'params':list(map(float,row[4:]))}
    return images,points,cameras


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['model-a','model-b','dataset-a','dataset-b','frames','database','lightglue','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--range-a',type=float,nargs=2,default=[160,184.8])
    p.add_argument('--range-b',type=float,nargs=2,default=[186.2,225])
    p.add_argument('--stride',type=float,default=2)
    p.add_argument('--max-keypoints',type=int,default=2048)
    a=p.parse_args()
    if a.stride<=0 or a.max_keypoints<100:raise ValueError('Invalid sampling')
    a.output.mkdir(parents=True,exist_ok=False)
    pin='eb42fee2d71449efb0aa5c10549752b5d75384d8'
    revision=subprocess.check_output(['git','-C',str(a.lightglue),'rev-parse','HEAD'],text=True).strip()
    if revision!=pin:raise ValueError('Unexpected LightGlue revision')
    spec=importlib.util.spec_from_file_location('bridge_lightglue',a.lightglue/'lightglue/lightglue.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    torch.set_num_threads(4)
    matcher=module.LightGlue(features='sift',depth_confidence=-1,width_confidence=-1).eval().cuda()
    frames=json.loads(a.frames.read_text());times={r['name']:r['timestamp'] for r in frames}
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True)
    features=[];metadata=[]
    for label,model,dataset,interval in [('a',a.model_a,a.dataset_a,a.range_a),('b',a.model_b,a.dataset_b,a.range_b)]:
        available=[]
        with (model/'images.txt').open() as f:
            for line in f:
                if not line.strip() or line.startswith('#'):continue
                row=line.split();next(f)
                if interval[0]<=times[row[9]]<=interval[1]:available.append(row[9])
        if len(available)<2:raise ValueError('Not enough registered frames in interval')
        names=sorted({min(available,key=lambda n:abs(times[n]-t)) for t in np.arange(*interval,a.stride)})
        images,points,cameras=read_subset(model,set(names));cache={};meta={}
        for name in names:
            item=images[name];row=item['row'];obs=item['obs'];iid=int(row[0]);camera=cameras[int(row[8])]
            assert db.execute('SELECT name FROM images WHERE image_id=?',(iid,)).fetchone()[0]==name
            nr,nc,data=db.execute('SELECT rows,cols,data FROM keypoints WHERE image_id=?',(iid,)).fetchone()
            kp=np.frombuffer(data,np.float32).reshape(nr,nc)
            nr,nc,data=db.execute('SELECT rows,cols,data FROM descriptors WHERE image_id=?',(iid,)).fetchone()
            desc=np.frombuffer(data,np.uint8).reshape(nr,nc).astype(np.float32)
            assert nr==len(obs)==len(kp) and nc==128
            with Image.open(dataset/'masks'/(Path(name).stem+'.png')) as im:
                mask=np.asarray(im)
            assert tuple(camera['size'])==(mask.shape[1],mask.shape[0])
            xy=obs[:,:2];ids=obs[:,2].astype(np.int64)
            inside=(xy[:,0]>=0)&(xy[:,0]<mask.shape[1])&(xy[:,1]>=0)&(xy[:,1]<mask.shape[0])&(ids>=0)
            keep=np.flatnonzero(inside)
            keep=np.array([i for i in keep if mask[int(xy[i,1]),int(xy[i,0])]>0 and ids[i] in points and points[ids[i]][1]<=2.5 and points[ids[i]][2]>=3])
            if kp.shape[1]==6:
                scales=(np.hypot(kp[:,2],kp[:,4])+np.hypot(kp[:,3],kp[:,5]))/2
                angles=np.arctan2(kp[:,4],kp[:,2])
            elif kp.shape[1]==4:scales,angles=kp[:,2],kp[:,3]
            else:raise ValueError('Unsupported COLMAP keypoint format')
            keep=keep[np.argsort(scales[keep],kind='stable')[-a.max_keypoints:]]
            if len(keep)<30:raise ValueError(f'Too few static points: {name}')
            d=desc[keep];d/=np.maximum(np.linalg.norm(d,axis=1,keepdims=True),1e-8)
            # COLMAP extraction used its default L1_ROOT normalization. Do not
            # square-root the stored descriptors a second time.
            camid=db.execute('SELECT camera_id FROM images WHERE image_id=?',(iid,)).fetchone()[0]
            size=db.execute('SELECT width,height FROM cameras WHERE camera_id=?',(camid,)).fetchone()
            feat={'keypoints':kp[keep,:2].copy(),'descriptors':d,'scales':scales[keep],'oris':angles[keep],'image_size':np.array(size,np.float32)}
            feat={k:torch.tensor(v,dtype=torch.float32,device='cuda')[None] for k,v in feat.items()}
            cache[name]={'feat':feat,'indices':keep,'ids':ids[keep],'xyz':np.array([points[ids[i]][0] for i in keep]),'xy':xy[keep]}
            meta[name]={'seconds':times[name],'R':rotation(row).tolist(),'t':list(map(float,row[5:8])),**camera,'static_keypoints':len(keep)}
        features.append(cache);metadata.append(meta)
    db.close()
    report={'lightglue_revision':revision,'normalization':'COLMAP L1_ROOT, L2 renormalized after byte quantization', 'max_keypoints':a.max_keypoints,'cameras_a':metadata[0],'cameras_b':metadata[1], 'pairs':[]}
    left,right=features
    with torch.inference_mode():
        aa=list(left)
        control=matcher({'image0':left[aa[0]]['feat'],'image1':left[aa[1]]['feat']})['matches'][0]
        report['positive_control']={'images':aa[:2],'matches':len(control)}
        print('positive control',report['positive_control'],flush=True)
        if len(control)<30:raise ValueError('Positive control failed; inspect descriptor conventions')
        for i,(na,fa) in enumerate(left.items()):
            for j,(nb,fb) in enumerate(right.items()):
                start=time.monotonic()
                result=matcher({'image0':fa['feat'],'image1':fb['feat']})
                matches=result['matches'][0].cpu().numpy();scores=result['scores'][0].cpu().numpy()
                ia,ib=matches.T
                filename=f'{Path(na).stem}--{Path(nb).stem}.npz'
                np.savez_compressed(a.output/filename,xyz_a=fa['xyz'][ia],xyz_b=fb['xyz'][ib],xy_a=fa['xy'][ia],xy_b=fb['xy'][ib],ids_a=fa['ids'][ia],ids_b=fb['ids'][ib],indices_a=fa['indices'][ia],indices_b=fb['indices'][ib],scores=scores)
                report['pairs'].append({'a':na,'b':nb,'matches':len(matches),'file':filename,'split':'held-out' if (i+j)%4==0 else 'fit'})
                (a.output/'matches.json').write_text(json.dumps(report,indent=2)+'\n')
                print(f'{len(report["pairs"])}/{len(left)*len(right)} {na} {nb}: {len(matches)} matches, {time.monotonic()-start:.2f}s',flush=True)
    print('Matching complete; alignment validation still required.',flush=True)


if __name__=='__main__':main()
