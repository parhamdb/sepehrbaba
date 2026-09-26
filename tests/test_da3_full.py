import sys,tempfile,json
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import run_da3_full as run
import compare_da3_full as compare


def pose(c):
    return dict(center=[c,0,0],R=np.eye(3).tolist(),t=[-c,0,0],K=np.eye(3).tolist(),dist=[0,0,0,0],component='test')


class FullDA3Tests(unittest.TestCase):
    def test_frame_inventory_requires_original_order_and_timing(self):
        f=[dict(name='a.jpg',timestamp=0),dict(name='b.jpg',timestamp=.1)]
        run.validate_frames(f,['b.jpg','a.jpg'])
        with self.assertRaises(ValueError):run.validate_frames(f[::-1],['a.jpg','b.jpg'])
        with self.assertRaises(ValueError):run.validate_frames(f,['a.jpg'])
        f[1]['timestamp']=0
        with self.assertRaises(ValueError):run.validate_frames(f,['a.jpg','b.jpg'])

    def test_cached_predictions_require_identity_and_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'chunk.npy';r=p.with_suffix('.receipt.json');p.write_bytes(b'complete')
            run.save(r,dict(identity='run-a',sha256=run.digest(p)))
            self.assertTrue(run.cached_prediction(p,r,'run-a'))
            self.assertFalse(run.cached_prediction(p,r,'run-b'))
            p.write_bytes(b'partial');self.assertFalse(run.cached_prediction(p,r,'run-a'))

    def test_export_maps_calibration_and_rejects_incomplete_or_bad_cameras(self):
        frames=[dict(name='a.jpg',timestamp=.12)];C=np.eye(4)[None];C[0,:3,3]=[1,2,3];K=np.array([[400.,400.,140.,252.]])
        rows=run.export_poses(frames,C,K,[1080,1920],[280,504]);self.assertEqual(rows[0]['timestamp'],.12)
        np.testing.assert_allclose(np.array(rows[0]['intrinsics_native'])[:2,2],[540,960])
        self.assertEqual(compare.as_pose(rows[0])['center'],[1,2,3])
        with self.assertRaises(ValueError):run.export_poses(frames,C[:0],K,[1080,1920],[280,504])
        C[0,0,0]=2
        with self.assertRaises(ValueError):run.export_poses(frames,C,K,[1080,1920],[280,504])

    def test_actual_image_changes_invalidate_identity(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'a.jpg').write_bytes(b'original pixels')
            _,first=run.image_manifest(p,['a.jpg'])
            (p/'a.jpg').write_bytes(b'replaced pixels')
            _,second=run.image_manifest(p,['a.jpg'])
            self.assertNotEqual(first,second)
        with self.assertRaises(ValueError):
            run.validate_frames([dict(name='a.jpg',timestamp=0)],['a.jpg','extra.png'])

    def test_empty_image_observations_are_unsupported_not_fatal(self):
        a,b=pose(0),pose(1);a['dist']=[.1,0,0,0];b['dist']=[.1,0,0,0]
        score=compare.image_metrics(a,b,np.empty((0,2)),np.empty((0,2)))
        self.assertIsNone(score['median_px'])

    def test_temporal_holdout_does_not_fit_away_later_drift(self):
        fs=[dict(name=str(i),timestamp=i*.1) for i in range(30)]
        ref={f['name']:pose(i*.1) for i,f in enumerate(fs)};src={f['name']:pose(i*.1+(2 if i>=6 else 0)) for i,f in enumerate(fs)}
        r=compare.camera_check(fs,src,ref)
        self.assertFalse(set(r['fit_names'])&set(r['withheld_names']))
        self.assertGreater(r['median_position_percent_initial_span'],100)
        self.assertFalse(r['accepted_connection'])
        good=compare.camera_check(fs,ref,ref)
        self.assertAlmostEqual(good['median_position_percent_initial_span'],0)
        self.assertFalse(good['accepted_connection'])


if __name__=='__main__':unittest.main()
