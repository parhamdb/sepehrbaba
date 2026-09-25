# Recovering the larger component and remaining recording

This campaign preserves the failed full-recording attempt and the accepted
18-second public pilot. Its first deliverable is a separately labeled **186–257 s**
preview, if geometry and visual checks pass. The next step attempts overlapping
windows across the recording. No disconnected geometry is forcibly joined.

## Numerical repair

The failed model had 1,041 cameras and 346,215 points. Recomputed projections
identified six invalid points contributing six behind-camera observations in
two images. One depth was nearly zero, making its projection enormous. The mean
over the other observations was 1.1991 px. This diagnosis does not validate the
model's unobserved surfaces or solve missing camera coverage.

`scripts/sanitize_geometry.py` checks actual projections, removes whole point
tracks with nonpositive depth, nonfinite projection, or residual above 100 px,
and removes their reciprocal image associations. It keeps camera parameters,
image inventory and feature coordinates. In this run the first pass removes six
points and twelve associations. It does not remove pixels from the source video.

The complete repair, geometry assessment and conditional undistortion are available
as one command. Use a fresh output directory:

```sh
python3 scripts/recover_component.py --source-model work/failed/model-text \
  --source-run work/native --work work/recovery --colmap /path/to/cuda-colmap \
  --start 186 --end 257
```

The individual numerical steps, for inspection or manual recovery, are:

```sh
python3 scripts/sanitize_geometry.py --source-model work/failed/model-text \
  --output work/recovery/sanitized-before
colmap model_converter --input_path work/recovery/sanitized-before \
  --output_path work/recovery/filtered-bin --output_type BIN
colmap bundle_adjuster --input_path work/recovery/filtered-bin \
  --output_path work/recovery/refined
colmap model_converter --input_path work/recovery/refined \
  --output_path work/recovery/refined-text --output_type TXT
python3 scripts/sanitize_geometry.py --source-model work/recovery/refined-text \
  --output work/recovery/sanitized-after
colmap model_converter --input_path work/recovery/sanitized-after \
  --output_path work/recovery/final-model --output_type BIN
```

Create the COLMAP output directories before invoking its commands. Sanitizer
outputs must be fresh. The second sanitization is recorded separately in case
refinement introduces new invalid tracks. Do not silently overwrite the input.

Assess the final text model with `repair_scene.assess`, using **every native
frame whose timestamp is in [186, 257)** as the selected inventory. Require the
same 90% coverage, 1,000-point, 1.5 px mean, 3.5 px p95 and zero-behind-camera
thresholds as the pilot. Also retain the whole-recording fraction: passing this
71-second interval does not turn 8.1% into full-video coverage.

If geometry passes, undistort at maximum edge 1920, run `mask_people.py`, inspect
masks, and use `video_to_splat.py --stage train` with 8,000 steps, maximum edge
1920, 500,000-splat cap and every tenth image held out. The current semantic masks
also exclude stationary human content; that limitation remains.

Use `python3 scripts/inspect_masks.py work/recovery/dataset work/mask-review.jpg`
to verify the full image/mask inventory and generate source/overlay pairs sampled
across the interval, including the smallest and largest excluded regions. Red
marks excluded pixels. Review the sheet before training; file validation alone
does not establish correct segmentation. The helper was checked on all 252 masks
of the retained pilot; that does not validate the new component's masks.

## Overlapping-window continuation

```sh
python3 scripts/recover_windows.py --source-run work/native \
  --database work/full-recording/database.db \
  --bootstrap-models work/native/sparse \
  --extra-seed work/recovery/final-model --work work/windows \
  --colmap /path/to/cuda-colmap --plan-only
# Inspect the plan; remove --plan-only to execute it.
```

The plan covers all 12,793 frames with 90-second windows and 30-second overlap.
It reuses the largest retained seed wholly inside each interval. If none exists,
it attempts bootstrap mapping of that interval's existing sharp keyframes. Each
interval then uses the native-frame repair command with **no time limit**.

A single sequential process shares one private copy of the match database across
windows. The source database stays unchanged. Each window has separate logs,
models, snapshots and a measured outcome. A failed window does not stop independent
windows; no failed geometry is automatically trained or published. Disk and memory
resource safeguards remain. These are attempts to recover coverage, not a promise
of a single connected final scene.

The September 25 campaign was launched with the sanitized `filtered-bin` seed
while the larger component's refinement was still running. The retained source
models and match database remain unchanged. Its first interval is 0–90 seconds;
all 12,793 source frames are included somewhere in the window plan. This is a
running experiment, not an accepted reconstruction of the full recording.

## Frozen acceptance inventory

| ID | Required evidence |
| --- | --- |
| R1 | Invalid point removal preserves camera/feature data and reciprocal track consistency |
| R2 | Repaired interval passes the unchanged measured geometry thresholds |
| R3 | Inspected masks and a separate completed 8,000-step model |
| R4 | Complete held-out inventory plus source/render and browser navigation inspection |
| R5 | A separately labeled public candidate, with original pilot preserved |
| R6 | Full-frame window plan checked and its sequential recovery campaign launched with retained results |

One discovery pass, focused checks of actual failures, and one final candidate
verification are allowed. No more than two viewer builds. Keep long-running
window recovery monitorable; do not impose an elapsed-time stop on it.
