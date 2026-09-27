# Connect sections while skipping gap 098

This experiment excludes the missing frames at 412.290311–414.512889 seconds.
It attempts to align the existing before/after components directly; it does not
reconstruct, interpolate or certify the camera's movement during the gap.

The earlier component contains 78 registered cameras spanning
408.134389–412.230244 s; the later contains 235 spanning
414.562967–427.800311 s. `select_skipped_gap_bridge.py` examines these 313 source
images and freezes the two highest whole-image Laplacian-variance images per
one-second bin: **10 before, 28 after**. The 30-second search bound cannot extend
a component beyond its actual registered observations. Sharpness is a selection
proxy and is not evidence of static architectural texture.

Reuse unchanged SAM 3.1 floor/ground/wall-minus-person masks where the source
hash agrees, infer the rest, then run the existing native SIFT + LightGlue
matcher on all 703 pairs (including 280 cross-gap pairs and within-side pairs).
No cameras filter or select the image matches. Keep the raw cache.

## Alignment method and acceptance

Read both COLMAP models without modifying them. Associate native SIFT indices
with their exact reconstructed observations; reject coordinate disagreement.
Existing landmarks require at least three observations and ≤2.5-pixel map error.
Descriptor support must remain inside the static masks, as in the prior campaign.

Two declared variants share the cache and criteria:

1. Existing reconstructed static landmarks only.
2. Add static landmarks triangulated inside each component with fixed cameras:
   ≥1-degree parallax, positive depth, <2-pixel reprojection in every associated
   selected view and at least three views. Existing landmark associations cannot
   be merged inconsistently. This tests whether the original map omitted useful
   floor features; it does not establish that its camera poses are correct.

Collect cross-component landmark correspondences. Reject whole bipartite groups
with conflicting one-to-many landmark IDs. Split entire remaining landmark groups
using a stable hash of the earlier landmark ID; all observations of a landmark
remain in one fold. Repeated views cannot inflate the distinct-landmark count.

Normalize each component by its selected camera-center median and median radius.
Fit a positive-scale similarity transform from before to after using 2,000 seeded
three-point RANSAC hypotheses. Require ≥12 fitting landmarks/inliers and ≥6
withheld landmarks; reject collinear/coincident configurations, but permit a
well-spread plane. Use 0.03 of the after-component camera radius for fitting
consensus, and withheld 3D median <0.03 / p90 <0.06 in those normalized units.

A candidate must additionally project withheld landmarks in **both directions**:
positive depth, median error <3.5 native pixels and p90 <8. Score the maximum
observation error per landmark so repeated views cannot dominate. Require ≥0.5%
image-area coverage separately in at least two images on each side. Independent
review caught and corrected pooled-across-image coverage before the first run.

Only then inspect the correspondences and transformed geometry visually before
promoting a connection. `accepted_connection` remains false in diagnostic output.
A passing planar similarity aligns the existing component gauges, not metric
world scale or unobserved motion. The original maps can still be distorted.

Independent per-pair homography/essential-matrix diagnostics use a fixed earlier
lens calibration and the prior feature-ID holdout rule. They do not filter the
3D alignment, replace its landmark-level holdout, or certify a component join.

## Frozen execution inventory and scope

Budget: one discovery pass, focused fixes at failed boundaries, one final pass;
reuse neural inference and matches. At most three distinct recovery hypotheses
for a repeated blocker; 45 minutes active work per turn.

- Numerical controls: known planar positive similarity, corrupted withheld
  landmarks, collinearity rejection, conflicting ID groups, duplicate-observation
  counts; two regression checks for incomplete caches and per-image coverage.
- Complete selected-frame/mask/pair inventory and source/model/code hashes.
- Run both declared alignment variants and record numerical evidence, including
  insufficient support as a scientific blocker rather than an accepted join.
- Inspect masks and strongest cross-section match candidates.
- Commit and publish reproducible scripts, results, limitations, and privacy-checked artifacts.

Full-video inference, missing camera recovery, new splat training and manual
landmark invention are outside scope. If an alignment passes, the minimum usable
result is a documented, inspectable transform connecting these two pieces while
retaining the unknown camera interval.

## Reproduce

Use the same installed environments as the local-camera campaign. Variables
below are runtime inputs, not private infrastructure defaults:

```sh
python scripts/select_skipped_gap_bridge.py --state "$STATE" --frames "$FRAMES" --images "$IMAGES" --output selection.json
python scripts/mask_gap_anchors.py --selection selection.json --images "$IMAGES" --output masks
python scripts/match_static_clip.py --selection selection.json --database "$DATABASE" --masks masks --lightglue "$LIGHTGLUE" --output matches
python scripts/evaluate_skipped_gap_bridge.py --selection selection.json --pairs matches/pairs.json --state "$STATE" --reader "$COLMAP_READER" --output existing
python scripts/evaluate_skipped_gap_bridge.py --selection selection.json --pairs matches/pairs.json --state "$STATE" --reader "$COLMAP_READER" --augment --output augmented
```

Each evaluator requires a complete all-pairs cache, validates the frozen selection
and state hashes, and records source model hashes. Output directories must be new.
Existing matching and triangulation dependencies are in this repository. No
source database, camera model, or published scene is overwritten.
