#!/usr/bin/env python3
"""Freeze two short windows for the user-selected landmark/depth experiment."""
import argparse, hashlib, json
from pathlib import Path
import cv2
import numpy as np


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, v): p.write_text(json.dumps(v, indent=2, allow_nan=False)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('images','da3','numbered','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args()
    a.output.mkdir(exist_ok=False,parents=True)
    poses=json.loads((a.da3/'poses.json').read_text())['frames']
    hashes={r['name']:r['sha256'] for r in json.loads((a.da3/'image-hashes.json').read_text())}
    questions=json.loads((a.numbered/'proposals/questions.json').read_text())['questions']
    human=json.loads((a.numbered/'human-choices.json').read_text())
    answers={q['id']:q['choice'] for q in human['questions']}
    sides={}
    for side,name,crop in [('before',questions[0]['source_frame'],[0,300,650,1100]),('after',questions[0]['target_frame'],[450,500,1080,1450])]:
        index=next(i for i,r in enumerate(poses) if r['name']==name)
        rows=[]
        for i in range(index-10,index+11):
            row=poses[i];src=a.images/row['name'];assert sha(src)==hashes[row['name']]
            npz=a.da3/'results_output'/f'frame_{i}.npz'
            with np.load(npz) as d:
                # Verified upstream upper_bound_resize: 1080x1920 -> 284x504 -> 280x504.
                image=cv2.cvtColor(cv2.imread(str(src)),cv2.COLOR_BGR2RGB)
                assert image.shape==(1920,1080,3)
                small=cv2.resize(cv2.resize(image,(284,504),interpolation=cv2.INTER_AREA),(280,504),interpolation=cv2.INTER_AREA)
                error=float(np.mean(np.abs(small.astype(float)-d['image'].astype(float))))
                if error>2:raise ValueError(f'Processed/source image mismatch: {row["name"]} {error}')
                K=np.diag([1080/280,1920/504,1.])@d['intrinsics']
                if not np.allclose(K,row['intrinsics_native'],atol=.01):raise ValueError('Intrinsic mapping mismatch')
                rows.append(dict(**row,depth_index=i,depth_file=npz.name,image_sha256=hashes[row['name']],depth_sha256=sha(npz),processed_image_mae=error,depth_hw=list(d['depth'].shape)))
        points=[]
        for q in questions:
            xy=q['source_xy'] if side=='before' else next(o['xy'] for o in q['options'] if o['label']==answers[q['id']])
            points.append(dict(id=q['id'],x=xy[0],y=xy[1]))
        save(a.output/f'{side}-selection.json',dict(frames=[dict(name=r['name'],timestamp=r['timestamp']) for r in rows],image_sha256={r['name']:r['image_sha256'] for r in rows}))
        save(a.output/f'{side}-seed.json',dict(verdict='supported',support='User-selected correspondence hypothesis; not geometrically verified',seed_frame=name,target_frame=rows[-1]['name'],points=points))
        sides[side]=dict(seed_frame=name,seed_index=10,crop_xyxy=crop,frames=rows)
    cfg=dict(schema=1,sides=sides,source_sha256=json.loads((a.da3/'inputs.json').read_text())['source_sha256'],human_choices_sha256=sha(a.numbered/'human-choices.json'),questions_sha256=sha(a.numbered/'proposals/questions.json'),preparation_script_sha256=sha(Path(__file__)),da3_poses_sha256=sha(a.da3/'poses.json'),da3_inputs_sha256=sha(a.da3/'inputs.json'),
        thresholds=dict(track_cycle_native_px=5.,reprojection_native_px=5.,depth_patch_relative_mad=.1,temporal_depth_relative_difference=.1),
        fit_plan='All six user pairs; SQPnP then LM; leave-one-landmark-out; both directions; primary shared median lens, cached intrinsics sensitivity. Never choose accepted fit by best displayed result.',
        temporal_plan='Fit only seed pair; propagate using cached within-side relative poses to excluded adjacent frames. These are withheld views of the same points, not independent scene landmarks.',
        independent_static_landmarks=dict(status='unavailable',reason='Six human-selected points cover one local flexible region; no verified separate cross-gap floor landmarks.'),accepted_connection=False)
    save(a.output/'experiment.json',cfg)
    print(json.dumps(dict(frames=sum(len(s['frames']) for s in sides.values()),image_mae_max=max(r['processed_image_mae'] for s in sides.values() for r in s['frames']))))

if __name__=='__main__':main()
