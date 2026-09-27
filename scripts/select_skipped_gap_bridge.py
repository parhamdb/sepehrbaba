#!/usr/bin/env python3
"""Freeze sharp registered views on both sides of gap 098; exclude missing frames."""
import argparse, json, math
from pathlib import Path
import cv2
from probe_gap_recovery import digest, write


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('state','frames','images','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();cv2.setNumThreads(2)
    if a.output.exists():raise FileExistsError(a.output)
    state=json.loads(a.state.read_text());frames=json.loads(a.frames.read_text());times={f['name']:f['timestamp'] for f in frames}
    sides={};scores={};selected=set()
    for side,cid in (('before','cbc3a19f69fce48a'),('after','0bc7a95fc61b9c4c')):
        c=next(c for c in state['components'] if c['id']==cid);bins={}
        for name in c['names']:
            t=times[name]
            if (side=='before' and not 382.290311<=t<412.290311) or (side=='after' and not 414.512889<t<=444.512889):continue
            im=cv2.imread(str(a.images/name),cv2.IMREAD_GRAYSCALE)
            if im is None or im.shape!=(1920,1080):raise ValueError('Expected native image')
            scores[name]=float(cv2.Laplacian(cv2.resize(im,(270,480)),cv2.CV_64F).var())
            bins.setdefault(math.floor(t),[]).append(name)
        names=sorted(n for values in bins.values() for n in sorted(values,key=lambda n:(-scores[n],n))[:2])
        sides[side]=dict(component=cid,names=names);selected.update(names)
    samples=[f for f in frames if f['name'] in selected]
    out=dict(schema=1,sides=sides,samples=samples,quality_scores=scores,
        identity=dict(state=digest(a.state),frames=digest(a.frames),script=digest(Path(__file__))),
        image_sha256={f['name']:digest(a.images/f['name']) for f in samples},
        selection='Top two whole-image Laplacian-variance registered images per one-second bin, separate existing before/after components, at most 30 seconds each side; no gap frames.')
    a.output.parent.mkdir(parents=True,exist_ok=True);write(a.output,out)
    print(json.dumps(dict(selected=len(samples),sides={k:len(v['names']) for k,v in sides.items()},quality_candidates=len(scores))))


if __name__=='__main__':main()
