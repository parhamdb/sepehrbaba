# Reconstructing the Sepehr Baba recording

This is the reproducible method for the [preserved source recording](../evidence/README.md),
not a claim that the entire recording or all visible people have been reconstructed.
The current public artifact covers 199–217 seconds. The
[180–240 second expansion](expansion-60s.md) is a separate candidate.

## Pipeline and committed tools

| Stage | Tool | Output / boundary |
| --- | --- | --- |
| Acquire and verify source | Git LFS, `evidence/source/SHA256SUMS` | Exact acquired MP4, retained audio, metadata and provenance |
| Preserve all frames and recover bootstrap cameras | `scripts/full_video.py` | Native-size JPEGs, original presentation timestamps, features/matches, separate camera components |
| Expand/refine a bounded connected component | `scripts/repair_scene.py` | Copied database, bundle-adjusted cameras, measured geometry gate, undistorted dataset |
| Exclude detected people during environment fitting | `scripts/mask_people.py` | Inspected masks; also excludes some stationary people |
| Train and validate an export | `scripts/video_to_splat.py --stage train` | Brush Gaussian PLY, run fingerprint, held-out renders |
| Inspect native Brush evaluation | `scripts/inspect_brush.py` | Pixel-pooled static-region PSNR and source/render contact sheet |
| Prepare matched browser evaluation | `scripts/prepare_references.py` | Portable camera poses, explicit split, resized RGB/masks and manifest |
| Render the PLY in the browser engine | `scripts/render_evaluation.mjs` | PNGs with a capture manifest; no publication |
| Measure browser output | `scripts/evaluate_renders.py` | Per-view static PSNR; not a geometry/visual acceptance test |
| Compare cleanup hypotheses | `clean_static_geometry.py`, `prune_splat_candidates.py`, `score_splat_contributions.py` | Separate reversible candidates; see linked failed experiments |
| Publish an accepted scene | `scripts/build.mjs`, `.github/workflows/pages.yml` | GitHub Pages viewer, model and coverage metadata |

The older sampling path in `video_to_splat.py --stage prepare` remains available
for diagnostics. The native-frame method uses `full_video.py` and `repair_scene.py`.
Do not confuse the older sampling path's looser geometry gate with pilot acceptance.

## Environment and setup

Verified tool versions: COLMAP **3.12.6 with CUDA**, Brush **0.3.0**, PlayCanvas
**2.22.3**, SuperSplat Viewer **1.32.0**. The viewer uses the committed npm lockfile
and Node 24 in CI. Thor is Linux ARM64 with NVIDIA drivers; observed ML packages
were PyTorch 2.10.0, torchvision 0.25.0, NumPy 2.4.2 and Pillow 10.2.0.

```sh
git lfs pull --include='evidence/source/*.mp4'
sha256sum --check evidence/source/SHA256SUMS
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
bash setup.sh
```

`setup.sh` installs distro FFmpeg/COLMAP and a checksum-verified Brush binary on
x86_64; on ARM64 it builds a pinned Brush commit with an existing Rust toolchain.
It invokes sudo and may build software. `bash setup.sh --brush-only` skips the
basic FFmpeg/COLMAP installation. **The distro COLMAP may lack CUDA**; the native
workflow requires a working CUDA build supplied via `--colmap`. Check its version,
runtime libraries and GPU support before beginning. Setup does not install a
CUDA toolkit, drivers or ML wheels. Choose platform-compatible Torch/torchvision
wheels before using `requirements-ml.txt`; preserve working vendor environments.

The acquisition URL remains documented, but reconstruction should use the
hash-verified archived copy rather than silently downloading a changing source.
Work on a copy, for example `cp evidence/source/sepehr-baba.mp4 work/input.mp4`
after creating `work/`. Do not modify the preserved MP4.

## Reproduce the accepted pilot method

```sh
python3 scripts/full_video.py evidence/source/sepehr-baba.mp4 \
  --work work/native --colmap /path/to/cuda-colmap --max-seconds 7200

# Choose a recovered seed whose cameras lie within 199–217 seconds.
python3 scripts/repair_scene.py \
  --source-run work/native --database work/native/database.db \
  --seed-model /path/to/seed-model --work work/pilot \
  --colmap /path/to/cuda-colmap --start 199 --end 217 --max-seconds 900

python3 scripts/mask_people.py work/pilot/dataset
# Inspect masks against the source before proceeding.
python3 scripts/video_to_splat.py --stage train \
  --dataset work/pilot/dataset --output work/pilot-training \
  --brush /path/to/brush_app --steps 8000 --train-resolution 1920 \
  --max-splats 500000 --eval-split-every 10

python3 scripts/inspect_brush.py work/pilot/dataset \
  work/pilot-training/splats/eval_8000 work/pilot-native-evaluation --expected-views 26
```

