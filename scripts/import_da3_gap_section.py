#!/usr/bin/env python3
"""Append one completed DA3 section to a LAN library without changing old IDs.

A caller supplies the frame inventory and copied experiment folder. This imports
an explicitly experimental candidate, not a visually accepted reconstruction.
"""
import argparse,fcntl,hashlib,json,shutil
from pathlib import Path
from PIL import Image
from video_to_splat import validate_splat


def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['library','section','frames']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();lock=(a.library/'.import.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    catalog_path=a.library/'catalog.json';catalog=json.loads(catalog_path.read_text());identity=a.section.name
    if not identity.startswith('da3-gap-') or not identity.replace('-','').isalnum():raise ValueError('Unexpected section ID')
    prep=json.loads((a.section/'preparation.json').read_text());evaluation=json.loads((a.section/'evaluation.json').read_text())
    ply=a.section/'splats/scene.ply';validate_splat(ply);sha=digest(ply)
    found=next((s for s in catalog['sections'] if s['id']==identity),None)
    if found:
        if found['sha256']!=sha:raise ValueError('Existing section ID has different asset bytes')
        if digest(a.library/'assets'/found['asset'])!=sha:raise ValueError('Imported asset changed')
        print('Already imported',identity);return
    frames=json.loads(a.frames.read_text());times={f['name']:f['timestamp'] for f in frames};inputs=prep['frame_inputs']
    if any(f['name'] not in times or abs(f['timestamp']-times[f['name']])>1e-6 for f in inputs):raise ValueError('Source frame association differs')
    if len(frames)!=catalog['source_frames']:raise ValueError('Wrong source inventory')
    if evaluation['held_out_views']!=sum(f['split']=='held-out' for f in inputs):raise ValueError('Incomplete evaluation')
    with ply.open('rb') as stream:
        count=None
        while True:
            line=stream.readline()
            if line.startswith(b'element vertex '):count=int(line.split()[2])
            if line.strip()==b'end_header':break
    shutil.copyfile(ply,a.library/'assets'/(identity+'.ply'))
    if digest(a.library/'assets'/(identity+'.ply'))!=sha:raise ValueError('Asset copy mismatch')
    renders=sorted((a.section/'splats').glob('eval_*/*.png'));render=renders[len(renders)//2]
    with Image.open(render) as im:
        im.thumbnail((270,480));im.convert('RGB').save(a.library/'previews'/(identity+'.jpg'),quality=85)
    entry={'id':identity,'number':len(catalog['sections'])+1,'camera_method':'DA3','start':inputs[0]['timestamp'],'end':inputs[-1]['timestamp'],
        'registered_frames':len(inputs),'frame_names':[f['name'] for f in inputs],'asset':identity+'.ply','preview':identity+'.jpg','preview_frame':render.stem,
        'bytes':ply.stat().st_size,'sha256':sha,'gaussians':count,'placement':prep['placement'],
        'original_status':'experimental-da3-awaiting-review','mask_method':prep['mask_method'],
        'quality':'Experimental DA3 cameras and depth; unverified geometry. Local normalization does not fix drift.',
        'evaluation':evaluation,'preparation_sha256':digest(a.section/'preparation.json')}
    catalog['sections'].append(entry)
    covered=set().union(*(set(s['frame_names']) for s in catalog['sections']))
    catalog['trained_frames']=len(covered)
    catalog['coverage_bins']=[{'start':start,'end':min(start+10,catalog['duration']),
        'source_frames':sum(start<=f['timestamp']<start+10 for f in frames),
        'trained_frames':sum(start<=f['timestamp']<start+10 and f['name'] in covered for f in frames)} for start in range(0,int(catalog['duration'])+1,10)]
    missing=[]
    for i,f in enumerate(frames):
        if f['name'] in covered:continue
        end=frames[i+1]['timestamp'] if i+1<len(frames) else catalog['duration']
        if missing and missing[-1]['end']==f['timestamp']:missing[-1].update(end=end,frames=missing[-1]['frames']+1)
        else:missing.append({'start':f['timestamp'],'end':end,'frames':1})
    catalog['missing_intervals']=missing
    catalog['warning']='COLMAP and experimental DA3 splats; frame representation is not camera accuracy or recovered surfaces. See each section method and masks.'
    backup=catalog_path.with_name(f'catalog-before-{identity}.json')
    if not backup.exists():shutil.copyfile(catalog_path,backup)
    temp=catalog_path.with_suffix('.tmp');temp.write_text(json.dumps(catalog,indent=2)+'\n');temp.replace(catalog_path)
    print(json.dumps({'imported':identity,'number':entry['number'],'frames_represented':len(covered)}))


if __name__=='__main__':main()
