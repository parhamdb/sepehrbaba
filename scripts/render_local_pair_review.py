#!/usr/bin/env python3
"""Render every primary-calibration supported pair without hiding held-out errors."""
import argparse, json
from pathlib import Path
import cv2
import numpy as np
from probe_gap_recovery import digest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('pairs', 'evaluation', 'images', 'output'):
        p.add_argument('--' + key, required=True, type=Path)
    a = p.parse_args()
    data = json.loads(a.pairs.read_text())
    report = json.loads(a.evaluation.read_text())
    if report['identity']['pairs'] != digest(a.pairs):
        raise ValueError('Pair cache identity mismatch')
    a.output.mkdir(parents=True, exist_ok=True)
    lookup = {(r['a'], r['b']): r for r in data['pairs']}
    entries = []
    for row in report['pairs']:
        check = row['variants']['lookback']
        if not (check['homography_passed'] or check['relative_pose_screen_passed']):
            continue
        pair = lookup[row['a'], row['b']]
        matches = np.asarray(pair['matches'], int).reshape(-1, 2)
        withheld = set(check['withheld_indices'])
        tiles = []
        for name in (row['a'], row['b']):
            im = cv2.imread(str(a.images / name))
            if im is None or im.shape[:2] != (1920, 1080):
                raise ValueError('Expected native portrait source')
            tiles.append(cv2.resize(im, (540, 960)))
        canvas = np.zeros((1032, 1080, 3), np.uint8)
        canvas[72:] = np.hstack(tiles)
        for i, (left, right) in enumerate(matches):
            x = np.asarray(data['frames'][row['a']]['xy'][left]) / 2 + [0, 72]
            y = np.asarray(data['frames'][row['b']]['xy'][right]) / 2 + [540, 72]
            x, y = tuple(np.round(x).astype(int)), tuple(np.round(y).astype(int))
            color = (0, 255, 255) if i in withheld else (255, 160, 40)
            # Show all match locations; connect only held-out observations for readability.
            for point in (x, y):
                cv2.circle(canvas, point, 4 if i in withheld else 2, color, 1)
            if i in withheld:
                cv2.line(canvas, x, y, color, 1)
        labels = [f"{row['a']} -> {row['b']}  H:{check['homography_passed']} E:{check['relative_pose_screen_passed']}",
                  'Yellow: ALL withheld matches; blue: fitting matches. No certified camera.']
        for y, label in zip((26, 54), labels):
            cv2.putText(canvas, label, (8, y), cv2.FONT_HERSHEY_SIMPLEX, .53, (255,255,255), 1)
        name = row['a'][:-4] + '--' + row['b'][:-4] + '.jpg'
        cv2.imwrite(str(a.output / name), canvas, [cv2.IMWRITE_JPEG_QUALITY, 90])
        entries.append(dict(file=name, a=row['a'], b=row['b'], matches=len(matches), withheld=len(withheld)))
    (a.output / 'index.json').write_text(json.dumps(dict(
        pairs_sha256=digest(a.pairs), evaluation_sha256=digest(a.evaluation),
        script_sha256=digest(Path(__file__)), pairs=entries), indent=2) + '\n')


if __name__ == '__main__':
    main()
