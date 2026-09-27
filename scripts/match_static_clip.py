#!/usr/bin/env python3
"""Cache all masked native SIFT/LightGlue pairs in a frozen bounded clip.

No camera estimate is used to choose or filter matches. Match-cache output can be
reused for different geometric checks without rerunning inference.
"""
import argparse,importlib.util,itertools,json,sqlite3,subprocess
from pathlib import Path
import cv2,numpy as np
from probe_gap_recovery import digest,mask_indices,write
from triangulate_static_gap import independent_features


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('selection','database','masks','lightglue','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();import torch
    torch.set_num_threads(4);cv2.setNumThreads(2)
    pin='eb42fee2d71449efb0aa5c10549752b5d75384d8'
    if subprocess.check_output(['git','-C',str(a.lightglue),'rev-parse','HEAD'],text=True).strip()!=pin:raise ValueError('Pinned LightGlue required')
    spec=importlib.util.spec_from_file_location('lg',a.lightglue/'lightglue/lightglue.py');lg=importlib.util.module_from_spec(spec);spec.loader.exec_module(lg)
    matcher=lg.LightGlue(features='sift',depth_confidence=-1,width_confidence=-1).eval().cuda()
    selection=json.loads(a.selection.read_text());manifest=json.loads((a.masks/'selection.json').read_text())
    if manifest['selection_sha256']!=digest(a.selection):raise ValueError('Mask selection changed')
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True);ids=dict(db.execute('select name,image_id from images'))
    identity=dict(selection=digest(a.selection),database=digest(a.database),masks=digest(a.masks/'selection.json'),lightglue=pin,script=digest(Path(__file__)),support_script=digest(Path(__file__).with_name('probe_gap_recovery.py')),dedup_script=digest(Path(__file__).with_name('triangulate_static_gap.py')))
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True);features={};public={};mask_hashes={}
    for frame in selection['samples']:
        name=frame['name'];iid=ids[name]
        def array(table,dtype):
            nr,nc,blob=db.execute(f'SELECT rows,cols,data FROM {table} WHERE image_id=?',(iid,)).fetchone();return np.frombuffer(blob,dtype).reshape(nr,nc)
        kp=array('keypoints',np.float32);d=array('descriptors',np.uint8).astype(np.float32)
        if kp.shape[1]!=6 or len(d)!=len(kp):raise ValueError('Unexpected native SIFT layout')
        d/=np.maximum(np.linalg.norm(d,axis=1,keepdims=True),1e-8);scale=(np.hypot(kp[:,2],kp[:,4])+np.hypot(kp[:,3],kp[:,5]))/2;ori=np.arctan2(kp[:,4],kp[:,2])
        path=a.masks/(name+'.png');meta=json.loads((a.masks/(name+'.json')).read_text());mask_hashes[name]=digest(path)
        if mask_hashes[name]!=meta['mask_sha256'] or meta['source_sha256']!=selection['image_sha256'][name]:raise ValueError('Mask/source changed')
        mask=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
        if mask is None or mask.shape!=(1920,1080):raise ValueError('Native mask required')
        distance=cv2.distanceTransform(np.pad((mask>0).astype(np.uint8),1),cv2.DIST_L2,5)[1:-1,1:-1]
        idx=independent_features(kp,mask_indices(dict(kp=kp,scales=scale),np.arange(len(kp)),distance))
        values=dict(keypoints=kp[idx,:2],descriptors=d[idx],scales=scale[idx],oris=ori[idx],image_size=np.array([1080,1920]))
        features[name]={k:torch.tensor(v,dtype=torch.float32,device='cuda')[None] for k,v in values.items()}
        public[name]=dict(timestamp=frame['timestamp'],xy=kp[idx,:2].tolist(),feature_ids=idx.tolist())
    report=dict(identity=identity,mask_sha256=mask_hashes,frames=public,pairs=[],status='running')
    pairs=list(itertools.combinations(public,2))
    with torch.inference_mode():
        for index,(x,y) in enumerate(pairs):
            row=dict(a=x,b=y,matches=[],scores=[])
            if len(public[x]['xy'])>=2 and len(public[y]['xy'])>=2:
                out=matcher(dict(image0=features[x],image1=features[y]));row.update(matches=out['matches'][0].cpu().numpy().tolist(),scores=out['scores'][0].cpu().numpy().tolist())
            report['pairs'].append(row)
            if (index+1)%100==0:write(a.output/'pairs.json',report);print(f'{index+1}/{len(pairs)} pairs',flush=True)
    for name,h in mask_hashes.items():
        if digest(a.masks/(name+'.png'))!=h:raise ValueError('Mask changed during matching')
    report['status']='complete-raw-matches-not-verified';write(a.output/'pairs.json',report);db.close()
    print('complete',len(pairs),'pairs',flush=True)


if __name__=='__main__':main()
