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
- Copy the database retained by the one-minute expansion into a fresh run.
- Start from its latest complete **452-camera** snapshot, not the unsaved
  494-camera count from the interrupted mapper log.
- Use the unchanged `scripts/repair_scene.py`: explicit keyframe-neighbor
  matching, all native frames eligible for registration, one seeded component,
  four mapper threads, global refinement growth ratio 1.5, and native-size
  undistortion. Disconnected regions are not forcibly joined.
- Give this single geometry attempt **7,200 seconds**. Retain snapshots every
  50 registered cameras. Existing protection stops below 4 GiB available memory.
  A dedicated systemd user unit contains the job and its children, with a
  7,800-second outer runtime cap. No automatic retries.

## Reproduce with retained inputs

Set these paths to your local retained inputs and a fresh output directory:

```sh
python3 scripts/repair_scene.py \
  --source-run /path/to/full-video-native \
  --database /path/to/expansion-180-240/database.db \
  --seed-model /path/to/expansion-180-240/snapshots/1790348186087 \
  --work /path/to/full-recording-experiment \
  --colmap /path/to/cuda-colmap \
  --start 0 --end 737.301333 --max-seconds 7200
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

| ID | Check | Launch status |
| --- | --- | --- |
| F1 | Source hash and all-frame feature inventory match the preserved recording | Passed on Thor |
| F2 | Geometry attempt produces a measured coverage/quality result, or a documented stop with retained snapshots | Untested |
| F3 | Geometry passes existing thresholds; undistorted images and inspected masks match recovered cameras | Blocked by F2 |
| F4 | A separate trained PLY, held-out comparisons, and browser inspection provide a usable experimental result | Blocked by F3 |
| F5 | User can open a separately labeled candidate with accurate coverage and limitations | Blocked by F4 |

The existing geometry thresholds remain: at least 90% of selected frames in one
model, at least 1,000 points, mean residual ≤1.5 px, p95 ≤3.5 px, and no associated
observations behind cameras. Coverage failure and visual quality are different
findings; report both when available.

Validation budget: one discovery run, only necessary focused failure checks,
and one final candidate inspection if all prerequisites pass. Active supervision
is bounded to 45 minutes per turn; a healthy detached run may continue with its
unit, log, and deadline handed off. Do not restart completed stages to obtain
another progress reading.

Runtime evidence: `state.json`, `logs/match.log`, `logs/map.log`, `snapshots/`,
and, if reached, `quality.json`. Mapper messages report in-memory registration;
only completed model files establish retained camera counts. A two-hour budget
is a stop deadline, not an estimate that a complete 3D scene will exist then.
