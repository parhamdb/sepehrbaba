#!/usr/bin/env python3
"""Headless VGGT-SLAM 2.0 trial; retain native IDs and full portrait field of view.

Requires the official VGGT-SLAM/VGGT_SPARK/SALAD checkouts and their weights.
Pose output is a candidate, not a recovery/accuracy verdict.
"""
import argparse
import json
from pathlib import Path
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--images',type=Path,required=True)
    p.add_argument('--frames',type=Path,required=True)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--submap-size',type=int,default=16)
    p.add_argument('--max-loops',type=int,default=1,choices=[0,1])
    p.add_argument('--min-disparity',type=float,default=50)
    a=p.parse_args()
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    import vggt_slam.solver as implementation
    from vggt.utils.load_fn import load_and_preprocess_images
    from vggt.models.vggt import VGGT
    from vggt_slam.slam_utils import decompose_camera
    torch.set_num_threads(4);cv2.setNumThreads(2)
    a.output.mkdir(parents=True,exist_ok=False)
    frames=json.loads(a.frames.read_text()); names={int(Path(f['name']).stem.split('_')[-1]):f for f in frames}
    # The upstream default center-crops portrait images. Use its supported pad
    # mode, preserve the mapping, and keep the viewer disabled in unattended jobs.
    implementation.load_and_preprocess_images=lambda paths:load_and_preprocess_images(paths,mode='pad')
    implementation.Viewer=lambda:None
    solver=implementation.Solver(init_conf_threshold=25.,lc_thres=.95)
    model=VGGT()
    model.load_state_dict(torch.load(a.checkpoint,map_location='cpu',weights_only=True))
    model=model.eval().to(dtype=torch.bfloat16,device='cuda')
    pending=[];started=time.time();submaps=0
    with torch.inference_mode():
        for i,f in enumerate(frames):
            path=a.images/f['name']; im=cv2.imread(str(path))
            if im is None:raise ValueError('Source image failed to decode')
            if solver.flow_tracker.compute_disparity(im,a.min_disparity,False):pending.append(str(path))
            if len(pending)>=a.submap_size+1 or (i==len(frames)-1 and len(pending)>1):
                predictions=solver.run_predictions(pending,model,a.max_loops,None,None)
                solver.add_points(predictions);solver.graph.optimize()
                submaps+=1
                print(f'Processed submap {submaps}; source frame {i+1}/{len(frames)}',flush=True)
                pending=pending[-1:]
    rows={}
    for submap in solver.map.ordered_submaps_by_key():
        if submap.get_lc_status():continue
        matrices=submap.get_all_poses_world(solver.graph,give_camera_mat=True)
        for fid,P in zip(submap.get_frame_ids(),matrices):
            fid=int(fid);frame=names[fid]
            K,R,C,_=decompose_camera(P)
            if not np.isfinite(P).all() or not np.allclose(R.T@R,np.eye(3),atol=1e-5) or np.linalg.det(R)<0:
                raise ValueError('Invalid recovered camera decomposition')
            with Image.open(a.images/frame['name']) as im:w,h=im.size
            # VGGT pad resizes long side to 518 and rounds the other side to a
            # multiple of 14. Save the exact transform for downstream projection.
            if h>=w:
                rh=518;rw=round(w*518/h/14)*14
            else:
                rw=518;rh=round(h*518/w/14)*14
            transform=np.array([[rw/w,0,(518-rw)//2],[0,rh/h,(518-rh)//2],[0,0,1.]])
            rawK=np.linalg.inv(transform)@K
            rows[frame['name']]=dict(**frame,camera_to_world_rotation=R.tolist(),center=C.tolist(),
                world_to_camera_rotation=R.T.tolist(),translation=(-R.T@C).tolist(),
                intrinsics_native=rawK.tolist(),projection_processed=np.asarray(P).tolist(),
                native_to_processed=transform.tolist(),source_size=[w,h])
    result=dict(method='VGGT-SLAM 2.0',status='candidate poses; independent recovery review pending',
        input_frames=len(frames),estimated_frames=len(rows),submaps=submaps,
        loops=solver.graph.get_num_loops(),elapsed_seconds=time.time()-started,
        settings=dict(submap_size=a.submap_size,max_loops=a.max_loops,min_disparity=a.min_disparity,portrait_mode='pad'),
        frames=[rows[k] for k in sorted(rows)])
    (a.output/'poses.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='frames'}),flush=True)


if __name__=='__main__':main()
