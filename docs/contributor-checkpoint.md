# Source preservation and contributor checkpoint — 2026-09-25

Scope: preserve this recording in Git LFS, publish attributed provenance and the
project's purpose, make the saved reconstruction/evaluation method usable by
contributors, and attempt the separately documented one-minute geometry expansion.
No new reconstruction method, identity attribution from imagery, synthetic scene
completion, or court-admissibility certification is included.

Budget: one discovery pass, focused failure checks, one final complete acceptance
pass; no more than two viewer builds and no repeated unchanged reconstruction.
The expansion has its own 900-second geometry limit, now reached.

| ID | Check | Status / evidence |
| --- | --- | --- |
| C1 | MP4 tracked and remotely retrievable with identical bytes | Passed: LFS upload and independent empty-cache fetch; SHA-256 `9f4e121a4d89afdd5dd8b958070203b4c8247e6792f92031f149400931add02a`, 417,094,424 bytes |
| C2 | Portable code correctness and CLI checks | Passed: 10 pipeline tests locally, 4 reference/metric tests locally, 4 contribution tests on Thor; shell/Python/JS syntax checks |
| C3 | Actual-source evaluation helpers | Passed: generated 15 training + 26 held-out reference views, reproduced native static PSNR 22.3286210999 dB across all 26 views |
| C4 | Actual browser-engine capture | Passed: frame 3139, stable capture, no page errors; 41.0464 dB agreement with archived browser capture, visually inspected; not bit-identical |
| C5 | Public viewer description and navigation | Untested at this source checkpoint; build passed; browser discovery/final results will be recorded below |
| C6 | Committed contributor handoff | Untested at this source checkpoint; final commit/push and link checks pending |

Initial implementation discovery found that blank COLMAP observation lines were
not portable across NumPy versions. Stripping those lines before parsing fixed
the observed fixture failure. Independent review found that an incomplete
evaluation folder could silently contaminate the training split. Reference export
now checks the complete expected Brush split against the saved training period;
the regression test passes. Neither fix changes the accepted PLY.

The real browser capture is close to the archived capture but not identical.
Fresh-page sorting/capture history remains a renderer comparison limitation;
stable screenshots alone do not prove accurate geometry. Existing failed ghost
cleanup results are preserved, not reclassified as successes.

The archive is a platform download. Original camera file, recording time,
pre-acquisition custody and edit history remain unverified. The
[provenance record](provenance.md) keeps these gaps explicit.

The [one-minute expansion](expansion-60s.md) remains blocked; no larger scene has
been accepted or published. Code licensing remains awaiting the owner's choice;
source-media rights are separate.
