# Stitching, motion removal, cleanup and completion

**Research checked September 26, 2026.** Sources below are original repositories,
author project pages and papers. This is a ranked shortlist for this recording,
not an exhaustive survey or a benchmark on our footage. This research pass did
not run new tools. A subsequent [tracked-mask and cleanup experiment](tracked-cleanup-experiment.md)
records implementation, actual results and remaining prerequisites separately.
The full-recording batch and published scenes were not changed by this research.

Research acceptance: cover the four requested problems, distinguish available
code from papers, rank options against our observed failures, and preserve
sources plus a concrete next experiment. Model installation, GPU experiments
and generation of synthetic content are outside this research pass.

## What changes the recommendation for our case

The [three connection attempts](connecting-scenes.md) found plausible appearance
matches but no defensible alignment between the 48s and 71s scenes. Repeated
bags and labels are ambiguous; a coat occludes almost the whole view at the
transition. Temporal continuity does not establish relative 3D pose or scale.

[Geometric pruning](post-training-cleanup.md),
[approximate contribution scoring](contribution-cleanup.md) and
[sparse-point cleanup](static-cleanup-comparison.md) did not remove the principal
ghosts. Independent person masks also fluctuate and erase some static details.
New temporal, depth and camera evidence deserve priority over more threshold
tuning. The order below is **our assessment of fit**, not a benchmark ranking.

| Priority | Intervention | Why it fits | Main cost or limitation |
|---|---|---|---|
| 1 | Tracked instances plus actual-motion masks | Reduces inconsistent moving-person masks while protecting static evidence | Segmentation is not motion detection; review and retraining required |
| 2 | Component-overlap graph, shared-camera alignment, then dense matching | Reuses recovered sections and may find indirect connections through other intervals | Requires real overlap; repeated objects remain ambiguous |
| 3 | Alternative long-video trajectory recovery | Changes the camera-recovery approach instead of repeating failed sparse matching | Learned geometry and false loop closures require independent checks |
| 4 | Transient-aware training | Addresses moving content while the model is formed | Another trainer and static-only export integration |
| 5 | Blur compensation and reliable depth guidance | Targets phone-motion smear and weak floors/walls | Extra variables and uncertain predicted depth |
| 6 | Source-verified local splat suppression and seam refinement | Useful for remaining isolated artifacts and duplicate density | Can erase valid surfaces or open holes |
| 7 | Separate, explicitly synthetic completion | Can make unseen areas navigable | Plausibility cannot establish what was actually present |

## Stitching existing scenes

