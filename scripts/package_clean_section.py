#!/usr/bin/env python3
"""Archive reviewed masks and camera models without local paths or credentials."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
from repair_scene import model_names


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('reviewed-dataset','static-dataset','native-model','frames','output'):
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();names=model_names(a.native_model/'images.bin')
    if any(Path(n).name!=n or not n.startswith('frame_') or not n.endswith('.jpg') for n in names):raise ValueError('Unexpected model image name')
    report=json.loads((a.reviewed_dataset/'mask-report.json').read_text())
    if sorted(names)!=sorted(x['image'] for x in report['images']):raise ValueError('Camera/mask inventory differs')
    times={f['name']:f['timestamp'] for f in json.loads(a.frames.read_text())}
    members={}
    for folder,source in [('native-sparse',a.native_model),('static-sparse',a.static_dataset/'sparse'),('masks',a.static_dataset/'masks')]:
        for path in sorted(source.iterdir()):
            if path.is_file() and path.suffix in ('.bin','.png'):
                members[folder+'/'+path.name]=path.read_bytes()
    members['mask-report.json']=(a.reviewed_dataset/'mask-report.json').read_bytes()
    members['review-receipt.json']=(a.reviewed_dataset/'review-receipt.json').read_bytes()
    metadata=dict(frames=[dict(name=n,timestamp=times[n]) for n in sorted(names)],
        contents_sha256={key:hashlib.sha256(value).hexdigest() for key,value in members.items()},
        note='Original imagery is not duplicated. Extract source frames and undistort with the native model; masks and final sparse model are retained for reproduction. No physical scale or scene connection is established.')
    members['metadata.json']=(json.dumps(metadata,indent=2)+'\n').encode()
    with a.output.open('xb') as file,tarfile.open(fileobj=file,mode='w:gz') as archive:
        for name,value in members.items():
            info=tarfile.TarInfo(name);info.size=len(value);info.mode=0o644;info.mtime=0
            archive.addfile(info,io.BytesIO(value))
    print(json.dumps(dict(frames=len(names),files=len(members),sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())))


if __name__=='__main__':main()
