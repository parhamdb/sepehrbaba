#!/usr/bin/env python3
"""Check mask inventory and make an evenly spaced source/overlay review sheet.

Red marks excluded pixels. This does not certify segmentation accuracy.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    report = json.loads((a.dataset/'mask-report.json').read_text())
    rows = report['images']
    names = sorted(x['image'] for x in rows)
    if not names or len(set(names)) != len(names):
        raise ValueError('Missing or duplicate mask inventory')
    if set(names) != {p.name for p in (a.dataset/'images').glob('*.jpg')}:
        raise ValueError('Mask report and dataset image inventory differ')
    expected = {Path(n).stem+'.png' for n in names}
    if expected != {p.name for p in (a.dataset/'masks').glob('*.png')}:
        raise ValueError('Missing or extra mask files')
    for name in names:
        with Image.open(a.dataset/'images'/name) as source, Image.open(a.dataset/'masks'/(Path(name).stem+'.png')) as mask:
            if source.size != mask.size:
                raise ValueError(f'Mask size mismatch: {name}')
    chosen = {names[round(i*(len(names)-1)/5)] for i in range(6)}
    chosen.update(x['image'] for x in (min(rows, key=lambda x:x['excluded_fraction']),
                                      max(rows, key=lambda x:x['excluded_fraction'])))
    chosen = sorted(chosen)
    canvas = Image.new('RGB', (540*4, 510*((len(chosen)+3)//4)))
    draw = ImageDraw.Draw(canvas)
    for i, name in enumerate(chosen):
        with Image.open(a.dataset/'images'/name) as source, Image.open(a.dataset/'masks'/(Path(name).stem+'.png')) as mask:
            source = source.convert('RGB'); source.thumbnail((270, 480))
            excluded = np.asarray(mask.resize(source.size, Image.Resampling.NEAREST)) == 0
            pixels = np.asarray(source).copy()
            pixels[excluded] = .5*pixels[excluded]+[127, 0, 0]
            x, y = (i%4)*540, (i//4)*510
            canvas.paste(source, (x, y+24)); canvas.paste(Image.fromarray(pixels), (x+270, y+24))
            draw.text((x+4, y+4), name+' | excluded pixels in red', fill='white')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(a.output)
    print(json.dumps({'validated_masks': len(names), 'review_images': chosen}))


if __name__ == '__main__':
    main()
