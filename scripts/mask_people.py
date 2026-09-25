#!/usr/bin/env python3
"""Generate conservative person-exclusion masks for an undistorted Brush dataset.

Requires torch, torchvision, Pillow. COCO/VOC person segmentation masks all
detected people, including static people; inspect masks before training.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
import torch
from torchvision.models.segmentation import deeplabv3_resnet50, DeepLabV3_ResNet50_Weights


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path)
    a=p.parse_args()
    torch.set_num_threads(4)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    weights=DeepLabV3_ResNet50_Weights.COCO_WITH_VOC_LABELS_V1
    model=deeplabv3_resnet50(weights=weights).eval().to(device)
    transform=weights.transforms()
    person=weights.meta['categories'].index('person')
    masks=a.dataset/'masks';masks.mkdir(exist_ok=True)
    rows=[]
    files=sorted((a.dataset/'images').glob('*.jpg'))
    if not files:raise RuntimeError('No dataset images')
    with torch.inference_mode():
        for i,path in enumerate(files):
            output=masks/(path.stem+'.png')
            with Image.open(path) as image:
                image=image.convert('RGB')
                logits=model(transform(image).unsqueeze(0).to(device))['out']
                probability=logits.softmax(1)[0,person]
                excluded=(probability>.25).cpu().numpy().astype('uint8')*255
                exclusion=Image.fromarray(excluded).resize(image.size,Image.Resampling.NEAREST)
                exclusion=exclusion.filter(ImageFilter.MaxFilter(15))
                temporary=output.with_suffix('.partial.png')
                Image.fromarray(255-np.asarray(exclusion)).save(temporary)
                temporary.replace(output)
                with Image.open(output) as mask:
                    if mask.size!=image.size:raise RuntimeError('Mask dimensions mismatch')
                    fraction=float((np.asarray(mask)==0).mean())
            rows.append({'image':path.name,'excluded_fraction':fraction})
            if i%20==0:print(f'masked {i+1}/{len(files)}',flush=True)
    (a.dataset/'mask-report.json').write_text(json.dumps({'model':str(weights),
        'device':device,'threshold':.25,'dilation_pixels':15,'images':rows},indent=2)+'\n')
    print(f'Completed {len(rows)} masks; visual review required before training.',flush=True)


if __name__=='__main__':main()
