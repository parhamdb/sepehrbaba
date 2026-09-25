#!/usr/bin/env python3
"""Video -> sampled images -> COLMAP cameras -> Brush Gaussian-splat PLY.

Python standard library only. External programs: ffmpeg, ffprobe, COLMAP,
and (for training) Brush 0.3.0. See README.md for installation and examples.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import time
import urllib.request

DEFAULT_URL = "https://video.twimg.com/amplify_video/2015558220249530368/vid/avc1/1080x1920/2LxgD15qCvFD42mt.mp4?tag=21"
ROOT = Path(__file__).resolve().parent


def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def binary_count(path):
    with path.open("rb") as f:
        return struct.unpack("<Q", f.read(8))[0]


def select_model(sparse):
    models = []
    for path in sorted(sparse.iterdir()):
        if path.is_dir() and all((path / f"{name}.bin").is_file()
                                 for name in ("cameras", "images", "points3D")):
            models.append({"path": str(path),
                           "registered_images": binary_count(path / "images.bin"),
                           "points": binary_count(path / "points3D.bin")})
    if not models:
        raise RuntimeError("COLMAP produced no model. Inspect logs/map.log; try a shorter, sharper segment with parallax.")
    return max(models, key=lambda m: (m["registered_images"], m["points"])), models


class Pipeline:
    def __init__(self, args):
        self.a = args
        self.out = args.output.resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        self.logs = self.out / "logs"
        self.logs.mkdir(exist_ok=True)
        self.state_file = self.out / "state.json"
        self.state = json.loads(self.state_file.read_text()) if self.state_file.exists() else {"stages": {}}

    def run(self, stage, command):
        command = list(map(str, command))
        log = self.logs / f"{stage}.log"
        print(f"[{stage}] {shlex.join(command)}\n  log: {log}", flush=True)
        with log.open("a") as f:
            f.write(f"\n{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {shlex.join(command)}\n")
            f.flush()
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            child = subprocess.Popen(command, stdout=f, stderr=subprocess.STDOUT, env=env)
            try:
                code = child.wait()
            except KeyboardInterrupt:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                raise
        if code:
            raise RuntimeError(f"{stage} exited {code}; inspect {log}")

    def stage(self, name, action, outputs):
        record = self.state["stages"].get(name, {})
        if record.get("status") == "passed":
            if not all(p.exists() for p in outputs):
                raise RuntimeError(f"Completed {name} output is missing. Restore it or use a new --output directory.")
            print(f"[{name}] reusing completed output", flush=True)
            return
        self.state["stages"][name] = {"status": "running", "started": time.time()}
        save_json(self.state_file, self.state)
        try:
            action()
            if not all(p.exists() for p in outputs):
                raise RuntimeError(f"{name} did not produce its expected outputs")
        except (Exception, KeyboardInterrupt) as e:
            self.state["stages"][name].update(status="failed", error=str(e))
            save_json(self.state_file, self.state)
            raise
        self.state["stages"][name].update(status="passed", finished=time.time())
        save_json(self.state_file, self.state)

    def source(self):
        source = self.a.source
        if not source.startswith(("https://", "http://")):
            path = Path(source).resolve()
            if not path.is_file():
                raise RuntimeError(f"Video does not exist: {path}")
            return path
        path = self.out / "source.mp4"
        saved = self.state.get("download", {})
        if saved.get("url") == source and path.exists() and sha256(path) == saved.get("sha256"):
            return path
        if path.exists():
            raise RuntimeError("Existing downloaded video has a different source or checksum; use a new output directory.")
        print(f"Downloading {source}", flush=True)
        part = path.with_suffix(".mp4.part")
        request = urllib.request.Request(source, headers={"User-Agent": "sepehr-video-to-splat/1"})
        with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as f:
            shutil.copyfileobj(response, f)
        # Validate before accepting a download (including an HTML error page).
        probe(part)
        part.replace(path)
        self.state["download"] = {"url": source, "sha256": sha256(path)}
        save_json(self.state_file, self.state)
        return path

    def prepare(self):
        if "dataset_fingerprint" in self.state:
            raise RuntimeError("Video preparation requires a separate output from imported-component training")
        for exe in ("ffmpeg", "ffprobe", "colmap"):
            require(exe)
        video = self.source()
        info = probe(video)
        duration = float(info["format"]["duration"])
        if self.a.start >= duration:
            raise RuntimeError("--start is beyond the end of the video")
        span = min(self.a.duration or duration, duration - self.a.start)
        if math.ceil(span * self.a.fps) > self.a.max_frames:
            raise RuntimeError(f"Requested segment needs about {math.ceil(span * self.a.fps)} frames; "
                               "reduce --duration/--fps or explicitly raise --max-frames. Video is never silently truncated.")
        config = {"video_sha256": sha256(video), "start": self.a.start, "duration": span,
                  "fps": self.a.fps, "max_size": self.a.max_size,
                  "overlap": self.a.overlap, "camera_model": self.a.camera_model,
                  "colmap_gpu": self.a.colmap_gpu}
        if self.state.get("config") not in (None, config):
            raise RuntimeError("Preparation settings or video changed. Use a new --output directory to avoid stale cameras.")
        self.state.update(config=config, source=str(video), probe=info)
        save_json(self.state_file, self.state)
        images = self.out / "frames"
        images.mkdir(exist_ok=True)
        db = self.out / "database.db"
        sparse = self.out / "sparse"
        sparse.mkdir(exist_ok=True)

        def extract():
            # Only our own numbered images; an interrupted extraction can be retried.
            for p in images.glob("frame_*.jpg"):
                p.unlink()
            scale = f"scale={self.a.max_size}:{self.a.max_size}:force_original_aspect_ratio=decrease:force_divisible_by=2"
            self.run("extract", ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin", "-y",
                                 "-ss", self.a.start, "-i", video, "-t", span, "-map", "0:v:0",
                                 "-vf", f"fps={self.a.fps},{scale}", "-q:v", "2",
                                 "-threads", self.a.threads, images / "frame_%06d.jpg"])
            if len(list(images.glob("frame_*.jpg"))) < 8:
                raise RuntimeError("Fewer than eight frames; choose a longer segment or higher --fps.")

        self.stage("extract", extract, [images / "frame_000008.jpg"])
        # COLMAP 4 renamed these groups. Inspect installed help rather than assume.
        eh = help_text("colmap", "feature_extractor", "-h")
        mh = help_text("colmap", "sequential_matcher", "-h")
        ex = "FeatureExtraction" if "--FeatureExtraction.use_gpu" in eh else "SiftExtraction"
        mt = "FeatureMatching" if "--FeatureMatching.use_gpu" in mh else "SiftMatching"
        self.stage("features", lambda: self.run("features", [
            "colmap", "feature_extractor", "--database_path", db, "--image_path", images,
            "--ImageReader.single_camera", "1", "--ImageReader.camera_model", self.a.camera_model,
            f"--{ex}.use_gpu", int(self.a.colmap_gpu), f"--{ex}.num_threads", self.a.threads]), [db])
        self.stage("matches", lambda: self.run("matches", [
            "colmap", "sequential_matcher", "--database_path", db,
            f"--{mt}.use_gpu", int(self.a.colmap_gpu), f"--{mt}.num_threads", self.a.threads,
            "--SequentialMatching.overlap", self.a.overlap,
            "--SequentialMatching.loop_detection", "0"]), [db])

        def mapping():
            self.run("map", ["colmap", "mapper", "--database_path", db, "--image_path", images,
                             "--output_path", sparse, "--Mapper.num_threads", self.a.threads])
            selected, models = select_model(sparse)
            save_json(self.out / "models.json", {"selected": selected, "components": models})

        self.stage("map", mapping, [self.out / "models.json"])
        selected, models = select_model(sparse)
        count = len(list(images.glob("frame_*.jpg")))
        ratio = selected["registered_images"] / count
        quality = {"input_frames": count, "registered_fraction": ratio,
                   "selected": selected, "components": models,
                   "minimum_registered_fraction": self.a.min_registered,
                   "accepted": ratio >= self.a.min_registered and selected["points"] >= 100}
        save_json(self.out / "quality.json", quality)
        print(f"Registered {selected['registered_images']}/{count} frames ({ratio:.1%}); "
              f"{selected['points']} points; {len(models)} component(s)", flush=True)
        if not quality["accepted"]:
            raise RuntimeError("Insufficient coherent geometry. See quality.json and preserved sparse models. "
                               "Try a shorter continuous segment; moving subjects and blur cannot be fixed by more training.")
        dataset = self.out / "dataset"
        self.stage("undistort", lambda: self.run("undistort", [
            "colmap", "image_undistorter", "--image_path", images, "--input_path", selected["path"],
            "--output_path", dataset, "--output_type", "COLMAP", "--max_image_size", self.a.max_size]),
            [dataset / "images", dataset / "sparse" / "cameras.bin", dataset / "sparse" / "images.bin",
             dataset / "sparse" / "points3D.bin"])
        print(f"Prepared training dataset: {dataset}", flush=True)

    def train(self):
        dataset = self.out / "dataset"
        if getattr(self.a, "dataset", None):
            dataset = self.a.dataset.resolve()
            self.import_dataset(dataset)
        else:
            quality_file = self.out / "quality.json"
            if not quality_file.exists() or not json.loads(quality_file.read_text())["accepted"]:
                raise RuntimeError("Run --stage prepare successfully before training; quality.json must accept the geometry.")
            if self.state["stages"].get("undistort", {}).get("status") != "passed":
                raise RuntimeError("Dataset undistortion has not completed")
        brush = self.a.brush
        require(brush)
        bh = help_text(brush, "--help")
        if "--total-steps" not in bh or "--export-name" not in bh:
            raise RuntimeError("Unsupported Brush CLI. Install pinned Brush 0.3.0 using setup.sh.")
        config = {"steps": self.a.steps, "max_splats": self.a.max_splats,
                  "resolution": self.a.train_resolution, "brush_version": help_text(brush, "--version").strip(),
                  "eval_split_every": self.a.eval_split_every}
        if self.state.get("training") not in (None, config):
            raise RuntimeError("Training settings changed. Preserve this run and use a new output directory.")
        self.state["training"] = config
        export = self.out / "splats"
        export.mkdir(exist_ok=True)
        final = export / "scene.ply"

        def fit():
            candidate = export / f"scene-{time.time_ns()}.partial.ply"
            command = [brush, dataset, "--total-steps", self.a.steps,
                               "--max-resolution", self.a.train_resolution,
                               "--max-splats", self.a.max_splats,
                               "--growth-stop-iter", max(1, self.a.steps // 2),
                               "--export-every", self.a.steps, "--export-path", export,
                               "--export-name", candidate.name]
            if self.a.eval_split_every:
                command += ["--eval-split-every", self.a.eval_split_every,
                            "--eval-every", self.a.steps, "--eval-save-to-disk"]
            self.run("train", command)
            validate_splat(candidate)
            if self.a.eval_split_every and not list(export.glob(f"eval_{self.a.steps}/*.png")):
                raise RuntimeError("Trainer did not produce requested evaluation renders")
            candidate.replace(final)

        self.stage("train", fit, [final])
        validate_splat(final)
        print(f"Gaussian splat: {final}\nOpen it in Brush or PlayCanvas SuperSplat.", flush=True)

    def import_dataset(self, dataset):
        """Use an explicitly selected COLMAP component, without rerunning SfM.

        Coverage here refers only to the supplied dataset, never its source video.
        A fresh output keeps rejected whole-video evidence separate and intact.
        """
        if "config" in self.state:
            raise RuntimeError("--dataset requires a separate output from video preparation")
        sparse = dataset / "sparse"
        if not (sparse / "images.bin").is_file():
            sparse = sparse / "0"
        models = [sparse / f"{name}.bin" for name in ("cameras", "images", "points3D")]
        images = sorted(p for p in (dataset / "images").rglob("*")
                        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png"))
        if not all(p.is_file() for p in models) or len(images) < 8:
            raise RuntimeError("Dataset requires at least eight images and COLMAP binary cameras/images/points3D")
        registered = binary_count(sparse / "images.bin")
        points = binary_count(sparse / "points3D.bin")
        if registered != len(images) or points < 100:
            raise RuntimeError("Provided dataset must contain exactly its registered images and at least 100 points")
        masks = sorted((dataset / "masks").glob("*")) if (dataset / "masks").exists() else []
        if masks and ({p.stem for p in masks} != {p.stem for p in images}
                      or any(p.suffix.lower() != ".png" for p in masks)):
            raise RuntimeError("Masks must contain one PNG per image, with matching stems")
        hashes = {str(p.relative_to(dataset)): sha256(p) for p in models + images + masks}
        fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
        if self.state.get("dataset_fingerprint") not in (None, fingerprint):
            raise RuntimeError("Dataset changed; use a new --output directory")
        self.state.update(dataset_fingerprint=fingerprint, dataset=str(dataset))
        save_json(self.state_file, self.state)
        save_json(self.out / "quality.json", {
            "accepted": True, "scope": "Explicitly supplied COLMAP component only; not whole-video coverage",
            "registered_images": registered, "input_frames": len(images), "points": points,
            "dataset_fingerprint": fingerprint, "masked_images": len(masks)})
        print(f"Using selected component: {registered} cameras, {points} points; whole-video coverage is not asserted.", flush=True)


def validate_splat(path):
    if not path.is_file():
        raise RuntimeError(f"Trainer did not export {path}")
    # Pinned Brush writes fixed-stride float32 binary vertices. A header alone
    # is not success: Brush can warn about a failed export yet exit with code 0.
    lines = []
    with path.open("rb") as f:
        while f.tell() < 65536:
            line = f.readline(4096)
            if not line:
                break
            lines.append(line.strip())
            if lines[-1] == b"end_header":
                break
        offset = f.tell()
    if not lines or lines[0] != b"ply" or lines[-1] != b"end_header":
        raise RuntimeError("Invalid PLY: incomplete header")
    if b"format binary_little_endian 1.0" not in lines:
        raise RuntimeError("Expected Brush's binary little-endian PLY export")
    elements = [line.split() for line in lines if line.startswith(b"element ")]
    if len(elements) != 1 or len(elements[0]) != 3 or elements[0][1] != b"vertex":
        raise RuntimeError("Expected one PLY vertex element")
    count = int(elements[0][2])
    properties = [line.split() for line in lines if line.startswith(b"property ")]
    if any(len(prop) != 3 or prop[1] not in (b"float", b"float32") for prop in properties):
        raise RuntimeError("Expected fixed-size float32 Gaussian properties")
    names = {prop[2] for prop in properties}
    required = {b"x", b"y", b"z", b"opacity"}
    required.update(f"{prefix}_{i}".encode() for prefix, n in (("f_dc", 3), ("scale", 3), ("rot", 4)) for i in range(n))
    if not required <= names:
        raise RuntimeError(f"Invalid Gaussian-splat PLY (missing {sorted(required - names)}): {path}")
    if count <= 0:
        raise RuntimeError("Empty Gaussian-splat PLY")
    expected = offset + count * len(properties) * 4
    if path.stat().st_size != expected:
        raise RuntimeError(f"Truncated or inconsistent Gaussian-splat PLY: expected {expected} bytes, got {path.stat().st_size}")


def require(exe):
    if not shutil.which(exe):
        raise RuntimeError(f"Missing executable: {exe}. See README.md / setup.sh.")


def help_text(*command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
    if result.returncode:
        raise RuntimeError(f"Cannot run {command[0]}: {result.stdout[-2000:]}")
    return result.stdout


def probe(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                             "-show_entries", "format=duration,size:stream=codec_name,width,height,avg_frame_rate",
                             "-of", "json", str(path)], capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    if not info.get("streams") or float(info["format"]["duration"]) <= 0:
        raise RuntimeError("Input is not a readable video")
    return info


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", nargs="?", default=DEFAULT_URL, help="Local video or HTTP(S) URL")
    p.add_argument("--output", type=Path, default=Path("runs/scene"))
    p.add_argument("--stage", choices=("prepare", "train", "all"), default="all")
    p.add_argument("--dataset", type=Path, help="Train an existing COLMAP component in a separate output; requires --stage train")
    p.add_argument("--start", type=float, default=0, help="Start time in seconds")
    p.add_argument("--duration", type=float, help="Seconds to process; default: rest of video")
    p.add_argument("--fps", type=float, default=2, help="Sampling rate (not source frame rate)")
    p.add_argument("--max-frames", type=int, default=2000)
    p.add_argument("--max-size", type=int, default=1280, help="Maximum extracted image edge")
    p.add_argument("--overlap", type=int, default=10, help="Sequential matching window")
    p.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 1))
    p.add_argument("--camera-model", choices=("SIMPLE_RADIAL", "OPENCV", "PINHOLE"), default="SIMPLE_RADIAL")
    p.add_argument("--colmap-gpu", action="store_true", help="Requires a CUDA-enabled COLMAP build")
    p.add_argument("--min-registered", type=float, default=0.6,
                   help="Minimum fraction of frames in largest coherent model")
    p.add_argument("--brush", default=str(ROOT / ".tools/brush-app-x86_64-unknown-linux-gnu/brush_app"))
    p.add_argument("--steps", type=int, default=15000)
    p.add_argument("--max-splats", type=int, default=1000000)
    p.add_argument("--train-resolution", type=int, default=960)
    p.add_argument("--eval-split-every", type=int, default=0, help="Hold out every Nth image and save evaluation renders; 0 disables")
    a = p.parse_args(argv)
    if a.dataset and a.stage != "train":
        p.error("--dataset requires --stage train")
    if a.eval_split_every != 0 and a.eval_split_every < 2:
        p.error("--eval-split-every must be 0 or at least 2")
    if not math.isfinite(a.start) or a.start < 0 or not 0 < a.min_registered <= 1:
        p.error("--start must be finite and >= 0; --min-registered must be in (0, 1]")
    for name in ("fps", "max_frames", "max_size", "overlap", "threads", "steps", "max_splats", "train_resolution"):
        if not math.isfinite(getattr(a, name)) or getattr(a, name) <= 0:
            p.error(f"--{name.replace('_', '-')} must be finite and positive")
    if a.duration is not None and (not math.isfinite(a.duration) or a.duration <= 0):
        p.error("--duration must be finite and positive")
    try:
        pipeline = Pipeline(a)
        # An advisory lock prevents two invocations from corrupting one run.
        import fcntl
        with (pipeline.out / ".lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if a.stage in ("prepare", "all"):
                pipeline.prepare()
            if a.stage in ("train", "all"):
                pipeline.train()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Completed stages and logs are preserved.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
