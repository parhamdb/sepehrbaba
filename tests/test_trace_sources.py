import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trace_splat_sources import project,weights


class TraceTests(unittest.TestCase):
    def test_occlusion_not_just_ellipse_overlap(self):
        p=(np.array([0,1]),np.zeros((2,2)),np.repeat(np.eye(2)[None],2,axis=0),np.array([.9,.8]),np.ones((2,2)))
        np.testing.assert_allclose(weights(p,[[0,0]])[:,0],[.9,.08])
        np.testing.assert_array_equal(weights(p,[[100,100]]),np.zeros((2,1)))

    def test_projection_retains_original_ids_and_depth_order(self):
        m=(np.array([[0.,0.,4.],[0.,0.,-2.],[0.,0.,2.]]),np.repeat(np.eye(3)[None]*.01,3,axis=0),np.full(3,.9),np.ones((3,3)))
        v={'position':[0,0,0],'target':[0,0,1],'up':[0,1,0],'fov':60,'width':400,'height':600}
        p=project(m,v)
        self.assertEqual(p[0].tolist(),[2,0])
        np.testing.assert_allclose(p[1],[[200,300],[200,300]])
        self.assertGreater(weights(p,[[200,300]])[0,0],weights(p,[[200,300]])[1,0])


if __name__=='__main__':unittest.main()
