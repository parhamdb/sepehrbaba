#!/usr/bin/env python3
"""Inventory missing poses and unsupported component transitions; never merge maps."""
import argparse
import hashlib
import json
from pathlib import Path


def inventory(state, frames, minimum_seconds=1.0):
    names = [f['name'] for f in frames]
    if len(set(names)) != len(names) or any(b['timestamp'] <= a['timestamp'] for a, b in zip(frames, frames[1:])):
        raise ValueError('Unique frames in strictly increasing timestamp order required')
    membership = {name: set() for name in names}
    for component in state['components']:
        for name in component['names']:
            membership[name].add(component['id'])
    gaps = []; start = None
    for i in range(len(frames) + 1):
        missing = i < len(frames) and not membership[names[i]]
        if missing and start is None: start = i
        if not missing and start is not None:
            end = i - 1
            gaps.append(dict(id=f'gap-{len(gaps)+1:03}', first=frames[start], last=frames[end],
                missing_frames=i-start, sampled_span_seconds=frames[end]['timestamp']-frames[start]['timestamp'],
                before=frames[start-1] if start else None, after=frames[i] if i<len(frames) else None,
                midpoint=frames[(start+end)//2]))
            start = None
    transitions = []
    registered = [f for f in frames if membership[f['name']]]
    for a, b in zip(registered, registered[1:]):
        if not membership[a['name']] & membership[b['name']]:
            transitions.append(dict(before=a, after=b, components_before=sorted(membership[a['name']]),
                                    components_after=sorted(membership[b['name']])))
    return dict(schema=1, source_frames=len(frames), registered_union=len(registered),
        missing_frames=len(frames)-len(registered), component_count=len(state['components']),
        gaps=gaps, experiment_gap_ids=[g['id'] for g in gaps if g['sampled_span_seconds']>=minimum_seconds],
        unsupported_adjacent_transitions=transitions, minimum_gap_span_seconds=minimum_seconds,
        warning='Union of provisional camera models. Shared frames indicate overlap, not an accepted alignment. Missing-frame spans exclude the intervals to bounding observations.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('state','frames','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();result=inventory(json.loads(a.state.read_text()),json.loads(a.frames.read_text()))
    result['input_sha256']={k:hashlib.sha256(getattr(a,k).read_bytes()).hexdigest() for k in ('state','frames')}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('gaps','unsupported_adjacent_transitions')}))


if __name__=='__main__':main()
