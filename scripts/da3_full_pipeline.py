#!/usr/bin/env python3
"""Run full DA3 then cross-reference retained reference cameras automatically."""
import argparse,gzip,json,subprocess,sys,time
from pathlib import Path
from run_da3_full import save


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('checkout','weights','salad','images','frames','video','comparison','snapshot','native','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--resume',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    state=dict(status='inference',started=time.time(),complete=False);statepath=a.output/'pipeline.json';save(statepath,state)
    reference=json.load(gzip.open(a.comparison,'rt'));scripts=Path(__file__).resolve().parent
    cmd=[sys.executable,str(scripts/'run_da3_full.py')]
    for key in ('checkout','weights','salad','images','frames','video'):cmd+=['--'+key,str(getattr(a,key))]
    cmd+=['--output',str(a.output/'inference'),'--expected-video-sha256',reference['source_sha256']]
    if a.resume:cmd+=['--resume']
    try:
        subprocess.run(cmd,check=True)
        state.update(status='cross-reference',updated=time.time());save(statepath,state)
        cmd=[sys.executable,str(scripts/'compare_da3_full.py'),'--poses',str(a.output/'inference/poses.json')]
        for key in ('comparison','snapshot','native'):cmd+=['--'+key,str(getattr(a,key))]
        cmd+=['--output',str(a.output/'comparison.json')]
        subprocess.run(cmd,check=True)
        state.update(status='complete-candidate-not-certified',complete=True,updated=time.time());save(statepath,state)
    except Exception as error:
        state.update(status='failed',failure_type=type(error).__name__,updated=time.time());save(statepath,state);raise


if __name__=='__main__':main()
