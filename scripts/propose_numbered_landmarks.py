#!/usr/bin/env python3
"""Propose numbered SIFT locations using RoMa v2, without accepting geometry.

Run with the pinned official RoMaV2 checkout on PYTHONPATH. Original full images
enter the dense model. A frozen region restricts review candidates only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from romav2 import RoMaV2


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def detect(im, roi, contrast):
    sift = cv2.SIFT_create(contrastThreshold=contrast)
    keypoints, descriptors = sift.detectAndCompute(im, None)
    x0, y0, x1, y1 = roi
    rows = []
    for k, d in zip(keypoints, descriptors):
        if x0 <= k.pt[0] < x1 and y0 <= k.pt[1] < y1:
            rows.append((dict(xy=list(k.pt), response=k.response, size=k.size, angle=k.angle), d))
    rows.sort(key=lambda row: (-row[0]['response'], row[0]['xy']))
    unique = []
    for row in rows:
        if all(np.linalg.norm(np.array(row[0]['xy'])-u[0]['xy']) >= 4 for u in unique):
            unique.append(row)
    return unique


def track(a, b, xy):
    pts = np.asarray(xy, np.float32).reshape(-1, 1, 2)
    out, status, _ = cv2.calcOpticalFlowPyrLK(a, b, pts, None, winSize=(31, 31), maxLevel=3)
    back, status_back, _ = cv2.calcOpticalFlowPyrLK(b, a, out, None, winSize=(31, 31), maxLevel=3)
    return [dict(xy=q.tolist(), valid=bool(s and t and np.isfinite(q).all()), return_error_px=float(np.linalg.norm(r-p))) for p, q, r, s, t in zip(pts[:, 0], out[:, 0], back[:, 0], status[:, 0], status_back[:, 0])]


def sample(field, xy, width=1080, height=1920):
    # Same normalized-coordinate convention as the official to_pixel helper.
    q = torch.as_tensor(xy, device=field.device, dtype=torch.float32)
    q = 2*q/q.new_tensor([width, height])-1
    values = F.grid_sample(field.permute(0, 3, 1, 2).float(), q[None, None], align_corners=False)
    return values[0, :, 0].T.cpu().numpy()


def warp(pred, xy, direction):
    q = sample(pred['warp_'+direction], xy)
    return (q+1)/2*np.array([1080, 1920])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('images', 'experiment', 'model_repo', 'output'):
        p.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error('Output exists; retain previous experiment')
    cfg = json.loads(a.experiment.read_text())
    a.output.mkdir(parents=True)
    cv2.setNumThreads(4)
    torch.set_num_threads(4)
    torch.manual_seed(20260927)
    images = {}
    for name, expected in cfg['image_sha256'].items():
        if Path(name).name != name or digest(a.images/name) != expected:
            raise ValueError('Unsafe name or source hash mismatch')
        im = cv2.imread(str(a.images/name), cv2.IMREAD_GRAYSCALE)
        if im is None or im.shape != (1920, 1080):
            raise ValueError('Expected original 1080x1920 JPEG')
        images[name] = im
    main_a, main_b = cfg['pairs'][cfg['main_pair_index']]
    source = detect(images[main_a], cfg['source_roi_xyxy'], cfg['thresholds']['sift_contrast'])
    target = detect(images[main_b], cfg['target_roi_xyxy'], cfg['thresholds']['sift_contrast'])
    references = []
    for k, d in source:
        if all(np.linalg.norm(np.array(k['xy'])-r[0]['xy']) >= cfg['minimum_reference_separation_px'] for r in references):
            references.append((k, d))
        if len(references) == cfg['maximum_reference_points']:
            break
    if not references or len(target) < cfg['options_per_question']:
        raise ValueError('Insufficient detector features for numbered choices')
    ref_xy = np.array([k['xy'] for k, _ in references])
    save(a.output/'features.json', dict(source_region_features=len(source), target_region_features=len(target), references=[k for k, _ in references], targets=[k for k, _ in target], opencv_version=cv2.__version__))
    print(json.dumps(dict(stage='features', references=len(references), source_candidates=len(source), target_candidates=len(target))), flush=True)
    model = RoMaV2()
    model.apply_setting(cfg['setting'])
    outputs = []
    for i, (left, right) in enumerate(cfg['pairs']):
        start = time.monotonic()
        transport = track(images[main_a], images[left], ref_xy) if left != main_a else [dict(xy=q.tolist(), valid=True, return_error_px=0) for q in ref_xy]
        queries = np.array([t['xy'] for t in transport])
        with torch.inference_mode():
            predictions = model.match(str(a.images/left), str(a.images/right))
            mapped = warp(predictions, queries, 'AB')
            back = warp(predictions, mapped, 'BA')
            overlaps = sample(predictions['overlap_AB'], queries)[:, 0]
        if not np.isfinite(mapped).all() or not np.isfinite(back).all():
            raise ValueError('Nonfinite dense prediction')
        row = dict(pair=[left, right], source_transport=transport, predictions=[dict(id=f'Q{j+1}', source_xy=queries[j].tolist(), target_xy=mapped[j].tolist(), overlap_score=float(overlaps[j]), warp_return_error_px=float(np.linalg.norm(back[j]-queries[j]))) for j in range(len(references))], elapsed_seconds=time.monotonic()-start)
        outputs.append(row)
        save(a.output/f'pair-{i}.json', row)
        print(json.dumps(dict(stage='pair_complete', index=i, seconds=row['elapsed_seconds'], scores=overlaps.tolist())), flush=True)
        del predictions
        torch.cuda.empty_cache()
    rng = np.random.default_rng(cfg['option_order_seed'])
    target_xy = np.array([k['xy'] for k, _ in target])
    target_descriptors = np.stack([d for _, d in target])
    questions, answer_key = [], []
    for i, (keypoint, descriptor) in enumerate(references):
        predicted = np.array(outputs[0]['predictions'][i]['target_xy'])
        distances = np.linalg.norm(target_xy-predicted, axis=1)
        descriptor_distances = np.linalg.norm(target_descriptors-descriptor, axis=1)
        nearest = int(np.argmin(distances))
        # Include the nearest detected point and descriptor alternatives; all
        # options are actual detector locations, never invented pixel offsets.
        candidates = []
        for idx in [nearest]+np.argsort(descriptor_distances).tolist()+np.argsort(distances).tolist():
            if idx not in candidates and all(np.linalg.norm(target_xy[idx]-target_xy[j]) >= 12 for j in candidates):
                candidates.append(idx)
            if len(candidates) == cfg['options_per_question']:
                break
        if len(candidates) != cfg['options_per_question']:
            raise ValueError('Insufficient distinct distractors')
        rng.shuffle(candidates)
        question = dict(id=f'Q{i+1}', source_frame=main_a, target_frame=main_b, source_xy=keypoint['xy'], source_scale_px=keypoint['size'], options=[dict(label=str(j+1), target_feature_index=int(idx), xy=target_xy[idx].tolist()) for j, idx in enumerate(candidates)], allowed_answers=['1', '2', '3', '4', 'none', 'unclear'])
        questions.append(question)
        answer_key.append(dict(id=question['id'], nearest_dense_option=next(o['label'] for o in question['options'] if o['target_feature_index']==nearest), snap_distance_px=float(distances[nearest]), nearest_within_frozen_snap_limit=bool(distances[nearest]<=cfg['thresholds']['target_snap_max_px']), dense_prediction=outputs[0]['predictions'][i]))
    # Neighbor transport for all target options: retained independently of Luna.
    after_neighbor = cfg['pairs'][2][1]
    neighbor_targets = track(images[main_b], images[after_neighbor], target_xy)
    save(a.output/'questions.json', dict(method='Numbered detector choices; none and unclear permitted; scores hidden during visual review', questions=questions, source_crop_xyxy=cfg['review_source_crop_xyxy'], target_crop_xyxy=cfg['review_target_crop_xyxy']))
    save(a.output/'matcher-evidence.json', dict(answer_key=answer_key, pairs=outputs, target_neighbor_frame=after_neighbor, target_neighbor_transport=neighbor_targets, model_revision=subprocess.check_output(['git', '-C', str(a.model_repo), 'rev-parse', 'HEAD'], text=True).strip(), model_settings=dict(lr=[model.H_lr, model.W_lr], hr=[model.H_hr, model.W_hr], bidirectional=model.bidirectional), checkpoint_sha256=digest(Path(torch.hub.get_dir())/'checkpoints/romav2.0.1.pt'), script_sha256=digest(__file__), experiment_sha256=digest(a.experiment), torch_version=torch.__version__, accepted_connection=False))
    print(json.dumps(dict(stage='complete', questions=len(questions))), flush=True)


if __name__ == '__main__':
    main()
