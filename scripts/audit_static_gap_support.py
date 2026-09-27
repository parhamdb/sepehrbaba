#!/usr/bin/env python3
"""Count selected static features and mapped support without changing reconstructions."""
import argparse,collections,importlib.util,json,sqlite3
from pathlib import Path
import cv2,numpy as np
from probe_gap_recovery import mask_indices,digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('selection','state','database','reader','masks','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();s=json.loads(a.selection.read_text());state=json.loads(a.state.read_text());db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True)
    spec=importlib.util.spec_from_file_location('reader',a.reader);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    ids=dict(db.execute('select name,image_id from images'));features={};rows={}
    for sample in s['samples']:
        name=sample['name'];nr,nc,data=db.execute('select rows,cols,data from keypoints where image_id=?',(ids[name],)).fetchone();kp=np.frombuffer(data,np.float32).reshape(nr,nc)
        scales=(np.hypot(kp[:,2],kp[:,4])+np.hypot(kp[:,3],kp[:,5]))/2 if nc==6 else kp[:,2]
        mask=cv2.imread(str(a.masks/(name+'.png')),cv2.IMREAD_GRAYSCALE)
        distance=cv2.distanceTransform(np.pad((mask>0).astype(np.uint8),1),cv2.DIST_L2,5)[1:-1,1:-1]
        f=dict(kp=kp,scales=scales);keep=mask_indices(f,np.arange(nr),distance);features[name]=(kp,keep)
        xy=kp[:,:2].astype(int);inside=(xy[:,0]>=0)&(xy[:,0]<1080)&(xy[:,1]>=0)&(xy[:,1]<1920);centers=xy[inside]
        rows[name]=dict(timestamp=sample['timestamp'],all_features=nr,static_center_features=int((mask[centers[:,1],centers[:,0]]>0).sum()),static_support_features=len(keep))
    maps=[]
    for gid,case in s['cases'].items():
        for direction,cfg in case['directions'].items():
            cid=cfg['component'];root=Path(next(c['path'] for c in state['components'] if c['id']==cid));images=reader.read_images_binary(root/'images.bin');points=reader.read_points3D_binary(root/'points3D.bin');counts=collections.Counter();anchors=[]
            for name in cfg['anchors']:
                im=images[ids[name]];kp,keep=features[name]
                if len(im.point3D_ids)!=len(kp) or np.max(np.abs(im.xys-kp[:,:2]),initial=0)>.01:raise ValueError('Feature indexing mismatch')
                all_good={int(pid) for pid in im.point3D_ids if pid>=0 and points[pid].error<=2.5 and len(points[pid].image_ids)>=3}
                static_good={int(im.point3D_ids[i]) for i in keep if int(im.point3D_ids[i]) in all_good};counts.update(static_good)
                anchors.append(dict(name=name,quality_landmarks=len(all_good),static_landmarks=len(static_good)))
            maps.append(dict(gap=gid,direction=direction,component=cid,anchors=anchors,static_landmarks_union=len(counts),static_landmarks_in_two_anchors=sum(v>=2 for v in counts.values())))
    report=dict(selection_sha256=digest(a.selection),script_sha256=digest(Path(__file__)),features=rows,maps=maps,
        limitation='Counts measure available descriptors and provisional 3D tracks, not certified static points. Query-specific exclusion of its own observation may further reduce eligible tracks.')
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    for row in maps:print(row['gap'],row['direction'],row['static_landmarks_union'],row['static_landmarks_in_two_anchors'])
    db.close()


if __name__=='__main__':main()
