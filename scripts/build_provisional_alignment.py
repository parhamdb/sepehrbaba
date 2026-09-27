#!/usr/bin/env python3
"""Make a reversible, explicitly provisional two-window depth-cloud alignment."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from align_component_matches import similarity,residual


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def arr(x):return np.asarray(x,dtype=np.float64)


def plane(points,threshold=.01):
    rng=np.random.default_rng(20260927);best=np.zeros(len(points),bool)
    for _ in range(512):
        a,b,c=points[rng.choice(len(points),3,replace=False)];n=np.cross(b-a,c-a)
        if np.linalg.norm(n)<1e-9:continue
        n/=np.linalg.norm(n);keep=np.abs((points-a)@n)<threshold
        if keep.sum()>best.sum():best=keep
    if best.sum()<3:raise ValueError('No floor plane')
    center=points[best].mean(0);_,_,vt=np.linalg.svd(points[best]-center,full_matrices=False);n=vt[-1]
    if n@(-center)<0:n=-n
    d=float(-n@center);error=np.abs(points@n+d)
    tangent=arr([1,0,0])-n*n[0];tangent/=np.linalg.norm(tangent)
    basis=np.column_stack([tangent,np.cross(n,tangent),n]);origin=-d*n
    return dict(normal=n.tolist(),offset=d,basis=basis.tolist(),origin=origin.tolist(),points=len(points),inlier_fraction=float(np.mean(error<threshold)),median_error=float(np.median(error)),threshold=threshold)


def floor_similarity(x,y,pa,pb,coincident=True,fixed_scale=None):
    A=arr(pa['basis']);B=arr(pb['basis']);oa=arr(pa['origin']);ob=arr(pb['origin'])
    xx=(x-oa)@A;yy=(y-ob)@B;mx=xx[:,:2].mean(0);my=yy[:,:2].mean(0)
    X=xx[:,:2]-mx;Y=yy[:,:2]-my;u,_,vt=np.linalg.svd(Y.T@X);D=np.diag([1,np.linalg.det(vt.T@u.T)])
    R2=vt.T@D@u.T
    scale=float((np.sum((Y@R2.T)*X)+np.sum(yy[:,2]*xx[:,2]))/(np.sum(Y*Y)+np.sum(yy[:,2]**2)))
    if not coincident:
        X3=xx-xx.mean(0);Y3=yy-yy.mean(0);R3=np.eye(3);R3[:2,:2]=R2
        scale=float(np.sum((Y3@R3.T)*X3)/np.sum(Y3*Y3))
    if fixed_scale is not None:scale=float(fixed_scale)
    if scale<=0:raise ValueError('Nonpositive floor-constrained scale: anchor heights conflict')
    Rlocal=np.eye(3);Rlocal[:2,:2]=R2;R=A@Rlocal@B.T
    vertical=0 if coincident else xx[:,2].mean()-scale*yy[:,2].mean()
    t=oa+A@np.r_[mx-scale*(R2@my),vertical]-scale*(R@ob)
    return scale,R,t


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('depth-evidence','da3','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    e=read(a.depth_evidence/'experiment.json');evaluated=read(a.depth_evidence/'evaluation.json')
    # Selected from original seed images before inspecting floor fit or alignment.
    rois={'before':[[5,1430,150,1830],[750,1770,1060,1910]],'after':[[250,1350,1000,1860]]}
    plan=dict(source='Retained user-selected six pairs and the 42 cached depth frames',floor_regions_native_xyxy=rois,cloud_stride=3,methods=['six_point_similarity','floor_constrained_similarity'],floor_plane_ransac_threshold=.01,minimum_floor_inlier_fraction=.7,units='Earlier seed median depth is one display unit; not metres',default='six_point_similarity',independent_static_correspondences=False,accepted_connection=False)
    save(a.output/'plan.json',plan)
    sides={};clouds={};planes={};landmarks={}
    dtype=np.dtype([('xyz','<f4',(3,)),('rgb','u1',(3,)),('tag','u1')]);assert dtype.itemsize==16
    for side,info in e['sides'].items():
        source_fit=evaluated['fits'][side+'_to_'+('after' if side=='before' else 'before')]['variants']['cached_lens']
        unit=source_fit['arbitrary_depth_unit'];seed=info['frames'][info['seed_index']];R0=arr(seed['camera_to_world_rotation']);C0=arr(seed['center'])
        landmarks[side]=arr(source_fit['source_points_3d']);parts=[];frame_info=[]
        for index,frame in enumerate(info['frames']):
            cache=a.da3/'results_output'/frame['depth_file']
            if sha(cache)!=frame['depth_sha256']:raise ValueError('Depth cache changed')
            with np.load(cache) as d:
                h,w=d['depth'].shape;vv,uu=np.mgrid[0:h:3,0:w:3];z=d['depth'][vv,uu];pixel=np.stack([uu,vv,np.ones_like(uu)],axis=-1).reshape(-1,3)
                good=np.isfinite(z.ravel())&(z.ravel()>0);pixel=pixel[good];z=z.ravel()[good]
                X=(pixel@np.linalg.inv(d['intrinsics']).T)*z[:,None]
                Ri=arr(frame['camera_to_world_rotation']);Ci=arr(frame['center']);local=((X@Ri.T+Ci-C0)@R0)/unit
                colors=d['image'][vv,uu].reshape(-1,3)[good];native=pixel[:,:2]*[1080/w,1920/h]
                onfloor=np.zeros(len(local),bool)
                if index==info['seed_index']:
                    for x0,y0,x1,y1 in rois[side]:onfloor|=(native[:,0]>=x0)&(native[:,0]<x1)&(native[:,1]>=y0)&(native[:,1]<y1)
                    planes[side]=plane(local[onfloor]);planes[side]['camera_unit']=unit
                part=np.empty(len(local),dtype=dtype);part['xyz']=local;part['rgb']=colors;part['tag']=index+128*onfloor.astype(np.uint8);parts.append(part)
                frame_info.append(dict(name=frame['name'],timestamp=frame['timestamp'],slot=index,points=len(local),depth_sha256=frame['depth_sha256'],image_sha256=frame['image_sha256']))
        packed=np.concatenate(parts);packed.tofile(a.output/f'{side}.bin');clouds[side]=packed
        sides[side]=dict(asset=f'{side}.bin',sha256=sha(a.output/f'{side}.bin'),count=len(packed),seed_slot=info['seed_index'],frames=frame_info,median_depth_unit=unit)
    x=landmarks['before'];y=landmarks['after'];candidates={}
    transforms={'six_point_similarity':similarity(y,x)}
    floor_blocked=None
    if all(p['inlier_fraction']>=plan['minimum_floor_inlier_fraction'] for p in planes.values()):
        try:transforms['floor_constrained_similarity']=floor_similarity(x,y,planes['before'],planes['after'])
        except ValueError as error:floor_blocked=str(error)
        transforms['floor_direction_similarity']=floor_similarity(x,y,planes['before'],planes['after'],coincident=False,fixed_scale=transforms['six_point_similarity'][0])
    else:floor_blocked='Floor plane support below frozen limit'
    save(a.output/'floor-check.json',dict(planes=planes,coincident_floor_blocked=floor_blocked,followup='Parallel floor directions with scale fixed to six-point similarity; normal offset remains free and visible',reason='Free-scale parallel-floor fit collapsed to 0.01648 because vertical anchor covariance is negative; retain landmark-derived scale instead of shrinking the scene'))
    # Both baselines are provisional. Floor-constrained residual is not independent floor validation.
    for name,(scale,R,t) in transforms.items():
        q=scale*y@R.T+t;nb=R@arr(planes['after']['normal']);na=arr(planes['before']['normal']);angle=np.degrees(np.arccos(np.clip(nb@na,-1,1)))
        origin=scale*(R@arr(planes['after']['origin']))+t
        floor_offset=float(na@origin+planes['before']['offset'])
        candidates[name]=dict(scale_source='six-point similarity; fixed during floor-direction refinement',scale=float(scale),rotation=R.tolist(),translation=t.tolist(),transformed_after_landmarks=q.tolist(),landmark_residuals=residual(y,x,(scale,R,t)).tolist(),floor_normal_angle_degrees=float(angle),floor_plane_offset=floor_offset,floor_used_in_fit=name!='six_point_similarity',accepted_connection=False)
    # Existing DA3 camera relationship, solely for a reversible comparison toggle.
    ba=e['sides']['before']['frames'][10];aa=e['sides']['after']['frames'][10]
    A=arr(ba['camera_to_world_rotation']);B=arr(aa['camera_to_world_rotation']);unitA=sides['before']['median_depth_unit'];unitB=sides['after']['median_depth_unit']
    prior=dict(scale=unitB/unitA,rotation=(A.T@B).tolist(),translation=((arr(aa['center'])-arr(ba['center']))@A/unitA).tolist())
    # Level only the display using the before floor. Positive Y is height above that floor.
    basis=arr(planes['before']['basis']);display_R=np.array([[1,0,0],[0,0,1],[0,-1,0]])@basis.T;display_t=-display_R@arr(planes['before']['origin'])
    result=dict(schema=1,coincident_floor_blocked=floor_blocked,status='provisional human-anchored local alignment; no verified join',sides=sides,landmarks={k:v.tolist() for k,v in landmarks.items()},floor_planes=planes,candidates=candidates,cached_camera_relationship=prior,display_transform=dict(rotation=display_R.tolist(),translation=display_t.tolist()),identity=dict(script_sha256=sha(Path(__file__)),depth_experiment_sha256=sha(a.depth_evidence/'experiment.json'),depth_evaluation_sha256=sha(a.depth_evidence/'evaluation.json')),plan=plan,accepted_connection=False,limitations=['Only two approximately one-second windows; no full-recording scene merge.','Depth clouds are model estimates. No surfaces have been generated to fill holes.','People, flexible material and occlusion can produce ghosting in the multi-frame display.','Floor regions are manually selected surface hypotheses; a shared plane cannot establish horizontal position or yaw.','Anchor residuals and constrained floor coincidence are fitting results, not independent accuracy estimates.'])
    save(a.output/'alignment.json',result)
    print(json.dumps(dict(clouds={s:v['count'] for s,v in sides.items()},floor={s:{k:v[k] for k in ['inlier_fraction','median_error']} for s,v in planes.items()},candidates={k:{x:v[x] for x in ['scale','floor_normal_angle_degrees','floor_plane_offset','landmark_residuals']} for k,v in candidates.items()})))

if __name__=='__main__':main()
