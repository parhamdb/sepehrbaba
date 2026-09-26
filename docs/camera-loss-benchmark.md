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
