# Sepehr Baba

An interactive 3D Gaussian-splat viewer published on GitHub Pages.

**[Open the 3D scene](https://parhamdb.github.io/sepehrbaba/)**

**Current scene: an 18-second pilot, approximately 03:19–03:37 of a 12:17 recording.**
It contains 226,293 Gaussians recovered from 252 of the interval's 271 native
frames. The floor and stationary objects remained recognizable in inspected
held-out views, a small orbit, and a 0.27-unit sideways camera movement. Blur,
holes and peripheral artifacts remain, especially around people. This is a limited
pilot, not a complete reconstruction of the recording. The scene contains imagery
of deceased people.

Enter the scene, drag to orbit, and scroll/pinch to zoom. Choose **Move freely**
to navigate with W A S D or the on-screen directional controls. **Reset view**
returns to the authored camera. Press Esc to release the mouse after keyboard movement. This is a visual scene with no collision barriers.

## Development and publishing

```sh
npm ci
npm run build
python3 -m http.server 8080 --directory dist
```

The Pages workflow builds and deploys `dist/` on pushes to `main`. All scene and
viewer files are served from the repository's Pages site; no visitor login is
needed. The viewer uses WebGPU with WebGL fallback. Append `?webgl` to force WebGL.

`public/scene.json` describes the current scene, initial camera and orientation.
`public/assets/preview.ply` is the current model. Replace these together when a
larger reconstruction is verified, and update the visible coverage labels.
Do not label this small preview as a reconstruction of the entire video.

## Technology and evidence

- [SuperSplat Viewer](https://github.com/playcanvas/supersplat-viewer), MIT license.
- [PlayCanvas Engine](https://github.com/playcanvas/engine), MIT license.
- Reconstruction: COLMAP camera recovery and Brush Gaussian training.
- Current model: 8,000 training steps, 1920-pixel maximum edge; 226 training views /
  26 held-out views. PSNR on unmasked static regions is 22.33 dB; this excludes
  detected people and is not directly comparable to the original preview score.
- Geometry: 109,642 points; mean reprojection error 1.23 pixels, 95th percentile
  2.49 pixels. Nineteen interval frames could not be registered.
- Conservative person masks were inspected before training; some static human
  content is also excluded. The saved PLY is about 53 MB.

Third-party license notices accompany the bundled viewer. No license or identity
claim is made about the underlying source recording or the people it depicts.

## Full recording reconstruction

`scripts/full_video.py` preserves every decoded frame at its native dimensions
as high-quality JPEG (quality 1; not lossless), with exact source timestamps.
The original MP4 remains the unchanged source reference. It extracts features
from every frame. The sharpest frame in each group of four bootstraps mapping;
adjacent selected keyframes are explicitly matched in addition to linear native-frame
neighbors. Preparation stops at bootstrap geometry. It does not train disconnected
fragments automatically.

Requires Linux, Python 3 + Pillow, FFmpeg, a CUDA-enabled COLMAP 3.12.6 build,
and Brush 0.3.0. Supply your own local tool paths:

```sh
python3 scripts/full_video.py /path/to/input.mp4 \
  --work /path/to/reconstruction \
  --colmap /path/to/colmap \
  --max-seconds 7200
```

Completed stages resume with the same command. The process stops its own child
jobs at the time limit or below 4 GiB available memory. See `state.json`,
`frames.json`, `logs/`, and, after mapping, `coverage.json`. Interrupted mapping
is preserved separately before a new mapping attempt. Feature/match databases
can resume completed entries. An interrupted training stage starts again.

Disconnected camera models remain separate. Missing registrations are listed;
continuity of the video is not proof of one connected 3D model. Retain existing
runs when changing scripts: stage fingerprints intentionally reject changed code.

### Bounded repair and visual acceptance

Reuse saved features and a seed model whose cameras lie inside the selected
interval. The repair command copies the database, explicitly matches selected
keyframe neighbors, and continues mapping with every native frame in that interval.
It triangulates new points, jointly refines poses, and measures actual reprojection
errors instead of trusting stale stored point errors.

```sh
python3 scripts/repair_scene.py \
  --source-run /path/to/reconstruction \
  --database /path/to/reconstruction/database.db \
  --seed-model /path/to/reconstruction/sparse/0 \
  --work /path/to/pilot --colmap /path/to/colmap \
  --start 199 --end 217 --max-seconds 900
python3 scripts/mask_people.py /path/to/pilot/dataset
# Inspect masks against their source frames before running training.
python3 scripts/video_to_splat.py --stage train \
  --dataset /path/to/pilot/dataset --output /path/to/pilot-training \
  --brush /path/to/brush_app --steps 8000 --train-resolution 1920 \
  --max-splats 500000 --eval-split-every 10
```

The example interval must contain the chosen seed's cameras; choose a matching seed.
Repair requires NumPy. Masking additionally requires PyTorch, torchvision and Pillow;
it downloads the official DeepLabV3 ResNet50 COCO/VOC weights on first use.
The person masks exclude detected people, including static people, and dilate the
boundary by seven pixels. This is an imperfect automatic segmentation: inspect it.
Masks retain the exact undistorted image dimensions and are included in the training
fingerprint so a changed mask cannot silently reuse a completed training run.

Geometry acceptance requires at least 90% of the interval's frames in one model,
1,000 points, mean reprojection error at most 1.5 pixels, 95th percentile at most
3.5 pixels, and no associated points behind cameras. `quality.json` records both
missing frames and measured errors. Snapshots and logs survive the runtime cap;
interrupted mapping is not automatically claimed as resumable training.

Passing geometry is only permission to evaluate a candidate. Compare held-out
renders against their source images, then move through the candidate in the viewer.
Do not publish or expand to the full recording until the static environment remains
recognizable from nearby viewpoints. The current pilot passed a bounded visual check of the central static scene.
Larger movements, unseen surfaces, and the full recording remain unverified.

### Controlled static-geometry cleanup

`scripts/clean_static_geometry.py` creates a separate dataset from an existing
undistorted, masked dataset. It removes masked feature observations, keeps the
best-fitting observation of each point within each image, and requires support
from at least two distinct unmasked views. It refines cameras with sufficient
remaining observations while preserving weak-camera poses and fixed intrinsics.
Images and masks are copied byte-for-byte; all image names and the evaluation
ordering remain unchanged. This permits a comparison at the same training budget.

```sh
python3 scripts/clean_static_geometry.py \
  --source-dataset /path/to/pilot/dataset \
  --work /path/to/static-clean --colmap /path/to/colmap
python3 scripts/video_to_splat.py --stage train \
  --dataset /path/to/static-clean/dataset --output /path/to/static-training \
  --brush /path/to/brush_app --steps 8000 --train-resolution 1920 \
  --max-splats 400000 --eval-split-every 10
```

Use a fresh work directory and retain the accepted scene during the comparison.
Add `--preserve-poses` to the cleanup command to skip bundle adjustment and keep
both the original camera poses and the retained points' original coordinates.
Point filtering remains identical, allowing its effect to be tested separately.
`quality.json` records removed points, frozen cameras, actual reprojection errors
and camera-pose changes. Geometry must remain connected and pass the accuracy
checks before training. Cleaner inputs do not guarantee a better splat: compare
the same held-out images and identical viewer camera positions before publishing.

The [controlled comparisons](docs/static-cleanup-comparison.md) tested cleanup
with refined poses and with original poses. Both produced smaller models but no
clear visual gain. The published scene remains the accepted baseline; neither
cleanup candidate was promoted.

### Post-training cleanup

`scripts/prune_splat_candidates.py` exports reversible candidates from a trained
PLY by filtering needle-shaped Gaussians or large, faint, isolated Gaussians.
It preserves retained records exactly and saves excluded records separately.
The [three-candidate experiment](docs/post-training-cleanup.md) found no clear
visual improvement; these filters are diagnostic tools, not proven ghost detectors.

The [ranked ghosting research and fallback options](docs/ghosting-options.md)
preserve 26 approaches, ordered by suitability for this recording, with source
links, implementation limits, prior failures, and criteria for revisiting each.
The ranking is a research assessment; no new method is claimed as validated.

`scripts/score_splat_contributions.py` implements the first option as reversible,
source-verified opacity reduction. The [two-candidate experiment](docs/contribution-cleanup.md)
passed its implementation checks but did not visibly resolve the dominant ghosts.
The accepted scene is unchanged; usage, limitations and preserved evidence are
documented for a future experiment with stronger source or depth evidence.
