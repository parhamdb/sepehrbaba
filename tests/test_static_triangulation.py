import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from triangulate_static_gap import assemble_tracks,independent_features
from check_static_floor_bridge import triangulate,project


class StaticTriangulationTests(unittest.TestCase):
    def test_track_cannot_include_conflicting_features_in_one_image(self):
        edges=[dict(a=('a',0),b=('b',0),angle=4),dict(a=('b',0),b=('c',0),angle=3),dict(a=('a',1),b=('c',0),angle=2)]
        tracks=assemble_tracks(edges)
        self.assertEqual(tracks,[{('a',0),('b',0),('c',0)}])

    def test_close_oriented_features_do_not_create_independent_landmarks(self):
        xy=np.array([[10,10],[10.1,10.1],[20,20]],float)
        self.assertEqual(independent_features(xy,np.arange(3)).tolist(),[0,2])

    def test_triangulates_known_geometry_and_rejects_zero_parallax(self):
        K=np.array([[900.,0,540],[0,900,960],[0,0,1.]])
        a=dict(R=np.eye(3),t=np.zeros(3),center=np.zeros(3),K=K,dist=np.zeros(4))
        b=dict(a,t=np.array([-1.,0,0]),center=np.array([1.,0,0]))
        xyz=np.array([[0.,0,5],[1,1,6],[-1,-1,7]])
        x,_=project(xyz,a);y,_=project(xyz,b)
        points,keep,_=triangulate(x,y,a,b)
        self.assertTrue(keep.all());np.testing.assert_allclose(points,xyz,atol=1e-6)
        _,keep,_=triangulate(x,x,a,a);self.assertFalse(keep.any())

if __name__=='__main__':unittest.main()
