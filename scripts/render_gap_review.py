#!/usr/bin/env python3
"""Render authentic source samples for a gap experiment (no generated scene data)."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('report','frames','images','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--gap-ids',nargs='+',default=['gap-007','gap-034','gap-135'])
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    report=json.loads(a.report.read_text());times={f['name']:f['timestamp'] for f in json.loads(a.frames.read_text())}
    for gap in report['gaps']:
        if gap['id'] not in a.gap_ids:continue
        pairs=[p for p in gap['pair_counts'] if p['query']==gap['midpoint']['name'] and p['direction']=='lookback']
        anchor=max((p['anchor'] for p in pairs),key=times.get,default=None)
        tiles=[]
        for label,name in [('earlier reference',anchor),('missing midpoint',gap['midpoint']['name']),('first tracked return',(gap['after'] or {}).get('name'))]:
            tile=np.full((628,324,3),25,np.uint8)
            if name:
                im=cv2.imread(str(a.images/name))
                if im is None:raise ValueError('Missing source image')
                tile[52:]=cv2.resize(im,(324,576))
                cv2.putText(tile,f'{name}  {times[name]:.2f}s',(5,40),cv2.FONT_HERSHEY_SIMPLEX,.4,(240,240,240),1)
            cv2.putText(tile,label,(5,18),cv2.FONT_HERSHEY_SIMPLEX,.5,(240,240,240),1)
            tiles.append(tile)
        cv2.imwrite(str(a.output/(gap['id']+'.jpg')),np.hstack(tiles),[cv2.IMWRITE_JPEG_QUALITY,88])


if __name__=='__main__':main()
