# Static geometry cleanup comparison — 2026-09-25

**Decision: retain the published scene.** Static geometry cleanup and camera
refinement did not produce a clear visual improvement at the same training budget.
The candidate is preserved separately; it is not the model served by GitHub Pages.

## Controlled inputs

Both models use the same 252 registered images from 199–217 seconds of the source
recording, byte-identical native-resolution images and masks, 226 training views,
26 held-out views, 8,000 training steps, a 1920-pixel maximum image edge, a
400,000-splat cap, and growth stopping at step 4,000.

`scripts/clean_static_geometry.py` removed masked associations and 6,445 duplicate
point observations. It retained points supported by at least two distinct
unmasked views, then refined 250 cameras with fixed intrinsics. Two cameras with
too few static observations retained their original poses. All 252 image names
and the train/evaluation ordering were preserved.

## Results

| Measurement | Published baseline | Cleanup candidate |
| --- | ---: | ---: |
| Seed points | 109,642 | 91,960 |
| Static-region held-out PSNR | 22.3286 dB | 22.3302 dB |
| Trained Gaussians | 226,293 | 206,042 |
| PLY bytes | 53,406,699 | 48,627,463 |

On the retained static observations, refinement reduced mean reprojection error
from 1.2052 to 1.1780 pixels and the 95th percentile from 2.4575 to 2.4297 pixels.
The final graph remained connected, no associated points lay behind cameras,
and reciprocal point tracks survived the COLMAP binary round trip. Maximum camera
translation was 0.4607 scene units; maximum rotation was 1.657 degrees.

Twelve of the 26 held-out views improved and fourteen worsened. No view regressed
by more than 1 dB; the largest regression was 0.9647 dB. The aggregate gain of
0.0016 dB is effectively a tie, not evidence of a meaningful quality increase.
This is one training run per configuration, not a repeated statistical comparison.

Browser renders used the same authored camera and three fixed offsets: 0.3 scene
units left, 0.3 right, and 0.6 backward. All four loaded without page errors.
Central static objects remained recognizable, but reduced artifacts in some areas
were accompanied by new or shifted smearing elsewhere. Peripheral streaks remained.
The candidate did not pass the predeclared visual-improvement gate.

Published PLY SHA-256:
`75a8950883fbc87bb88b0002763be6bb94d9edabc9fa2a328542c81acb44a622`

## Implication

Cleaner sparse geometry alone was insufficient in this comparison. Because
cleanup and camera refinement were combined, this experiment does not isolate
their individual effects. The next bounded diagnostic would hold the original
camera poses fixed while using the cleaned seed points. Improving temporal masks
is a separate option for the persistent artifacts around occluded people.
Neither follow-up has been run, and this experiment adds no video coverage.
