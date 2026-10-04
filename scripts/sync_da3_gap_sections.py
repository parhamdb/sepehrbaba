#!/usr/bin/env python3
"""Copy completed experimental sections from a worker into an append-only library.

Uses an existing SSH identity/control connection; credentials never enter files.
Three consecutive transfer failures stop polling. No training or Git writes.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['host','remote','control-path']:p.add_argument('--'+name,required=True)
    for name in ['local','library','frames']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--interval',type=int,default=60)
    p.add_argument('--once',action='store_true')
    a=p.parse_args();a.local.mkdir(parents=True,exist_ok=True)
    lock=(a.local/'.sync.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-S',a.control_path]
    failures=0
    while True:
        try:
            raw=subprocess.check_output(ssh+[a.host,'cat '+shlex.quote(a.remote+'/progress.json')],timeout=60)
            progress=json.loads(raw)
            (a.local/'worker-progress.json').write_bytes(raw)
            catalog=json.loads((a.library/'catalog.json').read_text())
            imported={s['id']:s for s in catalog['sections']}
            for row in progress['sections']:
                if row['status']!='complete':continue
                identity=row['id']
                if not identity.startswith('da3-gap-') or not identity.replace('-','').isalnum():raise ValueError('Invalid worker section ID')
                if identity in imported:
                    if imported[identity]['sha256']!=row['ply_sha256']:raise ValueError('Published section identity changed')
                    continue
                dest=a.local/identity;dest.mkdir(exist_ok=True)
                subprocess.run(['rsync','-a','--protect-args','-e',shlex.join(ssh),
                    '--include=preparation.json','--include=evaluation.json','--include=comparison.jpg',
                    '--include=splats/','--include=splats/scene.ply','--include=splats/eval_*/',
                    '--include=splats/eval_*/*.png','--exclude=*',
                    a.host+':'+a.remote+'/'+identity+'/',str(dest)+'/'],check=True,timeout=900)
                ply=dest/'splats/scene.ply'
                with ply.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
                if sha!=row['ply_sha256']:raise ValueError('Transferred PLY hash mismatch')
                subprocess.run([sys.executable,str(Path(__file__).with_name('import_da3_gap_section.py')),
                    '--library',str(a.library),'--section',str(dest),'--frames',str(a.frames)],check=True)
            failures=0
            status={'updated':time.time(),'worker_status':progress['status'],
                'completed':sum(r['status']=='complete' for r in progress['sections']),
                'failed':sum(r['status']=='failed' for r in progress['sections']),
                'pending':sum(r['status']=='pending' for r in progress['sections'])}
            (a.local/'sync-status.json').write_text(json.dumps(status,indent=2)+'\n')
            print(json.dumps(status),flush=True)
            if a.once or progress['status'] in {'finished','stopped-repeated-failure'}:return
        except Exception as error:
            failures+=1
            (a.local/'sync-error.txt').write_text(str(error)+'\n')
            print('Synchronization failed:',type(error).__name__,failures,flush=True)
            if failures>=3 or a.once:raise
        time.sleep(a.interval)


if __name__=='__main__':main()
