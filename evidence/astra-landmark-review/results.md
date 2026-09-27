# GPT-6 Astra visual review: a shared bag region across the gap

**A GPT-6 Astra subagent found convincing regional overlap and three tentative
point correspondences. No camera alignment has been established.**

[Open the interactive marked comparison](https://parhamdb.github.io/sepehrbaba/landmark-review.html).
Choose a point, switch the after frame, hide markers, or inspect the full original
images. Yellow circles show Astra's stated localization uncertainty; overlays do
not alter the underlying source pixels.

## Finding

Astra independently inspected **all 38 original 1080×1920 frames** from the prior
before/after selection, plus five native crops. It did not consult the previous
matcher overlays. The requested model was explicitly `gpt-6-astra`.

The strongest shared configuration is a **reflective rectangular patch beside a
green strip and hanging white cord on a black bag**. The best pair is
`frame_006454.jpg` (**410.237478 s**) → `frame_006548.jpg` (**415.494189 s**).
`frame_006549.jpg` provides an adjacent after-frame observation.

| Candidate | Material feature | Before 006454 (x,y) | After 006548 (x,y) | Stated uncertainty before / after |
|---|---|---|---|---|
| A01 | Patch lower-left corner | (211, 621) | (944, 1008) | ±15 / ±12 px |
| A02 | Patch lower-right corner | (276, 626) | (1008, 990) | ±16 / ±12 px |
| A03 | Patch upper-left corner | (205, 562) | (914, 894) | ±14 / ±12 px |

Coordinates are native pixels with origin at the top left. Astra assigns
**medium confidence to the exact points**, and high confidence to the regional
overlap. These are qualitative visual judgments, not calibrated probabilities.
The physical patch boundaries are intended; moving specular highlights are not.

The parent agent inspected the before/after crops and the rendered point overlay.
It also checked the previous architectural masks at every annotated point center:
**all nine locations were excluded**. The prior masked feature runs therefore
could not use these locations. This provides a concrete reason to revise the
region selection before assuming the sections lack shared content.
[Point-center mask audit](mask-audit.json).

## Limits and rejected points

All three candidates belong to one small patch on flexible bag material. They
are spatially correlated and do not provide enough independent constraints to
certify a section connection. The before view is blurred and partially occluded;
movement or deformation during the gap is unverified. The adjacent after frame
checks repeatability but is not an independent baseline.

Astra rejected the apparent cord endpoint: it may be an occlusion/bend rather
than the same material point. It found no confidently shared floor landmark and
did not assume repeating tile intersections, white coverings or generic bag
shapes were identical. No facial identities or biometric landmarks were used.

`usable_for_geometric_test: true` means a candidate worth refining or rejecting,
not a measured 3D landmark or accepted alignment. No model inference, geometric
solve, camera modification or reconstruction training was performed in this
visual-review task.

## Reproducibility and evidence

- [Unedited Astra review](astra-review.md).
- [Astra annotations, rejected hypotheses and crop bounds](astra-candidates.json).
- [Frame selection and source SHA256s](../../public/landmark-review/selection.json).
- [Provenance and review checks](provenance.json).
- Analytical source crops: [before patch](analytical-crop-0.png),
  [blurred before view 1](analytical-crop-1.png),
  [blurred before view 2](analytical-crop-2.png),
  [after patch](analytical-crop-3.png),
  [before floor](analytical-crop-4.png).

The subagent was instructed to compare original images independently, propose
only distinguishable shared material points, report native coordinates with
honest uncertainty, and preserve ambiguity rather than inventing matches. Its
raw outputs are retained. The original JPEGs used by the page are byte-identical
to the frozen source hashes. All five crops were checked against the decoded
source pixels and are exact unenhanced crops.

The static review page reads the annotation JSON and draws separate SVG markers.
Local browser checks covered all three candidates, both after observations,
original-image loading, marker toggles, focused/full-image views and mobile
layout; no JavaScript errors were observed. The parent inspected the screenshot.

## Next use

Use this region to seed a targeted matching/refinement test that includes the
bag surface, while seeking additional independent stationary features elsewhere.
Preserve the original uncertainty and test for deformation. A fit supported only
by this single patch must remain a local hypothesis rather than a verified scene
connection.
