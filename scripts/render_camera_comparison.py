#!/usr/bin/env python3
"""Render synchronized three-camera diagnostics from frozen existing estimates.

Every selected source frame is rendered at its original relative timestamp.
Paths are gauge-aligned using pre-loss cameras only, never joined across COLMAP
components. Image-motion constraints are diagnostics, not a static-scene verdict.
"""
import argparse
from fractions import Fraction
import gzip
import json
from pathlib import Path
import subprocess
import numpy as np
from compare_camera_tracks import aligned_center, METHODS

COLORS={'colmap':'#90d6ff','vggt':'#ffca64','da3':'#87e3a4'}
TITLES={'colmap':'Original COLMAP','vggt':'VGGT-SLAM','da3':'DA3-Streaming'}
BASIS=np.array([[.70710678,0,-.70710678],[.40824829,-.81649658,.40824829]])


def layout_paths(case,report):
    paths={};all_points=[]
    for m in METHODS:
        fit=report['alignments'][m];coords={}
        for f in case['frames']:
            p=case['methods'][m].get(f['name'])
            if p is None or fit is None:continue
            if m=='colmap' and p['component']!=report['reference_component']:continue
            coords[f['name']]=aligned_center(p,fit)@BASIS.T
        paths[m]=coords;all_points.extend(coords.values())
    if not all_points:return paths,np.zeros(2),1.
    xy=np.asarray(all_points);mid=(xy.min(0)+xy.max(0))/2
    scale=min(396/max(float(np.ptp(xy[:,0])),1e-8),142/max(float(np.ptp(xy[:,1])),1e-8))
    return paths,mid,scale


