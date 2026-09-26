# Camera recovery at tracking losses

The requested comparison cuts ten seconds before and ten seconds after each
loss onset and gives the same native images and timestamps to each method.
The frozen [inventory](../evidence/camera-loss-benchmark/inventory.json) contains
**19 clips** and the [result ledger](../evidence/camera-loss-benchmark/results.json)
contains **76 method/clip combinations**: motion-masked COLMAP, VGGT-SLAM 2.0,
DA3-Streaming and MASt3R-SLAM. Existing cameras are the retained baseline.

Candidates are contiguous absent-pose runs lasting at least one second. The
union of the camera-review snapshot and all 31 native bootstrap model inventories
contains 4,946 registered source frames. Including the raw models reduces 22
snapshot-only gaps to 19 candidate losses. Raw poses have not all passed geometry
review; their presence does not establish accurate tracking. Absence means no
pose in these supplied inventories, not mathematical impossibility or completion
of the separate full-recording search. The full recording contains 12,793 frames.

Every selected native frame is retained at its original resolution. Solvers may
select internal keyframes; outputs must identify which frames were estimated.
Skipped frames are not interpolated or counted as recovered. The 03:05 break is
`loss-008` (174.862244–194.862244 seconds), our first live trial. Several gaps last
longer than ten seconds: their clips test recovery within the requested window,
and do not contain the eventual baseline return. That distinction is recorded.

## Acceptance and boundaries

1. Clip boundaries, native frame membership and source hashes are verified.
2. Every method/clip combination receives a retained outcome or precise blocker.
3. Report estimated frames and continuity separately from validated recovery.
4. Compare stationary landmarks withheld from camera fitting; inspect complete
   comparison clips for jumps, false connections and moving-object contamination.
5. Commit methods, sanitized results and review artifacts. Protect original
   footage, existing scenes, credentials and private runtime paths.

A continuous predicted path is not sufficient to pass recovery. An executable
failure is distinct from a geometric failure. No benchmark winner is declared
before independent geometric and visual checks. Full-video retraining and public
scene replacement are outside this experiment. RoMa/CoTracker are potential
correspondence frontends, not additional standalone camera solvers in this matrix.

Budget: one discovery pass over the frozen inventory, at most three distinct
remedies for any blocker, and one final verification of accepted artifacts.
Long-running jobs remain supervised with handles and progress. Existing valid
results are retained across turns; the inventory is not regenerated mid-campaign.

## Reproduce clip selection

```sh
python3 scripts/tracking_loss_clips.py \
  --snapshot evidence/camera-review/snapshot.json.gz \
  --extra-registered evidence/camera-loss-benchmark/raw-inventory.json \
  --output NEW_INVENTORY.json --images NATIVE/images --prepare NEW_CLIP_ROOT
python3 -m unittest discover -s tests -p test_tracking_loss_clips.py
```

Prepared directories contain private symlinks to original native JPEGs and
`frames.json` inventories. Do not commit these runtime directories. The public
raw inventory contains image names and model-file hashes only.

SAM 3.1 authentication and gated configuration download succeeded on September
26; the checkpoint was downloaded and its builder imports with the existing
vendor PyTorch. Inference and mask quality remain separate checks. Credentials
are held in private runtime authentication storage, outside this repository.

## First runnable checkpoint — September 26, 2026

