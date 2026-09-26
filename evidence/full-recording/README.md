# Full-recording processing evidence

[Window plan](plan.json) covers the complete 737.301333-second recording with
37 overlapping windows and accounts for all 12,793 native frames. The retained
feature database contains every source frame; 12,780 have detectable keypoints.
The 13 without keypoints are not silently removed from the coverage denominator.

[Batch method and reproduction](../../docs/full-recording-batch.md).

The batch runs retained-component training first, followed by shorter-window gap
recovery. Processing the recording does not guarantee reconstruction of every
surface. New splats remain provisional until visual review. The published
18-second pilot overlaps the existing 71-second scene and adds no unique duration.

## Running campaign snapshot

[Processing status](processing-status.json) is a **committed snapshot**, not a
live connection to the reconstruction machine. Its Unix `updated` timestamp
identifies when it was captured. The full batch is still running; the 37 gap
windows are queued after retained-component training. Do not interpret an empty
attempted-window list as a completed search.

## First additional candidate: 09:50–10:06

[Download provisional Gaussian splat, 7.9 MB](https://media.githubusercontent.com/media/parhamdb/sepehrbaba/main/evidence/full-recording/candidate-590-606.ply)
· [Held-out source/render comparison](candidate-590-606-views.jpg)
· [Mask review](candidate-590-606-masks.jpg)
· [Measured held-out views](candidate-590-606-evaluation.json)

- Registered interval: **590.629889–606.465111 seconds**; 368 of 374 interval
  frames, 98.40%; 15,481 sparse points.
- Geometry: mean reprojection 1.27674 px, p95 2.56575 px; no observations behind
  cameras. These checks do not establish complete or survey-accurate geometry.
- Training: 8,000 steps, maximum image edge 1920, 331 training views and 37
  held-out views; **33,497 exported Gaussians**. 500,000 is a cap, not a target.
- Export: 7,906,842 bytes; SHA-256
  `d2352a2cfc2fdf7cef17f9cbbd636f7be38a2f782c6e074b8fa996d57da8d76c`.
- Pixel-pooled held-out PSNR: **23.4921 dB over unmasked pixels**. Scores across
  different scenes/masks are not directly comparable and do not prove geometry.

Eight mask examples and first/middle/last held-out comparisons were visually
inspected. Central bags and nearby static surfaces remain recognizable; the
ends contain motion blur and uncertain surfaces. Median mask exclusion is
33.93%; 97 of 368 frames exclude over half their pixels. Some static human
details are incorrectly masked; moving people are not perfectly removed.

**This candidate is not published in the interactive viewer yet.** Two selected
floor regions failed the minimum reconstructed-point check, so no floor rotation
was accepted. [Retained display-review selections](candidate-590-606-floor-review.json)
preserve those attempts. Camera entry, display orientation and novel-view browser
navigation remain unverified. The download preserves the original Brush axes;
the existing public scenes are unchanged.
