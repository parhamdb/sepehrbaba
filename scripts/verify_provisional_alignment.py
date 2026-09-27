#!/usr/bin/env python3
"""Numerical and binary-format checks for the provisional alignment artifact."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from align_component_matches import similarity
from build_provisional_alignment import floor_similarity


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('assets',type=Path);a=p.parse_args();r=json.loads((a.assets/'alignment.json').read_text())
 assert r['accepted_connection'] is False
 rng=np.random.default_rng(17);x=rng.normal(size=(20,3));angle=.4;R=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1.]])
 y=1.7*x@R.T+[.3,-.2,0.];s,Q,t=similarity(x,y);assert np.allclose(s,1.7) and np.allclose(Q,R) and np.allclose(t,[.3,-.2,0])
 plane={'basis':np.eye(3).tolist(),'origin':[0,0,0]};s,Q,t=floor_similarity(y,x,plane,plane,coincident=False,fixed_scale=1.7)
 assert np.allclose(s,1.7) and np.allclose(Q,R) and np.allclose(t,[.3,-.2,0])
 for side,info in r['sides'].items():
  b=(a.assets/info['asset']).read_bytes();assert len(b)==info['count']*16 and hashlib.sha256(b).hexdigest()==info['sha256']
  points=np.frombuffer(b,dtype=[('xyz','<f4',(3,)),('rgb','u1',(3,)),('tag','u1')]);assert np.isfinite(points['xyz']).all()
  assert set((points['tag']&127).tolist())==set(range(21));assert np.all((points['tag'][points['tag']>=128]&127)==10)
 x=np.array(r['landmarks']['before']);y=np.array(r['landmarks']['after'])
 for name,c in r['candidates'].items():
  R=np.array(c['rotation']);t=np.array(c['translation']);s=c['scale'];assert s>0 and np.allclose(R.T@R,np.eye(3),atol=1e-8) and np.linalg.det(R)>.999999
  q=s*y@R.T+t;assert np.allclose(q,c['transformed_after_landmarks']) and np.allclose(np.linalg.norm(q-x,axis=1),c['landmark_residuals'])
  n=np.array(r['floor_planes']['before']['normal']);after=np.array(r['floor_planes']['after']['normal']);cos=np.clip(n@(R@after),-1,1)
  assert np.isclose(np.degrees(np.arccos(cos)),c['floor_normal_angle_degrees'],atol=1e-5)
  origin=s*R@r['floor_planes']['after']['origin']+t;assert np.isclose(n@origin+r['floor_planes']['before']['offset'],c['floor_plane_offset'])
 f=r['candidates']['floor_direction_similarity'];assert f['floor_normal_angle_degrees']<1e-4 and f['scale']==r['candidates']['six_point_similarity']['scale']
 assert abs(f['floor_plane_offset'])>.01 and r['coincident_floor_blocked']
 display=np.array(r['display_transform']['rotation']);assert np.isclose(np.linalg.det(display),1)
 floor=r['floor_planes']['before'];assert np.allclose(display@floor['normal'],[0,1,0],atol=1e-7)
 print('PASS: known similarity/floor-direction transforms, all binary hashes and frame tags, all candidate residuals, visible floor-offset conflict, level display, no accepted join.')

if __name__=='__main__':main()
