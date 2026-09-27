# Local camera recovery: gap 098

This campaign tests the missing-camera interval **412.290311–414.512889 s**.
The previous static-mask experiment showed usable image features but too few
landmarks consistent with fixed reference cameras. The next question is whether
matches are wrong or camera geometry is wrong.

Freeze **61 native frames**: every frame from 412.0 through 414.9 seconds, plus
the earlier gap-098 anchors and controls. Generate/reuse SAM static-surface masks
with identical settings, then match every image pair without using camera poses.
Keep the raw LightGlue cache so alternative geometry checks do not rerun inference.

A local VGGT-SLAM run uses every supplied frame (`--every-frame`), preserving
native IDs and full portrait field of view. Full-recording DA3 outputs are reused.
COLMAP references remain separate component gauges; do not evaluate a relative
pose between disconnected components as if they shared coordinates.

## Independent image geometry and shared-lens trials

Split matched features by original first-image SIFT ID modulo five. Fit only on
four folds; the fifth fold evaluates each pair. This is a **per-pair** holdout,
not a global independent test set for a trajectory or later bundle adjustment.
Require 12 fitting homography inliers or positive-depth relative-pose inliers,
six withheld matches, at least 0.5% image-area coverage in both views, median
withheld error below 3.5 native pixels and p90 below eight.

Fit a homography and a calibrated essential matrix independently of the old
camera poses. Hold one lens calibration fixed across each trial: the earlier
reference calibration is primary; the later calibration is a declared sensitivity
trial. Do not select the lens using withheld residuals. The physical lens is the
same, but the original reconstructions estimated slightly different focal lengths
and distortion. Shared calibration is a hypothesis, not a known measurement.

Score original COLMAP, full DA3 and local VGGT on the **same withheld points**,
using their native calibrations. Camera epipolar error is invariant to component
scale; a near-zero numerical gauge must not be mistaken for no physical baseline.

A supported homography is evidence for a planar explanation. Essential-matrix
pose recovery gives translation direction without metric scale and can be
ambiguous on a plane. Neither a passing homography nor low epipolar error alone
certifies a recovered 3D camera or scene connection. Inspect correspondences,
then require multi-view evidence before accepting a recovered pose.

## Reproduce

- `match_static_clip.py`: cache masked native SIFT/LightGlue pairs from a frozen selection.
- `evaluate_local_camera_pairs.py`: independent H/E fits and same-point camera comparison.
- `run_vggt_loss.py --every-frame`: bounded local VGGT comparison on the selected frames.

Existing reader, camera state, database and cached weights are runtime inputs;
public evidence records hashes and native IDs without private paths or credentials.

## Frozen validation inventory

One discovery pass, focused failure checks, one final pass; reuse unchanged neural
inference and its raw-match cache. The in-scope target is a verified local camera
recovery if the data supports it, otherwise a precisely documented evidence gap.
Full-video inference, scene stitching and splat retraining are excluded.

1. Four unit controls: correct plane, shuffled holdout rejection, nonplanar relative
   pose, and camera-error invariance to tiny coordinate scale.
2. All selected masks and all-pairs cache complete with source provenance.
3. Local VGGT/native frame identity and COLMAP/DA3 comparison availability verified.
4. Inspect independent geometry, candidate correspondences and recovery connectivity;
   do not turn planar ambiguity or unavailable estimates into passes.
5. Commit scripts, observations, limitations and privacy-checked results.
