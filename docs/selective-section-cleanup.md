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
