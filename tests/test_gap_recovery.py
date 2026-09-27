import sys,unittest,tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from inventory_camera_gaps import inventory
from probe_gap_recovery import localize,select_anchors,unique_correspondences,verify_models,digest


class RecoveryTests(unittest.TestCase):
    def test_inventory_preserves_edge_gaps_and_component_boundaries(self):
        f=[dict(name=str(i),timestamp=float(i)) for i in range(7)]
        s=dict(components=[dict(id='a',names=['1','2']),dict(id='b',names=['4','5'])])
        r=inventory(s,f)
        self.assertEqual(r['missing_frames'],3)
        self.assertEqual(len(r['gaps']),3)
        self.assertIsNone(r['gaps'][0]['before']);self.assertIsNone(r['gaps'][-1]['after'])
        self.assertEqual(len(r['unsupported_adjacent_transitions']),1)

    def test_search_uses_seconds_in_both_directions(self):
        t={str(i):float(i) for i in [0,5,9,11,20,29,31,39,45,49,51,60,69,71]}
        c=dict(names=list(t))
        self.assertEqual(set(select_anchors(c,t,40,-1)),{'11','29','31','39'})
        self.assertEqual(set(select_anchors(c,t,40,1)),{'45','49','51','69'})

    def test_duplicate_orientations_and_landmarks_do_not_inflate_support(self):
        rows=[dict(id=1,xy=[0,0],score=1),dict(id=2,xy=[1,1],score=.9),dict(id=1,xy=[40,40],score=.8)]
        self.assertEqual(len(unique_correspondences(rows)),1)

    def test_pnp_recovers_known_pose_and_rejects_shuffled_holdout(self):
        rng=np.random.default_rng(12);xyz=rng.uniform([-3,-4,5],[3,4,9],(150,3));K=np.array([[900.,0,540],[0,900,960],[0,0,1]])
        xy=(xyz@K.T);xy=xy[:,:2]/xy[:,2,None]
        rows=[dict(id=i,xyz=p.tolist(),xy=q.tolist(),score=1.) for i,(p,q) in enumerate(zip(xyz,xy))]
        result=localize(rows,K,np.zeros(4));self.assertTrue(result['passed']);self.assertLess(result['withheld_median_px'],.01)
        for row in rows:
            if row['id']%5==0:row['xy']=[1000-row['xy'][0],1800-row['xy'][1]]
        self.assertFalse(localize(rows,K,np.zeros(4))['passed'])

    def test_resume_rejects_changed_model(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'images.bin';path.write_bytes(b'baseline')
            report=dict(gaps=[dict(model_sha256={'a':{'images.bin':digest(path)}})])
            components=[dict(id='a',path=temp)]
            verify_models(report,components)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):verify_models(report,components)

    def test_tiny_world_scale_does_not_change_pnp(self):
        rng=np.random.default_rng(3);xyz=rng.uniform([-3,-4,5],[3,4,9],(150,3));K=np.array([[900.,0,540],[0,900,960],[0,0,1]])
        uv=xyz@K.T;uv=uv[:,:2]/uv[:,2,None]
        rows=[dict(id=i,xyz=(p*1e-7).tolist(),xy=q.tolist(),score=1.) for i,(p,q) in enumerate(zip(xyz,uv))]
        self.assertTrue(localize(rows,K,np.zeros(4))['passed'])

if __name__=='__main__':unittest.main()
