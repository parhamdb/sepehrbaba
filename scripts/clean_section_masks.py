#!/usr/bin/env python3
"""Propose selective obstruction masks while explicitly protecting ground bodies.

Runs the SAM 3.1 native image detector on undistorted reconstruction images.
Independent-frame segmentation is not motion classification or video tracking.
Outputs are proposals; inspect overlays before using them for training.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sample-count', type=int, default=0)
    parser.add_argument('--exclude', action='append', help='Reviewed obstruction category; repeat as needed')
    args = parser.parse_args()
    import cv2
    import numpy as np
    import torch
    import torchvision
    from PIL import Image
    from huggingface_hub import hf_hub_download
    from sam3.model_builder import build_sam3_predictor
    from sam3.model.sam3_image_processor import Sam3Processor

    files = sorted((args.dataset/'images').glob('*.jpg'))
    if not files:
        parser.error('No dataset JPEG images')
    if args.sample_count:
        if args.sample_count < 2:
            parser.error('sample-count must be at least two')
        files = [files[i] for i in sorted(set(np.linspace(0,len(files)-1,args.sample_count).round().astype(int))) ]
    checkpoint = Path(hf_hub_download('facebook/sam3.1','sam3.1_multiplex.pt',local_files_only=True))
    exclude = args.exclude or ['standing person', 'walking person']
    protect = ['person lying on the ground', 'person lying down', 'body bag']
    manifest = dict(model='SAM 3.1 native image detector', checkpoint_sha256=sha(checkpoint),
        script_sha256=sha(__file__), exclude_prompts=exclude, protect_prompts=protect,
        threshold=.5, dilation_pixels=5, images={p.name:sha(p) for p in files},
        status='proposals requiring visual review; not motion labels')
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_path=args.output/'manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text())!=manifest:
        raise ValueError('Input/configuration changed; use a new output directory')
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    for sub in ['masks','protected','review','metadata']:
        (args.output/sub).mkdir(exist_ok=True)
    todo=[]
    for path in files:
        meta=args.output/'metadata'/(path.stem+'.json')
        if meta.exists():
            row=json.loads(meta.read_text())
            for sub,key in [('masks','mask_sha256'),('protected','protected_sha256')]:
                if sha(args.output/sub/(path.stem+'.png'))!=row[key]:raise ValueError('Saved mask changed')
        else:todo.append(path)
    if not todo:return
    torch.set_num_threads(4)
    original_roi=torchvision.ops.roi_align
    def cpu_roi(value,boxes,*a,**kw):
        boxes=[b.cpu().float() for b in boxes] if isinstance(boxes,(list,tuple)) else boxes.cpu().float()
        with torch.autocast('cuda',enabled=False):result=original_roi(value.cpu().float(),boxes,*a,**kw)
        return result.to(device=value.device,dtype=value.dtype)
    torchvision.ops.roi_align=cpu_roi
    predictor=build_sam3_predictor(checkpoint_path=str(checkpoint),version='sam3.1',compile=False,
        warm_up=False,use_fa3=False,async_loading_frames=False,max_num_objects=16)
    processor=Sam3Processor(predictor.model.detector,confidence_threshold=.5)
    started=time.time()
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        for index,path in enumerate(todo):
            image=Image.open(path).convert('RGB');state=processor.set_image(image)
            unwanted=np.zeros((image.height,image.width),bool);protected=unwanted.copy();scores={}
            for prompt in exclude+protect:
                processor.reset_all_prompts(state)
                result=processor.set_text_prompt(prompt,state)
                masks=result['masks'].detach().cpu().numpy().reshape(-1,image.height,image.width)
                union=np.any(masks>0,axis=0) if len(masks) else np.zeros_like(unwanted)
                if prompt in exclude:unwanted|=union
                else:protected|=union
                scores[prompt]=result['scores'].detach().float().cpu().tolist()
            unwanted=cv2.dilate(unwanted.astype('uint8'),np.ones((5,5),np.uint8))>0
            ambiguity=unwanted&protected
            # Preservation wins on disputed pixels; never assume a semantic prompt is perfect.
            unwanted&=~protected
            mask_path=args.output/'masks'/(path.stem+'.png')
            protected_path=args.output/'protected'/(path.stem+'.png')
            Image.fromarray((~unwanted).astype('uint8')*255).save(mask_path)
            Image.fromarray(protected.astype('uint8')*255).save(protected_path)
            preview=np.asarray(image).copy()
            preview[protected]=(preview[protected]*.65+np.array([0,180,230])*.35).astype('uint8')
            preview[unwanted]=(preview[unwanted]*.4+np.array([255,75,20])*.6).astype('uint8')
            review=Image.fromarray(preview);review.thumbnail((432,768));review.save(args.output/'review'/(path.stem+'.jpg'))
            row=dict(image=path.name,source_sha256=manifest['images'][path.name],scores=scores,
                excluded_fraction=float(unwanted.mean()),protected_fraction=float(protected.mean()),
                ambiguous_fraction=float(ambiguity.mean()),mask_sha256=sha(mask_path),protected_sha256=sha(protected_path))
            (args.output/'metadata'/(path.stem+'.json')).write_text(json.dumps(row,indent=2)+'\n')
            print(json.dumps(dict(done=index+1,total=len(todo),elapsed_seconds=round(time.time()-started,1),**row)),flush=True)
    rows=[json.loads((args.output/'metadata'/(p.stem+'.json')).read_text()) for p in files]
    (args.output/'report.json').write_text(json.dumps(dict(status='awaiting visual review',frames=len(rows),rows=rows),indent=2)+'\n')


if __name__=='__main__':main()
