# Gap 098: static image links found, continuous camera recovery not established

**No new camera poses were accepted.** This completed experiment isolates a
partial static-image connection inside the 06:52–06:54 tracking loss. It does not
join the before/after COLMAP maps or change the public 3D scene.

We processed **61 native 1080×1920 frames**: every source frame from 412.0 through
414.9 seconds, plus the previous gap-098 anchors and controls. There are **1,830
image pairs**, all matched without camera-pose filtering. SAM masks exclude
people from proposed floor/ground/wall regions. Both local VGGT configurations
estimated all 61 cameras; full-video DA3 was reused; COLMAP supplied 23 reference
poses in separate component gauges.

## What worked

With the earlier reference lens calibration shared across the pairwise fits,
**12 pairs passed the withheld homography check** and **13 passed the calibrated
relative-pose screen** (16 distinct pairs). Their union connects eight images,
from frame 006490 at **412.110100 s** through frame 006515 at **413.741811 s**.
A second trial using the later reference calibration produced 10 homography and
14 relative-pose passes, with the same eight-image connected component.

These are image-geometry screens, not eight accepted cameras. The matches are
mostly floor marks and cracks on a plane; planar ambiguity, translation scale,
and multi-view consistency remain unresolved. Shared calibration was held fixed,
not jointly optimized with a trajectory.

## Same-observation camera comparison

The table is the **median of per-pair median symmetric epipolar errors**, measured
in native pixels on the same withheld points in the 12 primary homography-supported
pairs. These pairs are correlated and selected for static planar support; this is
not a full-clip or full-video accuracy ranking.

| Camera estimate | Native pixel error |
|---|---:|
| Local VGGT, four submaps, size 16 | 2.49 |
| Existing full-video DA3 | 6.33 |
| Local VGGT, one submap, size 64 | 19.95 |
| COLMAP | Unavailable for these particular pairs |

The longest supported link, frame 006490 → 006513, scores **47.32 px** with four
VGGT submaps, **93.60 px** with one, and **18.73 px** with DA3. Putting all frames
into a single submap therefore did not repair this link. It does not prove that
submap boundaries never matter. Low epipolar error alone cannot certify depth,
metric scale, or a correct camera trajectory.

## Where recovery stops

**All 658 tested pairs crossing the return boundary at 414.562967 s lacked the
required fitting or withheld-match count.** None reached the fixed geometry test.
The largest such pair has 25 matches but only five withheld observations; another
has 19 matches but only 11 fitting observations. We retained the predeclared
minimums (12 fitting, six withheld) rather than selecting a threshold from these
results. This is insufficient evidence under this protocol, not proof that the
video is unrecoverable.

The accepted image-link graph does not reach the registered return frame 006531
or the later reference map. There is therefore no independently supported bridge
across the whole missing interval. Local bundle adjustment of only the supported
island would not establish that missing connection, and was not run.

## Visual inspection

All six [mask contact sheets](review/contact-01.jpg) were inspected. The mask
usually removes the foreground person's legs and retains visible floor, but can
miss portions of people and includes shadows moving across the floor. Motion
blur is visible around the return. A person mask also excludes some stationary
people; it is an architectural-region experiment, not a measured motion mask.

Correspondence examples inspected:

- [Before-gap to middle-gap link](correspondences/frame_006490--frame_006513.jpg).
- [Within-gap wider movement](correspondences/frame_006501--frame_006514.jpg).
- [Nearby floor detail](correspondences/frame_006513--frame_006515.jpg).

The marked floor matches look plausible, but cluster strongly in a small region.
Yellow lines show **all** withheld observations, including outliers; blue dots
show fitting observations. All 16 supported-pair panels are listed in
[the image index](correspondences/index.json). Visual plausibility is not a pose
acceptance test.

## Next bounded experiment

Try denser static point tracks through **413.74–414.86 s**, with forward/backward
consistency and explicit occlusion checks, then reconnect those tracks to earlier
and later sharp anchors. Pool observations across views and freeze **track-level**
holdouts before shared-lens local bundle adjustment; the current per-pair fold
split is not a valid global holdout for that optimizer.

This targets the observed sparse-match shortage. It can use weak floor texture,
but risks following shadows or crossing occlusions, so independent anchor checks
remain necessary. Simply increasing VGGT's context size was tested here and made
the measured errors worse. No full-video rerun is needed for the next experiment.

## Reproduction and provenance

- [Method and commands](../../docs/local-camera-gap-098.md).
- [Frozen selection and source hashes](selection.json); it was frozen before inference.
- [Raw camera-independent match cache](pairs.json).
- [Four-submap evaluation](evaluation.json) and [single-submap evaluation](evaluation-single.json).
- [Compact comparison and connected components](summary.json).
- [VGGT run/checkpoint provenance](run-provenance.json).
- Candidate camera outputs: [VGGT](vggt-poses.json), [single-submap VGGT](vggt-single-poses.json), [selected full-DA3 frames](da3-selected-poses.json).
- [Masks and per-frame metadata](masks.tar.gz), with normalized archive ownership.
- [Validation ledger](validation.json).

The selection manifest's `identity.script` is inherited from the **parent static
anchor selector**, not a claim that it generated this expanded selection. The
expansion retained gap-098 queries, anchors and controls, added every native frame
with `412.0 <= timestamp <= 414.9`, removed quality scores, and recalculated source
hashes. The committed manifest is the authoritative frozen input. Evaluation
receipts separately hash that complete manifest and each executed evaluator.
