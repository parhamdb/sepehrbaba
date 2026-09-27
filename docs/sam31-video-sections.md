# SAM 3.1 temporal masking of the two stitching sections

The previous cleanup used SAM 3.1's image detector independently on each frame.
Video propagation had stopped after three compatibility failures in the earlier
camera-loss campaign: unsupported state offloading, unavailable CUDA ROI Align,
and tuple boxes in the CPU fallback. That fallback now accepts lists and tuples,
as the successful image-mask path already did. The previously exhausted campaign
was not silently retried: this is a separately requested video-tracking delivery.

Scope: temporal segmentation of the 78-frame earlier and 235-frame later sections,
review and protection of ground bodies, independent candidate training, and a
comparison against the current models. Original scenes and manual alignment stay
available. Full-recording processing and new camera recovery are outside scope.

The adapter invokes SAM 3.1's video predictor and `propagate_in_video`, retaining
per-object IDs and masks, original timestamps, source/model/script hashes and
review overlays. Text prompts are standing person and walking person. These are
tracked semantic proposals, not automatic physical-motion labels; object identity
alone does not prove an object moved. Existing reviewed foreground-hand corrections
are retained, and lying bodies/coverings remain protected.

Reproduction uses the pinned SAM checkout and cached gated weights (credentials
stay in the worker cache):

```sh
python scripts/sam31_clip_masks.py --images DATASET/images --frames FRAMES.json \
  --output NEW_TRACK_PROPOSALS --prompt 'standing person' \
  --review-stride 1 --cpu-roi-align
```

Repeat for walking person. The frames JSON is the ordered original source
inventory restricted to the section's registered images, without inventing a
constant timestamp rate. Review all additions before using them as exclusions.

Acceptance inventory: (T1) native video propagation completes with tracked IDs;
(T2) all 313 frames and both prompts complete with provenance; (T3) reviewed mask
additions preserve protected details; (T4) candidate training and fixed-mask
comparison complete; (T5) separate inspectable candidates and reproducible records
are delivered. One discovery pass, focused failures only, and one final artifact
review; no more than three attempts for the same blocker. Healthy jobs may be
handed off with their handle and ETA at the active-work limit.

Initial T1 result: 8/8 frames completed, one persistent ID across five consecutive
frames, 8.45 seconds propagation time after model initialization. A standing
visitor's legs were inspected in the overlay. This is inference proof, not proof
that full-section masks or resulting geometry are accurate.

