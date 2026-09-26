# Camera-motion review video

This diagnostic lets a viewer compare recovered camera motion with the actual
recording. It does not refine cameras, train splats, join scenes or invent poses.
The full review includes all 12,793 native video frames, including frames with
**no pose in the supplied snapshot**. It is a scaled, JPEG-derived and re-encoded
review aid; the preserved source remains the evidence reference.

[Watch/download the full 12:17 review](https://media.githubusercontent.com/media/parhamdb/sepehrbaba/main/evidence/camera-review/full.mp4)
· [Silent 17-second sample (09:50–10:07)](https://media.githubusercontent.com/media/parhamdb/sepehrbaba/main/evidence/camera-review/preview.mp4)
· [Full report](../evidence/camera-review/full-report.json)
· [Preview report](../evidence/camera-review/preview-report.json)
· [Portable camera snapshot](../evidence/camera-review/snapshot.json.gz)
· [Per-frame diagnostics](../evidence/camera-review/frame-diagnostics.json.gz).
The content note for the original graphic recording applies to these derivatives.

## Reading the overlay

- Left: source image. Middle: the same image with projected 3D landmarks.
- Cyan circles: where the recovered camera predicts a fixed 3D landmark should
  appear. IDs are stable only inside the named local component.
- Orange crosses: where an adjacent-frame image tracker finds the preceding
  landmark. Pink lines connect predicted and image-tracked positions. Repeated
  sliding on stationary floor or wall features merits investigation.
- Right: local camera trajectory, current position and viewing direction.
  Its orientation and scale are arbitrary. Component changes reset this panel;
  separate components have **not** been aligned into one route.
- No-pose frames are labeled explicitly. Nothing is interpolated through gaps.

Small fitting errors do not independently prove camera correctness: the cameras
and landmarks were fitted to these images. Optical flow is an additional image
measurement, but shares image evidence and can fail under blur, occlusion,
repeated texture or moving people. Similar motion can also arise from different
3D solutions. Review stationary details across time rather than interpreting a
single low error or an attractive trajectory as validation. Areas with no
selected landmarks are not checked by this overlay. No synthetic missing
geometry is added.

The snapshot contains 27 supplied local models and selects poses for 4,502 of
12,793 frames (35.2% by frame count, not time coverage). Supplied models include
unreviewed candidates as well as published scenes. The largest supplied model
wins overlaps, with a deterministic label tie break; this is a display selection,
not a quality ranking. Other unfinished/raw bootstrap models are outside this
snapshot. Processing may recover more cameras after this snapshot was taken.

## Observations from inspected frames

- [03:06.262 component boundary](../evidence/camera-review/component-boundary-0306.jpg):
  the unaligned-component banner and local-path reset are visible. Some fitted
  landmarks lie on visitors' clothing, so these cannot automatically be treated
  as static scene evidence. Camera bias from moving features remains possible.
- [09:50.009 missing pose](../evidence/camera-review/no-pose-0950.jpg): the source
  continues while pose and path are explicitly unavailable.
- [09:58.483 blur](../evidence/camera-review/blur-0958.jpg): only three selected
  fitted landmarks are visible, with median fit error 0.41 source pixels, while
  eight image-flow comparisons have p95 disagreement 33.2 pixels. Heavy blur is
  visible; this discrepancy alone does not establish a camera failure.
- [10:02.049 closer agreement](../evidence/camera-review/closer-agreement-1002.jpg):
  32 flow comparisons have p95 disagreement 3.3 pixels. This is stronger local
  image agreement than the blurred example, not proof of correct global shape.

## Reproduction commands

Dependencies: Python 3, NumPy, Pillow, OpenCV, PyAV, ffmpeg/ffprobe and the DejaVu
Sans font. Rendering is CPU-only. Use native, distorted source JPEGs with the
corresponding raw COLMAP text models; do not mix undistorted training images or
cameras with the raw video. `scripts/full_video.py` creates the native frame and
timestamp inventory.

```sh
python3 scripts/camera_review.py snapshot \
  --frames NATIVE/frames.json --video evidence/source/sepehr-baba.mp4 \
  --model segment-a=RAW_MODEL_TEXT --model segment-b=OTHER_MODEL_TEXT \
  --output snapshot.json.gz

python3 scripts/camera_review.py render \
  --data snapshot.json.gz --images NATIVE/images \
  --video evidence/source/sepehr-baba.mp4 --output NEW_REVIEW_DIRECTORY

# Optional silent preview; intervals use original source seconds.
python3 scripts/camera_review.py render \
  --data snapshot.json.gz --images NATIVE/images \
  --video evidence/source/sepehr-baba.mp4 --output NEW_PREVIEW_DIRECTORY \
  --start 590 --end 607

python3 -m unittest discover -s tests -p test_camera_review.py
```

The portable snapshot includes selected poses/landmarks, local trajectories,
frame times, model hashes and source hashes. It does not include machine paths,
credentials or inferred global transforms. Raw model files must remain unchanged
while the snapshot is read. Rendering checks the source video checksum and raw
camera/image dimensions. The full-length output copies original audio; interval
previews are silent. Every output frame's timestamp is checked against the source
manifest, with a two-microsecond tolerance and an exact frame-count requirement.

Landmarks must have at least five observations and mean COLMAP error at most two
source pixels. Up to 32 are chosen per frame, favoring long tracks and spatial
coverage. Flow uses the preceding selected observations, forward/backward LK
consistency within one display pixel, adjacent poses in the same component, and
a maximum time gap of 0.20 seconds. Error values are reported in source pixels;
tracking itself runs on the 432×768 display image. Simple radial distortion is
applied before comparing predictions with raw images.

## Acceptance and evidence

Frozen inventory: (1) projection/pose math and an intentionally wrong camera
synthetic control, (2) short real preview with visual inspection, (3) complete
frame/timestamp/audio checks, (4) representative tracked/gap/component-boundary
stills, and (5) portable artifacts and public download. One discovery pass,
focused remedies and one final check of the frozen output. The reconstruction
batch, splat quality, global registration and public 3D viewer are outside scope.
Renderer source was frozen at `081d785`. Full rendering retained 12,793 frames,
with zero timestamp error against the native manifest. There are 4,502 posed
frames, 8,291 no-pose frames and 4,361 frames with image-flow comparisons.
The report's 120 `component_changes` count includes resumptions after missing
poses, not just changes to a different model. Twenty-two of the 27 supplied
models contribute selected frames. The three synthetic/numeric controls passed
again on the frozen renderer; independent code review found no high/medium
defect. The selected visual observations above are diagnostic findings, not
certification of the whole camera trajectory.

[Final verification ledger](../evidence/camera-review/validation.json): **5 passed,
0 failed, 0 blocked, 0 untested**. The frozen full and preview videos were decoded
independently and every frame timestamp checked again. Full duration is
737.301333 seconds; the encoded audio payload hash exactly matches the original.
The full public download at artifact commit `d3a0edf` matches the report SHA-256.
These checks validate the diagnostic's delivery and timing, not scene geometry.

Method references: [COLMAP camera and image conventions](https://colmap.github.io/format.html#text-format)
and [PyAV timestamps and time bases](https://pyav.org/docs/stable/api/time.html).
