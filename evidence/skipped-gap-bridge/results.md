# Skipping the missing interval: direct section alignment remains unsupported

**The two sections have not been joined.** We excluded the missing camera frames
and tested a direct connection between the existing reconstructed pieces. All
three bounded attempts completed, but none supplied enough independent static
3D correspondences to estimate and validate their relative rotation, position,
and scale. No public scene or source camera model was modified.

## What was tested

The earlier piece has 78 registered views covering **408.13–412.23 seconds**; the
later has 235 covering **414.56–427.80 seconds**. We ranked all 313 images for
sharpness and selected two per one-second bin: **10 before and 28 after**. Thus
this tests views farther from the gap within those components, not only the two
immediately adjacent frames. It does not search unrelated components elsewhere
in the recording.

Of 38 SAM static-region masks, 13 were reused and 25 inferred. SIFT + LightGlue
and fresh ALIKED + LightGlue each processed **703 image pairs**, including the
same **280 before/after pairs**. No gap image participated. Inference results and
raw correspondences are preserved for further analysis.

| Attempt | Static 3D landmarks before / after | Unique cross-section landmark groups | Fitting / withheld groups | Accepted connection |
|---|---:|---:|---:|---|
| Existing SIFT map landmarks | 25 / 36 | 2 | 2 / 0 | No |
| SIFT plus newly triangulated static tracks | 33 / 40 | 3 | 3 / 0 | No |
| Fresh ALIKED detections and triangulation | 5 / 1 | 0 | 0 / 0 | No |

The fixed requirement is at least **12 fitting and six withheld distinct
landmark groups**, followed by 3D and bidirectional image reprojection checks.
All three attempts stopped at the support check; no similarity transform was
fitted. A three-point mathematical fit without independent validation would not
establish that these are the same physical landmarks.

Independent pairwise image-geometry diagnostics also produced **zero passes**.
For SIFT, 278 of 280 cross pairs lacked fitting/holdout counts; the other two
failed the geometric screen. All 280 ALIKED cross pairs lacked the counts.
The largest raw SIFT pair had 22 matches; the largest ALIKED pair had 13. A raw
match count is not a count of correctly reconstructed shared landmarks.

## What the images show

We inspected all four [mask contact sheets](review/contact-01.jpg) and two strongest
cross-pair panels per matcher:

- [SIFT: 408.89 → 416.55 seconds](sift-review/frame_006427--frame_006569.jpg).
- [SIFT: 411.34 → 415.54 seconds](sift-review/frame_006476--frame_006549.jpg).
- [ALIKED: 411.34 → 416.55 seconds](learned-review/frame_006476--frame_006569.jpg).
- [ALIKED: 412.05 → 416.55 seconds](learned-review/frame_006489--frame_006569.jpg).

The candidate matches concentrate on floor cracks, tile seams, or small patches;
some appear inconsistent. The later views increasingly show bodies and bags with
little exposed floor. Both feature caches have **12 images with no retained
features** after static-mask and boundary filtering. Shadows remain visible on
the floor; a floor mask does not make every feature stationary.

These masks deliberately target architecture and subtract detected people. They
also exclude stationary people, and generally omit body bags and clothing rather
than assessing their motion. This conservative choice can discard potentially
useful stationary detail. The experiment therefore rejects these three automatic
architectural-feature configurations, not the possibility of joining the scene.

All six strongest cross-pair panels are indexed for each matcher:
[SIFT](sift-review/index.json), [ALIKED](learned-review/index.json). Yellow lines
show unverified raw candidates; none is presented as a verified connection.

## Next decision

The shortest different approach is a **manual common-landmark audit** of the two
sections: identify genuinely shared floor intersections, distinctive cracks, or
stationary object details; record the image coordinates and provenance; then
attempt alignment with separate withheld annotations. This can rescue features
that automatic detectors miss, but cannot create overlap that is absent. Static
object candidates must be checked for actual movement rather than accepted solely
because they are not standing people.

An approximate manual placement could also support a navigation preview, but
would need a separate label and must not be presented as recovered evidence.
No approximate placement was performed in this campaign. The missing two seconds
can stay unknown even if a future section alignment succeeds.

Three distinct hypotheses are complete; further automatic variants were stopped
under the bounded attempt policy. All outputs are retained for revisiting them.

## Reproduce and inspect

- [Method, thresholds and commands](../../docs/skipped-gap-bridge.md).
- [Frozen selection, all sharpness scores and source hashes](selection.json).
- Raw caches: [SIFT](sift-pairs.json), [ALIKED](learned-pairs.json), including learned checkpoint hashes.
- Final evaluations: [existing landmarks](existing-final.json), [augmented SIFT](augmented-final.json), [fresh learned landmarks](learned-final.json).
- Discovery evaluations: [existing](existing.json), [augmented](augmented.json), [learned](learned.json).
- [Comparison summary](summary.json), [validation ledger](validation.json).
- [Static masks and per-image metadata](masks.tar.gz); archive ownership normalized.

The final evaluations reproduced every discovery result after freezing the source
at `79fc4b5`. Eight numerical controls passed. Five execution checks passed with
zero failed, blocked or untested checks; **the scientific connection remains
blocked by insufficient support**, separately recorded in the ledger. Independent
review found and verified fixes for per-image coverage and incomplete-cache
handling before the first dataset evaluation. The learned-coordinate integration
was reviewed separately. No model weights, private host paths, credentials or
personal runtime notes are included in these artifacts.
