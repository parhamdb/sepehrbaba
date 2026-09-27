import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from check_floor_drift import world_points,plane_fit,plane_difference,unique_locations
from check_static_floor_bridge import project


class FloorTests(unittest.TestCase):
    def test_plane_fit_is_invariant_to_tiny_monocular_scale(self):
        rng=np.random.default_rng(9);pts=np.c_[rng.uniform(-2,2,1000),np.zeros(1000),rng.uniform(-2,2,1000)]
        fit=plane_fit(pts*1e-7,np.array([0,2e-7,0]),2e-9)
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit['camera_height']/1e-7,2.)

    def test_descriptor_orientations_cannot_duplicate_holdout_landmarks(self):
        a=np.array([[10.,10.],[10,10],[11,11],[30,30],[50,50],[70,70]])
        b=np.array([[20.,20.],[20,20],[21,21],[40,40],[60,60],[60,60]])
        result=unique_locations([(i,i) for i in range(len(a))],a,b)
        self.assertEqual(result,[(0,0),(3,3),(4,4)])

    def test_world_projection_roundtrip_with_rotated_camera(self):
        t=.4;R=np.array([[np.cos(t),0,np.sin(t)],[0,1,0],[-np.sin(t),0,np.cos(t)]])
        C=np.array([2,3,4]);K=np.array([[100,0,50],[0,100,80],[0,0,1.]])
        xy=np.array([[10.,20.],[50,80],[60,100]]);depth=np.array([2.,3.,4.])
        xyz=world_points(xy,depth,K,C,R)
        uv,z=project(xyz,dict(R=R.T,t=-R.T@C,K=K,dist=[0,0,0,0]))
        np.testing.assert_allclose(uv,xy);np.testing.assert_allclose(z,depth)

    def test_plane_finds_height_change_but_not_sideways_translation(self):
        rng=np.random.default_rng(0);pts=np.c_[rng.uniform(-2,2,1000),np.zeros(1000),rng.uniform(-2,2,1000)]
        ref=plane_fit(pts,np.array([0,2,0]),.02)
        moved=plane_fit(pts+[5,0,7],np.array([5,2,7]),.02)
        same=plane_difference(ref,moved)
        self.assertAlmostEqual(same['tilt_deg'],0,delta=1e-5);self.assertAlmostEqual(same['signed_offset_camera_heights'],0)
        lifted=plane_fit(pts+[0,1,0],np.array([0,3,0]),.02)
        self.assertAlmostEqual(plane_difference(ref,lifted)['signed_offset_camera_heights'],.5)

    def test_nonplanar_and_sparse_samples_remain_unsupported(self):
        rng=np.random.default_rng(2)
        self.assertIsNone(plane_fit(rng.normal(size=(100,3)),np.array([0,2,0]),.01))
        self.assertIsNone(plane_fit(rng.normal(size=(1000,3)),np.array([0,2,0]),.01))


if __name__=='__main__':unittest.main()
