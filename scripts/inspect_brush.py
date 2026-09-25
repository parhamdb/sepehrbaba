"""Measure static-region held-out error and prepare a source/render contact sheet."""
import argparse,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
p=argparse.ArgumentParser();p.add_argument('dataset',type=Path);p.add_argument('renders',type=Path);p.add_argument('output',type=Path);p.add_argument('--expected-views',type=int,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
rows=[];total=0.;pixels=0
files=sorted(a.renders.glob('*.png'))
if not files or len(files)!=a.expected_views:raise RuntimeError('Held-out render count differs from the frozen inventory')
for path in files:
    gt=Image.open(a.dataset/'images'/(path.stem+'.jpg')).convert('RGB')
    render=Image.open(path).convert('RGB');mask=Image.open(a.dataset/'masks'/path.name).convert('L')
    if gt.size!=render.size or gt.size!=mask.size:raise RuntimeError('Evaluation dimensions mismatch')
    keep=np.asarray(mask)>0
    if not keep.any():raise RuntimeError('No unmasked static pixels')
    error=((np.asarray(gt,dtype=np.float32)-np.asarray(render,dtype=np.float32))/255.)**2
    values=error[keep];squared=float(values.sum());n=values.size;total+=squared;pixels+=n
    rows.append({'image':path.stem,'static_fraction':float(keep.mean()),'static_psnr_db':-10*math.log10(max(squared/n,1e-12))})
report={'held_out_views':len(rows),'static_region_psnr_db':-10*math.log10(max(total/pixels,1e-12)),'metric_scope':'Only unmasked pixels; automatic person masks inspected separately. Scores do not prove novel-view geometry.','views':rows}
(a.output/'held-out.json').write_text(json.dumps(report,indent=2)+'\n')
chosen=[files[0],files[len(files)//2],files[-1]]
canvas=Image.new('RGB',(6*270,504));draw=ImageDraw.Draw(canvas)
for i,path in enumerate(chosen):
    for j,source in enumerate([a.dataset/'images'/(path.stem+'.jpg'),path]):
        im=Image.open(source).convert('RGB');im.thumbnail((270,480));x=(i*2+j)*270;canvas.paste(im,(x,24));draw.text((x+4,6),path.stem+(' source' if j==0 else ' render'),fill='white')
canvas.save(a.output/'held-out-contact.jpg')
print(json.dumps({k:v for k,v in report.items() if k!='views'},indent=2))
