# Ghosting research and ranked fallback options

For the September 26 update covering stitching, newer models and missing-region
completion, see [current reconstruction options](reconstruction-options-2026-09.md).
The experiments and original ranking below remain preserved.
The [tracked-occluder and geometry-cleanup trial](tracked-cleanup-experiment.md)
records the newer SAM 2.1 fallback experiment, including missed instances and
unchanged evaluation masks; it does not establish that every new option works.

Research snapshot: **2026-09-25**. This document preserves the options discussed
for this recording so unsuccessful experiments can lead to a different,
evidence-based approach rather than repeated threshold tuning.

**Status: ranked research, with a completed bounded rank-1 experiment.** Its two
contribution-aware opacity candidates did not clearly improve ghosting and were
not promoted. See the [implementation and results](contribution-cleanup.md).
The remaining options are fallbacks, not automatic follow-on jobs.

## Goal, evidence, and ranking rules

The goal is a faithful, navigable static environment on
[GitHub Pages](https://parhamdb.github.io/sepehrbaba/), retaining recorded detail.
The source is a continuous 12:17 phone recording, 1080 × 1920 with variable frame
timing. Motion, blur, occlusions, and limited views of some surfaces complicate
static reconstruction. The accepted artifact covers only **199–217 seconds**:
252 registered images, 226 training views, 26 held-out views, and 226,293 Gaussians.
It is not a reconstruction of the full video.

Baseline PLY SHA-256:
`75a8950883fbc87bb88b0002763be6bb94d9edabc9fa2a328542c81acb44a622`.
The repository state before this document was `dd489b4`.

The ranking is our engineering assessment of **expected usefulness for this
scene, preservation of real detail, implementation readiness, reversibility,
cost, and compatibility with a static browser viewer**. It is not a measured
leaderboard. Rank 1 has now had a bounded scene-specific experiment. Its original
position reflects the smallest useful first experiment; a diagnosed cause can move a lower
option to the front. Within grouped methods, order does not assert superiority.

Public code availability means source was located, not that it was installed,
audited completely, or validated. Thor compatibility remains unverified for the
new research implementations. Its ARM64/CUDA environment differs from many
documented research setups; paper runtimes are not our ETAs. A PLY export also
does not guarantee identical appearance in a different renderer.

## What already failed

| Experiment | Observed result | Implication |
| --- | --- | --- |
| Static sparse-point cleanup plus camera refinement | Seed points 109,642 → 91,960; 26-view static PSNR 22.3286 → 22.3302 dB; mixed visual changes | Essentially a metric tie and no clear visual gain; candidate not promoted. |
| Same point cleanup with original camera poses and retained point coordinates | PSNR 22.3286 → 22.2404 dB; worst view -1.2603 dB | Failed visual and numeric gates; candidate not promoted. |
| Strict needle pruning | 190 splats removed; three-training-view PSNR change -0.0065 dB | Dominant ghosts remained. |
| Broader needle pruning | 1,978 removed; change -0.0285 dB | Dominant ghosts remained. |
| Large, faint, isolated-splat pruning | 3,074 removed; change -0.0970 dB | Dominant ghosts remained. |
| Contribution-aware opacity reduction, two variants | 40 or 49 splats halved using source-view evidence | Tiny changes; dominant ghosts remained; neither candidate promoted. |

The pruning metric used PlayCanvas at 532 × 946 on **three training views**, not
the native-resolution 26-view Brush held-out metric. Do not compare those scores
across protocols. These were single runs, not statistical demonstrations.
The full held-out and publication checks for pruning were not completed because
the initial visual gate failed. See the authoritative
[static cleanup report](static-cleanup-comparison.md) and
[post-training cleanup report](post-training-cleanup.md).

An initial comparison renderer exaggerated artifacts until sorting, gamma,
antialiasing, and clipping matched the viewer. This establishes that renderer
configuration matters. It does **not** establish that the remaining ghosts are
primarily renderer errors. Those corrected settings were already used for the
reported candidate comparison.

The first five failures tested sparse-point and geometric/opacity heuristics.
The latest experiment also tested approximate contribution attribution with
static source-color verification. Reliable depth evidence, temporal tracking,
learned artifact detection, and static/dynamic decomposition remain untested.

## Ranked options: best to worst fit for this case

### 1. Source-verified, contribution-aware cleanup of the existing model

**Tested, not accepted:** a custom analytical scorer selected 40 or 49 splats
for reversible half-opacity previews. Both retained the dominant ghosts.
This tested coarse region localization and static RGB evidence, without depth,
learned ghost labels or surface refinement. [Results and revisit criteria](contribution-cleanup.md).

**Recommendation:** identify a particular ghost in multiple rendered views,
trace its actual alpha-weighted Gaussian contributions, and check the implicated
splats against unobstructed source views and reliable depth. Temporarily reduce
opacity, inspect the change, then consider constrained refinement of surrounding
surfaces. Preserve excluded IDs and the baseline.

[FlashSplat](https://github.com/florinshen/FlashSplat) supplies established
mask-to-Gaussian labeling using alpha blending. Its
[removal script](https://github.com/florinshen/FlashSplat/blob/master/objremoval.py)
renders with selected Gaussians excluded; cleaned-PLY export needs integration.
[SAGA](https://github.com/Jumpat/SegAnyGAussians) is an alternative for interactive
segmentation, but requires additional feature training.

**Why first:** uses the accepted model, targets observed errors, and allows small,
reversible comparisons. **Limit:** the combined ghost-identification and
source-verification pipeline is our proposed adaptation, not a demonstrated
FlashSplat feature. Masks can select valid surfaces behind a translucent ghost.
FlashSplat's setup documentation is incomplete. SAGA/FlashSplat label content;
neither independently decides whether that content is geometrically wrong.

**Revisit/advance when:** specific ghost regions can be consistently identified.
If deletion exposes holes or destroys valid detail, investigate ranks 2–4 or 9
rather than increasing deletion thresholds.

### 2. T-3DGS: temporal transient detection and mask refinement

[T-3DGS](https://github.com/Vadim200116/T-3DGS) learns transient/static differences
during reconstruction, then refines detections with segmentation and bidirectional
tracking. Its [AutoVidSeg companion](https://github.com/Vadim200116/AutoVidSeg)
contains the SAM-based refinement pipeline.

**Why high:** continuous video supplies temporal evidence missing from independent
person masks. **Requirements:** another training pipeline, initial transient
predictions, mask refinement, and final training. **Risk:** missed boundaries,
temporary occlusions, and static content can still be misclassified. Temporal
tracking is not proof of correct geometry.

**Revisit when:** ghosts follow moving people or mask boundaries, or rank 1 finds
moving content entangled with many legitimate splats. Official code exists;
custom-data execution and browser export remain unvalidated here.

### 3. DeSplat: explicitly separate static and view-specific content

[DeSplat](https://aaltoml.github.io/desplat/) learns a shared static scene and
view-specific distractor Gaussians through decomposed compositing. Its
[Nerfstudio implementation](https://github.com/AaltoML/desplat) supports custom
COLMAP datasets without relying on an external pretrained semantic detector.
[HybridGS](https://gujiaqivadin.github.io/) is a related separation approach using
2D and 3D Gaussian components; it was noted as an alternative, not independently
audited to the same depth.

**Why high:** addresses moving-content contamination at training time.
**Cost/risk:** retraining and additional model components; the documented setup
uses an older CUDA/PyTorch stack and reports a checkpoint compatibility issue.
Static-only export into our viewer needs verification.

**Revisit when:** moving content is broadly mixed into the environment, especially
when semantic masks remove too much legitimate static content.

### 4. Depth- and normal-regularized training or refinement

The [reference 3DGS implementation](https://github.com/graphdeco-inria/gaussian-splatting#depth-regularization)
already supports depth priors. [DN-Splatter](https://github.com/maturk/dn-splatter)
adds depth/normal guidance and meshing. Prefer reliable multi-view depth where
available; treat monocular estimates as uncertain, scale-aligned guidance.

**Why high:** helps constrain floors, walls, and other weakly textured surfaces
that photometric loss can explain using floating density. **Risk:** inaccurate
depth or normals can flatten details and put surfaces in the wrong place;
moving/occluded pixels require special treatment. The reference implementation
explicitly reports that depth priors can worsen some scenes.

**Revisit when:** haze occupies observed empty space or surfaces lack coherent
depth after transient regions are excluded. Code exists, but the necessary depth
evidence has not been validated for this video.

### 5. Phone-camera motion blur and rolling-shutter compensation

[Gaussian Splatting on the Move](https://github.com/SpectacularAI/3dgs-deblur)
models camera motion during capture. Its updated implementation supports ordinary
video in blur or rolling-shutter mode without IMU data or known exposure/readout
times. [3DGUT/3DGRUT](https://github.com/nv-tlabs/3dgrut) supports distorted and
time-dependent cameras. Other research variants include
[BARD-GS](https://openaccess.thecvf.com/content/CVPR2025/papers/Lu_BARD-GS_Blur-Aware_Reconstruction_of_Dynamic_Scenes_via_Gaussian_Splatting_CVPR_2025_paper.pdf)
and [CoMoGaussian](https://openaccess.thecvf.com/content/ICCV2025/papers/Lee_CoMoGaussian_Continuous_Motion-Aware_Gaussian_Splatting_from_Motion-Blurred_Images_ICCV_2025_paper.pdf);
their integration readiness was not verified.

**Why relevant:** handheld video can violate the assumption that each image has
one sharp, instantaneous camera pose. **Risk/cost:** retraining and more camera
parameters; cannot independently solve transient objects or unseen surfaces.

**Move to the front when:** static edges smear with camera speed, or row-dependent
distortion remains despite good feature alignment. Do not assume ordinary
image deblurring preserves multi-view geometry.

### 6. RobustSplat / SpotLessSplats: robust training and controlled growth

[RobustSplat](https://github.com/fcyycf/RobustSplat) delays splitting/cloning while
learning static structure and progressively improves transient masks.
[SpotLessSplats](https://github.com/lilygoli/SpotLessSplats) uses robust masking
with semantic features; its implementation includes utilization-based pruning.

**Benefit:** prevents model capacity from being spent fitting transient errors.
**Cost/risk:** retraining, feature extraction, and modified GPU kernels; masks and
growth controls can also suppress real detail. Both have official code.

**Revisit when:** early checkpoints are cleaner and later Gaussian growth adds
ghosts, or improved person masks alone are insufficient.

### 7. Camera calibration and joint pose/scene refinement

Inspect feature residual patterns, lens assumptions, and cross-view alignment.
[COLMAP](https://colmap.github.io/faq.html) supports intrinsic refinement and
bundle adjustment. [NVIDIA LongSplat](https://github.com/NVlabs/LongSplat) couples
pose estimation with reconstruction for long videos and provides conversion to
ordinary 3DGS format.

**Benefit:** can address duplicated static geometry at its source. **Risk:**
camera optimization can absorb reconstruction errors; it needs constraints and
independent evidence. The earlier fixed-intrinsics cleanup/refinement experiment
did not improve overall quality, so repeating that same intervention is low value.

**Move up when:** stationary edges are systematically misregistered or the camera
model is demonstrably wrong. LongSplat is a different, untested pipeline, not an
assured upgrade or an automatic moving-object remover.

### 8. Better frame weighting, local reconstruction, and source coverage

Retain all decoded source frames and timestamps, but distinguish their roles:
sharp observations for geometry, adjacent frames for tracking, and all usable
views for visibility/coverage evidence. One continuous video need not fit one
equally weighted static optimization. [COLMAP capture guidance](https://colmap.github.io/tutorial.html)
emphasizes overlap, texture, and camera translation.

**Benefit:** reduces conflicting supervision without throwing away the original
data. If the original camera file becomes available, it may retain detail lost
in the downloaded encoding. **Limit:** this is a data strategy, not a finished
algorithm; segment registration and boundary consistency still require validation.

**Revisit when:** errors correlate with blur/occlusion, the full sequence drifts,
or extra segments provide new views of a poorly observed surface. A longer video
or more adjacent frames does not guarantee more depth information. Previously
unseen surfaces require additional observations or explicitly synthetic completion.

### 9. FreeSplat++-style depth-guided soft suppression

[FreeSplat++](https://arxiv.org/html/2503.22986v1) adjusts opacity using multi-view
depth consistency and accumulated fusion weights, rather than only deleting
Gaussians. This offers a useful model for suppressing floaters while avoiding
holes. Its [official repository](https://github.com/wangys16/FreeSplatPP) still
announced forthcoming code at research time. A related implementation in
[EmbodiedSplat](https://github.com/0nandon/EmbodiedSplat) reports floater removal
following FreeSplat++; that code path has not been audited for reuse here.

**Limit:** our PLY does not contain its fusion weights or trusted predicted depth.
Transplanting the idea requires adaptation. **Revisit when:** rank 1 can identify
bad density but hard removal damages the image, and reliable depth is available.

### 10. Manual SuperSplat cleanup

[SuperSplat's editing tools](https://developer.playcanvas.com/user-manual/supersplat/editor/editing-splats/)
provide depth-aware selection, splat footprint inspection, and reversible edits.

**Benefit:** available now, directly compatible with the delivered asset, and
useful for a small number of isolated artifacts. **Limit:** labor-intensive,
subjective, and difficult when real surfaces and ghosts overlap. It cannot repair
missing structure.

**Revisit when:** only a few localized artifacts remain or a manual selection can
serve as ground truth for a bounded automatic-cleanup experiment.

### 11. Exposure, appearance, and camera-processing compensation

[3DGS exposure compensation](https://github.com/graphdeco-inria/gaussian-splatting#exposure-compensation)
fits per-image adjustments. [WildGaussians](https://github.com/jkulhanek/wild-gaussians)
addresses uncontrolled appearance and occlusions.
[3DGRUT's PPISP integration](https://github.com/nv-tlabs/3dgrut#post-processing-linear-to-srgb-and-ppisp)
models exposure, color, vignetting, and camera response. Splatfacto/gsplat also
provide appearance-related building blocks, rather than a single ghost fix.

**Benefit:** reduces photometric conflicts from changing phone-camera settings.
**Risk:** appearance flexibility may conceal incorrect geometry. Retraining or
refinement is required; export may require baking a chosen appearance.

**Move up when:** residuals track brightness/color changes across otherwise aligned
static frames. It will not independently repair moving-object trails.

### 12. Renderer sorting, projection, antialiasing, and configuration

[StopThePop](https://r4dl.github.io/StopThePop/) addresses depth-order/blending
inconsistency. [Mip-Splatting](https://arxiv.org/abs/2311.16493) addresses sampling
and zoom-related aliasing. Both have implementations; the research renderer is
not automatically a drop-in replacement for our browser viewer.

**Benefit:** can improve appearance without misclassifying valid geometry as a
ghost. **Limit:** incorrect geometry remains incorrect. Some methods require
matching training and rendering behavior. Native rendering benefits must survive
the actual GitHub Pages delivery path.

**Move to the front when:** artifacts pop during rotation, change abruptly with
zoom, or differ between matched native/browser renders. Basic viewer-setting
alignment has already been performed in the previous comparison.

### 13. PlayCanvas voxel / connected-component filters

[SplatTransform](https://developer.playcanvas.com/user-manual/splat-transform/)
provides `--filter-floaters` (remove Gaussians not contributing to solid voxels)
and `--filter-cluster` (retain a selected connected component). These are
[GPU/WebGPU operations](https://developer.playcanvas.com/user-manual/splat-transform/docker/).

**Benefit:** existing tooling that outputs standard assets; considers aggregate
structure rather than only individual axis ratios. **Risk:** voxel scale and
opacity thresholds can remove thin/sparse real geometry; attached ghosts survive.

**Revisit when:** artifacts are clearly disconnected or form low-density clouds.
These filters have not been tried here and are distinct from our nearest-neighbor
heuristic, but no evidence yet makes them a solution for the dominant smearing.

### 14. TIDI-GS: multiple evidence signals during training

[TIDI-GS](https://arxiv.org/abs/2601.09291) combines multi-view visibility,
optimization activity, learned importance, spatial information, and detail
protection, supported by depth regularization.

**Benefit:** more principled than opacity or shape thresholds alone.
**Limit:** requires training statistics unavailable in the exported PLY.
Usable official code was not confirmed in this research.

**Revisit when:** established trainers still produce floaters and a larger
training modification is justified. Treat as a research implementation project.

### 15. CleanSplat: structural graph pruning plus transient masking

[CleanSplat](https://doi.org/10.1016/j.vrih.2026.02.001) combines coarse-to-fine
transient masking with superpoint-graph identification and hierarchical pruning
of spotted artifacts. It is a different method from Clean-GS at rank 17.

**Benefit:** considers groups and structural relationships, rather than isolated
scalar thresholds. **Limit:** custom training/structural processing; official
implementation availability was not confirmed.

**Revisit when:** residual artifacts form identifiable incoherent groups after
moving-object suppression, and simpler approaches fail.

### 16. ReorgGS: rebuild the Gaussian parameterization and refine

[ReorgGS](https://arxiv.org/html/2605.08739v1) reorganizes a converged distribution
into a low-opacity, locally aligned arrangement and continues optimization.

**Benefit:** addresses persistent overlap and poor access to gradients for true
surfaces. **Limit:** not a deletion-only filter; requires more optimization and
reasonable existing scene support. Severe errors can survive resampling and
unobserved geometry cannot be recovered. Official code was not confirmed.

**Revisit when:** the scene is mostly correct but optimization stagnates around
overlapping density, after input inconsistency has been addressed.

### 17. Clean-GS: semantic whitelist, color validation, and outlier removal

[Clean-GS](https://github.com/smlab-niser/clean-gs) has a post-training PLY pipeline
using masked projections, depth-buffered color checks, and k-nearest-neighbor
filtering. Its demonstrations emphasize monument/object isolation.

**Benefit:** existing code and no full reconstruction required. **Limit:** the
inspected implementation uses projected centers and color checks, not complete
alpha-weighted footprint attribution. Its mask/image conventions require care;
dark content and valid background outside an object whitelist can be discarded.

**Revisit when:** isolating a clearly bounded object is desired. For the complete
environment, broad deletion risks losing content we want to preserve.

### 18. Surface representations: 2DGS and mesh-oriented reconstruction

[2D Gaussian Splatting](https://github.com/hbb1/2d-gaussian-splatting) uses oriented
disks with depth-distortion and normal-consistency constraints. DN-Splatter at
rank 4 offers another route toward explicit surfaces/meshes.

**Benefit:** encourages coherent surfaces instead of diffuse volumes.
**Cost/risk:** retraining and a compatible renderer or mesh export; thin,
transparent, and complex geometry may lose detail. Dynamic content still needs
separate treatment.

**Revisit when:** navigable geometric stability matters more than retaining all
view-dependent appearance, and ordinary 3DGS remains volumetrically ambiguous.

### 19. Semantic category-guided suppression

[Semantic-Guided 3DGS for Transient Object Removal](https://arxiv.org/abs/2602.15516)
accumulates vision-language similarity per Gaussian and uses opacity
regularization/pruning for selected distractor categories.

**Benefit:** category evidence can supplement ambiguous motion signals.
**Risk:** a category such as “person” is not equivalent to “unwanted moving
content”; this recording contains static human content too. Thresholds require
calibration. Official runnable code was not verified.

**Revisit when:** the unwanted category can be specified without also selecting
important scene content. It is not a universal amorphous-ghost detector.

### 20. CompSplat: account for video compression during reconstruction

[CompSplat](https://arxiv.org/abs/2602.09816) proposes compression-aware frame
weighting and adaptive pruning for long, compressed video.

**Benefit:** relevant to a downloaded social-media encoding. **Limit:** a preprint
whose official implementation was not confirmed; compression has not been
established as our dominant error source.

**Move up when:** residuals correlate with compression damage after camera,
motion, and depth problems are controlled, or a better source file is unavailable.

### 21. StableGS and other cross-view consistency regularizers

[StableGS: A Floater-Free Framework](https://arxiv.org/abs/2503.18458) proposes
cross-view depth consistency and a dual-opacity model during training.

**Benefit:** directly targets unstable density. **Limit:** requires a different
training objective and is not a PLY-only filter; usable official code was not
confirmed. A separate project also named StableGS discusses geometric probing;
do not assume a repository with that name implements this paper.

**Revisit when:** consistent static inputs still produce floaters and an
experimental trainer is justified beyond the available options above.

### 22. Compression-oriented importance pruning: PUP 3D-GS / POTR

[PUP 3D-GS](https://github.com/j-alex-hanson/gaussian-splatting-pup) has code for
sensitivity-based pruning and refinement.
[POTR](https://arxiv.org/abs/2601.14821) evaluates removal effects through
compositing for post-training compression; official code was not confirmed.

**Benefit:** principled ways to measure contribution and reduce model size.
**Limit:** preserving the current render can preserve its ghosts. High importance
does not mean correct geometry. An artifact-specific, source-aware objective
would be an adaptation, as proposed in rank 1.

**Revisit when:** seeking attribution machinery or compression after quality is
acceptable. Do not equate compression percentage with ghost removal.

### 23. Repeat geometric/opacity/isolation pruning

The [existing script and experiment](post-training-cleanup.md) already tested
long needles and large, faint, isolated splats. Statistical/radius outlier rules,
axis-ratio limits, and opacity thresholds belong to this broad heuristic family.

**Benefit:** cheap, reversible, and useful for obvious extremes. **Evidence
against repeating now:** three tested candidates left dominant ghosts intact and
slightly worsened the small comparison metric. Flat valid surfaces may have
extreme aspect ratios; sparse real details may be isolated.

**Revisit only when:** a newly identified artifact is demonstrably separable by
one of these properties. Do not restart a blind threshold sweep.

### 24. Repeat sparse seed-point filtering

Both [controlled seed-cleanup variants](static-cleanup-comparison.md) failed to
produce a clear improvement. **Benefit:** can repair identifiable bad input
tracks. **Limit:** cleaner sparse inputs did not fix the dominant artifacts here.

**Revisit only when:** new evidence identifies a specific track/triangulation
failure. This negative result does not reject all camera calibration, temporal
masking, or depth-based reconstruction methods.

### 25. Dynamic / 4D Gaussian reconstruction

[4D Gaussian Splatting](https://github.com/fudan-zvg/4d-gaussian-splatting) preserves
motion through time instead of forcing moving content into a static scene.

**Benefit:** appropriate if the intended output changes to an animated scene.
**Why low for this goal:** a different model, substantially different training,
and a time-aware browser viewer. Monocular occlusion and unseen sides remain
ambiguous. It is not a drop-in static-scene cleanup.

**Revisit when:** retaining motion is explicitly prioritized over a static
environment. A frozen time slice would still need validation and export work.

### 26. Generative repair / synthetic views / inpainting

[ArtifactWorld](https://github.com/fyting/ArtifactWorld) predicts artifact
heatmaps and restores rendered videos using a video-generation model. Inference
code and weights are released; training code/data were still listed as planned.
Its released workflow does not directly deliver a cleaned navigable PLY.
[Generative Sparse-View Gaussian Splatting](https://openaccess.thecvf.com/content/CVPR2025/papers/Kong_Generative_Sparse-View_Gaussian_Splatting_CVPR_2025_paper.pdf)
is another direction using generated views; integration readiness was not checked.

**Benefit:** can fill visually objectionable gaps. **Why last:** new content can
look plausible without matching this recording, and video restoration does not
ensure correct 3D geometry. Using only an artifact heatmap as a proposal for rank
1 is conceivable, but unvalidated and still requires source verification.

**Revisit when:** synthetic completion is an explicitly accepted product choice,
with generated regions distinguished from observed reconstruction.

## Cause-based override of the ranking

This table is a triage guide, not a diagnosis already established for this model.

| Observed symptom | First options to investigate |
| --- | --- |
| Localized false blob visible from several viewpoints | 1, 10; 13 if disconnected |
| Trails around moving people or inconsistent masks | 2, 3, 6 |
| Haze in front of an otherwise identifiable surface | 1, 4, 9 |
| Doubled static edges across many source views | 7; 5 if correlated with camera motion |
| Distortion varying across image rows | 5 |
| Errors correlated with brightness/color shifts | 11 |
| Popping on rotation or disagreement between matched renderers | 12 |
| Sharpness/artifacts change mainly with zoom/resolution | 12 |
| Correct areas surrounded by unseen/missing geometry | 8; deletion cannot supply observations |
| Early training looks cleaner than later training | 6, then 14 or 16 |

## Smallest useful next experiment and stop conditions

1. Preserve the baseline and choose a few confirmed ghost regions plus protected
   real surfaces. Use exactly matched camera poses, resolution, masks, and renderer
   settings. Distinguish source-frame motion from model artifacts.
2. For rank 1, produce a per-Gaussian contribution/selection preview before any
   deletion. Check more than one view and account for occlusion. A splat behind a
   masked person must not be rejected merely because it projects inside that mask.
3. Export a reversible candidate or reduce opacity in a separate model. Record
   selected IDs, hashes, parameters, changed regions, and any refinement steps.
4. Inspect fixed nearby navigation views and protected details. If those pass,
   compare the existing 26 held-out views using the same static-region protocol.
   Use source images where the relevant background is visible; dynamic pixels
   must not reward reintroducing people as ghosts. Do not tune on held-out views.
5. Promote only for a clear visual improvement without unacceptable loss of real
   detail. A smaller file or higher aggregate PSNR alone is insufficient. Verify
   the actual browser export before any publication.

Freeze each experiment's inventory and budget before running it: one discovery
pass, focused failed/blocked checks, and one final pass only for an accepted
candidate. Use at most three distinct evidence-based attempts at the same blocker;
preserve failures instead of restarting broad runs. Stop a failed idea and use
the cause table to choose the next option; do not automatically run all 26.

## Revisit record

Add one short row per future experiment. Keep the detailed measurements and
renders in that experiment's own report and link them here.

| Date | Rank / method | Hypothesis and exact artifact | Result / report | Decision and next option |
| --- | --- | --- | --- | --- |
| 2026-09-25 | 23: heuristic PLY pruning | Needles or faint isolated density cause dominant ghosts; baseline hash above | [No clear gain](post-training-cleanup.md) | Retain baseline; investigate source/visibility evidence. |
| 2026-09-25 | 24: sparse cleanup, two variants | Masked/weak sparse tracks cause the artifacts | [No clear gain](static-cleanup-comparison.md) | Retain baseline; do not repeat seed-filter variations without new evidence. |
| 2026-09-25 | 1: contribution-aware opacity, two variants | Multi-view attribution plus static source-color protection isolates ghosts; 40/49 opacity changes | [No clear gain](contribution-cleanup.md) | Retain baseline; revisit with better labels/background or depth evidence; rank 2 remains a separate next option. |

No other ranked option has a scene-specific pass result. The literature is a
menu of hypotheses, not evidence that our scene has been fixed.
