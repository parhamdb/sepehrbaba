#!/usr/bin/env python3
"""Make contact sheets and fitted-correspondence overlays from authentic gap frames."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np
from probe_gap_recovery import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('selection','masks','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    selection=json.loads(a.selection.read_text());rows=[]
    for sample in selection['samples']:
        name=sample['name'];preview=a.masks/(name+'.preview.jpg')
        im=cv2.imread(str(preview));meta=json.loads((a.masks/(name+'.json')).read_text())
        if im is None:raise ValueError('Missing preview')
        tile=np.zeros((512,270,3),np.uint8);tile[32:]=im
        label=f"{name[6:12]}  {sample['timestamp']:.2f}s  static {meta['static_fraction']:.0%}"
        cv2.putText(tile,label,(4,21),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
        rows.append(tile)
    for start in range(0,len(rows),12):
        tiles=rows[start:start+12]
        tiles+= [np.zeros_like(rows[0]) for _ in range(12-len(tiles))]
        canvas=np.vstack([np.hstack(tiles[i:i+3]) for i in range(0,12,3)])
        cv2.imwrite(str(a.output/f'contact-{start//12+1:02}.jpg'),canvas,[cv2.IMWRITE_JPEG_QUALITY,90])
    (a.output/'manifest.json').write_text(json.dumps(dict(selection_sha256=digest(a.selection),samples=len(rows),
        legend='Cyan: proposed static surface after person subtraction. Red: dilated detected person. Black/no tint: excluded region.'),indent=2)+'\n')


if __name__=='__main__':main()
