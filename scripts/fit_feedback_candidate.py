#!/usr/bin/env python3
"""Fit one reviewed feedback iteration; retain a receipt and compare frozen views.

Use a new output directory for every hypothesis. This tool never approves masks
or promotes a reconstruction. An agent reviews the trace, seeds SAM, and signs a
manifest-bound mask review before calling it. Repeat only with a new diagnosis.
"""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('dataset','proposals','review','reference-dataset','baseline-renders','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--trace',type=Path);p.add_argument('--hypothesis',required=True)
    p.add_argument('--brush',required=True);p.add_argument('--colmap',required=True)
    a=p.parse_args();review=json.loads(a.review.read_text())
    if review.get('status')!='reviewed-for-provisional-training' or review.get('manifest_sha256')!=sha(a.proposals/'manifest.json'):raise ValueError('A matching visual review is required before fitting')
    a.output.mkdir(parents=True,exist_ok=False);scripts=Path(__file__).resolve().parent
    receipt={'status':'running','hypothesis':a.hypothesis,'review_sha256':sha(a.review),'proposal_sha256':sha(a.proposals/'manifest.json'),'trace_sha256':sha(a.trace) if a.trace else None,'script_sha256':sha(__file__),'stages':{},'promotion':'not approved'}
    def save():(a.output/'cycle.json').write_text(json.dumps(receipt,indent=2)+'\n')
    def run(stage,script,*args):
        receipt['stages'][stage]={'status':'running','started':time.time()};save()
        try:
            with (a.output/(stage+'.log')).open('w') as log:subprocess.run([sys.executable,str(scripts/script),*map(str,args)],stdout=log,stderr=subprocess.STDOUT,check=True)
            receipt['stages'][stage].update(status='passed',finished=time.time());save()
        except Exception:
            receipt['stages'][stage].update(status='failed',finished=time.time());receipt['status']='failed; retain outputs and diagnose';save();raise
    run('prepare','prepare_reviewed_section.py','--dataset',a.dataset,'--proposals',a.proposals,'--review',a.review,'--output',a.output/'reviewed')
    run('geometry','clean_static_geometry.py','--source-dataset',a.output/'reviewed','--work',a.output/'static','--colmap',a.colmap,'--preserve-poses')
    run('train','video_to_splat.py','--stage','train','--dataset',a.output/'static/dataset','--output',a.output/'training','--brush',a.brush,'--steps','8000','--train-resolution','1920','--max-splats','500000','--eval-split-every','10')
    run('compare','compare_cleanup_renders.py',a.reference_dataset,a.baseline_renders,a.output/'training/splats/eval_8000',a.output/'comparison')
    receipt.update(status='ready for render review',candidate_sha256=sha(a.output/'training/splats/scene.ply'));save();print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
