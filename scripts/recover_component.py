#!/usr/bin/env python3
"""Repair a retained component on a copy, assess it, and undistort if accepted.

No elapsed-time limit. Masks, training, visual review and publication are separate.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from repair_scene import assess, save
from sanitize_geometry import sanitize


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-model', type=Path, required=True, help='COLMAP TXT model')
    p.add_argument('--source-run', type=Path, required=True, help='Native images and frames.json')
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--colmap', required=True)
    p.add_argument('--start', type=float, required=True)
    p.add_argument('--end', type=float, required=True)
    a = p.parse_args()
    frames = json.loads((a.source_run/'frames.json').read_text())
    selected = [x['name'] for x in frames if a.start <= x['timestamp'] < a.end]
    if len(selected) < 20:
        p.error('Select at least 20 source frames')
    w = a.work.resolve(); w.mkdir(parents=True, exist_ok=False)
    logs = w/'logs'; logs.mkdir()
    state = {'stages': {}, 'scope_seconds': [a.start, a.end], 'source_frames': len(frames)}

    def step(name, action):
        state['stages'][name] = {'status': 'running', 'started': time.time()}
        save(w/'state.json', state); print(name, flush=True)
        try:
            result = action()
        except BaseException as error:
            state['stages'][name].update(status='failed', error=str(error))
            save(w/'state.json', state)
            raise
        state['stages'][name].update(status='passed', finished=time.time())
        save(w/'state.json', state)
        return result

    def run(name, args):
        output = w/name; output.mkdir()
        with (logs/(name+'.log')).open('w') as log:
            subprocess.run([a.colmap, *map(str, args), '--output_path', str(output)],
                stdout=log, stderr=subprocess.STDOUT, check=True,
                env=dict(os.environ, OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='2'))

    step('sanitize-before', lambda: sanitize(a.source_model, w/'sanitized-before'))
    step('filtered-bin', lambda: run('filtered-bin', ['model_converter',
        '--input_path', w/'sanitized-before', '--output_type', 'BIN']))
    step('refined', lambda: run('refined', ['bundle_adjuster', '--input_path', w/'filtered-bin']))
    step('refined-text', lambda: run('refined-text', ['model_converter',
        '--input_path', w/'refined', '--output_type', 'TXT']))
    step('sanitize-after', lambda: sanitize(w/'refined-text', w/'sanitized-after'))
    step('final-model', lambda: run('final-model', ['model_converter',
        '--input_path', w/'sanitized-after', '--output_type', 'BIN']))

    def inspect():
        quality = assess(w/'sanitized-after', selected)
        quality.update(scope_seconds=[a.start, a.end], whole_recording_frames=len(frames),
            whole_recording_fraction=quality['registered_frames']/len(frames), visual_acceptance='pending')
        quality['accepted_geometry'] = (quality['fraction'] >= .9 and quality['points'] >= 1000
            and quality['mean_reprojection_px'] <= 1.5 and quality['p95_reprojection_px'] <= 3.5
            and quality['behind_camera_observations'] == 0)
        save(w/'quality.json', quality)
        if not quality['accepted_geometry']:
            raise RuntimeError('Geometry checks failed; no dataset generated')
        return quality

    quality = step('inspect', inspect)
    step('dataset', lambda: run('dataset', ['image_undistorter',
        '--image_path', a.source_run/'images', '--input_path', w/'final-model',
        '--output_type', 'COLMAP', '--max_image_size', '1920']))
    print(json.dumps({k: v for k, v in quality.items() if not k.endswith('_names')}, indent=2))


if __name__ == '__main__':
    main()
