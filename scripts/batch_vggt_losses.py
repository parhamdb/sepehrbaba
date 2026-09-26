#!/usr/bin/env python3
"""Run the frozen VGGT loss inventory once, preserving failures and completed trials."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time


def save(p,d):
    q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['inventory','clips','adapter','checkpoint','output']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--python',required=True)
    p.add_argument('--reuse',type=Path,help='Previously completed loss-008 trial from this campaign')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    lock=(a.output/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    config=dict(inventory_sha256=hashlib.sha256(a.inventory.read_bytes()).hexdigest(),
        adapter_sha256=hashlib.sha256(a.adapter.read_bytes()).hexdigest())
    state_path=a.output/'state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else dict(config=config,trials={})
    if state['config']!=config:raise ValueError('Frozen inputs changed; use new output directory')
    cases=json.loads(a.inventory.read_text())['cases']
    for case in cases:
        name=case['id']
        if name in state['trials']:continue
        work=a.output/name;clip=a.clips/name
        if name=='loss-008' and a.reuse:
            prior=json.loads((a.reuse/'poses.json').read_text())
            if prior['input_frames']!=len(case['frames']):raise ValueError('Prior inventory mismatch')
            if any(f['name'] not in {x['name'] for x in case['frames']} for f in prior['frames']):raise ValueError('Prior source mismatch')
            work.mkdir();(work/'poses.json').write_text(json.dumps(prior,indent=2)+'\n')
            result='reused-completed'
        else:
            state['active_case']=name;save(state_path,state)
            command=[a.python,str(a.adapter),'--images',str(clip/'images'),'--frames',str(clip/'frames.json'),
                '--checkpoint',str(a.checkpoint),'--output',str(work)]
            with (a.output/(name+'.log')).open('w') as log:
                code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT).returncode
            result='completed' if code==0 and (work/'poses.json').is_file() else 'execution-failed'
        row=dict(execution=result,recovery='not_assessed',finished=time.time())
        if (work/'poses.json').is_file():
            d=json.loads((work/'poses.json').read_text());row['estimated_frames']=d['estimated_frames'];row['input_frames']=d['input_frames']
        state['trials'][name]=row;state.pop('active_case',None);save(state_path,state)
        print(name,result,flush=True)
    state['finished']=time.time();save(state_path,state)


if __name__=='__main__':main()
