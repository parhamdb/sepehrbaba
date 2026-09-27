# Recover camera gaps with a portfolio of methods

The goal is to recover this recording locally, using whichever method is supported
at each gap. Preserve each original camera component. Add a pose or a component
connection only after independent geometric checks; do not average incompatible
trajectories or interpolate across unseen motion and call it measured.

## Current inventory and first experiment

The completed full-video batch contains **239 provisional camera components**.
Their union covers **9,403 / 12,793 native frames**, leaving **3,390 missing poses**
in **229 runs**, of which **47 span at least one second**. There are also **84
adjacent registered-frame transitions without a common component**. These are
connection candidates, not necessarily 84 distinct disconnected scene pairs.
The union includes models whose splat training failed; camera availability and
accepted reconstruction quality are separate quantities.

[Machine-readable inventory](../evidence/gap-recovery/inventory.json) includes
all gaps, timestamps, surrounding observations and component transitions. Gap
span is last missing timestamp minus first missing timestamp, not a duration
including the surrounding tracked frames. The source lasts 737.301333 seconds.

First bounded experiment: all 47 longer gaps; test their midpoint and first
returning registered frame. Compare **SIFT versus LightGlue**, **10 versus 30
seconds**, and **lookback versus lookahead**: eight variants per query where
anchors exist. Use up to four existing reference views per direction, matched
against existing native-resolution descriptors. Estimate PnP with one fixed
calibration per reference component. This is local lens consistency, not yet a
single calibration recovered for the entire video.

Positive controls use nearby registered views, excluding the query itself as an
anchor. Their landmarks must have at least three other observing views, but their
map was not rebuilt without the control: controls test plumbing, not independent
accuracy. Withhold landmark IDs divisible by five from PnP. Require 12 fit
inliers, six distinct held-out landmarks, median held-out error below 3.5 native
pixels, p90 below eight, positive depth and at least 0.5% image-area coverage.
Duplicate orientations, repeated landmarks and query locations within three
pixels cannot inflate the count. World coordinates are locally normalized.

**Passing is only a camera candidate.** Existing sparse maps can contain people.
Static-region review, more query frames and independent validation are required
before promoting a pose; a component join additionally needs consistency of its
scale, rotation and translation. Any query already present in the selected reference map is explicitly labelled
a control and excluded from recovery counts, including returns reached from the
earlier side. No source databases or scenes are modified.

## First completed result

[Per-gap results and comparison table](../evidence/gap-recovery/results.md): all 47
selected gaps completed, 912 PnP screens, 1,248 image-pair/matcher trials. No new
pose passed; 16 in-map control screens passed. Six source triptychs were visually
inspected. This rejects this sparse-anchor configuration on these query frames,
not relocalization in general. The low control pass rate is an additional reason
not to treat this as a definitive ranking of algorithms. All other methods retain explicit tested/untested
status below.

**Next completed campaign:** [denser anchors and SAM static-region comparison](static-gap-recovery.md), including the map-support audit.

## Targeted follow-ups

[Nearest-map and ALIKED results](../evidence/gap-recovery/followups.md): both
completed on gaps 007, 034 and 135. Neither recovered a new pose. Across the full
pass and two follow-ups, 1,056 PnP screens were evaluated; none was promoted to an
accepted new camera. These three focused hypotheses are closed, with all outputs
retained for revisiting the failure cases.

## Ranked recovery methods for this video

Priority means expected usefulness given our observed gaps, not a universal
ranking. Combine methods at individual gaps; preserve failed attempts too.

