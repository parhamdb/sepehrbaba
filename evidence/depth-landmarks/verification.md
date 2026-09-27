# Delivery verification — depth landmark camera overlay

Scope frozen from the user-approved plan: exact human seeds, verified cached
source/depth mappings, local tracking, depth-aware candidate poses, withheld-view
checks, inspectable overlay and public method. No scene merge, full-video rerun,
new generated scene detail or independent-landmark invention.

Budget: one discovery pass, focused fixes, one final deployed pass. Scientific
failure is a measured result; missing independent scene evidence remains a
scientific blocker, not a passing recovery claim.

| ID | Status | Evidence |
|---|---|---|
| D1 inputs and actual tracking | passed | 42 source hashes/mappings, processed-image pixel comparisons, two 21-frame forward/reverse CoTracker runs; retained provenance. |
| D2 numerical integrity | passed | Known-pose PnP and depth round-trip controls; independent 4×4 reprojection of every retained withheld view; exact human seeds and rejection state. |
| D3 artifact inspection | passed | Both videos have 21 frames, 1280×1120 pixels, 5.25 s duration and recorded hashes. Seed/end overlays were visually inspected; frames decoded from the final MP4s confirm actual encoded content and corrected grey failed tracks. |
| D4 local browser | passed | Both directions, six rows, both movies decode/play/seek, hashes/JSON match, mobile no overflow, no script errors. Passed before final track-quality data update; unchanged UI retained, updated assets require final live pass. |
| D5 independent review | passed | Read-only reviewer checked mapping, upstream common depth/pose scale, C2W transforms and closure; no medium/high issues. |
| D6 final deployed page | passed | Pages run 36302415797 succeeded at c63d453bd4ac2e293dcca550c65f0ceaf73216dc. Live Chromium verified both directions, six rows, both videos decode/play/seek, 1280×1120 and 5.25 s metadata, both video hashes and exact report JSON, mobile no overflow and no script errors. |

Discovery numerical check initially failed at 1e-6 px tolerance. Diagnosis found
cached float32 rotations have <=6.2e-8 orthogonality residual: explicit inverse
versus transpose reprojection differs <=0.0000693 px. Verification now uses an
explicit absolute 0.0001 px tolerance with zero relative tolerance; product
geometry and the 5 px scientific acceptance limit were unchanged. Focused check
passed. The pre-fix log is retained in the private runtime session.

Visual inspection found a forced reverse endpoint could look reliable despite
failing return to its original seed. Reliability now additionally requires the
full trajectory's seed-return/visibility screen. Fits and selected seed points
were unchanged; numerical summaries and overlays were regenerated. No tracker
or depth model rerun was necessary.

Current ledger: 5 passed, 0 failed, 0 blocked, 1 untested delivery check.

Final ledger: **6 passed, 0 failed, 0 blocked, 0 untested delivery checks**.
Accepted publication artifact: `c63d453bd4ac2e293dcca550c65f0ceaf73216dc`.
[Build/deploy receipt](https://github.com/parhamdb/sepehrbaba/actions/runs/36302415797).
The final live pass used the regenerated track-quality data and movies, retaining
unchanged numerical/source verification. The independent reviewer also verified
the full-trajectory correction and inspected its final grey/yellow overlays.
All experiment jobs and browser checks completed. Scientific camera recovery
failed the stated gates and remains blocked on independent static evidence.
This ledger-only commit does not change the deployed artifact.
