# Post-training cleanup experiment — 2026-09-25

**Decision: keep the published model unchanged.** Three conservative filters of
the trained Gaussians did not produce a clear reduction in the principal ghost
artifacts. No retraining or new scene deployment was performed.

## What was tested

All candidates started from the accepted 226,293-Gaussian PLY, SHA-256
`75a8950883fbc87bb88b0002763be6bb94d9edabc9fa2a328542c81acb44a622`.
Every retained Gaussian record remained byte-for-byte identical. Removed records
and their original indices were saved separately, making each removal inspectable.

| Candidate | Removal rule | Removed | Change in static PSNR on three training views |
| --- | --- | ---: | ---: |
| Strict needles | Longest axis > 0.3 model units; longest / second-longest > 30 | 190 (0.084%) | -0.0065 dB |
| Broader needles | Longest axis > 0.3; longest / second-longest > 10 | 1,978 (0.874%) | -0.0285 dB |
| Isolated haze | Longest axis > 0.3; opacity < 0.1; mean distance to eight neighbours above the scene's 95th percentile | 3,074 (1.358%) | -0.0970 dB |

The needle test uses the two largest axes. A large longest-to-shortest ratio alone
also selects legitimate flat surface Gaussians. These thresholds are diagnostic
choices for this model's arbitrary scale, not general ghost-detection settings.

## Inspection and limitations

The three training views were `frame_003139`, `frame_003140`, and `frame_003269`.
The first two inspect adjacent views of the entry region; the third checks another
part of the interval. Source-view renders used PlayCanvas at 532×946 with the same
camera poses and renderer settings for every variant. Baseline static PSNR in
this comparison was 22.1404 dB. This is **not** the native-resolution, 26-view Brush
held-out metric and must not be compared numerically with that earlier result.

Initial renderer calibration was rejected because default sorting and gamma
settings did not reproduce the baseline appearance. Radial sorting, gamma output,
antialiasing, contribution cutoff, and alpha clipping were then matched to the
viewer before candidate evaluation. Rejected calibration renders were retained
separately and excluded from the reported comparison.

All three candidates were also inspected at the same four viewer positions:
authored entry, 0.3 model units left and right, and 0.6 backward. All twelve renders
loaded without page errors. Ghost regions and protected floor/fabric regions were
identified before inspecting candidate results. Changes were subtle; the dominant
peripheral streaks and smearing remained, without a clear overall visual gain.

No candidate was selected for publication. The 26-view held-out check and final
deployment validation were therefore blocked by the failed visual gate, not
reported as passing. No further threshold tuning was performed.

This experiment tests geometric/opacity heuristics with multi-view inspection.
It does **not** implement per-Gaussian visibility scoring, source-guided removal
scoring, semantic segmentation, or learned ghost classification. Those remain
distinct approaches; these negative results do not establish that post-training
cleanup cannot work.

## Reproducing candidate export

`scripts/prune_splat_candidates.py` requires Python and NumPy. The isolated-haze
mode additionally requires SciPy. It accepts standard binary little-endian 3DGS
PLY files with float vertex properties and refuses existing output paths.

```sh
python3 scripts/prune_splat_candidates.py input.ply candidates/needle.ply \
  --min-length 0.3 --min-axis-ratio 30
python3 scripts/prune_splat_candidates.py input.ply candidates/haze.ply \
  --mode isolated-haze --min-length 0.3 --max-opacity 0.1 \
  --isolation-percentile 95
```

Each command writes the candidate, a `-removed.ply` containing excluded records,
and a JSON report with indices and hashes. The default removal limit is 2%; an
empty selection or an exceeded limit stops export. A successful export is only
an integrity check. The report marks visual quality as unaccepted until a separate
comparison establishes an improvement.
