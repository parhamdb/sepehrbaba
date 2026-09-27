#!/usr/bin/env python3
"""Freeze original frames from equal time windows around a camera gap.

Includes intervening gap frames for possible indirect visual overlap. This
selects by source time, not camera-registration status or whole-image sharpness.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frames', type=Path, required=True)
    p.add_argument('--images', type=Path, required=True)
    p.add_argument('--gap-start', type=float, required=True)
    p.add_argument('--gap-end', type=float, required=True)
    p.add_argument('--seconds-each-side', type=float, default=10)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error('Output exists; preserve previous selection')
    if not all(math.isfinite(t) for t in (a.gap_start, a.gap_end, a.seconds_each_side)) or not (0 <= a.gap_start < a.gap_end and a.seconds_each_side > 0):
        p.error('Need finite ordered nonnegative gap times and positive window')
    start, end = max(0, a.gap_start-a.seconds_each_side), a.gap_end+a.seconds_each_side
    rows = []
    for frame in json.loads(a.frames.read_text()):
        t = frame['timestamp']
        if not math.isfinite(t):
            p.error('Nonfinite source timestamp')
        if start <= t <= end:
            name = frame['name']
            if not re.fullmatch(r'frame_\d+\.jpg', name):
                p.error('Expected original frame basename')
            side = 'before' if t < a.gap_start else 'after' if t > a.gap_end else 'gap'
            rows.append(dict(name=name, timestamp=t, side=side))
    if not rows or not all(b['timestamp'] > a['timestamp'] for a, b in zip(rows, rows[1:])) or len({r['name'] for r in rows}) != len(rows):
        p.error('Need unique chronologically ordered original frames')
    counts = {s: sum(r['side'] == s for r in rows) for s in ('before', 'gap', 'after')}
    if not counts['before'] or not counts['after']:
        p.error('Need source observations on both sides')
    result = dict(interval_seconds=[start, end], windows=dict(before=[start, a.gap_start], gap=[a.gap_start, a.gap_end], after=[a.gap_end, end]), frames=rows, source_frames_sha256=digest(a.frames), image_sha256={r['name']: digest(a.images/r['name']) for r in rows})
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(frames=len(rows), by_side=counts)))


if __name__ == '__main__':
    main()
