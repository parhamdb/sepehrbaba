#!/usr/bin/env python3
"""Compare candidate renders on frozen baseline masks, never candidate masks."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def psnr(squared, count):
    return -10 * math.log10(max(squared / count, 1e-12))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset', type=Path)
    p.add_argument('baseline', type=Path)
    p.add_argument('candidate', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--eval-every', type=int, default=10)
    a = p.parse_args()
    if a.eval_every < 2:
        p.error('eval-every must be >=2')
    sources = sorted((a.dataset/'images').glob('*.jpg'))[::a.eval_every]
    names = {f.stem+'.png' for f in sources}
    if not names or any({f.name for f in d.glob('*.png')} != names for d in (a.baseline, a.candidate)):
        raise ValueError('Render inventories must match the exact frozen held-out split')
    a.output.mkdir(parents=True, exist_ok=False)
    totals = [0., 0.]
    count = 0
    rows = []
    chosen = {round(i*(len(sources)-1)/5) for i in range(6)}
    sheet = Image.new('RGB', (810, 510*len(chosen)))
    draw = ImageDraw.Draw(sheet)
    sheet_row = 0
    for idx, source in enumerate(sources):
        name = source.stem+'.png'
        mask_path = a.dataset/'masks'/name
        with Image.open(source) as im:
            gt = np.asarray(im.convert('RGB'), dtype=np.float32)
        with Image.open(mask_path) as im:
            mask = np.asarray(im)
        if mask.shape != gt.shape[:2] or not np.isin(mask, [0, 255]).all():
            raise ValueError('Expected exact-size binary reference mask')
        keep = mask > 0
        n = int(keep.sum())*3
        if not n:
            raise ValueError('Empty reference evaluation region')
        count += n
        scores = []
        for i, directory in enumerate((a.baseline, a.candidate)):
            with Image.open(directory/name) as im:
                rendered = np.asarray(im.convert('RGB'), dtype=np.float32)
            if rendered.shape != gt.shape:
                raise ValueError('Render dimensions differ from source')
            error = float((((gt-rendered)/255.)**2)[keep].sum(dtype=np.float64))
            totals[i] += error
            scores.append(psnr(error, n))
        rows.append({'image': source.name, 'baseline_psnr_db': scores[0],
                     'candidate_psnr_db': scores[1], 'delta_db': scores[1]-scores[0],
                     'reference_mask_sha256': hashlib.sha256(mask_path.read_bytes()).hexdigest()})
        if idx in chosen:
            for col, (label, path) in enumerate((('source', source), ('baseline', a.baseline/name), ('candidate', a.candidate/name))):
                with Image.open(path) as im:
                    im = im.convert('RGB'); im.thumbnail((270, 480))
                    sheet.paste(im, (270*col, 510*sheet_row+24))
                draw.text((270*col+3, 510*sheet_row+4), f'{source.stem} {label}', fill='white')
            sheet_row += 1
    baseline, candidate = (psnr(total, count) for total in totals)
    report = {'metric_scope': 'Identical baseline unmasked pixels; not proof of novel-view geometry or restored detail',
              'held_out_views': len(rows), 'baseline_psnr_db': baseline,
              'candidate_psnr_db': candidate, 'delta_db': candidate-baseline,
              'improved_views': sum(r['delta_db'] > 0 for r in rows),
              'worst_view_delta_db': min(r['delta_db'] for r in rows), 'views': rows}
    (a.output/'comparison.json').write_text(json.dumps(report, indent=2)+'\n')
    sheet.save(a.output/'comparison.jpg')
    print(json.dumps({k:v for k,v in report.items() if k!='views'}, indent=2))


if __name__ == '__main__':
    main()
