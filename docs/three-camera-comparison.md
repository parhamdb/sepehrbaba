# Three camera estimates around the same tracking losses

[Open the synchronized comparison viewer](https://parhamdb.github.io/sepehrbaba/camera-comparison.html).
It compares original COLMAP, VGGT-SLAM and DA3-Streaming on the **same 19 windows**,
each ten seconds before and ten seconds after the loss onset. Every selected
source frame and its original relative timestamp is retained in the videos.
The original recording and published 3D scenes are unchanged.

The follow-up [connection checks](camera-connections.md) test both sides of the gaps; no join is verified.

## Findings

**Retain COLMAP where it tracks; prioritize DA3 for further gap-recovery trials.**
This is a recommendation from camera/image agreement, not verified recovery.

- COLMAP has the lowest median image disagreement in **all 18 three-way overlap
  comparisons**. Across those clips, the median of per-clip scores is **2.25
  native pixels for COLMAP, 4.18 for VGGT, and 3.62 for DA3**.
- Where COLMAP has no pose, DA3 scores lower in **14/18** comparisons; VGGT scores
  lower in four. Some margins are small. These counts are not significance tests.
- The clearest retained-reference comparison is the loss near **08:50**
  (`loss-014`). After fitting coordinates only before the loss, the same 53
  post-gap frames show median position disagreement of **18.6%** of the pre-loss
  reference span for VGGT versus **8.7%** for DA3; orientation disagreement is
  **20.3° versus 6.6°**. COLMAP remains a reference, not ground truth.
- Around the important **03:05** occlusion (`loss-008`), gap-region image errors
  are **7.32 px for VGGT versus 5.81 px for DA3**, from only **14 supported pairs**.
  The original COLMAP reconstructions on either side are separate components,
  so this test cannot certify their connection. Different residual summaries
  can favor different methods: moving visitors and weak image support matter.
- VGGT failed camera decomposition on `loss-007`; DA3 produced estimates for
  every selected frame in every clip. Dense camera output is not proof of accuracy.

**No tracking gap has been declared geometrically recovered by this comparison.**
It does establish which estimates agree better with the tested image evidence
and where a meaningful retained-camera reference exists.

## What is—and is not—available

All source images exist for all three methods. COLMAP has camera gaps. In **10
of the 19 windows**, it does not return within ten seconds of the loss onset.
In others, its return belongs to a different local component. Only `loss-007`
and `loss-014` have usable pre-loss and post-gap cameras in the same selected
reference component. Missing poses stay missing; independent components are
never joined or treated as a continuous ground-truth trajectory.

The comparison freezes the reviewed COLMAP snapshot used to identify the losses
and fills its absent frames from the same 31 native raw model inventories used
by clip selection. Existing snapshot poses take priority; among raw models,
the largest component wins with a fixed label tie-break. This reproduces the
4,946-frame union that defined the experiment. New results from the separate
full-recording processing job are deliberately outside this frozen comparison.

## Reading the videos

The left, middle and right panels show **the identical source frame** for COLMAP,
VGGT and DA3. Source-relative timestamps are displayed. Videos are silent.

- Cyan dots are image observations measured independently by forward/backward
  Lucas–Kanade tracking. Short yellow/red lines show each method's discrepancy
  from the corresponding epipolar constraint. These are not semantic landmarks.
- A score is shown only at the exact endpoint of an evaluated frame pair.
  Frames without a shared pair retain their source image and pose status.
- Below each image is a camera path. All three panels use the same plotting view
  and scale. Predicted paths are aligned to one COLMAP component using only
  pre-loss shared cameras. Grey is the reference path. Other COLMAP components
  are explicitly marked as unaligned and are not plotted as joined paths.
- Path lines connect estimated samples; they do not create intermediate camera
  poses. A frame without a VGGT keyframe is labeled accordingly. A failed solver
  has a distinct failure label.

## Numerical comparison

The [frozen input cameras](../evidence/camera-comparison/inputs.json.gz) and
[report](../evidence/camera-comparison/report.json) retain source frame names,
timestamps, calibrations, component identities, counts and input hashes. Detailed
pair observations are retained in `pair-reports.json.gz` alongside the report.

For overlap scores, use only frames estimated by every participating method,
pair consecutive common frames no more than 0.75 seconds apart, and reject
COLMAP component changes. For the failed VGGT clip, compare COLMAP and DA3 only;
exclude that clip from three-way aggregate statistics. A second, separate
VGGT/DA3 comparison uses pairs where COLMAP lacks at least one endpoint.
Both methods receive exactly the same observations and pairs in each comparison.

Track up to 400 corners on 540×960 source views; require forward/backward agreement
within one working pixel and in-frame tracks. Score symmetric distances to the
predicted epipolar lines in **native 1080×1920 pixels**. No new camera or fundamental
matrix is fitted to those image correspondences. A pair contributes to aggregates
only with at least 20 corners and finite constraints from every participating
method. Aggregate the pair medians within each clip; clip scores have equal
weight in the reported across-clip median. `loss-003` has only seven supported
three-way pairs, so its overlap result is particularly limited.

Calibration handling preserves each model's camera convention. COLMAP's radial
distortion is undone before scoring. DA3 intrinsics are mapped from its verified
280×504 portrait processing coordinates to the native image. VGGT's 518-square
pad transform is inverted. Its cameras often include skew: observations with
zero distortion are preserved directly, and the full intrinsic matrix is used
in the epipolar relation. A synthetic skew-camera test caught and now prevents
an OpenCV zero-skew assumption from corrupting those scores. The initial affected
analysis is retained privately as rejected evidence; only corrected scores are
published.

For coordinate plots and post-gap agreement, estimate a single rotation from
pre-loss camera orientations, then positive scale and translation from pre-loss
centers. At least five shared anchor frames with nonzero translation span are
required. Fit no post-gap camera. Compare post-gap positions/orientations only
on identical frames and within the same reference component. Position deviations
are fractions of the pre-loss reference span, **not meters**. A large pre-loss fit
error is displayed rather than hidden.

## Limits and next use

Visitors can dominate image flow; bodies, clothing and bags can also move. Low
parallax, planar surfaces, blur and camera calibration errors can make epipolar
scores misleading. They do not validate translation scale. Pre-loss gauge fitting
can absorb coordinate differences and is not proof of a shared physical map.
Contact-sheet inspection is distinct from continuous video inspection or manual
stationary-landmark verification; inspection receipts record the actual review.

The useful next reconstruction experiment is to retain trustworthy COLMAP camera
anchors and test DA3 constraints in the gaps, beginning with `loss-014` and the
03:05 break. This report does not perform that fusion or replace the public scene.
Manual stationary-region checks and masks for moving visitors remain necessary
before treating any join as accepted reconstruction evidence.

## Reproduction

Use the existing native images and completed solver runs; no model inference is
rerun by these scripts. Paths are runtime inputs and must stay out of public data.

```sh
python3 scripts/prepare_camera_comparison.py \
  --inventory INVENTORY.json --snapshot SNAPSHOT.json.gz \
  --raw-inventory RAW_INVENTORY.json --native NATIVE_RUN \
  --vggt VGGT_BATCH --da3 DA3_BATCH --da3-first DA3_FIRST_TRIAL \
  --output NEW_COMPARISON/inputs.json.gz
python3 scripts/compare_camera_tracks.py \
  --inputs NEW_COMPARISON/inputs.json.gz --images NATIVE_RUN/images \
  --output NEW_COMPARISON/analysis
python3 scripts/render_camera_comparison.py \
  --inputs NEW_COMPARISON/inputs.json.gz --analysis NEW_COMPARISON/analysis \
  --images NATIVE_RUN/images --output NEW_COMPARISON/videos
python3 -m unittest discover -s tests -p test_camera_comparison.py
```

The comparison environment uses NumPy, OpenCV, Pillow, PyAV and ffprobe; the
existing [VGGT environment versions](../evidence/camera-loss-benchmark/vggt-packages.json)
were retained. No credentials, hostnames or private runtime paths belong in the
published artifacts. The acceptance inventory is seven focused geometry checks,
19 video frame/timing checks, artifact/privacy checks, and desktop/mobile viewer
selection and playback. One discovery pass, focused fixes and one final pass
are the validation budget; unrelated 3D viewer tests are outside this change.

## Delivery evidence

All 19 comparison videos contain **6,504 frame appearances** in total (overlapping windows can repeat source frames). Each passed frame-count and relative-timestamp verification. [Artifact hashes](../evidence/camera-comparison/artifacts.json), [representative inspection](../evidence/camera-comparison/inspection.json), and the [validation ledger](../evidence/camera-comparison/validation.json) record the checked scope. Browser checks exercise every clip selector on desktop and mobile, playback, seeking, failed-method labels and missing-reference warnings.
