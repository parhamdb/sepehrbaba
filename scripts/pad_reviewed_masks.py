#!/usr/bin/env python3
"""Make reviewed-baseline + SAM additions with explicit native-pixel padding.

Source masks use white=keep. Output proposals require visual review. Previously
reviewed preserve polygons are promoted to protection, never inferred from white.
"""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter,ImageDraw
import cv2


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('dataset','baseline-report','protection','prior-review','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--tracked',type=Path,action='append',default=[])
    p.add_argument('--radius',type=int,default=5)
    p.add_argument('--minimum-padding-component',type=int,default=64,help='Native pixel area: do not expand tiny detached exclusions; baseline itself is retained')
    a=p.parse_args()
    if not 0<=a.radius<=20 or a.minimum_padding_component<1:p.error('Invalid native-pixel padding parameters')
    base=json.loads(a.baseline_report.read_text());review=json.loads(a.prior_review.read_text());rows={r['image']:r for r in base['images']}
    if review.get('status')!='reviewed-for-provisional-training' or base['review_sha256']!=sha(a.prior_review):raise ValueError('Baseline review receipt mismatch')
    names=sorted(f.name for f in (a.dataset/'images').glob('*.jpg'))
    if names!=sorted(rows):raise ValueError('Baseline inventory mismatch')
    tracks=[{r['name']:r for r in json.loads((t/'report.json').read_text())['rows']} for t in a.tracked]
    protection_manifest=json.loads((a.protection.parent/'manifest.json').read_text())
    if any(sorted(t)!=names for t in tracks):raise ValueError('Tracked inventory mismatch')
    a.output.mkdir(parents=True,exist_ok=False)
    for d in ('masks','protected','metadata','review','sheets'):(a.output/d).mkdir()
    manifest={'images':{},'radius_pixels':a.radius,'kernel_size':2*a.radius+1,'minimum_padding_component_pixels':a.minimum_padding_component,'coordinate_basis':'native undistorted training pixels','baseline_report_sha256':sha(a.baseline_report),'prior_review_sha256':sha(a.prior_review),'track_report_hashes':[sha(t/'report.json') for t in a.tracked],'script_sha256':sha(__file__),'status':'proposals requiring visual review'}
    def substantial(mask):
        n,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'),connectivity=8)
        keep=stats[:,cv2.CC_STAT_AREA]>=a.minimum_padding_component;keep[0]=False
        return keep[labels].astype('uint8')
    thumbs=[];stats=[]
    for name in names:
        stem=Path(name).stem;source=a.dataset/'images'/name;mp=a.dataset/'masks'/(stem+'.png');assert rows[name]['source_sha256']==sha(source) and rows[name]['mask_sha256']==sha(mp)
        if protection_manifest['images'].get(name)!=sha(source):raise ValueError('Protection source mismatch')
        protection_meta=json.loads((a.protection.parent/'metadata'/(stem+'.json')).read_text())
        if protection_meta['protected_sha256']!=sha(a.protection/(stem+'.png')):raise ValueError('Protection changed')
        original=np.asarray(Image.open(mp).convert('L'))==0;protected=np.asarray(Image.open(a.protection/(stem+'.png')).convert('L'))>0
        if protected.shape!=original.shape:raise ValueError('Protection dimensions differ')
        protected_image=Image.fromarray(protected.astype('uint8')*255);draw=ImageDraw.Draw(protected_image)
        for polygon in review.get('corrections',{}).get(name,{}).get('preserve',[]):draw.polygon([(round(x*(original.shape[1]-1)),round(y*(original.shape[0]-1))) for x,y in polygon],fill=255)
        protected=np.asarray(protected_image)>0;protected&=~original
        raw=np.zeros_like(original)
        for root,index in zip(a.tracked,tracks):
            f=root/'proposals'/(name+'.png');assert index[name]['source_sha256']==sha(source) and index[name]['mask_sha256']==sha(f);raw|=np.asarray(Image.open(f).convert('L'))==0
        # Baseline already used radius2. Expanding it by3 gives an additional
        # 3-pixel boundary experiment; raw new SAM masks get exactly radius5.
        extra=max(0,a.radius-2)
        expanded=cv2.dilate(substantial(original),np.ones((2*extra+1,2*extra+1),dtype='uint8'))>0
        padded=cv2.dilate(substantial(raw),np.ones((2*a.radius+1,2*a.radius+1),dtype='uint8'))>0
        final=original|((expanded|padded)&~protected)
        out=a.output/'masks'/(stem+'.png');prot=a.output/'protected'/(stem+'.png');Image.fromarray((~final).astype('uint8')*255).save(out);Image.fromarray(protected.astype('uint8')*255).save(prot)
        meta={'source_sha256':sha(source),'mask_sha256':sha(out),'protected_sha256':sha(prot),'added_fraction':float((final&~original).mean())};(a.output/'metadata'/(stem+'.json')).write_text(json.dumps(meta,indent=2)+'\n');manifest['images'][name]=sha(source);stats.append({'image':name,**meta})
        rgb=np.asarray(Image.open(source).convert('RGB')).copy();rgb[original]=(rgb[original]*.5+np.array([255,110,0])*.5).astype('uint8');rgb[final&~original]=(rgb[final&~original]*.3+np.array([255,0,200])*.7).astype('uint8')
        im=Image.fromarray(rgb);im.thumbnail((270,480));tile=Image.new('RGB',(270,510));tile.paste(im,(0,30));ImageDraw.Draw(tile).text((3,4),f'{name} +{100*meta["added_fraction"]:.2f}%',fill='white');tile.save(a.output/'review'/name);thumbs.append(tile)
    for start in range(0,len(thumbs),12):
        sheet=Image.new('RGB',(1080,1530))
        for j,t in enumerate(thumbs[start:start+12]):sheet.paste(t,((j%4)*270,(j//4)*510))
        sheet.save(a.output/'sheets'/f'review-{start:03}.jpg',quality=92)
    manifest['baseline_expansion_pixels']=max(0,a.radius-2);manifest['baseline_padding_assumption']='Baseline automatic masks had radius2; manual polygons receive the same additional border. This is not a claim all final masks equal dilation(raw, radius5).'
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(a.output/'report.json').write_text(json.dumps({'status':'awaiting visual review','rows':stats},indent=2)+'\n')
    print(json.dumps({'frames':len(stats),'mean_added_fraction':float(np.mean([r['added_fraction'] for r in stats]))}))


if __name__=='__main__':main()
