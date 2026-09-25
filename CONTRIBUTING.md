# Contributing to Sepehr Baba

Help reconstruct **this recording** faithfully and make every accepted result
traceable to its source. Contributions to geometry, camera recovery, masking,
evaluation, source research, Persian transcription, documentation and browser
navigation are welcome. Read the [project purpose and provenance](docs/provenance.md)
and [method](docs/method.md) before changing the reconstruction.

## A useful contribution

1. Open an issue describing a specific observed problem, source-video time range,
   and the affected baseline/model revision. Avoid speculation about identities.
2. Fork the repository and make a focused branch. Preserve the accepted model and
   original video; write experiments to a fresh ignored `work/` or `runs/` directory.
3. Record the input hash, source revision, commands, tool versions, frame inventory,
   train/evaluation split, masks, runtime and output hashes. Keep failed results.
4. Compare the same poses and static source pixels, then inspect nearby navigation
   views. A higher PSNR or smaller model alone does not establish better geometry.
5. Submit a pull request with the problem, method, results, limitations and exact
   reproduction commands. Link large artifacts separately; include small manifests
   and relevant code in Git. State what remains untested or blocked.

For research contributions, cite the original publication and distinguish a
reported claim from independent verification. Preserve correction history.
For transcription, include timecodes, the Persian text, translation, review status
and explicit inaudible/uncertain spans. Do not publish confidential contacts or
new identifying details about witnesses or relatives as part of a code change.

## Checks appropriate to your change

```sh
python3 -m unittest discover -s tests -p 'test_pipeline.py' -v
python3 -m unittest discover -s tests -p 'test_evaluation.py' -v
# Requires torch, NumPy and Pillow:
python3 tests/test_contribution_scoring.py

npm ci
npx playwright install chromium
npm run build
npm test
# Verify a deployed Pages subdirectory with its trailing slash preserved:
SITE_URL=https://parhamdb.github.io/sepehrbaba/ npm test
```

Pipeline/reference tests use synthetic inputs and do not launch GPU training.
Browser tests use the existing scene. Reconstruction changes additionally need
real-source evaluation and visual inspection, as described in the method guide.
Use one discovery pass, focused checks of failures, then one final complete pass
for an accepted change; do not repeatedly rebuild or retrain unchanged layers.

## Source preservation and licensing

The [source MP4](evidence/README.md) is tracked with Git LFS. Do not replace its
contents or add altered audio under the same source identifier. A newly obtained
version needs its own path, checksum, provenance and documented relationship.
Do not add credentials, machine access details, model-weight caches, decoded
frame collections or temporary logs to Git.

Before committing, inspect `git diff --cached` and `git diff --cached --stat`.
Use `/path/to/...` placeholders instead of personal home directories, SSH
accounts, private IP addresses, hostnames, or private service URLs. Keep access
instructions, credentials, raw runtime state and logs in ignored local storage.
Check archive contents as well as their filenames: normalize archive owner/group
IDs and names, remove host paths, and verify that research payloads remain
unchanged. Git ignore rules do not protect already tracked files or forced adds.
Use your public GitHub identity and a GitHub noreply commit email when appropriate.
The [publication privacy audit](docs/publication-privacy.md) records the current
check and its limits.

A permissive license for project-authored code is awaiting the owner's choice.
Until a license is added, do not assume that publication alone grants broad reuse
rights. Third-party licenses remain applicable. The source video and derived
scene are not covered by any future code license unless explicitly stated.

Pull requests do not automatically deploy or replace the accepted scene. A
maintainer promotes an inspected asset and updates its coverage/evidence labels
together. Research candidates stay clearly labeled as candidates.
