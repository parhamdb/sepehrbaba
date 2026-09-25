#!/usr/bin/env python3
"""Build a separate static-only COLMAP dataset from an already masked dataset.

Images, masks, intrinsics, frame inventory and evaluation ordering are preserved.
Requires NumPy, Pillow and COLMAP 3.12.6. Does not train or publish.
"""
import argparse
from collections import Counter, defaultdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_model(path):
    images, points = {}, {}
    with (path / 'images.txt').open() as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            row = line.split()
            obs = np.fromstring(next(f), sep=' ').reshape(-1, 3)
            images[int(row[0])] = {'row': row, 'obs': obs}
    for line in (path / 'points3D.txt').read_text().splitlines():
        if line.strip() and not line.startswith('#'):
            row = line.split()
            points[int(row[0])] = row[:8]
    return images, points


def tracks_for(images):
    tracks = defaultdict(list)
    for iid, image in images.items():
        ids = image['obs'][:, 2].astype('int64')
        valid = ids[ids >= 0]
        if len(np.unique(valid)) != len(valid):
            raise ValueError('Duplicate point association in one image')
        for index in np.flatnonzero(ids >= 0):
            tracks[int(ids[index])].append((iid, int(index)))
    return tracks


def write_model(path, cameras_text, images, points):
    path.mkdir(exist_ok=True)
    (path / 'cameras.txt').write_text(cameras_text)
    tracks = tracks_for(images)
    if set(tracks) != set(points) or any(len(t) < 2 for t in tracks.values()):
        raise ValueError('Geometry must have reciprocal tracks supported by >=2 images')
    with (path / 'images.txt').open('w') as f:
        for iid in sorted(images):
            image = images[iid]
            f.write(' '.join(image['row']) + '\n')
            f.write(' '.join(f'{x:.17g} {y:.17g} {int(pid)}'
                             for x, y, pid in image['obs']) + '\n')
    with (path / 'points3D.txt').open('w') as f:
        for pid in sorted(points):
            f.write(' '.join(points[pid]) + ' ' +
                    ' '.join(f'{iid} {idx}' for iid, idx in tracks[pid]) + '\n')


