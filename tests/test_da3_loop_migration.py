import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import run_da3_full as run
import migrate_da3_loop_receipts as migration


class MigrationTests(unittest.TestCase):
    def setup_run(self, root):
        current = Path(run.__file__)
        previous = root / 'previous.py'
        previous.write_bytes(current.read_bytes().replace(migration.NEW.encode(), migration.OLD.encode()))
        frozen = dict(adapter_sha256=migration.PREVIOUS_SHA256, source_sha256='unchanged', settings={'chunk_size': 32})
        run.save(root / 'inputs.json', frozen)
        identity = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
        directory = root / '_tmp_results_unaligned'; directory.mkdir()
        prediction = directory / 'chunk_0.npy'; prediction.write_bytes(b'original prediction')
        receipt = prediction.with_suffix('.receipt.json')
        run.save(receipt, dict(identity=identity, sha256=run.digest(prediction), frames=32))
        return previous, current, prediction, receipt, frozen

    def test_verified_migration_keeps_prediction_and_preserves_original_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); old, new, prediction, receipt, frozen = self.setup_run(root)
            original_receipt = receipt.read_bytes(); original_stat = prediction.stat()
            report = migration.migrate(root, old, new, expected_chunks=1)
            self.assertTrue(run.cached_prediction(prediction, receipt, report['new_identity']))
            self.assertEqual(prediction.stat().st_mtime_ns, original_stat.st_mtime_ns)
            backup = json.loads((root / 'loop-int64-migration-backup.json').read_text())
            self.assertEqual(backup['inputs'], frozen)
            self.assertEqual(backup['receipts'][str(receipt.relative_to(root))], json.loads(original_receipt))

    def test_corrupt_prediction_rejected_before_any_receipt_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); old, new, prediction, receipt, frozen = self.setup_run(root)
            original = receipt.read_bytes(); prediction.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'Invalid prediction'):
                migration.migrate(root, old, new, expected_chunks=1)
            self.assertEqual(receipt.read_bytes(), original)
            self.assertEqual(json.loads((root / 'inputs.json').read_text()), frozen)

    def test_additional_adapter_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); old, new, prediction, receipt, frozen = self.setup_run(root)
            changed = root / 'changed.py'; changed.write_bytes(new.read_bytes() + b'\n# different adapter\n')
            with self.assertRaisesRegex(ValueError, 'exceed'):
                migration.migrate(root, old, changed, expected_chunks=1)
            self.assertEqual(json.loads((root / 'inputs.json').read_text()), frozen)


if __name__ == '__main__':
    unittest.main()
