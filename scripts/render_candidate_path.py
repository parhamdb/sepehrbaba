#!/usr/bin/env python3
"""Show original frames beside a candidate local camera path, without pose interpolation.

This diagnostic is not an independent geometric recovery test. The projection
is an arbitrary fixed view of local coordinates, not an aligned floor plan.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('frames','poses','images','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--loss-time',type=float,required=True)
    a=p.parse_args()
    import av
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    frames=json.loads(a.frames.read_text());data=json.loads(a.poses.read_text())
    poses={f['name']:f for f in data['frames']}
    if not set(poses).issubset({f['name'] for f in frames}):raise ValueError('Pose/frame mismatch')
    basis=np.array([[.70710678,0,-.70710678],[.40824829,-.81649658,.40824829]])
    centers=np.array([f['center'] for f in data['frames']]);xy=centers@basis.T
    mid=(xy.min(0)+xy.max(0))/2;scale=350/max(float(np.ptp(xy,axis=0).max()),1e-8)
    def pixel(c):return tuple(((np.asarray(c)@basis.T-mid)*scale+[666,435]).tolist())
    path=[pixel(c) for c in centers]
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
    if a.output.exists():raise FileExistsError(a.output)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    out=av.open(str(a.output),'w',options={'movflags':'+faststart'})
    stream=out.add_stream('libx264',rate=30);stream.width=900;stream.height=864
    stream.pix_fmt='yuv420p';stream.time_base=stream.codec_context.time_base=Fraction(1,1000000)
    stream.codec_context.thread_count=2;stream.options={'crf':'20','preset':'veryfast'}
    origin=frames[0]['timestamp']
    for i,f in enumerate(frames):
        canvas=Image.new('RGB',(900,864),'#101820');draw=ImageDraw.Draw(canvas)
        with Image.open(a.images/f['name']) as im:canvas.paste(im.convert('RGB').resize((432,768)),(0,65))
        draw.text((10,10),f'{data["method"]} | source {f["timestamp"]:.3f}s',font=font,fill='white')
        draw.text((445,70),'CANDIDATE — NOT VALIDATED',font=font,fill='#ffbb55')
        draw.text((445,105),'Local camera path; arbitrary scale',font=font,fill='white')
        draw.text((445,140),f'Loss onset: {a.loss_time:.3f}s',font=font,fill='white')
        if len(path)>1:draw.line(path,fill='#506070',width=2)
        pose=poses.get(f['name'])
        if pose:
            x,y=pixel(pose['center']);draw.ellipse((x-5,y-5,x+5,y+5),fill='#2be5ee')
            rotation=np.asarray(pose['camera_to_world_rotation'])
            # Orientation arrow uses the optical axis in the same local basis.
            delta=(rotation[:,2]@basis.T)*35
            draw.line((x,y,x+delta[0],y+delta[1]),fill='#2be5ee',width=3)
            label='Estimated keyframe'
        else:label='NO ESTIMATE — no interpolation'
        draw.text((445,710),label,font=font,fill='#2be5ee' if pose else '#ffbb55')
        draw.text((445,748),f'{data["estimated_frames"]}/{data["input_frames"]} frames estimated',font=font,fill='white')
        draw.text((445,788),'No landmark accuracy verdict yet',font=font,fill='#ffbb55')
        frame=av.VideoFrame.from_image(canvas);frame.pts=round((f['timestamp']-origin)*1000000);frame.time_base=Fraction(1,1000000)
        for packet in stream.encode(frame):out.mux(packet)
    for packet in stream.encode():out.mux(packet)
    out.close()
    print(f'Rendered {len(frames)} source frames',flush=True)


if __name__=='__main__':main()
