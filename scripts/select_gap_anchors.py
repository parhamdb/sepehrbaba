#!/usr/bin/env python3
"""Freeze denser, sharper gap anchors without using matching or pose-fit outcomes."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np
from inventory_camera_gaps import inventory
from probe_gap_recovery import choose_reference,digest,write


def select_bins(names,times,boundary,direction,quality):
    selected=[]
    for lo,hi in ((0,1),(1,2),(2,4),(4,6),(6,8),(8,10)):
        group=[n for n in names if lo<direction*(times[n]-boundary)<=hi]
        if group:selected.append(max(group,key=lambda n:(quality(n),n)))
    return selected


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('state','frames','images','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--gap-ids',nargs='+',default=['gap-098','gap-103','gap-144'])
    a=p.parse_args();cv2.setNumThreads(2)
    state=json.loads(a.state.read_text());frames=json.loads(a.frames.read_text());times={f['name']:f['timestamp'] for f in frames}
    inv=inventory(state,frames);cases={};quality_cache={};image_hashes={}
    def quality(name):
        if name not in quality_cache:
            path=a.images/name;im=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
            if im is None or im.shape!=(1920,1080):raise ValueError('Missing native source image')
            # Selection proxy, not a guarantee of sharp static architecture.
            im=cv2.resize(im,(270,480));quality_cache[name]=float(cv2.Laplacian(im,cv2.CV_64F).var())
            image_hashes[name]=digest(path)
        return quality_cache[name]
    wanted=set(a.gap_ids)
    if not wanted<=set(inv['experiment_gap_ids']):raise ValueError('Unknown long gap')
    for gap in inv['gaps']:
        if gap['id'] not in wanted:continue
        queries=[]
        for kind in ('first','midpoint','last','after'):
            frame=gap[kind]
            if frame and frame['name'] not in [q['name'] for q in queries]:queries.append(dict(frame,kind='registered-return' if kind=='after' else 'missing-'+kind))
        case=dict(queries=queries,directions={})
        for direction,label,boundary in ((-1,'lookback',gap['first']['timestamp']),(1,'lookahead',gap['last']['timestamp'])):
            component=choose_reference(state['components'],times,boundary,direction,'nearest')
            if component is None:continue
            anchors=select_bins(component['names'],times,boundary,direction,quality)
            excluded=set(anchors)|{q['name'] for q in queries}
            controls=[n for n in component['names'] if n not in excluded and 0<direction*(times[n]-boundary)<=10]
            control=max(controls,key=quality) if controls else None
            case['directions'][label]=dict(component=component['id'],anchors=anchors,control=control)
        cases[gap['id']]=case
    names=set()
    for c in cases.values():
        names.update(q['name'] for q in c['queries'])
        for d in c['directions'].values():
            names.update(d['anchors'])
            if d['control']:names.add(d['control'])
    for name in names:image_hashes[name]=digest(a.images/name)
    report=dict(schema=1,cases=cases,samples=[f for f in frames if f['name'] in names],
        identity=dict(state=digest(a.state),frames=digest(a.frames),script=digest(Path(__file__))),
        quality_scores=quality_cache,image_sha256=image_hashes,
        selection='One highest whole-image Laplacian-variance view per 0-1,1-2,2-4,4-6,6-8,8-10 second bin; nearest eligible reference map; fixed first/midpoint/last/return queries')
    if a.output.exists():raise FileExistsError(a.output)
    a.output.parent.mkdir(parents=True,exist_ok=True);write(a.output,report)
    print(json.dumps(dict(cases=len(cases),samples=len(names),quality_candidates=len(quality_cache))))


if __name__=='__main__':main()
