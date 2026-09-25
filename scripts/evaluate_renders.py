#!/usr/bin/env python3
"""Measure static-region PSNR for a named render split. Not a visual quality gate.

Requires NumPy/Pillow. Missing images fail instead of silently shrinking the set.
Reference folders are produced by prepare_references.py. Render folders contain
<name>.png. Always compare the same poses, images, masks and renderer settings.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image


def evaluate(references, renders, split):
    views = [v for v in json.loads((references/'views.json').read_text()) if v['split'] == split]
    if not views:
        raise ValueError('Requested split has no views')
    rows = []
    for view in views:
        name = view['name']
        source = np.asarray(Image.open(references/'images'/f'{name}.jpg').convert('RGB'), dtype=float)/255
        rendered = np.asarray(Image.open(renders/f'{name}.png').convert('RGB'), dtype=float)/255
        mask = np.asarray(Image.open(references/'masks'/f'{name}.png').convert('L')) > 0
        if source.shape != rendered.shape or mask.shape != source.shape[:2]:
            raise ValueError(f'{name}: dimensions differ')
        if not mask.any():
            raise ValueError(f'{name}: no static pixels')
        mse = float(np.mean((source[mask]-rendered[mask])**2))
        rows.append({'name': name, 'static_pixels': int(mask.sum()), 'mse': mse,
                     'psnr_db': -10*math.log10(mse) if mse else None, 'perfect_match': mse == 0})
    finite = [r['psnr_db'] for r in rows if r['psnr_db'] is not None]
    return {'split': split, 'views': rows, 'mean_psnr_db': sum(finite)/len(finite) if len(finite)==len(rows) else None,
            'aggregation': 'equal weight per view; perfect matches reported explicitly',
            'visual_acceptance': 'not assessed by this metric'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('references', type=Path); p.add_argument('renders', type=Path)
    p.add_argument('--split', choices=['train', 'held-out'], required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = evaluate(a.references, a.renders, a.split)
    with a.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps({'views': len(result['views']), 'mean_psnr_db': result['mean_psnr_db']}))


if __name__ == '__main__':
    main()
