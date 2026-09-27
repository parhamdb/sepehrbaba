# Selective section cleanup before manual stitching

This experiment targets the two complete retained camera components around the
human-reviewed 06:50–06:55 match: 78 registered images at 408.134389–412.230244 s,
and 235 registered images at 414.562967–427.800311 s. Original cameras are reused;
this is not a fresh camera-recovery claim. Each component remains independent.

`clean_section_masks.py` uses the cached SAM 3.1 checkpoint's native image detector
on undistorted training images. Prompts propose standing, sitting and walking
people for exclusion; lying people and body bags are protection proposals.
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
