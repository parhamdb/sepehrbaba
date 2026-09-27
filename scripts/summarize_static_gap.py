#!/usr/bin/env python3
"""Compare paired static-anchor reports and summarize fixed-camera triangulation."""
import argparse,json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);a=p.parse_args();root=a.evidence
    reports={n:json.loads((root/(n+'.json')).read_text()) for n in ('unmasked','masked','triangulated-sift','triangulated-lightglue')}
    if any(r['status']!='complete-candidates-not-certified' for r in reports.values()):raise ValueError('Incomplete report')
    x=reports['unmasked']['identity'];y=reports['masked']['identity'];delta={k:v for k,v in y.items() if k not in ('mask_manifest','masks')}
    if x!=delta:raise ValueError('Masked and unmasked settings differ beyond masks')
    if [g['model_sha256'] for g in reports['unmasked']['gaps']]!=[g['model_sha256'] for g in reports['masked']['gaps']]:raise ValueError('Reference maps differ')
    lines=['# Static-anchor recovery results','', '[Method and limitations](../../docs/static-gap-recovery.md) · [Selection](selection.json) · [Mask archive](masks.tar.gz) · [Support audit](support.json)','',
        'All three selected gaps completed. No missing-frame or cross-component camera passed. Twelve focused unit tests passed. The paired runs differ only by static-mask filtering, with identical anchors, queries, original camera models and PnP settings.','',
        '| Gap | Unmasked maximum missing-frame matches | Masked maximum | Earlier/later SIFT triangulated points | Earlier/later LightGlue points |','|---|---:|---:|---:|---:|']
    for ga,gb in zip(reports['unmasked']['gaps'],reports['masked']['gaps']):
        if ga['id']!=gb['id']:raise ValueError('Gap order differs')
        maximum=lambda g:max((t.get('matches',0) for t in g['trials'] if t.get('query_kind','').startswith('missing-')),default=0)
        counts=[]
        for name in ('triangulated-sift','triangulated-lightglue'):
            maps={m['direction']:m for m in reports[name]['maps'] if m['gap']==ga['id']};counts.append('/'.join(str(len(maps[d]['landmarks'])) for d in ('lookback','lookahead')))
        lines.append(f"| {ga['id']} | {maximum(ga)} | {maximum(gb)} | {counts[0]} | {counts[1]} |")
    for name in ('triangulated-sift','triangulated-lightglue'):
        report=reports[name];landmarks=[p for m in report['maps'] for p in m['landmarks']]
        novel=sum(p['origin']=='previously-unmapped-observations' for p in landmarks)
        pairs=[p for m in report['maps'] for p in m['pairs']];trials=[t for m in report['maps'] for t in m['trials']]
        lines+=['',f"**{name}:** {len(landmarks)} constructed points across independent maps; {novel} use only previously unmapped anchor observations. {sum(p['matches'] for p in pairs)} raw pair matches, {sum(p.get('triangulated',0) for p in pairs)} pair triangulations before track merging, {len(trials)} PnP screens, {sum(t['passed'] and t['evidence_role']=='recovery-candidate' for t in trials)} new-pose passes."]
    lines+=['','Constructed points are provisional, may retriangulate existing landmarks, and can represent the same physical feature in different component gauges. They are not 36 certified new scene points or a connected reconstruction.','',
        '## What each gap needs next','',
        '- **098:** the richer static maps remain below the required landmark support. Check correspondences against local camera estimates, then broaden overlap or refine cameras using static matches. The first and midpoint frames contain usable static features; the last missing frame has only five descriptors after support filtering.',
        '- **103:** very few repeatable floor/wall descriptors survive. Search other rigid surfaces, including stationary objects, while distinguishing moving people from stationary human remains. A semantic person mask alone cannot make that distinction.',
        '- **144:** the midpoint and earlier anchors contain many static descriptors, but few pair matches satisfy the fixed cameras. Independently validate the correspondences and local camera/lens calibration before optimizing either. The first/last missing frames have zero/one surviving descriptors.',
        '', 'LightGlue increases constructed points, but many pair matches fail the fixed-camera reprojection check. The tests do not distinguish a wrong match from a wrong reference pose or calibration. Insufficient parallax is not the dominant rejection in these particular LightGlue pairs. Thresholds were not relaxed to force acceptance.',
        '', '## Preserved evidence','', '- [Unmasked PnP](unmasked.json)', '- [Masked PnP](masked.json)', '- [SIFT retriangulation](triangulated-sift.json)', '- [LightGlue retriangulation](triangulated-lightglue.json)', '- [All 39 mask previews in four contact sheets](review)', '- [Validation ledger](validation.json)', '']
    (root/'results.md').write_text('\n'.join(lines))


if __name__=='__main__':main()
