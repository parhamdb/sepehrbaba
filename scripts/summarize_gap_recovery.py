#!/usr/bin/env python3
"""Summarize completed candidate screens without promoting controls to recoveries."""
import argparse,collections,json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('report','inventory','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();report=json.loads(a.report.read_text());inv=json.loads(a.inventory.read_text())
    if report['status']!='complete-candidates-not-certified':raise ValueError('Require completed report')
    trials=[t for g in report['gaps'] for t in g['trials'] if 'method' in t]
    recovery=[t for t in trials if t['evidence_role']=='recovery-candidate'];controls=[t for t in trials if t['evidence_role']=='control']
    passing=[t for t in recovery if t['passed']]
    lines=['# Gap recovery experiment results','',f"Completed {len(report['gaps'])} gaps; {len(trials)} PnP screens and {sum(len(g['pair_counts']) for g in report['gaps'])} image-pair/matcher trials.",
        f"**{len(passing)} new-pose screens passed; {sum(t['passed'] for t in controls)} / {len(controls)} in-map control screens passed.** No new poses or component joins were accepted.",
        '','The low control pass rate limits this experiment: it diagnoses this sparse-anchor configuration and does not establish that relocalization or a matcher generally cannot recover these gaps.',
        '','A screen is a method/window/direction/query combination, not a distinct recovered frame. Related screens share features and are not independent evidence. Unsupported anchor directions are recorded separately in report.json.',
        '','[Full report](report.json) · [All missing-frame runs and component transitions](inventory.json) · [Method list and limitations](../../docs/gap-recovery.md)',
        '','| Matcher | Search | Direction | New-pose screens | New-pose passes | Control passes / screens |','|---|---:|---|---:|---:|---:|']
    for method in sorted({t['method'] for t in trials}):
        for window in (10,30):
            for direction in ('lookback','lookahead'):
                chosen=[t for t in trials if (t['method'],t['window_seconds'],t['direction'])==(method,window,direction)]
                r=[t for t in chosen if t['evidence_role']=='recovery-candidate'];c=[t for t in chosen if t['evidence_role']=='control']
                lines.append(f"| {method} | {window} s | {direction} | {len(r)} | {sum(t['passed'] for t in r)} | {sum(t['passed'] for t in c)} / {len(c)} |")
    lines+=['','## Per-gap next attempt','', 'These are evidence-based next experiments, **not running jobs**. A maximum match count is not a correctness score. Reference selection currently favors the component with the most views in the search interval; that can omit closer small components. Low-feature failures therefore justify checking alternate reference maps before expensive full-video inference.', '',
        '| Gap | Missing timestamps (s) | Frames | Maximum midpoint matches | Proposed next test |','|---|---:|---:|---:|---|']
    gaps={g['id']:g for g in inv['gaps']}
    for g in report['gaps']:
        ref=gaps[g['id']];mid=[t for t in g['trials'] if t.get('query_kind')=='missing-midpoint'];maximum=max((t.get('matches',0) for t in mid),default=0)
        if maximum>=18:next_test='Static mask + stronger descriptors; inspect PnP inconsistency'
        elif ref['after'] is None:next_test='Earlier-map retrieval; tail has no later anchor'
        else:next_test='Closer alternative maps + denser clear anchors; then learned descriptors'
        lines.append(f"| {g['id']} | {ref['first']['timestamp']:.2f}–{ref['last']['timestamp']:.2f} | {ref['missing_frames']} | {maximum} | {next_test} |")
    lines+=['','## Source-image inspection','', 'Six source triptychs were inspected. At 98.02 s the image is heavily occluded and overexposed; at 283.71 s the view is obstructed near a doorway; at 512.96 s there is strong motion blur. The larger-match cases at 377.41, 413.47 and 442.27 s still contain foreground people, repeated floor patterns and substantial viewpoint/blur changes. These observations suggest follow-up tests; they do not establish which matches caused each PnP failure.','']
    for gid in ('gap-007','gap-034','gap-135','gap-084','gap-098','gap-103'):
        lines.append(f'- [{gid}: authentic reference / midpoint / return](review/{gid}.jpg)')
    lines+=['','The six synthetic tests passed, including shuffled held-out correspondence rejection and resume rejection when a reference model changes. Passing these implementation checks does not mean camera recovery succeeded. All source models remain separate.','']
    a.output.write_text('\n'.join(lines))


if __name__=='__main__':main()
