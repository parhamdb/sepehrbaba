# Manual Gaussian scene stitching on a LAN

This local application loads independently reconstructed Gaussian PLY sections together. Select a section, translate it in XYZ, rotate it around XYZ, and change its uniform scale until shared surfaces agree. The first section starts locked. Camera orbit/pan/zoom is separate from scene transforms. Solo mode follows Previous/Next selection; Show all restores the comparison. Nothing modifies source Gaussian or video files.

A saved placement is an approximate manual alignment, not a verified camera connection. This editor does not mask people, clean geometry, or fill missing surfaces. Inspect the floor and several identifiable stationary features from multiple viewpoints. Bodies, coverings and belongings are part of the documentation and must not be blanket-masked as people.

For pairwise manual adjustment, expose exactly one earlier section and one later
section. Keep alternative reconstruction versions in a separate comparison setup
or the evidence archive, rather than listing them as additional sections in the
adjustment editor. Back up the manifest and saved state before reducing an
existing scene list; retain the chosen pair's transforms and filter settings.

## Launch

From the repository root, using the existing locked dependencies:

```sh
npm ci
node scripts/build-stitch-editor.mjs
node scripts/stitch-editor-server.mjs \
  --manifest /path/to/local/sections.json \
  --assets /path/to/local/gaussian-files \
  --state /path/to/local/stitch-state \
  --host 0.0.0.0 --port 8092
```

Open `http://<server-LAN-address>:8092` from a browser on the same trusted LAN. Default binding without `--host` is loopback. This is a single shared project for trusted LAN users, with no login; do not expose it publicly. Concurrent stale saves are rejected. Only listed PLY files and the editor assets are served, rather than the surrounding folders. `--web` optionally overrides `dist/stitch-editor`.

For an existing-asset demonstration, use `public/stitch-editor/example-manifest.json` as the manifest and `public/assets` as the asset directory. Those existing scenes are explicitly **uncleaned examples**, not the newly cleaned sections or a claim of an established connection.

## Section manifest

```json
{
  "version": 1,
  "scenes": [
    {
      "id": "earlier",
      "label": "Earlier full section",
      "asset": "earlier.ply",
      "status": "Selective masks reviewed; reconstruction inspection pending",
      "locked": true,
      "transform": {"position": [0, 0, 0], "rotation": [0, 0, 0], "scale": 1}
    },
    {
      "id": "later",
      "label": "Later full section",
      "asset": "later.ply",
      "status": "Selective masks reviewed; reconstruction inspection pending",
      "locked": false,
      "transform": {"position": [0, 0, 0], "rotation": [0, 0, 0], "scale": 1}
    }
  ]
}
```

IDs are unique letters, digits, underscores or hyphens. Asset paths resolve inside the explicitly configured asset directory. Scene labels and status are plain text. Omitted transforms default to identity. An optional top-level `camera` provides `position` and `target` XYZ arrays; otherwise Focus selected frames that section's bounds. Status defaults to “Quality not reviewed. Placement is provisional.”

Coordinate convention matches this repository's SuperSplat viewer: each raw PLY first receives 180° about Z; the section's editable transform is then applied above it. Rotations are PlayCanvas local Euler angles in degrees; translations use the section world coordinates; scale is positive and uniform. Rotation and scaling pivot at the section origin, not the camera. Independent reconstructions may have unrelated origins, scale and floor orientation. Use Focus selected if the second section starts outside the view.

Save writes `<state>/project.json` atomically. Reload saved discards local unsaved edits after confirmation. Export JSON downloads a portable placement file; Import validates scene IDs/assets/transforms before applying it, then Save persists it. Source PLY files are read-only. Reset this placement restores that section's original manifest transform, not the last save. Lock placement prevents transform edits; unlocking the reference is an explicit checkbox action.

## Attach further sections

Save first. Add a new scene with a new stable ID and PLY filename to the manifest, then restart the server and reload the browser. Existing saved transforms are retained; newly listed sections receive their manifest transforms. Do not reuse an existing ID/asset name for a different reconstruction. Keep a new manifest and state directory for replacement assets to preserve provenance. Removed or renamed saved assets fail startup rather than silently dropping previous work.

Lock completed sections, select the new section and place it against the existing area. This constructs one shared coordinate system while retaining each independent Gaussian source and reversible transform. The editor renders them together; it does not deduplicate overlapping splats or export a fused PLY.

## Focused verification

```sh
node scripts/build-stitch-editor.mjs
node tests/stitch-editor-check.mjs
```

