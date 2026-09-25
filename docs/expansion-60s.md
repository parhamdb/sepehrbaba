# One-minute coverage experiment

Authorized scope: expand the same reconstruction from **199–217 s** to
**180–240 s**, preserving the published 18-second pilot as the baseline. Do not
change transient masking or training method at the same time. This experiment
does not reconstruct the full 12:17 recording.

## Observed first attempt — 2026-09-25

The 900-second attempt stopped during mapper global bundle adjustment. Matching
completed. The log reached **494 registered cameras**, but the latest completed
snapshot contains **452 cameras**, compared with the original 252-camera seed.
These are recovery counts, not accepted geometry or expanded published coverage.
No final reprojection assessment, undistortion, mask generation, training or
publication followed the stop.

Runtime record: `expansion-180-240-20260925/state.json`; latest retained snapshot
`snapshots/1790348186087`. The original pilot and match database were preserved.
Source was frozen at `347f633` for the launch. The current site still shows
199–217 seconds.

Acceptance status: **0 passed, 0 failed, 5 blocked, 0 untested** (E1 blocked by
the bounded mapper stop; E2–E5 depend on it). Matching is a passed substep, not
an accepted end-to-end geometry result. No final regression pass was run.

Smallest resumption: inspect and reuse the retained 452-camera snapshot with the
existing copied database in a separately budgeted continuation. Do not replay
frame extraction/features, claim the unsaved 494-camera in-memory state was
retained, or assume a mapper snapshot is an optimizer checkpoint.

## Frozen geometry checkpoint

The native-frame inventory contains **903 frames** in this minute, from
`frame_002714.jpg` at 180.001156 s to `frame_003616.jpg` at 239.994556 s.
The accepted pilot supplies 252 seed cameras. Reuse the retained all-frame
features and copy the pilot's match database; never write into the baseline run.

Script: `scripts/repair_scene.py`, SHA-256
`8c9b0de205e96bb773f9946c00b096cd71c411aba1c2a5c839e1265807be82e1`.
COLMAP 3.12.6 with CUDA. New output directory; one bounded 900-second geometry
attempt. Preserve snapshots and logs if it reaches its limit. Do not silently
restart mapping or lower the quality thresholds.

```sh
python3 scripts/repair_scene.py \
  --source-run /path/to/full-video-native \
  --database /path/to/pilot-continued/database.db \
  --seed-model /path/to/pilot-continued/refined \
  --work /path/to/expansion-180-240 \
  --colmap /path/to/colmap --start 180 --end 240 --max-seconds 900
```

Acceptance inventory, before execution:

| ID | Required result | Initial status |
| --- | --- | --- |
| E1 | One model registers at least 90% of the 903 frames, with at least 1,000 points, mean residual ≤1.5 px, p95 ≤3.5 px, and zero associated observations behind cameras | Untested |
| E2 | Undistorted images and inspected person masks cover the accepted model | Blocked by E1 |
| E3 | Separate candidate trains and exports with held-out evaluation images | Blocked by E2 |
| E4 | Browser inspection shows useful additional area and preserves recognizable detail in the original pilot | Blocked by E3 |
| E5 | Held-out source comparisons support promotion; scene asset and coverage labels are published together | Blocked by E4 |

Use one discovery pass, focused failed checks, and one final full acceptance pass
only if the candidate clears the initial gates. At most three distinct hypotheses
for a blocker, within the active-work budget. The authoritative runtime ledger
and `state.json` live beside the new run. Update this document with its observed
result before claiming expanded coverage.

If geometry passes, use the existing mask generator and Brush 0.3.0 at 8,000
steps, maximum edge 1920, every tenth image held out, and cap 500,000 Gaussians.
Hold the method constant for this first coverage comparison; the frame count and
coverage necessarily change. Camera/world coordinates may shift during bundle
adjustment, so align comparisons to shared cameras rather than blindly reusing
the baseline viewer coordinates. Do not compare aggregate PSNR across different
view inventories as evidence of improvement.
