# Use visual models to find better evidence before measuring points

Research checked September 27, 2026. This plan is specific to this recording and
its repetitive bags, moving occluders, blurred handheld views and fragmented
camera estimates. It does not rank models by an unmeasured benchmark on our video.

## Change the question

The unsuccessful A01 exercise asked for an exact corner before establishing that
the physical corner was visible. A near-perfect adjacent-frame tracking cycle
cannot repair that missing observation. The more useful first question is:
**Which views show the same distinctive scene content clearly enough to measure?**

Time separation is not itself the problem. Two views ten seconds apart may share
more exposed detail than two views adjacent to an occlusion. Increasing the
search interval means considering more source views, not deleting intervening
evidence or pretending that the endpoints are connected.

The new experiment gives **GPT-6 Luna two ten-second windows**: 402.290311–412.290311
and 414.512889–424.512889 seconds. It also retains the intervening 38 frames. The
408-frame inventory includes 178 before, 38 gap and 192 after images, regardless
of camera-registration status. Luna receives timestamped contact sheets and can
open originals; it is not given the old point coordinates or old preferred pairs.
Its job is to propose frame pairs and regions, not certify pixel correspondence.

[Completed Luna scout and its limitations](../evidence/luna-wide-landmarks/results.md):
21 contact sheets and 19 original images inspected; no clearly better match
established. A weak floor-color proposal remains unresolved.

## Ranked approaches for this case

| Order | Approach | What the visual model contributes | What must verify it |
|---|---|---|---|
| 1 | Wider temporal search, then inspect original pixels | Select views with visible shared details, useful viewpoint change and limited occlusion; explicitly explain why each is better | Inspect full originals and neighboring frames; compare region visibility rather than global sharpness |
| 2 | Match several distinctive details in their spatial arrangement | Describe a patch, cord, seam, floor mark or rigid junction together with its neighbors; propose a region, not an invented exact corner | Check the same details and arrangement in both views; obtain spatially distributed measurements, not many samples on one flexible patch |
| 3 | Number candidate regions or detected points and offer alternatives | Choose among visible numbered candidates, including “none/unclear,” rather than regressing coordinates from prose | Use the underlying detector coordinates; inspect unmarked pixels and reject lookalikes; numbering is an aid, not a match guarantee |
| 4 | Dense matching restricted by reviewed scene context | Choose promising full-image pairs and describe which proposed correspondences belong to plausible common content | Run RoMa v2 on full context, inspect regional support, then geometric checks and held-out views; avoid counting neighboring dense pixels as independent evidence |
| 5 | Connect through another view | Find A–C and C–B overlaps even when no single reliable A–B match exists; include useful gap frames | Verify both edges separately and their joint geometry; an overlap graph alone does not determine a metric transform |
| 6 | Search the whole recording for a revisit | Rerank retrieved views, distinguish repetitive objects using context, identify alternative matches | Use place retrieval such as SALAD/hloc to propose a manageable set, followed by local matching and geometric verification |

These are complementary stages. The first two are being explored in the Luna
experiment; the remaining methods are proposals, not completed runs.

## Creative review procedures worth testing

**Separate discovery from criticism.** A first pass makes an inventory of visible
features without seeing an expected match. A second pass receives the proposed
pair alongside similar-looking alternatives and must explain what distinguishes
it. Reversing the query direction can expose inconsistency. Agreement between
language models is still not independent physical proof.

**Use short sequences around each candidate.** Show an original frame with its
preceding and following views. Ask whether a mark stays attached to a surface,
disappears behind an occluder, or changes with a reflection. This can reject a
shadow or shiny highlight before spending time on a tracker. Actual stationarity
still needs motion relative to reliable scene geometry.

**Ask for the next useful observation.** Instead of repeatedly changing a point,
ask what view would resolve the ambiguity: a lower viewing angle, an uncovered
floor seam, or another side of a patch. Search nearby original frames for that
condition. Stop refining coordinates when the material boundary is not exposed.

**Prefer a visible junction to an inferred object corner.** If the original A01
definition is unobservable, a different visible texture feature may be usable.
Give it a new landmark ID and description; do not silently move A01 or call an
occluding edge the hidden corner. Keep both observations and their provenance.

**Use marks with controlled choices.** Start with a few numbered regions, then
number detected corners or texture samples within the chosen region. Keep the
original unmarked image beside the marked version and include distractors.
This draws on [Set-of-Mark prompting](https://github.com/microsoft/SoM), which
uses spatial labels to help a vision-language model refer to image regions.
Applying it to our correspondence review is our proposed adaptation, not a
validated result from that project.

## Why separate visual recognition from measurement

[CrossPoint-Bench / CroPond](https://arxiv.org/abs/2512.04686) explicitly evaluates
the transition from cross-view reasoning to point correspondence and reports
substantial limitations in the models it tested. [SOCO](https://arxiv.org/abs/2605.31597)
finds that tested large vision-language models are better at language-described
part localization than visual-reference correspondence. These studies do **not**
measure our current Luna/Astra workflow or establish its error rate. They motivate
using the models for candidate selection with explicit uncertainty, followed by
tools that estimate and check coordinates.

[RoMa v2](https://github.com/Parskatt/RoMaV2) supplies dense image correspondences;
its predictions still need rejection of repeated patterns, occluders and unstable
surfaces. [hloc](https://github.com/cvg/Hierarchical-Localization) provides the
retrieval/local-feature structure for scalable localization.
[DINOv2 SALAD](https://github.com/serizba/salad) provides place-retrieval descriptors.
For this recording, their role would be to propose and verify additional overlap
edges, not to make a disconnected trajectory correct by smoothing it.

## Preserve the distinction between evidence and hypotheses

Keep exact source times, hashes, region bounds and the model's original rationale.
Record which images were inspected at full resolution versus thumbnails. Preserve
rejected alternatives. Do not treat multiple points on one bag, repeated grid
intersections, predicted invisible trajectories or generated detail as independent
observations. No deblurring, image generation, camera solve or splat training is
part of this widened visual-search experiment.

The next numerical experiment should use the strongest surviving frame pairs,
reviewed regions and separate held-out observations. A weak shortlist is an
instruction to search for more evidence, not permission to force an alignment.

## Completed numbered-choice trial

The proposed detector-and-numbered-choice approach was run on three RoMa v2 pairs
with six source queries. Luna abstained on all six. Five model proposals passed
coarse snap/cycle screens, showing why numerical consistency needs visual and
physical checks. No homography or section connection was accepted.
[Results, raw review, thresholds and reproduction](../evidence/numbered-landmarks/results.md).
