# Contribution-aware cleanup experiment

2026-09-25. **Implemented and tested; neither candidate improves the dominant
ghosting enough to publish. The accepted scene remains unchanged.** This tests
a bounded version of [rank 1](ghosting-options.md), not every possible version
of contribution-aware cleanup.

## Scope and decision

Use the existing 199–217 second pilot, trace contributions to nominated artifact
regions, and halve opacity only where static source evidence supports the change.
The input has 226,293 Gaussians. No retraining, depth estimation, full-video
expansion, or new segmentation model was included. No candidate was deployed.

Baseline SHA-256:
`75a8950883fbc87bb88b0002763be6bb94d9edabc9fa2a328542c81acb44a622`.
Implementation commits: `209812a`, `12c580f`; mask-exclusion test: `eae4a01`.

| Candidate | Hypothesis | Changed splats | Result |
| --- | --- | ---: | --- |
| Static-region attribution | Splats contributing to an artifact in several unmasked views can be suppressed without hurting other observed surfaces | 40 (0.0177%) | Tiny changes; dominant ghosting remains |
| Masked-region localization | Masked pixels may locate an artifact, while source RGB outside masks verifies the change | 49 (0.0217%) | Slightly more change; dominant ghosting remains |

Both candidates retain all Gaussian records and halve only selected opacity
values. Unselected records and every other field are verified byte-identical.
Candidate manifests save the selected IDs, original opacity logits, input/output
hashes, fraction, views and selection scores.

Candidate SHA-256 values, respectively:

```text
46e9fa0fc4817340a746df993cd56c7aa614e52c99ad3ec375e9c98101edca48
abb0dbe58a37701a7a755a7ffe4357e79eb88d284c96b6e30dc9b1ac2d6372d9
```

The conservative evidence checks selected very few splats: 2,890 contributed
to nominated regions in at least two views, and 380 also had sufficient static
support outside those regions. Most of those did not pass the source-error
checks. This suggests that this selection rule does not isolate the dominant
ghosts. It does not prove that the underlying geometry is inseparable or that
all forms of rank 1 will fail.

## What the script computes

