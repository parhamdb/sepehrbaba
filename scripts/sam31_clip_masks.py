#!/usr/bin/env python3
"""Generate SAM 3.1 visitor-mask proposals for review, not automatic motion labels.

Uses private Hugging Face authentication/cache; never accepts or logs a token.
Outputs retain per-object masks, source frame IDs and source timestamps.
"""
import argparse
import json
import inspect
from pathlib import Path
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--images',type=Path,required=True)
    p.add_argument('--frames',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prompt',default='standing person')
    p.add_argument('--limit',type=int,default=0,help='Optional smoke-test frame count, 0 means every frame')
    p.add_argument('--cpu-roi-align',action='store_true',help='Use the same torchvision ROI Align on CPU when its CUDA kernel is unavailable')
    a=p.parse_args()
    import numpy as np
    import torch
    from PIL import Image,ImageDraw
    from sam3.model_builder import build_sam3_predictor
    if a.cpu_roi_align:
        import torchvision
        roi_align = torchvision.ops.roi_align
        def cpu_roi_align(input, boxes, *args, **kwargs):
            cpu_boxes = [b.cpu().float() for b in boxes] if isinstance(boxes, list) else boxes.cpu().float()
            with torch.autocast('cuda', enabled=False):
                result = roi_align(input.cpu().float(), cpu_boxes, *args, **kwargs)
            return result.to(device=input.device, dtype=input.dtype)
        torchvision.ops.roi_align = cpu_roi_align
    torch.set_num_threads(4)
    frames=json.loads(a.frames.read_text())
    if a.limit:frames=frames[:a.limit]
    a.output.mkdir(parents=True,exist_ok=False)
    video=a.output/'tracking-frames';video.mkdir()
    masks=a.output/'proposals';masks.mkdir()
    reviews=a.output/'review';reviews.mkdir()
    for i,f in enumerate(frames):(video/f'{i:06d}.jpg').symlink_to((a.images/f['name']).resolve(strict=True))
    predictor=build_sam3_predictor(version='sam3.1',compile=False,warm_up=False,
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
        predictor.handle_request(dict(type='add_prompt',session_id=sid,frame_index=0,text=a.prompt))
        for response in predictor.handle_stream_request(dict(type='propagate_in_video',session_id=sid)):
            i=response['frame_index'];out=response['outputs'];f=frames[i]
            ids=np.asarray(out['out_obj_ids']).astype(int)
            binary=np.asarray(out['out_binary_masks']).astype(bool)
            with Image.open(a.images/f['name']) as im:
                width,height=im.size;im=im.convert('RGB')
                if len(ids) and binary.shape!=(len(ids),height,width):raise ValueError('Unexpected mask shape')
                union=np.any(binary,axis=0) if len(ids) else np.zeros((height,width),bool)
                Image.fromarray((~union).astype('uint8')*255).save(masks/(f['name']+'.png'))
                np.savez_compressed(masks/(Path(f['name']).stem+'.npz'),ids=ids,
                    shape=np.array([height,width]),masks=np.packbits(binary.reshape(len(ids),-1),axis=1) if len(ids) else np.empty((0,0),dtype=np.uint8))
                if i%15==0 or i==len(frames)-1:
                    arr=np.asarray(im).copy();arr[union]=(arr[union]*.4+np.array([255,100,20])*.6).astype('uint8')
                    review=Image.fromarray(arr);review.thumbnail((432,768))
                    draw=ImageDraw.Draw(review);draw.rectangle((0,0,432,35),fill='black')
                    draw.text((5,5),f'{f["timestamp"]:.3f}s | IDs {ids.tolist()} | PROPOSAL',fill='white')
                    review.save(reviews/(Path(f['name']).stem+'.jpg'))
            rows.append(dict(**f,object_ids=ids.tolist(),excluded_fraction=float(union.mean())))
            if i%20==0:print(f'Proposed masks {i+1}/{len(frames)}',flush=True)
        predictor.handle_request(dict(type='close_session',session_id=sid))
    if sorted(x['name'] for x in rows)!=sorted(x['name'] for x in frames):raise ValueError('Incomplete mask inventory')
    report=dict(method='SAM 3.1',prompt=a.prompt,frames=len(rows),elapsed_seconds=time.time()-started,
        cpu_roi_align=a.cpu_roi_align,
        status='proposals only; motion and protected static details require review',rows=rows)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('SAM 3.1 inference finished; proposals require review',flush=True)


if __name__=='__main__':main()
