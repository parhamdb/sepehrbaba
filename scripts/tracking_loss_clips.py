#!/usr/bin/env python3
"""Freeze camera-loss clips using native timestamps and every supplied pose inventory.

An absent pose is a benchmark candidate, not proof that recovery is impossible.
Inputs and source frames are read-only. Runtime symlinks must not be committed.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def losses(frames, registered, duration, margin=10., minimum=1.):
    if not frames or duration <= frames[-1]['timestamp'] or margin <= 0 or minimum <= 0:
        raise ValueError('Invalid frame inventory or interval settings')
    names = {f['name'] for f in frames}
    if len(names) != len(frames) or not registered <= names:
        raise ValueError('Duplicate or unknown frame names')
    if any(b['timestamp'] <= a['timestamp'] for a,b in zip(frames,frames[1:])):
        raise ValueError('Non-increasing timestamps')
    output = []
    start = None
    for i in range(len(frames)+1):
        missing = i < len(frames) and frames[i]['name'] not in registered
        if missing and start is None:
            start = i
        if not missing and start is not None:
            t = frames[start]['timestamp']
            end = frames[i]['timestamp'] if i < len(frames) else duration
            if end-t >= minimum:
                lo, hi = max(0.,t-margin), min(duration,t+margin)
                selected = [f for f in frames if lo <= f['timestamp'] < hi]
                output.append(dict(id=f'loss-{len(output)+1:03d}', loss_time=t,
                    gap_end=end, gap_seconds=end-t, start=lo, end=hi,
                    recovery_visible_in_clip=i < len(frames) and end < hi,
                    pre_loss_registered_frames=sum(f['name'] in registered for f in selected if f['timestamp'] < t),
                    classification='no pose in supplied raw and reviewed inventories',
                    frames=selected))
            start = None
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--extra-registered',type=Path,required=True)
    p.add_argument('--duration',type=float,default=737.301333)
    p.add_argument('--margin',type=float,default=10)
    p.add_argument('--minimum-gap',type=float,default=1)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--images',type=Path)
    p.add_argument('--prepare',type=Path,help='New private runtime directory of native image symlinks')
    a=p.parse_args()
    s=json.load(gzip.open(a.snapshot,'rt')); extra=json.loads(a.extra_registered.read_text())
    frames=[dict(name=f['name'],timestamp=f['timestamp']) for f in s['frames']]
    known={f['name'] for f in s['frames'] if f['pose']} | set(extra['registered_names'])
    cases=losses(frames,known,a.duration,a.margin,a.minimum_gap)
    result=dict(schema=1,source_sha256=s['source_sha256'],snapshot_sha256=sha(a.snapshot),
        raw_inventory_sha256=sha(a.extra_registered),duration=a.duration,margin=a.margin,
        minimum_gap=a.minimum_gap,known_frames=len(known),source_frames=len(frames),cases=cases,
        warning='Missing pose means no estimate in supplied inventories, not independently certified tracking failure.')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    if a.prepare:
        if not a.images:raise ValueError('--prepare requires --images')
        a.prepare.mkdir(parents=True,exist_ok=False)
        for case in cases:
            dest=a.prepare/case['id'];(dest/'images').mkdir(parents=True)
            (dest/'frames.json').write_text(json.dumps(case['frames'],indent=2)+'\n')
            for frame in case['frames']:
                source=(a.images/frame['name']).resolve(strict=True)
                (dest/'images'/frame['name']).symlink_to(source)
    print(json.dumps(dict(cases=len(cases),known_frames=len(known),source_frames=len(frames))))


if __name__=='__main__':main()