**Shared cameras first.** Find source frames registered in multiple components,
estimate rotation, translation **and scale**, validate independent views, then
jointly refine accepted connections. COLMAP's model merger requires common
registered images; it cannot directly merge our rejected 48s/71s pair.
[COLMAP documentation](https://colmap.github.io/faq.html#merge-disconnected-models).

**RoMa v2 — preferred new image-matching experiment.** Released dense matching
with overlap/precision estimates and DINOv3 features. Unlike our sparse
SIFT/ALIKED attempts, it can propose matches away from existing keypoints. Our
adaptation would mask moving regions, retrieve plausible overlapping frames
throughout the video, and use verified depth/tracks to estimate relative poses.
More matches do not prove that similar bags are the same bag.
[Official code](https://github.com/Parskatt/RoMaV2) ·
[November 2025 paper](https://arxiv.org/abs/2511.15706).

**splatreg — practical direct-splat candidate.** Released library for SE(3)/Sim(3)
registration, alignment without fusion, overlap deduplication and rotation of
spherical-harmonic appearance. The core is described as pure PyTorch without a
custom CUDA extension; optional components differ. Its author-reported results
are not validation on our data. First recover a known alignment between
overlapping components, then attempt a hard pair. Keep both original assets.
[Repository and results](https://github.com/Archerkattri/splatreg).

**GaussReg — established research alternative.** ECCV 2024 coarse geometric
registration followed by image-guided refinement. The author page links code
and datasets; custom-data integration and model/data requirements were not
audited in this pass. [Project](https://jiahao620.github.io/gaussreg/).

**Graph-GSReg — relevant 2026 watchlist item.** Its June 2026 paper uses semantic
scene graphs for registration and test-time optimization to improve merged
renderings. However, the official repository still says code will be released
soon. Repeated object categories may also make graph matching ambiguous here.
[Paper](https://arxiv.org/abs/2606.29782) ·
[Release status](https://github.com/Lee-JaeWon/Graph-GSReg).

**ICP and pose graphs are refinement tools.** Independent monocular scales need
resolution before ordinary rigid ICP. Prefer verified architecture and surface
points over all Gaussian centers. Optimize accepted connections jointly and
check loops; do not force a transform when several placements fit similarly.
[Open3D multiway registration](https://www.open3d.org/docs/latest/tutorial/pipelines/multiway_registration.html).

Once alignment is accepted, transform covariance/scale and view-dependent
appearance along with positions, then refine duplicate seam density against real
source views. [PlayCanvas SplatTransform](https://github.com/playcanvas/splat-transform)
provides merge, transform, filter and compressed-output utilities. Applying a
chosen transform is different from establishing its correctness.

## Longer trajectory and denser reconstruction

| Tool | Current verified availability/capability | Fit and limitation |
|---|---|---|
| [VGGT-SLAM 2.0](https://github.com/MIT-SPARK/VGGT-SLAM) | Released January 2026, real-time code added June; RGB submaps and loop closure | Leading alternative trajectory experiment. README warns portrait inputs can be cropped; preserve/remap our image coordinates. Optional SAM 3 integration is object detection, not automatic moving-object removal. |
| [DA3-Streaming](https://github.com/ByteDance-Seed/Depth-Anything-3/tree/main/da3_streaming) | Released chunked long-video inference, camera poses and combined point-cloud output | Strong second choice for the 12-minute sequence. Output is a geometry candidate, not proof of a correct connected splat. |
| [MASt3R-SLAM](https://github.com/rmurai0610/MASt3R-SLAM) | CVPR 2025; code accepts MP4/images with optional calibration | Alternative to feature-based tracking; still needs static support through occlusion and compatible dependencies. |
| [MapAnything](https://github.com/facebookresearch/map-anything) | Released model accepts images and optional poses, calibration and depth; COLMAP export documented | Useful for difficult bridge intervals while retaining known camera constraints. Predicted metric scale is not a surveyed measurement. |
| [WorldMirror 2.0](https://github.com/Tencent-Hunyuan/HY-World-2.0) | Reconstruction code and weights released April 2026; predicts cameras, depth, normals and Gaussian attributes | Worth a local comparison. Use reconstruction, separate from its world-generation path. July's HY-World 2.1 product announcement does not establish a separately released 2.1 reconstruction checkpoint. |
| [LongSplat](https://github.com/NVlabs/LongSplat) | ICCV 2025; joint incremental pose/scene optimization and ordinary 3DGS conversion; reproduction fixes December 2025 | Relevant long-video alternative with more trainer/kernel integration. Not automatically a transient-removal solution. |

Test a difficult 30–60-second interval with known cameras on both sides before
replacing the full pipeline. Preserve every original frame and timestamp;
keyframe selection for a solver does not require discarding data from tracking,
training or coverage accounting. These systems are unbenchmarked on Thor here.

## Moving content and ghosting

**SAM 3.1 plus motion checks — best incremental change.** Meta released Object
Multiplex on March 27, 2026 for shared-memory multi-object video tracking. SAM 3
supports text/visual prompts and interactive corrections. Checkpoint access is
gated and our account access is unverified. Replace independent masks with
tracked instances, but measure motion relative to the camera: a static body is
still semantically a person. Label static evidence, moving occluders and uncertain
pixels separately. Protect examples of bodies, bags, labels and floor detail.
[Code](https://github.com/facebookresearch/sam3) ·
[3.1 release notes](https://github.com/facebookresearch/sam3/blob/main/RELEASE_SAM3p1.md).

**T-3DGS — video-specific transient removal.** Learns transient/static differences
then refines masks using segmentation and bidirectional tracking. Code and
separate mask-refinement tooling exist. Temporal consistency makes it a strong
retraining candidate for this recording.
[Method](https://transient-3dgs.github.io/) ·
[Code](https://github.com/Vadim200116/T-3DGS).

**DeSplat — separate shared static and view-specific content.** Released
Nerfstudio implementation with custom COLMAP support. Relevant when moving
content is entangled throughout the reconstruction. Requires retraining and
static-export verification; its documented older PyTorch/CUDA setup and known
checkpoint issue need an isolated compatibility test.
[Official code](https://github.com/AaltoML/desplat).

**RobustSplat — prevent contamination during Gaussian growth.** ICCV 2025 method
with released code, delayed growth and progressively improved transient-mask
supervision. This addresses how ghosts form, unlike deleting long Gaussians
afterward. [Code](https://github.com/fcyycf/RobustSplat) ·
[Paper](https://openaccess.thecvf.com/content/ICCV2025/papers/Fu_RobustSplat_Decoupling_Densification_and_Dynamics_for_Transient-Free_3DGS_ICCV_2025_paper.pdf).

A dynamic/4D representation is an alternative if preserving motion becomes a
separate output goal. It needs time-dependent viewing/export, rather than a
small edit to the static PLY. Retain the source video and all exclusion masks.

## Cleanup, blur and weak surfaces

**Depth and visibility checks:** suppress density only when multiple real views
support the surface behind it or establish observed empty space. Compare soft
opacity reduction plus local refinement with hard deletion. This is a proposed
adaptation; our existing approximate scorer does not implement reliable depth.

[Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3) supplies
pose-conditioned depth and confidence. Its current README recommends refreshed
`-1.1` checkpoints where available after a training-bug fix. Scale-align and
confidence-filter predictions; prefer consistent observed multi-view depth.
Neither predicted depth nor a confidence score is independent measured truth.

[FlashSplat](https://github.com/florinshen/FlashSplat) provides 2D-mask-to-Gaussian
labeling and object removal. Useful for local reversible edits after identifying
a ghost in several views. Segmentation does not determine geometric validity;
our failed approximate attribution experiment did not test FlashSplat itself.

[Gaussian Splatting on the Move](https://github.com/SpectacularAI/3dgs-deblur)
models camera motion during exposure. The released implementation supports plain
video in blur or rolling-shutter mode without IMU or known exposure/readout times.
Relevant to blurred stationary edges, but adds optimization uncertainty and does
not independently remove moving people. Generative sharpening would not prove
recovery of original detail.

Recent papers, below the better-matched released options:

- [TIDI-GS, January 2026](https://arxiv.org/abs/2601.09291): multi-view consistency,
  neighborhood/importance pruning and monocular depth. Paper verified; runnable
  official code not confirmed in this pass.
- [CleanSplat, April 2026](https://doi.org/10.1016/j.vrih.2026.02.001): curriculum
  transient handling and structural cleanup. Publisher abstract verified; full
  page access was inconsistent and official code not confirmed.
- [Signal Structure-Aware Gaussian Splatting, July 2026](https://arxiv.org/abs/2607.01698):
  coordinates image resolution and Gaussian growth, with spatial constraints.
  Paper links code, but installation/portability was not audited. Its large-scene
  results do not establish effectiveness on our crowded recording.

## Missing parts: recover first, generate separately

1. **Visible elsewhere in the recording:** recover using those real views,
   registration and retraining. This is the preferred way to fill our gaps.
2. **Small gaps between observed surfaces:** depth, normal or plane constraints
   can interpolate geometry. Label it inferred; a continued floor plane does
   not establish objects or marks on that floor.
3. **Never visible:** generation can produce plausible content, but the recording
   cannot validate what it invents.

| Tool | Availability checked | Fit |
|---|---|---|
| [Inpaint360GS, WACV 2026](https://github.com/dfki-av/Inpaint360GS) | Code/data/results released January 19, 2026; object removal, color/depth inpainting, 3D completion | Most concrete released Gaussian-inpainting candidate in this shortlist. Start with a small background hole; retain synthetic labels. |
| [GaussFiller](https://yhpffy.github.io/GaussFiller/) | Project/paper verified; sparse RGB-D and VLM-guided completion; runnable official code not confirmed | Less direct fit because our video has no measured depth. Predicted depth adds another inference layer. |
| [CoIn, June 2026](https://arxiv.org/abs/2606.27584) | Paper verified; diffusion inpainting with Gaussian-guided multi-view consistency; code not confirmed | Promising research. Agreement between generated views does not authenticate generated content. |
| [HY-World 2.0 generation](https://github.com/Tencent-Hunyuan/HY-World-2.0) | Generation inference and WorldStereo 2.0 weights released May 2026 | Produces explorable environments, but low priority for documenting the actual location. Distinct from its reconstruction path. |
| [SAM 3D Objects](https://github.com/facebookresearch/sam-3d-objects) | Single-image object reconstruction code and model access instructions released | Hidden object surfaces are inferred. Not a whole-scene registration method or a source of factual victim/event details. |

Keep observed reconstruction, inferred geometric completion and synthetic
content in separate assets with provenance. Offer synthetic context only as an
explicitly labeled optional layer, off by default. Do not generate missing victim
anatomy, injuries, identities, labels or event details and present them as recovered
evidence. A visually seamless result can still contain invented information.

## Smallest useful next experiments

1. Compare existing masks with SAM 3.1 tracked-instance/motion masks on one
   problematic 15–30-second interval. Freeze cameras, training budget, held-out
   views and protected static regions. Measure both ghosts and lost real detail.
2. Establish reference alignment from components sharing cameras. Test RoMa v2
   or splatreg on those controls, then a difficult bridge. Check withheld source
   views and ambiguous solutions; search for indirect connections through third
   components rather than retrying only the previous pair.
3. If real bridges remain absent, test VGGT-SLAM 2.0 on a bounded transition and
   compare known cameras on both sides. DA3-Streaming is a subsequent alternative,
   not a simultaneous full-recording replacement.
4. Compare the best masks with one transient-aware trainer. Move blur compensation
   earlier if artifacts follow camera speed along stationary edges.
5. Test completion by artificially hiding an observed background patch, then
   compare against the withheld original before considering unverifiable holes.

The initial research pass started no installations or GPU jobs. Subsequent
[tracked-mask and cleanup trials](tracked-cleanup-experiment.md) record what
actually ran, including the SAM 3.1 access prerequisite and SAM 2.1 fallback.
Weight access, licenses and hardware compatibility must still be checked for
each remaining tool. Do not replace working vendor PyTorch to try a package.
