#!/usr/bin/env python3
"""Check retained depth-camera evidence against independent projection algebra."""
import argparse,hashlib,json
from pathlib import Path
import cv2
import numpy as np
from evaluate_depth_landmarks import solve,unproject


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);a=p.parse_args()
    root=a.evidence;d=json.loads((root/'evaluation.json').read_text());cfg=json.loads((root/'experiment.json').read_text())
    assert hashlib.sha256((root/'experiment.json').read_bytes()).hexdigest()==d['identity']['experiment_sha256']
    assert d['accepted_connection'] is False
    K=np.array([[900.,0,540],[0,905,960],[0,0,1.]])
    X=np.array([[-.8,-.4,3],[.4,-.6,4],[.7,.5,3.2],[-.5,.6,4.5],[.1,.2,2.5],[.3,-.1,5.]])
    rv=np.array([.12,-.07,.04]);tv=np.array([.2,-.1,.3]);uv=cv2.projectPoints(X,rv,tv,K,None)[0][:,0]
    fit=solve(X,uv,K);assert max(fit['error_px'])<1e-4
    assert np.allclose(fit['R'],cv2.Rodrigues(rv)[0],atol=1e-5) and np.allclose(fit['t'],tv,atol=1e-5)
    xy=np.array([[170.,570.],[890.,930.]])
    xyz=unproject(xy,np.array([.003,.002]),K);reproject=(K@xyz.T).T;assert np.allclose(reproject[:,:2]/reproject[:,2:],xy)
    expected={'before':[[q['x'],q['y']] for q in json.loads((root/'before-seed.json').read_text())['points']], 'after':[[q['x'],q['y']] for q in json.loads((root/'after-seed.json').read_text())['points']]}
    for side,s in d['sides'].items():
        assert np.allclose(s['seed_xy'],expected[side])
        assert len(s['frames'])==21
        for frame in s['frames']:
            assert int(frame['name'].split('_')[1].split('.')[0])-1==frame['depth_index']
            assert frame['processed_image_mae']<=2
    for name,f in d['fits'].items():
        primary=f['variants']['shared_lens'];fit=primary['fit'];source=np.array(primary['source_points_3d']);unit=primary['arbitrary_depth_unit']
        projected=cv2.projectPoints(source,cv2.Rodrigues(np.array(fit['R']))[0],np.array(fit['t']),np.array(primary['target_K']),None)[0][:,0]
        assert np.allclose(projected,fit['projected_xy'],atol=1e-7)
        target=d['sides'][f['target_side']];seed=target['frames'][target['seed_index']]
        # Build world coordinates with 4x4 transforms instead of evaluator's relative-pose formula.
        T=np.eye(4);T[:3,:3]=seed['camera_to_world_rotation'];T[:3,3]=seed['center']
        cam=source@np.array(fit['R']).T+fit['t'];world=(T@np.c_[cam*unit,np.ones(len(cam))].T).T
        for row,retained in zip(target['frames'],f['temporal']):
            C=np.eye(4);C[:3,:3]=row['camera_to_world_rotation'];C[:3,3]=row['center']
            camera=(np.linalg.inv(C)@world.T).T[:,:3]
            uv=(np.array(d['shared_K'])@camera.T).T;uv=uv[:,:2]/uv[:,2:]
            # Cached float32 rotations have ~6e-8 orthogonality residual.
            assert np.allclose(uv,retained['projected_xy'],rtol=0,atol=1e-4)
            assert np.allclose(np.linalg.norm(uv-np.array(row['xy']),axis=1),retained['error_px'],rtol=0,atol=1e-4)
        assert not f['summary']['seed_all_six_pass'] and not f['summary']['held_out_all_six_pass']
    print('PASS: known-pose PnP; depth unprojection; 42 image/index mappings; exact human seeds; independent seed and withheld-camera reprojections; rejection state.')

if __name__=='__main__':main()
