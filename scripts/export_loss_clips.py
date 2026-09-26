#!/usr/bin/env python3
"""Export every frozen loss interval at native size and variable frame timing."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('inventory','video','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();inventory=json.loads(a.inventory.read_text())
    if digest(a.video)!=inventory['source_sha256']:raise ValueError('Source checksum mismatch')
    a.output.mkdir(parents=True,exist_ok=False);rows=[]
    for case in inventory['cases']:
        path=a.output/(case['id']+'.mp4')
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n',
            '-ss',str(case['start']),'-i',str(a.video),'-t',str(case['end']-case['start']),
            '-map','0:v:0','-map','0:a:0?','-c:v','libx264','-preset','veryfast','-crf','18',
            '-threads','2','-fps_mode','vfr','-enc_time_base','1:1000000',
            '-video_track_timescale','1000000','-c:a','aac','-movflags','+faststart',str(path)],check=True)
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
            '-show_frames','-show_entries','frame=best_effort_timestamp_time,width,height','-of','json',str(path)]))['frames']
        expected=case['frames']
        if len(probe)!=len(expected):raise ValueError(f'{case["id"]}: frame count mismatch')
        drift=max(abs((float(f['best_effort_timestamp_time'])-float(probe[0]['best_effort_timestamp_time']))-
                      (s['timestamp']-expected[0]['timestamp'])) for f,s in zip(probe,expected))
        if drift>.002:raise ValueError(f'{case["id"]}: VFR timestamp mismatch {drift}')
        if any((f['width'],f['height'])!=(1080,1920) for f in probe):raise ValueError('Native size changed')
        rows.append(dict(id=case['id'],frames=len(probe),max_relative_time_error=drift,sha256=digest(path)))
        (a.output/'exports.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(case['id'],len(probe),'verified',flush=True)


if __name__=='__main__':main()
