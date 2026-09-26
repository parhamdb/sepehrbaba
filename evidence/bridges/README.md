# Rejected bridge candidates

These are **failed alignment experiments**, not recovered connections between
the public scenes. See [method and results](../../docs/connecting-scenes.md).

| Archive | Bytes | SHA-256 |
|---|---:|---|
| [RootSIFT + LightGlue candidates](sift-candidates.tar.gz) | 337404 | `7bb00c432667ea39acc5eaec8f2a33d93f766eabc73e91b45df1063d4cefda2b` |
| [Learned descriptors at existing points](learned-at-sift-candidates.tar.gz) | 275617 | `de70a3dfcf4f5532df3df7b20ef02356b74349377c2f11f1e48a35afc259b115` |

Each archive contains `matches.json` and compressed NumPy arrays for each image
pair. The archive preserves the candidate values while normalizing tar ownership,
permissions and timestamps; it contains no private workspace or host metadata.

Extract into a new directory and run:

```sh
python3 scripts/align_component_matches.py "$EXTRACTED_CANDIDATES" "$NEW_REPORT"
```

The reports [SIFT](sift-rejected.json) and
[learned descriptors](learned-at-sift-rejected.json) retain the rejected fits,
all acceptance checks and per-pair statistics. **Do not apply their transforms
to the scene.** The [summary](summary.json) records matching controls and hashes.
The preserved source MP4 and original component models were not modified.
