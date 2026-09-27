#!/usr/bin/env python3
"""Evaluate the frozen three-pair numbered-landmark experiment, without alignment."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def distance(a, b):
    value = math.dist(a, b)
    if not math.isfinite(value):
        raise ValueError('Nonfinite coordinate distance')
    return value


def evaluate(root, review_path):
    cfg = read(root/'experiment.json')
    props = root/'proposals'
    questions = read(props/'questions.json')['questions']
    evidence = read(props/'matcher-evidence.json')
    review = read(review_path)
    ids = [q['id'] for q in questions]
    answers = {q['id']: q for q in review['questions']}
    if set(answers) != set(ids) or len(review['questions']) != len(ids):
        raise ValueError('Review must answer every question exactly once')
    if evidence['experiment_sha256'] != hashlib.sha256((root/'experiment.json').read_bytes()).hexdigest():
        raise ValueError('Experiment changed after inference')
    if len(evidence['pairs']) != 3 or [p['pair'] for p in evidence['pairs']] != cfg['pairs']:
        raise ValueError('Unexpected pair inventory')
    limits = cfg['thresholds']
    rows, supported = [], []
    for i, q in enumerate(questions):
        answer = answers[q['id']]
        if answer['choice'] not in q['allowed_answers']:
            raise ValueError('Invalid answer')
        if type(answer['physical_point_identifiable']) is not bool:
            raise ValueError('Missing physical point judgment')
        preds = [p['predictions'][i] for p in evidence['pairs']]
        if any(p['id'] != q['id'] for p in preds):
            raise ValueError('Prediction order mismatch')
        key = evidence['answer_key'][i]
        option = next((o for o in q['options'] if o['label'] == answer['choice']), None)
        nearest = next(o for o in q['options'] if o['label'] == key['nearest_dense_option'])
        # Always report numerical diagnostics of the model-preferred option,
        # including when the blinded reviewer abstained. Never call it accepted.
        transport = evidence['target_neighbor_transport'][nearest['target_feature_index']]
        source_transport = evidence['pairs'][1]['source_transport'][i]
        diagnostics = dict(
            model_preferred_option=nearest['label'],
            snap_distance_px=distance(nearest['xy'], preds[0]['target_xy']),
            warp_cycle_error_px=preds[0]['warp_return_error_px'],
            source_neighbor_prediction_delta_px=distance(preds[0]['target_xy'], preds[1]['target_xy']),
            source_neighbor_lk_valid=source_transport['valid'],
            source_neighbor_lk_return_error_px=source_transport['return_error_px'],
            target_neighbor_lk_valid=transport['valid'],
            target_neighbor_lk_return_error_px=transport['return_error_px'],
            target_neighbor_prediction_delta_px=distance(transport['xy'], preds[2]['target_xy']))
        diagnostics['passes_snap_and_cycle_limits'] = (diagnostics['snap_distance_px'] <= limits['target_snap_max_px'] and diagnostics['warp_cycle_error_px'] <= limits['warp_cycle_max_native_px'])
        selected = None
        if option:
            t = evidence['target_neighbor_transport'][option['target_feature_index']]
            selected = dict(xy=option['xy'], model_prediction_distance_px=distance(option['xy'], preds[0]['target_xy']), target_neighbor_lk_valid=t['valid'], target_neighbor_lk_return_error_px=t['return_error_px'], target_neighbor_prediction_delta_px=distance(t['xy'], preds[2]['target_xy']))
            if answer['physical_point_identifiable']:
                supported.append((q['source_xy'], option['xy']))
        elif answer['physical_point_identifiable']:
            raise ValueError('Abstention cannot identify a corresponding point')
        rows.append(dict(id=q['id'], summary=f"Luna: {answer['choice']}. {answer['reason']}", visual_review=answer, model_diagnostics=diagnostics, selected_option=selected, accepted_correspondence=False))
    geometry = dict(status='blocked', reason=f'Need six visually identifiable corresponding points; found {len(supported)}.', supported_points=len(supported), homography_fitted=False)
    if len(supported) >= 6:
        import cv2
        import numpy as np
        src, dst = map(lambda x: np.asarray(x, dtype=np.float64), zip(*supported))
        if min(np.linalg.matrix_rank(x-x.mean(axis=0)) for x in (src, dst)) < 2:
            geometry['reason'] = 'Collinear points cannot constrain a local homography.'
        else:
            errors = []
            for i in range(len(src)):
                keep = np.arange(len(src)) != i
                H, _ = cv2.findHomography(src[keep], dst[keep], cv2.RANSAC, limits['local_homography_ransac_px'])
                if H is None:
                    errors.append(None)
                else:
                    projected = cv2.perspectiveTransform(src[i:i+1, None], H)[0, 0]
                    errors.append(distance(projected.tolist(), dst[i].tolist()))
            geometry.update(status='evaluated', reason='Local flexible-surface fit only; not section alignment.', homography_fitted=True, held_out_errors_px=errors, held_out_pass=all(e is not None and e <= limits['held_out_local_reprojection_px'] for e in errors))
    return dict(summary=f"Luna identified {len(supported)} of {len(rows)} physical point correspondences. No camera connection accepted.", questions=rows, geometry=geometry, thresholds=limits, accepted_connection=False, limitations=['Model round-trip and neighboring-view consistency are not independent physical correspondence evidence.', 'Neighboring checks span about 0.05 seconds on each side, not the missing interval.', 'All queries lie in one flexible or occluded region. This experiment does not rule out matches elsewhere.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experiment-dir', type=Path, required=True)
    p.add_argument('--review', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = evaluate(a.experiment_dir, a.review)
    with a.output.open('x') as f:
        f.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(result['summary'])


if __name__ == '__main__':
    main()
