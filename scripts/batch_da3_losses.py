#!/usr/bin/env python3
"""Run each frozen DA3 loss clip once; preserve failures and stop on low disk."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time


def save(path,state):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2)+'\n');temp.replace(path)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('inventory','clips','checkout','weights','salad','adapter','output','reuse'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--python',required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    lock=(a.output/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    frozen={k:hashlib.sha256(getattr(a,k).read_bytes()).hexdigest() for k in ('inventory','adapter')}
    path=a.output/'state.json';state=json.loads(path.read_text()) if path.exists() else dict(config=frozen,trials={})
    if state['config']!=frozen:raise ValueError('Frozen inputs changed')
    for case in json.loads(a.inventory.read_text())['cases']:
        name=case['id']
        if name in state['trials']:continue
        if shutil.disk_usage(a.output).free<24*1024**3:
            state['blocker']='Fewer than 24 GiB free; retained completed work';save(path,state);return
        state['active_case']=name;save(path,state);work=a.output/name
        if name=='loss-008':
            d=json.loads((a.reuse/'poses.json').read_text())
            if [f['name'] for f in d['frames']]!=[f['name'] for f in case['frames']]:raise ValueError('Prior frame inventory mismatch')
            work.mkdir();shutil.copy2(a.reuse/'poses.json',work/'poses.json');code=0
        else:
            cmd=[a.python,str(a.adapter)]
            for k in ('checkout','weights','salad'):cmd+=['--'+k,str(getattr(a,k))]
            cmd+=['--images',str(a.clips/name/'images'),'--frames',str(a.clips/name/'frames.json'),'--output',str(work)]
            with (a.output/(name+'.log')).open('w') as log:code=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
        row=dict(execution='completed' if code==0 else 'execution-failed',recovery='not_assessed',finished=time.time())
        if code==0:
            d=json.loads((work/'poses.json').read_text());row.update(input_frames=d['input_frames'],estimated_frames=d['estimated_frames'])
        state['trials'][name]=row;state.pop('active_case',None);save(path,state);print(name,row['execution'],flush=True)
    state['finished']=time.time();save(path,state)


if __name__=='__main__':main()
