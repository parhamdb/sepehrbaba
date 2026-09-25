"""Focused checks of failure handling and reconstruction selection."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from video_to_splat import Pipeline, main, select_model, validate_splat


class PipelineTests(unittest.TestCase):
    def test_selects_largest_registered_component_not_first(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, count, points in (("0", 12, 1000), ("1", 40, 800), ("2", 40, 1200)):
                model = root / name
                model.mkdir()
                for file, number in (("cameras", 1), ("images", count), ("points3D", points)):
                    (model / f"{file}.bin").write_bytes(struct.pack("<Q", number))
            chosen, models = select_model(root)
            self.assertEqual(Path(chosen["path"]).name, "2")
            self.assertEqual(len(models), 3)

    def test_absent_geometry_is_failure(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError, "no model"):
                select_model(Path(d))

    def test_failed_stage_is_recorded_and_completed_stage_is_reused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = Pipeline(argparse.Namespace(output=root))
            artifact = root / "artifact"
            with self.assertRaisesRegex(RuntimeError, "expected outputs"):
                p.stage("example", lambda: None, [artifact])
            self.assertEqual(json.loads(p.state_file.read_text())["stages"]["example"]["status"], "failed")
            p.stage("example", lambda: artifact.write_text("valid"), [artifact])
            p.stage("example", lambda: self.fail("Reran a successful stage"), [artifact])
            artifact.unlink()
            with self.assertRaisesRegex(RuntimeError, "missing"):
                p.stage("example", lambda: None, [artifact])

    def test_rejects_point_cloud_as_splat(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cloud.ply"
            path.write_bytes(b"ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\nend_header\n0\n")
            with self.assertRaises(RuntimeError):
                validate_splat(path)

    def test_rejects_truncated_export_and_accepts_complete_payload(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "scene.ply"
            names = ["x", "y", "z", "opacity"]
            names += [f"{prefix}_{i}" for prefix, n in (("f_dc", 3), ("scale", 3), ("rot", 4)) for i in range(n)]
            header = ("ply\nformat binary_little_endian 1.0\nelement vertex 2\n" +
                      "".join(f"property float {name}\n" for name in names) + "end_header\n").encode()
            path.write_bytes(header)
            with self.assertRaisesRegex(RuntimeError, "Truncated"):
                validate_splat(path)
            path.write_bytes(header + struct.pack("<" + "f" * 2 * len(names), *([0.] * 2 * len(names))))
            validate_splat(path)

    def test_rejects_invalid_sampling(self):
        for args in (("--fps", "nan"), ("--start", "-1"), ("--duration", "0"), ("--steps", "0")):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main(args)
                self.assertEqual(error.exception.code, 2)

    def test_training_requires_accepted_cameras(self):
        with tempfile.TemporaryDirectory() as d:
            p = Pipeline(argparse.Namespace(output=Path(d)))
            with self.assertRaisesRegex(RuntimeError, "prepare"):
                p.train()

    def test_explicit_component_import_detects_changed_images(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dataset = root / "dataset"
            (dataset / "sparse").mkdir(parents=True)
            (dataset / "images").mkdir()
            for name, count in (("cameras", 1), ("images", 8), ("points3D", 100)):
                (dataset / "sparse" / f"{name}.bin").write_bytes(struct.pack("<Q", count))
            for i in range(8):
                (dataset / "images" / f"{i}.jpg").write_bytes(b"fixture")
            p = Pipeline(argparse.Namespace(output=root / "run"))
            p.import_dataset(dataset)
            self.assertIn("not whole-video", json.loads((p.out / "quality.json").read_text())["scope"])
            (dataset / "images" / "0.jpg").write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "Dataset changed"):
                p.import_dataset(dataset)

    def test_component_import_cannot_override_failed_video_run(self):
        with tempfile.TemporaryDirectory() as d:
            p = Pipeline(argparse.Namespace(output=Path(d)))
            p.state["config"] = {"fps": 2}
            with self.assertRaisesRegex(RuntimeError, "separate output"):
                p.import_dataset(Path(d))

    def test_video_preparation_cannot_reuse_component_training(self):
        with tempfile.TemporaryDirectory() as d:
            p = Pipeline(argparse.Namespace(output=Path(d)))
            p.state["dataset_fingerprint"] = "previous-component"
            with self.assertRaisesRegex(RuntimeError, "separate output"):
                p.prepare()


if __name__ == "__main__":
    unittest.main()
