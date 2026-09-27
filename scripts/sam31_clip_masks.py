#!/usr/bin/env python3
"""Generate SAM 3.1 visitor-mask proposals for review, not automatic motion labels.

Uses private Hugging Face authentication/cache; never accepts or logs a token.
Outputs retain per-object masks, source frame IDs and source timestamps.
"""
import argparse
import json
import inspect
import hashlib
from pathlib import Path
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--images',type=Path,required=True)
    p.add_argument('--frames',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prompt',default='standing person')
    p.add_argument('--review-stride',type=int,default=15,help='Write an overlay every N frames; use 1 for full review')
    p.add_argument('--limit',type=int,default=0,help='Optional smoke-test frame count, 0 means every frame')
    p.add_argument('--cpu-roi-align',action='store_true',help='Use the same torchvision ROI Align on CPU when its CUDA kernel is unavailable')
    p.add_argument('--seed',type=Path,help='Reviewed JSON: frame name, normalized points and point_labels, reason; separate proposal session')
    a=p.parse_args()
    if a.review_stride<1:p.error('review-stride must be positive')
    import numpy as np
    import torch
    from PIL import Image,ImageDraw
    from sam3.model_builder import build_sam3_predictor
    if a.cpu_roi_align:
        import torchvision
        roi_align = torchvision.ops.roi_align
        def cpu_roi_align(input, boxes, *args, **kwargs):
            cpu_boxes = [b.cpu().float() for b in boxes] if isinstance(boxes, (list, tuple)) else boxes.cpu().float()
            with torch.autocast('cuda', enabled=False):
                result = roi_align(input.cpu().float(), cpu_boxes, *args, **kwargs)
            return result.to(device=input.device, dtype=input.dtype)
        torchvision.ops.roi_align = cpu_roi_align
    torch.set_num_threads(4)
    frames=json.loads(a.frames.read_text())
    if a.limit:frames=frames[:a.limit]
    seed=json.loads(a.seed.read_text()) if a.seed else None
    seed_index=0
    if seed:
        seed_index=next(i for i,f in enumerate(frames) if f['name']==seed['frame'])
        if not seed.get('reason'):raise ValueError('Reviewed seed reason required')
        if 'box' in seed:
            x,y,w,h=seed['box']
            if not seed.get('text') or not (0<=x<1 and 0<=y<1 and w>0 and h>0 and x+w<=1 and y+h<=1):raise ValueError('Invalid normalized semantic box')
        else:
            if len(seed['points'])!=len(seed['point_labels']) or not seed['points']:raise ValueError('Seed points required')
            if any(len(point)!=2 or not all(0<=x<=1 for x in point) for point in seed['points']) or any(x not in (0,1) for x in seed['point_labels']):raise ValueError('Invalid normalized point prompt')
    a.output.mkdir(parents=True,exist_ok=False)
    video=a.output/'tracking-frames';video.mkdir()
    masks=a.output/'proposals';masks.mkdir()
    reviews=a.output/'review';reviews.mkdir()
    for i,f in enumerate(frames):(video/f'{i:06d}.jpg').symlink_to((a.images/f['name']).resolve(strict=True))
    from huggingface_hub import hf_hub_download
    checkpoint=Path(hf_hub_download('facebook/sam3.1','sam3.1_multiplex.pt',local_files_only=True))
    predictor=build_sam3_predictor(checkpoint_path=str(checkpoint),version='sam3.1',compile=False,warm_up=False,
        use_fa3=False,async_loading_frames=False,max_num_objects=16)
    # Current base predictor passes this SAM2 option to multiplex SAM3.1,
    # whose init_state has no such parameter. False is the default behavior.
    original_init = predictor.model.init_state
    if 'offload_state_to_cpu' not in inspect.signature(original_init).parameters:
        def compatible_init(*args, **kwargs):
            if kwargs.pop('offload_state_to_cpu', False):
                raise ValueError('SAM 3.1 multiplex does not support state offloading')
            return original_init(*args, **kwargs)
        predictor.model.init_state = compatible_init
    started=time.time();rows=[]
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        sid=predictor.handle_request(dict(type='start_session',resource_path=str(video)))['session_id']
        if seed:
            if 'box' in seed:predictor.handle_request(dict(type='add_prompt',session_id=sid,frame_index=seed_index,text=seed['text'],bounding_boxes=[seed['box']],bounding_box_labels=[1],clear_old_boxes=True))
            else:predictor.handle_request(dict(type='add_prompt',session_id=sid,frame_index=seed_index,points=seed['points'],point_labels=seed['point_labels'],obj_id=1,rel_coordinates=True,clear_old_points=True,output_prob_thresh=.5))
        else:predictor.handle_request(dict(type='add_prompt',session_id=sid,frame_index=0,text=a.prompt))
        propagation=dict(type='propagate_in_video',session_id=sid)
        if seed:propagation.update(start_frame_index=seed_index,propagation_direction='both')
        seen=set()
        for response in predictor.handle_stream_request(propagation):
            i=response['frame_index'];out=response['outputs'];f=frames[i]
            if i in seen:continue
            seen.add(i)
            ids=np.asarray(out['out_obj_ids']).astype(int)
            binary=np.asarray(out['out_binary_masks']).astype(bool)
            with Image.open(a.images/f['name']) as im:
                width,height=im.size;im=im.convert('RGB')
                if len(ids) and binary.shape!=(len(ids),height,width):raise ValueError('Unexpected mask shape')
                union=np.any(binary,axis=0) if len(ids) else np.zeros((height,width),bool)
                Image.fromarray((~union).astype('uint8')*255).save(masks/(f['name']+'.png'))
                np.savez_compressed(masks/(Path(f['name']).stem+'.npz'),ids=ids,
                    shape=np.array([height,width]),masks=np.packbits(binary.reshape(len(ids),-1),axis=1) if len(ids) else np.empty((0,0),dtype=np.uint8))
                if i%a.review_stride==0 or i==len(frames)-1:
                    arr=np.asarray(im).copy();arr[union]=(arr[union]*.4+np.array([255,100,20])*.6).astype('uint8')
                    review=Image.fromarray(arr);review.thumbnail((432,768))
                    draw=ImageDraw.Draw(review);draw.rectangle((0,0,432,35),fill='black')
                    draw.text((5,5),f'{f["timestamp"]:.3f}s | IDs {ids.tolist()} | PROPOSAL',fill='white')
                    review.save(reviews/(Path(f['name']).stem+'.jpg'))
            rows.append(dict(**f,object_ids=ids.tolist(),excluded_fraction=float(union.mean()),source_sha256=hashlib.sha256((a.images/f['name']).read_bytes()).hexdigest(),mask_sha256=hashlib.sha256((masks/(f['name']+'.png')).read_bytes()).hexdigest()))
            if i%20==0:print(f'Proposed masks {i+1}/{len(frames)}',flush=True)
        predictor.handle_request(dict(type='close_session',session_id=sid))
    if sorted(x['name'] for x in rows)!=sorted(x['name'] for x in frames):raise ValueError('Incomplete mask inventory')
    report=dict(method='SAM 3.1 video propagation with persistent object IDs',script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),prompt=None if seed else a.prompt,frames=len(rows),nonempty_frames=sum(r['excluded_fraction']>0 for r in rows),elapsed_seconds=time.time()-started,
        cpu_roi_align=a.cpu_roi_align,seed=seed,
        status='proposals only; motion and protected static details require review',rows=rows)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('SAM 3.1 inference finished; proposals require review',flush=True)


if __name__=='__main__':main()
