"""Exercise the production chunk wrapper at the failed loop receipt boundary."""
import ast
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import run_da3_full as run


class LoopReceiptTests(unittest.TestCase):
    def test_numpy_loop_ranges_write_valid_receipt(self):
        source = ast.parse(Path(run.__file__).read_text())
        wrapper = next(n for n in ast.walk(source) if isinstance(n, ast.ClassDef) and n.name == 'CheckedStreaming')
        wrapper.body = [n for n in wrapper.body if isinstance(n, ast.FunctionDef) and n.name == 'process_single_chunk']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prediction = SimpleNamespace(extrinsics=np.zeros((16, 3, 4)), intrinsics=np.zeros((16, 3, 3)),
                                         processed_images=SimpleNamespace(shape=(16, 504, 280, 3)))
            class Estimator:
                def process_single_chunk(self, range_1, chunk_idx, range_2, is_loop):
                    (root / 'loop_100_108_200_208.npy').write_bytes(b'saved prediction')
                    return prediction
            state = {}
            scope = dict(DA3_Streaming=Estimator, guard=lambda: None, Path=Path, np=np, identity='test',
                         cached_prediction=run.cached_prediction, digest=run.digest, save=run.save,
                         state=state, progress=lambda **kw: state.update(kw))
            exec(compile(ast.Module(body=[wrapper], type_ignores=[]), run.__file__, 'exec'), scope)
            instance = scope['CheckedStreaming']()
            instance.result_loop_dir = root
            instance.process_single_chunk((np.int64(100), np.int64(108)), range_2=(200, 208), is_loop=True)
            receipt = json.loads((root / 'loop_100_108_200_208.receipt.json').read_text())
            self.assertEqual(receipt['frames'], 16)
            self.assertTrue(run.cached_prediction(root / 'loop_100_108_200_208.npy', root / 'loop_100_108_200_208.receipt.json', 'test'))
            self.assertEqual(state['loop_chunks_done'], 1)


if __name__ == '__main__':
    unittest.main()
