#!/usr/bin/env python3
"""Estimate display up from manually selected floor pixels and rotate a scene pose.

Reads an undistorted COLMAP TXT model. Writes a new viewer manifest; never changes
the PLY or source model. Scene units and the estimated floor are not surveyed.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from clean_static_geometry import rotation


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-text', type=Path, required=True)
    p.add_argument('--scene', type=Path, required=True)
    p.add_argument('--selection', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    scene = json.loads(a.scene.read_text())
    selection = json.loads(a.selection.read_text())
    if a.output.exists() or 'orientation' in scene:
        raise ValueError('Use an unrotated scene and a fresh output')
    cameras = {}
    for line in (a.model_text/'cameras.txt').read_text().splitlines():
        if line.strip() and not line.startswith('#'):
            row = line.split(); cameras[int(row[0])] = tuple(map(int, row[2:4]))
    regions = {r['image']: r for r in selection['regions']}
    ids, centers, counts = set(), [], {}
    to_viewer = np.diag([-1., -1., 1.])
    with (a.model_text/'images.txt').open() as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            row = line.split(); observations = next(f)
            if row[9] not in regions:
                continue
            region = regions[row[9]]; size = region['reference_size']
            mask = Image.new('1', tuple(size))
            ImageDraw.Draw(mask).polygon([tuple(v) for v in region['polygon_pixels']], fill=1)
            width, height = cameras[int(row[8])]
            selected = set()
            for x, y, pid in np.fromstring(observations, sep=' ').reshape(-1, 3):
                ix, iy = int(x/width*size[0]), int(y/height*size[1])
                if pid >= 0 and 0 <= ix < size[0] and 0 <= iy < size[1] and mask.getpixel((ix, iy)):
                    selected.add(int(pid))
            ids.update(selected); counts[row[9]] = len(selected)
            centers.append(to_viewer @ (-rotation(row).T @ np.array(row[5:8], float)))
    if set(counts) != set(regions) or any(n < 10 for n in counts.values()):
        raise ValueError('Each floor region needs at least ten reconstructed points')
    xyz = []
    with (a.model_text/'points3D.txt').open() as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                row = line.split()
                if int(row[0]) in ids:
                    xyz.append(to_viewer @ np.array(row[1:4], float))
    xyz = np.array(xyz)
    if len(xyz) < 30 or not np.isfinite(xyz).all():
        raise ValueError('Need at least thirty finite floor candidates')
    threshold = float(selection['threshold_scene_units'])
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError('Positive finite threshold required')
    rng = np.random.default_rng(0); best = np.zeros(len(xyz), dtype=bool)
    for _ in range(2000):
        aa, bb, cc = xyz[rng.choice(len(xyz), 3, replace=False)]
        normal = np.cross(bb-aa, cc-aa); length = np.linalg.norm(normal)
        if length < 1e-10:
            continue
        normal /= length
        inliers = np.abs((xyz-aa)@normal) < threshold
        if inliers.sum() > best.sum():
            best = inliers
    for _ in range(3):
        if best.sum() < max(30, .6*len(xyz)):
            raise ValueError('Selected floor points do not support a coherent plane')
        center = xyz[best].mean(0)
        _, singular, vectors = np.linalg.svd(xyz[best]-center, full_matrices=False)
        normal = vectors[-1]
        best = np.abs((xyz-center)@normal) < threshold
    if singular[1] < 5*singular[2]:
        raise ValueError('Floor fit is too thin or noisy to establish up')
    if (np.mean(centers, axis=0)-center)@normal < 0:
        normal = -normal
    # Quaternion rotating the fitted upward normal to the viewer's +Y axis.
    q = np.array([-normal[2], 0., normal[0], 1+normal[1]])
    if np.linalg.norm(q) < 1e-8:
        raise ValueError('Opposite up direction needs explicit review')
    q /= np.linalg.norm(q)
    x, y, z, w = q
    matrix = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                       [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                       [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    assert np.allclose(matrix@normal, [0, 1, 0], atol=1e-8)
    origin = np.array(scene['camera']['position'])
    forward = np.array(scene['camera']['target'])-origin
    forward /= np.linalg.norm(forward)
    distance = float((center-origin)@normal / (forward@normal))
    if not np.isfinite(distance) or distance <= 0:
        raise ValueError('The opening view must point toward the selected floor')
    target = origin+forward*distance
    scene['orientation'] = {'rotation_xyzw': q.tolist(), 'floor_normal_before': normal.tolist(),
        'floor_center_before': center.tolist(), 'orbit_distance_scene_units': distance,
        'degrees': float(np.degrees(np.arccos(np.clip(normal[1], -1, 1)))),
        'selected_points': len(xyz), 'inlier_points': int(best.sum()), 'region_counts': counts,
        'floor_rms_scene_units': float(np.sqrt(np.mean(((xyz[best]-center)@normal)**2))),
        'method': 'RANSAC and SVD fit to manually selected floor pixels; display alignment only',
        'source_camera': scene['camera'], 'selection': selection}
    scene['camera'] = {**scene['camera'], 'position': (matrix@origin).tolist(), 'target': (matrix@target).tolist()}
    a.output.write_text(json.dumps(scene, indent=2)+'\n')
    print(json.dumps(scene['orientation'], indent=2))


if __name__ == '__main__':
    main()
