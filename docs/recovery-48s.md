# Earlier 48-second component

This experiment reuses the completed full-video window search. It reconstructs
**136.7–184.9 seconds (about 02:17–03:05)** as a separate scene. It does not
extend the 71-second model's coordinate system or establish a continuous walk
between the previews.

## Camera geometry and masks

The retained `window-120-210/refined` component contains **689 cameras and
264,661 points**. Over the deliberately scoped 48.2-second interval, it registers
**689 of 725 frames (95.0%)**. Its mean reprojection error is **1.12089 px**, p95
**2.41875 px**, with **zero observations behind their camera**. Those 689 cameras
are only **5.39% of the recording's 12,793 frames**. Scoping the component does
not turn the rejected 90-second window into a complete reconstruction.

`prepare_component.py` checks the existing geometry against the unchanged 90%
coverage, 1,000-point, 1.5 px mean, 3.5 px p95 and zero-behind-camera thresholds.
It records source model hashes and verifies that undistortion did not modify the
model. It avoids repeating mapping or bundle adjustment unnecessarily.

All **689 masks** passed inventory and dimension checks. Eight source/overlay
examples, including the minimum and maximum exclusions, were visually inspected.
The median excluded area is 33.2%; 159 frames have more than half their pixels
excluded. Standing people are mostly excluded, but masks miss parts of blurred clothing
and also exclude some trolley parts and static human details. These limitations
remain relevant to human-rights documentation: the derived model cannot replace
the source recording for examining people or their injuries.

## Reproduction

Use the pinned tools from `setup.sh`. Set the paths to your own retained window
search and native-frame run; no private host or workspace is required.

```sh
python3 scripts/prepare_component.py \
  --model "$WINDOWS/window-120-210/refined" --source-run "$NATIVE" \
  --work "$COMPONENT" --colmap "$COLMAP" --start 136.7 --end 184.9
python3 scripts/mask_people.py "$COMPONENT/dataset"
python3 scripts/inspect_masks.py "$COMPONENT/dataset" "$COMPONENT/mask-review.jpg"
# Inspect mask-review.jpg before training.
python3 scripts/video_to_splat.py --stage train \
  --dataset "$COMPONENT/dataset" --output "$TRAINING" --brush "$BRUSH" \
  --steps 8000 --train-resolution 1920 --max-splats 500000 --eval-split-every 10
python3 scripts/inspect_brush.py "$COMPONENT/dataset" \
  "$TRAINING/splats/eval_8000" "$TRAINING/inspection" --expected-views 69
mkdir "$COMPONENT/dataset-model-text"
"$COLMAP" model_converter --input_path "$COMPONENT/dataset/sparse" \
  --output_path "$COMPONENT/dataset-model-text" --output_type TXT
python3 scripts/prepare_references.py --dataset "$COMPONENT/dataset" \
  --model-text "$COMPONENT/dataset-model-text" \
  --held-out-renders "$TRAINING/splats/eval_8000" \
  --training-state "$TRAINING/state.json" --output "$TRAINING/references" \
  --train-stride 20 --include frame_002261
```

The opening pose is `frame_002261`, beside the brick wall. Its position, target
and field of view come from the undistorted camera model through
`prepare_references.py`. Ground pixels in frames 2261 and 2368 are recorded in
[floor-selection-48s.json](floor-selection-48s.json). `level_scene.py` fits
**1,505 inliers from 2,067 selected points**, with RMS **0.00695 scene units**,
and applies a **17.8218° display rotation**. The PLY stays in its original axes;
there is no established metric scale.

To reproduce the display rotation from the published manifest, write its
`orientation.source_camera` back into `camera`, remove `orientation`, and save
that as a fresh unrotated JSON file. Then run:

```sh
python3 scripts/level_scene.py --model-text "$COMPONENT/dataset-model-text" \
  --scene "$UNROTATED_SCENE" --selection docs/floor-selection-48s.json \
  --output "$LEVELED_SCENE"
```

## Why it is not joined to the later section

The registered time ranges end at **184.795589 s** and begin at **186.262200 s**:
a **1.466611-second gap**. Inspection of frames from 183.5–188 seconds shows
people very close to the camera; a coat almost completely blocks the view
around 185.5 seconds. Temporal continuity does not supply visible, static
features through that occlusion.

