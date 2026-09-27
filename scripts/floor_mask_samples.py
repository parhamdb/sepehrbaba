#!/usr/bin/env python3
"""Sample the full recording and propose visible-floor masks with cached SAM3.1 detector weights."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('images','frames','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--limit',type=int,default=0)
    a=p.parse_args()
    import cv2, torch
    from PIL import Image
    from huggingface_hub import hf_hub_download
    from sam3.model_builder import build_sam3_predictor
    from sam3.model.sam3_image_processor import Sam3Processor
    torch.set_num_threads(4)
    frames=json.loads(a.frames.read_text());ts=np.array([f['timestamp'] for f in frames])
    samples=[];pairs=[]
    for t in np.arange(0,ts[-1],15):
        ids=[int(np.argmin(abs(ts-min(t+offset,ts[-1])))) for offset in (0,1)]
        pairs.append(ids)
        for i in ids:
            if i not in [f['index'] for f in samples]:samples.append(dict(frames[i],index=i))
    ckpt=Path(hf_hub_download('facebook/sam3.1','sam3.1_multiplex.pt',local_files_only=True))
    manifest=dict(prompt=['floor','ground'],method='SAM3.1 native image detector; independent frames; CPU ROI Align',
                  checkpoint_sha256=sha(ckpt),frames_sha256=sha(a.frames),samples=samples,pairs=pairs,interval_seconds=15)
    a.output.mkdir(parents=True,exist_ok=True)
    if (a.output/'selection.json').exists() and json.loads((a.output/'selection.json').read_text())!=manifest:raise ValueError('Selection changed')
    (a.output/'selection.json').write_text(json.dumps(manifest,indent=2)+'\n')
    todo=[f for f in samples if not (a.output/(f['name']+'.png')).exists()]
    if a.limit:todo=todo[:a.limit]
    if not todo:return
    # Thor's torchvision lacks CUDA ROI Align; use the established CPU fallback.
    import torchvision
    roi_align=torchvision.ops.roi_align
    def cpu_roi_align(value,boxes,*args,**kwargs):
        cpu_boxes=[b.cpu().float() for b in boxes] if isinstance(boxes,(list,tuple)) else boxes.cpu().float()
        with torch.autocast('cuda',enabled=False):result=roi_align(value.cpu().float(),cpu_boxes,*args,**kwargs)
        return result.to(device=value.device,dtype=value.dtype)
    torchvision.ops.roi_align=cpu_roi_align
    predictor=build_sam3_predictor(checkpoint_path=str(ckpt),version='sam3.1',compile=False,warm_up=False,use_fa3=False,async_loading_frames=False,max_num_objects=16)
    processor=Sam3Processor(predictor.model.detector,confidence_threshold=.5)
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        for f in todo:
            path=a.images/f['name'];im=Image.open(path).convert('RGB')
            state=processor.set_image(im);mask=np.zeros((im.height,im.width),bool);scores={}
            for prompt in ('floor','ground'):
                processor.reset_all_prompts(state)
                out=processor.set_text_prompt(prompt,state)
                masks=out['masks'].detach().cpu().numpy().reshape(-1,im.height,im.width)
                if len(masks):mask |= np.any(masks>0,axis=0)
                scores[prompt]=out['scores'].detach().float().cpu().tolist()
            cv2.imwrite(str(a.output/(f['name']+'.png')),mask.astype('uint8')*255)
            meta=dict(source_sha256=sha(path),floor_fraction=float(mask.mean()),scores=scores,proposal_only=True)
            (a.output/(f['name']+'.json')).write_text(json.dumps(meta)+'\n')
            preview=np.asarray(im).copy();preview[mask]=(preview[mask]*.5+np.array([0,220,200])*.5).astype('uint8')
            Image.fromarray(preview).resize((270,480)).save(a.output/(f['name']+'.preview.jpg'))
            print(json.dumps(dict(frame=f['name'],seconds=f['timestamp'],floor_fraction=meta['floor_fraction'])),flush=True)


if __name__=='__main__':main()
