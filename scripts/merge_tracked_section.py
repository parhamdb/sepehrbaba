#!/usr/bin/env python3
"""Merge tracked proposals into a separate review set, retaining approved exclusions.

New tracked exclusions cannot erase previously protected pixels. Original masks,
images and cameras are read-only. Output is NOT approved for training by this tool.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('dataset','protection','baseline-report','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--tracked',type=Path,action='append',required=True)
    a=p.parse_args();names=sorted(x.name for x in (a.dataset/'images').glob('*.jpg'))
    baseline_report=json.loads(a.baseline_report.read_text())
    if not baseline_report.get('status','').startswith('reviewed for provisional training'):raise ValueError('Reviewed baseline receipt required')
    baseline_index={row['image']:row for row in baseline_report['images']}
    if sorted(baseline_index)!=names:raise ValueError('Baseline review inventory differs')
    protection_manifest=json.loads((a.protection.parent/'manifest.json').read_text())
    reports=[json.loads((r/'report.json').read_text()) for r in a.tracked]
    for report in reports:
        if sorted(x['name'] for x in report['rows'])!=names:raise ValueError('Tracked frame inventory differs')
    index=[{r['name']:r for r in report['rows']} for report in reports]
    a.output.mkdir(parents=True,exist_ok=False)
    for sub in ('masks','protected','metadata','review','sheets'):(a.output/sub).mkdir()
    manifest=dict(status='tracked additions requiring visual review',method='reviewed baseline exclusions plus protected SAM3.1 temporal proposals',images={},baseline_masks={},track_reports=[sha(r/'report.json') for r in a.tracked],script_sha256=sha(__file__),protection_manifest_sha256=sha(a.protection.parent/'manifest.json'),dilation_pixels=5,baseline_review_sha256=sha(a.baseline_report))
    rows=[];thumbs=[]
    for name in names:
        source=a.dataset/'images'/name;stem=Path(name).stem;digest=sha(source)
        if protection_manifest['images'].get(name)!=digest:raise ValueError('Protection belongs to another source image')
        original_meta=json.loads((a.protection.parent/'metadata'/(stem+'.json')).read_text())
        if original_meta['protected_sha256']!=sha(a.protection/(stem+'.png')):raise ValueError('Protection mask changed')
        baseline_path=a.dataset/'masks'/(stem+'.png')
        if baseline_index[name]['source_sha256']!=digest or baseline_index[name]['mask_sha256']!=sha(baseline_path):raise ValueError('Reviewed baseline source or mask changed')
        baseline=np.asarray(Image.open(baseline_path).convert('L'))==0
        protected=np.asarray(Image.open(a.protection/(stem+'.png')).convert('L'))>0
        if protected.shape!=baseline.shape:raise ValueError('Protection dimensions differ')
        union=np.zeros_like(baseline)
        for root,lookup in zip(a.tracked,index):
            row=lookup[name];mp=root/'proposals'/(name+'.png')
            if row['source_sha256']!=digest or row['mask_sha256']!=sha(mp):raise ValueError('Tracked input or mask changed')
            mask=np.asarray(Image.open(mp).convert('L'))==0
            if mask.shape!=baseline.shape:raise ValueError('Tracked dimensions differ')
            union|=mask
        union=np.asarray(Image.fromarray(union.astype('uint8')*255).filter(ImageFilter.MaxFilter(5)))>0
        additions=union&~protected&~baseline
        final=baseline|additions
        # Baseline overrides (reviewed foreground hands) remain valid; protection
        # covers all other previously protected pixels.
        effective_protection=protected&~baseline
        assert not np.any(additions&effective_protection)
        mp=a.output/'masks'/(stem+'.png');pp=a.output/'protected'/(stem+'.png')
        Image.fromarray((~final).astype('uint8')*255).save(mp)
        Image.fromarray(effective_protection.astype('uint8')*255).save(pp)
        rgb=np.asarray(Image.open(source).convert('RGB')).copy()
        rgb[baseline]=(rgb[baseline]*.55+np.array([255,100,20])*.45).astype('uint8')
        rgb[additions]=(rgb[additions]*.25+np.array([255,0,180])*.75).astype('uint8')
        preview=Image.fromarray(rgb);preview.thumbnail((270,480))
        tile=Image.new('RGB',(270,510));tile.paste(preview,(0,30));draw=ImageDraw.Draw(tile)
        draw.text((3,2),f'{name} +{100*additions.mean():.2f}%',fill='white');draw.text((3,15),'orange=baseline magenta=NEW',fill='white')
        tile.save(a.output/'review'/name)
        thumbs.append(tile)
        row=dict(image=name,source_sha256=digest,mask_sha256=sha(mp),protected_sha256=sha(pp),baseline_excluded_fraction=float(baseline.mean()),added_fraction=float(additions.mean()),protected_track_overlap_fraction=float((union&effective_protection).mean()),excluded_fraction=float(final.mean()))
        (a.output/'metadata'/(stem+'.json')).write_text(json.dumps(row,indent=2)+'\n');rows.append(row)
        manifest['images'][name]=digest;manifest['baseline_masks'][name]=sha(baseline_path)
    for start in range(0,len(thumbs),12):
        sheet=Image.new('RGB',(1080,1530))
        for i,tile in enumerate(thumbs[start:start+12]):sheet.paste(tile,((i%4)*270,(i//4)*510))
        sheet.save(a.output/'sheets'/f'review-{start:03d}.jpg',quality=92)
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    report=dict(status='awaiting visual review',frames=len(rows),frames_with_additions=sum(r['added_fraction']>0 for r in rows),mean_added_fraction=float(np.mean([r['added_fraction'] for r in rows])),maximum_added_fraction=max(r['added_fraction'] for r in rows),rows=rows)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))


if __name__=='__main__':main()
