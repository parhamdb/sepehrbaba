#!/usr/bin/env python3
"""Fresh ALIKED detections and LightGlue matches on frozen static-mask regions.

Unlike ALIKED descriptors sampled at old SIFT locations, this can discover new
floor features. CPU extraction supports Thor's missing CUDA deform-conv operator.
Masks provide candidate static regions, not proof that a feature is stationary.
"""
import argparse, itertools, json, subprocess, sys
from pathlib import Path
import cv2
import numpy as np
from probe_gap_recovery import digest, write
from triangulate_static_gap import independent_features


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('selection','images','masks','lightglue','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();import torch
    torch.set_num_threads(4);cv2.setNumThreads(2)
    pin='eb42fee2d71449efb0aa5c10549752b5d75384d8'
    if subprocess.check_output(['git','-C',str(a.lightglue),'rev-parse','HEAD'],text=True).strip()!=pin:raise ValueError('Pinned LightGlue required')
    selection=json.loads(a.selection.read_text());manifest=json.loads((a.masks/'selection.json').read_text())
    if manifest['selection_sha256']!=digest(a.selection):raise ValueError('Wrong mask selection')
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True)
    sys.path.insert(0,str(a.lightglue))
    from lightglue import ALIKED, LightGlue
    from lightglue.utils import load_image
    weights=Path(torch.hub.get_dir())/'checkpoints'
    for name in ('aliked-n16.pth','aliked_lightglue_v0-1_arxiv.pth'):
        if not (weights/name).exists():raise FileNotFoundError('Pre-cached ALIKED weights required')
    extractor=ALIKED(max_num_keypoints=8192).eval().cpu()
    matcher=LightGlue(features='aliked',depth_confidence=-1,width_confidence=-1).eval().cuda()
    report=dict(feature_family='aliked-native',identity=dict(selection=digest(a.selection),masks=digest(a.masks/'selection.json'),lightglue=pin,script=digest(Path(__file__))),
        settings=dict(max_detected=8192,resize=1920,mask_boundary_clearance_px=32,extractor_device='cpu',matcher_device='cuda'),
        weight_sha256={n:digest(weights/n) for n in ('aliked-n16.pth','aliked_lightglue_v0-1_arxiv.pth')},mask_sha256={},frames={},pairs=[],status='running')
    features={}
    with torch.inference_mode():
        for sample in selection['samples']:
            name=sample['name'];source=a.images/name;maskfile=a.masks/(name+'.png');meta=json.loads((a.masks/(name+'.json')).read_text());h=digest(maskfile)
            if digest(source)!=selection['image_sha256'][name] or meta['source_sha256']!=selection['image_sha256'][name] or h!=meta['mask_sha256']:raise ValueError('Source/mask changed')
            mask=cv2.imread(str(maskfile),cv2.IMREAD_GRAYSCALE)
            if mask is None or mask.shape!=(1920,1080):raise ValueError('Native mask required')
            image=load_image(source)
            if tuple(image.shape[-2:])!=(1920,1080):raise ValueError('Native image required')
            distance=cv2.distanceTransform(np.pad((mask>0).astype(np.uint8),1),cv2.DIST_L2,5)[1:-1,1:-1]
            out=extractor.extract(image,resize=1920);xy=out['keypoints'][0].cpu().numpy();pixels=np.floor(xy).astype(int)
            inside=(pixels[:,0]>=0)&(pixels[:,0]<1080)&(pixels[:,1]>=0)&(pixels[:,1]<1920)
            idx=np.flatnonzero(inside);idx=idx[distance[pixels[idx,1],pixels[idx,0]]>=32]
            idx=independent_features(xy,idx)
            features[name]={k:out[k][:,idx].cuda() for k in ('keypoints','descriptors')};features[name]['image_size']=out['image_size'].cuda()
            report['frames'][name]=dict(timestamp=sample['timestamp'],xy=xy[idx].tolist(),feature_ids=idx.tolist());report['mask_sha256'][name]=h
            write(a.output/'pairs.json',report);print('features',name,len(idx),flush=True)
        pairs=list(itertools.combinations(report['frames'],2))
        for number,(x,y) in enumerate(pairs):
            row=dict(a=x,b=y,matches=[],scores=[])
            if len(report['frames'][x]['xy'])>=2 and len(report['frames'][y]['xy'])>=2:
                matched=matcher(dict(image0=features[x],image1=features[y]));row.update(matches=matched['matches'][0].cpu().numpy().tolist(),scores=matched['scores'][0].cpu().numpy().tolist())
            report['pairs'].append(row)
            if (number+1)%100==0:write(a.output/'pairs.json',report);print('pairs',number+1,len(pairs),flush=True)
    for name,h in report['mask_sha256'].items():
        if digest(a.masks/(name+'.png'))!=h:raise ValueError('Mask changed during inference')
    report['status']='complete-raw-matches-not-verified';write(a.output/'pairs.json',report);print('complete',len(pairs),flush=True)


if __name__=='__main__':main()
