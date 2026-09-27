# Trace, review, mask, retrain, and inspect again

The inspector turns a selected screen artifact into checkpoint-bound Gaussian IDs
and a ranked source-frame review strip. It does not infer a causal object label
from a projected ellipse. The first real selection isolated four splats that draw
a long ray. Their footprints cross a walking visitor and static coverings; most
of the visitor was already excluded. The experiment therefore tests a specific
boundary hypothesis without masking the entire footprint.

## Inspector

Open Filters, select a supported section, press **Select a ray**, then tap the
artifact. The selected section is isolated and display filters are bypassed.
Checkboxes select among the strongest sampled contributors. **Trace checked
splats** recomputes source support; **Show traced only** renders just those original
Gaussian records, and **Restore scene** restores the complete section.

Each source strip contains an undistorted, resized video-frame preview, selected
Gaussian footprints, and the current exclusions. Open an image for full-size
review. Timestamps refer to the original recording. The trace receipt retains the
camera, selected pixel, original PLY hash, vertex IDs, and preview-image hashes.
IDs are meaningful only within that checkpoint; retraining requires a fresh pick.

The NumPy projection follows the repository's previously calibrated analytical
PlayCanvas convention. Picking weights include front-to-back alpha compositing.
Source ranking samples centers and nearby points and accounts for occlusion at
those samples. Colored source overlays show projected footprints, not full
per-pixel visibility. This is an approximate review aid; isolated rendering checks
that the selected records actually draw the observed artifact. Held-out images are
excluded from source ranking and mask-seed selection.

Start the existing editor with an additional private configuration:

```json
{
  "python": "python3",
  "output": "/absolute/path/to/new-trace-results",
  "references": {
    "earlier-tracked": "/absolute/path/to/earlier-references",
    "later-tracked": "/absolute/path/to/later-references"
  }
}
```

Pass `--trace-config CONFIG.json` to `scripts/stitch-editor-server.mjs`. Scene IDs
must exist in the manifest. References use `prepare_references.py`'s `views.json`,
`images/`, and `masks/`, plus `frames.json` containing original names/timestamps.
The inspector requires NumPy and Pillow; SAM and training run separately on the
worker. Original files and saved placements are not rewritten by a trace.

## Repeatable correction cycle

1. Inspect the isolated ray and several timestamped source strips. Classify the
   evidence as missed moving foreground, uncertain, or static-geometry trouble.
   Keep the trace receipt. A footprint over a body or covering is not permission
   to exclude it.
2. For a verified visitor, create a reviewed normalized point or semantic-box seed
   for SAM3.1. Record the frame, coordinates, reason, and trace ID. Track in both
   directions. Check mask coverage, not just successful process completion.
3. Create padded proposals with `pad_reviewed_masks.py`. Review every changed
   frame. Record preservation corrections and bind approval to the proposal
   manifest hash using the existing review-receipt format.
4. Run `fit_feedback_candidate.py` to prepare the reviewed masks, remove masked
   sparse observations with fixed cameras, train 8,000 steps, and compare exactly
   the same held-out cameras and frozen reference pixels.
5. Review matched and novel viewpoints. Re-pick surviving artifacts against the
   new checkpoint. Repeat with a new output directory and evidence-based
   hypothesis. Never reuse Gaussian IDs across retraining or silently promote a
   candidate. Stop unsupported masking when the trace points to legitimate static
   detail. At most three distinct attempts are allowed for the same blocker.

```sh
python scripts/sam31_clip_masks.py --images DATASET/images --frames FRAMES.json \
  --seed SEED.json --output NEW_TRACK --review-stride 1 --cpu-roi-align
python scripts/pad_reviewed_masks.py --dataset DATASET \
  --baseline-report PREVIOUS_REVIEWED/mask-report.json \
  --prior-review PREVIOUS_REVIEW.json --protection PREVIOUS_PROPOSALS/protected \
  --tracked NEW_TRACK --radius 5 --output NEW_PROPOSALS
# After source review, create NEW_REVIEW.json with the exact manifest hash.
python scripts/fit_feedback_candidate.py --dataset DATASET \
  --proposals NEW_PROPOSALS --review NEW_REVIEW.json --trace TRACE.json \
  --hypothesis 'Reviewed visitor boundary correction' \
  --reference-dataset FROZEN_REFERENCE_DATASET \
  --baseline-renders PREVIOUS_TRAINING/splats/eval_8000 \
  --output NEW_CYCLE --brush BRUSH_BINARY --colmap COLMAP_BINARY
```

Semantic-box seed format uses normalized top-left x/y and width/height:

```json
{"frame":"frame_006449.jpg","box":[0.22,0,0.46,0.44],
 "text":"standing person","reason":"Source-reviewed visitor; preserve coverings"}
```

