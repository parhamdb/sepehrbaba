# Luna search across wider time windows

**The wider search did not establish a clearly better landmark match.** It did
produce a reproducible frame inventory, a weak floor candidate to reject or
verify, and a more useful approach to using visual models for frame selection.
It does not overturn the earlier plausible shared patch/cord region.

[Compare the original views](https://parhamdb.github.io/sepehrbaba/wide-landmark-review.html)
or read the [ranked research and proposed methods](../../docs/llm-assisted-landmark-search.md).

## What was actually inspected

The explicitly requested model, **GPT-6 Luna**, received two ten-second windows
around the tracking loss, with the intervening frames retained:

| Interval | Time in seconds | Native frames |
|---|---|---|
| Before | 402.290311–412.290311 | 178 |
| Gap | 412.290311–414.512889 | 38 |
| After | 414.512889–424.512889 | 192 |

All **408** original-frame entries in that interval were supplied and represented
in **21 contact sheets**. Camera registration and whole-image sharpness were not
selection filters. Luna inspected every contact sheet, then 13 original JPEGs.
The parent noticed that these originals did not cover the newly added early
portion, so a bounded six-image follow-up explicitly examined farther-apart
views. Total: **19 unique original images inspected by Luna**. Thumbnail screening
is not full-resolution inspection of all 408 frames.

The initial scout was not given the previous point coordinates or preferred
frame pair. The parent inspected six original images and critically compared
the proposed floor pair and two examples from the follow-up.

## Findings and limits

1. **Weak floor candidate:** frame 006491 at 412.170167 s versus frame 006704 at
   423.695311 s, separated by **11.525144 seconds**. Both contain tile seams and
   teal/tan coloring, but no unique shared stain contour or particular seam
   junction was established. Lighting, shadows and repetitive tiles are strong
   alternatives. No point from this pair is accepted.
2. **Earlier context:** frame 006350 at 404.510022 s contains a small white tag on
   a dark bag. Later views 006580/006605 did not establish its counterpart or the
   same surrounding arrangement. A potentially distinctive earlier detail is
   not itself a correspondence.
3. **Possible indirect overlap:** floor-facing gap frames could be intermediate
   views, but neither edge of a proposed A–C–B connection was established. This
   remains a method to test, not an observed bridge.

The initial raw report incorrectly called the selected pair 9.18 seconds apart
and described an “unsampled interval.” Preserve those raw outputs as model
evidence, but use the manifest-derived **11.525144 seconds** and the complete
**408-frame supplied interval**. The follow-up corrects these statements; its
remaining “sparse samples” wording applies only to sparse original-image
inspection, not missing source frames. [Parent review and corrections](parent-review.json).

This is a limited negative scouting result, not proof that overlap is absent or
that all other frames are useless. No GPU model run, tracking experiment, camera
solve, source-image enhancement, generated detail or reconstruction change was
performed in this research step.

## Better next use of language models

Use a model to propose **frame pairs, visible regions and alternative matches**.
Then number detector-generated candidate features and ask the model to choose
among them, including “none/unclear.” Inspect neighboring frames to reject moving
shadows and occluding edges. Dense matching and geometry should estimate and
validate coordinates; prose descriptions should not become guessed pixel shifts.

If these local windows provide no stronger support, search the full recording
for a revisited view that overlaps both components. A geometrically verified
indirect path may be more useful than forcing the frames next to the loss to
match. The [research document](../../docs/llm-assisted-landmark-search.md) ranks
these options, links primary sources, and distinguishes proposals from runs.

## Reproduce and inspect

```sh
python scripts/select_landmark_windows.py \
  --frames ORIGINAL_FRAMES_JSON --images ORIGINAL_NATIVE_IMAGES \
  --gap-start 412.290311 --gap-end 414.512889 --seconds-each-side 10 \
  --output INPUT_DIRECTORY/selection.json
# Make the selected original JPEGs available in INPUT_DIRECTORY/images.
node scripts/render_landmark_contacts.mjs INPUT_DIRECTORY OUTPUT_DIRECTORY
```

The reusable selector exactly reproduced the frozen inventory, timestamps and
408 hashes. Boundary checks confirm that gap endpoints stay in the gap and an
existing selection cannot be overwritten. The sheet renderer verifies every
input hash and labels frame IDs, timestamps and side of the gap.

- [Selection and source hashes](selection.json), [artifact provenance](provenance.json).
- [Initial Luna report](luna-review.md), [raw shortlist](luna-shortlist.json).
- [Six-image follow-up](followup-review.md), [structured follow-up](followup-review.json).
- [All 21 contact sheets](contacts/).
- [19 inspected original JPEGs](../../public/wide-landmark-review/images/).

The comparison page displays original JPEGs with no invented landmark markers.
Its broader-context example is explicitly not a proposed match. Source hashes,
timestamps and review status are retained in its downloadable JSON.
