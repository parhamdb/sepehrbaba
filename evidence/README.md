# Preserved source recording

This project reconstructs **this specific recording**, commonly known as
**“Sepehr Baba” / «سپهر بابا … کجایی؟»**, for human-rights documentation,
preservation, and potential future investigations and judicial proceedings.
It is not a generic demonstration dataset. The video contains graphic images
of deceased people and distressed relatives.

**[Download the preserved MP4 (417 MB)](https://media.githubusercontent.com/media/parhamdb/sepehrbaba/main/evidence/source/sepehr-baba.mp4)**

`source/sepehr-baba.mp4` is the exact downloaded platform copy used for the
reconstruction, including its audio. It is tracked through **Git LFS**. It has
not been transcoded, trimmed, enhanced, or replaced during archival ingestion.
“Preserved source” means the acquired file, **not an authenticated original from
the recording device**. Its pre-acquisition editing history is unresolved.

```sh
git lfs install
git clone https://github.com/parhamdb/sepehrbaba.git
cd sepehrbaba
git lfs pull --include='evidence/source/*.mp4'
sha256sum --check evidence/source/SHA256SUMS
```

Expected size: **417,094,424 bytes**. SHA-256:

```text
9f4e121a4d89afdd5dd8b958070203b4c8247e6792f92031f149400931add02a
```

The Git object is an LFS pointer; the corresponding video bytes reside in the
repository's LFS storage. An ordinary source ZIP or a clone without LFS may
contain only the pointer. [GitHub explains this storage model](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage).
The video is outside `public/`, so the Pages build does not bundle it into the
3D viewer or silently load 417 MB when a visitor opens the scene.

The source URL, acquisition limits, metadata and archival event are in
[`source/provenance.json`](source/provenance.json). [`source/ffprobe.json`](source/ffprobe.json)
records the observed container and stream metadata; container timestamps are
not treated as a verified filming date. [Context and provenance research](../docs/provenance.md)
separates reported claims from verified file properties and open questions.
[`reconstruction.json`](reconstruction.json) links the accepted derived PLY to
this source hash and its limited time interval.
The [accepted pilot package](pilot/README.md) preserves recovered cameras,
the actual masks, frame timestamps and image hashes for reproducible analysis.

## Preserve the distinction between source and reconstruction

- Analyze working copies. Never overwrite or “clean up” the preserved MP4.
- Keep decoded frame timestamps, camera registration results, excluded frames,
  masks, commands, tool versions and model hashes for every accepted run.
- The Gaussian scene is a derived visualization. It contains interpolation,
  ghosts, missing surfaces and uncertain geometry; it is not a new camera view
  that was actually recorded. Its scale is not a surveyed metric scale.
- Automatic person masks also exclude some stationary people. They are used
  for environment fitting, never to claim that the removed content was absent.
- Do not infer identities, injury mechanisms, victim counts, individual guilt,
  or a precise chronology from splat geometry. Report such claims only with
  independently attributable evidence.
- Preserve failed experiments. Any future synthetic completion must be separate
  and explicitly identified; it must not be presented as recorded evidence.

These choices follow preservation principles discussed in the
[Berkeley Protocol, paragraphs 167–169](https://digitallibrary.un.org/record/3973652/files/OHCHR_BerkeleyProtocol.pdf?version=1).
They do not certify this repository as protocol-compliant or establish a complete
chain of custody from the camera. A Git commit and hash establish the identity
of archived bytes; they do not by themselves establish authenticity, capture
date, or admissibility. Preserve independently stored backups as well as Git/LFS.

The source media and reconstruction assets are **not granted a new reuse license**
by the project's code licensing. Copyright and any applicable rights remain with
their respective holders. Public preservation does not establish ownership.
