#!/usr/bin/env python3
"""Remove invalid sparse point tracks from a copy of a SIMPLE_RADIAL TXT model.

Recomputes projections rather than trusting stored point errors. Keeps every
camera and feature coordinate, removing reciprocal associations for rejected
points. Does not alter source frames, refine poses, train, or publish.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

from clean_static_geometry import rotation


def sanitize(source, output, maximum=100.0):
    if output.exists():
        raise ValueError('Use a fresh output directory; preserve previous models')
    if not np.isfinite(maximum) or maximum <= 0:
        raise ValueError('Positive finite projection threshold required')
    cameras = {}
    for line in (source/'cameras.txt').read_text().splitlines():
        if line.strip() and not line.startswith('#'):
            row = line.split()
            if row[1] != 'SIMPLE_RADIAL':
                raise ValueError('Expected distorted SIMPLE_RADIAL input')
            cameras[int(row[0])] = np.array(row[4:], float)
    points = {}
    with (source/'points3D.txt').open() as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                row = line.split(); points[int(row[0])] = list(map(float, row[1:4]))
    ids = np.array(sorted(points), dtype=np.int64)
    if not len(ids):
        raise ValueError('Empty model')
    xyz = np.array([points[i] for i in ids])
    rejected, observations, camera_count = set(), [], 0
    with (source/'images.txt').open() as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            row = line.split(); camera_count += 1
            obs = np.fromstring(next(f).strip(), sep=' ').reshape(-1, 3)
            obs = obs[obs[:, 2] >= 0]
            if not len(obs):
                continue
            point_ids = obs[:, 2].astype(np.int64)
            indices = np.searchsorted(ids, point_ids)
            if np.any(indices >= len(ids)) or not np.all(ids[indices] == point_ids):
                raise ValueError('Unknown point association')
            R = rotation(row); t = np.array(row[5:8], float)
            params = cameras[int(row[8])]
            if not all(np.isfinite(v).all() for v in [R, t, params]):
                raise ValueError('Invalid camera parameters; point filtering is insufficient')
            camera = xyz[indices] @ R.T + t
            focal, cx, cy, radial = params
            with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
                xy = camera[:, :2] / camera[:, 2, None]
                projection = focal*xy*(1+radial*(xy*xy).sum(axis=1))[:, None]+[cx, cy]
                errors = np.linalg.norm(projection-obs[:, :2], axis=1)
            invalid = (camera[:, 2] <= 0) | ~np.isfinite(errors) | (errors > maximum)
            for i in np.flatnonzero(invalid):
                pid = int(point_ids[i]); rejected.add(pid)
                observations.append({'image': row[9], 'point_id': pid,
                    'depth': float(camera[i, 2]) if np.isfinite(camera[i, 2]) else None,
                    'reprojection_px': float(errors[i]) if np.isfinite(errors[i]) else None})
    output.mkdir(parents=True)
    shutil.copyfile(source/'cameras.txt', output/'cameras.txt')
    removed_associations = 0
    with (source/'images.txt').open() as src, (output/'images.txt').open('w') as dst:
        for line in src:
            dst.write(line)
            if not line.strip() or line.startswith('#'):
                continue
            observation_line = next(src)
            obs = np.fromstring(observation_line.strip(), sep=' ').reshape(-1, 3)
            drop = np.isin(obs[:, 2].astype(np.int64), list(rejected))
            if drop.any():
                removed_associations += int(drop.sum()); obs[drop, 2] = -1
                dst.write(' '.join(f'{x:.17g} {y:.17g} {int(pid)}' for x,y,pid in obs)+'\n')
            else:
                dst.write(observation_line)
    with (source/'points3D.txt').open() as src, (output/'points3D.txt').open('w') as dst:
        for line in src:
            if not line.strip() or line.startswith('#') or int(line.split()[0]) not in rejected:
                dst.write(line)
    report = {'cameras_preserved': camera_count, 'original_points': len(points),
        'retained_points': len(points)-len(rejected), 'removed_point_ids': sorted(rejected),
        'removed_associations': removed_associations, 'invalid_observations': observations,
        'maximum_reprojection_px': maximum,
        'source_model_sha256': {n: hashlib.file_digest((source/n).open('rb'), 'sha256').hexdigest()
            for n in ['cameras.txt','images.txt','points3D.txt']}}
    (output/'sanitization.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-model', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--max-reprojection', type=float, default=100)
    a = p.parse_args()
    print(json.dumps(sanitize(a.source_model, a.output, a.max_reprojection), indent=2))