| Priority | Method | Best use / limitation | Current experiment status |
|---|---|---|---|
| 1 | Relocalize against earlier static 3D landmarks, looking back 10 s then 30 s | An occluder interrupts adjacent-frame matches; use PnP against the old map. Cannot recover unseen motion. | SIFT and LightGlue trials implemented; initial campaign below. |
| 2 | Offline reverse recovery and actual-return windows | Later clear frames can recover earlier gap views. Extend through the actual return, rather than stopping at an arbitrary 20-second clip. | Lookahead PnP included; long-window remapping still untested. |
| 3 | Fixed/shared lens calibration plus local bundle adjustment | Prevent focal changes from absorbing motion/scale error. One physical lens is strong evidence, but phone stabilization/cropping may still change effective intrinsics. | Per-component fixed calibration included; whole-video shared calibration and BA remain untested. |
| 4 | Static architectural/floor masks with SAM 3.1 plus geometric motion rejection | Remove moving-person matches; retain floor, walls, pillars and other rigid landmarks. SAM proposals need review, and a stationary-looking person is not an architectural anchor. | Targeted 39-image SAM static-surface ablation completed on three gaps; no new pose passed. Motion-specific masking remains untested. |
| 5 | Stronger descriptors/matchers: ALIKED + LightGlue, DSP-SIFT, guided matching | Illumination, viewpoint and low texture changes; avoid mixing descriptor families in one database. | Cached SIFT + LightGlue included; Targeted ALIKED-descriptor follow-up recorded below; DSP-SIFT remains untested. |
| 6 | Adaptive wider local SfM, triangulation and bidirectional registration | More overlap and parallax than a short clip; extend only where new anchors exist. | Fixed-camera static retriangulation tested on three gaps (SIFT and LightGlue); full local camera remapping remains untested. |
| 7 | Retrieve revisits anywhere in the recording and geometric loop closure | Reappearing walls/floor may connect distant components. Appearance retrieval only proposes pairs; repeated tiles can cause false matches. | Full DA3 had loop proposals; independent full-history landmark retrieval untested. |
| 8 | Local DA3 and VGGT-SLAM proposals, cross-checked against static geometry | Seed difficult local views when feature methods fail. Full DA3 showed severe scale drift; learned pose agreement alone is insufficient. | Existing loss-window and full-DA3 results retained; new extended-window trials not yet run. |
| 9 | Joint graph optimization and bundle adjustment of verified connections | Combines different successful local methods into one trajectory. Reject inconsistent edges first; do not force connectivity. | Waiting for independently accepted bridge edges. |
| 10 | Piecewise floor planes, wall normals and vanishing directions | Check roll/pitch and relative floor height. A floor alone cannot determine sideways position or yaw; stairs/curbs require separate planes. | [Floor diagnostic](floor-drift.md) completed; constraint optimization untested. |
| 11 | Manual static landmark annotations and calibrated local reconstruction | Rescue a few important gaps where automation has no repeatable features; record annotation provenance and withheld points. | Earlier loss-014 floor attempt unsupported; other annotations not done. |
| 12 | Motion priors / interpolation | Optional navigation preview through completely obscured intervals. It is an inferred path, never recovered evidence or a scene join. | Excluded from measured recovery. |

Generating missing scenery is **not camera recovery**. If later used for an
illustrative view, it must remain a separately labelled generated layer, absent
from evidence geometry. Complete occlusion may leave permanently unknown frames.

## Reproduce and inspect

`inventory_camera_gaps.py` reads the saved full-batch state and native timestamps:

```sh
python scripts/inventory_camera_gaps.py --state "$BATCH/state.json" \
  --frames "$NATIVE/frames.json" --output inventory.json
python scripts/probe_gap_recovery.py --state "$BATCH/state.json" \
  --frames "$NATIVE/frames.json" --database "$DATABASE" \
  --reader "$COLMAP_SOURCE/scripts/python/read_write_model.py" \
  --lightglue "$LIGHTGLUE_SOURCE" --output "$EXPERIMENT"
```

Needs NumPy, OpenCV, CUDA PyTorch and the cached SIFT LightGlue weights. LightGlue
is pinned to `eb42fee2d71449efb0aa5c10549752b5d75384d8`. The reader and database
are hashed along with model binaries, inputs and scripts. Use a quiescent database
with no nonempty WAL. All recorded reference-model hashes are checked on resume and at completion.
The output is checkpointed after each gap and can resume
only with identical identities/options. `--gap-ids gap-007 gap-034 gap-135`
restricts a pilot; keep it in a separate output directory from the full campaign.
`--reference-policy nearest` tests a closer, smaller map instead of the largest
local reference. `--descriptor aliked-at-sift --images "$NATIVE/images"` replaces
the descriptor at existing SIFT locations, comparing mutual-ratio matching and
ALIKED LightGlue. It does not run a fresh ALIKED keypoint detector or retriangulate
the map. Extraction uses CPU to support the available torchvision build, with
LightGlue on CUDA; source image hashes are retained and checked.

## Frozen validation inventory

One discovery pass, failure-only corrections, then one final pass of these checks:

1. Synthetic inventory, time-window selection, duplicate rejection and PnP
   positive/negative/scale controls (seven unit tests, including follow-up reference selection).
2. Actual native feature/model compatibility and GPU matching on Thor.
3. Complete all 47 gap experiments, or explicitly retain a running checkpoint.
4. Inspect representative recovered candidates and failure source frames.
5. Public evidence contains no host paths, credentials or personal configuration.

The runnable minimum delivery is this inventory plus the gap-wise experiment
report and reproducible scripts. Dense recovery of all 3,390 frames, certified
component joins, new splat training and generative completion are outside this
first experiment. They follow the resulting per-gap evidence.

## Primary references

- [COLMAP relocalization, shared/fixed intrinsics and reconstruction options](https://colmap.github.io/faq.html)
- [COLMAP matching and reconstruction tutorial](https://colmap.github.io/tutorial.html)
- [LightGlue official implementation](https://github.com/cvg/LightGlue)
- [Hierarchical Localization: retrieval and local feature localization](https://github.com/cvg/Hierarchical-Localization)
- [VGGT-SLAM official implementation](https://github.com/MIT-SPARK/VGGT-SLAM)
- [Depth Anything 3 official implementation](https://github.com/ByteDance-Seed/Depth-Anything-3)
- [SAM 3 official implementation](https://github.com/facebookresearch/sam3)

**Local camera follow-up:** [gap 098 independent geometry and VGGT context ablation](../evidence/local-camera-gap-098/results.md). All 1,830 pairs were tested; the supported image graph stops before the registered return. Zero new poses accepted.
