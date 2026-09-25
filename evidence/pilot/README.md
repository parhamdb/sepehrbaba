# Accepted 18-second pilot: reproducibility inputs

`accepted-pilot.tar.gz` preserves the actual accepted pilot's camera models and
masks, rather than requiring contributors to recover the same cameras by chance.
The package is tracked in Git LFS alongside the separately preserved source MP4.

```text
SHA-256  2f11d07ed0a455829dad9fe95d249b489eb0e771fb2a6441e37562e5087c64b6
Bytes    69806245
```

Contents:

- `refined/`: distorted COLMAP binary model for the 252 recovered cameras and
  sparse points; usable as the retained seed for interval expansion.
- `dataset/sparse/`: the corresponding undistorted COLMAP binary model.
- `dataset/masks/`: the exact 252 person-exclusion masks used in training.
- `quality.json`: measured geometry results for the selected 199–217 s interval.
- `frames.json`: all 12,793 source frame names and presentation timestamps.
- `image-sha256.json`: hashes of the 252 undistorted training/evaluation JPEGs.

The package does not contain decoded JPEGs, model weights, credentials, host
configuration, or a training optimizer checkpoint. [`training-state.json`](training-state.json)
preserves the historical training settings and the complete held-out name list,
with host paths omitted. The final PLY remains `public/assets/preview.ply`.

## Use the retained cameras

```sh
git lfs pull --include='evidence/source/*.mp4,evidence/pilot/*.tar.gz'
sha256sum --check evidence/source/SHA256SUMS
sha256sum --check evidence/pilot/SHA256SUMS
mkdir -p work/accepted-pilot
tar -xzf evidence/pilot/accepted-pilot.tar.gz -C work/accepted-pilot

# Extract working images from the unchanged acquired MP4; no feature/mapping run.
python3 scripts/full_video.py evidence/source/sepehr-baba.mp4 \
  --work work/native --colmap /path/to/colmap --stop-after extract
/path/to/colmap image_undistorter --image_path work/native/images \
  --input_path work/accepted-pilot/refined --output_path work/accepted-pilot/dataset \
  --output_type COLMAP --max_image_size 1920
```

The undistorter regenerates images/model files in the extracted working copy,
not the archived package. Use the documented FFmpeg/COLMAP versions and compare
the resulting image hashes with `image-sha256.json` before claiming byte-identical
inputs. Different decoder/encoder builds can change JPEG bytes. Preserve and
report any mismatch rather than silently replacing the historical hashes.

For expansion, use `work/accepted-pilot/refined` as the seed, after preparing the
matching feature database from the source. Camera models alone do not contain
the descriptor/match database. The existing full-video database is not bundled.
The [method guide](../../docs/method.md) documents its construction.

These are derived research artifacts with known scene/masking limitations,
not additional eyewitness evidence. Their presence does not certify the source
recording's capture date, authenticate identities, or establish metric scale.
