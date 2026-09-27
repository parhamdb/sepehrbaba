# Numbered landmark experiment — September 27, 2026

**Initial blind-review result: zero visually verified point correspondences; no camera join.**
RoMa v2 ran on three original-image pairs on Thor. GPT-6 Luna reviewed six
queries, each with four detector-generated alternatives, and abstained on all
six: five `none`, one `unclear`. A homography was not fitted because the frozen
minimum of six visually identifiable correspondences was not met.

[Interactive original-image review](https://parhamdb.github.io/sepehrbaba/numbered-landmark-review.html)
· [Raw Luna choices](luna-choices.json) · [Numerical evaluation](evaluation.json)
· [Exact review boards](boards/manifest.json)

## What was tested

The previous wider search did not expose a clearly better rigid landmark. This
experiment tests whether numbered detector points in the plausible shared
patch/cord region make exact correspondence easier to judge. It does not repeat
or supersede the wider frame search.

The main pair is frame 006454 at **410.237478 s** and frame 006548 at
**415.494189 s**, a **5.256711-second separation** across gap 098. Neighbor checks
use frame 006453 (410.187400 s) and frame 006549 (415.544256 s). Each neighbor is
only about 0.05 seconds away on its own side; this is not tracking through the gap.

The [experiment](experiment.json) froze regions, six-query limit, spacing,
shuffle seed and thresholds before inference. SIFT detected 141 source-region
and 340 target-region locations after deduplication. The six highest-response
spatially separated source points were queried. Target options include the
nearest SIFT point to RoMa's prediction and spaced descriptor alternatives.
All options are measured detector locations. A correct answer need not be present.

Luna received 12 marked/unmarked boards and access to four original frames.
It saw neither scores nor the preferred option. The saved raw answer and its
reasoning are retained unchanged. `None` here means no offered alternative was
visually identifiable as the queried physical point; it does not prove that the
point disappears from the entire target image.

## Numerical results, without visual acceptance

All distances below are **native-image pixels**. Snap measures the offset from
a dense prediction to the nearest detected target feature. Cycle is the dense
forward/reverse return error. Source-neighbor delta compares dense predictions
from nearby source views. Source LK return diagnoses the validity of that
short-view transport. Target-neighbor delta compares the transported preferred
SIFT option with RoMa's prediction in the neighboring target view; it also
includes the original snapping offset.

| Query | Luna | Snap | Dense cycle | Source-neighbor delta | Source LK return | Target-neighbor delta |
|---|---|---:|---:|---:|---:|---:|
| Q1 | none | 6.21 | 0.61 | 1.68 | 0.03 | 6.71 |
| Q2 | none | 3.51 | 2.19 | 1.64 | 0.14 | 3.28 |
| Q3 | none | 15.91 | 2.07 | 4.65 | 1.21 | 15.58 |
| Q4 | none | 46.34 | 16.16 | 26.44 | 4.41 | 44.31 |
| Q5 | none | 4.71 | 2.02 | 5.07 | 0.49 | 7.42 |
| Q6 | unclear | 3.44 | 8.12 | 3.44 | 43.92 | 4.62 |

Five queries pass the frozen 25 px snap and 10 px dense-cycle diagnostic limits.
These are candidate screens, not an accuracy claim. Q4 fails both. **Q6's source
LK return is 43.92 px**, despite the optical-flow routine reporting success;
its source-neighbor comparison cannot be treated as reliable local transport.
No new acceptance threshold was chosen after seeing this error. No candidate
passed the independent visual-identification prerequisite in any case.

The smooth cord, reflections, blur and changing occlusion allow plausible region
matches without identifying the same material point. Agreement or round-trip
consistency from one learned matcher is not independent scene evidence. Even a
successful local fit on this flexible surface would not establish rigid-scene
alignment. We made no camera, splat, source-image or existing manual-point edits.

## Reproduction and provenance

Use the project's original 1080×1920 extracted JPEGs, checked against the four
SHA-256 values in `experiment.json`. Review images in
`public/numbered-landmark-review/images/` are byte-identical copies. Board PNGs
are browser screenshots with separate SVG overlays, not replacement evidence.

- Official [RoMa v2](https://github.com/Parskatt/RoMaV2), revision
  `95c9968145c8906b7b59383258e9f73b02853d89`, version 2.0.1.
- Precise setting: 800×800 low resolution, 1280×1280 refinement, bidirectional.
  Full images enter the model; internal resizing still occurs. No architecture
  mask excluded the shared region in this experiment.
- Official checkpoint `romav2.0.1.pt`, SHA-256
  `1557dec0d21b62366465f7ff4d5fdf228cc695d0582e196ad2b80e05230828b7`.
- DINOv3 code pin downloaded by the official model:
  `adc254450203739c8149213a7a69d8d905b4fcfa`. Respect upstream code and weight licenses.
- Native PyTorch correlation fallback; no custom CUDA extension or upstream edits.
- [Matcher record](proposals/matcher-evidence.json) includes actual settings,
  checkpoint/script/experiment hashes, library version, pair runtimes, predictions
  and LK diagnostics. [Feature record](proposals/features.json) retains locations.
- [Set-of-Mark](https://github.com/microsoft/SoM) informed the numbered visual
  interface; this correspondence experiment is our adaptation, not that project's
  validated matching procedure. We did not run its segmentation pipeline.

```bash
# Install the official RoMa requirements in a suitable CUDA environment first.
git clone https://github.com/Parskatt/RoMaV2 third_party/romav2
git -C third_party/romav2 checkout 95c9968145c8906b7b59383258e9f73b02853d89
mkdir -p runs/numbered
cp evidence/numbered-landmarks/experiment.json runs/numbered/experiment.json
PYTHONPATH=third_party/romav2/src python3 scripts/propose_numbered_landmarks.py \
  --images ORIGINAL_NATIVE_IMAGES --experiment runs/numbered/experiment.json \
  --model-repo third_party/romav2 --output runs/numbered/proposals
# Re-evaluate the retained run and blind review without downloading any model:
python3 scripts/evaluate_numbered_landmarks.py \
  --experiment-dir evidence/numbered-landmarks \
  --review evidence/numbered-landmarks/luna-choices.json --output /tmp/numbered-evaluation.json
# Browser boards from the published choices (npm ci first):
node scripts/render_numbered_review.mjs public /tmp/numbered-review-boards
```

An independent new blind review must receive choices and original pixels before
seeing `matcher-evidence.json`, the published answers, or this result. The current
page intentionally reveals the completed review. Re-rendered boards preserve
pixel content and coordinates; PNG hashes may differ with browser/font versions.
No automatic LLM invocation or credential is embedded in these scripts.

## Next hypothesis

Search for a distinctive rigid junction, floor seam or persistent material mark
visible on both sides, including more distant views and revisits. Use an LLM to
name/rank those observations and a matcher to estimate coordinates. Do not spend
further coordinate-refinement attempts on this six-point set. These results
reject this shortlist, not every possible cross-gap correspondence.

## Human selections and geometric check

The user subsequently selected **Q1→2, Q2→1, Q3→1, Q4→1, Q5→1, Q6→4**.
These assertions are recorded separately in [human-choices.json](human-choices.json),
with no invented confidence or pixel uncertainty. Luna's original record remains
unchanged. This human review was not blind: the model and Luna results were public.
The page defaults to the human selections and allows switching to Luna's review.

The existing 5 px RANSAC and 5 px held-out thresholds were retained. We now had six
user-identified points, so the previously blocked local homography check ran on
Thor using OpenCV 4.11.0. No dense-model inference was repeated. Its
[complete result](human-evaluation.json) records the fitted matrix, inlier mask,
actual reprojection errors and held-out errors:

| Point excluded from fitting | User's option | Error predicting that point (native px) |
|---|---|---:|
| Q1 | 2 | No valid fit |
| Q2 | 1 | 31.89 |
| Q3 | 1 | 43.55 |
| Q4 | 1 | 147.06 |
| Q5 | 1 | 325.54 |
| Q6 | 4 | 57.70 |

The all-point RANSAC fit interpolates Q1, Q2, Q3 and Q5; Q4 and Q6 miss by
263.99 and 135.42 px. Fitting four pairs exactly is not validation of the other
two or of camera geometry. Five of the six source points occupy a narrow strip;
Q5 is the main point extending to the right. This limited layout, depth differences,
flexible material and possible correspondence error are competing explanations.
**This failed planar-fit check does not establish which human selections are
wrong.** A single homography is not a general 3D scene model. No section transform
or camera correction was applied. Human selections remain available for future
multi-view/depth checks and additional spatially spread observations.

[OpenCV's homography reference](https://docs.opencv.org/3.4.20/d9/d0c/group__calib3d.html)
describes the RANSAC reprojection threshold and rejection of collinear samples.
Here we also directly recompute errors rather than equating an inlier mask with
verified correspondence.

Reproduce the human result with the same evaluator and OpenCV version:

```bash
python3 scripts/evaluate_numbered_landmarks.py \
  --experiment-dir evidence/numbered-landmarks \
  --review evidence/numbered-landmarks/human-choices.json \
  --output /tmp/numbered-human-evaluation.json
```
