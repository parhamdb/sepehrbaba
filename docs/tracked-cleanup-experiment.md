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
failure. Mask review and candidate training results remain pending.

The implementation passed four prompt-validation checks and an independent
read-only review. No quality improvement is claimed yet.
