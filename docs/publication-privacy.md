# Publication privacy check — September 25, 2026

Scope: the public repository's 55 tracked files before this change, all 95 text
blob versions reachable through its local Git refs, commit identity metadata,
the reconstruction package, and the metadata/header portions of large assets.
Private work directories and the separate reconstruction host are not publication
inputs. No GPU job was modified for this audit.

## Findings and changes

- Pattern checks found no private network addresses, personal home-directory
  paths, recognizable private keys/access tokens, embedded URL credentials, or
  quoted secret assignments in the checked source and history. Candidate email
  matches in source were matrix operations; matches in binary numeric camera
  data were not email fields.
- Commit authors match the owner's public GitHub profile. All recorded author
  and committer emails use GitHub noreply addresses. Public repository URLs and
  ordinary public attribution are intentional.
- The accepted pilot archive contained build-host ownership labels. Its current
  version now uses zero owner/group IDs, empty owner/group names, and normalized
  tar/gzip timestamps. All 268 members were preserved; individual file hashes
  match the prior package. The package hash and size were updated in its README,
  checksum file, and reconstruction manifest.
- The source MP4 and published PLY were not changed. The project intentionally
  preserves this video and its derived scene; source-media metadata is separate
  from build-host metadata. The already sanitized training manifest contains no
  machine paths.
- Ignore rules now also cover common private credential/key files, SSH/cloud
  configuration folders, logs, databases, and a private working directory.
  Contributor instructions require inspection of staged changes and archive
  metadata before publication.

## Limits

This is a targeted source/history and archive audit, not a guarantee that every
possible secret format can be recognized. Ignore rules can be bypassed and do
not remove previously tracked material. The history scope is refs present in
the local checkout; it does not cover other repositories, issues, messages,
forks, caches, or unreachable server-side objects.

No history rewrite was performed. Earlier LFS package revisions still carry the
old build-host ownership metadata; no credentials or private network addresses
were found there. If sensitive material is discovered later, removing it from a
new commit alone is insufficient: assess credential revocation and historical
cleanup separately.
