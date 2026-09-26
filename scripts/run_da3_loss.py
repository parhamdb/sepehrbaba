#!/usr/bin/env python3
"""Run official DA3-Streaming on a frozen native clip; retain unreviewed poses."""
import argparse
import json
from pathlib import Path
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('checkout','weights','salad','images','frames','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    import numpy as np
    import torch
    import yaml
    torch.set_num_threads(4)
    streaming=a.checkout/'da3_streaming';sys.path.insert(0,str(streaming))
    from da3_streaming import DA3_Streaming
    frames=json.loads(a.frames.read_text())
    if sorted(f['name'] for f in frames)!=sorted(x.name for x in a.images.glob('*.jpg')):raise ValueError('Image inventory mismatch')
    a.output.mkdir(parents=True,exist_ok=False)
    config=yaml.safe_load((streaming/'configs/base_config.yaml').read_text())
    config['Weights']={'DA3':str(a.weights/'model.safetensors'),'DA3_CONFIG':str(a.weights/'config.json'),'SALAD':str(a.salad)}
    config['Model'].update(chunk_size=32,overlap=16,loop_chunk_size=8,align_lib='torch',delete_temp_files=True)
    config['Loop']['SIM3_Optimizer']['lang_version']='python'
    config['Loop']['SALAD']['batch_size']=8
    # Runtime config contains private paths; only publish the sanitized settings.
    (a.output/'runtime-config.yaml').write_text(yaml.safe_dump(config))
    started=time.time();runner=DA3_Streaming(str(a.images),str(a.output),config)
    runner.run();runner.close()
    matrices=np.loadtxt(a.output/'camera_poses.txt').reshape(-1,4,4)
    if len(matrices)!=len(frames) or not np.isfinite(matrices).all():raise ValueError('Missing or invalid camera matrices')
    rows=[]
    for f,C in zip(sorted(frames,key=lambda f:f['name']),matrices):
        R=C[:3,:3]
        if not np.allclose(R.T@R,np.eye(3),atol=1e-4) or np.linalg.det(R)<0:raise ValueError('Invalid camera rotation')
        rows.append(dict(**f,center=C[:3,3].tolist(),camera_to_world_rotation=R.tolist()))
    report=dict(method='DA3-Streaming',status='candidate poses; independent recovery review pending',
        input_frames=len(frames),estimated_frames=len(rows),elapsed_seconds=time.time()-started,
        settings={k:v for k,v in config.items() if k!='Weights'},frames=rows)
    (a.output/'poses.json').write_text(json.dumps(report,indent=2)+'\n')
    print('DA3 candidate poses exported; recovery remains unassessed',flush=True)


if __name__=='__main__':main()
