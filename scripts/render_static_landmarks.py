#!/usr/bin/env python3
"""Overlay candidate triangulation correspondences on authentic anchor images."""
import argparse,itertools,json
from pathlib import Path
import cv2,numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('report','images','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);report=json.loads(a.report.read_text());index=[]
    for m in report['maps']:
        candidates={}
        for landmark in m['landmarks']:
            for first,second in itertools.combinations(landmark['observations'],2):
                key=(first['name'],second['name']);candidates.setdefault(key,[]).append((landmark,first,second))
        if not candidates:continue
        pair,rows=max(candidates.items(),key=lambda item:(len(item[1]),item[0]));canvas=np.zeros((1008,1080,3),np.uint8)
        for side,name in enumerate(pair):
            im=cv2.imread(str(a.images/name))
            if im is None:raise ValueError('Missing source image')
            canvas[48:,side*540:(side+1)*540]=cv2.resize(im,(540,960))
            cv2.putText(canvas,name,(side*540+8,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
        for j,(landmark,first,second) in enumerate(rows):
            x=tuple((np.asarray(first['xy'])*.5+[0,48]).astype(int));y=tuple((np.asarray(second['xy'])*.5+[540,48]).astype(int))
            color=(60,255,60) if landmark['origin']=='previously-unmapped-observations' else (0,190,255)
            cv2.line(canvas,x,y,color,1,cv2.LINE_AA)
            for pos in (x,y):
                cv2.circle(canvas,pos,5,color,2);cv2.putText(canvas,str(j),pos,cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
        cv2.putText(canvas,f"{m['gap']} {m['direction']}: {len(rows)} candidate points; not certified",(8,40),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
        name=m['gap']+'-'+m['direction']+'.jpg';cv2.imwrite(str(a.output/name),canvas,[cv2.IMWRITE_JPEG_QUALITY,91])
        index.append(dict(gap=m['gap'],direction=m['direction'],pair=pair,landmark_ids=[r[0]['id'] for r in rows],image=name))
    (a.output/'index.json').write_text(json.dumps(dict(selection='Largest number of shared candidate landmarks per map; ties by filenames',green='Only previously unmapped observations',orange='Includes existing map observations',pairs=index),indent=2)+'\n')


if __name__=='__main__':main()
