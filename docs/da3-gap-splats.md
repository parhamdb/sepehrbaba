# Experimental DA3 splats for missing video intervals

The current 72-model library is based on COLMAP. This experiment trains separate
short sections from already retained full-recording DA3 camera/depth predictions
for the 5,100 source frames absent from those splats. A frozen plan uses ten-second
windows on an eight-second grid, extending one second before each grid anchor.
All 78 windows with missing frames are included, including short registration
holes. Every native frame in each selected window remains eligible.

The first pilot is the earliest substantial mostly missing interval, around
02:07–02:17. After inspection, remaining windows run in descending missing-frame
count. Each section has its own camera-centered origin, orientation and scale.
This removes arbitrary global coordinate scale from training; **it does not
correct DA3's within-window drift or certify the camera path**. No camera
inference or global scene connection is repeated.

## Frozen method

- Preserve native 1080×1920 JPEGs and verify their hashes against DA3's input
  inventory. Retain original frame names and variable timestamps.
- Reuse DA3's 280×504 depth, confidence and camera calibration. Map intrinsics
  to native pixels, verify processed/source image association on three views,
  and retain actual depth-file hashes for every prepared section.
- Initialize from the upper half of depth confidence on an eight-pixel grid
  in every eighth eligible training view. These are **predicted depth points**,
  exported with empty COLMAP observation tracks, not recovered feature matches.
- Every tenth image is withheld from Brush and depth/color seeding. DA3 itself
  previously processed all images, so this is an appearance holdout, not a fully
  independent neural-camera evaluation.
- Brush 0.3.0: 8,000 steps, 1920 maximum image edge, at most 500,000 Gaussians.
  Retain the Gaussian PLY, all held-out renders, full-image PSNR and comparisons.
- **No person-exclusion masks in this camera experiment.** Bodies and people
  remain in the source images. Moving visitors can ghost. Selective SAM cleanup
  requires a separate reviewed pass; legacy blanket person masks are not reused.

The existing 72 splats and their identifiers/numbers remain unchanged. New
outputs are experimental additions, never replacements or automatic joins.
Coordinate normalization does not count as recovered geometry. Source video,
DA3 predictions and earlier reconstruction results remain unchanged.

## Run

Use the existing worker environment with NumPy, SciPy, Pillow, OpenCV and the
pinned Brush executable. The baseline catalog must be frozen for the campaign.

```sh
python scripts/train_da3_gap_sections.py \
  --inference /path/to/full-da3/inference --images /path/to/native/images \
  --catalog /path/to/frozen-72-section-catalog.json \
  --output /path/to/new-da3-gap-campaign --brush /path/to/brush_app --limit 1
# After inspecting the pilot, continue with the identical inputs and scripts:
python scripts/train_da3_gap_sections.py \
  --inference /path/to/full-da3/inference --images /path/to/native/images \
  --catalog /path/to/frozen-72-section-catalog.json \
  --output /path/to/new-da3-gap-campaign --brush /path/to/brush_app --resume
```

Use a persistent service, no runtime cutoff, and an appropriate memory ceiling.
There is one writer/lock. `progress.json` records stages and completed, failed
and pending sections. Completed outputs are reused only if their PLY hash still
matches; failed stages are retained without automatic retries. An interrupted
running section or changed source/configuration requires explicit diagnosis in
a fresh campaign. Three consecutive failures of the same stage/type stop the
batch for inspection. Disk and memory reserve checks precede each section.

Acceptance: geometry/export checks; real native pilot preparation and training;
held-out and interactive inspection; persistent sequential continuation; stable
numbered library additions and timestamp linkage; committed scripts and honest
coverage/quality records. Test budget: one discovery, targeted failure checks,
one final pass. The prior local test attempt lacked SciPy; all three focused
checks passed in the actual worker's existing DA3 environment.

## Numbered LAN previews

`scripts/import_da3_gap_section.py` appends a completed experiment after checking
its PLY, source-frame timestamps and evaluation inventory. Original entries stay
in the same order; DA3 additions begin at #73, in completion order. Their cards
and editor labels say **DA3 experimental**. The source-video overlay includes
their numbers at the corresponding timestamps. Frame coverage counts their
input views; it is not a measurement of accurate recovered surfaces.

```sh
python scripts/import_da3_gap_section.py --library /path/to/library \
  --section /path/to/copied/da3-gap-000128 --frames /path/to/frames.json
```

The server accepts append-only catalog refreshes without restarting open pair
editors. Reload the library page to see newly completed sections. Each ordered
pair still has separate saved placements; importing does not edit those saves.
The campaign's baseline catalog remains frozen at 72 entries, independently of
the growing runtime catalog.

For automatic copying, run `scripts/sync_da3_gap_sections.py` as a persistent
local service with `--host`, `--control-path` (an existing authenticated SSH
connection), `--remote`, `--local`, `--library` and `--frames`. It transfers only
completed PLYs, preparation/evaluation receipts and renders, verifies the worker
PLY hash, then imports. `--once` performs one scan. It never trains, changes Git,
or stores credentials. Three consecutive transfer failures stop polling and
retain `sync-error.txt`; reconnect and restart after inspecting the cause.

Automatically imported models remain unreviewed experiments. Only an explicit
visual review can establish whether a particular section is useful for manual
alignment, and that review alone cannot certify metric accuracy.
