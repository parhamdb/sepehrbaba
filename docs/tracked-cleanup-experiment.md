# Tracked occluders and cleanup experiment

Started September 26, 2026. This implements the first bounded experiment from
the [ranked research](reconstruction-options-2026-09.md). The public scenes and
full-recording processing controller are unchanged.

**Outcome:** both 8,000-step candidates finished; neither is accepted as a
replacement. Tracked masks recover some stationary detail but miss another
visitor, and the additional sparse-point cleanup does not improve the average
held-out score. Downloads, comparisons and the precise next step are below.

## Frozen scope and acceptance

- Use the existing 590.629889–606.465111-second component: 368 undistorted
  images, identical camera poses and 37 held-out images (sorted index modulo 10).
- Compare independent DeepLab person masks with source-reviewed occluders tracked
  by SAM 2.1. Validate every mask's inventory, size and binary encoding; inspect
  overlays for missed visitors, drift onto stationary bodies, bags and labels.
- If masks pass review, train a mask-only candidate, then a separate candidate
  that also removes masked sparse observations and unsupported points while
  preserving camera poses. Keep 8,000 steps, 1,920-pixel maximum edge and 500,000
  maximum splats. Compare both against the retained baseline on **identical
  baseline evaluation masks**, plus visual review of recovered static detail.
- Preserve scripts, prompts, model revision, hashes, comparison results and
  rejected outcomes. A completed run is not an accepted quality improvement.

Budget: one mask/inventory discovery pass, up to three distinct focused remedies
if needed, and one final verification of the frozen artifacts. Two candidate
training runs at most. No automatic full-video rerun, deployment, forced scene
alignment, generative completion or replacement of the vendor PyTorch stack.

## Selected method and fallback

