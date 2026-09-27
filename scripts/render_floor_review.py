#!/usr/bin/env python3
"""Render a clearly labeled sampled overview and contact sheets for floor review."""
import argparse,json,subprocess
from pathlib import Path
import cv2
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=json.loads((a.output/'report.json').read_text())
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','bgr24','-video_size','540x1000','-framerate','6','-i','-','-an','-c:v','libx264','-preset','fast','-crf','25','-pix_fmt','yuv420p','-movflags','+faststart',str(a.output/'samples.mp4')]
    process=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    for row in report['samples']:
        im=cv2.imread(str(a.output/row['image']));assert im is not None
        frame=np.zeros((1000,540,3),np.uint8);frame[:960]=im
        cv2.putText(frame,'SAMPLED FRAMES - NOT CONTINUOUS PLAYBACK',(8,986),0,.49,(255,255,255),1)
        for _ in range(6):process.stdin.write(frame.tobytes())
    process.stdin.close()
    if process.wait():raise RuntimeError('Video encoding failed')
    for start in range(0,len(report['samples']),20):
        canvas=np.zeros((4*424,5*216,3),np.uint8)
        for n,row in enumerate(report['samples'][start:start+20]):
            im=cv2.resize(cv2.imread(str(a.output/row['image'])),(216,384));y=(n//5)*424;x=(n%5)*216
            canvas[y:y+384,x:x+216]=im
            cv2.putText(canvas,f"{start+n}: {row['timestamp']:.1f}s",(x+4,y+407),0,.5,(255,255,255),1)
        cv2.imwrite(str(a.output/f'contact-{start//20}.jpg'),canvas)


if __name__=='__main__':main()
