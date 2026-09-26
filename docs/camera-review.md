# Camera-motion review video

This diagnostic lets a viewer compare recovered camera motion with the actual
recording. It does not refine cameras, train splats, join scenes or invent poses.
The full review includes all 12,793 native video frames, including frames with
**no pose in the supplied snapshot**. It is a scaled, JPEG-derived and re-encoded
review aid; the preserved source remains the evidence reference.

[Watch the silent 17-second sample (09:50–10:07)](https://media.githubusercontent.com/media/parhamdb/sepehrbaba/main/evidence/camera-review/preview.mp4)
· [Preview report](../evidence/camera-review/preview-report.json)
· [Portable camera snapshot](../evidence/camera-review/snapshot.json.gz).
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

## Reproduce

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
Results and artifact links are recorded here after rendering.

Method references: [COLMAP camera and image conventions](https://colmap.github.io/format.html#text-format)
and [PyAV timestamps and time bases](https://pyav.org/docs/stable/api/time.html).
