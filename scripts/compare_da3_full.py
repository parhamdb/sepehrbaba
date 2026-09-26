#!/usr/bin/env python3
"""Cross-reference a full DA3 trajectory against frozen COLMAP and local VGGT.

Independent COLMAP components retain independent gauges. Camera agreement is a
diagnostic, never automatic certification of a connection or absolute scale.
"""
import argparse
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from compare_camera_tracks import align_cameras,aligned_center,rotation_angle,pair_schedule,track,epipolar,summarize
from prepare_camera_comparison import raw_model,original_pose


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def as_pose(frame):
    R=np.asarray(frame['camera_to_world_rotation']).T;C=np.asarray(frame['center'])
    return dict(R=R.tolist(),t=(-R@C).tolist(),center=C.tolist(),K=frame['intrinsics_native'],dist=[0.,0.,0.,0.],component='full-da3')


def camera_check(frames,source,reference):
    common=[f for f in frames if f['name'] in source and f['name'] in reference]
    # Temporal holdout: initial fifth establishes coordinates; later cameras test drift.
    n=max(5,len(common)//5);fit_frames=common[:n];test_frames=common[n:]
    result=dict(common_frames=len(common),fit_names=[f['name'] for f in fit_frames],withheld_names=[f['name'] for f in test_frames],accepted_connection=False)
    fit=align_cameras([source[f['name']] for f in fit_frames],[reference[f['name']] for f in fit_frames])
    if fit is None or len(test_frames)<5:return dict(**result,status='insufficient-anchor-or-heldout-support')
    positions=[np.linalg.norm(aligned_center(source[f['name']],fit)-reference[f['name']]['center'])/fit['reference_span']*100 for f in test_frames]
    rotations=[rotation_angle(np.asarray(reference[f['name']]['R'])@np.asarray(fit['rotation'])@np.asarray(source[f['name']]['R']).T) for f in test_frames]
    result.update(status='compared-not-certified',alignment=fit,withheld_frames=len(test_frames),
        median_position_percent_initial_span=float(np.median(positions)),p90_position_percent_initial_span=float(np.percentile(positions,90)),
        median_orientation_deg=float(np.median(rotations)),p90_orientation_deg=float(np.percentile(rotations,90)))
    return result


def frozen_baseline(snapshot,comparison,native):
    if sha(snapshot)!=comparison['snapshot_sha256']:raise ValueError('Original snapshot changed')
    snap=json.load(gzip.open(snapshot,'rt'));baseline={f['name']:original_pose(f['pose'],f['pose']['component']) for f in snap['frames'] if f['pose']}
    candidates={}
    for spec in comparison['raw_models']:
        model=native/spec['label'].removeprefix('native-')
        if sha(model/'images.txt')!=spec['images_sha256'] or sha(model/'cameras.txt')!=spec['cameras_sha256']:raise ValueError('Frozen raw camera model changed')
        rows=raw_model(model)
        for name,row in rows.items():
            rank=(len(rows),spec['label'])
            if name not in candidates or rank>candidates[name][0]:candidates[name]=(rank,original_pose(row,spec['label']))
    for name,(_,pose) in candidates.items():baseline.setdefault(name,pose)
    if len(baseline)!=4946:raise ValueError('Frozen COLMAP camera union differs from reviewed 4946 frames')
    return baseline,snap['frames']


def image_metrics(first,second,observed_first,observed_second):
    if not len(observed_first):return dict(median_px=None,under_4px_fraction=None)
    error,_=epipolar(first,second,observed_first,observed_second)
    error=error[np.isfinite(error)] if error is not None else []
    return dict(median_px=float(np.median(error)) if len(error) else None,
                under_4px_fraction=float(np.mean(error<4)) if len(error) else None)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('poses','comparison','snapshot','native','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    data=json.loads(a.poses.read_text());comparison=json.load(gzip.open(a.comparison,'rt'))
    if data['source_sha256']!=comparison['source_sha256']:raise ValueError('Source recording mismatch')
    baseline,frames=frozen_baseline(a.snapshot,comparison,a.native)
    if [f['name'] for f in data['frames']]!=[f['name'] for f in frames]:raise ValueError('Missing or reordered full-video poses')
    if [f['timestamp'] for f in data['frames']]!=[f['timestamp'] for f in frames]:raise ValueError('Source timestamps changed')
    full={f['name']:as_pose(f) for f in data['frames']};groups=defaultdict(list)
    for f in frames:
        if f['name'] in baseline:groups[baseline[f['name']]['component']].append(f)
    components=[dict(component=component,start=fs[0]['timestamp'],end=fs[-1]['timestamp'],**camera_check(fs,full,baseline)) for component,fs in groups.items()]
    vggt=[dict(id=c['id'],start=c['start'],end=c['end'],**camera_check(c['frames'],full,c['methods']['vggt'])) for c in comparison['cases']]
    # One deterministic image pair per second/component, chosen by time before
    # looking at residuals. Pose checks above use every available reference camera.
    import cv2
    cv2.setNumThreads(2);seen=set();pairs=[];case=dict(frames=frames,methods=dict(colmap=baseline,da3=full))
    for first,second in pair_schedule(case,['colmap','da3']):
        key=(int(first['timestamp']),baseline[first['name']]['component'])
        if key in seen:continue
        seen.add(key);x,y=track(a.native/'images',first,second);metrics={}
        for name,poses in [('colmap',baseline),('da3',full)]:
            metrics[name]=image_metrics(poses[first['name']],poses[second['name']],x,y)
        pairs.append(dict(first=first['name'],second=second['name'],timestamp=first['timestamp'],component=key[1],corners=len(x),metrics=metrics))
    report=dict(schema=1,source_sha256=data['source_sha256'],poses_sha256=sha(a.poses),comparison_sha256=sha(a.comparison),
        full_frames=len(frames),da3_frames=len(full),colmap_frames=len(baseline),colmap_components=components,vggt_windows=vggt,
        image_agreement=summarize(pairs,['colmap','da3']),image_pairs=pairs,accepted_connections=0,
        limits='Temporal gauge holdout per independent component/window; no cross-component reference gauge. Small anchor span amplifies percentage errors. Image corners may be moving. Image pairs sampled by time, camera checks use all available reference poses. No verified continuous path claimed.')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(frames=len(full),components=len(components),vggt_windows=len(vggt),image_pairs=len(pairs))),flush=True)


if __name__=='__main__':main()