SAM 3.1 checkpoint requests returned HTTP 401; no configured Hugging Face token
was present. That access prerequisite is blocked, not a model failure. We use
the available [official SAM 2.1 tracker](https://github.com/facebookresearch/sam2)
at revision `2b90b9f5ceec907a1c18123530e92e794ad901a4` with Hiera-small weights,
SHA-256 `6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38`.
Its license is Apache 2.0. A separate environment inherits the working PyTorch
installation; Hydra 1.3.2 and iopath 0.1.10 are installed there. Optional custom
CUDA mask postprocessing is disabled. This does not test SAM 3.1 itself.

The tracked objects are manually selected visible visitors whose movement is
reviewed in the source sequence, **not every object classified as a person**.
Negative prompts distinguish stationary bodies and bags. Each object is tracked
forward and backward from its anchor and combined into exclusion masks, with a
7-pixel dilation. This is bidirectional coverage, not a forward/backward
consistency algorithm or an automatic motion detector. Static pixels that were
incorrectly excluded by the old semantic masks become available for training.
The old masks use a 15-pixel dilation. This compares complete masking strategies,
not solely the neural network with every other mask parameter held constant.

The second candidate isolates sparse initialization cleanup under the new masks.
Earlier sparse cleanup under the old masks was rejected; it is not an established
improvement. Neither candidate implements T-3DGS, DeSplat or FlashSplat. Those,
depth/visibility pruning, blur compensation and registration remain separately
ranked future comparisons; the research document records their sources and costs.

## Reproduction

Prepare a separate environment with the official SAM 2 checkout and checkpoint.
Install it with `SAM2_BUILD_CUDA=0 pip install --no-deps --no-build-isolation -e
"$SAM2_CHECKOUT"` after installing its dependencies. Do not upgrade a working
vendor torch installation. With the original prepared component in `$DATASET`:

```sh
python scripts/track_occluders.py "$DATASET" \
  evidence/tracked-cleanup/prompts.json "$EXPERIMENT" \
  --checkpoint "$SAM2_CHECKPOINT" \
  --model-revision 2b90b9f5ceec907a1c18123530e92e794ad901a4
python scripts/inspect_masks.py "$EXPERIMENT/dataset" "$EXPERIMENT/mask-review.jpg"
# Review overlays before proceeding. Use fresh output directories throughout.
python scripts/video_to_splat.py --stage train --dataset "$EXPERIMENT/dataset" \
  --output "$MASK_TRAINING" --brush "$BRUSH" --steps 8000 \
  --train-resolution 1920 --max-splats 500000 --eval-split-every 10
python scripts/clean_static_geometry.py --source-dataset "$EXPERIMENT/dataset" \
  --work "$CLEAN_DATA" --colmap "$COLMAP" --preserve-poses
python scripts/video_to_splat.py --stage train --dataset "$CLEAN_DATA/dataset" \
  --output "$CLEAN_TRAINING" --brush "$BRUSH" --steps 8000 \
  --train-resolution 1920 --max-splats 500000 --eval-split-every 10
# Evaluate BOTH candidates with the same original dataset masks, not their own.
python scripts/inspect_brush.py "$DATASET" "$MASK_TRAINING/splats/eval_8000" \
  "$MASK_EVALUATION" --expected-views 37
python scripts/inspect_brush.py "$DATASET" "$CLEAN_TRAINING/splats/eval_8000" \
  "$CLEAN_EVALUATION" --expected-views 37
```

Runtime datasets contain absolute symlinks; public evidence contains only source
frame names, hashes and relative references. Preserve originals and run manifests.
Do not commit runtime state containing machine-specific paths.

The [geometry input archive](../evidence/tracked-cleanup/geometry-inputs.tar.gz)
preserves the original distorted text model, undistorted binary model and
baseline evaluation masks. Recreate native source images from the preserved
video using the [native-frame method](method.md), then undistort with the pinned
COLMAP version and original model. Check the resulting image hashes against
`mask-report.json` before claiming an exact replication. The 368 undistorted
JPEGs are not duplicated in this archive. Archive ownership/timestamps are
normalized; source-image and mask hashes retain content identity.

`scripts/compare_cleanup_renders.py DATASET BASELINE_RENDERS CANDIDATE_RENDERS
OUTPUT` also checks the exact held-out inventory, scores identical reference
pixels and exports source/baseline/candidate contact sheets. The tracker sees
the entire source sequence during segmentation, including held-out frames;
those frames are withheld from Gaussian color/geometry optimization, not from
mask preprocessing. This is not a completely blind benchmark. Single training
runs also leave optimizer randomness as a limitation.

## Results ledger

SAM 3.1 access is blocked; SAM 2.1 is the selected runnable alternative.
Attempt 1 tracked both objects over 368 images and passed inventory/dimension
checks, but missed the foreground visitor at the beginning. Its
[overlay](../evidence/tracked-cleanup/attempt1-mask-review.jpg), prompts and hash
report are retained. Attempt 2 adds a first-frame anchor to address that specific
failure. Its [review sheet](../evidence/tracked-cleanup/mask-review.jpg) fixes the
missed beginning and preserves stationary details in the reviewed views. Small
boundary errors remain, including overlap onto a stationary bag/cloth near the
moving arm; this is accepted for a bounded training comparison, not certified
segmentation. The final [368 binary masks](../evidence/tracked-cleanup/masks.tar.gz)
and their [hash report](../evidence/tracked-cleanup/mask-report.json) are retained.

All source image hashes and copied sparse-model binaries match the baseline.
Median excluded area changes from 33.9284% to 0%; maximum tracked exclusion is
26.5986%. This is coverage, not an accuracy score: many frames show stationary
details without either tracked visitor. Cleanup retains 15,220 of 15,481 sparse
points and removes 2,058 duplicate observations. Camera translations remain
unchanged; measured rotation difference is numerical roundoff. Reprojection
mean/p95 are 1.2717/2.5577 pixels, with no behind-camera observations.
[Geometry report](../evidence/tracked-cleanup/geometry-cleanup.json).

The [self-comparison](../evidence/tracked-cleanup/calibration.json) reproduced
23.49210 dB over all 37 held-out images, with exactly zero baseline/candidate
delta. Six [fixed offset cameras](../evidence/tracked-cleanup/novel-views.json)
also probe small novel views: three reference cameras shifted left/right by
0.07025147 scene units (1% of median retained sparse depth), with target shifted
equally and orientation/intrinsics preserved. These are unmeasured scene units,
not metres, and the novel views have no ground-truth images.

| Acceptance item | Status | Evidence |
|---|---|---|
| Reviewed tracked masks and complete inventory | Passed for trial | 368 binary masks, corrected first-frame anchor, retained limitations above |
| Preserve sources, cameras and held-out split | Passed | Image/model hashes; comparator verifies exact sorted-index split |
| Mask-only 8,000-step candidate | Passed execution; not promoted | 545.5 seconds, 37,009 Gaussians, all 37 held-out renders |
| Additional geometry-cleanup candidate | Passed execution; not promoted | 799.3 seconds, 36,266 Gaussians, all 37 held-out renders |
| Fixed-mask comparison and visual inspection | Passed execution | 37 held-out views per candidate; six offset views each plus baseline; visual review completed |
| Reproducible code and documentation | Passed | Frozen code, four prompt checks, independent review and final artifact checks |
| Promote mask-only candidate | Failed | Incomplete visitor coverage; mixed detail changes |
| Promote additional cleanup candidate | Failed | Lower average reference score; no clear visual improvement |

Final ledger: **6 passed, 2 failed, 0 blocked, 0 untested**. All execution and
comparison work finished, but both replacement-quality gates failed. The bounded
experiment is complete; an improved replacement reconstruction is not accepted.
The final artifact gate on commit `44572d4` passed: both PLYs are structurally
valid with finite values; 74 held-out records and 18 successful offset captures
match the fixed inventories; all 368 archived masks match their hashes; input
archives, documentation links and public-report privacy checks pass. The four
prompt checks passed again on the frozen code. Both training services exited
successfully, and the separate full-video service remained active.
The rejected first mask attempt is retained as resolved failure evidence. SAM
3.1 access remains a prerequisite for a different model comparison, rather than
a blocker for this SAM 2.1 experiment.

## Mask-only result

The [comparison](../evidence/tracked-cleanup/mask-only-comparison.json) scores
23.52290 dB versus 23.49210 dB: only **+0.03081 dB**, with 17/37 improved views
and a worst-view change of **−4.18676 dB**. See the
[held-out comparison](../evidence/tracked-cleanup/mask-only-comparison.jpg) and
[six offset-view comparison](../evidence/tracked-cleanup/mask-only-novel-comparison.jpg).

The [worst-view review](../evidence/tracked-cleanup/worst-view-review.jpg) at
frame 009807 explains why average scores are insufficient. The old semantic mask
excludes large stationary body/bag regions; tracking preserves those details.
However, another visitor's legs at the upper-right edge are **not covered by the
two prompted tracks**, and appear in the candidate. The mask review was sufficient
to run a trial, but did not establish complete occluder coverage. Broader reviewed
instance coverage is needed before a replacement scene can be accepted. The
six small novel-view offsets show mixed detail changes, not a clear overall win.

One multi-view browser process closed after its first successful capture. That
capture was retained; all five missing views passed in fresh individual browser
processes. The combined capture manifest records this recovery. No training
was rerun for the renderer failure.

The [candidate PLY](../evidence/tracked-cleanup/mask-only.ply) is retained for
inspection, in the original unlevelled component coordinates. It is not a new
public viewer default. The implementation passed four prompt-validation checks
and an independent read-only review; reconstruction quality remains unaccepted.

## Additional cleanup result and next decision

| Variant | Fixed-reference PSNR | Change from baseline | Improved views |
|---|---:|---:|---:|
| Retained baseline | 23.49210 dB | — | — |
| Tracked masks | 23.52290 dB | +0.03081 dB | 17/37 |
| Tracked masks plus sparse cleanup | 23.38183 dB | −0.11027 dB | 18/37 |

Cleanup is also 0.14107 dB below the mask-only run. Its worst per-view change
from baseline is −2.94848 dB. See the
[complete scores](../evidence/tracked-cleanup/cleanup-comparison.json),
[held-out contact sheet](../evidence/tracked-cleanup/cleanup-comparison.jpg), and
[candidate PLY](../evidence/tracked-cleanup/mask-plus-cleanup.ply). Retaining fewer
points did not reliably improve this scene. The longer training time overlapped
another full-recording GPU job and is not a fair method-speed benchmark.
All six [cleanup offset views](../evidence/tracked-cleanup/cleanup-novel-comparison.jpg)
rendered successfully in fresh browser processes. Their visual comparison shows
mixed detail changes and persistent weak boundaries/blur, rather than a clear
overall improvement. No third training run or threshold-tuning cycle was started.

The next smallest change is to enumerate **every visible visitor instance**,
give distinct tracks separate IDs, add anchors at entrances/reappearances, and
review edge coverage throughout the interval. Review bodies, bags, labels and
floor details as protected content. A sparse-point filter cannot remove an
unmasked visitor merely because it is transient. Complete that mask review
before a separately budgeted reconstruction comparison; do not increase pruning
thresholds to hide the symptom. This pass used its two-candidate training budget.

SAM 3.1 remains access-gated. T-3DGS/DeSplat/RobustSplat, real FlashSplat labeling,
depth/visibility cleanup, new registration and completion tools remain **not
run** here; their ranking and sources stay in the research document. No synthetic
completion, fabricated scene connection or public-viewer change was made.
