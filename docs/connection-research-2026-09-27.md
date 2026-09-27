# Connecting sections after the gap-skipping experiments

Research checked **September 27, 2026**, against official repositories, author
papers and tool documentation. This is a ranked experimental plan for this
recording, not a benchmark claim. No models were installed and no reconstruction
or GPU experiment was started during this research pass.

## Follow-up: broader visual scouting

The [Luna-assisted wider-window search](../evidence/luna-wide-landmarks/results.md)
screened 408 frames around the loss and found no clearly better new landmark.
[LLM-assisted frame and region selection](llm-assisted-landmark-search.md) records
more focused ways to use visual models, including numbered alternatives and
indirect overlap searches. These remain separate from geometric acceptance.

## What the failures actually establish

The [direct section-joining experiment](../evidence/skipped-gap-bridge/results.md)
used 38 selected images and 280 cross-section pairs. Existing static SIFT maps,
augmented SIFT tracks and fresh ALIKED tracks yielded 2, 3 and 0 cross-section
3D landmark groups. Twelve selected views had no retained features. This rejects
those configurations; it does not establish that physical overlap is absent.

Four restrictions may be making the task harder than necessary:

1. **Architecture-only masks.** Floor/ground/wall minus every detected person
   excludes stationary people and usually omits bags and clothing. It also retains
   moving shadows. Semantic category and actual motion are different.
2. **Sparse measurements.** Both matchers depended on detected keypoints. Neither
   trial tested a dense matcher such as RoMa v2.
3. **Fixed existing geometry.** New landmarks had to agree with the old camera
   estimates, and a cross-link needed a triangulated point in both pieces. Camera
   errors can prevent a correct 2D match from becoming a usable 3D correspondence.
4. **A narrow graph.** The last trial searched two components only. A third section
   elsewhere in the recording might overlap both and provide an indirect route.

The 12-fit/6-held threshold is our campaign acceptance rule, not a mathematical
minimum for fitting a similarity. A smaller set may propose a hypothesis; it
cannot be described as independently verified merely because an optimizer fits
it. Dense neighboring pixels must not be counted as independent landmarks.

## Ranked options for this case

The ranking below is our assessment from the retained evidence. Several options
are complementary stages, not competing complete pipelines.

