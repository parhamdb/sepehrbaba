#!/usr/bin/env python3
"""Attempt overlapping intervals using retained native frames and matches.

One sequential writer uses a private database copy shared by its interval runs.
Failed geometry remains recorded. Does not train, merge, or publish candidates.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from repair_scene import model_names, save


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-run', type=Path, required=True)
    p.add_argument('--database', type=Path, required=True)
    p.add_argument('--bootstrap-models', type=Path, required=True)
    p.add_argument('--extra-seed', type=Path)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--colmap', required=True)
    p.add_argument('--duration', type=float, default=737.301333)
    p.add_argument('--window', type=float, default=90)
    p.add_argument('--overlap', type=float, default=30)
    p.add_argument('--plan-only', action='store_true')
    a = p.parse_args()
    if not (0 <= a.overlap < a.window <= a.duration):
        p.error('Require 0 <= overlap < window <= duration')
    source = a.source_run.resolve()
    frames = json.loads((source/'frames.json').read_text())
    timestamp = {x['name']:x['timestamp'] for x in frames}
    models = sorted(a.bootstrap_models.glob('*/images.bin'))
    if a.extra_seed:
        models.append(a.extra_seed/'images.bin')
    seeds = []
    for path in models:
        names = model_names(path)
        if names and set(names) <= set(timestamp):
            seeds.append((path.parent.resolve(), names))
    plan = []; start = 0.
    while start < a.duration:
        end = min(start+a.window, a.duration)
        names = {x['name'] for x in frames if start <= x['timestamp'] < end}
        candidates = [(path, ns) for path, ns in seeds if set(ns) <= names and len(ns) >= 8]
        seed = max(candidates, key=lambda x:len(x[1]))[0] if candidates else None
        plan.append({'start':start, 'end':end, 'frames':len(names),
                     'seed':str(seed) if seed else None, 'status':'pending'})
        if end == a.duration:
            break
        start += a.window-a.overlap
    covered = {x['name'] for x in frames if any(w['start'] <= x['timestamp'] < w['end'] for w in plan)}
    if len(covered) != len(frames):
        raise ValueError('Window plan must cover every retained source frame')
    if a.plan_only:
        print(json.dumps({'source_frames':len(frames),'windows':plan}, indent=2)); return
    work = a.work.resolve(); work.mkdir(parents=True, exist_ok=True)
    lock = (work/'.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    if any(x.name != '.lock' for x in work.iterdir()):
        raise ValueError('Use a fresh campaign directory; preserve existing results')
    if shutil.disk_usage(work).free < a.database.stat().st_size+20*1024**3:
        raise RuntimeError('Insufficient disk headroom for the private database and results')
    state = {'source_frames':len(frames), 'window_seconds':a.window,
             'overlap_seconds':a.overlap, 'started':time.time(), 'windows':plan,
             'training':'not scheduled', 'merging':'not attempted'}
    save(work/'state.json', state)
    database = work/'database.db'; shutil.copyfile(a.database, database)
    keys = (source/'keyframes.txt').read_text().splitlines()
    for row in plan:
        if shutil.disk_usage(work).free < 20*1024**3:
            row.update(status='blocked',reason='Less than 20 GiB disk headroom'); save(work/'state.json',state); break
        selected = {x['name'] for x in frames if row['start'] <= x['timestamp'] < row['end']}
        folder = work/f"window-{row['start']:g}-{row['end']:g}"; folder.mkdir()
        row.update(status='running',started=time.time()); save(work/'state.json',state)
        print(folder.name, 'started', flush=True)
        seed = Path(row['seed']) if row['seed'] else None
        if seed is None:
            bootstrap = folder/'bootstrap'; bootstrap.mkdir()
            image_list = folder/'bootstrap-images.txt'
            image_list.write_text(''.join(n+'\n' for n in keys if n in selected))
            with (folder/'bootstrap.log').open('w') as log:
                result = subprocess.run([a.colmap,'mapper','--database_path',str(database),
                    '--image_path',str(source/'images'),'--image_list_path',str(image_list),
                    '--output_path',str(bootstrap),'--Mapper.num_threads','4'],
                    stdout=log,stderr=subprocess.STDOUT)
            candidates = [(len(model_names(p)),p.parent) for p in bootstrap.glob('*/images.bin')]
            if result.returncode or not candidates:
                row.update(status='blocked',reason='No bootstrap model',finished=time.time())
                save(work/'state.json',state); continue
            seed = max(candidates,key=lambda x:x[0])[1]; row['seed']=str(seed)
        # Only this sequential campaign writes this private shared database.
        (folder/'database.db').symlink_to(database)
        command = [sys.executable,str(Path(__file__).with_name('repair_scene.py')),
            '--source-run',str(source),'--database',str(database),'--seed-model',str(seed),
            '--work',str(folder),'--colmap',a.colmap,'--start',str(row['start']),
            '--end',str(row['end']),'--max-seconds','0']
        with (folder/'console.log').open('w') as log:
            result = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,
                env=dict(os.environ,OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='2'))
        quality = folder/'quality.json'
        row.update(status='geometry-passed' if result.returncode==0 else 'failed',
                   exit_code=result.returncode,finished=time.time())
        if quality.exists():
            row['quality']={k:v for k,v in json.loads(quality.read_text()).items() if not k.endswith('_names')}
        save(work/'state.json',state); print(folder.name,row['status'],flush=True)
    state['finished']=time.time(); save(work/'state.json',state)


if __name__ == '__main__':
    main()