def render(case,report,images,output):
    import av
    from PIL import Image,ImageDraw,ImageFont
    paths,mid,scale=layout_paths(case,report)
    fontroot='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    fonts={n:ImageFont.truetype(fontroot,n) for n in [13,15,17,21,24]}
    pairs={r['second']:r for r in report['pairs'] if r['group']=='shared'}
    for row in report['pairs']:
        if row['group']=='gap':pairs.setdefault(row['second'],row)
    if output.exists():raise FileExistsError(output)
    container=av.open(str(output),'w',options={'movflags':'+faststart'})
    stream=container.add_stream('libx264',rate=30);stream.width=1440;stream.height=1120;stream.pix_fmt='yuv420p'
    stream.time_base=stream.codec_context.time_base=Fraction(1,1000000);stream.codec_context.thread_count=2
    stream.options={'crf':'22','preset':'veryfast'}
    origin=case['frames'][0]['timestamp']
    def path_pixel(x,col):return tuple(((x-mid)*scale+[col*480+240,1012]).tolist())
    for f in case['frames']:
        canvas=Image.new('RGB',(1440,1120),'#101820');draw=ImageDraw.Draw(canvas)
        t=f['timestamp'];row=pairs.get(f['name']);phase='BEFORE LOSS' if t<case['loss_time'] else ('BASELINE GAP' if t<case['gap_end'] else 'AFTER BASELINE RETURN')
        draw.text((16,7),f'{case["id"]} | source {int(t)//60:02d}:{t%60:06.3f} | {phase}',font=fonts[24],fill='white')
        draw.text((16,39),'Same source frames. Dots: image observations. Lines: epipolar discrepancy. Moving people can cause errors.',font=fonts[15],fill='#d0d8df')
        with Image.open(images/f['name']) as im:
            if im.size!=(1080,1920):raise ValueError('Native source dimensions changed')
            source=im.convert('RGB').resize((432,768),Image.Resampling.LANCZOS)
        for col,m in enumerate(METHODS):
            x0=col*480+24;canvas.paste(source,(x0,105));color=COLORS[m];p=case['methods'][m].get(f['name'])
            draw.text((x0,64),TITLES[m],font=fonts[21],fill=color)
            count=len(case['methods'][m]);label=f'{count}/{len(case["frames"])} estimated frames'
            draw.text((x0,88),label,font=fonts[13],fill='white')
            if p is None:
                label='NO COLMAP POSE' if m=='colmap' else ('FRAME NOT SELECTED' if count else 'CAMERA VALIDATION FAILED')
                draw.rectangle((x0,109,x0+432,140),fill='#231f1a');draw.text((x0+8,115),label,font=fonts[17],fill='#ffca64')
            else:
                if row and m in row['metrics']:
                    metric=row['metrics'][m];value=metric.get('median_px');n=row['corners']
                    label=f'Flow pairs {n} | median {value:.1f}px' if value is not None else f'Flow pairs {n} | constraint unavailable'
                    if n<20:label+=' | SPARSE'
                    draw.rectangle((x0,109,x0+432,140),fill='#18232a');draw.text((x0+5,117),label,font=fonts[13],fill='white')
                    for v in row['vectors'].get(m,[]):
                        point=np.asarray(v['observed'])*.4+[x0,105];foot=np.asarray(v['constraint'])*.4+[x0,105]
                        # Keep annotations inside this source-image panel.
                        if x0<=foot[0]<=x0+432 and 145<=foot[1]<=873 and point[1]>=145:
                            draw.line((*point,*foot),fill='#ff7070' if v['error_px']>8 else '#ffd060',width=2)
                        if point[1]>=145:
                            x,y=point;draw.ellipse((x-3,y-3,x+3,y+3),outline='#00ffff',width=2)
                else:
                    draw.rectangle((x0,109,x0+432,138),fill='#18232a');draw.text((x0+5,115),'POSE PRESENT | no shared pair at this frame',font=fonts[13],fill='white')
            draw.text((x0,883),'Pre-loss-aligned path; common scale and view',font=fonts[13],fill='white')
            # The grey reference is always the same pre-loss COLMAP component.
            for method,linecolor in [('colmap','#526572'),(m,color)]:
                previous=None
                for item in case['frames']:
                    coord=paths[method].get(item['name'])
                    if coord is None:
                        if method=='colmap':previous=None
                        continue
                    pt=path_pixel(coord,col)
                    if previous is not None:draw.line((*previous,*pt),fill=linecolor,width=2)
                    previous=pt
            fit=report['alignments'][m];current=paths[m].get(f['name'])
            if current is not None:
                x,y=path_pixel(current,col);draw.ellipse((x-4,y-4,x+4,y+4),fill=color)
                direction=(np.asarray(fit['rotation'])@np.asarray(p['R']).T[:,2])@BASIS.T
                draw.line((x,y,x+direction[0]*19,y+direction[1]*19),fill=color,width=2)
            if m=='colmap' and p and p['component']!=report['reference_component']:
                label='Different COLMAP component: not joined'
            elif fit is None:label='No reliable pre-loss coordinate alignment'
            elif m=='colmap':label='Reference component; grey in every panel'
            else:label=f'Pre-loss fit: {fit["fit_median_percent_span"]:.1f}% of reference span'
            draw.text((x0,1090),label,font=fonts[13],fill=color)
        frame=av.VideoFrame.from_image(canvas);frame.pts=round((t-origin)*1000000);frame.time_base=Fraction(1,1000000)
        for packet in stream.encode(frame):container.mux(packet)
    for packet in stream.encode():container.mux(packet)
    container.close()
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(output)]))['frames']
    if len(probe)!=len(case['frames']):raise ValueError('Rendered source-frame count mismatch')
    drift=max(abs(float(r['best_effort_timestamp_time'])-(f['timestamp']-origin)) for r,f in zip(probe,case['frames']))
    if drift>1e-5:raise ValueError('Rendered source timing mismatch')
    return dict(id=case['id'],frames=len(probe),max_timing_error_seconds=drift,width=1440,height=1120)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('inputs','analysis','images','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    data=json.load(gzip.open(a.inputs,'rt'));receipts=[]
    for case in data['cases']:
        report=json.loads((a.analysis/(case['id']+'.json')).read_text())
        receipts.append(render(case,report,a.images,a.output/(case['id']+'.mp4')))
        (a.output/'render-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
        print(case['id'],'rendered and frame/timing verified',flush=True)


if __name__=='__main__':main()