The [read-only bridge audit](bridge-48s-71s.json) finds **zero shared registered
cameras**, only **two cross-component verified SIFT pairs**, with **16 and 15
inliers**, and none with at least 100 inliers. The latter count is a diagnostic,
not an alignment acceptance threshold. These observations do not support
merging the models. No model-merger, fresh mapping, or learned-matching bridge
run is claimed by this checkpoint.

```sh
python3 scripts/audit_bridge.py --model-a "$COMPONENT/model-text" \
  --model-b "$LATER_MODEL_TEXT" --database "$WINDOWS/database.db" \
  --frames "$NATIVE/frames.json" --output "$BRIDGE_REPORT"
```

The subsequent [connection experiments](connecting-scenes.md) tested static
RootSIFT matching, fresh ALIKED detections and learned descriptors at existing
3D features. None passed independent alignment checks. Candidate data and
rejected fits are preserved; the public models remain separate. Manual review
of unmistakable shared static landmarks is the next proposed step.
[COLMAP guidance on disconnected models](https://colmap.github.io/faq.html#merge-disconnected-models)
requires common registered images for its model-merger workflow.
[LightGlue's official implementation](https://github.com/cvg/LightGlue)
supports SIFT and ALIKED. Our pinned COLMAP 3.12.6 does not automatically gain the
learned-feature options described in newer COLMAP documentation.

## Export and native evaluation

Training completed all **8,000 steps in 615.5 seconds**, using **620 training
views and 69 held-out views**, with maximum image edge 1920. The export contains
**500,000 Gaussians**, is **118,001,551 bytes**, and has SHA-256
`93a813f158351d1e328479f3440a3097b02497176504bb4397efafa25f5a69e6`.

All 69 held-out renders were measured. Pixel-pooled PSNR over unmasked regions
is **22.6128 dB**. This is not directly comparable with another scene's score
because the views and excluded regions differ. The first, middle and last
source/render pairs were inspected: central static ground and body-bag surfaces
remain recognizable, while the occluded ends have substantial blur and uncertain
surfaces. The opening pose was checked against the actual exported references.

The separate viewer URL is
[the experimental earlier scene](https://parhamdb.github.io/sepehrbaba/?scene=recovery-48s).
Its manifest records coverage, export hash, training counts, limitations, original
camera, floor selection and display rotation. The pilot and 71-second PLY files
are preserved unchanged.

## Browser and release validation — September 26, 2026

The public release is `6688f4b88b8324a8748af87a37bda0423ca75a5d`.
[GitHub Pages build and deployment](https://github.com/parhamdb/sepehrbaba/actions/runs/36210240452)
succeeded. The live HTML, JavaScript, CSS and 48-second manifest matched the local
build byte for byte. Downloading and hashing the entire public PLY confirmed the
118,001,551-byte export and SHA-256 above.

The frozen browser inventory comprised seven cases: pilot desktop and mobile,
missing-manifest recovery, 71-second desktop and mobile, and 48-second desktop
and mobile. Local discovery passed six cases; the new desktop case exhausted
its 90-second overall budget just before Reset after rendering, orbit and free
movement. The same product passed that single focused case with a 150-second
budget; no viewer or reconstruction change was made for this test issue.

The final pass against the **public Pages site passed all seven cases in 6.9
minutes: 7 passed, 0 failed, 0 blocked, 0 untested**. It used Chromium software
WebGL, a 1280×720 desktop viewport and 390×844 mobile emulation. This is not a
physical-device or hardware WebGPU test. Checks cover scene loading, entry pose,
visible surfaces, orbit, free movement, reset, scene links, error recovery and
rendered ground alignment. Entry and orbit screenshots were visually inspected;
blur and ghosting around people, trolley parts and peripheral surfaces remain.

The pilot and 71-second assets and manifests were unchanged. Changed text files
and the PLY header were checked for personal paths, private IPs and credential
markers; none were found. Both reconstruction jobs had exited successfully,
and the GPU was idle after completion. This validation record is a documentation
update; it does not change the tested release artifact.
