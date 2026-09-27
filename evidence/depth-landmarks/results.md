# Depth-aware human landmark experiment

**Two camera hypotheses were produced and rejected by the frozen checks. No
section alignment or scene join was applied.** The six user-selected matches
remain recorded hypotheses, including Q5→1. This experiment does not prove which
observations, depths or motion assumptions are wrong.

**[Watch both camera-projection overlays](https://parhamdb.github.io/sepehrbaba/depth-landmark-review.html)**
· [Complete numerical record](evaluation.json)
· [Exact source mapping and thresholds](experiment.json)
· [Original human choices](../numbered-landmarks/human-choices.json)

## Actual run

We reused cached DA3 depth/poses and ran CoTracker3 on two separate 21-frame
windows: **409.736733–410.738200 s** and **414.913478–415.994922 s**. Each includes
ten frames before and after its selected seed, 410.237478 s and 415.494189 s.
The reverse tracker is seeded from the predicted final view and checked back
against the original seed. Both directions within each window were inferred;
no tracker was run through the missing interval. CoTracker GPU inference took
about 2.1 seconds per window, including the reverse pass. No full-video inference
or splat training was launched.

Camera estimates use all six human seed pairs. The primary fit shares one lens
matrix (median cached intrinsics over the 42 views), respecting the fixed-lens
hypothesis. A separate cached-intrinsics sensitivity fit is reported without
selecting a winner. We unproject 3×3 median depth samples, normalize 3D coordinates
by median seed depth for numerical stability, solve SQPnP and refine with LM.
Each leave-one-point-out fit uses only the other five correspondences. Both
before→after and after→before camera solves are independent; the second is not
constructed by inverting the first.

Nearby target views are excluded from camera fitting. We propagate the candidate
with existing within-side DA3 relative camera motion and compare its projections
with tracks. This is a temporal consistency test on the same six points. It is
not independent validation by other objects, and cached camera motion may be wrong.

## Results

All values below are **native-image pixel errors**. The predeclared projection
limit is 5 px. Seed-fit errors are training residuals, not validation scores.

| Point | Earlier→later seed fit | Earlier→later excluded point | Later→earlier seed fit | Later→earlier excluded point |
|---|---:|---:|---:|---:|
| Q1 | 13.43 | 20.32 | 6.74 | 11.17 |
| Q2 | 3.14 | 4.06 | 2.09 | 2.85 |
| Q3 | 20.60 | 28.57 | 12.47 | 17.03 |
| Q4 | 1.80 | 321.07 | 2.16 | 100.91 |
| Q5 | 4.63 | 19.96 | 0.60 | 4.23 |
| Q6 | 16.61 | 29.06 | 11.29 | 16.82 |

Neither direction passes all six seed points or the excluded-point tests. Changing
from the shared lens to individual cached lens estimates does not resolve this.
The independent forward/reverse fits disagree by **14.62° in rotation**.

After track-quality screening, withheld target views have median errors of
**18.37 px over 21 usable observations** in the earlier→later direction and
**8.05 px over 39** in the reverse direction. These are observations of repeated
points, not 60 independent landmarks. The existing source-side camera/depth
projection itself has about **5.1 px median error** against usable local tracks.
Thus the local inputs already have measurable uncertainty.

The median predicted-versus-cached target-depth discrepancies are **13.25%** and
**5.95%**, respectively. At the frozen 10% depth diagnostic limit, 0/21 and 36/39
usable observations pass. These checks share the DA3 model and are not independent
physical measurements.

Earlier seed depth confidence scores lie around the **13th–27th percentiles** of
that frame's score distribution. Later seed points are mostly in the 82nd–99th
percentiles, with Q4 around the 24th. Scores are not calibrated probabilities.
Low earlier confidence is a reason to distrust that depth prior, not a reason to
alter the user's selections.

Full-window return checks support only Q1/Q2/Q6 on the earlier side and Q1/Q2 on
the later side. Other trajectories remain visible as unreliable hypotheses;
Q5 leaves the later image. Per-frame agreement alone cannot pass a track whose
reverse endpoint is forced by the predictor: the original-seed return and both
visibility checks must also pass the 5 px limit. Original human seed observations
remain yellow even when their subsequent track fails.

**Independent stationary-object validation is unavailable.** All six points cover
one local flexible region. Prior searches did not establish a separate verified
cross-gap floor landmark. This blocks a verified camera connection regardless of
how well a candidate fits these six points. Further progress needs better depth
or nearby-view triangulation plus spatially separate stationary observations.

## How to read the overlays

Each movie contains the same 21 original samples per side, displayed at 4 fps for
5.25 seconds. Source timestamps stay visible. The two windows run side by side;
there is no generated intermediate camera path. Native frames are cropped for
readability, preserving aspect ratio. The full source recording remains the
original evidence, linked from the main README.

- Yellow circles: the user's seed points. Green: tracks passing return, visibility,
  bounds and per-frame cycle screens. Grey: an unreliable predicted track.
- Cyan crosses in the source panel: projections from existing local DA3 motion.
- Magenta crosses in the target panel: projections from the candidate PnP camera,
  propagated using cached local motion. Lines connect observations and predictions.
- Out-of-crop or behind-camera projections are counted rather than clipped to a
  misleading edge. Grey-point errors are displayed but excluded from the temporal
  usable-observation summaries.

## Mapping and reproducibility

A source name is **not** its depth index. `frame_006454.jpg` maps to
`frame_6453.npz`, and `frame_006548.jpg` maps to `frame_6547.npz`. All 42 mappings
were checked against ordered pose names and image hashes. We reproduced upstream
image preprocessing (1080×1920 → 284×504 → 280×504) and compared it to the image
stored beside depth. Maximum mean absolute image difference was **0.420/255**.
This is small denormalization/quantization difference, not a frame substitution.
The native intrinsic mapping was checked against each NPZ intrinsic matrix.

Pinned upstream DA3 export multiplies later-chunk depths by the cumulative
optimized Sim3 scale; camera export uses the same transforms. The first chunk is
the reference. Depth and translations therefore share the cached reconstruction's
arbitrary scale. Numbers are not measured metres. No existing cache was edited.

[CoTracker3](https://github.com/facebookresearch/co-tracker) revision
`82e02e8029753ad4ef13cf06be7f4fc5facdda4d` and its retained offline checkpoint were
used through the existing tracking script. Exact model, script, selection and
checkpoint hashes are retained in both track files. DA3 cache provenance is in
[da3-cache-provenance.json](da3-cache-provenance.json). OpenCV 4.11.0 was used;
[OpenCV documents the 3D-to-2D PnP model and refinement methods](https://docs.opencv.org/4.13.0/d5/d1f/calib3d_solvePnP.html).
The evaluation records library versions and script/input hashes. The overlay
manifest records renderer/evaluation hashes and each movie's hash.

```bash
python3 scripts/prepare_depth_landmarks.py \
  --images ORIGINAL_NATIVE_IMAGES --da3 DA3_EXPORT \
  --numbered evidence/numbered-landmarks --output runs/depth-landmarks
# Use a compatible Torch/CUDA environment with official CoTracker on PYTHONPATH.
python3 scripts/track_landmark_local.py \
  --images ORIGINAL_NATIVE_IMAGES --selection runs/depth-landmarks/before-selection.json \
  --seed runs/depth-landmarks/before-seed.json --checkpoint COTRACKER_CHECKPOINT \
  --model-repo COTRACKER_CHECKOUT --output runs/depth-landmarks/before-tracks.json \
  --crop 0 300 650 1100 --padding-frames 10
python3 scripts/track_landmark_local.py \
  --images ORIGINAL_NATIVE_IMAGES --selection runs/depth-landmarks/after-selection.json \
  --seed runs/depth-landmarks/after-seed.json --checkpoint COTRACKER_CHECKPOINT \
  --model-repo COTRACKER_CHECKOUT --output runs/depth-landmarks/after-tracks.json \
  --crop 450 500 1080 1450 --padding-frames 10
python3 scripts/evaluate_depth_landmarks.py \
  --experiment-dir runs/depth-landmarks --da3 DA3_EXPORT \
  --output runs/depth-landmarks/evaluation.json
# The retained numerical record can be checked without DA3 or a GPU:
python3 scripts/verify_depth_landmarks.py evidence/depth-landmarks
python3 scripts/render_depth_landmarks.py --images ORIGINAL_NATIVE_IMAGES \
  --experiment-dir evidence/depth-landmarks --output runs/depth-overlay
```

No tokens, private host names or personal configuration are required by these
scripts or included in the published evidence. Source images remain untouched.
