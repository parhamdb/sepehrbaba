import importlib.util
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location('camera_review', Path(__file__).parents[1]/'scripts/camera_review.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class CameraReviewTests(unittest.TestCase):
    def test_projection_distortion_and_behind_camera(self):
        camera = dict(model='SIMPLE_RADIAL', params=[100, 50, 50, .1])
        uv, good = m.project([[1, 0, 10], [0, 0, -1]], np.eye(3), [0, 0, 0], camera)
        np.testing.assert_allclose(uv[0], [60.01, 50])
        self.assertEqual(good.tolist(), [True, False])

    def test_colmap_camera_center_and_rotation(self):
        R = m.rotation([np.sqrt(.5), 0, np.sqrt(.5), 0])
        center = np.array([2, 3, 4.]); t = -R@center
        np.testing.assert_allclose(-R.T@t, center, atol=1e-12)
        np.testing.assert_allclose(R@np.array([0, 0, 1.]), [1, 0, 0], atol=1e-12)

    def test_flow_detects_intentionally_wrong_pose(self):
        import cv2
        cv2.setNumThreads(2)
        rng = np.random.default_rng(5)
        before = rng.integers(0, 256, (160, 160), dtype=np.uint8)
        after = cv2.warpAffine(before, np.float32([[1, 0, 4], [0, 1, 0]]), (160, 160))
        xy = np.array([[x, y] for x in [40, 60, 80, 100, 120] for y in [40, 60, 80, 100, 120]])
        tracked, good = m.flow_check(before, after, xy)
        self.assertGreater(good.sum(), 15)
        camera = dict(model='PINHOLE', params=[160, 160, 80, 80])
        xyz = np.column_stack(((xy-[80, 80])/160*4, np.full(len(xy), 4.)))
        expected, _ = m.project(xyz, np.eye(3), [.1, 0, 0], camera)
        wrong, _ = m.project(xyz, np.eye(3), [.35, 0, 0], camera)
        self.assertLess(np.median(np.linalg.norm(tracked[good]-expected[good], axis=1)), .5)
        self.assertGreater(np.median(np.linalg.norm(tracked[good]-wrong[good], axis=1)), 8)


if __name__ == '__main__':
    unittest.main()
