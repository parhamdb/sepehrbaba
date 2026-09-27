#!/usr/bin/env python3
"""Track reviewed native-pixel landmarks on a short original-frame interval.

Requires the official CoTracker checkout on PYTHONPATH and a compatible torch
environment. Outputs hypotheses, never accepted camera connections. A reverse
pass checks cycle consistency; it is not independent correspondence evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np
import torch
from cotracker.predictor import CoTrackerPredictor


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('images', 'selection', 'seed', 'checkpoint', 'model_repo', 'output'):
        p.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    p.add_argument('--crop', type=int, nargs=4, required=True, metavar=('X0', 'Y0', 'X1', 'Y1'))
    p.add_argument('--padding-frames', type=int, default=3)
    a = p.parse_args()
    if a.output.exists():
        p.error('Output already exists; preserve previous experiment')
    selection = json.loads(a.selection.read_text())
    seed = json.loads(a.seed.read_text())
    if seed['verdict'] != 'supported' or not seed['points']:
        p.error('Need visually supported seed points')
    names = [f['name'] for f in selection['frames']]
    si, ti = names.index(seed['seed_frame']), names.index(seed['target_frame'])
    if si == ti or a.padding_frames < 0:
        p.error('Need distinct seed/target and nonnegative padding')
    start, end = max(0, min(si, ti)-a.padding_frames), min(len(names), max(si, ti)+a.padding_frames+1)
    rows = selection['frames'][start:end]
    si, ti = si-start, ti-start
    x0, y0, x1, y1 = a.crop
    if not (0 <= x0 < x1 <= 1080 and 0 <= y0 < y1 <= 1920):
        p.error('Crop must be within native 1080x1920 images')
    points = seed['points']
    if len({q['id'] for q in points}) != len(points):
        p.error('Point IDs must be unique')
    for q in points:
        if not (x0 <= q['x'] < x1 and y0 <= q['y'] < y1):
            p.error('Seed outside crop')
    frames = []
    for row in rows:
        name = row['name']
        if Path(name).name != name:
            p.error('Expected image basename')
        source = a.images/name
        if digest(source) != selection['image_sha256'][name]:
            raise ValueError('Source hash mismatch: ' + name)
        im = cv2.imread(str(source))
        if im is None or im.shape != (1920, 1080, 3):
            raise ValueError('Expected native image: ' + name)
        frames.append(cv2.cvtColor(im[y0:y1, x0:x1], cv2.COLOR_BGR2RGB))
    torch.manual_seed(0)
    torch.set_num_threads(4)
    video = torch.from_numpy(np.stack(frames)).permute(0, 3, 1, 2)[None].float().cuda()
    model = CoTrackerPredictor(checkpoint=str(a.checkpoint), offline=True).eval().cuda()
    query = torch.tensor([[[si, q['x']-x0, q['y']-y0] for q in points]], device='cuda', dtype=torch.float32)
    begin = time.monotonic()
    print(json.dumps({'stage': 'tracking', 'frames': len(rows), 'points': len(points), 'crop': a.crop}), flush=True)
    with torch.inference_mode():
        tracks, visibility = model(video, queries=query, backward_tracking=True)
        # Query from the predicted target in reversed frame order. Checking only
        # the forced query coordinates would trivially yield zero error.
        reverse_query = torch.cat([torch.full((1, len(points), 1), len(rows)-1-ti, device='cuda'), tracks[:, ti]], dim=-1)
        reverse_tracks, reverse_visibility = model(video.flip(1), queries=reverse_query, backward_tracking=True)
    forward = tracks[0].cpu().numpy() + np.array([x0, y0])
    reverse = reverse_tracks[0].flip(0).cpu().numpy() + np.array([x0, y0])
    visible = visibility[0].cpu().numpy()
    reverse_visible = reverse_visibility[0].flip(0).cpu().numpy()
    if not np.isfinite(forward).all() or not np.isfinite(reverse).all():
        raise ValueError('Nonfinite trajectory')
    cycles = np.linalg.norm(reverse[si] - np.array([[q['x'], q['y']] for q in points]), axis=1)
    result = {
        'schema': 1, 'method': 'CoTracker3 offline; original-frame crop; reversed-video cycle check',
        'model_revision': subprocess.check_output(['git', '-C', str(a.model_repo), 'rev-parse', 'HEAD'], text=True).strip(),
        'model_resolution_hw': list(model.interp_shape), 'torch_version': torch.__version__,
        'identity': {'checkpoint_sha256': digest(a.checkpoint), 'script_sha256': digest(__file__), 'selection_sha256': digest(a.selection), 'seed_sha256': digest(a.seed)},
        'crop_xyxy': a.crop, 'seed_frame': seed['seed_frame'], 'target_frame': seed['target_frame'],
        'points': points, 'elapsed_seconds': time.monotonic()-begin,
        'target_predictions': [{'id': q['id'], 'xy': forward[ti, j].tolist(), 'predicted_visible': bool(visible[ti, j]), 'cycle_error_native_px': float(cycles[j]), 'reverse_seed_predicted_visible': bool(reverse_visible[si, j])} for j, q in enumerate(points)],
        'frames': [{'name': row['name'], 'timestamp': row['timestamp'], 'xy': forward[i].tolist(), 'predicted_visible': visible[i].tolist(), 'reverse_xy': reverse[i].tolist(), 'reverse_predicted_visible': reverse_visible[i].tolist()} for i, row in enumerate(rows)],
        'limitations': ['Visibility is a model prediction, thresholded by the official predictor at 0.9; query-frame visibility/coordinates are forced by that predictor.', 'Cycle consistency uses the same model and cannot certify semantic identity or stationarity.', 'No cross-gap solve or accepted camera connection; independent marked-image review required.'],
        'accepted_connection': False,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'stage': 'complete', 'elapsed_seconds': result['elapsed_seconds'], 'target_predictions': result['target_predictions']}), flush=True)


if __name__ == '__main__':
    main()
