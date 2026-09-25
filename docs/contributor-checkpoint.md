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
| C5 | Public viewer description and navigation | Passed: all 3 local tests, then all 3 corrected-URL live tests; purpose/source links and unchanged 18-second coverage verified |
| C6 | Committed contributor handoff | Passed: method/setup/tests/contribution guidance pushed; local documentation links resolved; final record committed separately |

**Final implementation inventory: 6 passed, 0 failed, 0 blocked, 0 untested.**
Runtime source frozen at `98dc444`; method tools at `2f4ce6e`. The
[Pages deployment](https://github.com/parhamdb/sepehrbaba/actions/runs/36152081757)
succeeded. Source archive commit: `17b0f5b`. Subsequent evidence/documentation
commits do not require another viewer build.

Final validation repeated the 10 pipeline, 4 reference/metric and 4 contribution
tests, actual reference preparation, native 26-view evaluation, and one browser
capture. The two fresh-page browser captures were pixel-identical. The first
live navigation invocation omitted the trailing slash from `SITE_URL`, resolving
relative URLs to the account's empty root site and failing all three checks.
Its logs/screenshots were retained; a corrected-URL `--last-failed` rerun passed
the three affected checks. No additional broad pass was run. This was an
invocation error, not evidence that the deployed scene had disappeared.

The public video URL returned HTTP 200 with 417,094,424 bytes. An independent
Git LFS fetch reproduced the source hash. The accepted PLY bytes and scene camera
metadata were unchanged by this delivery. The larger scene is not included in
the six contributor/preservation passes; its separate geometry gate remains blocked.

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
