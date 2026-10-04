#!/usr/bin/env python3
"""Collect existing full-recording splats into a portable, unaligned LAN library.

Retains failed components and actual frame coverage. Does not retrain, certify,
mask, align sections, or change source artifacts. Requires NumPy and Pillow.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image
from clean_static_geometry import rotation


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def seed_placement(model):
    rows = []
    with (model / 'images.txt').open() as stream:
        for line in stream:
            if line.strip() and not line.startswith('#'):
                rows.append(line.split())
                next(stream)
    rows.sort(key=lambda r: r[9])
    row = rows[len(rows) // 2]
    R = rotation(row)
    t = np.array(row[5:8], float)
    depths = []
    for line in (model / 'points3D.txt').read_text().splitlines():
        if line.strip() and not line.startswith('#'):
            xyz = np.array(line.split()[1:4], float)
            z = (R @ xyz + t)[2]
            if np.isfinite(z) and z > 0:
                depths.append(z)
    if not depths:
        raise ValueError('No positive sparse depths for a preview camera')
    scale = 1 / float(np.median(depths))
    D = np.diag([-1., -1., 1.])
    # Editor applies D below the editable parent. Put the seed camera at origin,
    # looking toward +Z with +Y up. This is an individual display gauge, not a join.
    return {'seed': row[9], 'rotation_matrix': (D @ R @ D).tolist(),
            'position': (D @ t * scale).tolist(), 'scale': scale,
            'meaning': 'Independent seed-camera normalization; no cross-section alignment.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--published', nargs=3, action='append', default=[], metavar=('ID', 'TRAINING', 'MODEL_TEXT'))
    args = parser.parse_args()
    state = json.loads((args.campaign / 'state.json').read_text())
    frames = json.loads((Path(state['config']['source_run']) / 'frames.json').read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    for folder in ['assets', 'previews']:
        (args.output / folder).mkdir()
    entries, failures, covered = [], [], set()
    published = {identity: (Path(training), Path(model)) for identity, training, model in args.published}
    for c in sorted(state['components'], key=lambda x: (x['start'], x['end'], x['id'])):
        base = args.campaign / 'components' / c['id']
        training, model = published.get(c['id'], (base / 'training', base / 'prepared/dataset-model-text'))
        ply = training / 'splats/scene.ply'
        if not ply.is_file():
            failures.append({k: c[k] for k in ['id', 'start', 'end', 'status', 'failed_stage', 'registered_frames', 'quality', 'covered_by'] if k in c})
            continue
        header = ply.open('rb')
        lines = []
        with header:
            while True:
                line = header.readline()
                if not line or len(lines) > 100: raise ValueError('Invalid PLY header')
                lines.append(line)
                if line.strip() == b'end_header': break
        text = b''.join(lines).decode('ascii')
        if not all(f' {key}\n' in text for key in ['x', 'opacity', 'scale_0', 'rot_0']):
            raise ValueError('Missing Gaussian PLY fields')
        count = int(next(l.split()[2] for l in text.splitlines() if l.startswith('element vertex ')))
        if count <= 0: raise ValueError('Empty PLY')
        placement = seed_placement(model)
        name = c['id'] + '.ply'
        shutil.copyfile(ply, args.output / 'assets' / name)
        digest = sha(ply)
        if sha(args.output / 'assets' / name) != digest: raise ValueError('Copy changed bytes')
        renders = sorted((training / 'splats/eval_8000').glob('*.png'))
        if not renders: raise ValueError('Missing actual held-out render')
        render = renders[len(renders) // 2]
        with Image.open(render) as image:
            image.thumbnail((270, 480))
            image.convert('RGB').save(args.output / 'previews' / (c['id'] + '.jpg'), quality=85)
        entries.append({'id': c['id'], 'start': c['start'], 'end': c['end'],
            'registered_frames': len(c['names']), 'frame_names': c['names'],
            'asset': name, 'sha256': digest, 'bytes': ply.stat().st_size, 'gaussians': count,
            'preview': c['id'] + '.jpg', 'preview_frame': render.stem,
            'placement': placement, 'original_status': c['status'],
            'mask_method': 'Legacy blanket person masks; static human details may be removed.',
            'quality': 'Unreviewed independent reconstruction; rays and ghosts may remain.'})
        covered.update(c['names'])
    missing = []
    for index, f in enumerate(frames):
        if f['name'] in covered: continue
        end = frames[index+1]['timestamp'] if index+1 < len(frames) else state['config']['duration']
        if missing and missing[-1]['end'] == f['timestamp']:
            missing[-1]['end'] = end; missing[-1]['frames'] += 1
        else: missing.append({'start': f['timestamp'], 'end': end, 'frames': 1})
    report = {'version': 1, 'duration': state['config']['duration'], 'source_frames': len(frames),
        'trained_frames': len(covered), 'sections': entries, 'unavailable_components': failures,
        'missing_intervals': missing, 'windows': state['windows'],
        'coverage_bins': [{'start': start, 'end': min(start+10, state['config']['duration']),
            'source_frames': sum(start <= f['timestamp'] < start+10 for f in frames),
            'trained_frames': sum(start <= f['timestamp'] < start+10 and f['name'] in covered for f in frames)}
            for start in range(0, int(state['config']['duration'])+1, 10)],
        'script_sha256': sha(Path(__file__)), 'campaign_state_sha256': sha(args.campaign / 'state.json'),
        'warning': 'Independent sections, not a continuous reconstruction. Legacy masks differ from the selectively masked current pair.'}
    (args.output / 'catalog.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'sections': len(entries), 'trained_frames': len(covered),
        'source_frames': len(frames), 'bytes': sum(e['bytes'] for e in entries)}))


if __name__ == '__main__':
    main()
