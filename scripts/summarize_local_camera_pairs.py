#!/usr/bin/env python3
"""Summarize the frozen gap-098 pair experiment without certifying camera poses."""
import argparse, hashlib, json, statistics
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(root):
    raw = json.loads((root / 'pairs.json').read_text())
    old = json.loads((root / 'evaluation.json').read_text())
    single = json.loads((root / 'evaluation-single.json').read_text())
    for report in (old, single):
        if report['identity']['pairs'] != digest(root / 'pairs.json'):
            raise ValueError('Pair identity mismatch')
    index = {(r['a'], r['b']): r for r in single['pairs']}
    selected = [r for r in old['pairs'] if r['variants']['lookback']['homography_passed']]
    comparisons = []
    for r in selected:
        comparisons.append(dict(a=r['a'], b=r['b'], da3_px=r['existing']['da3']['median_px'],
            vggt_four_px=r['existing']['vggt']['median_px'],
            vggt_single_px=index[r['a'], r['b']]['existing']['vggt']['median_px'],
            colmap_status=r['existing']['colmap']['status']))
    sensitivity = {}
    for variant in ('lookback', 'lookahead'):
        graph = {}
        for r in old['pairs']:
            c = r['variants'][variant]
            if c['homography_passed'] or c['relative_pose_screen_passed']:
                graph.setdefault(r['a'], set()).add(r['b'])
                graph.setdefault(r['b'], set()).add(r['a'])
        components = []
        while graph:
            pending = [next(iter(graph))]; component = set()
            while pending:
                name = pending.pop()
                if name in component: continue
                component.add(name); pending.extend(graph[name] - component)
            for name in component: del graph[name]
            components.append(sorted(component))
        sensitivity[variant] = dict(
            homography_passes=sum(r['variants'][variant]['homography_passed'] for r in old['pairs']),
            relative_pose_screen_passes=sum(r['variants'][variant]['relative_pose_screen_passed'] for r in old['pairs']),
            supported_components=components)
    crossing = [r for r in old['pairs'] if raw['frames'][r['a']]['timestamp'] < 414.562967 <= raw['frames'][r['b']]['timestamp']]
    return dict(status='complete-diagnostic-experiment-no-recovered-trajectory', accepted_poses=0,
        inputs={name:digest(root / name) for name in ('pairs.json','evaluation.json','evaluation-single.json')},
        frames=len(raw['frames']), pairs=len(raw['pairs']), camera_counts=old['camera_counts'],
        sensitivity=sensitivity, cross_return_pairs=len(crossing),
        cross_return_insufficient_matches=sum(r['variants']['lookback']['status']=='insufficient-independent-matches' for r in crossing),
        supported_planar_pair_comparisons=comparisons,
        median_of_pair_medians_px={key:statistics.median(r[key] for r in comparisons) for key in ('da3_px','vggt_four_px','vggt_single_px')},
        limitation='Planar-supported and correlated pair subset; epipolar errors do not establish metric scale, depth, full 3D pose correctness or a continuous camera path.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', type=Path, required=True)
    a = p.parse_args()
    result = summarize(a.evidence)
    (a.evidence / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:result[k] for k in ('frames','pairs','accepted_poses','median_of_pair_medians_px')}))


if __name__ == '__main__':
    main()
