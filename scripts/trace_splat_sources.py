#!/usr/bin/env python3
"""Local, approximate ray attribution. Never labels a projected object as a cause.

Uses the calibrated analytical PlayCanvas convention from score_splat_contributions.
The checkpoint hash and vertex index identify each Gaussian. Only training frames
are ranked. Source overlays show footprints; sampled scores account for occlusion.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from prune_splat_candidates import read_ply


def model(data):
    xyz=np.stack([data[k] for k in ('x','y','z')],1).astype(float)
    q=np.stack([data[f'rot_{i}'] for i in range(4)],1).astype(float)
    q/=np.linalg.norm(q,axis=1,keepdims=True)
    w,x,y,z=q.T
    R=np.stack([1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y),2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x),2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)],1).reshape(-1,3,3)
    scales=np.exp(np.stack([data[f'scale_{i}'] for i in range(3)],1).astype(float))
    cov=(R*scales[:,None,:]**2)@R.transpose(0,2,1)
    opacity=np.exp(-np.logaddexp(0,-data['opacity'].astype(float)))
    return xyz,cov,opacity,scales


def project(m,view):
    xyz,cov,opacity,_=m;D=np.array([-1.,-1.,1.]);pos=np.array(view['position'])*D
    f=np.array(view['target'])*D-pos;f/=np.linalg.norm(f)
    right=np.cross(f,np.array(view['up'])*D);right/=np.linalg.norm(right)
    R=np.stack([right,-np.cross(right,f),f]);offset=xyz-pos;c=offset@R.T
    z=np.maximum(c[:,2],1e-5);w,h=view['width'],view['height'];focal=h/(2*math.tan(math.radians(view['fov'])/2))
    center=c[:,:2]/z[:,None]*focal+[w/2,h/2]
    J=np.zeros((len(xyz),2,3));J[:,0,0]=focal/z;J[:,1,1]=focal/z;J[:,:,2]=-c[:,:2]*focal/z[:,None]**2
    T=J@R;C=T@cov@T.transpose(0,2,1);det=np.maximum(np.linalg.det(C),0)
    C+=np.eye(2)[None]*.075;opacity=opacity*np.sqrt(np.clip(det/np.maximum(np.linalg.det(C),1e-12),0,1))
    diagonal=(C[:,0,0]+C[:,1,1])/2;spread=np.sqrt(((C[:,0,0]-C[:,1,1])/2)**2+C[:,0,1]**2)
    l1=np.clip(diagonal+spread,.025,min(1024,w,h)**2/8);l2=np.clip(diagonal-spread,.025,min(1024,w,h)**2/8)
    angle=.5*np.arctan2(2*C[:,0,1],C[:,0,0]-C[:,1,1]);co=np.cos(angle);si=np.sin(angle)
    C=np.stack([l1*co*co+l2*si*si,(l1-l2)*co*si,(l1-l2)*co*si,l1*si*si+l2*co*co],1).reshape(-1,2,2)
    inv=np.stack([C[:,1,1],-C[:,0,1],-C[:,1,0],C[:,0,0]],1).reshape(-1,2,2)/(l1*l2)[:,None,None]
    radius=np.sqrt(8*np.maximum(C.diagonal(axis1=1,axis2=2),0))
    visible=(c[:,2]>0)&(opacity>1/255)&(center[:,0]+radius[:,0]>0)&(center[:,0]-radius[:,0]<w)&(center[:,1]+radius[:,1]>0)&(center[:,1]-radius[:,1]<h)
    ids=np.flatnonzero(visible);ids=ids[np.argsort(np.sum(offset[ids]**2,axis=1),kind='stable')]
    return ids,center[ids],inv[ids],opacity[ids],radius[ids]


def weights(projection,pixels):
    ids,c,inv,opacity,radius=projection
    delta=np.asarray(pixels)[None]-c[:,None]
    power=-.5*np.einsum('npi,nij,npj->np',delta,inv,delta,optimize=True)
    alpha=np.clip((np.exp(np.minimum(power,0))-math.exp(-4))/(1-math.exp(-4)),0,1)*opacity[:,None]
    alpha=np.clip(alpha,0,.999);alpha[alpha<1/255]=0
    before=np.concatenate([np.ones((1,len(pixels))),np.cumprod(1-alpha,axis=0)[:-1]],axis=0)
    return alpha*before


def run(ply,references,request,output):
    header,data=read_ply(ply);m=model(data);v=request['view']
    for key in ('position','target','up'):
        if len(v[key])!=3 or not np.isfinite(v[key]).all():raise ValueError('Invalid camera vector')
    if not 1<v['fov']<179 or not 1<=v['width']<=2048 or not 1<=v['height']<=2048:raise ValueError('Invalid camera dimensions')
    if np.linalg.norm(np.subtract(v['target'],v['position']))<1e-9 or np.linalg.norm(np.cross(np.subtract(v['target'],v['position']),v['up']))<1e-9:raise ValueError('Degenerate camera')
    point=request['pixel']
    if len(point)!=2 or not all(np.isfinite(point)) or not all(0<=x<=1 for x in point):raise ValueError('Invalid selection')
    p=project(m,v);score=weights(p,[[point[0]*v['width'],point[1]*v['height']]])[:,0]
    order=np.argsort(-score)[:12];candidates=[{'id':int(p[0][i]),'weight':float(score[i]),'axis_ratio':float(np.sort(m[3][p[0][i]])[-1]/np.sort(m[3][p[0][i]])[-2])} for i in order if score[i]>.001]
    selected=request.get('ids',[x['id'] for x in candidates[:4]])
    if not selected or len(selected)>12 or any(type(i)!=int or i<0 or i>=len(data) for i in selected):raise ValueError('Select 1–12 contributing splats')
    selected=list(dict.fromkeys(selected));views=json.loads((references/'views.json').read_text());times={Path(r['name']).stem:r['timestamp'] for r in json.loads((references/'frames.json').read_text())}
    ranked=[]
    for view in views:
        if view['split']!='train':continue
        pp=project(m,view);indices=np.flatnonzero(np.isin(pp[0],selected))
        if not len(indices):continue
        samples=[]
        for i in indices:
            c=pp[1][i];rad=pp[4][i]
            samples.extend([c,c+[min(rad[0]/3,20),0],c+[0,min(rad[1]/3,20)]])
        samples=np.array(samples);samples=samples[(samples[:,0]>=0)&(samples[:,0]<view['width'])&(samples[:,1]>=0)&(samples[:,1]<view['height'])]
        if not len(samples):continue
        support=float(weights(pp,samples)[indices].sum()/len(samples))
        if support>.001:ranked.append(dict(name=view['name'],timestamp=times[view['name']],support=support))
    ranked.sort(key=lambda x:-x['support']);chosen=[]
    for row in ranked:
        if all(abs(row['timestamp']-r['timestamp'])>=.25 for r in chosen):chosen.append(row)
        if len(chosen)==6:break
    output.mkdir(parents=True,exist_ok=False)
    for row in chosen:
        view=next(v for v in views if v['name']==row['name']);pp=project(m,view);indices=np.flatnonzero(np.isin(pp[0],selected))
        source=Image.open(references/'images'/(row['name']+'.jpg')).convert('RGB');arr=np.asarray(source).copy();h,w=arr.shape[:2]
        yy,xx=np.mgrid[:h,:w];overlay=np.zeros((h,w),float)
        for i in indices:
            delta=np.stack([xx+.5-pp[1][i,0],yy+.5-pp[1][i,1]],-1);power=-.5*np.einsum('...i,ij,...j->...',delta,pp[2][i],delta,optimize=True)
            overlay=np.maximum(overlay,np.exp(np.minimum(power,0))*pp[3][i]*(power>=-4))
        mask=np.asarray(Image.open(references/'masks'/(row['name']+'.png')))==0
        a=(overlay>max(.005,overlay.max()*.1))
        footprint=arr.copy();footprint[a]=(footprint[a]*.35+np.array([255,0,200])*.65).astype('uint8')
        masked=arr.copy();masked[mask]=(masked[mask]*.45+np.array([255,100,0])*.55).astype('uint8')
        sheet=Image.new('RGB',(w*3,h+30));draw=ImageDraw.Draw(sheet)
        for j,(label,im) in enumerate([('Source',arr),('Selected footprint',footprint),('Existing exclusions',masked)]):sheet.paste(Image.fromarray(im),(j*w,30));draw.text((j*w+4,5),label,fill='white')
        sheet.save(output/(row['name']+'.jpg'),quality=92)
        row['source_sha256']=hashlib.sha256((references/'images'/(row['name']+'.jpg')).read_bytes()).hexdigest()
    with (output/'selection.ply').open('xb') as f:
        for line in header:f.write(f'element vertex {len(selected)}\n'.encode() if line.startswith(b'element vertex ') else line)
        f.write(data[selected].tobytes())
    result={'status':'review required','method':'approximate alpha-compositing attribution; source overlays are projected footprints, not causal object labels','ply_sha256':hashlib.sha256(ply.read_bytes()).hexdigest(),'selected_ids':selected,'candidates':candidates,'frames':chosen,'request':request,'ranked_training_frames':len(ranked)}
    (output/'trace.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('ply','references','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();print(json.dumps(run(a.ply,a.references,json.load(sys.stdin),a.output)))
