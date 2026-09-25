# Full-recording experiment — September 25, 2026

Requested outcome: run the existing method over the complete **0–737.301333 s**
recording and inspect what it can recover. Preserve the published 18-second
pilot and all earlier runs. A full input interval is not a claim of full recovered
coverage. New reconstruction algorithms, parameter searches, synthetic filling,
and replacing the accepted public scene are outside this experiment.

## Frozen input and method

- Source SHA-256: `9f4e121a4d89afdd5dd8b958070203b4c8247e6792f92031f149400931add02a`.
- Reuse all **12,793** native 1080 × 1920 frames and timestamps, plus retained
  features. All image, keypoint and descriptor database inventories have 12,793
  entries. No extraction or feature computation is repeated.
- The initial full-recording attempt copied the one-minute expansion database
  and started from its complete 452-camera snapshot.
- The unlimited continuation reuses the completed full-recording matching and
  starts from the new **602-camera** snapshot, `1790350962541`. Earlier runs
  remain preserved.
- Use the existing reconstruction algorithm in `scripts/repair_scene.py`: explicit keyframe-neighbor
  matching, all native frames eligible for registration, one seeded component,
  four mapper threads, global refinement growth ratio 1.5, and native-size
  undistortion. Disconnected regions are not forcibly joined.
- **No elapsed-time limit**, as explicitly requested by the project owner.
  `--max-seconds 0` disables the script timer; the dedicated systemd user unit
  also has `RuntimeMaxSec=infinity`. Retain snapshots every 50 registered
  cameras. Protection below 4 GiB available memory remains enabled.
  The initial timed launch is retained; continuation uses its latest complete
  snapshot and already matched database. No extraction or feature recomputation.

## Reproduce with retained inputs

Set these paths to your local retained inputs and a fresh output directory:

```sh
python3 scripts/repair_scene.py \
  --source-run /path/to/full-video-native \
  --database /path/to/initial-full-recording/database.db \
  --seed-model /path/to/initial-full-recording/snapshots/1790350962541 \
  --work /path/to/full-recording-experiment \
  --colmap /path/to/cuda-colmap \
  --start 0 --end 737.301333 --max-seconds 0
```

The seed and match database are retained runtime artifacts; they are not part
of a fresh clone. The [method](method.md) describes preparation and the archived
pilot inputs. Preserve the script revision and hashes with each run.

The command stops before training. If geometry clears the existing checks,
inspect person masks and train with the pilot settings: Brush 0.3.0, 8,000 steps,
1920-pixel maximum edge, at most 500,000 Gaussians, every tenth view held out.
If it fails, record actual coverage and residuals before deciding whether a
clearly labeled partial diagnostic preview is useful. No failed geometry is
silently promoted as the full recording.

## Acceptance and monitoring

| ID | Check | Observed status |
| --- | --- | --- |
| F1 | Source hash and all-frame feature inventory match the preserved recording | Passed on Thor |
| F2 | Geometry attempt produces a measured coverage/quality result, or a documented stop with retained snapshots | Passed: retained refined model and measured quality report |
| F3 | Geometry passes existing thresholds; undistorted images and inspected masks match recovered cameras | Failed: 8.1% coverage, extreme mean residual, six observations behind cameras |
| F4 | A separate trained PLY, held-out comparisons, and browser inspection provide a usable experimental result | Blocked by F3 |
| F5 | User can open a separately labeled candidate with accurate coverage and limitations | Blocked by F4 |

The existing geometry thresholds remain: at least 90% of selected frames in one
model, at least 1,000 points, mean residual ≤1.5 px, p95 ≤3.5 px, and no associated
observations behind cameras. Coverage failure and visual quality are different
findings; report both when available.

Validation budget: one discovery run, only necessary focused failure checks,
and one final candidate inspection if all prerequisites pass. Active supervision
is bounded to 45 minutes per turn; a healthy detached run may continue with its
unit and log handed off; the explicitly authorized long-running computation
has no time deadline. Do not restart completed stages to obtain
another progress reading.

Runtime evidence: `state.json`, `logs/match.log`, `logs/map.log`, `snapshots/`,
and, if reached, `quality.json`. Mapper messages report in-memory registration;
only completed model files establish retained camera counts. There is no
completion ETA yet: mapping may converge on only part of the recording despite
all frames being eligible. Do not stop a healthy run merely because two hours
have elapsed.

## Unlimited continuation

Frozen code: `82eda825480acc64a3cc3fcbff85842593c3363a`.
The original unit was stopped cleanly after preserving its completed matching
and camera snapshots. The continuation is a separate run:

- Work directory name: `full-recording-unlimited-20260925` on Thor.
- User service: `sepehr-full-recording-unlimited-20260925.service`.
- Script option: `--max-seconds 0`; systemd runtime: `infinity`.
- Source interval: 0–737.301333 seconds, all 12,793 frames eligible.
- The published pilot remains unchanged. No full-recording PLY exists yet.

```sh
systemctl --user status sepehr-full-recording-unlimited-20260925.service
# Inside the work directory:
tail -n 20 logs/map.log
cat state.json
```

The detached process stopped at the geometry gate. The source hash and
runtime command are retained in `launch.json`; the prior run points to this
continuation in `continuation.json`.

## Observed result — September 25, 2026

The unlimited run completed mapping and refinement after approximately 90 minutes,
then exited at the geometry gate around 17:14 UTC. This was **not a timeout**.
No reconstruction process remained active when checked at 18:01 UTC.

- Matching, mapping, bundle adjustment and model conversion completed.
- The retained refined model has **1,041 cameras / 12,793 source frames (8.14%)**,
  spanning 186.2622–256.992944 seconds, approximately **03:06–04:17**.
  This span does not imply that every frame within it registered.
- There are **346,215 sparse points**. The measured p95 reprojection residual is
  2.4685 px, but the reported mean is approximately **2.27 × 10^17 px**, and six
  associated observations lie behind their cameras. The extreme mean needs
  diagnosis; the p95 alone cannot establish acceptable geometry.
- Undistortion, masks, Gaussian training and a new browser candidate did not run.
  The accepted 18-second public scene remains the only published model.

Acceptance inventory: **2 passed, 1 failed, 2 blocked, 0 untested**. F2 passing
means the experiment produced its measured result, not that full reconstruction
succeeded. No final candidate acceptance pass was possible.

The earlier 12–24-hour estimate assumed continued registration. That assumption
was not borne out: the mapper finished with limited coverage. More waiting on
this completed run cannot recover additional cameras. Retain its matched database,
`refined/`, snapshots and `quality.json` for diagnosis of camera connectivity and
the extreme projection residuals before attempting another trained candidate.
