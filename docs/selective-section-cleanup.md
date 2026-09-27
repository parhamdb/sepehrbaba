# Selective section cleanup before manual stitching

This experiment targets the two complete retained camera components around the
human-reviewed 06:50–06:55 match: 78 registered images at 408.134389–412.230244 s,
and 235 registered images at 414.562967–427.800311 s. Original cameras are reused;
this is not a fresh camera-recovery claim. Each component remains independent.

`clean_section_masks.py` uses the cached SAM 3.1 checkpoint's native image detector
on undistorted training images. Default prompts propose standing and walking people for exclusion; lying people
and body bags are protection proposals. Additional reviewed categories can be
passed with repeated `--exclude` arguments. The initial sitting-person proposal
misclassified clothing on a ground body, so it is not used for these sections.
Protection wins where proposals conflict. These semantic labels are imperfect:
absence of a protection detection does not establish that no body is present.
Every output is a proposal until visual inspection; masks are stored separately.

This is independent-frame segmentation, not the previously blocked video-tracker
adapter and not automatic world-motion classification. A CPU ROI Align fallback
handles both tensor and list/tuple boxes on workers without that CUDA kernel.
No credentials are accepted or logged by the script.

```sh
python scripts/clean_section_masks.py --dataset EXISTING_DATASET \
  --output NEW_PROPOSALS --sample-count 4
# After the pilot, run all registered images into a separate output:
python scripts/clean_section_masks.py --dataset EXISTING_DATASET \
  --output FULL_PROPOSALS
```

Orange review pixels are proposed exclusions; cyan pixels are protected proposals.
Five-pixel dilation covers narrow mask boundaries, with protected pixels restored.
Per-frame source and mask hashes, scores and ambiguous areas are retained. Blurred
images, partial hands and segmentation misses must be reviewed; scene cleanliness
is assessed from actual renders, not inferred from successful masking alone.

After review, copy accepted masks to a new dataset with white retained pixels and
black excluded pixels. Keep original sparse cameras and images unchanged. Train
the two components independently, inspect held-out views, and load their resulting
PLY files in the LAN editor. Manual alignment changes only saved transforms.

[Campaign verification](../evidence/clean-sections/verification.md)

The earlier full proposal audit found six missed leg/shoe views. The retained
[review receipt](../evidence/clean-sections/earlier-review.json) records explicit
normalized exclusion polygons and their reasons. `prepare_reviewed_section.py`
checks every proposal/source hash and creates a new dataset, with protected
pixels restored after corrections. Original inputs remain byte-identical.

Before training, the existing `clean_static_geometry.py --preserve-poses` removes
masked feature observations and unsupported seed points without changing camera
poses. This reduces initialization from moving obstructions.

The later audit inspected all 235 proposals and added 134 source-reviewed
polygons across 129 images for foreground hands, shoes and partial visitors.
[The receipt](../evidence/clean-sections/later-review.json) retains every polygon.
Only the verified foreground hand uses `override_protection: true`, because SAM
sometimes incorrectly protected it together with the ground body. That explicit
manual exclusion overrides semantic protection only inside the reviewed polygon.
Blurred hand edges and tiny partial walker remnants remain uncertain. Four
polygons extending beyond the image were geometrically clipped to its boundary;
the validator rejected the unbounded input and its partial dataset was preserved.

## Reproduce the reviewed training stage

Use fresh output directories. The review receipt must match the proposal manifest
hash and complete source-image inventory. The worker needs the existing pinned
COLMAP 3.12.6 and Brush 0.3.0 toolchain; authentication stays in its model cache.

```sh
python scripts/prepare_reviewed_section.py --dataset ORIGINAL_DATASET \
  --proposals FULL_PROPOSALS --review REVIEW.json --output REVIEWED_DATASET
python scripts/clean_static_geometry.py --source-dataset REVIEWED_DATASET \
  --work STATIC_WORK --colmap COLMAP_BINARY --preserve-poses
python scripts/video_to_splat.py --stage train --dataset STATIC_WORK/dataset \
  --output TRAINING --brush BRUSH_BINARY --steps 8000 \
  --train-resolution 1920 --max-splats 500000 --eval-split-every 10
python scripts/inspect_brush.py STATIC_WORK/dataset TRAINING/splats/eval_8000 \
  INSPECTION --expected-views EXPECTED_COUNT
```

Held-out counts are 8 earlier and 24 later. Their images are reserved for evaluation,
so the 78/235 registered-image inventories are not claims that every image was
used as a training view. No new camera recovery is performed. Mask changes alter
the evaluated pixel set, so PSNR cannot be directly compared with the earlier
blanket-person-mask result as a quality improvement score.

Load the generated `TRAINING/splats/scene.ply` files through a private manifest in
[the LAN editor](lan-stitch-editor.md), with distinct filenames and status labels.
A saved project records placements; it does not weld, deform, deduplicate or fill
the source Gaussian geometry. Add further reviewed sections to the manifest with
new IDs, restart the server, and continue aligning them against the saved area.