Point seeds instead use `points`, `point_labels` (1 foreground, 0 background),
`frame`, and `reason`. They are not mixed with text/boxes in the same request.
The script retains raw per-instance masks. Neither a seed nor a successful track
automatically approves the masks for training.

## What five pixels means

The previous `dilation_pixels=5` represented a **5×5 kernel**, which extends only
two pixels per axis. Raw masks now receive an **11×11 kernel: radius five native
undistorted training pixels**. Reviewed baseline masks receive three additional
pixels because their automatic masks already used radius two. Manual polygons
also receive that additional border; this is not a claim every final mask equals
one dilation of a raw mask by five pixels.

The full baseline exclusions are retained. Semantic protection and explicit prior
preserve polygons constrain all additions. Tiny disconnected components below64
native pixels are retained in the baseline but are not expanded; such components
in new raw proposals are rejected. This was added after review caught enlargement
of old speckles near bags. It is a reviewed experiment parameter, not a universal
safe threshold. Mask preparation requires OpenCV in the worker environment.

## Initial campaign

The first point landed in the gap between the visitor's legs and selected a tiny
patch. Corrected points segmented the visitor in the seed frame but produced empty
masks on77/78 frames. Both failed proposals are retained. A third, semantic-box
prompt exercised native semantic video propagation and returned nonempty masks
on78/78 frames. This demonstrates coverage, not automatic correctness.

The earlier candidate tests source-guided visitor masking plus wider padding.
The later candidate is a padding-only control. They are different scenes, so their
relative scores cannot isolate the contribution of tracking versus padding.
Acceptance and quality decisions are retained in
[the campaign ledger](../evidence/ghost-feedback/verification.json).

## First measured result

The later padding-only candidate completed all 8,000 steps. Against the previous
SAM-video tracked checkpoint on the same 24 held-out views and frozen image-mask
reference pixels, PSNR changed from 25.64966 to 25.66645 dB (+0.01679 dB).
Twelve views improved and twelve worsened; the worst change was -0.68133 dB.
Independent visual review of six displayed matched views found no convincing
ray/ghosting improvement and no broad new loss of bodies or coverings. Keep the
candidate for comparison; these results do not justify promotion. The comparator
is the prior tracked version, not the older image-mask version.

The [reviewed input archive](../evidence/ghost-feedback/reviewed-inputs.tar.gz)
contains the final proposal masks, protected regions, metadata, approvals, and
raw SAM attempt records. The [geometry archive](../evidence/ghost-feedback/candidate-geometry.tar.gz)
contains the corresponding filtered sparse models. Candidate PLY files and
comparison receipts are retained beside these archives. Original source imagery
and the earlier datasets remain in the existing evidence archives. Runtime
configuration, credentials, personal paths, and worker logs are not published.

The retained [novel-view screenshots](../evidence/ghost-feedback/novel-view-review/)
also show long rays remaining in the later candidate. A fresh trace uses new
checkpoint IDs and returns six source frames; this verifies the inspector across
retraining, not a successful cleanup. Further automatic expansion is not warranted
by this result.

## Source-guided correction and repeat inspection

The earlier source-guided SAM plus padding candidate completed 8,000 steps.
Against the prior tracked version on eight held-out views and frozen reference
pixels, PSNR changed from 24.21441 to 24.18268 dB (-0.03173 dB); three views
improved. Independent review found a localized reduction of an upright spike
behind the rear purple-covered body, but no scene-wide improvement. Other
rays and diffuse floor ghosting remain. Both candidates stay experimental.

The same saved camera and selected pixel were traced again against the new
checkpoint. New Gaussian IDs 3583, 5956, 6377, and 5 isolate a surviving diagonal
ray. The [repeat source strips](../evidence/ghost-feedback/repeat-trace/) overlap
already-excluded visitors and legitimate static coverings. Three source strips
were inspected directly, including frames 006491, 006453, and 006419. This is
insufficient evidence for another broader mask: neither footprint overlap nor
nonempty SAM tracking establishes the cause. Stop this masking hypothesis here;
the next diagnosis should distinguish pose/depth inconsistency and weak static
view support before proposing further exclusions.

The inspector is an interactive tool and the correction cycle is agent-reviewed.
It is not an unattended classifier that automatically erases every suspect
footprint. One full source-guided correction and reinspection, plus the padding
control, were completed in this campaign. Training jobs are finished. Desktop
and phone picking, source tracing, isolation, and restoration were verified with
the real assets. All 313 actual training masks match their reviewed proposals,
and source-image hashes are unchanged. Original editor state was preserved.

Trace download URLs are local to the running inspector session. Restarting the
server invalidates those URLs; receipts and images remain on disk. Retained
campaign examples are committed above. Re-pick a scene to obtain a fresh URL.
