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

## September 25 recovered component

The repaired 186–257 s component passed geometry checks: **1,041 / 1,067**
eligible frames (97.56%), 346,209 sparse points, mean residual **1.1989 px**,
p95 **2.4683 px**, and zero behind-camera observations. All 1,041 masks passed
inventory/dimension checks. Eight sampled source/overlay pairs were inspected;
foreground people are largely excluded, with some missed limbs and exclusion
of static human details. This is an experimental mask policy, not an accurate
classification of all people or evidence.

Training completed all **8,000 steps**, with **936 training views**, **105 held-out
views**, maximum image edge 1920, and **500,000 Gaussians**. The complete held-out
inventory was verified against Brush's actual split. Static-region PSNR is
**22.0874 dB**, over unmasked pixels only. It does not measure masked human details
or establish accurate novel-view geometry. Sampled source/render pairs show useful
central detail and pronounced blur at occluded ends and around people.

The separate [experimental viewer](https://parhamdb.github.io/sepehrbaba/?scene=recovery-71s)
uses `public/experiments/recovery-71s.json`; the default pilot asset and camera are
unchanged. The candidate PLY is 118,001,551 bytes, SHA-256
`02b746a41c81e707917b03da4713c07b6bee0e40d0139e01c0b79748f541bb43`.
It is stored in Git LFS; the Pages workflow explicitly fetches this asset before
building. Local builds also require `git lfs pull --include="public/assets/recovery-71s.ply"`.

All five local browser checks passed: pilot desktop/mobile navigation, missing
manifest recovery, and expanded desktop/mobile rendering and movement. Entry and
movement screenshots were inspected. Three additional poses translated the camera
and target by ±0.25 on scene X and +0.25 on scene Y, relative to `frame_003348`.
These are arbitrary reconstruction units, not meters, and synthetic viewpoints,
not additional held-out source observations. Central surfaces remained recognizable;
blur and distortion increased off the recorded view. This supports an experimental
preview, not a claim that the scene is geometrically accurate throughout.

The batch capture browser closed during its second pose. The first result was
retained; the remaining poses succeeded with separate `render_evaluation.mjs
--only IMAGE_NAME` invocations, each in a fresh browser. Use this workaround for
reproduction; the multi-pose capture failure has not been fixed. Walking forward
can pass through surfaces because the viewer does not supply collision geometry.

The full-video campaign remains independent. As of 21:40 UTC, September 25,
windows 0–90 s and 60–150 s finished but failed the unchanged coverage threshold
(303/1,352 and 356/1,361 frames respectively). Their residuals were low and their
partial models were retained. Window 120–210 s was still mapping. No disconnected
models have been forced together, and completed attempts are not accepted coverage.

## Display orientation

COLMAP's arbitrary coordinate axes left the expanded scene tilted relative to the
viewer's vertical axis. `scripts/level_scene.py` estimates a floor plane from the
two manually selected regions in `docs/floor-selection-71s.json`. The regions are
visible floor pixels in undistorted frames 003314 and 003348. Of 79 unique sparse
points, 51 support the plane within 0.015 scene units; the fitted RMS residual is
0.00749. The estimated up direction differs from the previous viewer up by 27.28°.
This is approximate display leveling, not a surveyed gravity measurement.

The manifest records the selection, original camera, fitted normal and rotation.
The viewer rotates the splat entity before measuring its bounds, and uses the
same rotation for the camera. The opening ray is unchanged; its orbit centre is
moved to the fitted floor intersection, about 1.21 arbitrary scene units away.
Orbit, free movement and reset therefore share one upright coordinate system.
The PLY, its hash, original video and reconstruction geometry are unchanged.
Opening the raw PLY in another application still uses its original coordinates.

To reproduce from the original viewer manifest and undistorted model export:

```sh
git show 2bb5e31:public/experiments/recovery-71s.json > work/unleveled-scene.json
python3 scripts/level_scene.py --model-text work/recovery/dataset-model-text \
  --scene work/unleveled-scene.json --selection docs/floor-selection-71s.json \
  --output work/leveled-scene.json
```

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
