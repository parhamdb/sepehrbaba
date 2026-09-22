# Sepehr Baba

An interactive 3D Gaussian-splat viewer published on GitHub Pages.

**[Open the 3D scene](https://parhamdb.github.io/sepehrbaba/)**

**Current scene: partial preview, approximately 00:16–00:26 of a 12:17 recording.**
It contains 4,635 Gaussians recovered from 21 camera views. It is soft and incomplete;
the rest of the recording is not represented by this preview. The page labels this
coverage before and during viewing. The scene contains imagery of deceased people.

Enter the scene, drag to orbit, and scroll/pinch to zoom. Choose **Move freely**
to navigate with W A S D or the on-screen directional controls. **Reset view**
returns to the authored camera. Press Esc to release the mouse after keyboard movement. This is a visual scene with no collision barriers.

## Development and publishing

```sh
npm ci
npm run build
python3 -m http.server 8080 --directory dist
```

The Pages workflow builds and deploys `dist/` on pushes to `main`. All scene and
viewer files are served from the repository's Pages site; no visitor login is
needed. The viewer uses WebGPU with WebGL fallback. Append `?webgl` to force WebGL.

`public/scene.json` describes the current scene, initial camera and orientation.
`public/assets/preview.ply` is the current model. Replace these together when a
larger reconstruction is verified, and update the visible coverage labels.
Do not label this small preview as a reconstruction of the entire video.

## Technology and evidence

- [SuperSplat Viewer](https://github.com/playcanvas/supersplat-viewer), MIT license.
- [PlayCanvas Engine](https://github.com/playcanvas/engine), MIT license.
- Reconstruction: COLMAP camera recovery and Brush Gaussian training.
- Current model: 3,000 training steps; 18 training views / 3 held-out views;
  held-out PSNR 19.21 dB and SSIM 0.675. These are small-preview metrics only.

Third-party license notices accompany the bundled viewer. No license or identity
claim is made about the underlying source recording or the people it depicts.

## Full recording reconstruction

`scripts/full_video.py` preserves every decoded frame at its native dimensions
as high-quality JPEG (quality 1; not lossless), with exact source timestamps.
The original MP4 remains the unchanged source reference. It extracts features
from every frame. The sharpest frame in each group of four bootstraps mapping;
remaining frames are then offered to camera registration. Recovered views feed
training, with every tenth view held out for evaluation.

Requires Linux, Python 3 + Pillow, FFmpeg, a CUDA-enabled COLMAP 3.12.6 build,
and Brush 0.3.0. Supply your own local tool paths:

```sh
python3 scripts/full_video.py /path/to/input.mp4 \
  --work /path/to/reconstruction \
  --colmap /path/to/colmap --brush /path/to/brush_app \
  --max-seconds 7200
```

Completed stages resume with the same command. The process stops its own child
jobs at the time limit or below 4 GiB available memory. See `state.json`,
`frames.json`, `logs/`, and, after mapping, `coverage.json`. Interrupted mapping
is preserved separately before a new mapping attempt. Feature/match databases
can resume completed entries. An interrupted training stage starts again.

Disconnected camera models remain separate. Missing registrations are listed;
the script never treats continuity of the video as proof of one connected 3D
model. Inspect coverage and held-out renders before publishing a larger scene.
The full pipeline is still being exercised on the source footage; the published
preview does not imply that the full recording has been reconstructed.
