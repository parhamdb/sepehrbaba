# Provisional alignment from the human-selected matches

**[Open the interactive 3D comparison](https://parhamdb.github.io/sepehrbaba/provisional-alignment.html).**
This is a reversible local placement hypothesis using the six human-selected
correspondences. It does not certify camera recovery or modify the original
Gaussian scenes. The user explicitly requested an approximate alignment preview
after observing convincing visual overlap in the shared object.

## What is available

Cyan and orange point clouds represent the two previously tested windows,
409.736733–410.738200 s and 414.913478–415.994922 s. All **42 cached depth frames**
are included: **331,632 samples per side**, using every third depth pixel in each
axis. No depth model or splat trainer was rerun. The default shows the two seed
frames; “All nearby frames” exposes the full windows and their motion artifacts.
This covers approximately one second on each side, not the complete sections or
all twelve minutes.

Drag or use arrow keys to orbit, scroll/pinch or +/− to zoom, right-drag or
Shift-drag to pan. Layer toggles let you inspect either cloud. Photo colors show
original image colors, while cyan/orange distinguish the source windows. Lines
connect the six selected points. Reset and top views are available. The viewer
checks both binary-file SHA-256 hashes before displaying them.

[Your selections](../numbered-landmarks/human-choices.json) remain exactly
Q1→2, Q2→1, Q3→1, Q4→1, Q5→1 and Q6→4. Neither Luna's abstentions nor the prior
camera-fit threshold vetoes using them as provisional alignment constraints.

## Three comparisons

1. **Landmarks + floor direction** is the default *view*. It keeps the scale from
   the six-point similarity, aligns the estimated floor normals, then fits yaw
   and translation to the six landmarks. Vertical translation remains free.
   The floors are parallel, but a **−0.1124-unit height offset** remains visible.
2. **Six landmarks only** is the primary unconstrained fit. A proper-rotation
   similarity maps the later seed's 3D points to the earlier seed's points,
   using all six equally and no outlier removal. Scale is **0.6072** between the
   two normalized local frames. Its estimated floor normals differ by **118.0°**,
   demonstrating that fitting this small region does not establish the surrounding
   scene geometry.
3. **Original cached cameras** shows the retained DA3 global relationship in the
   same earlier-camera coordinate frame. It is a comparison, not a reference truth.

All distances are in normalized model units: the earlier seed's median landmark
depth is one unit. They are **not metres**. Each local cloud was normalized by
its own seed's median depth before the similarity was estimated.

| Point | Six-point residual | Floor-direction residual |
|---|---:|---:|
| Q1 | 0.0313 | 0.0551 |
| Q2 | 0.0114 | 0.0359 |
| Q3 | 0.0148 | 0.0387 |
| Q4 | 0.0320 | 0.1414 |
| Q5 | 0.0131 | 0.0212 |
| Q6 | 0.0420 | 0.0273 |

These are fitting residuals, not accuracy estimates. The floor-direction option
trades point agreement for an explicit structural hypothesis. It has not acquired
independent validation by enforcing its own floor constraint.

## Floor check and bounded alternatives

The following native-image rectangles were selected by visually inspecting the
original seed frames **before** calculating floor fits:

- Earlier: `(5,1430)–(150,1830)` and `(750,1770)–(1060,1910)`.
- Later: `(250,1350)–(1000,1860)`.

The sampled rectangles contain visible floor; they are not corresponding tile
corners. RANSAC used a fixed 0.01 local-unit plane threshold and seed 20260927,
then SVD refinement. Both sampled patches fit their own cached depth closely.
That establishes local model planarity, not physical accuracy or shared position.
“Floor samples only” displays these seed patches. Source images are linked in the
viewer; exact plane equations and bases are retained in the numerical record.

The earlier model places several selected object points slightly below its fitted
floor, while the later model places the points above its floor. This discrepancy
is consistent with the previously observed weak earlier depth confidence.

Three bounded hypotheses were examined and retained:

- Coincident floors plus six-point fitting yielded a **negative scale**, which is
  physically unsuitable and was rejected. The initial generator stopped before
  producing a complete alignment report; its partial clouds were retained privately.
- Parallel floors with freely optimized scale collapsed the later scene to
  **0.01648** of its normalized size. This diagnoses conflicting vertical geometry;
  it is not used as a usable placement.
- The published floor-direction alternative fixes scale to the unconstrained
  landmark estimate **0.6072**, preserving the scene's size while showing the
  remaining vertical mismatch. We stopped geometric variants at this point.

No floor height was secretly shifted to zero, no holes were filled, and no scene
geometry was deformed to make the match appear stronger. The single shared floor
cannot determine horizontal translation or yaw by itself; those depend on the
human-selected region. Nearby objects are available for visual comparison, but
no additional object or floor point has been certified as an independent match.

## Coordinate and data provenance

The input is the [depth-camera experiment](../depth-landmarks/results.md), whose
source/depth frame mapping and image hashes were checked. Each point is unprojected
using its cached intrinsic matrix, transformed by its cached camera into its
window's seed-camera frame, and divided by that seed's median depth. The selected
landmarks use the retained `cached_lens` unprojections with the same coordinate
convention. A separate proper rotation levels the display against the earlier
floor; it changes neither fitted distances nor the underlying coordinate data.

- [Alignment, transforms and hashes](alignment.json)
- [Initial frozen plan](plan.json): its `default` identifies the primary six-point
  fit; the viewer defaults to the subsequently derived floor-direction comparison.
- [Floor diagnostic and follow-up rationale](floor-check.json)
- [Delivery verification](verification.md)

The binary point-cloud format is 16 bytes per sample, little endian: three
float32 coordinates, three RGB uint8 values, and one uint8 tag. Tag bits 0–6 are
frame slot 0–20; bit 7 marks a selected seed-floor sample. Frame groups are contiguous
in order. The viewer draws only the selected group by default, avoiding unnecessary
work on hidden frames. Binary SHA-256 values, frame counts, timestamps and depth
hashes are in the alignment JSON. Original images and existing scene assets were
not edited. No personal runtime configuration or credentials are published.

```bash
# Compatible NumPy environment; no GPU is needed for this retained-data step.
python3 scripts/build_provisional_alignment.py \
  --depth-evidence evidence/depth-landmarks --da3 DA3_EXPORT \
  --output runs/provisional-alignment
python3 scripts/verify_provisional_alignment.py runs/provisional-alignment
# Published site uses the existing locked PlayCanvas dependency.
npm ci
npm run build
```

The viewer uses the project's PlayCanvas 2.22.3 dependency, with point meshes and
custom color/frame selection shaders. Official API references:
[Mesh](https://api.playcanvas.com/engine/classes/Mesh.html) and
[ShaderMaterial](https://api.playcanvas.com/engine/classes/ShaderMaterial.html).

Further reconstruction should improve or cross-check local depth and obtain
spatially separate stationary correspondences. The preview is useful for examining
that problem now; it is not promoted to an accepted merged reconstruction.
