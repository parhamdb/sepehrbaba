import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec=importlib.util.spec_from_file_location('compare',Path(__file__).parents[1]/'scripts/compare_camera_tracks.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def pose(center,R=None):
    R=np.eye(3) if R is None else R;center=np.array(center,float)
    return dict(center=center.tolist(),R=R.tolist(),t=(-R@center).tolist(),K=[[800.,0,540],[0,800.,960],[0,0,1]],dist=[.03,0.,0.,0.],component='one')


class CameraComparisonTests(unittest.TestCase):
    def test_pre_loss_gauge_fit_predicts_withheld_position(self):
        theta=.4;Q=np.array([[np.cos(theta),0,np.sin(theta)],[0,1,0],[-np.sin(theta),0,np.cos(theta)]])
        centers=np.array([[0,0,0],[1,0,0],[2,.1,0],[2,1,0],[3,2,.1],[4,2,.2]],float)
        src=[pose(c) for c in centers];target=[pose(2.3*Q@c+[5,3,-2],Q.T) for c in centers]
        fit=m.align_cameras(src[:5],target[:5])
        np.testing.assert_allclose(m.aligned_center(src[5],fit),target[5]['center'],atol=1e-10)
        self.assertAlmostEqual(fit['scale'],2.3)

    def test_epipolar_static_points_with_radial_distortion(self):
        import cv2
        a,b=pose([0,0,0]),pose([.2,.1,0])
        X=np.array([[.1,.2,3],[.5,-.3,4],[-.2,.1,2],[.7,.4,5]],float)
        pixels=[]
        for p in [a,b]:
            q,_=cv2.projectPoints(X,np.zeros(3),np.array(p['t']),np.array(p['K']),np.array(p['dist']))
            pixels.append(q.reshape(-1,2))
        error,_=m.epipolar(a,b,*pixels)
        self.assertLess(max(error),1e-6)
        wrong=pose([0,.2,0]);bad,_=m.epipolar(a,wrong,*pixels)
        self.assertGreater(np.median(bad),10)

    def test_component_changes_and_long_gaps_are_not_joined(self):
        fs=[dict(name=str(i),timestamp=t) for i,t in enumerate([0,.1,.2,2.])]
        ps={str(i):pose([i,0,0]) for i in range(4)};ps['2']['component']='two';ps['3']['component']='two'
        case=dict(frames=fs,methods=dict(colmap=ps,da3=ps))
        self.assertEqual([(a['name'],b['name']) for a,b in m.pair_schedule(case,['colmap','da3'])],[('0','1')])

    def test_zero_distortion_skew_camera_preserves_observations(self):
        a,b=pose([0,0,0]),pose([.2,.1,0])
        X=np.array([[.1,.2,3],[.5,-.3,4],[-.2,.1,2],[.7,.4,5]],float)
        pixels=[]
        for p in [a,b]:
            p['K']=[[800.,200.,540],[0,900.,960],[0,0,1.]];p['dist']=[0.,0.,0.,0.]
            h=(X+np.array(p['t']))@np.array(p['K']).T;pixels.append(h[:,:2]/h[:,2:])
        error,foot=m.epipolar(a,b,*pixels)
        self.assertLess(max(error),1e-9)
        np.testing.assert_allclose(foot,pixels[1],atol=1e-9)

    def test_zero_translation_cannot_score_epipolar_constraint(self):
        p=pose([0,0,0]);self.assertIsNone(m.essential(p,p))

    def test_sparse_or_asymmetric_pairs_are_not_ranked(self):
        rows=[dict(corners=3,metrics={k:dict(median_px=1,under_4px_fraction=1) for k in ['colmap','da3']}),
              dict(corners=25,metrics={'colmap':dict(median_px=2),'da3':dict(median_px=None)})]
        self.assertEqual(m.summarize(rows,['colmap','da3'])['supported_pairs'],0)

    def test_post_gap_methods_use_identical_frames(self):
        poses={str(i):pose([i,0,0]) for i in range(3)}
        case=dict(gap_end=0,frames=[dict(name=str(i),timestamp=i) for i in range(3)],
                  methods=dict(colmap=poses,da3=poses,vggt={'1':poses['1']}))
        fit=dict(rotation=np.eye(3),scale=1,offset=[0,0,0],reference_span=1)
        result=m.post_gap_agreement(case,dict(vggt=fit,da3=fit),'one')
        self.assertEqual(result['da3']['frame_names'],['1'])
        self.assertEqual(result['vggt']['frame_names'],['1'])


if __name__=='__main__':unittest.main()
