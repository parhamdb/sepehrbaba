# Tracked occluders and cleanup experiment

Started September 26, 2026. This implements the first bounded experiment from
the [ranked research](reconstruction-options-2026-09.md). The public scenes and
full-recording processing controller are unchanged.

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
| Additional geometry-cleanup candidate | Untested | Input geometry gate passed; separate training pending |
| Fixed-mask comparison and visual inspection | Untested | Comparator calibration passed; candidate renders pending |
| Reproducible code and documentation | Passed for setup | Commit `cd1cee6`, four prompt checks, independent review |

Current execution checks: **4 passed, 0 failed, 0 blocked, 2 untested**.
Separately, **mask-only promotion failed** for missed-visitor artifacts. Successful
execution does not turn that quality failure into an accepted reconstruction.
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
