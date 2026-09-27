# Manual Gaussian scene stitching on a LAN

This local application loads independently reconstructed Gaussian PLY sections together. Select a section, translate it in XYZ, rotate it around XYZ, and change its uniform scale until shared surfaces agree. The first section starts locked. Camera orbit/pan/zoom is separate from scene transforms. Solo mode follows Previous/Next selection; Show all restores the comparison. Nothing modifies source Gaussian or video files.

A saved placement is an approximate manual alignment, not a verified camera connection. This editor does not mask people, clean geometry, or fill missing surfaces. Inspect the floor and several identifiable stationary features from multiple viewpoints. Bodies, coverings and belongings are part of the documentation and must not be blanket-masked as people.

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