| Priority | Intervention and released tools | Why it fits this failure | Main limitation / test |
|---|---|---|---|
| 1 | Manual overlap audit, then motion-aware regions: [CVAT points/polygons](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/), [SAM 3.1](https://github.com/facebookresearch/sam3/blob/main/RELEASE_SAM3p1.md) | Identify the same distinctive marks or objects across sections; preserve verified stationary bodies, bags, clothing and labels instead of masking by category | SAM tracks segmentation/identity, not world motion. Check motion relative to scene geometry; uncertain/deforming regions remain uncertain. |
| 2 | Dense matching: [RoMa v2](https://github.com/Parskatt/RoMaV2), [paper](https://arxiv.org/abs/2511.15706) | Proposes correspondences across image regions rather than only existing SIFT/ALIKED keypoints; exposes overlap and precision estimates | Repeated tiles/bags and correlated dense predictions can produce convincing false matches. Spread samples spatially and validate whole patches/tracks on unseen views. |
| 3 | Point re-detection: [TAPNext++](https://github.com/google-deepmind/tapnet), [CoTracker3](https://github.com/facebookresearch/co-tracker) | Track reviewed floor/object points through short occlusions and check where they reappear; fewer independent pair decisions | Visibility and coordinates are predictions. Invisible portions do not become measurements; require observed reappearance and forward/backward consistency. |
| 4 | Whole-recording retrieval and an overlap graph: [DINOv2 SALAD](https://github.com/serizba/salad), [hloc](https://github.com/cvg/Hierarchical-Localization) | Find another view of the same patch minutes away; connect A to C and C to B even when A–B matching fails | Retrieval only proposes candidates. Similar bodies/bags are a major false-loop risk; each edge needs geometric verification. |
| 5 | Joint reconstruction of selected bridge views: [MASt3R-SfM](https://github.com/naver/mast3r), [COLMAP shared intrinsics / bundle adjustment](https://colmap.github.io/faq.html) | Allows cameras and landmarks to improve together, rather than requiring every match to fit the old maps | Needs a real correspondence graph. Re-estimating bad geometry cannot manufacture overlap. Anchor one gauge and validate separate landmarks/views. |
| 6 | Structured floor evidence: [LIMAP](https://github.com/cvg/limap) | Uses lines, vanishing directions and planes alongside points; tile seams and intersections may survive blur better than tiny marks | Repeated grids are ambiguous; one plane does not determine all alignment freedoms. Combine distinctive points and lines, not floor normals alone. |
| 7 | Conditioned geometry proposals: [Pi3X](https://github.com/yyfz/Pi3), [MapAnything](https://github.com/facebookresearch/map-anything) | Can accept calibration and some camera/depth information, giving an alternative initialization for a small mixed before/after set | Prior-conditioned output is not independent confirmation of the supplied prior. Do not feed unrelated component coordinates as one world frame or treat predicted metric scale as measured. |
| 8 | Camera recovery designed for moving scenes: [MegaSaM](https://github.com/mega-sam/mega-sam), [MonST3R](https://github.com/Junyi42/monst3r), [MASt3R-SLAM](https://github.com/rmurai0610/MASt3R-SLAM) | Changes the trajectory estimator; the first two explicitly address dynamic video, the third supplies dense matching/loop-closure machinery | More integration and another uncertain trajectory. Benchmark a local interval against independent static observations before a full-video run. |
| 9 | Direct splat registration: [splatreg](https://github.com/Archerkattri/splatreg) | Attempts rotation/translation/scale alignment from the existing splat representations; can keep aligned outputs separate | Our splats contain ghosts and distortions; optimizing their agreement can align artifacts. Validate against original images and keep multiple hypotheses when ambiguous. |

Manual audit is a small diagnostic step, not a request to hand-place the whole
scene. It can establish whether there are shared stationary details worth giving
the automatic methods. Whole-recording retrieval can proceed independently if
local overlap remains unclear.

## What is newer or materially different

**RoMa v2** has released dense-matching code and a November 2025 paper. The API
returns overlap and precision information, supports bidirectional matching and
balanced sampling. It was already recommended in our earlier research but was
not exercised by the recent sparse-feature experiments. This is a distinct next
hypothesis, not another setting of ALIKED. [Official implementation](https://github.com/Parskatt/RoMaV2).

**TAPNext++** is now listed with released PyTorch checkpoints and demos, including
a 512×512 variant. Its authors specifically describe occlusion tracking and
re-detection. This directly addresses the earlier question about a point leaving
view and returning. CoTracker3 also exposes point tracks and visibility, with
both offline and online interfaces. Neither is itself a complete camera solver.
[TAPNext++ availability](https://github.com/google-deepmind/tapnet),
[CoTracker3 API](https://github.com/facebookresearch/co-tracker).

**LIMAP's current code/docs** include point-line localization and reconstruction
with structural primitives, rather than only line visualization. This gives a
concrete implementation path for the floor-reference idea: jointly optimize tile
lines/intersections and camera geometry. We have not tested its current COLMAP
compatibility or build on our environment. [Official toolbox](https://github.com/cvg/limap).

**Pi3X**, released in December 2025, supports optional poses, intrinsics and depth.
MapAnything likewise accepts mixed geometry inputs. A useful trial would supply
one shared-lens hypothesis and only trusted anchor poses in a consistent gauge,
then withhold other observations for validation. More prior inputs are not always
better: incorrect anchors can steer the result incorrectly.
[Pi3X](https://github.com/yyfz/Pi3),
[MapAnything](https://github.com/facebookresearch/map-anything).

**MASt3R-SfM and MASt3R-SLAM are different integration choices.** For this task,
offline selected-view reconstruction may be more appropriate than demanding an
uninterrupted sequential tracker. The MASt3R authors define their SfM pipeline as
retrieval-based pairing plus sparse global alignment; they explicitly distinguish
it from their less-tested COLMAP/GLOMAP demonstration wrappers.
[Authors' implementation notes](https://github.com/naver/mast3r#mast3r-sfm).
Our earlier SLAM setup record is incomplete and must not be counted as a failed
MASt3R reconstruction result. That historical environment was not rechecked here.

**Graph-GSReg** remains a watchlist item: the official repository still says the
implementation will be released soon. It is not an immediately runnable option.
[Release status checked this pass](https://github.com/Lee-JaeWon/Graph-GSReg).

## Recommended next bounded experiment

1. Reuse the current before/after frame selection as a baseline. Add a small,
   separately recorded set of views selected for visible shared static detail,
   overlap and viewpoint diversity; global sharpness alone can select a sharp
   person while the floor is blurred or absent.
2. Make a review sheet of candidate common details. Label stationary, moving and
   uncertain regions separately; protect stationary evidence. Keep the source
   masks and all exclusions for audit. Camera-relative motion needs robust scene
   consensus and refinement, not a raw pixel-motion threshold.
3. Run RoMa v2 on the candidate cross-section pairs. Use full image context, then
   classify/filter matches by reviewed regions and geometry. Record overlap,
   precision, spatial spread and alternative matches on repeated floor patterns.
4. If static details reappear across the transition, seed TAPNext++ or CoTracker3
   in both directions. Preserve native frame IDs/timestamps and mapping through
   resizing. Skipping an interval in the viewer does not require deleting those
   frames from the estimation process.
5. Use 2D–3D localization where only one section has trustworthy depth, or jointly
   triangulate and refine a small view set when both existing maps are weak.
   Share/refine one lens hypothesis rather than independently fitting every
   frame's focal length. Keep separate component gauges until justified alignment.
6. Freeze validation by physical track and spatial patch, with additional views
   excluded from fitting. A thousand adjacent dense pixels are not a thousand
   independent witnesses. Check both projection directions, depth signs, scale,
   viewpoint coverage and sensitivity to different anchor subsets.

The immediate useful output is a source-linked correspondence/track review and
one inspectable candidate section transform, or a precise statement that no
shared static region was established. Full-video retraining is unnecessary to
answer that question. If the local pair has no support, use global retrieval for
an indirect path before another local model sweep.

## Lower-priority alternatives and limits

A floor normal can constrain tilt; an identified floor plane can constrain
relative height. It cannot alone establish translation along the floor, yaw or
metric scale. Repeated tile dimensions may become a scale hypothesis, but their
real dimensions are currently unknown. Joint line/point evidence is preferable
to snapping every section to one visually level plane.

Deblurring can be tested as a matching proposal aid, but final landmark checks
should use original pixels. Generated missing imagery or geometry cannot verify
a scene connection. More frames, a larger neural context, or a smoother camera
curve do not independently establish accuracy.

For the public viewer, temporal navigation between **unaligned** sections is also
possible without pretending to know their physical relative placement. An
approximate manual layout would need an explicit uncertainty label and a separate
layer. These are presentation options, not substitutes for measured alignment.

## Research delivery checkpoint

Primary-source availability/capabilities were checked, recommendations were
compared with the actual retained failures, and references and experiment limits
were preserved here. This document does not claim an installation, compatibility
check, successful new camera estimate or accepted section connection. Research
only; no GPU jobs launched.
