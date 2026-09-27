# Nearby-frame search and local tracking controls

**A01 remains unresolved. A02/A03 can be tracked consistently between adjacent
before-gap frames, but this does not establish a connection across the gap.**

[Open the marked tracking sequence](https://parhamdb.github.io/sepehrbaba/landmark-local-tracking.html).

## Search outcome

A GPT-6 Astra subagent inspected eight contact sheets covering **all 159 original
frames from 408.034244 to 416.495656 seconds**, then 15 promising original images
and four unenhanced native crops. The previously obscured interval was included;
camera registration was not a selection requirement. Contact sheets are browsing
aids, not full-resolution inspection of every image.

The gray patch's lower-left boundary merges with or is overlapped by green
material. Even the larger later view does not expose a uniquely identifiable
material corner. There is **no supported A01 seed or new A01 coordinate**.
The earlier arbitrary 15-pixel shift remains rejected. Extrapolating an unseen
corner from the other edges would not be an observed landmark.

- [Astra search report](seed-review.md) and [structured result](seed-review.json).
- [Frozen 159-frame selection, timestamps and source hashes](selection.json).
- [Contact sheets](contacts/) and [native inspection crops](inspect-native-006454.png).

## Tracking control

Astra provided approximate A02/A03 seeds in frame 006453, immediately before the
target frame 006454. CoTracker3 offline ran on **eight original frames,
006450–006457, spanning 0.351 seconds**. These are entirely before the tracking
gap; this is not an occlusion-recovery benchmark.

| Point | Seed 006453 (x, y) | Prediction 006454 (x, y) | Reverse-cycle error at seed |
|---|---|---|---|
| A02, lower-right | (279, 619), approximately ±6 px | (278.68, 628.07) | 0.53 px |
| A03, upper-left | (209, 554), approximately ±6 px | (208.04, 562.94) | 0.64 px |

The target predictions and reverse-return seeds were predicted visible by the
model. Its official predictor thresholds visibility at 0.9 and forcibly sets
query-frame coordinates/visibility. We check the return at the original seed
after querying from the predicted target in reversed video, rather than treating
the forced query result as a successful check.

Small cycle errors measure this model's internal consistency; they do not prove
that a seed identifies the right physical point. The manually estimated seed
uncertainty is much greater than the reported cycle errors. Neither the same
model run twice nor another language-model review establishes stationarity or
geometric ground truth. This flexible patch alone cannot certify scene alignment.

## Independent marked-image review

A separate GPT-6 Astra thread inspected all eight marked comparisons, the
unmarked seed and target originals, the later reference, and native crops. It
found no gross drift or feature switch in A02/A03, while retaining their blur
and corner-identity uncertainty. It agrees that A01 remains unresolved.
In frame 006456, A02 is predicted visible by the forward run but invisible by
the reverse run. This disagreement is preserved, not treated as a pass.
[Full independent report](final-review.md) · [Structured verdicts](final-review.json).

## Reproduce

Use the original native JPEGs and a compatible CUDA PyTorch environment with
NumPy, OpenCV and einops. The recorded run used PyTorch 2.10.0 on NVIDIA Thor.
No existing camera models, source images or reconstruction datasets were changed.

The [official CoTracker implementation](https://github.com/facebookresearch/co-tracker)
was pinned to `82e02e8029753ad4ef13cf06be7f4fc5facdda4d`; the offline checkpoint is
[scaled_offline.pth](https://huggingface.co/facebook/cotracker3/resolve/main/scaled_offline.pth),
SHA256 `2670d4562ed69326dda775a26e54883925cd11b6fc9b24cb7aa9f8078bce7834`.
The native crop is `(60, 400)–(500, 850)` in every frame. CoTracker internally
resamples this crop to 384×512 and returns coordinates converted back to native
pixels. Model input resampling is distinct from the unchanged original JPEGs
shown in the review page. No enhancement or synthesized imagery was used.

```sh
PYTHONPATH=third_party/co-tracker python scripts/track_landmark_local.py \
  --images ORIGINAL_NATIVE_IMAGES \
  --selection evidence/landmark-local-tracking/selection.json \
  --seed evidence/landmark-local-tracking/control-seed.json \
  --checkpoint third_party/co-tracker/checkpoints/scaled_offline.pth \
  --model-repo third_party/co-tracker \
  --output runs/local-control-tracks.json --crop 60 400 500 850
```

The runner verifies source hashes and rejects an unresolved seed. Its default
three-frame padding around the seed/target yields the eight-frame run. The two
inference passes took approximately 1.08 seconds, excluding input loading and
model initialization. [Raw trajectories and provenance](control-tracks.json)
retain the code/checkpoint/input hashes, native coordinates and visibility.

To reproduce the browsing sheets, arrange the selected source images in
`INPUT_DIRECTORY/images` and copy `selection.json` into `INPUT_DIRECTORY`, then:

```sh
node scripts/render_landmark_contacts.mjs INPUT_DIRECTORY OUTPUT_DIRECTORY
```

The [marked review images](marked/) are screenshots of separate SVG overlays over
original JPEGs. A02 is yellow; A03 is cyan. Marker sizes are display aids, not
measured confidence intervals. No A01 marker was generated for this experiment.

## Remaining scientific question

The clearer-frame search did not resolve A01, so there is no basis for using
tracking to propagate that particular material corner. The useful next option
is to identify other visible landmarks or test dense matching on the shared
region while retaining its masks. This is follow-up work, not a completed
camera-section connection.
