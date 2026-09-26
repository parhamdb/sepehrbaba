#!/usr/bin/env python3
"""Validate a retained refined component over an explicit interval and undistort.

Reuses completed reconstruction work. Does not refine, train or claim whole-video
coverage. Source model and frames remain unchanged. Requires a fresh work path.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from repair_scene import assess, save
from clean_static_geometry import digest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--source-run', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--colmap', required=True)
    p.add_argument('--start', type=float, required=True)
    p.add_argument('--end', type=float, required=True)
    a = p.parse_args()
    frames = json.loads((a.source_run/'frames.json').read_text())
    selected = [x['name'] for x in frames if a.start <= x['timestamp'] < a.end]
    if len(selected) < 20:
        p.error('Select at least twenty source frames')
    a.work.mkdir(parents=True, exist_ok=False)
    logs = a.work/'logs'; logs.mkdir()
    state = {'stages': {}, 'source_hashes': {name:digest(a.model/name)
        for name in ['cameras.bin', 'images.bin', 'points3D.bin']}}

    def step(name, args):
        output = a.work/name; output.mkdir()
        state['stages'][name] = {'status':'running', 'started':time.time()}
        save(a.work/'state.json', state)
        try:
            with (logs/(name+'.log')).open('w') as log:
                subprocess.run([a.colmap, *map(str, args), '--output_path', str(output)],
                    check=True, stdout=log, stderr=subprocess.STDOUT,
                    env=dict(os.environ, OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='2'))
        except BaseException as error:
            state['stages'][name].update(status='failed', error=str(error))
            save(a.work/'state.json', state)
            raise
        state['stages'][name].update(status='passed', finished=time.time())
        save(a.work/'state.json', state)

    step('model-text', ['model_converter', '--input_path', a.model, '--output_type', 'TXT'])
    quality = assess(a.work/'model-text', selected)
    quality.update(scope_seconds=[a.start, a.end], whole_recording_frames=len(frames),
        whole_recording_fraction=quality['registered_frames']/len(frames), visual_acceptance='pending')
    quality['accepted_geometry'] = (quality['fraction'] >= .9 and quality['points'] >= 1000
        and quality['mean_reprojection_px'] <= 1.5 and quality['p95_reprojection_px'] <= 3.5
        and quality['behind_camera_observations'] == 0)
    save(a.work/'quality.json', quality)
    print(json.dumps({k:v for k,v in quality.items() if not k.endswith('_names')}, indent=2), flush=True)
    if not quality['accepted_geometry']:
        raise RuntimeError('Component failed geometry checks; undistortion blocked')
    step('dataset', ['image_undistorter', '--image_path', a.source_run/'images',
        '--input_path', a.model, '--output_type', 'COLMAP', '--max_image_size', '1920'])
    if any(digest(a.model/name) != value for name,value in state['source_hashes'].items()):
        raise RuntimeError('Source model changed during preparation')


if __name__ == '__main__':
    main()
