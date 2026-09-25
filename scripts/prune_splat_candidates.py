#!/usr/bin/env python3
"""Export a reversible post-training pruning candidate; this does not identify proven ghosts.

Supports standard binary little-endian 3DGS PLY with float vertex properties.
Retained records are copied without changing any parameters. Requires NumPy;
the isolated-haze mode additionally requires SciPy. Never overwrites outputs.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def read_ply(path):
    with path.open('rb') as f:
        lines, fields, count = [], [], None
        while True:
            raw = f.readline()
            if not raw or sum(map(len, lines)) + len(raw) > 65536:
                raise ValueError('Invalid or oversized PLY header')
            lines.append(raw)
            row = raw.decode('ascii').split()
            if row[:1] == ['element']:
                if row[1] != 'vertex' or count is not None:
                    raise ValueError('Only one vertex element is supported')
                count = int(row[2])
            elif row[:1] == ['property']:
                if count is None or len(row) != 3 or row[1] != 'float':
                    raise ValueError('Expected float vertex properties')
                fields.append((row[2], '<f4'))
            elif row == ['end_header']:
                break
        if lines[0].strip() != b'ply' or b'format binary_little_endian 1.0' not in [l.strip() for l in lines]:
            raise ValueError('Expected binary little-endian PLY')
        if count is None or count <= 0:
            raise ValueError('Empty PLY')
        data = np.fromfile(f, dtype=fields, count=count)
        if len(data) != count or f.read(1):
            raise ValueError('PLY payload size mismatch')
    needed = {'x', 'y', 'z', 'opacity', 'scale_0', 'scale_1', 'scale_2'}
    if not needed.issubset(data.dtype.names):
        raise ValueError('Missing Gaussian properties')
    if not all(np.isfinite(data[k]).all() for k in data.dtype.names):
        raise ValueError('Non-finite Gaussian properties')
    return lines, data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--mode', choices=['needle', 'isolated-haze'], default='needle')
    p.add_argument('--min-length', type=float, required=True, help='Minimum longest axis in model units')
    p.add_argument('--min-axis-ratio', type=float, default=30, help='Longest / second-longest axis; preserves flat splats')
    p.add_argument('--max-opacity', type=float, default=.1)
    p.add_argument('--isolation-percentile', type=float, default=95)
    p.add_argument('--max-removal-fraction', type=float, default=.02)
    a = p.parse_args()
    values = [a.min_length, a.min_axis_ratio, a.max_opacity, a.isolation_percentile, a.max_removal_fraction]
    if not np.isfinite(values).all() or a.min_length <= 0 or a.min_axis_ratio <= 1 or not 0 < a.max_opacity < 1 or not 0 < a.isolation_percentile < 100 or not 0 < a.max_removal_fraction < 1:
        p.error('Invalid threshold')
    report_path = a.output.with_suffix('.json')
    removed_path = a.output.with_name(a.output.stem + '-removed.ply')
    if len({a.input.resolve(), a.output.resolve(), report_path.resolve(), removed_path.resolve()}) != 4:
        p.error('Input and output paths must be distinct')
    if any(x.exists() for x in [a.output, report_path, removed_path]):
        p.error('Use fresh output paths; existing results are retained')
    header, data = read_ply(a.input)
    scales = np.sort(np.exp(np.stack([data[f'scale_{i}'].astype(float) for i in range(3)], axis=1)), axis=1)
    if not np.isfinite(scales).all() or (scales <= 0).any():
        raise ValueError('Invalid decoded scales')
    opacity = np.exp(-np.logaddexp(0, -data['opacity'].astype(float)))
    if a.mode == 'needle':
        remove = (scales[:, 2] > a.min_length) & (scales[:, 2] / scales[:, 1] > a.min_axis_ratio)
        isolation_threshold = None
    else:
        from scipy.spatial import cKDTree
        xyz = np.stack([data[k] for k in ['x', 'y', 'z']], axis=1)
        if len(data) < 10:
            raise ValueError('Insufficient neighbours')
        distances = cKDTree(xyz).query(xyz, k=9, workers=4)[0][:, 1:].mean(axis=1)
        isolation_threshold = float(np.percentile(distances, a.isolation_percentile))
        remove = (scales[:, 2] > a.min_length) & (opacity < a.max_opacity) & (distances > isolation_threshold)
    removed = int(remove.sum())
    if removed == 0 or removed / len(data) > a.max_removal_fraction:
        raise ValueError(f'Removal count {removed}/{len(data)} outside the allowed nonzero budget')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    for path, records in [(a.output, data[~remove]), (removed_path, data[remove])]:
        with path.open('xb') as f:
            for line in header:
                f.write(f'element vertex {len(records)}\n'.encode() if line.startswith(b'element vertex ') else line)
            f.write(records.tobytes())
        _, reread = read_ply(path)
        if reread.tobytes() != records.tobytes():
            raise RuntimeError('Output changed retained Gaussian records')
    report = {'input_sha256': hashlib.sha256(a.input.read_bytes()).hexdigest(),
              'output_sha256': hashlib.sha256(a.output.read_bytes()).hexdigest(),
              'mode': a.mode, 'original_count': len(data), 'removed_count': removed,
              'retained_count': len(data)-removed, 'removed_indices': np.flatnonzero(remove).tolist(),
              'min_length': a.min_length, 'min_axis_ratio': a.min_axis_ratio,
              'max_opacity': a.max_opacity, 'isolation_threshold': isolation_threshold,
              'retained_records_byte_identical': True, 'accepted_visual_quality': False}
    with report_path.open('x') as f:
        json.dump(report, f, indent=2); f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'removed_indices'}, indent=2))


if __name__ == '__main__':
    main()
