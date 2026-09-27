# Two selectively cleaned Gaussian sections and a LAN stitching editor

Two complete retained camera components were retrained independently with
reviewed SAM 3.1 proposals and explicit corrections. The original video, original
models and previous Gaussian candidates remain unchanged. These are actual
Gaussian scenes, replacing the one-second depth-cloud diagnostic for this workflow.

| Section | Source interval | Registered images | Held-out views | Retained-pixel PSNR | Training time |
|---|---|---:|---:|---:|---:|
| Earlier | 408.134389–412.230244 s | 78 | 8 | 24.37 dB | 494.7 s |
| Later | 414.562967–427.800311 s | 235 | 24 | 25.78 dB | 541.6 s |

Both ran 8,000 Brush steps at maximum resolution 1920 and maximum 500,000 splats.
The masked static initialization retained 1,890 / 9,976 points, preserving camera
poses. Every registered image was retained in the dataset; every tenth view was
reserved for evaluation. Temporal spans do not establish complete surfaces.

All 313 mask proposals were inspected. Six earlier images and 129 later images
received recorded corrections for partial visitors, foreground hands and shoes.
The sitting-person prompt was rejected after it mislabeled ground clothing.
Ground bodies, coverings and nearby belongings remain visible in the inspected
renders. All 32 held-out renders and the live editor's individual and combined
views were inspected. Prominent targeted obstructions are substantially removed;
source blur, soft shadow-like residuals, uncertain mask edges and peripheral
artifacts remain. This is a usable provisional cleanup, not a perfect reconstruction.

PSNR is measured only on retained pixels. The mask changes prevent a direct
quality-improvement comparison with older blanket-person-mask scores. Neither
these scores nor manual placement certify evidence accuracy or a camera join.

## Use the actual checkpoints locally

```sh
git lfs pull
npm ci
node scripts/build-stitch-editor.mjs
node scripts/stitch-editor-server.mjs \
  --manifest evidence/clean-sections/sections.json \
  --assets evidence/clean-sections \
  --state private/stitch-state --host 0.0.0.0 --port 8092
```

Open the host's LAN address at port 8092. The `private/` state directory is ignored
by Git. Select Later and adjust XYZ position/rotation and uniform scale. The earlier
section starts locked. Solo and Previous/Next switch between sections; Show all
compares them. Save project stores placements on the server; Export JSON keeps a
portable copy. Append further sections with new IDs as described in the
[editor documentation](../../docs/lan-stitch-editor.md).

The initial manifest independently normalizes each component to its selected
source-camera view. It does **not** place the two scenes into an accepted alignment.
The live delivery was reset to those initial transforms after testing. No original
Gaussian positions were baked, welded or deformed, and no unseen surfaces filled.

## Reproduction and verification

- [Selective masking and training method](../../docs/selective-section-cleanup.md)
- [Earlier review decisions](earlier-review.json), [later review decisions](later-review.json)
- [Earlier inputs](earlier-inputs.tar.gz), [later inputs](later-inputs.tar.gz): masks, native/filtered sparse models and source hashes
- [Earlier Gaussian](earlier-clean.ply), [later Gaussian](later-clean.ply)
- [Training and source-preservation receipt](training-receipt.json)
- [Earlier evaluation](earlier-held-out.json), [later evaluation](later-held-out.json)
- [Earlier rendered views](earlier-held-out-renders.jpg); later [1](later-held-out-renders-0.jpg), [2](later-held-out-renders-8.jpg), [3](later-held-out-renders-16.jpg)
- [Actual-scene LAN browser checks](lan-verification.json), [delivery ledger](verification.md)

Final browser verification exercised both new assets, later-only transforms,
reference locking, save/reload, reset, camera orbit and mobile layout. LAN HTTP
access was verified from a second machine. The editor's earlier focused checks
also covered server restart, adding another scene, and original PLY preservation.
An independently identified save race was fixed and its delayed-response regression
passed. No reconstruction, browser test or mask job remains running; the requested
LAN editor remains active. Personal runtime paths and credentials are excluded.
