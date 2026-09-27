# Static-anchor gap recovery

This follow-up tests gaps **098 (412.29–414.51 s), 103 (438.63–446.57 s), and
144 (552.98–554.63 s)**, selected because the previous midpoint tests had relatively
more candidate matches. These are explicitly targeted cases, not an unbiased
sample of the entire recording.

The first campaign used sparse reference anchors and tested only gap midpoints
and first returns. Here we test the **first, midpoint and last missing frame** and
first registered return. Choose the nearest eligible reference component on each
side, then its sharpest registered frame in each of the 0–1, 1–2, 2–4, 4–6, 6–8
and 8–10 second distance bins. Whole-image Laplacian variance is only an anchor
selection proxy; it can favor a sharp person over a blurred floor. It does not use
camera-fit success or match counts to pick winners. Keep a distinct registered
control if one is available.

Freeze this selection for two otherwise identical variants:

1. Denser sharp anchors, original unmasked SIFT descriptors, ratio matching and
   LightGlue, fixed reference intrinsics and held-out-landmark PnP.
2. The same views and settings, restricting both anchor and query descriptors to
   SAM 3.1 proposals for **floor, ground and wall**, excluding a 21-pixel dilation
   of **person** masks. Descriptor centers must be at least `max(8, 12*scale)`
   pixels inside the allowed region. This conservative support check avoids using
   a floor-centered descriptor whose patch includes a foreground person.

SAM outputs are semantic proposals. They neither establish that an object is
stationary nor undo bad original triangulation. Reference maps remain provisional;
a passing camera screen needs visual/static correspondence review. Floor-only
constraints can also be ambiguous. Controls already present in the reference map
remain controls even if they pass.

The two reported search windows (10 and 30 seconds) are identical in this campaign
because explicit anchors are restricted to ten seconds. They retain the runner's
schema for comparison and must not be counted as independent supporting evidence.

## Reproduce

```sh
python scripts/select_gap_anchors.py --state "$BATCH/state.json" \
  --frames "$NATIVE/frames.json" --images "$NATIVE/images" --output selection.json
python scripts/mask_gap_anchors.py --selection selection.json \
  --images "$NATIVE/images" --output masks
# Run in the SIFT/LightGlue environment; add --masks masks for the masked variant.
python scripts/probe_gap_recovery.py --state "$BATCH/state.json" \
  --frames "$NATIVE/frames.json" --database "$DATABASE" \
  --reader "$COLMAP_SOURCE/scripts/python/read_write_model.py" \
  --lightglue "$LIGHTGLUE_SOURCE" --selection selection.json --output unmasked
```

Masking uses the cached, approved SAM 3.1 checkpoint in the SAM environment.
Extraction is native resolution. The established CPU ROI Align fallback supports
this hardware's torchvision build. Source, model, selection and mask hashes are
recorded; no credentials or host configuration are required in the public repo.

## Frozen acceptance inventory

One complete discovery, focused failure-only checks, one final validation of the
frozen artifact. No full-video inference or splat training in this campaign.

- Nine geometry/selection/resume tests, including mask support and sharp-anchor bins.
- SAM masks produced with verified source identities; inspect all selected previews.
- Three-gap unmasked and masked variants complete with identical selection/settings.
- Inspect any new passing camera correspondences; keep unsupported intervals unknown.
- Public scripts, reproducible selection, masks and results committed without private configuration.

A usable outcome is a reviewed recovery candidate **or a reproducible negative
result that distinguishes masking failure, lack of static texture and bad map
support**. This does not promise a continuous trajectory through fully obscured
frames. No automatic joins or invented camera paths are permitted.

## Paired experiment results

All 39 SAM previews were inspected. Cyan areas generally isolate visible floor
and wall surfaces; blur and some boundary errors remain. The person subtraction
also removes deceased people, whose semantic class does not imply motion. This
experiment tests architectural anchors, not whether every person is moving.

