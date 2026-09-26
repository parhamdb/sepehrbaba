#!/usr/bin/env python3
"""Full-recording DA3 with verified chunk reuse, source timing and runtime status.

Keeps the upstream camera estimator and loop optimizer unchanged. Intermediate
predictions remain private checkpoints. Public poses and progress omit paths.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def save(path,data):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');temp.replace(path)


def validate_frames(frames,names):
    if not frames or [f['name'] for f in frames]!=sorted(names):raise ValueError('Frame/image order mismatch')
    if len(names)!=len(set(names)):raise ValueError('Duplicate image name')
    ts=[f['timestamp'] for f in frames]
    if not all(np.isfinite(ts)) or any(b<=a for a,b in zip(ts,ts[1:])):raise ValueError('Invalid source timestamps')


def export_poses(frames,matrices,intrinsics,source_size,processed_size):
    if len(frames)!=len(matrices) or len(frames)!=len(intrinsics):raise ValueError('Incomplete pose export')
    rows=[]
    native=np.diag([source_size[0]/processed_size[0],source_size[1]/processed_size[1],1.])
    for frame,C,cal in zip(frames,matrices,intrinsics):
        R=C[:3,:3];fx,fy,cx,cy=cal
        if not np.isfinite(C).all() or not np.isfinite(cal).all() or min(fx,fy)<=0:raise ValueError('Nonfinite camera or invalid focal length')
        if not np.allclose(C[3],[0,0,0,1],atol=1e-5) or not np.allclose(R.T@R,np.eye(3),atol=1e-4) or np.linalg.det(R)<0:raise ValueError('Invalid camera matrix')
        K=native@np.array([[fx,0,cx],[0,fy,cy],[0,0,1.]])
        rows.append(dict(**frame,center=C[:3,3].tolist(),camera_to_world_rotation=R.tolist(),intrinsics_native=K.tolist()))
    return rows


def cached_prediction(path,receipt,identity):
    if not path.exists() or not receipt.exists():return False
    data=json.loads(receipt.read_text())
    return data.get('identity')==identity and data.get('sha256')==digest(path)


def image_manifest(images,names):
    rows=[dict(name=name,sha256=digest(images/name)) for name in sorted(names)]
    identity=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
    return rows,identity


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('checkout','weights','salad','images','frames','video','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--resume',action='store_true');p.add_argument('--min-free-gib',type=float,default=24.)
    p.add_argument('--expected-video-sha256',required=True);p.add_argument('--expected-frame-count',type=int,default=12793)
    a=p.parse_args();frames=json.loads(a.frames.read_text());names=[x.name for pattern in ('*.jpg','*.png') for x in a.images.glob(pattern)]
    validate_frames(frames,names)
    if len(frames)!=a.expected_frame_count:raise ValueError('Unexpected full-recording frame count')
    if a.output.exists() and not a.resume:raise FileExistsError(a.output)
    a.output.mkdir(parents=True,exist_ok=True)
    lock=(a.output/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    import yaml
    streaming=a.checkout/'da3_streaming';sys.path.insert(0,str(streaming))
    config=yaml.safe_load((streaming/'configs/base_config.yaml').read_text())
    config['Weights']={'DA3':str(a.weights/'model.safetensors'),'DA3_CONFIG':str(a.weights/'config.json'),'SALAD':str(a.salad)}
    config['Model'].update(chunk_size=32,overlap=16,loop_chunk_size=8,align_lib='torch',delete_temp_files=False)
    config['Loop']['SIM3_Optimizer']['lang_version']='python';config['Loop']['SALAD']['batch_size']=8
    settings={k:v for k,v in config.items() if k!='Weights'}
    state=dict(status='preflight',total_frames=len(frames),sequential_chunks_done=0,total_chunks=(len(frames)-16+15)//16,
               covered_source_frames=0,completed=False,started=time.time(),last_update=time.time())
    save(a.output/'progress.json',state)
    try:
        image_rows,image_identity=image_manifest(a.images,names)
        freeze=dict(image_manifest_sha256=image_identity,source_sha256=digest(a.video),frames_sha256=digest(a.frames),adapter_sha256=digest(__file__),
            upstream_revision=subprocess.check_output(['git','-C',str(a.checkout),'rev-parse','HEAD'],text=True).strip(),
            upstream_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(a.checkout),'diff'])).hexdigest(),
            weights_sha256=digest(a.weights/'model.safetensors'),model_config_sha256=digest(a.weights/'config.json'),
            salad_sha256=digest(a.salad),settings=settings)
        if freeze['source_sha256']!=a.expected_video_sha256:raise ValueError('Wrong source recording')
        identity=hashlib.sha256(json.dumps(freeze,sort_keys=True).encode()).hexdigest()
        frozen=a.output/'inputs.json'
        if frozen.exists() and json.loads(frozen.read_text())!=freeze:raise ValueError('Resume source/config changed')
        save(frozen,freeze)
        save(a.output/'image-hashes.json',image_rows)
        (a.output/'runtime-config.yaml').write_text(yaml.safe_dump(config))
    except Exception as error:
        state.update(status='failed',failure_type=type(error).__name__,last_update=time.time())
        save(a.output/'progress.json',state)
        raise
    import torch
    torch.set_num_threads(4);torch.manual_seed(42);np.random.seed(42)
    from da3_streaming import DA3_Streaming
    def progress(**kw):
        state.update(**kw,last_update=time.time(),free_gib=shutil.disk_usage(a.output).free/1024**3)
        save(a.output/'progress.json',state)
    def guard():
        if shutil.disk_usage(a.output).free<a.min_free_gib*1024**3:raise RuntimeError('Free disk below configured reserve; checkpoints retained')
    class CheckedStreaming(DA3_Streaming):
        def process_single_chunk(self,range_1,chunk_idx=None,range_2=None,is_loop=False):
            guard()
            filename=f'loop_{range_1[0]}_{range_1[1]}_{range_2[0]}_{range_2[1]}.npy' if is_loop else f'chunk_{chunk_idx}.npy'
            path=Path(self.result_loop_dir if is_loop else self.result_unaligned_dir)/filename
            receipt=path.with_suffix('.receipt.json')
            count=range_1[1]-range_1[0]+(range_2[1]-range_2[0] if range_2 else 0)
            reused=cached_prediction(path,receipt,identity)
            if reused:
                prediction=np.load(path,allow_pickle=True).item()
                if not is_loop and range_2 is None:
                    self.all_camera_poses.append((self.chunk_indices[chunk_idx],prediction.extrinsics))
                    self.all_camera_intrinsics.append((self.chunk_indices[chunk_idx],prediction.intrinsics))
            else:
                prediction=super().process_single_chunk(range_1,chunk_idx,range_2,is_loop)
            if prediction.extrinsics.shape!=(count,3,4) or prediction.intrinsics.shape!=(count,3,3):raise ValueError('Chunk camera shape mismatch')
            if not np.isfinite(prediction.extrinsics).all() or not np.isfinite(prediction.intrinsics).all():raise ValueError('Invalid chunk cameras')
            shape=list(prediction.processed_images.shape[1:3][::-1])
            if shape!=[280,504]:raise ValueError('Unexpected preprocessing shape; native calibration mapping requires review')
            if not reused:save(receipt,dict(identity=identity,sha256=digest(path),frames=count,processed_size=shape))
            if is_loop:progress(status='loop-inference',loop_chunks_done=state.get('loop_chunks_done',0)+1)
            else:progress(status='sequential-inference',sequential_chunks_done=chunk_idx+1,covered_source_frames=range_1[1],last_chunk_reused=reused)
            return prediction
        def get_loop_pairs(self):
            guard();progress(status='loop-retrieval')
            pairs=super().get_loop_pairs();progress(status='loop-inference',loop_candidate_pairs=len(pairs));return pairs
        def get_loop_sim3_from_loop_predict(self,values):
            progress(status='loop-alignment');return super().get_loop_sim3_from_loop_predict(values)
        def plot_loop_closure(self,*args,**kwargs):
            result=super().plot_loop_closure(*args,**kwargs);progress(status='geometry-export');return result
        def save_depth_conf_result(self,*args,**kwargs):
            guard();return super().save_depth_conf_result(*args,**kwargs)
        def save_camera_poses(self):
            progress(status='camera-export');return super().save_camera_poses()
    try:
        guard();progress(status='loading-models');runner=CheckedStreaming(str(a.images),str(a.output),config)
        runner.run()
        matrices=np.loadtxt(a.output/'camera_poses.txt').reshape(-1,4,4)
        intrinsics=np.loadtxt(a.output/'intrinsic.txt').reshape(-1,4)
        rows=export_poses(frames,matrices,intrinsics,[1080,1920],[280,504])
        save(a.output/'poses.json',dict(method='DA3-Streaming full recording',status='candidate trajectory; independent recovery unverified',
            input_frames=len(frames),estimated_frames=len(rows),settings=settings,source_sha256=freeze['source_sha256'],frames=rows))
        progress(status='poses-complete',completed=True,estimated_frames=len(rows),elapsed_seconds=time.time()-state['started'])
    except Exception as error:
        progress(status='failed',failure_type=type(error).__name__)
        raise


if __name__=='__main__':main()
