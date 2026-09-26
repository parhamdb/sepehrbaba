#!/usr/bin/env python3
"""Screen learned gap bridges against withheld COLMAP cameras; never merge maps.

Fits each side in its own gauge. Independent component fits do not verify their
relative placement. All transforms exported here are hypotheses, not accepted joins.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from compare_camera_tracks import align_cameras, aligned_center, rotation_angle

LIMITS = dict(min_fit_frames=5, min_test_frames=5, max_position_percent_span=5.,
              max_orientation_deg=5., min_side_duration_seconds=.5)


def measure(source, reference, fit):
    if not source or fit is None:
        return None
    positions=[np.linalg.norm(aligned_center(s,fit)-t['center']) / fit['reference_span']*100
               for s,t in zip(source,reference)]
    angles=[rotation_angle(np.asarray(t['R'])@np.asarray(fit['rotation'])@np.asarray(s['R']).T)
            for s,t in zip(source,reference)]
    return dict(frames=len(source), position_percent_span=float(np.median(positions)),
                orientation_deg=float(np.median(angles)),
                p90_position_percent_span=float(np.percentile(positions,90)),
                p90_orientation_deg=float(np.percentile(angles,90)))


def good(score):
    return bool(score and score['frames']>=LIMITS['min_test_frames']
                and score['position_percent_span']<=LIMITS['max_position_percent_span']
                and score['orientation_deg']<=LIMITS['max_orientation_deg'])


def side_fit(frames, source, reference):
    frames=[f for f in frames if f['name'] in source]
    # Alternation is deterministic and retains the side's temporal extent in
    # each split. This is held-out gauge fitting, not held-out NN inference.
    train,test=frames[::2],frames[1::2]
    fit=align_cameras([source[f['name']] for f in train], [reference[f['name']] for f in train])
    score=measure([source[f['name']] for f in test], [reference[f['name']] for f in test],fit)
    duration=frames[-1]['timestamp']-frames[0]['timestamp'] if len(frames)>1 else 0.
    return dict(fit=fit, fit_names=[f['name'] for f in train],
                withheld_names=[f['name'] for f in test], withheld=score,
                duration_seconds=duration,
                passed=good(score) and duration>=LIMITS['min_side_duration_seconds'])


def compose_bridge(pre, post):
    """Map post-COLMAP to pre-COLMAP through the *hypothesized* NN gauge."""
    qa=np.asarray(pre['rotation']);qb=np.asarray(post['rotation'])
    scale=pre['scale']/post['scale'];rotation=qa@qb.T
    offset=np.asarray(pre['offset'])-scale*rotation@post['offset']
    return dict(scale=scale,rotation=rotation.tolist(),offset=offset.tolist())


def analyze_case(case):
    ref=case['methods']['colmap'];frames=case['frames']
    pre=[f for f in frames if f['timestamp']<case['loss_time'] and f['name'] in ref]
    post=[f for f in frames if f['timestamp']>=case['gap_end'] and f['name'] in ref]
    result=dict(id=case['id'],loss_time=case['loss_time'],gap_end=case['gap_end'],
                window_end=case['end'],accepted_connection=False,methods={})
    if not pre or not post:
        result.update(status='blocked',reason='Missing pre-gap or returning COLMAP anchor in this window')
        return result
    a=ref[pre[-1]['name']]['component'];b=ref[post[0]['name']]['component']
    # Nearest component on each side, not whichever larger component fits best.
    pre=[f for f in pre if ref[f['name']]['component']==a]
    post=[f for f in post if ref[f['name']]['component']==b]
    result.update(pre_component=a,post_component=b,same_component=a==b)
    for method in ('da3','vggt'):
        source=case['methods'][method]
        left=side_fit(pre,source,ref);right=side_fit(post,source,ref)
        row=dict(before=left,after=right,accepted_connection=False)
        if not left['fit'] or not right['fit']:
            row.update(status='blocked',reason='No positive-scale fit with five anchors on both sides')
        elif not left['passed'] or not right['passed']:
            row.update(status='rejected',reason='Withheld camera agreement or anchor duration failed')
        else:
            row.update(status='unverified',reason='Independent stationary cross-gap landmarks still required')
        if left['fit'] and right['fit']:
            row['candidate_post_to_pre']=compose_bridge(left['fit'],right['fit'])
            if a==b:
                pp=[f for f in post if f['name'] in source]
                row['pre_fit_predicts_post']=measure([source[f['name']] for f in pp],
                    [ref[f['name']] for f in pp],left['fit'])
                row['post_to_pre_fit_scale_ratio']=right['fit']['scale']/left['fit']['scale']
                if not good(row['pre_fit_predicts_post']):
                    row.update(status='rejected',reason='Pre-gap fit disagrees with same-component post-gap cameras')
        result['methods'][method]=row
    statuses=[r['status'] for r in result['methods'].values()]
    result['status']='unverified' if 'unverified' in statuses else ('rejected' if 'rejected' in statuses else 'blocked')
    result['reason']='See method-specific tests; no source camera or scene modified'
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    data=json.load(gzip.open(a.inputs,'rt'));rows=[analyze_case(c) for c in data['cases']]
    report=dict(schema=1,inputs_sha256=hashlib.sha256(a.inputs.read_bytes()).hexdigest(),
        limits=LIMITS,threshold_scope='Conservative experimental screening, not calibrated accuracy or evidentiary certification',
        split_scope='Withheld cameras are excluded from gauge fitting; the neural solver saw the complete clip',
        transform_scope='Rejected/unverified hypotheses only. Never apply automatically to source scenes.',
        accepted_connections=0,counts=dict(Counter(r['status'] for r in rows)),cases=rows)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report['counts']))


if __name__=='__main__':main()
