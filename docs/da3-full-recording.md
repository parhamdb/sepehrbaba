# Full-recording DA3 camera experiment

**Status: launched September 26, 2026; inference and cross-reference are pending.**
This run uses all **12,793 native source frames across 737.301333 seconds**.
It does not yet establish a correct continuous camera path or replace the
published 3D scenes. The earlier [connection checks](camera-connections.md)
remain unresolved.

## What runs

The pinned DA3-Streaming implementation processes the entire recording in one
run: **799 overlapping chunks**, 32 frames per chunk and 16-frame overlap,
followed by loop retrieval, loop inference/alignment, global Sim3 optimization
and camera export. The 8-frame loop setting, torch alignment and Python optimizer
match the completed short-clip experiments. No source frames are subsampled.

Native inputs are 1080×1920. DA3 internally uses **280×504 portrait views**;
using every source frame does not mean native-resolution neural inference.
Camera export retains original frame names and timestamps and maps intrinsics
back to native pixels. It checks finite matrices, proper rotations, frame counts
and preprocessing dimensions before claiming an exported trajectory.

The adapter is pinned to upstream revision
`3d835ec1a5802d64a8b8b15f817a1ab54809bfe4`, with the existing optional COLMAP-export
import patch. The checkpoint is `depth-anything/DA3NESTED-GIANT-LARGE-1.1`.
Per-run manifests hash the video, frame metadata, **actual image bytes**, model
weights/config, SALAD weights, upstream revision/diff and runner source.

## Checkpoints and storage

Each finished chunk has a content hash and an identity receipt. An explicitly
resumed run reuses only predictions with matching inputs/settings and matching
saved bytes, rebuilding upstream camera lists before alignment. Incomplete
chunks are recomputed. The estimator and loop optimizer remain upstream code;
resume may repeat alignment and final export.

Intermediate depth/geometry results are retained for recovery. A 24 GiB free-disk
reserve is checked before chunk inference and depth export. Crossing the reserve
stops the job with checkpoints retained; no automatic retry loop is enabled.
The launch environment had about 174 GiB free after a separately documented
host cleanup. No original source or reconstruction result was deleted.

`progress.json` distinguishes preflight, model loading, sequential inference,
loop retrieval/inference/alignment, geometry export, camera export and failure.
Its frame count measures completed inference coverage, **not recovered geometry**.
The enclosing pipeline has separate inference and comparison states. Source
verification or export failure must never be reported as completed recovery.

## Automatic cross-reference after inference

1. Recreate the frozen **4,946-camera COLMAP union**, verifying the reviewed
   snapshot and all 31 raw model hashes. Keep independent components separate.
2. Within each reference component, fit coordinates using the first fifth of
   shared cameras (at least five) and measure later held-out cameras. Report
   position errors relative to the initial reference span and orientation errors;
   a small span can amplify percentage errors. Insufficient support stays explicit.
3. Compare the full DA3 trajectory with each existing local VGGT window in the
   same way. Eighteen windows contain VGGT estimates; the failed nineteenth
   remains unsupported.
4. Measure COLMAP/DA3 epipolar agreement on identical observed image features,
   sampling the first eligible pair per second and reference component before
   looking at errors. Pairs never cross COLMAP components or exceed 0.75 seconds.
   Every available reference pose participates in camera checks; only this
   additional image-flow diagnostic is sampled. Empty or sparse observations
   remain unsupported, and moving people can affect image-flow scores.

These are consistency checks against estimated cameras, **not ground truth**.
No automatic connection acceptance, scene fusion, splat retraining, artificial
occlusion filling or claim of evidentiary certification is made.

## Reproduce and monitor

Use runtime paths supplied by your environment; keep host details, credentials
and private paths out of published source/results. The environment versions are
recorded with the [earlier DA3 trials](../evidence/camera-loss-benchmark/da3-packages.json).

```sh
python3 scripts/da3_full_pipeline.py \
  --checkout DA3_CHECKOUT --weights DA3_WEIGHTS --salad SALAD_CHECKPOINT \
  --images NATIVE_RUN/images --frames NATIVE_RUN/frames.json \
  --video ORIGINAL_VIDEO --native NATIVE_RUN \
  --comparison evidence/camera-comparison/inputs.json.gz \
  --snapshot evidence/camera-review/snapshot.json.gz --output NEW_FULL_RUN
```

Run as a monitored persistent job. The pipeline automatically starts camera
cross-reference after a valid complete pose export. Read `NEW_FULL_RUN/pipeline.json`
and `NEW_FULL_RUN/inference/progress.json`; private runtime logs contain detailed
upstream messages. Add `--resume` only for the same frozen inputs and runner.
A changed runner intentionally invalidates cache identity; do not bypass this
check without a separately reviewed migration.

Validation inventory: six focused checks covering frame/timestamp integrity,
actual-image cache identity, corrupted checkpoint rejection, matrix/calibration
export, temporal held-out drift and empty-image observations; live frozen-reference
preflight; launch and saved-checkpoint inspection; eventual complete export and
comparison inspection. One discovery pass, focused fixes and one final check of
the frozen scripts were used before launch. Long-running output validation remains
pending. [The ledger](../evidence/da3-full/validation.json) distinguishes these states.
