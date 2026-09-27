# Floor-reference diagnostic — September 27, 2026

[Open the interactive review](https://parhamdb.github.io/sepehrbaba/floor-drift.html)
or [watch the sampled overlays](https://parhamdb.github.io/sepehrbaba/floor-drift/samples.mp4).
These source images contain graphic human-rights documentation.

The floor is useful as a consistency reference, but it does not establish a
correct camera path by itself. This experiment measures the completed full-video
DA3 candidate without changing cameras, depth, splats, or existing scene joins.

## Result

- 100 frames: 50 anchors spaced 15 seconds apart, each with a neighbor roughly
  one second later, from 0 to 735.996 seconds of the 737.301-second recording.
- 87 proposed floor planes; 13 samples lack sufficient mask/depth/plane support.
- Median plane-normal difference from the first reference: **42.23 degrees**.
- Last supported camera-to-floor distance, in reconstructed world units:
  **0.00000582 times the first sample's distance**. This roughly 172,000-fold
  collapse is a strong consistency warning, not a physical measurement.
- 1,246 scheduled floor-feature pairs: 50 nearby and 1,196 distant. Only the
  first nearby pair passed the conservative image-matching screen. No distant
  pair passed, so this experiment provides **no verified cross-segment anchor**.

For the supported 0.000–1.017-second pair, eight spatially distinct held-out
floor features have a median homography error of **0.86 pixels** at 540×960.
DA3 depth-and-camera reprojection error is **12.70 pixels** at that resolution.
On those same held-out correspondences, median epipolar error at the original
1080×1920 resolution is **22.74 pixels for DA3** and **0.86 for COLMAP**.
Homography, depth reprojection and epipolar errors are different measurements;
compare the two methods only within the epipolar measurement.

The floor masks, all five contact sheets and the supported correspondence overlay
were visually inspected. The first pair's points lie on visible pavement and
cracks. Masks generally exclude people and body coverings, but some blur-heavy
frames and boundaries are uncertain. This is an overview review, not pixel-level
annotation or independent certification of every match.

There are visible curbs, transitions from road to tiled surfaces, and indoor
areas. A single common-level plane is therefore a **diagnostic hypothesis**, not
an established property of the entire recording. Real levels, slopes, segmentation
errors and depth errors can all affect the plane measurements. The sustained
scale collapse and the first-pair feature disagreement warrant investigation;
they do not justify automatically flattening the scene.

## Reproducible method

1. Fix sample timestamps before inspecting errors. SAM3.1's native image detector
   proposes masks from the prompts `floor` and `ground`, independently per frame.
   Use the existing cached checkpoint; no credential is accepted or recorded.
   Thor uses the established CPU ROI Align fallback, including tuple box inputs.
2. Preserve every source timestamp and hash. Erode mask edges. For plane fitting,
   retain finite positive depths and the higher-confidence half of masked pixels.
   Use DA3's exported depth and cameras in their existing optimized global gauge.
   Verify exported intrinsics against the per-frame depth calibration.
3. Fit a robust local plane with 160 deterministic RANSAC trials, at most 4,000
   points, a 1.5%-of-median-depth tolerance, at least 300 inliers, and 65% consensus.
   Normalize local coordinates during fitting so tiny monocular scales do not
   create false degeneracy. Compare plane orientation and signed plane distance
   against the first supported reference. Offset is normalized by the candidate's
   estimated camera-to-plane distance; it is **not meters**.
4. Project one fixed reference grid onto the images. It is never refitted per
   frame. Yellow grid may disappear when the assumed reference plane is behind
   the camera or outside the masked region, and can alias at shallow angles.
5. Extract SIFT features only inside eroded floor masks at 540×960. Require mutual
   matches and a 0.7 descriptor ratio. Deduplicate locations within three pixels
   in either image before splitting training and held-out landmarks. This avoids
   counting multiple SIFT orientations at the same corner as independent evidence.
6. Require 20 distinct matches, at least 12 fitting and four held-out points,
   12 homography inliers, 0.5% image-area spatial support, held-out median below
   three pixels and p90 below eight. Candidate selection does not use DA3/COLMAP
   errors. Check camera predictions afterward; retain rejected/unsupported pairs.
7. Compare COLMAP only when both frames belong to the same frozen component.
   Separate components have independent coordinates and are not joined by this
   diagnostic. DA3 depth reprojection mixes depth and camera error.

```sh
python scripts/floor_mask_samples.py --images NATIVE/images \
  --frames NATIVE/frames.json --output MASKS
python scripts/check_floor_drift.py --images NATIVE/images --masks MASKS \
  --inference FULL_DA3/inference --comparison FROZEN_COMPARISON.json.gz \
  --snapshot FROZEN_SNAPSHOT.json.gz --native NATIVE --output REVIEW
python scripts/render_floor_review.py --output REVIEW
```

Use the SAM environment for masks and the DA3 environment for geometry. The
mask command can continue the identical selection; geometry requires a new
output directory. When only plane fitting changes, `--reuse-pairs PREVIOUS/report.json`
preserves feature results after checking source-image, mask, depth, pose and
selection identities; keep the same frozen COLMAP reference inputs as well.

[All measurements](../public/floor-drift/report.json) contain per-sample hashes,
mask-checkpoint identity and unsupported outcomes. [Mask proposals and selection
metadata](../evidence/floor-drift/masks.tar.gz) let contributors inspect or replace
the masks. [Validation ledger](../evidence/floor-drift/validation.json) separates
algorithm checks, artifact review and website checks. Raw host logs stay private.

## What this does not establish

A flat plane cannot reveal translation along itself or rotation about its normal.
Repeated tiles can give false matches. Phone height need not stay constant.
Masks identify visible surfaces, not motion or historical truth. This sparse
diagnostic does not verify all source frames, recover unseen geometry, certify
camera continuity, or modify documentary source material.

Next work: inspect accumulated DA3 similarity scales and anchor reliable static
floor features to trusted COLMAP components; use shorter frame intervals or
stronger matching to improve cross-segment support. Corrections are a separate
experiment and must preserve this uncorrected baseline for comparison.
