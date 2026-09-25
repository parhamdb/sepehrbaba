"""Meaningful split, camera and masked-metric checks without COLMAP or a GPU."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_references import prepare, camera_parameters
from evaluate_renders import evaluate


class EvaluationTests(unittest.TestCase):
    def fixture(self, root):
        for folder in ['model', 'dataset/images', 'dataset/masks', 'held']:
            (root/folder).mkdir(parents=True)
        (root/'model/cameras.txt').write_text('1 PINHOLE 8 12 10 10 4 6\n')
        (root/'model/points3D.txt').write_text('')
        rows = []
        for i in range(1, 4):
            rows.extend([f'{i} 1 0 0 0 1 2 3 1 frame_{i}.jpg', ''])
            Image.new('RGB', (8,12), (100,100,100)).save(root/f'dataset/images/frame_{i}.jpg')
            Image.new('L', (8,12), 255).save(root/f'dataset/masks/frame_{i}.png')
        (root/'model/images.txt').write_text('\n'.join(rows)+'\n')
        (root/'held/frame_1.png').touch()

    def test_split_and_camera_transform_survive_sampling(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); self.fixture(root)
            views = prepare(root/'dataset', root/'model', root/'held', root/'refs',
                            6, 2, ['frame_1','frame_3'], eval_every=3)
            self.assertEqual([v['split'] for v in views], ['held-out','train','train'])
            np.testing.assert_allclose(views[0]['position'], [1,2,-3])
            np.testing.assert_allclose(views[0]['target'], [1,2,-2])
            np.testing.assert_allclose(views[0]['up'], [0,1,0])
            self.assertEqual((views[0]['width'], views[0]['height']), (4,6))
            with self.assertRaises(ValueError):
                prepare(root/'dataset',root/'model',root/'held',root/'refs')

    def test_incomplete_held_out_directory_cannot_leak_into_training(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); self.fixture(root)
            # Period 2 expects frames 1 and 3; only frame 1 exists.
            with self.assertRaisesRegex(ValueError, 'missing='):
                prepare(root/'dataset',root/'model',root/'held',root/'refs',eval_every=2)
            self.assertFalse((root/'refs').exists())

    def test_unsupported_camera_does_not_silently_make_wrong_rays(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'cameras.txt'
            for text in ['1 SIMPLE_RADIAL 8 12 10 4 6 0.1', '1 PINHOLE 8 12 10 11 4 6', '1 PINHOLE 8 12 10 10 3 6']:
                p.write_text(text+'\n')
                with self.assertRaises(ValueError): camera_parameters(p)

    def test_masks_exclude_rgb_error_and_missing_view_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); self.fixture(root)
            refs = root/'refs'
            prepare(root/'dataset',root/'model',root/'held',refs,12,eval_every=3)
            renders = root/'renders'; renders.mkdir()
            original = np.asarray(Image.open(refs/'images/frame_1.jpg').convert('RGB')).copy()
            mask = np.full((12,8),255,np.uint8); mask[:6]=0
            Image.fromarray(mask).save(refs/'masks/frame_1.png')
            original[:6]=255
            Image.fromarray(original).save(renders/'frame_1.png')
            self.assertTrue(evaluate(refs,renders,'held-out')['views'][0]['perfect_match'])
            (renders/'frame_1.png').unlink()
            with self.assertRaises(FileNotFoundError): evaluate(refs,renders,'held-out')


if __name__ == '__main__': unittest.main()