Official API example: [SAM 3.1 video predictor](https://github.com/facebookresearch/sam3/blob/main/examples/sam3.1_video_predictor_example.ipynb).

## Completed tracking and mask review

All 313 registered images completed both prompts: 626 frame/prompt outputs.
Propagation took 48.4/45.6 seconds for the earlier standing/walking runs and
124.1/100.3 seconds for the later runs, excluding model initialization. These are
registered section images, not every raw frame of the full recording.

Earlier proposals add exclusions averaging 0.632% of image area (maximum 3.165%).
All 78 frames were reviewed. Additions mostly recover visitor shoes, limbs and
mask boundaries; tiny floor speckles remain. Later proposals average 0.100%
before review, with a maximum of 8.056%. All 235 frames were reviewed. Four frames
(`006619`, `006624`, `006625`, `006627`) incorrectly included foreground body
clothing or bag edges. Their review receipt restores the lower region; a pixelwise
check first confirmed that region contains no approved baseline exclusions.
This failure is retained, not presented as successful automatic motion detection.

The existing semantic protection masks were insufficient in those four frames.
Tracking consistency does not establish whether an object is moving, nor does it
make these labels safe without source review. Camera/depth errors and poorly
observed geometry can still produce rays after visitor masking.

## Reproduce the candidate

SAM checkout: `2345a4ad109ac29c569da749c91d84f10dc08c40`. The cached
`facebook/sam3.1` multiplex checkpoint hash and each frame's source/mask hashes
are in [the tracking receipts](../evidence/sam31-video-sections/).

```sh
python scripts/merge_tracked_section.py --dataset BASELINE_STATIC/dataset \
  --baseline-report BASELINE_REVIEWED/mask-report.json \
  --protection IMAGE_PROPOSALS/protected \
  --tracked VIDEO_STANDING --tracked VIDEO_WALKING --output MERGED
# Review every addition and bind REVIEW.json to MERGED/manifest.json.
python scripts/prepare_reviewed_section.py --dataset BASELINE_STATIC/dataset \
  --proposals MERGED --review REVIEW.json --output REVIEWED
python scripts/clean_static_geometry.py --source-dataset REVIEWED \
  --work STATIC --colmap COLMAP_BINARY --preserve-poses
python scripts/video_to_splat.py --stage train --dataset STATIC/dataset \
  --output TRAINING --brush BRUSH_BINARY --steps 8000 \
  --train-resolution 1920 --max-splats 500000 --eval-split-every 10
python scripts/compare_cleanup_renders.py BASELINE_STATIC/dataset \
  BASELINE_TRAINING/splats/eval_8000 TRAINING/splats/eval_8000 COMPARISON
```

The comparison evaluates identical pixels using frozen baseline masks and the
same 8/24 held-out cameras. It does not establish novel-view geometry or restore
occluded detail. Masks and initialization change together, so this is an end-to-end
cleanup comparison, not an isolated segmentation ablation. Brush optimization can
also vary between runs; a small score change alone is not proof of improvement.

The reviewed input archive is retained through Git LFS as
`evidence/sam31-video-sections/reviewed-tracking-inputs.tar.gz` with a checksum in
`inputs-receipt.json`. It contains per-instance tracked masks, merged proposals,
protection maps, four correction polygons, final training masks, frame timestamps,
and sparse camera/point models. Reuse the byte-verified undistorted source images
from the baseline section dataset. Credentials, private worker paths, source
image duplicates and model weights are excluded from this archive.

After corrections, the later masks add only 0.059% of image area on average
(maximum 2.118%). All approved baseline exclusions remain intact in both sections.
Filtering masked seed observations removes 22 of 1,890 earlier points and none of
9,976 later points. Camera positions stay fixed. These small changes limit how
much improvement should be expected from temporal masks alone.

## Render comparison

The earlier candidate completed 8,000 steps. On the same eight held-out views and
frozen baseline scoring pixels, PSNR changed from 24.3717 to 24.2144 dB
(-0.1573 dB); one view improved. Independent inspection of the six contact-sheet
views found no convincing material improvement. The candidate floor appears
slightly smoother and less distinct at frame 006475; blur remains in both models.
The previous scene remains the default. Newly excluded visitor pixels can still
fall within baseline scoring support, so the score alone is not a quality verdict.

[Earlier source/baseline/candidate comparison](../evidence/sam31-video-sections/earlier-comparison/comparison.jpg)
and [numeric results](../evidence/sam31-video-sections/earlier-comparison/comparison.json).
Both section comparisons and the combined viewer are now available; see below.

The earlier interactive check also captured the same seed and orbited viewpoints
for both versions. Rays persist and some are more noticeable in the tracked
candidate. Its 7,060 Gaussians versus 7,232 baseline Gaussians do not establish
cleaner geometry; the 95th-percentile longest/second-longest axis ratio actually
increased from 17.11 to 18.45. These descriptive statistics are not ghost labels.

The later candidate completed 8,000 steps in 542 seconds (earlier: 495 seconds).
Across its 24 fixed held-out views, PSNR changed from 25.7760 to 25.6497 dB
(-0.1264 dB), with 8 improved views. Six sampled views, the worst score-change view
006722, and matching seed/orbit editor views were inspected. Bodies and coverings
remain visibly present, while softness, rays and floor distortion persist. Neither
candidate is promoted. The experiment successfully exercises video tracking but
does not demonstrate improved reconstruction quality.

[Later comparison](../evidence/sam31-video-sections/later-comparison/comparison.jpg),
[worst-score view](../evidence/sam31-video-sections/later-comparison/worst-view.jpg),
and [numeric results](../evidence/sam31-video-sections/later-comparison/comparison.json).

## Open the four-version comparison

Download LFS artifacts, build the existing editor, and use a fresh state directory.
The public manifest uses the already published seed transforms; it does not
publish anyone's private live editing state. The previous scene remains visible
initially. On phones open **Filters**, scroll to **Show / hide sections**, and use
**Only** next to a version. Camera position remains unchanged when switching.

```sh
git lfs pull
npm ci
npm run build
mkdir NEW_COMPARISON_STATE
cp evidence/sam31-video-sections/comparison-initial-state.json NEW_COMPARISON_STATE/project.json
node scripts/stitch-editor-server.mjs \
  --manifest evidence/sam31-video-sections/comparison-scenes.json \
  --assets evidence --state NEW_COMPARISON_STATE --host 0.0.0.0 --port 8093
```

The two source sections are still independent reconstructions. Switching versions
compares the same section; it does not connect them across the camera gap. No
existing source video, previous scene or saved alignment is overwritten.
