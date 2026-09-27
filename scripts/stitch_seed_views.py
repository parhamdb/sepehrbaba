#!/usr/bin/env python3
"""Normalize independent sections to selected seed cameras for manual placement.

This is a convenient common viewing gauge, NOT an estimated scene connection.
Source COLMAP text models and Gaussian files remain unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from clean_static_geometry import read_model, rotation


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--section',nargs=3,action='append',required=True,metavar=('ID','MODEL_TEXT','SEED_IMAGE'))
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();rows=[];D=np.diag([-1.,-1.,1.])
    for key,folder,seed in args.section:
        model=Path(folder);images,points=read_model(model)
        im=next(i for i in images.values() if i['row'][9]==seed)
        R=rotation(im['row']);t=np.array(im['row'][5:8],float)
        ids=[int(pid) for pid in im['obs'][:,2] if pid>=0]
        xyz=np.array([points[pid][1:4] for pid in ids],float)
        depth=(xyz@R.T+t)[:,2];valid=depth[np.isfinite(depth)&(depth>0)]
        if len(valid)<10:raise ValueError('Seed needs ten finite positive-depth observations')
        unit=float(np.median(valid));center=-R.T@t;rr=D@R@D;tt=D@t/unit
        if np.linalg.norm(rr@(D@center)/unit+tt)>1e-8:raise ValueError('Seed origin conversion failed')
        if np.linalg.norm(rr@(D@R.T@np.array([0,0,1]))-[0,0,1])>1e-8:raise ValueError('View direction conversion failed')
        rows.append(dict(id=key,seed=seed,rotation_matrix=rr.tolist(),translation=tt.tolist(),scale=1/unit,
            median_depth=unit,source_model_sha256={f:hashlib.sha256((model/f).read_bytes()).hexdigest()
                for f in ['cameras.txt','images.txt','points3D.txt']}))
    args.output.write_text(json.dumps(rows,indent=2)+'\n')


if __name__=='__main__':main()
