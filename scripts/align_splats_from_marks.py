#!/usr/bin/env python3
"""Provisional section placement from retained human marks and current splats.

No GPU, image generation, training, original asset mutation, or live editor write.
Depth is approximate alpha-weighted median Gaussian center depth, not a measured
surface. All six human choices are retained; the floor is a structural hypothesis.
"""
import argparse,hashlib
from pathlib import Path
import json,tarfile,struct
import numpy as np
from PIL import Image,ImageDraw
from trace_splat_sources import read_ply,model,project,weights
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,default=Path('evidence'))
parser.add_argument('--references',type=Path,required=True,help='Contains earlier-references and later-references from prepare_references.py')
parser.add_argument('--assets',type=Path,required=True,help='Contains earlier-tracked.ply and later-tracked.ply')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();evidence=args.evidence;out=args.output;refs=args.references;rows={}
out.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
choices=json.loads((evidence/'numbered-landmarks/human-choices.json').read_text())
questions=json.loads((evidence/'numbered-landmarks/proposals/questions.json').read_text())['questions']
answers={q['id']:q['choice'] for q in choices['questions']}
provenance={'human_choices_sha256':sha(evidence/'numbered-landmarks/human-choices.json'),'script_sha256':sha(Path(__file__)),'inputs':{},'limitations':['Approximate Gaussian center-depth attribution, not a physical surface measurement.','All six points lie on one local region; no independent cross-section landmark validation.','Estimated floor parallelism is imposed, not independently validated.']}

for side,key in [('earlier','before'),('later','after')]:
 seed=json.loads((evidence/f'depth-landmarks/{key}-seed.json').read_text());name=Path(seed['seed_frame']).stem;view=next(v for v in json.loads((refs/f'{side}-references/views.json').read_text()) if v['name']==name)
 for point,q in zip(seed['points'],questions):
  expected=q['source_xy'] if side=='earlier' else next(o['xy'] for o in q['options'] if o['label']==answers[q['id']])
  if point['id']!=q['id'] or not np.allclose([point['x'],point['y']],expected,rtol=0,atol=1e-8):raise ValueError('Seed no longer matches retained human choice')
 provenance['inputs'][side]={'seed_sha256':sha(evidence/f'depth-landmarks/{key}-seed.json'),'ply_sha256':sha(args.assets/f'{side}-tracked.ply'),'views_sha256':sha(refs/f'{side}-references/views.json'),'calibration_archive_sha256':sha(evidence/f'clean-sections/{side}-inputs.tar.gz'),'reference_preview_sha256':sha(refs/f'{side}-references/images/{name}.jpg')}
 with tarfile.open(evidence/f'clean-sections/{side}-inputs.tar.gz') as t:
  b=t.extractfile('native-sparse/cameras.bin').read();assert struct.unpack_from('<i',b,12)[0]==2;f,cx,cy,k=struct.unpack_from('<dddd',b,32)
 fy=view['height']/(2*np.tan(np.deg2rad(view['fov'])/2))
 def map_pixels(px):
  d=(np.array(px)-[cx,cy])/f;x=d.copy()
  for _ in range(20):x=d/(1+k*(x*x).sum(1))[:,None]
  return x*fy+[view['width']/2,view['height']/2]
 D=np.array([-1,-1,1]);pos=np.array(view['position'])*D;forward=np.array(view['target'])*D-pos;forward/=np.linalg.norm(forward);right=np.cross(forward,np.array(view['up'])*D);right/=np.linalg.norm(right);R=np.stack([right,-np.cross(right,forward),forward])
 m=model(read_ply(args.assets/f'{side}-tracked.ply')[1]);pr=project(m,view);depth=(m[0][pr[0]]-pos)@forward;order=np.argsort(depth)
 def lift(px):
  points=[];stats=[]
  for i in range(0,len(px),24):
   p=px[i:i+24];w=weights(pr,p);total=w.sum(0);cum=np.cumsum(w[order],axis=0);z=[]
   for j in range(len(p)):
    indices=[min(len(order)-1,np.searchsorted(cum[:,j],total[j]*q)) for q in [.25,.5,.75]];qs=depth[order[indices]];z.append(qs[1]);stats.append({'opacity':float(total[j]),'depth':float(qs[1]),'iqr':float(qs[2]-qs[0])})
   camera=np.c_[(p-[view['width']/2,view['height']/2])/fy,np.ones(len(p))]*np.array(z)[:,None]
   points.extend((camera@R+pos).tolist())
  return np.array(points),stats
 pixels=map_pixels([[p['x'],p['y']] for p in seed['points']]);xyz,stats=lift(pixels)
 floor_rects=[[5,1430,150,1830],[750,1770,1060,1910]] if side=='earlier' else [[250,1350,1000,1860]]
 floor_pixels=np.vstack([np.array(np.meshgrid(np.linspace(x0,x1,12),np.linspace(y0,y1,12))).reshape(2,-1).T for x0,y0,x1,y1 in floor_rects]);floor,fs=lift(map_pixels(floor_pixels));floor=floor[np.array([s['opacity']>.5 and s['iqr']/s['depth']<.15 for s in fs])]
 if len(floor)<3:raise ValueError(f'{side}: fewer than three usable floor samples')
 rng=np.random.default_rng(20261004);unit=np.median([s['depth'] for s in stats]);best=[]
 for _ in range(300):
  a,b,c=floor[rng.choice(len(floor),3,replace=False)];n=np.cross(b-a,c-a);n/=max(np.linalg.norm(n),1e-15);inliers=np.flatnonzero(np.abs((floor-a)@n)<unit*.01)
  if len(inliers)>len(best):best=inliers
 center=floor[best].mean(0);normal=np.linalg.svd(floor[best]-center)[2][-1];
 if (pos-center)@normal<0:normal=-normal
 image=Image.open(refs/f'{side}-references/images/{name}.jpg').convert('RGB');draw=ImageDraw.Draw(image)
 for p,xy in zip(seed['points'],pixels):
  x,y=xy;draw.ellipse((x-3,y-3,x+3,y+3),outline='yellow',width=1);draw.text((x+4,y-8),p['id'],fill='yellow')
 image.save(out/f'{side}-marked.png')
 rows[side]={'seed':name,'view':view,'pixels':pixels.tolist(),'points':xyz.tolist(),'depth_stats':stats,'unit':unit,'floor':{'normal':normal.tolist(),'offset':float(-normal@center),'inliers':len(best),'samples':len(floor),'median_error':float(np.median(np.abs((floor[best]-center)@normal)))}}
 print(side, 'sampled six marks; floor inliers',len(best),'/',len(floor))
