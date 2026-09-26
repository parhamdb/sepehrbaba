#!/usr/bin/env python3
"""Track reviewed moving occluders with SAM 2.1 into a NEW Brush dataset.

Prompts use normalized image coordinates. This is segmentation, not automatic
motion classification. Review source motion and output masks before training.
Requires the official SAM 2 checkout, torch, numpy and Pillow.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_prompts(document, names):
    objects = document['objects']
    if not objects or len({o['id'] for o in objects}) != len(objects):
        raise ValueError('Need distinct object IDs')
    for obj in objects:
        if not obj.get('motion_review') or not obj.get('prompts'):
            raise ValueError('Each object needs a source-motion review and prompts')
        for prompt in obj['prompts']:
            points, labels = np.asarray(prompt['points']), prompt['labels']
            if prompt['image'] not in names or points.shape != (len(labels), 2):
                raise ValueError('Invalid prompt image or point dimensions')
            if not np.isfinite(points).all() or (points < 0).any() or (points > 1).any():
                raise ValueError('Coordinates must be normalized to [0, 1]')
            if 1 not in labels or any(label not in (0, 1) for label in labels):
                raise ValueError('Need positive foreground and binary labels')
    return objects


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset', type=Path)
    p.add_argument('prompts', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--config', default='configs/sam2.1/sam2.1_hiera_s.yaml')
    p.add_argument('--model-revision', required=True)
    p.add_argument('--dilation', type=int, default=7)
    a = p.parse_args()
    files = sorted((a.dataset/'images').glob('*.jpg'))
    if not files or a.dilation < 1 or a.dilation % 2 != 1:
        p.error('Need input JPEGs and an odd positive dilation width')
    names = [f.name for f in files]
    document = json.loads(a.prompts.read_text())
    objects = validate_prompts(document, names)
    a.output.mkdir(parents=True, exist_ok=False)
    dataset = a.output/'dataset'
    dataset.mkdir()
    (dataset/'images').symlink_to((a.dataset/'images').resolve(), target_is_directory=True)
    shutil.copytree(a.dataset/'sparse', dataset/'sparse')
    masks = dataset/'masks'
    masks.mkdir()
    video = a.output/'tracking-frames'
    video.mkdir()
    sizes = []
    for i, source in enumerate(files):
        (video/f'{i:06d}.jpg').symlink_to(source.resolve())
        with Image.open(source) as im:
            sizes.append(im.size)
            Image.new('L', im.size, 255).save(masks/(source.stem+'.png'))
    if len(set(sizes)) != 1:
        raise ValueError('SAM video tracking requires constant frame dimensions')
    import torch
    from sam2.build_sam import build_sam2_video_predictor
    torch.set_num_threads(4)
    predictor = build_sam2_video_predictor(a.config, str(a.checkpoint),
                                         device='cuda', apply_postprocessing=False)
    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
        state = predictor.init_state(str(video), offload_video_to_cpu=True,
                                     offload_state_to_cpu=True)
        for obj in objects:
            predictor.reset_state(state)
            indices = []
            for prompt in obj['prompts']:
                idx = names.index(prompt['image'])
                indices.append(idx)
                points = np.asarray(prompt['points'], dtype=np.float32) * (np.array(sizes[idx])-1)
                predictor.add_new_points_or_box(state, frame_idx=idx, obj_id=obj['id'],
                                                points=points, labels=np.asarray(prompt['labels']))
            visited = set()
            # Propagate on both sides of the earliest anchor, without assuming
            # that an object was already visible in the first frame.
            for reverse in (False, True):
                for idx, ids, logits in predictor.propagate_in_video(
                        state, start_frame_idx=min(indices), reverse=reverse):
                    if idx in visited:
                        continue
                    visited.add(idx)
                    excluded = (logits[ids.index(obj['id']), 0] > 0).cpu().numpy()
                    path = masks/(files[idx].stem+'.png')
                    with Image.open(path) as im:
                        keep = np.asarray(im).copy()
                    keep[excluded] = 0
                    Image.fromarray(keep).save(path)
            if len(visited) != len(files):
                raise RuntimeError('Incomplete object propagation')
            print(f'tracked object {obj["id"]}: {len(visited)} frames', flush=True)
    rows = []
    for source in files:
        path = masks/(source.stem+'.png')
        with Image.open(path) as im:
            result = im.filter(ImageFilter.MinFilter(a.dilation))
            result.save(path)
            fraction = float((np.asarray(result) == 0).mean())
        rows.append({'image': source.name, 'excluded_fraction': fraction,
                     'source_sha256': digest(source), 'mask_sha256': digest(path)})
    report = {'model': 'SAM 2.1 Hiera small', 'model_revision': a.model_revision,
              'checkpoint_sha256': digest(a.checkpoint), 'prompts_sha256': digest(a.prompts),
              'dilation_pixels': a.dilation, 'motion_classification': 'manual source review',
              'postprocessing': False, 'review_required': True, 'images': rows}
    (dataset/'mask-report.json').write_text(json.dumps(report, indent=2)+'\n')
    shutil.copyfile(a.prompts, a.output/'prompts.json')
    print(f'Completed {len(rows)} masks. Review required before training.', flush=True)


if __name__ == '__main__':
    main()
