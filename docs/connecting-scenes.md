# Connecting the 48-second and 71-second scenes

[September 26 research update](reconstruction-options-2026-09.md) compares new
dense matchers, direct-splat registration and long-video trajectory alternatives.
It does not change the rejected alignment results documented here.

**Status: no defensible spatial alignment was recovered. The public scenes
remain separate.** Three approaches were investigated on September 26, 2026.
The failed candidates are preserved for contributors; their transforms must not
be used as a recovered spatial connection.

## What the recording establishes

The earlier component registers frames from **136.777533–184.795589 seconds**;
the later one registers **186.262200–256.992944 seconds**. They are consecutive
parts of the same recording, separated by **1.466611 seconds of unregistered
camera motion**. Source frames around the break show people close to the phone,
with a coat obscuring almost the entire view around 185.5 seconds.

The earlier section begins beside the brick wall and trolley and moves along
the rows of bags. The later section continues through the rows after that
occlusion. This establishes their order in the recording. It does **not** yet
establish the relative 3D translation, rotation or scale of the independent
reconstructions. A short time gap alone cannot determine those quantities.

## Measured attempts

| Method | Positive control within one component | Cross-scene result |
|---|---|---|
| Existing RootSIFT descriptors + LightGlue; 160–184.8s against 186.2–225s, sampled every 2s | 496 correctly matched known points out of 522 shared points | 247 image pairs; 2,599 candidate matches; best fit only 10 unique point pairs, no withheld-landmark support; rejected |
| Fresh ALIKED detections + LightGlue, associated to existing 3D features within 2 px | Best sampled control had only 11 shared 3D points; 9 matched correctly | Insufficient control evidence for the required 30-point check; stopped before cross-scene matching |
| ALIKED descriptors at the exact reconstructed feature locations + LightGlue; widened to 136.7–184.9s against 186–257s, sampled every 3s | 112 correctly matched known points out of 141 shared points | 300 image pairs; 1,944 candidates; best fit only 11 unique point pairs, no withheld-landmark support; rejected |

Counts of fitting pairs above refer to a 3D distance consensus, before the
symmetric image-projection checks. The first fit had **zero** candidates that
also passed those checks; the last had **two**, both in one fitting image pair.
Neither had successful withheld landmark matches or a held-out image pair with
15 consistent matches. Repeated bag folds, labels and ground texture produce
plausible appearance matches without supporting a common 3D placement.

The strongest learned-descriptor candidate pairs were inspected against the
source images. Several clearly connect different bags, labels or ground
patches. [Annotated candidate examples](bridge-candidate-review.jpg) contain
graphic source imagery; yellow numbers show proposed matches, **not verified
correspondences**.

The input projection conventions were checked independently: points projected
back into their own cameras had median/p95 errors of **1.30/2.59 px** for the
SIFT candidate set and **1.19/2.56 px** for the learned-descriptor set. The
similarity solver also recovered a known transform with 50% synthetic outliers.
Those checks distinguish a working coordinate/matching pipeline from a
successful connection. They do not authenticate the scene geometry.

## Reproduce or improve the experiments

Two small [candidate archives and rejected reports](../evidence/bridges/README.md)
allow offline experiments without repeating the full-video reconstruction.
They contain camera intrinsics/poses, candidate 2D/3D point associations, scores,
fit/held-out image-pair labels and original frame names. No private runtime
paths or host details are included.