The check starts an ephemeral loopback server and Chromium, renders two actual Gaussian assets, exercises transforms and independent camera orbit, reference locking, visibility, previous/next, reset, save and reload, server restart persistence, and verifies the original PLY SHA-256 is unchanged. It checks stale and cross-origin save rejection and browser exceptions. `STITCH_TEST_ASSETS` can specify another directory containing `preview.ply`. Test screenshot is `dist/stitch-editor/test-render.png` (ignored build output). It uses the existing pilot twice to test independent entity transforms without inventing a synthetic reconstruction; final cleaned-section quality requires separate visual inspection.

Validation budget for this delivery: one focused discovery, corrections at observed failures only, then one final focused pass on frozen source. No whole reconstruction or repository suite is required for this standalone editor.

## Optional seed-camera starting view

For this recording, the two sections can start in their selected seed-camera
views instead of unrelated COLMAP origins. This is a display convenience, not
registration: each seed camera maps independently to the origin looking along
+Z, and each seed's median positive sparse-point depth becomes one unit.

```sh
python scripts/stitch_seed_views.py \
  --section earlier EARLIER_MODEL_TEXT frame_006454.jpg \
  --section later LATER_MODEL_TEXT frame_006548.jpg --output SEED_VIEWS.json
node scripts/stitch_manifest.mjs SEED_VIEWS.json sections.json
```

The manifest expects `earlier-clean.ply` and `later-clean.ply`; edit labels/status
as needed before launch. The exporter checks camera-origin and view-direction
mapping, preserves source model hashes, and verifies the matrix-to-Euler roundtrip.
The initial nonzero rotations/scales are these independent camera gauges. Users
still need to align the scenes; resetting restores this starting view.

## Phone and tablet controls

On phones, the scene stays above a compact control panel; landscape phones place
controls beside the scene. Select **Move**, **Rotate**, or **Scale** to adjust one
kind of placement at a time. Buttons have at least 44-pixel touch targets. **More**
contains lock/visibility, Solo/Show all, Focus/Top view, reset and import/export.
The section selector and **Save** remain accessible while the panel scrolls.
**Hide** expands the scene; **Controls** brings the panel back.

Drag with one finger to orbit the camera. Use two fingers to pan and pinch to
zoom. These gestures change the viewing camera only; use the placement controls
to move the selected section. Desktop mouse controls remain available.

Mobile regression check (isolated temporary project, never the live LAN state):

```sh
node tests/stitch-mobile-check.mjs
node tests/stitch-save-race-check.mjs
```

The mobile check uses Chromium touch emulation with real browser touch events,
phone portrait/landscape, narrow phone, tablet and desktop sizes. It checks
placement/save/reload, locking, pan/pinch/orbit and finger release, visible
controls, panel collapse and browser errors. Screenshots are written under
`dist/stitch-editor/mobile-check/`. This is browser emulation, not a physical
phone performance or Safari compatibility claim. `STITCH_TEST_WEB` selects a
staged web build for all three editor checks; `STITCH_MOBILE_ONLY` selects one
named mobile check when diagnosing an observed failure.

## Independent section inspection

Open **Filters** on a phone (the inspection panel is always present on desktop).
The three filter inputs appear first, with no section-list scrolling required.
Scroll below them to **Show / hide sections**. Each section has a Show checkbox and an **Only** button. Only also selects that
section for editing. Switching sections while soloing follows the selection;
manually changing a Show checkbox exits solo mode. **Show all sections** restores
the comparison without changing placement.

Select a section in the top selector to adjust its three independent filters:

- **Minimum opacity:** hide splats below this opacity. Start near 0.05 and compare
  the original; opacity measures transparency, not geometric confidence.
- **Max size × median:** hide splats whose largest axis exceeds this multiple of
  that section's median largest axis. Zero disables the limit.
- **Max ray axis ratio:** hide splats with a largest-to-middle-axis ratio above
  the limit, but only if larger than the section's median. Zero disables it.
  Using the middle axis avoids treating every flat surface as a needle.

**Try ray filter** sets the ratio limit to 10 and leaves the other thresholds
unchanged. **Reset filters** disables all three for the selected section.
**Preview original** temporarily bypasses that section's filters without losing
its settings. Original preview is not saved; the underlying settings are.
The hidden-count estimate and viewport indicator make filtering visible.