| Gap | Maximum unmasked missing-frame matches | Masked maximum | New passing poses |
|---|---:|---:|---:|
| 098 | 97 | 6 | 0 |
| 103 | 37 | 2 | 0 |
| 144 | 60 | 0 | 0 |

Unmasked: 120 screens, ten passing in-map control screens. Masked: 88 screens,
zero passing controls, plus eight unsupported query/direction combinations with
fewer than two usable descriptors. The 10/30-second rows duplicate each other.
No scene connection was accepted. These results do not establish that SAM masks
are intrinsically harmful: masking changes the landmark support available.

The support audit found a specific limitation:

| Gap | Earlier-map floor/wall landmarks | Later-map floor/wall landmarks |
|---|---:|---:|
| 098 | 14 | 34 |
| 103 | 4 | 3 |
| 144 | 4 | 2 |

Five of six reference maps cannot possibly meet the 18 distinct-landmark minimum
using this selected support. Some frames still have many unused static SIFT
features: the two earlier gap-144 anchors have 197 and 372 descriptors inside the
mask support, but only four reconstructed landmarks in their union. That motivates
triangulating additional static points from fixed reference cameras, instead of
repeating a matcher against an almost empty map. Query frames also vary sharply:
gap-144's midpoint has 168 static descriptors, whereas its first and last missing
frames have zero and one. Neither rematching nor triangulation alone fixes frames
with no repeatable visible signal.

Evidence: [frozen selection](../evidence/static-gap-recovery/selection.json),
[unmasked report](../evidence/static-gap-recovery/unmasked.json),
[masked report](../evidence/static-gap-recovery/masked.json),
[feature/map support audit](../evidence/static-gap-recovery/support.json),
[reproducible mask archive](../evidence/static-gap-recovery/masks.tar.gz), and
[review contact sheets](../evidence/static-gap-recovery/review).

## Fixed-camera retriangulation follow-up

The support audit justified a second local test: build separate floor/wall
landmarks from **all usable masked SIFT features**, without requiring that they
were already mapped. Match anchor pairs with mutual-ratio SIFT or LightGlue,
triangulate with their fixed reference cameras, and require positive depth,
at least one degree of parallax and under two native pixels of reprojection error.
Merge compatible feature tracks, forbid two different observations in one image,
and check every merged observation. Distinct feature orientations within three
pixels do not become separate landmarks. All query and control frames are excluded
from map construction. Keep landmark-origin labels: some points retriangulate
existing tracks, so a constructed point is not automatically a newly discovered
landmark.

`triangulate_static_gap.py` accepts the same selection, database, reader and masks:

```sh
python scripts/triangulate_static_gap.py --state "$BATCH/state.json" \
  --selection selection.json --database "$DATABASE" \
  --reader "$COLMAP_SOURCE/scripts/python/read_write_model.py" \
  --masks masks --output triangulated-sift
# Add --matching lightglue --lightglue "$LIGHTGLUE_SOURCE" with a new output.
```

This is a diagnostic candidate map, not a replacement reconstruction. A source
camera can still be wrong, and repeated floor patterns can produce wrong matches.
Do not infer which is responsible from a reprojection rejection alone. Three
focused geometry tests cover track conflicts, duplicate feature orientations,
known 3D triangulation and zero-parallax rejection, in addition to the nine tests
above. No image, source camera or original model is modified.


Final results: [comparison, per-gap next methods and evidence](../evidence/static-gap-recovery/results.md).
SIFT constructed five candidate points; LightGlue constructed 36 across six
independent maps, 26 using only previously unmapped anchor observations. No map
reached sufficient supported query matches for a new passing camera. Four
[largest-support correspondence overlays](../evidence/static-gap-recovery/landmarks)
were inspected: many points lie on small floor marks or cracks and are spatially
clustered. They remain provisional rather than certified evidence geometry.

All final checks passed as execution/measurement checks; **camera recovery did not
pass**. The original maps and scene remain separate. Both source code and negative
results are preserved so a future method can target these exact frames without
repeating full-video inference.