To reproduce matching on the retained datasets, use the pinned official
[LightGlue implementation](https://github.com/cvg/LightGlue) at commit
`eb42fee2d71449efb0aa5c10549752b5d75384d8`. The existing source features use
COLMAP's default RootSIFT normalization; they must not be square-rooted again.
[ALIKED](https://github.com/Shiaoming/ALIKED) is used through that pinned
implementation, including its `describe` API for existing keypoint locations.

The observed environment had Torch 2.10.0, torchvision 0.25.0, NumPy 2.4.2 and
Pillow 10.2.0. The optional ALIKED dependencies were installed in an isolated
virtual environment with system Torch visible: `kornia==0.7.3` and
`kornia-rs==0.1.9`, using `--no-deps` to preserve the vendor Torch installation.
The installed torchvision lacked CUDA `deform_conv2d`, so **feature extraction
used CPU and LightGlue matching used GPU**. GPU extraction's failure is an
environment limitation, not evidence against ALIKED matching quality.

Set the following paths for your own reconstruction. `MODEL_A` and `MODEL_B`
are the undistorted COLMAP TXT exports; their observation indices must still
correspond to the original database. Dataset paths contain `images/` and
`masks/`. Each output path must be new.

```sh
python3 scripts/match_component_bridge.py \
  --features sift --model-a "$MODEL_A" --model-b "$MODEL_B" \
  --dataset-a "$DATASET_A" --dataset-b "$DATASET_B" \
  --frames "$NATIVE/frames.json" --database "$WINDOWS/database.db" \
  --lightglue "$LIGHTGLUE" --output "$SIFT_MATCHES"

# Run with the isolated environment's Python for these optional dependencies.
python3 scripts/match_component_bridge.py \
  --features aliked-sift --extractor-device cpu \
  --range-a 136.7 184.9 --range-b 186 257 --stride 3 \
  --model-a "$MODEL_A" --model-b "$MODEL_B" \
  --dataset-a "$DATASET_A" --dataset-b "$DATASET_B" \
  --frames "$NATIVE/frames.json" --database "$WINDOWS/database.db" \
  --lightglue "$LIGHTGLUE" --output "$LEARNED_MATCHES"

python3 scripts/align_component_matches.py "$SIFT_MATCHES" "$SIFT_REPORT"
python3 scripts/align_component_matches.py "$LEARNED_MATCHES" "$LEARNED_REPORT"
```

`--features aliked --extractor-device cpu` reproduces the fresh-detection
approach on the default intervals; it stops if the positive control is
insufficient. Highly occluded frames with fewer than 30 usable static features
are recorded as skipped, never counted as matched views.

`align_component_matches.py` estimates a positive-scale, proper-rotation
similarity from B to A. It excludes every fifth A landmark ID and one quarter of
sampled image pairs (the sum of their sample indices modulo four is zero) from fitting. The experimental gates are: at least 50 unique
fitting pairs, 20 unique withheld landmark pairs, three held-out image pairs
with at least 15 consistent matches, three views from each component, and
withheld median reprojection below 3.5 px. A consistent pair must be within
0.03 A-scene units, lie in front of both cameras, and project within 8 px in
both directions. These are screening criteria, not a proof of evidentiary
accuracy; floor/path plausibility and visual review remain necessary.

**A successful report-writing exit is not an accepted alignment.** Read
`accepted_geometry` and the individual checks; visual acceptance is separate.
No candidate from this experiment passed, and no splats were transformed,
merged, retrained or republished.

## Next unresolved step

The most useful next step is to identify a few **unmistakable stationary
landmarks visible in both sections**, preferably on the floor or fixed
architecture. Their source-frame correspondences would provide an independent
initial alignment and a way to reject visually plausible false matches.
Moving people and similar-looking bags cannot be the sole anchors.

If reliable shared landmarks cannot be found, recovering the camera transition
from the intervening source frames needs a separate experiment with explicit
uncertainty. The occlusion may make that connection underconstrained. A learned
pose prior or a manually placed model should be labeled an estimate until it
passes independent source-view checks.

If a future alignment passes, export must transform positions, Gaussian
orientations/scales **and view-dependent spherical-harmonic appearance**.
[PlayCanvas SplatTransform](https://github.com/playcanvas/splat-transform)
provides the transformation/merge tooling; it was researched but not run here
because no alignment was accepted.

Validation outcome for this checkpoint: controls/coordinate conventions and
reproducibility checks passed; alignment, withheld support and visual
correspondence acceptance failed; connected-view publication was blocked by
those failures. The existing public previews and their assets remain unchanged.
