#!/usr/bin/env python3
"""Export source images, masks and viewer poses from an undistorted COLMAP model.

Requires NumPy and Pillow. Convert dataset/sparse to COLMAP TXT first. Supply the
actual Brush eval output directory and training state; incomplete splits fail.
Only centered, square-pixel PINHOLE/SIMPLE_PINHOLE cameras are supported.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from clean_static_geometry import read_model, rotation


def camera_parameters(path):
    cameras = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        row = line.split()
        width, height = map(int, row[2:4])
        values = list(map(float, row[4:]))
        if row[1] == 'PINHOLE':
            fx, fy, cx, cy = values
        elif row[1] == 'SIMPLE_PINHOLE':
            fx, cx, cy = values
            fy = fx
        else:
            raise ValueError('Use an undistorted PINHOLE model, not a distorted sparse model')
        if (not all(math.isfinite(x) for x in [fx, fy, cx, cy]) or min(fx, fy) <= 0
                or abs(fx-fy) > 1e-4 or abs(cx-width/2) > .01 or abs(cy-height/2) > .01):
            raise ValueError('Viewer evaluation requires centered square-pixel intrinsics')
        cameras[int(row[0])] = (width, height, math.degrees(2*math.atan(height/(2*fy))))
    return cameras


def prepare(dataset, model, held_out, output, max_edge=946, train_stride=1, include=(), eval_every=None):
    if output.exists():
        raise ValueError('Use a new output directory')
    if max_edge < 1 or train_stride < 1:
        raise ValueError('Positive resolution and stride required')
    images, _ = read_model(model)
    cameras = camera_parameters(model/'cameras.txt')
    held = {p.stem for p in held_out.glob('*.png')}
    if not held:
        raise ValueError('No actual held-out renders found; refusing to infer the split')
    ordered = sorted(images.values(), key=lambda item: item['row'][9])
    # Brush 0.3.0 sorts by image name and holds out zero-based indices i % N == 0.
    # Directory presence alone cannot define the split: interrupted evaluation
    # may leave only a subset and silently leak missing holdouts into training.
    if not isinstance(eval_every, int) or isinstance(eval_every, bool) or eval_every < 2:
        raise ValueError('Supply the actual Brush training eval_split_every >=2')
    expected = {Path(item['row'][9]).stem for i, item in enumerate(ordered) if i % eval_every == 0}
    if held != expected:
        raise ValueError(f'Held-out renders do not match training split: missing={sorted(expected-held)}, extra={sorted(held-expected)}')
    names = {Path(item['row'][9]).stem for item in ordered}
    if len(names) != len(ordered) or not held <= names or not set(include) <= names:
        raise ValueError('Duplicate image stems or unknown held-out/include names')
    training = [item for item in ordered if Path(item['row'][9]).stem not in held]
    chosen = {Path(item['row'][9]).stem for item in training[::train_stride]} | set(include) | held
    output.mkdir(parents=True)
    for folder in ['images', 'masks']:
        (output/folder).mkdir()
    views = []
    transform = np.diag([-1, -1, 1])
    for item in ordered:
        row = item['row']; name = Path(row[9]).stem
        if name not in chosen:
            continue
        if Path(row[9]).name != row[9]:
            raise ValueError('Nested image paths are not supported by this evaluation format')
        width, height, fov = cameras[int(row[8])]
        ratio = min(1, max_edge/max(width, height))
        size = (round(width*ratio), round(height*ratio))
        with Image.open(dataset/'images'/row[9]) as image, Image.open(dataset/'masks'/f'{name}.png') as mask:
            if image.size != (width, height) or mask.size != image.size:
                raise ValueError(f'{name}: model, image and mask dimensions disagree')
            image.convert('RGB').resize(size, Image.Resampling.LANCZOS).save(output/'images'/f'{name}.jpg', quality=95)
            mask.convert('L').resize(size, Image.Resampling.NEAREST).save(output/'masks'/f'{name}.png')
        R = rotation(row); position = -R.T @ np.array(row[5:8], float)
        views.append({'name': name, 'split': 'held-out' if name in held else 'train',
                      'position': (transform@position).tolist(),
                      'target': (transform@(position+R.T@np.array([0, 0, 1]))).tolist(),
                      'up': (transform@R.T@np.array([0, -1, 0])).tolist(),
                      'fov': fov, 'width': size[0], 'height': size[1]})
    (output/'views.json').write_text(json.dumps(views, indent=2)+'\n')
    manifest = {'dataset': str(dataset.resolve()), 'model': str(model.resolve()),
                'held_out_source': str(held_out.resolve()), 'held_out_names': sorted(held),
                'eval_split_every': eval_every, 'split_convention': 'Brush 0.3.0 sorted names, zero-based i % N == 0',
                'max_edge': max_edge, 'train_stride': train_stride, 'include': list(include),
                'reference_jpeg_quality': 95, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'model_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in model.glob('*.txt')}}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return views


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--model-text', type=Path, required=True)
    parser.add_argument('--held-out-renders', type=Path, required=True)
    parser.add_argument('--training-state', type=Path, required=True, help='state.json written by video_to_splat.py')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-edge', type=int, default=946)
    parser.add_argument('--train-stride', type=int, default=1)
    parser.add_argument('--include', nargs='*', default=[], help='Extra image stems; preserves their actual split')
    args = parser.parse_args()
    state = json.loads(args.training_state.read_text())
    views = prepare(args.dataset, args.model_text, args.held_out_renders, args.output,
                    args.max_edge, args.train_stride, args.include, state['training']['eval_split_every'])
    (args.output/'training-state.json').write_bytes(args.training_state.read_bytes())
    print(json.dumps({'train': sum(v['split']=='train' for v in views),
                      'held_out': sum(v['split']=='held-out' for v in views)}))


if __name__ == '__main__':
    main()
