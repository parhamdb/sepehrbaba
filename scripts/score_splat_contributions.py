#!/usr/bin/env python3
"""Source-aware opacity experiments, using sampled alpha compositing on PyTorch.

This is an analytical approximation to PlayCanvas 2.22.3, NOT FlashSplat.
Calibrate against the browser before using its rankings. Input views use the
existing viewer coordinate convention (PLY rotated 180 degrees about Z).
Only training views contribute scores. Foreground masks mean zero=ignore.
Requires numpy, Pillow, torch. Writes fresh experiment directories only.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
import torch

from prune_splat_candidates import read_ply


def composite_effect(alpha, color, reference, fraction=.5):
    """Front-to-back alpha [N,P]; color [N,3]. Exact one-at-a-time delta.

    Returns current colors, Gaussian contribution weights, and per-pixel loss
    gains if each individual alpha were reduced by fraction. Other Gaussians
    are held fixed, including the newly exposed background (black).
    """
    trans = torch.cumprod(1-alpha, dim=0)
    before = torch.cat([torch.ones_like(trans[:1]), trans[:-1]], dim=0)
    weights = before*alpha
    contributions = weights[..., None]*color[:, None, :]
    prefix = contributions.cumsum(0)
    current = prefix[-1]
    suffix = current[None]-prefix
    delta = fraction*(alpha[..., None]/(1-alpha[..., None])*suffix-contributions)
    residual = current-reference
    gain = -(2*residual[None]*delta+delta.square()).mean(-1)
    return current, weights, gain


def tensors(data, device):
    def get(names):
        return torch.tensor(np.stack([data[n] for n in names],-1),device=device)
    xyz=get(['x','y','z'])
    q=get([f'rot_{i}' for i in range(4)])
    q=q/torch.linalg.vector_norm(q,dim=1,keepdim=True)
    w,x,y,z=q.unbind(-1)
    rotation=torch.stack([1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y),
                          2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x),
                          2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)],-1).reshape(-1,3,3)
    scale=get([f'scale_{i}' for i in range(3)]).exp()
    cov=(rotation*scale[:,None,:].square())@rotation.transpose(1,2)
    dc=get([f'f_dc_{i}' for i in range(3)])*.28209479177387814+.5
    rest=[n for n in data.dtype.names if n.startswith('f_rest_')]
    if len(rest)!=45:
        raise ValueError('This experiment requires a degree-3 SH PLY')
    sh=get([f'f_rest_{i}' for i in range(45)]).reshape(-1,3,15).transpose(1,2)
    opacity=get(['opacity'])[:,0].sigmoid()
    return xyz,cov,dc,sh,opacity


def project(model,view,width,height):
    xyz,cov,dc,sh,opacity=model;device=xyz.device
    def t(v): return torch.tensor(v,dtype=torch.float32,device=device)
    D=t([-1,-1,1]);pos=t(view['position'])*D
    forward=(t(view['target'])*D-pos);forward/=forward.norm()
    up=t(view['up'])*D;right=torch.linalg.cross(forward,up);right/=right.norm()
    down=-torch.linalg.cross(right,forward);R=torch.stack([right,down,forward])
    offset=xyz-pos;camera=offset@R.T;z=camera[:,2].clamp_min(1e-5)
    focal=height/(2*math.tan(math.radians(view['fov'])/2))
    center=camera[:,:2]/z[:,None]*focal+t([width/2,height/2])
    J=torch.zeros((len(xyz),2,3),device=device)
    J[:,0,0]=focal/z;J[:,1,1]=focal/z
    J[:,:,2]=-camera[:,:2]*focal/z[:,None].square()
    T=J@R;c=T@cov@T.transpose(1,2)
    # PlayCanvas uses 2*focal and halves the quad when converting clip -> pixels.
    det_orig=torch.linalg.det(c).clamp_min(0)
    c=c+torch.eye(2,device=device)[None]*.075
    opacity=opacity*torch.sqrt((det_orig/torch.linalg.det(c).clamp_min(1e-12)).clamp(0,1))
    # The browser caps ellipse axes in screen pixels; without this, Gaussians
    # close to the camera plane wrongly cover the whole image in this scorer.
    diagonal=(c[:,0,0]+c[:,1,1])/2
    spread=torch.sqrt(((c[:,0,0]-c[:,1,1])/2).square()+c[:,0,1].square())
    l1=(diagonal+spread).clamp(.025,min(1024,width,height)**2/8)
    l2=(diagonal-spread).clamp(.025,min(1024,width,height)**2/8)
    angle=.5*torch.atan2(2*c[:,0,1],c[:,0,0]-c[:,1,1]);co=angle.cos();si=angle.sin()
    c=torch.stack([l1*co*co+l2*si*si,(l1-l2)*co*si,
                   (l1-l2)*co*si,l1*si*si+l2*co*co],-1).reshape(-1,2,2)
    inv=torch.stack([c[:,1,1],-c[:,0,1],-c[:,1,0],c[:,0,0]],-1).reshape(-1,2,2)/(l1*l2)[:,None,None]
    radius=torch.sqrt(8*c.diagonal(dim1=-2,dim2=-1).clamp_min(0))
    visible=(camera[:,2]>0)&(opacity>1/255)&(center[:,0]+radius[:,0]>0)&(center[:,0]-radius[:,0]<width)&(center[:,1]+radius[:,1]>0)&(center[:,1]-radius[:,1]<height)
    ids=torch.where(visible)[0]
    ids=ids[torch.argsort(offset[ids].square().sum(-1),stable=True)]
    direction=offset/offset.norm(dim=1,keepdim=True)
    x,y,z=direction.unbind(-1);xx=x*x;yy=y*y;zz=z*z
    basis=torch.stack([-.4886025119*y,.4886025119*z,-.4886025119*x,
        1.0925484306*x*y,-1.0925484306*y*z,.3153915653*(2*zz-xx-yy),
        -1.0925484306*x*z,.5462742153*(xx-yy),
        -.5900435899*y*(3*xx-yy),2.8906114426*x*y*z,
        -.4570457995*y*(4*zz-xx-yy),.3731763326*z*(2*zz-3*xx-3*yy),
        -.4570457995*x*(4*zz-xx-yy),1.4453057213*z*(xx-yy),
        -.5900435899*x*(xx-3*yy)],-1)
    color=(dc+(sh*basis[...,None]).sum(1)).clamp_min(0)
    return ids,center[ids],inv[ids],radius[ids],opacity[ids],color[ids]


def sample_view(model,view,root,out,regions,full=False,fraction=.5):
    device=model[0].device;n=len(model[0]);name=view['name']
    source=np.asarray(Image.open(root/'images'/f'{name}.jpg').convert('RGB'),np.float32)/255
    mask=np.asarray(Image.open(root/'masks'/f'{name}.png'))>0
    h,w=mask.shape;target=np.zeros((h,w),bool)
    for region in regions:
        if region['image']==name:
            x0,y0,x1,y1=region['box'];target[int(y0*h):int(y1*h),int(x0*w):int(x1*w)]=True
    # Fixed deterministic samples, with denser sampling in nominated ghost areas.
    yy,xx=np.indices((h,w));sampling=((xx%8==4)&(yy%8==4)) | (target&(xx%4==2)&(yy%4==2))
    if full: sampling[:]=True
    ids,center,inv,radius,opacity,color=project(model,view,w,h)
    score=torch.zeros((n,6),device=device)
    rendered=np.zeros_like(source)
    for y0 in range(0,h,32):
        for x0 in range(0,w,32):
            sy,sx=np.where(sampling[y0:y0+32,x0:x0+32]);sy+=y0;sx+=x0
            if len(sx)==0:continue
            selected=(center[:,0]+radius[:,0]>=x0)&(center[:,0]-radius[:,0]<=x0+32)&(center[:,1]+radius[:,1]>=y0)&(center[:,1]-radius[:,1]<=y0+32)
            ix=torch.where(selected)[0]
            if len(ix)==0:continue
            pixels=torch.tensor(np.stack([sx+.5,sy+.5],-1),device=device,dtype=torch.float32)
            delta=pixels[None]-center[ix,None]
            power=-.5*torch.einsum('npi,nij,npj->np',delta,inv[ix],delta)
            shape=((torch.exp(power.clamp_max(0))-math.exp(-4))/(1-math.exp(-4))).clamp_min(0)
            alpha=(shape*opacity[ix,None]).clamp(0,.999)
            alpha=torch.where(alpha>=1/255,alpha,0)
            ref=torch.tensor(source[sy,sx],device=device)
            current,weights,gain=composite_effect(alpha,color[ix],ref,fraction)
            rendered[sy,sx]=current.cpu().numpy()
            valid=torch.tensor(mask[sy,sx],device=device)
            all_roi=torch.tensor(target[sy,sx],device=device)
            roi=all_roi&valid
            # The mask excludes unknown/occluded pixels from both gains and protection.
            gain=gain*valid[None]
            score[ids[ix],0]+=weights[:,roi].sum(1)
            score[ids[ix],1]+=gain[:,roi].sum(1)
            score[ids[ix],2]+=gain.sum(1)
            score[ids[ix],3]+=(-gain).clamp_min(0).sum(1)
            score[ids[ix],4]+=(weights*valid[None]).sum(1)
            # Localization is allowed in a masked region; its source RGB is
            # still excluded from every loss/protection score above.
            score[ids[ix],5]+=weights[:,all_roi].sum(1)
    values=score.cpu().numpy()
    np.save(out/f'{name}-scores.npy',values)
    if full:Image.fromarray(np.uint8(rendered.clip(0,1)*255+.5)).save(out/f'{name}.png')
    valid=sampling&mask
    mse=float(np.mean((rendered[valid]-source[valid])**2)) if valid.any() else None
    print(json.dumps({'view':name,'samples':int(sampling.sum()),'static_samples':int(valid.sum()),'target_static_samples':int((valid&target).sum()),'sample_psnr':-10*math.log10(mse) if mse else None}),flush=True)
    return values


def export_candidate(header,data,path,indices,fraction):
    if len(indices)==0:raise ValueError('No supported candidate; refusing empty change')
    result=data.copy();old=result['opacity'][indices].astype(np.float64)
    alpha=np.exp(-np.logaddexp(0,-old))*(1-fraction)
    result['opacity'][indices]=np.log(alpha)-np.log1p(-alpha)
    with path.open('xb') as f:f.write(b''.join(header));f.write(result.tobytes())
    _,reread=read_ply(path)
    for key in data.dtype.names:
        if key!='opacity':assert reread[key].tobytes()==data[key].tobytes()
    keep=np.ones(len(data),bool);keep[indices]=False
    assert reread[keep].tobytes()==data[keep].tobytes()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path);p.add_argument('references',type=Path);p.add_argument('regions',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--device',default='cuda');p.add_argument('--full-view');p.add_argument('--fraction',type=float,default=.5)
    p.add_argument('--export',action='store_true',help='Export only after independent renderer calibration')
    p.add_argument('--localize-masked',action='store_true',help='Use masked ROI pixels for attribution only; validate effects using static RGB elsewhere')
    a=p.parse_args()
    if not 0<a.fraction<1:p.error('fraction must be strictly between zero and one')
    if a.output.exists():p.error('Use a fresh output directory')
    header,data=read_ply(a.input);model=tensors(data,a.device)
    views=[v for v in json.loads((a.references/'views.json').read_text()) if v['split']=='train']
    regions=json.loads(a.regions.read_text())['regions']
    if a.full_view:
        views=[v for v in views if v['name']==a.full_view]
        if not views:p.error('full-view must name a training view')
    a.output.mkdir(parents=True)
    all_scores=[]
    with torch.no_grad():
        for v in views:all_scores.append(sample_view(model,v,a.references,a.output,regions,bool(a.full_view),a.fraction))
    stats=np.stack(all_scores);np.save(a.output/'scores.npy',stats)
    if a.export:
        # Require target contribution in >=2 views, target loss improvement,
        # and total source gain exceeding accumulated pixel-level harm.
        total=stats.sum(0);localization=5 if a.localize_masked else 0
        support=(stats[:,:,localization]>.05).sum(0)
        other_support=((stats[:,:,4]-stats[:,:,0])>.05).sum(0)
        select=(support>=2)&(other_support>=3)&(total[:,localization]>.2)&(total[:,2]>2*total[:,3])
        if not a.localize_masked:select &= total[:,1]>1e-4
        indices=np.flatnonzero(select)
        if len(indices)>.02*len(data):raise ValueError('Candidate exceeds 2% change budget; inspect evidence')
        digest=export_candidate(header,data,a.output/'candidate.ply',indices,a.fraction)
        report={'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'output_sha256':digest,'changed_count':len(indices),'indices':indices.tolist(),'fraction':a.fraction,'localize_masked':a.localize_masked,'training_views':[v['name'] for v in views],'held_out_used':False,'accepted_visual_quality':False,'approximate_renderer':True,'original_opacity_logits':data['opacity'][indices].tolist(),'selected_evidence':total[indices].tolist(),'evidence_columns':['static_roi_weight','static_roi_gain','static_gain','static_harm','static_weight','all_roi_weight']}
        (a.output/'candidate.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'changed_count':len(indices),'output_sha256':digest}),flush=True)


if __name__=='__main__':main()
