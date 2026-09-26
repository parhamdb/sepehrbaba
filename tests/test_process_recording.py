"""Focused coverage and failure-preservation checks for the full-video batch."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from process_recording import Campaign, windows


class RecordingTests(unittest.TestCase):
    def test_all_frames_including_short_tail_are_planned(self):
        frames = [{'name': str(i), 'timestamp': i*.05763} for i in range(12793)]
        plan = windows(frames, 737.301333)
        self.assertEqual(len(plan), 37)
        self.assertEqual(plan[0]['start'], 0)
        self.assertEqual(plan[-1]['end'], 737.301333)
        self.assertEqual(set().union(*(set(w['names']) for w in plan)), {f['name'] for f in frames})
        self.assertIn('12792', plan[-1]['names'])

    def test_failed_stage_does_not_retry_or_block_independent_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root/'source'; source.mkdir()
            (source/'frames.json').write_text(json.dumps([{'name':'frame.jpg','timestamp':0.0}]))
            args = argparse.Namespace(work=root/'work', source_run=source, duration=1,
                windows=root/'windows', database=root/'input.db', colmap='colmap', brush='brush', published_model=[])
            campaign = Campaign(args)
            with patch.object(campaign, 'headroom'):
                self.assertFalse(campaign.run('bad', [sys.executable, '-c', 'raise SystemExit(7)'], []))
                with patch('process_recording.subprocess.run') as child:
                    self.assertFalse(campaign.run('bad', ['must-not-run'], []))
                    child.assert_not_called()
                self.assertTrue(campaign.run('independent', [sys.executable, '-c', 'pass'], []))
                with patch('process_recording.subprocess.run') as child:
                    self.assertTrue(campaign.run('independent', ['must-not-rerun'], []))
                    child.assert_not_called()
            summary = (root/'work/summary.json').read_text()
            self.assertNotIn(str(root), summary)
            self.assertEqual(campaign.state['stages']['bad']['exit_code'], 7)
            campaign.state['stages']['interrupted'] = {'status': 'running'}
            with self.assertRaisesRegex(RuntimeError, 'interrupted stage'):
                campaign.run('interrupted', ['must-not-run'], [])
            campaign.lock.close()


if __name__ == '__main__':
    unittest.main()
