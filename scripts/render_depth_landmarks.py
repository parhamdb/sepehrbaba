#!/usr/bin/env python3
"""Render source-linked camera hypotheses over the actual two short windows."""
import argparse, hashlib, json, subprocess
from pathlib import Path
import cv2
import numpy as np


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def label(im,text,x,y,color=(235,235,235),scale=.6):
    cv2.putText(im,text,(x,y),cv2.FONT_HERSHEY_SIMPLEX,scale,color,1,cv2.LINE_AA)


def panel(canvas,image,record,crop,left,predcolor):
    x0,y0,x1,y1=crop;scale=min(620/(x1-x0),820/(y1-y0))
    resized=cv2.resize(image[y0:y1,x0:x1],None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    h,w=resized.shape[:2];ox=left+(640-w)//2;oy=155+(820-h)//2
    canvas[oy:oy+h,ox:ox+w]=resized
    def pos(xy):return (int(round(ox+(xy[0]-x0)*scale)),int(round(oy+(xy[1]-y0)*scale)))
    def inside(xy):return x0<=xy[0]<x1 and y0<=xy[1]<y1
    hidden=0
    for j,(obs,pred,good,positive) in enumerate(zip(record['observed_xy'],record['projected_xy'],record['usable_track'],record['positive_depth'])):
        color=(0,230,255) if record['seed_view'] else ((70,235,90) if good else (160,160,160))
        if inside(obs):
            p=pos(obs);cv2.circle(canvas,p,6,color,2,cv2.LINE_AA);label(canvas,f'Q{j+1}',p[0]+8,p[1]-7,color,.55)
        if positive and inside(pred):
            q=pos(pred);cv2.drawMarker(canvas,q,predcolor,cv2.MARKER_TILTED_CROSS,17,2,cv2.LINE_AA)
            if inside(obs):cv2.line(canvas,pos(obs),q,predcolor,1,cv2.LINE_AA)
        else:hidden+=1
    label(canvas,f"{record['name']}  {record['timestamp']:.3f}s",left+15,130)
    label(canvas,f"{hidden} projections outside crop / behind camera",left+15,1000,scale=.5)
    errs='  '.join(f"Q{j+1}:{e:.1f}" for j,e in enumerate(record['error_px']))
    label(canvas,'Error in original pixels: '+errs,left+15,1025,scale=.42)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('images','experiment-dir','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(exist_ok=False,parents=True)
    cfg=json.loads((a.experiment_dir/'experiment.json').read_text());data=json.loads((a.experiment_dir/'evaluation.json').read_text())
    sources={r['name']:r for side in cfg['sides'].values() for r in side['frames']}
    images={}
    for name,row in sources.items():
        f=a.images/name
        if sha(f)!=row['image_sha256']:raise ValueError('Image hash changed')
        images[name]=cv2.imread(str(f))
    manifest=dict(evaluation_sha256=sha(a.experiment_dir/'evaluation.json'),script_sha256=sha(Path(__file__)),video_fps=4,source_samples_per_side=21,source_window_seconds={},videos={},accepted_connection=False)
    for name,fit in data['fits'].items():
        output=a.output/(name+'.mp4')
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','bgr24','-s','1280x1120','-r','4','-i','-','-an','-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        try:
            for i,(source,target) in enumerate(zip(fit['source_local'],fit['temporal'])):
                canvas=np.full((1120,1280,3),18,np.uint8)
                label(canvas,'UNVERIFIED CAMERA HYPOTHESIS - NO SCENE JOIN',15,30,(80,200,255),.85)
                label(canvas,'Two separate 1-second windows shown slowly side by side. The gap is not reconstructed.',15,61,scale=.66)
                label(canvas,'SOURCE: cached local DA3 motion',15,96,(235,220,70),.67)
                label(canvas,'TARGET: fitted PnP + cached local motion',655,96,(225,100,245),.64)
                panel(canvas,images[source['name']],source,cfg['sides'][fit['source_side']]['crop_xyxy'],0,(235,220,70))
                panel(canvas,images[target['name']],target,cfg['sides'][fit['target_side']]['crop_xyxy'],640,(225,100,245))
                label(canvas,'Circles: yellow = human seed; green = tracked; grey = unreliable track.',15,1063,scale=.68)
                label(canvas,'Crosses: camera projections. Lines show disagreement. Six local points; no independent static validation.',15,1096,scale=.6)
                proc.stdin.write(canvas.tobytes())
                if i in [0,10,20]:cv2.imwrite(str(a.output/f'{name}-{i:02}.jpg'),canvas)
        finally:
            proc.stdin.close()
            code=proc.wait()
        if code:raise RuntimeError('Video encoding failed')
        manifest['videos'][output.name]=dict(sha256=sha(output),frames=len(fit['temporal']),duration_seconds=len(fit['temporal'])/4)
        for side in [fit['source_side'],fit['target_side']]:
            rows=cfg['sides'][side]['frames'];manifest['source_window_seconds'][side]=[rows[0]['timestamp'],rows[-1]['timestamp']]
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest['videos']))

if __name__=='__main__':main()
