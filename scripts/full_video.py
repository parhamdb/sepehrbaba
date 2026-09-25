#!/usr/bin/env python3
"""Retain every native video frame and recover bootstrap camera components.

Requires ffmpeg, ffprobe, CUDA COLMAP 3.12.6, Brush 0.3.0, and Pillow.
Use repair_scene.py to refine a bounded component before masking and training.
No disconnected models are silently joined. Nothing is automatically published.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import time


def write(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def count(path):
    with path.open('rb') as f:
        return struct.unpack('<Q', f.read(8))[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', type=Path)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--colmap', required=True)
    p.add_argument('--brush', help='Legacy compatibility; preparation does not train')
    p.add_argument('--max-seconds', type=int, default=7200)
    p.add_argument('--steps', type=int, default=15000)
    p.add_argument('--stop-after', choices=['extract', 'features', 'match', 'map'], default='map')
    a = p.parse_args()
    if a.max_seconds <= 0 or a.steps < 1:
        p.error('Positive time budget and steps required')
    a.video = a.video.resolve()
    work = a.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    lock = (work / '.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    started = time.monotonic()
    logs = work / 'logs'
    logs.mkdir(exist_ok=True)
    state_path = work / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'stages': {}}
    config = {'script_sha256': digest(Path(__file__)), 'video_sha256': digest(a.video), 'native_frames': True, 'jpeg_quality': 1,
              'bootstrap_group': 4, 'steps': a.steps, 'colmap': str(Path(a.colmap).resolve()),
              'matching': 'linear-native-plus-explicit-keyframe-neighbors'}
    if state.get('config', config) != config:
        raise RuntimeError('Source/settings changed; preserve this run and choose another work directory')
    state['config'] = config
    state['pid'] = os.getpid()
    write(state_path, state)

    def stage(name, command, outputs=()):
        if state['stages'].get(name, {}).get('status') == 'passed':
            if not all(Path(f).exists() for f in outputs):
                raise RuntimeError(f'{name}: completed output missing; restore it or use a fresh directory')
            return
        if time.monotonic() - started >= a.max_seconds:
            raise RuntimeError('Runtime budget reached; rerun the same command to resume completed stages')
        state['stages'][name] = {'status': 'running', 'started': time.time()}
        write(state_path, state)
        print(f'[{name}] started; log: {logs / (name + ".log")}', flush=True)
        with (logs / (name + '.log')).open('a') as log:
            child = subprocess.Popen(list(map(str, command)), stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            try:
                while child.poll() is None:
                    time.sleep(2)
                    mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
                    if int(mem['MemAvailable'].split()[0]) < 4 * 1024 * 1024:
                        raise RuntimeError('Available memory below 4 GiB; stopped this job to preserve other workloads')
                    if time.monotonic() - started >= a.max_seconds:
                        raise RuntimeError('Runtime budget reached; completed stages retained')
                if child.returncode:
                    raise RuntimeError(f'{name} exited {child.returncode}; see its log')
                if not all(Path(f).exists() for f in outputs):
                    raise RuntimeError(f'{name}: expected output missing')
            except BaseException as error:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
                state['stages'][name].update(status='blocked', error=str(error))
                write(state_path, state)
                raise
        state['stages'][name].update(status='passed', finished=time.time())
        write(state_path, state)
        print(f'[{name}] passed', flush=True)

    frames = work / 'images'
    frames.mkdir(exist_ok=True)
    probe_path = work / 'source.json'
    if not probe_path.exists():
        probe = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_streams', '-show_frames', '-show_entries',
            'stream=width,height,nb_frames,duration:frame=best_effort_timestamp_time', '-of', 'json', str(a.video)])
        write(probe_path, json.loads(probe))
    probe = json.loads(probe_path.read_text())
    expected = len(probe['frames'])
    if not expected:
        raise RuntimeError('No video frames reported')
    # Preserve the demuxer's timestamp precision. The MJPEG default time base
    # can round distinct VFR frames to the same PTS and stop encoding.
    stage('extract', ['ffmpeg', '-nostdin', '-y', '-v', 'warning', '-threads', '2', '-i', a.video,
        '-map', '0:v:0', '-fps_mode', 'passthrough', '-enc_time_base', '-1',
        '-q:v', '1', '-threads', '2', frames / 'frame_%06d.jpg'],
        [frames / f'frame_{expected:06d}.jpg'])
    files = sorted(frames.glob('frame_*.jpg'))
    if len(files) != expected:
        raise RuntimeError(f'Frame inventory mismatch: {len(files)} extracted / {expected} decoded')
    manifest = [{'name': f.name, 'timestamp': float(t['best_effort_timestamp_time'])}
                for f, t in zip(files, probe['frames'])]
    write(work / 'frames.json', manifest)
    if a.stop_after == 'extract':
        return
    keyframes = work / 'keyframes.txt'
    if not keyframes.exists():
        from PIL import Image, ImageFilter, ImageStat
        chosen = []
        for start in range(0, len(files), 4):
            candidates = []
            for path in files[start:start + 4]:
                with Image.open(path) as im:
                    if im.size != (probe['streams'][0]['width'], probe['streams'][0]['height']):
                        raise RuntimeError(f'Native dimensions changed: {path}')
                    im.thumbnail((320, 320))
                    score = ImageStat.Stat(im.convert('L').filter(ImageFilter.FIND_EDGES)).var[0]
                candidates.append((score, path.name))
            chosen.append(max(candidates)[1])
        keyframes.write_text('\n'.join(chosen) + '\n')
    db = work / 'database.db'
    stage('features', [a.colmap, 'feature_extractor', '--database_path', db, '--image_path', frames,
        '--ImageReader.single_camera', '1', '--ImageReader.camera_model', 'SIMPLE_RADIAL',
        '--SiftExtraction.use_gpu', '1', '--SiftExtraction.max_image_size', '1920',
        '--SiftExtraction.num_threads', '2'], [db])
    if a.stop_after == 'features':
        return
    stage('match', [a.colmap, 'sequential_matcher', '--database_path', db,
        '--SiftMatching.use_gpu', '1', '--SiftMatching.num_threads', '2',
        '--SequentialMatching.overlap', '10', '--SequentialMatching.quadratic_overlap', '0'], [db])
    keys = keyframes.read_text().splitlines()
    pairs = work / 'keyframe-pairs.txt'
    pairs.write_text(''.join(f'{first} {second}\n' for i, first in enumerate(keys)
                            for second in keys[i + 1:i + 6]))
    stage('match-keyframes', [a.colmap, 'matches_importer', '--database_path', db,
        '--match_list_path', pairs, '--match_type', 'pairs',
        '--SiftMatching.use_gpu', '1', '--SiftMatching.num_threads', '2'], [db])
    if a.stop_after == 'match':
        return
    sparse = work / 'sparse'
    if sparse.exists() and state['stages'].get('map', {}).get('status') != 'passed':
        sparse.rename(work / f'sparse-interrupted-{time.time_ns()}')
    sparse.mkdir(exist_ok=True)
    stage('map', [a.colmap, 'mapper', '--database_path', db, '--image_path', frames,
        '--image_list_path', keyframes, '--output_path', sparse, '--Mapper.num_threads', '2'], [sparse])
    components = sorted(d for d in sparse.iterdir() if (d / 'images.bin').exists())
    if not components:
        raise RuntimeError('No camera model recovered; inspect map.log')
    union, report = set(), []
    for model in components:
        text_model = work / f'model-text-{model.name}'
        text_model.mkdir(exist_ok=True)
        stage(f'inspect-{model.name}', [a.colmap, 'model_converter', '--input_path', model,
            '--output_path', text_model, '--output_type', 'TXT'], [text_model / 'images.txt'])
        names = [line.split()[-1] for line in (text_model / 'images.txt').read_text().splitlines()
                 if line.rstrip().endswith('.jpg')]
        union.update(names)
        npoints = count(model / 'points3D.bin')
        report.append({'component': model.name, 'registered_frames': len(names), 'points': npoints,
                       'names': names, 'trainable': False, 'status': 'bootstrap-needs-refinement'})
    write(work / 'coverage.json', {'source_frames': expected, 'registered_unique': len(union),
        'fraction': len(union) / expected, 'components': report,
        'unregistered': [item for item in manifest if item['name'] not in union],
        'connected_full_scene': len(components) == 1 and len(union) == expected})
    print('Bootstrap geometry only. Refine a bounded interval with repair_scene.py; '
          'training requires separate geometry and visual checks.', flush=True)


if __name__ == '__main__':
    main()
