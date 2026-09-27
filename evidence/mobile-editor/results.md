# Mobile stitching editor acceptance

Scope: usable mobile placement and camera controls in the existing LAN editor.
Reconstruction, masks, scene assets and saved user alignment are outside this fix.
Environment: Node 24.11.1, Playwright Chromium with software WebGL, isolated test
projects. Real cleaned scenes are also inspected through read-only LAN requests.

Budget: one discovery pass, focused failure checks, one final pass after freezing
product source. No model training, full site build or server restart is needed.

| Acceptance | Discovery | Final |
| --- | --- | --- |
| Phone placement controls, locked reference, isolated save/reload | passed | passed |
| Touch orbit, pan, pinch and lifting one finger | passed after input timing fix | passed |
| Portrait, landscape, narrow phone, tablet, desktop, panel collapse | passed | passed |
| No mobile browser exceptions | passed | passed |
| Existing desktop editor integration (9 checks) | passed | passed |
| Edits during a pending save stay dirty | passed | passed |
| Deployed cleaned scenes load on phone; live saved state untouched | untested | passed |

Discovery: 6 passed, 0 failed, 0 blocked, 1 untested. The first touch-pan assertion
read the camera before queued input was processed. Waiting two animation frames
after dispatched touch input made the focused gesture check pass; no production
change was needed. Independent read-only code review found no medium/high
acceptance violations. Screenshots inspected separately from automated bounds
checks. Physical-device performance and Safari are not verified by these tests.


Final validation on product commit `715ae31`: **7 passed, 0 failed, 0 blocked,
0 untested**. Mobile touch and layout checks, existing desktop integration and
save-race regression all passed. The deployed LAN page loaded both cleaned
scenes in portrait and landscape, with canvas and placement/save controls inside
the viewport and no browser errors. The browser blocked every write request;
the server project/revision and saved-file SHA-256 remained unchanged. The
existing service stayed running with the same process. Live phone screenshots
were inspected. This completes the mobile usability scope under browser emulation.

Served build hashes (verified equal to the frozen local build):

- HTML: `ecaa0a55a51e3b69e2aaa33d4c8bea5364684e5eb2e094afd5bd310c79c580c5`
- JavaScript: `c600f55838bbeeeace13d58833deee2fc0746b1d44404b79e50181bbd6aa781a`

Machine-readable results: [mobile](mobile-final.json),
[desktop](desktop-final.json), [live deployment](live-final.json).
The pending-save regression reported: `PASS: in-flight edits remain unsaved
until separately persisted`.