def rotation(row):
    w, x, y, z = map(float, row[1:5])
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def measure(images, points, cameras_text):
    cameras = {}
    for line in cameras_text.splitlines():
        if line.strip() and not line.startswith('#'):
            row = line.split()
            if row[1] != 'PINHOLE':
                raise ValueError('Expected undistorted PINHOLE cameras')
            cameras[int(row[0])] = np.array(row[4:], float)
    errors, depths = [], []
    for image in images.values():
        obs = image['obs']; obs = obs[obs[:, 2] >= 0]
        if not len(obs):
            continue
        xyz = np.array([points[int(pid)][1:4] for pid in obs[:, 2]], float)
        row = image['row']; R = rotation(row)
        cam = xyz @ R.T + np.array(row[5:8], float)
        fx, fy, cx, cy = cameras[int(row[8])]
        uv = cam[:, :2] / cam[:, 2, None] * [fx, fy] + [cx, cy]
        errors.extend(np.linalg.norm(uv - obs[:, :2], axis=1))
        depths.extend(cam[:, 2])
    if not errors or not np.isfinite(errors).all():
        raise ValueError('Empty or non-finite reprojection errors')
    return {'mean_reprojection_px': float(np.mean(errors)),
            'p95_reprojection_px': float(np.percentile(errors, 95)),
            'median_depth': float(np.median(depths)),
            'behind_camera_observations': int((np.array(depths) <= 0).sum())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dataset', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--colmap', required=True)
    parser.add_argument('--minimum-camera-observations', type=int, default=30)
    args = parser.parse_args()
    if args.minimum_camera_observations < 6:
        parser.error('At least six observations per refined camera required')
    source = args.source_dataset.resolve(); work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    lock = (work / '.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if any(p.name != '.lock' for p in work.iterdir()):
        raise RuntimeError('Retain existing results and use a fresh work directory')
    logs = work / 'logs'; logs.mkdir()
    def run(name, *command):
        print(name, 'started', flush=True)
        with (logs / (name + '.log')).open('w') as log:
            subprocess.run([args.colmap, *map(str, command)], check=True, timeout=300,
                           stdout=log, stderr=subprocess.STDOUT,
                           env=dict(os.environ, OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='2'))
        print(name, 'passed', flush=True)

    original = work / 'original'; original.mkdir()
    run('read', 'model_converter', '--input_path', source / 'sparse',
        '--output_path', original, '--output_type', 'TXT')
    images, points = read_model(original)
    original_rows = {iid: list(im['row']) for iid, im in images.items()}
    cameras_text = (original / 'cameras.txt').read_text()
    before_count = len(points)
    files = []
    duplicate_observations_removed = 0
    camera_params = {}
    for line in cameras_text.splitlines():
        if line.strip() and not line.startswith('#'):
            row = line.split()
            if row[1] != 'PINHOLE':
                raise ValueError('Expected undistorted PINHOLE cameras')
            camera_params[int(row[0])] = np.array(row[4:], float)
    for image in images.values():
        name = image['row'][9]
        path = source / 'images' / name
        mask_path = source / 'masks' / (Path(name).stem + '.png')
        with Image.open(path) as im, Image.open(mask_path) as mask_image:
            if im.size != mask_image.size or mask_image.mode != 'L':
                raise ValueError('Expected grayscale mask at exact image dimensions')
            mask = np.asarray(mask_image)
        files.extend([path, mask_path])
        obs = image['obs']; x = np.rint(obs[:, 0]).astype(int); y = np.rint(obs[:, 1]).astype(int)
        keep = (x >= 0) & (y >= 0) & (x < mask.shape[1]) & (y < mask.shape[0])
        keep[keep] &= mask[y[keep], x[keep]] > 0
        obs[~keep, 2] = -1
        # COLMAP can retain multiple feature observations for a point in one
        # image. Count distinct views, retaining the best static observation.
        grouped = defaultdict(list)
        for index in np.flatnonzero(obs[:, 2] >= 0):
            grouped[int(obs[index, 2])].append(index)
        row = image['row']; R = rotation(row); t = np.array(row[5:8], float)
        fx, fy, cx, cy = camera_params[int(row[8])]
        for pid, indices in grouped.items():
            if len(indices) > 1:
                xyz = R @ np.array(points[pid][1:4], float) + t
                uv = xyz[:2] / xyz[2] * [fx, fy] + [cx, cy]
                best = indices[int(np.argmin(np.linalg.norm(obs[indices, :2] - uv, axis=1)))]
                for index in indices:
                    if index != best:
                        obs[index, 2] = -1
                        duplicate_observations_removed += 1

    # Removing weak cameras can invalidate short tracks, so prune to a fixed point.
    frozen = set()
    while True:
        changed = False
        counts = Counter(int(pid) for im in images.values() for pid in im['obs'][:, 2] if pid >= 0)
        for iid, im in images.items():
            obs = im['obs']
            drop = np.array([pid >= 0 and counts[int(pid)] < 2 for pid in obs[:, 2]])
            if drop.any():
                obs[drop, 2] = -1; changed = True
            if (obs[:, 2] >= 0).sum() < args.minimum_camera_observations and iid not in frozen:
                frozen.add(iid); obs[:, 2] = -1; changed = True
        if not changed:
            break
    tracks = tracks_for(images); points = {pid: points[pid] for pid in tracks}
    active = {iid: im for iid, im in images.items() if iid not in frozen}
    # All refined cameras must remain in one connected observation graph.
    parent = {iid: iid for iid in active}
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for track in tracks.values():
        for iid, _ in track[1:]:
            parent[find(iid)] = find(track[0][0])
    if len({find(i) for i in active}) != 1 or len(points) < 1000:
        raise RuntimeError('Static geometry disconnected or too small; training blocked')
    before = measure(images, points, cameras_text)
    filtered = work / 'filtered'; write_model(filtered, cameras_text, active, points)
    adjusted = work / 'adjusted'; adjusted.mkdir()
    run('refine', 'bundle_adjuster', '--input_path', filtered, '--output_path', adjusted,
        '--BundleAdjustment.refine_focal_length', '0', '--BundleAdjustment.refine_principal_point', '0',
        '--BundleAdjustment.refine_extra_params', '0', '--BundleAdjustment.refine_sensor_from_rig', '0')
    adjusted_text = work / 'adjusted-text'; adjusted_text.mkdir()
    run('inspect', 'model_converter', '--input_path', adjusted, '--output_path', adjusted_text,
        '--output_type', 'TXT')
    refined_images, refined_points = read_model(adjusted_text)
    if set(refined_images) != set(active) or set(refined_points) != set(points):
        raise RuntimeError('Bundle adjustment changed the camera or point inventory')
    translations, angles = [], []
    for iid, im in refined_images.items():
        old = original_rows[iid]; new = im['row']; R0 = rotation(old); R1 = rotation(new)
        translations.append(float(np.linalg.norm(-R0.T @ np.array(old[5:8], float) + R1.T @ np.array(new[5:8], float))))
        angles.append(float(np.degrees(np.arccos(np.clip((np.trace(R1 @ R0.T)-1)/2, -1, 1)))))
        images[iid] = im
    after = measure(images, refined_points, cameras_text)
    report = {'source_dataset': str(source), 'source_script_sha256': digest(Path(__file__)),
              'original_points': before_count, 'retained_points': len(refined_points),
              'removed_points': before_count-len(refined_points), 'frames': len(images),
              'duplicate_observations_removed': duplicate_observations_removed,
              'refined_cameras': len(active), 'frozen_camera_names': [images[i]['row'][9] for i in sorted(frozen)],
              'before_static_refinement': before, 'after_static_refinement': after,
              'maximum_camera_translation': max(translations), 'maximum_camera_rotation_degrees': max(angles)}
    report['accepted_geometry'] = (after['mean_reprojection_px'] <= 1.5 and after['p95_reprojection_px'] <= 3.5
        and after['behind_camera_observations'] == 0 and max(angles) <= 5
        and max(translations) <= before['median_depth'] * .1)
    (work / 'quality.json').write_text(json.dumps(report, indent=2) + '\n')
    if not report['accepted_geometry']:
        raise RuntimeError('Static geometry or pose-change gate failed; training blocked')
    final_text = work / 'final-text'; write_model(final_text, cameras_text, images, refined_points)
    dataset = work / 'dataset'; dataset.mkdir(); sparse = dataset / 'sparse'; sparse.mkdir()
    run('export', 'model_converter', '--input_path', final_text, '--output_path', sparse, '--output_type', 'BIN')
    for directory in ['images', 'masks']:
        shutil.copytree(source / directory, dataset / directory)
    manifest = {str(p.relative_to(source)): digest(p) for p in files}
    if any(digest(dataset / name) != checksum for name, checksum in manifest.items()):
        raise RuntimeError('Images or masks changed during copying')
    (work / 'image-mask-hashes.json').write_text(json.dumps(manifest, indent=2) + '\n')
    report['images_and_masks_byte_identical'] = True
    (work / 'quality.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