Bootstrap recovery is not deterministic and may return disconnected components.
There is no claim that every fresh run automatically finds the same seed.
The historical accepted run continued a retained 199–217-second mapper snapshot;
its final model registered 252/271 frames. Commands, inputs and failure snapshots
must be retained when establishing a new seed. Do not join disconnected models
or lower thresholds merely to reach training.

Every source frame is retained as JPEG quality 1 with its timestamp; this is
high-quality **lossy** extraction, not bit-exact image preservation. The MP4 is
the authoritative acquired byte sequence. Adjacent frames help tracking but are
not independent ground-truth viewpoints. The baseline's 26 held-out views are
also temporally close to training frames, which limits what their scores prove.

## Portable browser/source evaluation

Convert the **undistorted** dataset model, not the original distorted model:

```sh
mkdir -p work/pilot-model-text
/path/to/colmap model_converter --input_path work/pilot/dataset/sparse \
  --output_path work/pilot-model-text --output_type TXT
python3 scripts/prepare_references.py --dataset work/pilot/dataset \
  --model-text work/pilot-model-text \
  --held-out-renders work/pilot-training/splats/eval_8000 \
  --training-state work/pilot-training/state.json \
  --output work/references --max-edge 946
npm ci
npx playwright install chromium
node scripts/render_evaluation.mjs --ply public/assets/preview.ply \
  --views work/references/views.json --split held-out --output work/browser-renders
python3 scripts/evaluate_renders.py work/references work/browser-renders \
  --split held-out --output work/browser-metrics.json
```

Use the PLY trained from the same camera coordinate system as the references;
the published baseline is suitable only for its matching pilot model. Reference
export supports centered, square-pixel PINHOLE/SIMPLE_PINHOLE intrinsics and applies
the viewer's 180-degree Z rotation. Unsupported cameras fail explicitly. Masks
use zero for ignored pixels. Source JPEGs are resized at quality 95 for this
evaluation format, so browser metrics are not identical to native Brush metrics.

`--train-stride 20 --include frame_003139 frame_003140 frame_003269` produces the
training subset used by the contribution experiment, with actual held-out
membership retained. [Its regions](../experiments/contribution-cleanup/regions.json)
are proposals for artifact localization, not verified semantic ghost labels.
The new exporter replaces a historical helper with hard-coded paths/intrinsics;
it is not claimed to reproduce its JPEG bytes exactly.

The browser renderer pins configuration and uses a fresh page per pose, bounded
capture time, and repeated stable pixels. This reduces capture-history errors
but does not certify sorting correctness. The actual product viewer must still
be inspected with nearby camera motion. Capture failures are failures, not
missing views to omit from a metric. All outputs require fresh directories.

Native `inspect_brush.py` pools pixel error across all renders; browser
`evaluate_renders.py` reports an equal-view mean PSNR. Do not compare these
aggregations, different source encodings, different view inventories or different
renderers as though they were the same metric. The accepted native baseline is
22.3286 dB on unmasked static pixels; this says nothing about masked people.

## Acceptance, provenance and contributions

Geometry gates require at least 90% of interval frames, 1,000 points, mean residual
≤1.5 px, p95 ≤3.5 px, and zero associated points behind cameras. Then inspect masks,
held-out renders and actual browser navigation. Keep readable coverage labels and
known artifacts. The current pilot is not a measured survey or forensic certification.

Commit reusable scripts, parameters, findings and artifact manifests. Keep machine
paths and credentials out of public examples. Store large intermediate artifacts
outside Git with hashes and retrieval instructions. The one deliberate source-media
exception is the hash-identified MP4 in Git LFS. The current accepted PLY is tracked
as a regular Git asset so Pages can serve it directly.

See [CONTRIBUTING](../CONTRIBUTING.md), [provenance](provenance.md),
[static cleanup](static-cleanup-comparison.md), [post-training cleanup](post-training-cleanup.md),
[contribution cleanup](contribution-cleanup.md), and the [ranked research](ghosting-options.md).
Failed methods are part of the record and should not be silently erased.