[`score_splat_contributions.py`](../scripts/score_splat_contributions.py) uses
PyTorch to approximate the pinned PlayCanvas 2.22.3 renderer: degree-3 spherical
harmonics, projected ellipses, radial sorting, antialiasing, and alpha compositing
against black. It is custom analytical code; FlashSplat was not installed or
claimed as the implementation. The reference shader behavior is in the pinned
[PlayCanvas source](https://github.com/playcanvas/engine/tree/v2.22.3/src/scene/shader-lib/glsl/chunks/gsplat).

For each sampled pixel, a splat contributes its opacity multiplied by the
transmittance of the splats in front. The counterfactual loss computes both the
removed contribution and the extra background revealed when opacity falls.
Synthetic tests compare this with an independent back-to-front compositor.

Fifteen training views were scored at 532 × 946. Sampling uses an 8-pixel grid
and additional 4-pixel samples inside nominated regions. These are coarse visual
regions in frames 3139, 3140 and 3269, not independently verified per-pixel ghost
labels. The existing person masks exclude uncertain source colors from every
loss and protection score. Masked-region localization uses contribution weights
inside masks, but never their RGB values as evidence of correctness.

Default selection requires all of the following:

- Region contribution above 0.05 in at least two views and total above 0.2.
- Static contribution outside the region above 0.05 in at least three views.
- Total predicted loss improvement greater than twice accumulated pixel-level harm.
- Positive static-region loss improvement above 0.0001. The masked-localization
  variant omits this last condition, retaining the other static-source checks.

The export refuses an empty selection or a selection exceeding 2% of the model.
That cap bounds the experiment; it is not a validated safe pruning percentage.
No thresholds were relaxed after the second candidate failed the visual gate.

## Verification and limits

| Frozen acceptance item | Status | Evidence |
| --- | --- | --- |
| Compositing, masks and reversible export | Passed | Four focused tests on Thor: occlusion-aware counterfactual, negligible hidden-splat effect, immutable unrelated PLY data, and masked RGB exclusion |
| Analytical/browser calibration | Passed | Full training-frame comparisons: 39.2958 dB for 3139 and 39.8451 dB for 3269; matched structure inspected |
| Training-only attribution | Passed | Fifteen training views scored; manifests exclude held-out views |
| Clear source/navigation visual gain | Failed | Four fixed navigation positions per candidate show only tiny changes and persistent ghosts |
| Held-out nonregression | Blocked | Visual acceptance prerequisite failed; 26 held-out views not used for tuning or evaluation |
| Browser publication | Blocked | No accepted candidate |

**Totals: 3 passed, 1 failed, 2 blocked, 0 untested acceptance items.** No final
broad regression run was warranted after the failed visual gate. Browser
navigation completed with no recorded page errors. Mean absolute changes across
the four 720 × 800 navigation captures were 0.019–0.022 intensity levels out of
255 for the 40-splat candidate, and 0.029–0.033 for the 49-splat candidate.
These difference measurements describe change, not improved quality.

Source-frame browser capture across all fifteen scored views did not complete:
software-renderer captures timed out or stalled. Logs were preserved and the
stalled job stopped. A focused comparison used the three nominated source poses.
The 3140 pair shows broader rendering differences than expected from the tiny
opacity edit, so its numeric change is not treated as reliable cleanup evidence.
This capture limitation does not change the failed four-view navigation result.
No completed fifteen-view browser metric or held-out result is claimed.

Further limits matter before reusing scores:

- The approximate renderer omits exact GPU texture quantization and sorting
  behavior. Its approximately 39 dB agreement is adequate for localization, but
  not proof that very small predicted gains are accurate.
- Positive effects are computed one splat at a time. Simultaneous changes can
  interact; the exported group must be evaluated independently.
- Denser region samples give a spatially weighted score, not uniform full-image
  loss. Fifteen views are a subset of the 226 training views.
- Masks can exclude the very background observations needed to distinguish a
  ghost from a real surface. They are not semantic proof of bad geometry.
- The initial calibration missed the screen-space axis cap; that was corrected
  before export. A CUDA eigensolver failure was avoided with closed-form 2 × 2
  eigenvalue arithmetic. Failed calibration artifacts were retained.

An independent code review found no high/medium correctness issue in the first
implementation, and specifically identified group interactions and sample
weighting as limits requiring browser validation.

## Running the bounded tool

Requires Python 3, NumPy, Pillow and PyTorch. This run used Thor with CUDA and
PyTorch 2.10; no training job is started by this tool. `--device cpu` is available
for small diagnostic inputs.

Inputs:

```text
references/views.json           array of camera records
references/images/<name>.jpg    undistorted RGB at the evaluation resolution
references/masks/<name>.png     matching dimensions; 0 = ignored, nonzero = static
regions.json                   {"regions": [{"image": "frame_003139", "box": [0, 0.05, 0.2, 0.4]}]}
```

Each camera record contains `name`, `split` (`train` or `held-out`), `position`,
`target`, `up`, and vertical `fov` in degrees. Poses use viewer coordinates with
the PLY rotated 180 degrees around Z. Images must match these poses and centered
pinhole intrinsics. Boxes use normalized `[left, top, right, bottom]` coordinates.
This interface does not recover poses from video or convert arbitrary cameras.

```sh
# First calibrate a full training view against the actual browser renderer.
python3 scripts/score_splat_contributions.py scene.ply references regions.json \
  calibration --full-view frame_003139

# Only after independent calibration: score training views and export a copy.
python3 scripts/score_splat_contributions.py scene.ply references regions.json \
  candidate-static --export
python3 scripts/score_splat_contributions.py scene.ply references regions.json \
  candidate-masked --export --localize-masked

python3 tests/test_contribution_scoring.py
```

Every output directory must be new. `--export` is an explicit manual calibration
gate, not an automatic verification that calibration passed. Inspect the separate
candidate; do not replace `public/assets/preview.ply` merely because export succeeds.

## Evidence and smallest useful revisit

Private local evidence is in `sepehr/runs/contribution-clean-20260925/`: the
authoritative `ledger.json`, manifests, calibration images, source/mask references,
browser captures, comparison panels, capture failures and helper scripts. Thor
retains `~/sepehr/contribution-clean-20260925/{discovery,masked-localization}/`,
including per-view scores and candidate PLYs. Local candidate assets are under
`sepehrbaba/work/post-clean/assets/`. Raw evidence and source imagery are not
added to the public repository by this experiment.

Revisit rank 1 with a precisely labeled ghost visible from independently useful
views, verified background observations, or reliable depth/free-space constraints.
An exact renderer contribution buffer would also remove approximation uncertainty.
Constrained surface refinement remains untested; this run did not identify a
visibly useful suppression to refine around. Simply increasing deletion or opacity
thresholds is not supported by the result.

Rank 2 remains the next separate experiment if temporal transient evidence is
prioritized. It was not launched as part of this work.
