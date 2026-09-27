#!/usr/bin/env python3
"""Create a new masked dataset from visually reviewed proposals and corrections."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('dataset','proposals','review','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    import numpy as np
    from PIL import Image,ImageDraw
    review=json.loads(a.review.read_text());manifest=json.loads((a.proposals/'manifest.json').read_text())
    if review.get('status')!='reviewed-for-provisional-training' or not review.get('observations'):
        raise ValueError('Explicit visual review receipt required')
    if review['manifest_sha256']!=sha(a.proposals/'manifest.json'):raise ValueError('Review belongs to another proposal set')
    names=sorted(p.name for p in (a.dataset/'images').glob('*.jpg'))
    if names!=sorted(manifest['images']):raise ValueError('Proposal inventory does not match full dataset')
    if not set(review.get('corrections',{}))<=set(names):raise ValueError('Unknown correction frame')
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'images').symlink_to((a.dataset/'images').resolve(),target_is_directory=True)
    shutil.copytree(a.dataset/'sparse',a.output/'sparse')
    (a.output/'masks').mkdir();(a.output/'review').mkdir();rows=[]
    for name in names:
        source=a.dataset/'images'/name
        if sha(source)!=manifest['images'][name]:raise ValueError('Source changed')
        meta=json.loads((a.proposals/'metadata'/(Path(name).stem+'.json')).read_text())
        mask_path=a.proposals/'masks'/(Path(name).stem+'.png')
        protected_path=a.proposals/'protected'/(Path(name).stem+'.png')
        if sha(mask_path)!=meta['mask_sha256'] or sha(protected_path)!=meta['protected_sha256']:raise ValueError('Proposal changed')
        with Image.open(source) as source_image,Image.open(mask_path) as mask_image,Image.open(protected_path) as protected_image:
            if source_image.size!=mask_image.size or mask_image.size!=protected_image.size:raise ValueError('Mask dimensions mismatch')
            image=source_image.convert('RGB');mask=mask_image.convert('L');protected=np.asarray(protected_image)>0
        correction=review.get('corrections',{}).get(name,{})
        if correction and not correction.get('reason'):raise ValueError('Correction requires rationale')
        if type(correction.get('override_protection',False)) is not bool:raise ValueError('Protection override must be explicit boolean')
        draw=ImageDraw.Draw(mask)
        for label,value in [('exclude',0),('preserve',255)]:
            for polygon in correction.get(label,[]):
                if len(polygon)<3 or any(len(v)!=2 or not all(0<=x<=1 for x in v) for v in polygon):raise ValueError('Invalid normalized polygon')
                draw.polygon([(round(x*(mask.width-1)),round(y*(mask.height-1))) for x,y in polygon],fill=value)
        array=np.asarray(mask).copy();array[protected]=255
        # Only source-reviewed hand/foot polygons may override a mistaken
        # semantic protection proposal; this never disables protection globally.
        if correction.get('override_protection', False):
            manual=Image.fromarray(array);draw=ImageDraw.Draw(manual)
            for label,value in [('exclude',0),('preserve',255)]:
                for polygon in correction.get(label,[]):
                    draw.polygon([(round(x*(mask.width-1)),round(y*(mask.height-1))) for x,y in polygon],fill=value)
            array=np.asarray(manual).copy()
        output=a.output/'masks'/(Path(name).stem+'.png');Image.fromarray(array).save(output)
        excluded=array==0
        arr=np.asarray(image).copy();arr[excluded]=(arr[excluded]*.4+np.array([255,75,20])*.6).astype('uint8')
        overlay=Image.fromarray(arr);overlay.thumbnail((432,768));overlay.save(a.output/'review'/name)
        rows.append(dict(image=name,source_sha256=sha(source),mask_sha256=sha(output),excluded_fraction=float(excluded.mean()),corrected=bool(correction)))
    report=dict(status='reviewed for provisional training; render review required',review_sha256=sha(a.review),proposal_manifest_sha256=sha(a.proposals/'manifest.json'),images=rows,source_cameras={f.name:sha(f) for f in (a.dataset/'sparse').glob('*.bin')})
    (a.output/'mask-report.json').write_text(json.dumps(report,indent=2)+'\n')
    shutil.copyfile(a.review,a.output/'review-receipt.json')
    print(json.dumps(dict(frames=len(rows),corrected=sum(r['corrected'] for r in rows))))


if __name__=='__main__':main()
