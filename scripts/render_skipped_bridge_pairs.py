#!/usr/bin/env python3
"""Show strongest raw cross-section matches, including rejected pairs and outliers."""
import argparse, json
from pathlib import Path
import cv2
import numpy as np
from probe_gap_recovery import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('selection','pairs','images','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();s=json.loads(a.selection.read_text());raw=json.loads(a.pairs.read_text())
    if raw['identity']['selection']!=digest(a.selection):raise ValueError('Selection mismatch')
    before=set(s['sides']['before']['names']);after=set(s['sides']['after']['names'])
    pairs=[r for r in raw['pairs'] if r['a'] in before and r['b'] in after]
    pairs=sorted(pairs,key=lambda r:(-len(r['matches']),r['a'],r['b']))[:6]
    a.output.mkdir(parents=True,exist_ok=True);entries=[]
    for row in pairs:
        canvas=np.zeros((1032,1080,3),np.uint8)
        for col,name in enumerate((row['a'],row['b'])):
            if digest(a.images/name)!=s['image_sha256'][name]:raise ValueError('Changed source image')
            im=cv2.imread(str(a.images/name));canvas[72:,col*540:(col+1)*540]=cv2.resize(im,(540,960))
        # Evenly sample at most 60 lines solely for legibility; cache retains every match.
        indices=np.linspace(0,len(row['matches'])-1,min(60,len(row['matches'])),dtype=int)
        for k in indices:
            i,j=row['matches'][k];x=np.array(raw['frames'][row['a']]['xy'][i])/2+[0,72];y=np.array(raw['frames'][row['b']]['xy'][j])/2+[540,72]
            u,v=tuple(np.round(x).astype(int)),tuple(np.round(y).astype(int));cv2.line(canvas,u,v,(0,255,255),1)
            cv2.circle(canvas,u,3,(0,255,255),1);cv2.circle(canvas,v,3,(0,255,255),1)
        for y,text in ((26,f"{row['a']} -> {row['b']}   raw matches: {len(row['matches'])}"),(54,f"Unverified candidates; {len(indices)} evenly sampled lines shown. NOT an accepted connection.")):
            cv2.putText(canvas,text,(8,y),cv2.FONT_HERSHEY_SIMPLEX,.51,(255,255,255),1)
        name=row['a'][:-4]+'--'+row['b'][:-4]+'.jpg';cv2.imwrite(str(a.output/name),canvas,[cv2.IMWRITE_JPEG_QUALITY,90])
        entries.append(dict(file=name,a=row['a'],b=row['b'],matches=len(row['matches']),shown_match_indices=indices.tolist()))
    (a.output/'index.json').write_text(json.dumps(dict(pairs_sha256=digest(a.pairs),selection_sha256=digest(a.selection),script_sha256=digest(Path(__file__)),pairs=entries),indent=2)+'\n')


if __name__=='__main__':main()
