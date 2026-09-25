#!/usr/bin/env python3
"""Refine one bounded video interval using saved native frames and features.

Does not train or publish. Writes a gated COLMAP dataset for mask generation
and subsequent training. Requires COLMAP 3.12.6 and numpy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import time
import fcntl
import numpy as np


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    temp.replace(path)


def model_names(path):
    names = []
    with path.open('rb') as f:
        count, = struct.unpack('<Q', f.read(8))
        for _ in range(count):
            f.read(64)
            name = bytearray()
            while (c := f.read(1)) != b'\0':
                if not c:
                    raise ValueError('Truncated camera model')
                name.extend(c)
            names.append(name.decode())
            points, = struct.unpack('<Q', f.read(8))
            f.seek(points * 24, 1)
    return names


def assess(model, selected):
    cameras = {}
    for line in (model / 'cameras.txt').read_text().splitlines():
        if line and not line.startswith('#'):
            row = line.split()
            if row[1] != 'SIMPLE_RADIAL':
                raise ValueError('Assessment currently supports SIMPLE_RADIAL cameras')
            cameras[int(row[0])] = np.array(row[4:], dtype=float)
    points = {}
    for line in (model / 'points3D.txt').read_text().splitlines():
        if line and not line.startswith('#'):
            row = line.split()
            points[int(row[0])] = list(map(float, row[1:4]))
    point_ids = np.array(sorted(points))
    xyz = np.array([points[i] for i in point_ids])
    names, errors, behind = [], [], 0
    with (model / 'images.txt').open() as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            row = line.split()
            names.append(row[9])
            w,x,y,z = map(float, row[1:5])
            rotation = np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
            observations = np.fromstring(next(f), sep=' ').reshape(-1,3)
            observations = observations[observations[:,2] >= 0]
            if not len(observations):
                continue
            indices = np.searchsorted(point_ids, observations[:,2].astype('int64'))
            if not np.all(point_ids[indices] == observations[:,2]):
                raise ValueError('Unknown point association')
            camera = xyz[indices] @ rotation.T + np.array(row[5:8], dtype=float)
            behind += int((camera[:,2] <= 0).sum())
            xy = camera[:,:2] / camera[:,2,None]
            focal,cx,cy,k = cameras[int(row[8])]
            projection = focal * xy * (1+k*(xy*xy).sum(axis=1))[:,None] + [cx,cy]
            errors.extend(np.linalg.norm(projection-observations[:,:2],axis=1).tolist())
    if not errors or not set(names).issubset(selected):
        raise ValueError('Empty geometry or cameras outside the selected interval')
    return {'selected_frames':len(selected), 'registered_frames':len(names),
        'fraction':len(names)/len(selected), 'points':len(points),
        'mean_reprojection_px':float(np.mean(errors)),
        'p95_reprojection_px':float(np.percentile(errors,95)),
        'behind_camera_observations':behind, 'registered_names':names,
        'unregistered_names':sorted(set(selected)-set(names))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run',type=Path,required=True)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--seed-model',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--colmap',required=True)
    parser.add_argument('--start',type=float,required=True)
    parser.add_argument('--end',type=float,required=True)
    parser.add_argument('--max-seconds',type=int,default=900)
    parser.add_argument('--global-refine-ratio',type=float,default=1.5,
                        help='Trigger global refinement after this relative growth; local and final refinement remain enabled')
    args = parser.parse_args()
    if not 0 <= args.start < args.end or args.max_seconds <= 0 or not 1 < args.global_refine_ratio <= 2:
        parser.error('Invalid interval or runtime budget')
    work=args.work.resolve();work.mkdir(parents=True,exist_ok=True)
    lock=(work/'.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state_path=work/'state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else {'stages':{}}
    source=args.source_run.resolve()
    config={'start':args.start,'end':args.end,'source':str(source),
        'database':str(args.database.resolve()),'seed_model':str(args.seed_model.resolve()),
        'global_refine_ratio':args.global_refine_ratio,
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if state.get('config',config)!=config:
        raise RuntimeError('Settings changed; retain this evidence and use a new work directory')
    state.update(config=config,pid=os.getpid());save(state_path,state)
    started=time.monotonic()
    logs=work/'logs';logs.mkdir(exist_ok=True)
    def stage(name,command,outputs):
        if state['stages'].get(name,{}).get('status')=='passed':
            if not all(x.exists() for x in outputs):
                raise RuntimeError(name+': retained output missing')
            return
        state['stages'][name]={'status':'running','started':time.time()};save(state_path,state)
        print(name,'started',flush=True)
        with (logs/(name+'.log')).open('w') as log:
            child=subprocess.Popen(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,
                start_new_session=True,env=dict(os.environ,OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='2'))
            try:
                while child.poll() is None:
                    time.sleep(2)
                    available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))
                    if time.monotonic()-started>args.max_seconds or available<4*1024*1024:
                        raise RuntimeError('Runtime or memory limit; completed stages and snapshots retained')
                if child.returncode or not all(x.exists() for x in outputs):
                    raise RuntimeError(f'{name} failed: exit {child.returncode}')
            except BaseException as error:
                if child.poll() is None:
                    os.killpg(child.pid,signal.SIGTERM)
                    try: child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGKILL);child.wait()
                state['stages'][name].update(status='blocked',error=str(error));save(state_path,state)
                raise
        state['stages'][name].update(status='passed',finished=time.time());save(state_path,state)
        print(name,'passed',flush=True)

    frames=json.loads((source/'frames.json').read_text())
    selected=[x['name'] for x in frames if args.start<=x['timestamp']<args.end]
    if len(selected)<20:
        raise RuntimeError('Pilot needs at least20 frames')
    if not set(model_names(args.seed_model/'images.bin')).issubset(selected):
        raise RuntimeError('Seed cameras lie outside interval; choose a covering interval')
    (work/'images.txt').write_text('\n'.join(selected)+'\n')
    keys=[x for x in (source/'keyframes.txt').read_text().splitlines() if x in set(selected)]
    pairs=[f'{a} {b}' for i,a in enumerate(keys) for b in keys[i+1:i+6]]
    (work/'pairs.txt').write_text('\n'.join(pairs)+'\n')
    db=work/'database.db'
    if not db.exists():
        temporary=db.with_suffix('.partial');shutil.copyfile(args.database,temporary);temporary.replace(db)
    exe=args.colmap
    stage('match',[exe,'matches_importer','--database_path',db,'--match_list_path',work/'pairs.txt',
        '--match_type','pairs','--SiftMatching.use_gpu','1','--SiftMatching.num_threads','4'],[db])
    mapped=work/'mapped';mapped.mkdir(exist_ok=True)
    snapshots=work/'snapshots';snapshots.mkdir(exist_ok=True)
    stage('map',[exe,'mapper','--database_path',db,'--image_path',source/'images',
        '--image_list_path',work/'images.txt','--input_path',args.seed_model,'--output_path',mapped,
        '--Mapper.multiple_models','0','--Mapper.num_threads','4','--Mapper.filter_max_reproj_error','3',
        '--Mapper.ba_global_frames_ratio',args.global_refine_ratio,
        '--Mapper.ba_global_points_ratio',args.global_refine_ratio,
        '--Mapper.snapshot_path',snapshots,'--Mapper.snapshot_frames_freq','50'],[mapped/'images.bin'])
    refined=work/'refined';refined.mkdir(exist_ok=True)
    stage('refine',[exe,'bundle_adjuster','--input_path',mapped,'--output_path',refined],[refined/'images.bin'])
    text_model=work/'model-text';text_model.mkdir(exist_ok=True)
    stage('inspect',[exe,'model_converter','--input_path',refined,'--output_path',text_model,
        '--output_type','TXT'],[text_model/'images.txt'])
    quality=assess(text_model,selected)
    quality['accepted_geometry']=(quality['fraction']>=.9 and quality['points']>=1000
        and quality['mean_reprojection_px']<=1.5 and quality['p95_reprojection_px']<=3.5
        and quality['behind_camera_observations']==0)
    quality['scope_seconds']=[args.start,args.end]
    quality['visual_acceptance']='pending masks, training and novel-view inspection'
    save(work/'quality.json',quality)
    if not quality['accepted_geometry']:
        raise RuntimeError('Geometry gate failed; training is blocked; see quality.json')
    dataset=work/'dataset';dataset.mkdir(exist_ok=True)
    stage('undistort',[exe,'image_undistorter','--image_path',source/'images',
        '--input_path',refined,'--output_path',dataset,'--output_type','COLMAP','--max_image_size','1920'],
        [dataset/'sparse/images.bin'])
    print(json.dumps({k:v for k,v in quality.items() if not k.endswith('_names')},indent=2),flush=True)


if __name__=='__main__':
    main()
