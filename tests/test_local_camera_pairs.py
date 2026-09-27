import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from evaluate_local_camera_pairs import screen_pair,camera_errors


class LocalCameraTests(unittest.TestCase):
    def test_homography_holdout_accepts_plane_but_not_physical_pose(self):
        rng=np.random.default_rng(8);x=rng.uniform([150,250],[850,1550],(100,2));y=x+[30,20];K=np.array([[1500.,0,540],[0,1500,960],[0,0,1]])
        r=screen_pair(x,y,np.arange(100),K,np.zeros(4))
        self.assertTrue(r['homography_passed']);self.assertTrue(r['planar_explanation_supported']);self.assertFalse(r['pose_accepted'])

    def test_shuffled_withheld_correspondences_are_rejected(self):
        rng=np.random.default_rng(8);x=rng.uniform([150,250],[850,1550],(100,2));y=x+[30,20];y[::5]=y[::5][::-1];K=np.array([[1500.,0,540],[0,1500,960],[0,0,1]])
        r=screen_pair(x,y,np.arange(100),K,np.zeros(4));self.assertFalse(r['homography_passed']);self.assertFalse(r['relative_pose_screen_passed'])

    def test_calibrated_relative_pose_on_nonplanar_points(self):
        rng=np.random.default_rng(4);xyz=rng.uniform([-1.5,-2,4],[1.5,2,8],(150,3));K=np.array([[1200.,0,540],[0,1200,960],[0,0,1]])
        def project(p):
            h=p@K.T;return h[:,:2]/h[:,2,None]
        x=project(xyz);y=project(xyz+[.5,.1,.03]);r=screen_pair(x,y,np.arange(150),K,np.zeros(4))
        self.assertTrue(r['relative_pose_screen_passed']);self.assertFalse(r['pose_accepted']);self.assertLess(r['pose_withheld']['median_px'],.01)

    def test_existing_camera_error_is_invariant_to_tiny_world_scale(self):
        K=np.array([[1200.,0,540],[0,1200,960],[0,0,1]]);a=dict(R=np.eye(3),t=np.zeros(3),K=K,dist=np.zeros(4),component='a');b=dict(a,t=np.array([1.,.1,0]))
        x=np.array([[300.,500],[500,900],[700,1100]]);y=x+np.array([100.,10])
        first=camera_errors(a,b,x,y);second=camera_errors(a,dict(b,t=np.asarray(b['t'])*1e-15),x,y)
        self.assertAlmostEqual(first['median_px'],second['median_px']);self.assertEqual(second['status'],'evaluated')

if __name__=='__main__':unittest.main()
