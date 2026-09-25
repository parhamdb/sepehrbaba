import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from sanitize_geometry import sanitize
from clean_static_geometry import read_model, tracks_for


class SanitizationTests(unittest.TestCase):
    def test_invalid_tracks_removed_reciprocally_without_changing_cameras(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root/'source'; source.mkdir(); output = root/'result'
            (source/'cameras.txt').write_text('1 SIMPLE_RADIAL 100 100 100 50 50 0\n')
            (source/'images.txt').write_text(
                '1 1 0 0 0 0 0 0 1 frame_1.jpg\n50 50 1 50 50 2\n'
                '2 1 0 0 0 0 0 0 1 frame_2.jpg\n50 50 1 50 50 2\n')
            (source/'points3D.txt').write_text(
                '1 0 0 5 1 2 3 0 1 0 2 0\n2 0 0 -1 1 2 3 0 1 1 2 1\n')
            before = {p.name:p.read_bytes() for p in source.iterdir()}
            report = sanitize(source, output)
            self.assertEqual(report['removed_point_ids'], [2])
            self.assertEqual(report['removed_associations'], 2)
            original, _ = read_model(source); cleaned, points = read_model(output)
            self.assertEqual(set(points), {1}); self.assertEqual(tracks_for(cleaned), {1:[(1,0),(2,0)]})
            for iid in original:
                self.assertEqual(original[iid]['row'], cleaned[iid]['row'])
                self.assertTrue((original[iid]['obs'][:,:2] == cleaned[iid]['obs'][:,:2]).all())
            self.assertEqual(before, {p.name:p.read_bytes() for p in source.iterdir()})
            with self.assertRaises(ValueError): sanitize(source, output)
