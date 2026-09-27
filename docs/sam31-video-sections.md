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