(out/'probe.json').write_text(json.dumps(rows,indent=2)+'\n')

(out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')

d=rows;A=np.array(d['earlier']['points']);B=np.array(d['later']['points']);unit=d['earlier']['unit'];r=out
def fit(A,B):
 a=A-A.mean(0);b=B-B.mean(0);U,s,V=np.linalg.svd(a.T@b);fix=np.ones(A.shape[1]);fix[-1]=np.linalg.det(U@V);R=U@np.diag(fix)@V;scale=(s*fix).sum()/(b*b).sum();return scale,R,A.mean(0)-scale*R@B.mean(0)
def basis(n):
 n=np.array(n);x=np.array([1,0,0])-n*n[0];x/=np.linalg.norm(x);return np.stack([x,np.cross(n,x),n],1)
E,L=[basis(d[s]['floor']['normal']) for s in ['earlier','later']]
rows={}
for name in ['landmarks','floor']:
 if name=='landmarks':s,R,t=fit(A,B)
 else:
  s,Q,u=fit((A@E)[:,:2],(B@L)[:,:2]);yaw=np.eye(3);yaw[:2,:2]=Q;R=E@yaw@L.T;t=E@np.r_[u,s*d['later']['floor']['offset']-d['earlier']['floor']['offset']]
 mapped=s*B@R.T+t;errors=np.linalg.norm(mapped-A,axis=1);angle=np.rad2deg(np.arccos(np.clip(E[:,2]@R@L[:,2],-1,1)))
 rows[name]={'scale':float(s),'rotation':R.tolist(),'translation':t.tolist(),'residuals':errors.tolist(),'median_residual_relative_depth':float(np.median(errors)/unit),'floor_normal_angle':float(angle),'landmark_extent':float(np.linalg.norm(np.ptp(A,axis=0))),'mapped':mapped.tolist()}
 print(name,'scale',s,'residuals',errors,'floorangle',angle,'landmarkspan',rows[name]['landmark_extent'])
s,Q,u=fit((A@E)[:,:2],(B@L)[:,:2]);yaw=np.eye(3);yaw[:2,:2]=Q;R=E@yaw@L.T;t=A.mean(0)-s*R@B.mean(0);errors=np.linalg.norm(s*B@R.T+t-A,axis=1)
rows['floor-direction']={'scale':float(s),'rotation':R.tolist(),'translation':t.tolist(),'residuals':errors.tolist(),'median_residual_relative_depth':float(np.median(errors)/unit),'floor_normal_angle':0.,'floor_offset_earlier_units':float(E[:,2]@t-s*d['later']['floor']['offset']+d['earlier']['floor']['offset'])}
(r/'fits.json').write_text(json.dumps(rows,indent=2)+'\n');print('direction',rows['floor-direction'])
