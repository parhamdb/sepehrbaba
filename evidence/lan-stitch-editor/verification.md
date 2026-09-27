# LAN stitching editor verification

Product source: `28af641` (2026-09-27). Locked PlayCanvas 2.22.3; Node 24.11.1; existing Chromium via Playwright. Standalone bundle from `scripts/build-stitch-editor.mjs`. Temporary loopback server; no persistent deployment started by this check.

Final focused command: `node tests/stitch-editor-check.mjs` — **passed**. Counts: **9 passed, 0 failed, 0 blocked, 0 untested** within the editor inventory.

| ID | Required behavior | Result / evidence |
|---|---|---|
| E1 | Render two actual Gaussian scenes | Passed; existing 226,293-splat pilot loaded as two independently transformable entities; 53,312 colored image pixels; rendered screenshot visually inspected |
| E2 | Translate, rotate, uniformly scale selected section | Passed; XYZ transform state with Y=25°, X position=0.3, scale=1.1 |
| E3 | Locked reference preserved | Passed; earlier transform unchanged, locked section's transform inputs disabled |
| E4 | Camera navigation independent of placements | Passed; mouse orbit changed camera yaw and left both section transforms unchanged |
| E5 | Visibility and section controls | Passed; solo/show-all, previous/next and reset selected placement |
| E6 | Persist and extend project | Passed; browser reload, server restart and appending a third manifest section preserved earlier saved transforms |
| E7 | Prevent accidental stale/cross-origin saves | Passed; stale revision returns 409, cross-origin write returns 403 |
| E8 | Original Gaussian bytes unchanged | Passed; source PLY SHA-256 identical before/after |
| E9 | Browser runtime | Passed; no browser exceptions |

Discovery found continuous software-WebGL rendering could prevent screenshot completion. The editor now uses PlayCanvas's documented `frame:request` event with on-demand rendering, and explicitly requests redraws for transforms, camera changes and viewport changes. The subsequent rendered image was inspected and showed actual Gaussian surfaces.

A test assertion initially queried `isDisabled()` on a fieldset. A narrow Chromium reproducer showed Playwright reports false for a disabled fieldset while correctly reporting true for its disabled input. The check was corrected to inspect the actual transform input. This was a verifier issue; the lock implementation did not need changing. The final complete focused pass ran after product commit `28af641` and passed.

Screenshot: ignored build output `dist/stitch-editor/test-render.png`. Test uses the same real pilot PLY twice to verify independent placement without claiming that two different reconstructions match. Cleaning/masking quality, final full-section assets and the eventual manual alignment are separate reconstruction acceptance checks owned by the surrounding workflow. This result proves editor operation, not an evidentiary scene connection.

Independent review found one save race: a newer edit made while a prior save was
awaiting acknowledgment could lose its dirty warning. The save handler now captures
the submitted project and only clears dirty state when the current project still
matches it. Concurrent save clicks are disabled during the request. Focused browser
regression `node tests/stitch-save-race-check.mjs` delayed the acknowledgment,
confirmed the newer edit stayed unsaved, then saved it separately and checked server
state. Passed on the corrected source. Existing unchanged editor checks retained;
final actual-cleaned-scene LAN verification belongs to the cleanup campaign.
