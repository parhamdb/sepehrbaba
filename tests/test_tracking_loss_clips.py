import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tracking_loss_clips',Path(__file__).parents[1]/'scripts/tracking_loss_clips.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class LossClipsTest(unittest.TestCase):
    def test_exact_boundary_and_return(self):
        frames=[dict(name=str(i),timestamp=i*.5) for i in range(100)]
        known={f['name'] for f in frames if not 20<=f['timestamp']<23}
        rows=m.losses(frames,known,50)
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual((r['start'],r['end'],r['gap_seconds']),(10,30,3))
        self.assertTrue(r['recovery_visible_in_clip'])
        self.assertEqual(len(r['frames']),40)

    def test_raw_poses_prevent_false_loss_and_terminal_gap(self):
        frames=[dict(name=str(i),timestamp=float(i)) for i in range(30)]
        known={str(i) for i in range(25)}
        rows=m.losses(frames,known,30)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['gap_seconds'],5)
        self.assertFalse(rows[0]['recovery_visible_in_clip'])
        self.assertEqual(rows[0]['end'],30)


if __name__=='__main__':unittest.main()
