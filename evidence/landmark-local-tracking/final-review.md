# Independent final marked-image review

Verdict: A02 and A03 are supported as approximate local tracking controls, including the adjacent seed-to-target correspondence. A01 remains unresolved. This is not a certified corner measurement, camera alignment, or recovery across the gap.

I directly inspected all eight rendered `marked/seed-vs-track-0.png` through `7.png` comparisons, not just coordinates or cycle errors. I also inspected the unmarked original JPEGs 006453, 006454, and 006548 and the native pixel inspection crops for those three frames. The earlier 159-contact-view/15-original search is documented in `seed-review.md`; I did not repeat that entire search in this final review.

## Point verdicts

- **A02 — supported approximately.** The yellow seed sits at the apparent lower-right termination of the gray patch against the darker surrounding material. In target 006454, the marker follows the corresponding lower-right boundary, with no obvious jump to an unrelated feature. Both unmarked originals support that approximate placement. The edge is soft, and the marker covers part of the endpoint; an exact physical corner or subpixel accuracy is not independently established.
- **A03 — supported approximately.** The cyan seed and target marker select the same apparent upper-left patch/rim junction. The surrounding gray texture and pale upper boundary move consistently with this selection. The boundary is blurred and partially merges into the upper rim, so the identification is usable as an approximate control, not precise geometry.
- **A01 — unresolved.** The unmarked seed, target, and later 006548 reference support the reported limitation: green material meets or overlaps the gray patch at its lower-left region. They do not resolve whether the visible junction is the requested material corner or an obscuring boundary. The larger later view helps recognize the patch but does not expose a unique lower-left corner. No replacement coordinate is warranted.

## Across the eight marked views

006451, 006452, 006454, and 006457 show markers remaining in the expected patch-corner neighborhoods relative to the 006453 seed. The blurred 006450, 006455, and 006456 views remain broadly consistent with that motion; their pixels do not independently establish exact endpoint location or visibility. I see no gross marker drift or feature switch in the inspected overlays. This consistency is weaker than proving an invariant physical point in every frame.

006453 is the forward query frame: its coordinates and visibility are forced by the predictor, so its apparent perfect agreement is not accuracy evidence. Likewise, the reverse pass is queried at target 006454, so reverse agreement there is forced. Forward A02 visibility is true in 006456 while reverse visibility is false, reinforcing that model visibility should not be treated as observed truth throughout the interval.

## Numerical and implementation checks

The recorded target predictions in native 1080 × 1920 coordinates are A02 (278.67575, 628.07483) and A03 (208.04317, 562.94240). Recorded return errors at the original seed are 0.5284 and 0.6412 native pixels. These are same-model cycle consistency measurements, not independent corner accuracy or semantic identity tests. The approximately 6-pixel seed uncertainty is a visual estimate, not a calibrated bound; the small cycle errors do not reduce it.

The result records crop [60, 400, 500, 850], internal model resolution [384, 512] in height/width order, and CoTracker revision `82e02e8029753ad4ef13cf06be7f4fc5facdda4d`. The script obtains the resolution from `model.interp_shape`; the crop is therefore internally resized for inference even though the browser overlays use original JPEG pixels. I verified that the inspected public script SHA-256 equals the script hash recorded in the result (`8f68be9c3b278b0393ad8135045d962f1b761ab57015eb0ed88bb8d0458dd52f`). No model was rerun, and this review does not independently revalidate the remote checkpoint or checkout.

The script computes reverse return error at the original seed rather than at the forced reverse query. The viewer overlays native coordinates over the original full-size JPEG through the crop viewBox and explicitly labels the forced forward query row. I found no high- or medium-severity correctness issue requiring a code change within this bounded review.

The experiment spans eight frames, 410.037178–410.387689 seconds (0.350511 seconds), entirely in the before-gap section. The 006548 image is a visual reference only, not part of this tracking run. There are zero accepted cross-gap connections. Publication is supported only with these approximate-control and unresolved-A01 qualifications.
