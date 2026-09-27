#!/usr/bin/env python3
"""Mask selected gap anchors with SAM3.1 static surfaces minus people. Proposals need review."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('images','selection','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--limit',type=int,default=0)
    a=p.parse_args()
    import cv2, torch
    from PIL import Image
    from huggingface_hub import hf_hub_download
    from sam3.model_builder import build_sam3_predictor
    from sam3.model.sam3_image_processor import Sam3Processor
    torch.set_num_threads(4)
    selection=json.loads(a.selection.read_text());samples=selection['samples']
    positive=('floor','ground','wall');negative=('person',)
    ckpt=Path(hf_hub_download('facebook/sam3.1','sam3.1_multiplex.pt',local_files_only=True))
    manifest=dict(positive_prompts=positive,negative_prompts=negative,negative_dilation_pixels=21,
        method='SAM3.1 native image detector; independent frames; CPU ROI Align; static surfaces minus dilated people',
        checkpoint_sha256=sha(ckpt),selection_sha256=sha(a.selection),script_sha256=sha(Path(__file__)),samples=samples)
    # JSON roundtrip keeps resume identity stable across tuple/list serialization.
    manifest=json.loads(json.dumps(manifest))
    a.output.mkdir(parents=True,exist_ok=True)
    if (a.output/'selection.json').exists() and json.loads((a.output/'selection.json').read_text())!=manifest:raise ValueError('Selection changed')
    (a.output/'selection.json').write_text(json.dumps(manifest,indent=2)+'\n')
    todo=[]
    for f in samples:
        name=f['name'];image_path=a.images/name
        if sha(image_path)!=selection['image_sha256'][name]:raise ValueError('Source image differs from selection')
        mask_path=a.output/(name+'.png');meta_path=a.output/(name+'.json')
        if mask_path.exists() and meta_path.exists():
            meta=json.loads(meta_path.read_text())
            if meta['mask_sha256']!=sha(mask_path) or meta['source_sha256']!=sha(image_path):raise ValueError('Saved mask/source changed')
        else:todo.append(f)
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
            state=processor.set_image(im);mask=np.zeros((im.height,im.width),bool);people=mask.copy();scores={}
            for prompt in positive+negative:
                processor.reset_all_prompts(state)
                out=processor.set_text_prompt(prompt,state)
                masks=out['masks'].detach().cpu().numpy().reshape(-1,im.height,im.width)
                if len(masks):
                    if prompt in positive:mask |= np.any(masks>0,axis=0)
                    else:people |= np.any(masks>0,axis=0)
                scores[prompt]=out['scores'].detach().float().cpu().tolist()
            people=cv2.dilate(people.astype('uint8'),np.ones((21,21),np.uint8))>0
            mask &= ~people
            cv2.imwrite(str(a.output/(f['name']+'.png')),mask.astype('uint8')*255)
            meta=dict(source_sha256=sha(path),static_fraction=float(mask.mean()),people_fraction=float(people.mean()),mask_sha256=sha(a.output/(f['name']+'.png')),scores=scores,proposal_only=True)
            (a.output/(f['name']+'.json')).write_text(json.dumps(meta)+'\n')
            preview=np.asarray(im).copy();preview[people]=(preview[people]*.5+np.array([230,0,0])*.5).astype('uint8');preview[mask]=(preview[mask]*.5+np.array([0,220,200])*.5).astype('uint8')
            Image.fromarray(preview).resize((270,480)).save(a.output/(f['name']+'.preview.jpg'))
            print(json.dumps(dict(frame=f['name'],seconds=f['timestamp'],static_fraction=meta['static_fraction'])),flush=True)


if __name__=='__main__':main()