Settings belong to each section. **Save**, **Reload saved**, and JSON export/import
include them. Legacy projects/imports without filter settings use all filters off.
Placement locks protect alignment, while still allowing visibility and filter
adjustments. Thresholds use original local Gaussian dimensions, so moving,
rotating or scaling a section does not change which splats match the filters.
Sources are read-only: these are renderer exclusions, not a modified PLY export.

This first interactive filter set does **not** include SplatTransform's GPU
voxel-floater/connected-cluster processing, identify moving people, or establish
that excluded splats are errors. Real bodies, coverings, belongings and floor
surfaces can be hidden by these heuristics. Compare each section alone from
multiple viewpoints before using filtered views for alignment. Strong thresholds
can hide everything; Reset filters and Show all recover the scene.

Implementation uses per-component work-buffer modifiers in the pinned PlayCanvas
version; see [the official modifier documentation](https://developer.playcanvas.com/user-manual/gaussian-splatting/rendering-architecture/work-buffer-format/).
Counts are estimated from the original CPU values; GPU half-float rounding can
change classifications very near a threshold. All three conditions are combined
with OR. No source opacity, scale, position, or other Gaussian property is edited.

```sh
node scripts/build-stitch-editor.mjs
node tests/stitch-filters-check.mjs
```

The filter check uses both actual cleaned sections in isolated temporary state.
It compares rendered image hashes (excluding status overlays), checks independent
visibility/filtering, each filter's rendered effect, Original/reset restoration,
locked alignment, save/reload and export/import, server restart, invalid settings,
phone control access and unchanged source hashes. Run browser checks sequentially
on constrained hosts. `STITCH_FILTER_ONLY` selects a named check for failure-only
reruns. Images are retained under `dist/stitch-editor/filter-check/`.

### Live filter sliders

The **Filters** tab puts all three sliders and numeric fields first. Dragging a
slider immediately updates the selected section; the numeric field shows its
current threshold. Visible endpoints are 0–1 for opacity, 0–50× median for size,
and 0–100 for ray axis ratio. Zero disables that filter. Use the numeric box for
precise or larger values. Entering a larger value expands the slider range; that
range stays steady while dragging and is reset by **Reset filters**.

The section list follows the filters. On small phones the panel uses more height
while Filters is selected, keeping all three controls visible without scrolling
and retaining a scene view. Filter algorithms, source files and project storage
are unchanged by the slider UI.

`node tests/stitch-filter-access-check.mjs` checks immediate visibility without
scrolling at four screen sizes, touch interaction, numeric/slider synchronization,
stable expanded maxima and independent section state. `STITCH_TEST_WEB` starts an
isolated server against a staged build; otherwise `STITCH_TEST_URL` selects an
existing editor, defaulting to loopback port 8092. All project writes are blocked.

## Reversible section cropping

Open **Crop** on a phone, or **Crop selected section** on desktop. The selector
still contains one earlier/later pair. Cropping starts disabled for older projects.
Enable it and slide each axis's **start** and **end** boundary, or enter exact
values. A green wire box shows the kept region. **Central 98%** offers a starting
box from the middle 98% of splat centers on each axis, with a small margin; it is
not a confidence estimate. Keep overlap landmarks until the sections are aligned.

Each crop uses the original section's local coordinates and follows its move,
rotation and uniform scale. The six limits and **Edge fade** are saved per section
with placements, and included in JSON export/import. Fade is a percentage of the
smallest crop-box dimension. **Reset crop** removes cropping; **Preview original**
in Filters temporarily bypasses both filters and cropping. **Show crop boxes** is
an unsaved display preference. Source PLY files remain unchanged.

Cropping clips fragments at their rendered camera-facing Gaussian billboard
positions, so a long splat can be trimmed even when its center remains inside.
This preserves unified cross-section sorting. It is a visual clipping operation,
not volumetric Gaussian intersection, mesh reconstruction, or a repair of depth.
Different viewpoints can still reveal holes or bad geometry. Bounds do not define
verified surfaces; edge fade does not establish correspondence between sections.

Focused validation uses a known elongated splat to verify partial clipping,
transformed boundaries, fade and bypass, then both actual reconstruction assets
for phone controls and preservation checks:

```sh
node tests/stitch-crop-check.mjs
```

The test uses an isolated temporary project. It retains screenshots and results
outside the checkout, including failures; it never writes the live placements.
`CROP_ONLY=C4` selects a previously failed check without repeating passing ones.

[Crop verification and rendered examples](../evidence/crop-editor/verification.json)
record the tested source and bundle. The live LAN editor runs as an enabled user
service with failure restart; runtime paths and placement backups stay private.
