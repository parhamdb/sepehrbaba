# Full-recording splats for manual stitching

The full 737.301333-second recording was already processed in 37 overlapping
windows. Inspection of retained worker results on October 4 found **70 trained
batch splats**, plus the **two previously published components**: **72 separate
models**. Ten batch components had failed only at reference-camera export after
training. Their actual PLYs and held-out renders are retained and loadable; they
must not be counted as missing training outputs.

The 72 models contain 7,693 distinct registered source frames out of 12,793
(**60.1%**). The union of their timestamp spans is 449.606298 seconds, about
7 minutes 30 seconds. Span coverage includes registration holes and is not full
surface coverage. The final trained section ends at 726.121689 seconds; the end
of the recording remains unreconstructed. Every source interval was attempted;
that does not mean all twelve minutes were successfully reconstructed.

The remaining 101 component failures comprise 100 preparation/geometry failures
and one Brush training failure (empty Gaussian array). Among preparation failures,
30 had low registration coverage, 23 had both low coverage and too few sparse
points, 43 had too few points, and four contained fewer than twenty source
frames. These are recorded screening failures; the library does not silently
relax their thresholds. Failures can overlap
successful components. The library lists exact missing-frame intervals, including
holes inside broad section spans, instead of substituting a continuous camera
path. It does not rerun completed training, weaken geometry gates, or generate
missing surfaces.

## What the library provides

- A time-ordered catalog of all 72 existing models, with actual held-out render
  thumbnails, timestamps, registered-view counts and Gaussian counts.
- A single-section 3D view, or exactly two selected sections in the existing
  mobile-friendly editor, retaining per-section filters, crop and visibility.
- Independent saved placement per ordered pair. Opening another pair does not
  carry a transform forward or establish a shared global coordinate system.
  Export JSON preserves a placement for later assembly.
- Each model starts at its own middle source camera, oriented consistently and
  scaled by median positive sparse depth. This is only a convenient display
  normalization. Apparent initial overlap does not establish a connection.
- Byte-verified source PLY copies and a complete processing/coverage inventory.
  The original source video, models and existing selectively cleaned pair remain
  unchanged. The latter stays in its existing separate editor.

**Mask limitation:** these older models used blanket person masks. Static human
bodies and other documentation details may have been removed. They have not
received the reviewed, selective SAM 3.1 video cleanup applied to the current
78/235-frame pair. Keep original footage authoritative and do not call these
legacy candidates clean. Rays, ghosting and inaccurate geometry remain possible.

The ten reference-export failures came from strict square-pixel requirements
(for example, focal lengths 1465.56947 versus 1465.67408). The library uses camera
extrinsics for a navigable preview and actual Brush renders for thumbnails;
it does not relax the calibrated-reference evaluation gate or claim exact
source-image reprojection in its arbitrary-aspect-ratio viewport.

## Reproduce

Use the retained full-processing campaign and its original source-frame metadata.
The packager requires Python, NumPy and Pillow. Supply the two published training
and text-model directories explicitly; private paths and credentials are never
written into the portable catalog.

```sh
python3 scripts/package_recording_sections.py \
  --campaign /path/to/full-processing-campaign \
  --output /path/to/new-section-library \
  --published 6deb698bd2335e70 /path/to/48s-training /path/to/48s-model-text \
  --published ad2074d6e6e51c50 /path/to/71s-training /path/to/71s-model-text
node scripts/build-stitch-editor.mjs
node scripts/section-library-server.mjs \
  --library /path/to/new-section-library \
  --state /path/to/new-pair-placements \
  --host 0.0.0.0 --port 8095
```

Open port 8095 on the trusted LAN host. Only the two selected assets load into an
editor, not all 72. The library contains about 1.31 GB of PLYs; phone memory may
limit the largest pairs. Run through a persistent user service for LAN access.
The catalog itself is lightweight and lazy-loads thumbnails. No GPU training is
necessary to recover these already completed outputs.

The source methods and sanitized coverage/verification receipts belong in Git.
Bulk generated PLYs remain in the local library; their hashes identify the exact
retained outputs. This delivery does not replace the public reconstruction page
with unreviewed legacy models.

Acceptance inventory: portable artifact integrity and complete window/coverage
accounting; all 72 models loading and rendering; pair-only editing with saved
state isolation; mobile catalog selection; preservation of the current pair.
Validation budget: one discovery pass, focused failure checks and one final pass.
No new geometry recovery, full-recording SAM cleanup, automatic stitching or
invented geometry is part of this library delivery.

## Verified delivery

Final verification on source `b71d945`: **77 passed, 0 failed, 0 blocked,
0 untested**. All 72 PLYs passed byte-identity and actual browser render checks.
Pair editing, save/reload, isolation, mobile selection and the live deployment
passed. The existing pair's manifest, transforms, filters, crop and visibility
were unchanged. One discovered single-section API routing defect was fixed in
`b417ec6` before the final pass. No training or source assets were altered.

[Portable catalog and frame gaps](../evidence/section-library/catalog.json),
[verification ledger](../evidence/section-library/verification.json),
[browser render samples](../evidence/section-library/browser-contact.jpg), and
[mobile pair](../evidence/section-library/mobile-pair.png) preserve the delivery
checkpoint. The three held-out contact sheets in that directory show all 72
legacy outputs. Loading/rendering success does not establish geometry quality.

## Find a splat in the original video

Supply `--video /path/to/original.mp4` to the library server. The original file
is served unchanged, with byte-range support for seeking; it is not cut into
new clips or modified with burned-in labels. The player shows the current time
and every splat whose section range contains that time. Intervals outside all
ranges explicitly show “No reconstructed section”. A range can still contain
unregistered frames; this indicates related footage, not exact camera recovery.

Splat numbers #01–#72 follow the fixed catalog order, including overlapping
alternatives. The same numbers appear on cards, selection menus, video overlays
and editor section labels. Watch buttons and the Jump to splat menu seek to the
section start. Links such as `/?t=414.562967&section=SECTION_ID#source` reopen that
part of the original video. The editor's “Watch source video” link opens it in a
new tab, preserving unsaved editor changes. On browsers that support container
fullscreen, “Fullscreen with numbers” retains the overlay; inline playback is
available on phones. Native video-only fullscreen may omit HTML overlays.

Verification for this change is limited to unchanged source bytes and HTTP
seeking, overlap/gap timestamp mapping, all 72 number mappings, live playback and
jump controls, editor-to-video links, mobile layout, and unchanged saved pair
projects. Existing 72-splat rendering evidence is reused; reconstruction and
masking are unchanged.
