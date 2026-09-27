# Static-anchor recovery results

[Method and limitations](../../docs/static-gap-recovery.md) · [Selection](selection.json) · [Mask archive](masks.tar.gz) · [Support audit](support.json)

All three selected gaps completed. No missing-frame or cross-component camera passed. Twelve focused unit tests passed. The paired runs differ only by static-mask filtering, with identical anchors, queries, original camera models and PnP settings.

| Gap | Unmasked maximum missing-frame matches | Masked maximum | Earlier/later SIFT triangulated points | Earlier/later LightGlue points |
|---|---:|---:|---:|---:|
| gap-098 | 97 | 6 | 0/4 | 13/14 |
| gap-103 | 37 | 2 | 0/0 | 0/0 |
| gap-144 | 60 | 0 | 0/1 | 7/2 |

**triangulated-sift:** 5 constructed points across independent maps; 0 use only previously unmapped anchor observations. 12 raw pair matches, 7 pair triangulations before track merging, 30 PnP screens, 0 new-pose passes.

**triangulated-lightglue:** 36 constructed points across independent maps; 26 use only previously unmapped anchor observations. 134 raw pair matches, 44 pair triangulations before track merging, 30 PnP screens, 0 new-pose passes.

Constructed points are provisional, may retriangulate existing landmarks, and can represent the same physical feature in different component gauges. They are not 36 certified new scene points or a connected reconstruction.

## What each gap needs next

- **098:** the richer static maps remain below the required landmark support. Check correspondences against local camera estimates, then broaden overlap or refine cameras using static matches. The first and midpoint frames contain usable static features; the last missing frame has only five descriptors after support filtering.
- **103:** very few repeatable floor/wall descriptors survive. Search other rigid surfaces, including stationary objects, while distinguishing moving people from stationary human remains. A semantic person mask alone cannot make that distinction.
- **144:** the midpoint and earlier anchors contain many static descriptors, but few pair matches satisfy the fixed cameras. Independently validate the correspondences and local camera/lens calibration before optimizing either. The first/last missing frames have zero/one surviving descriptors.

LightGlue increases constructed points, but many pair matches fail the fixed-camera reprojection check. The tests do not distinguish a wrong match from a wrong reference pose or calibration. Insufficient parallax is not the dominant rejection in these particular LightGlue pairs. Thresholds were not relaxed to force acceptance.

## Preserved evidence

- [Unmasked PnP](unmasked.json)
- [Masked PnP](masked.json)
- [SIFT retriangulation](triangulated-sift.json)
- [LightGlue retriangulation](triangulated-lightglue.json)
- [All 39 mask previews in four contact sheets](review)
- [Validation ledger](validation.json)
