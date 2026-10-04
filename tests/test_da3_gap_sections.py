import importlib.util
from pathlib import Path
import sys,tempfile,unittest,struct
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from train_da3_gap_sections import plan_windows,normalize_camera,write_model

class GapTests(unittest.TestCase):
    def test_plan_covers_every_missing_frame_and_empty(self):
        frames=[{'name':f'f{i:03d}.jpg','timestamp':i*.1} for i in range(300)]
        catalog={'duration':30.,'sections':[{'frame_names':[f['name'] for f in frames[50:100]]}]}
        plan=plan_windows(frames,catalog);selected={i for r in plan for i in r['indices']}
        self.assertTrue((set(range(300))-set(range(50,100)))<=selected)
        self.assertTrue(all(r['end']-r['start']<=10 for r in plan))
        catalog['sections']=[{'frame_names':[f['name'] for f in frames]}]
        self.assertEqual(plan_windows(frames,catalog),[])
    def test_local_camera_projection_preserved(self):
        from scipy.spatial.transform import Rotation
        R=Rotation.from_euler('xyz',[.2,-.3,.8]).as_matrix();O=Rotation.from_euler('xyz',[-.4,.1,.7]).as_matrix()
        C=np.array([10.,20.,30.]);origin=np.array([11.,19.,30.]);scale=.003
        row={'center':C.tolist(),'camera_to_world_rotation':R.tolist()}
        c,r=normalize_camera(row,origin,O,scale);camera=np.array([.3,.7,4.]);world=R@camera+C
        local=O.T@(world-origin)/scale;recovered=r.T@(local-c)
        np.testing.assert_allclose(recovered/recovered[2],camera/camera[2],atol=1e-10)
    def test_binary_export_keeps_camera_pose_and_empty_point_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);K=np.array([[100.,0,54],[0,110.,96],[0,0,1.]])
            write_model(root,[{'name':'frame.jpg'}],[(K,np.array([1.,2.,3.]),np.eye(3))],np.array([[0.,0.,5.]]),np.array([[12,34,56]]))
            b=(root/'sparse/images.bin').read_bytes();self.assertEqual(struct.unpack_from('<Q',b)[0],1)
            row=struct.unpack_from('<i4d3di',b,8);np.testing.assert_allclose(row[5:8],[-1,-2,-3]);self.assertEqual(row[8],1)
            p=(root/'sparse/points3D.bin').read_bytes();self.assertEqual(struct.unpack_from('<Q',p,len(p)-8)[0],0)
if __name__=='__main__':unittest.main()
