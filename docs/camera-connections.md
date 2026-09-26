# Testing camera connections across the tracking losses

[Open the connection checks](https://parhamdb.github.io/sepehrbaba/camera-connections.html).

**There is still no verified continuous camera trajectory across the recording.**
The September 26 bridge experiment screened all 19 frozen loss windows. It found
four locally consistent candidates, five camera-agreement failures, and ten
windows without returning COLMAP cameras. No source camera or public 3D scene
was transformed, fused, interpolated or retrained.

## Results and their meaning

| Windows | Outcome | What is missing |
|---|---|---|
| 001, 005, 006, 008 | At least one method fits withheld cameras locally on both sides | Independent stationary landmarks establishing the relative placement of separate COLMAP components |
| 002, 007, 009, 014, 015 | No method passes the two-sided camera screen | Better camera estimates, calibration or more reliable reference anchors; missing anchors also limit some individual methods |
| 003, 004, 010, 011, 012, 013, 016, 017, 018, 019 | No reference return within the 20-second window | Longer inference windows reaching registered cameras after the actual gap |

DA3 remains the preferred method from the earlier **shared-observation**
comparison, but that ranking does not validate a bridge. In this screen, VGGT
alone survives the local camera checks at `loss-008`; DA3 fails them. Neither
has the independent stationary evidence needed to connect the 48s and 71s maps.
Earlier [cross-component feature matching](connecting-scenes.md) also failed to
establish this particular connection.

At `loss-014`, around **08:50**, COLMAP cameras return in the same component.
DA3's pre-gap coordinate fit disagrees with the post-gap cameras by a median
**7.3% of its fitted pre-gap reference span and 6.8 degrees**. VGGT's corresponding
values are **18.8% and 20.5 degrees**. These are separate method checks on 87 and
53 available post-gap cameras, respectively, **not a like-for-like ranking**.
They use alternating anchors for fitting, unlike the earlier comparison.
Fitting each side separately changes the scale factor by about **42% for DA3**
and **65% for VGGT**. Neither a single pre-gap transform nor hiding the drift
inside separate endpoint fits establishes an accurate bridge. COLMAP itself
is a reference, not ground truth.

At `loss-007`, DA3's post-gap orientation disagreement is about **20.6 degrees**.
VGGT has no valid pose output there. This gap also remains unresolved.

## Frozen camera screen

The inputs are the [same frozen cameras](../evidence/camera-comparison/inputs.json.gz)
used in the comparison. Select the component nearest the gap on each side;
do not choose a more distant component because it gives a better fit. Within
each side, alternate shared cameras into fitting and withheld sets. Fit a
positive-scale similarity from mean camera orientation and centers using only
the fitting set. Require at least five fitting cameras, five withheld cameras,
at least half a second of anchor coverage, median withheld position error at
most 5% of the fit's reference span, and median orientation error at most 5 degrees.

These are conservative **experimental screening thresholds**, not calibrated
uncertainty bounds or standards of evidentiary accuracy. Neural inference has
already seen all source images; "withheld" here means excluded from coordinate
fitting. Small motion and planar structure still make scale poorly constrained.

When the reference component is the same on both sides, also predict the
post-gap cameras using the pre-gap fit alone. With independent components,
export a *hypothesized* post-to-pre similarity but do not compare coordinates
as though they already belonged to the same world. Every exported transform
remains rejected or unverified. `accepted_connection` is always false in this
screening script; acceptance requires additional geometry and visual review.

## Independent stationary-floor trial

A second script tests a concrete source of geometric evidence at `loss-014`.
Two native RGB frames before the loss were reviewed manually and bare-floor
polygons selected. People, bags, gloves and the wheeled trolley were excluded.
The [selected regions and reports](../evidence/camera-connections) preserve what
was actually inspected. The trolley was deliberately excluded because it can move.

SIFT descriptors use mutual nearest-neighbor matches and a 0.7 ratio screen.
The map uses the fixed COLMAP anchor cameras. Triangulation requires positive
depth in both views, at least 1 degree of parallax and less than 2 native pixels
of reprojection error in each anchor. Every fifth seed feature ID is withheld
from PnP. A localization requires at least 12 fitting and six withheld landmarks,
then withheld median reprojection below 3.5 px and p90 below 8 px. Planar ambiguity
and false texture matches would still require visual review even if it passed.

Two distinct attempts were preserved:

1. Frames at 525.397 and 525.995 seconds: **zero mutual descriptor matches**, so
   no map and no usable localization control.
2. Closer frames at 525.795 and 525.995 seconds, to reduce appearance change:
   **two mutual matches, zero triangulated landmarks** after the fixed checks.

The controls in both trials and all **53 source frames in the original camera gap** remain
blocked. No PnP pose was exported. This is a failure of these selected regions,
views and matcher, not proof that floor-based reconstruction is impossible.
Representative source views also show near-total occlusion followed by severe
overexposure around 532.7–533.4 seconds. A camera prediction through those images
must retain uncertainty rather than be presented as observed geometry.

## Reproduce

```sh
python3 scripts/check_camera_connections.py \
  --inputs evidence/camera-comparison/inputs.json.gz --output NEW_REPORT.json
python3 scripts/check_static_floor_bridge.py \
  --inputs evidence/camera-comparison/inputs.json.gz \
  --selection evidence/camera-connections/floor-selection.json \
  --images NATIVE_IMAGES --output NEW_FLOOR_RUN
# Repeat with floor-selection-near.json to reproduce the second hypothesis.
python3 -m unittest discover -s tests -p test_camera_connections.py
```

NumPy and OpenCV are required; exact executed versions and input hashes are in
the reports. Outputs must be new paths. No credentials, host addresses or private
runtime paths are written into public results. No GPU inference is repeated.

## Next useful work

- For the ten missing-return cases, extend each inference clip through the
  actual first returning reference plus an anchor margin. Another 20-second
  comparison cannot validate these longer gaps.
- For the four locally consistent candidates, inspect fixed architecture or
  recognizable floor landmarks on both sides, then test their matches with
  withheld geometric observations. The existing neural similarity is only an
  initializer; it cannot supply its own proof.
- For 08:50, try a matcher robust to the observed blur/viewpoint change and more
  stationary anchor views. Keep complete occlusion explicitly unresolved if
  source evidence cannot constrain it. Do not fill it with an unlabeled spline.

Scripts and synthetic checks are a delivered tool, not a recovered camera path.
The [validation ledger](../evidence/camera-connections/validation.json) separates
software verification from unresolved reconstruction evidence.