[Watch the 03:05 candidate-path diagnostic](https://media.githubusercontent.com/media/parhamdb/sepehrbaba/main/evidence/camera-loss-benchmark/vggt-loss008/preview.mp4).
It contains all **301 source frames** from 174.862244–194.862244 seconds;
VGGT selected **140 keyframes**, built nine submaps and accepted zero loop
closures. The path is an arbitrary projection of local coordinates. Missing
keyframes are explicitly labeled, without interpolation. The video is silent.
[Candidate poses](../evidence/camera-loss-benchmark/vggt-loss008/poses.json)
are available for independent review. This is **not a recovered-camera verdict**.

A one-second contact sheet covering the complete clip was inspected. Coats and
moving visitors obscure much of the scene near the loss. The additional
[image-motion diagnostic](../evidence/camera-loss-benchmark/vggt-loss008/epipolar.json)
tracks corners independently with forward/backward Lucas–Kanade flow and compares
them with epipolar lines from the supplied cameras, without fitting new cameras.
The median of pairwise median residuals is about 3.5 native pixels before the
loss, 8.1 during it, and 5.1 afterward; one pair during the loss reaches about
184 pixels. These corners include moving people. This flags an interval for
inspection; it does not distinguish camera error from object motion and does
not establish a valid cross-gap connection. Full moving-video inspection and
stationary-landmark checks remain outstanding.

The [VGGT execution snapshot](../evidence/camera-loss-benchmark/vggt-progress.json)
records the continuing sequential 19-clip batch. Execution completion and recovery
acceptance are separate fields in the result ledger. The existing full-recording
reconstruction continues independently.

### Reproduction and compatibility

- VGGT-SLAM: `MIT-SPARK/VGGT-SLAM` revision
  `35327ac28b7d193df9ccc39ba6346052bb6f1207`.
  `run_vggt_loss.py` disables the viewer and selects upstream `pad` preprocessing
  to preserve portrait field of view. Model input is 518-square, not native-size
  inference. Native inputs and the exact resize/padding transform are retained.
  Settings: submap 16 plus one overlap, disparity threshold 50 native pixels,
  maximum one loop candidate per submap. The first trial took 58.7 seconds after
  model startup; shared-GPU batch times are longer.
- DA3: `ByteDance-Seed/Depth-Anything-3` revision
  `3d835ec1a5802d64a8b8b15f817a1ab54809bfe4`, checkpoint
  `depth-anything/DA3NESTED-GIANT-LARGE-1.1`. `run_da3_loss.py` uses 32-frame
  chunks, 16-frame overlap, 8-frame loop chunks, torch alignment, CPU FAISS
  retrieval and the supported Python Sim3 optimizer. Upstream default processing
  gives 504×280 portrait inputs. The optional COLMAP-export import is made lazy
  by [this patch](../patches/camera-loss/da3-optional-colmap-export.patch).
- MASt3R-SLAM: `rmurai0610/MASt3R-SLAM` revision
  `e6f4e3d474fad0e11f561482012be864ba8c3f17`.
  [CUDA/PyTorch compatibility patch](../patches/camera-loss/mast3r-cuda13-torch210.patch)
  selects the actual GPU architecture and updates two removed C++ API usages.
  Its native extension built successfully on the third attempt. Complete runtime
  setup and inference are still outstanding, including `lietorch` and retrieval
  dependencies. A successful extension build is not a solver result.
- SAM: `facebookresearch/sam3` revision
  `2345a4ad109ac29c569da749c91d84f10dc08c40`, gated SAM 3.1 weights.
  `sam31_clip_masks.py` is an **experimental, currently blocked adapter**.
  Three smoke attempts exposed (1) an unsupported false state-offload argument,
  (2) an absent torchvision CUDA ROI Align kernel, and (3) a tuple-input error
  in the attempted CPU fallback. No masks passed inference or visual review.
  Do not use its proposals as approved exclusion masks. The third failure is
  retained; further remediation is outside this pass's attempt budget.

All environments use isolated virtual environments with the existing vendor
PyTorch; it was not replaced. Runtime paths, authentication and raw logs remain
private. Patches change compatibility/loading, not learned model weights.

```sh
python3 scripts/run_vggt_loss.py --images CLIP/images --frames CLIP/frames.json \
  --checkpoint VGGT_WEIGHTS --output NEW_TRIAL
python3 scripts/batch_vggt_losses.py --inventory INVENTORY.json --clips CLIPS \
  --adapter scripts/run_vggt_loss.py --checkpoint VGGT_WEIGHTS \
  --python VGGT_ENV/bin/python --output NEW_BATCH
python3 scripts/render_candidate_path.py --frames CLIP/frames.json \
  --poses NEW_TRIAL/poses.json --images CLIP/images \
  --loss-time 184.862244 --output NEW_PREVIEW.mp4
python3 scripts/check_candidate_epipolar.py --poses NEW_TRIAL/poses.json \
  --images CLIP/images --output NEW_DIAGNOSTIC.json
python3 scripts/export_loss_clips.py --inventory INVENTORY.json \
  --video SOURCE.mp4 --output NEW_CLIPS
```

Clip export verifies the source checksum, frame count, native 1080×1920 size and
relative timestamps. Explicit microsecond encoder timing avoids the default
frame-rate timebase rounding observed in the first retained failed export.
Solvers consume the original native JPEGs, not the re-encoded viewing clips.

Validation so far: two inventory unit tests passed; independent read-only review
reproduced all 19 inventories and verified camera/padding conventions; exported
VGGT projections agree to numerical precision. The candidate video decodes to
301 frames at 900×864. Recovery acceptance remains incomplete.
