#!/usr/bin/env python3
"""Read-only evidence for joining two disconnected COLMAP TXT models.

Counts existing verified cross-model pairs; does not establish a valid alignment.
The database and model image names must refer to the same source frame inventory.
"""
import argparse
import json
from pathlib import Path
import sqlite3


def names(path):
    result = set()
    with (path/'images.txt').open() as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            result.add(line.split()[9])
            next(f)
    if not result:
        raise ValueError('Empty model')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-a', type=Path, required=True)
    p.add_argument('--model-b', type=Path, required=True)
    p.add_argument('--database', type=Path, required=True)
    p.add_argument('--frames', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    first, second = names(a.model_a), names(a.model_b)
    times = {x['name']: x['timestamp'] for x in json.loads(a.frames.read_text())}
    with sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro', uri=True) as db:
        images = dict(db.execute('SELECT image_id,name FROM images'))
        if not first | second <= set(images.values()) & times.keys():
            raise ValueError('Models, database and frame inventory disagree')
        left = {i for i,n in images.items() if n in first-second}
        right = {i for i,n in images.items() if n in second-first}
        pairs = []
        for pair, count, config in db.execute('SELECT pair_id,rows,config FROM two_view_geometries WHERE rows >= 15'):
            i,j = divmod(pair, 2147483647)
            if config in (0,1,7) or not ((i in left and j in right) or (j in left and i in right)):
                continue
            pairs.append({'images':[images[i],images[j]], 'seconds':[times[images[i]],times[images[j]]],
                          'inliers':count,'configuration':config})
    report = {'model_a_cameras':len(first), 'model_b_cameras':len(second),
        'shared_registered_cameras':len(first & second),
        'model_a_seconds':[min(times[n] for n in first),max(times[n] for n in first)],
        'model_b_seconds':[min(times[n] for n in second),max(times[n] for n in second)],
        'verified_cross_pairs':len(pairs), 'cross_pairs_at_least_100_inliers':sum(x['inliers']>=100 for x in pairs),
        'strongest_pairs':sorted(pairs,key=lambda x:x['inliers'],reverse=True)[:20],
        'interpretation':'Diagnostic counts only. Neither pair counts nor temporal proximity prove a valid merge.'}
    with a.output.open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
