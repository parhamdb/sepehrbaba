# Selective cleanup and LAN stitching campaign

Acceptance: clean the two complete retained camera components surrounding the
reviewed 06:50–06:55 match, preserve ground bodies and coverings, reconstruct
actual Gaussian scenes, and provide a LAN editor with reversible placement,
scene selection, visibility, uniform scale and durable save/reload.
No full-recording merge, missing-surface generation or certified camera join.

Frozen source baseline: `2574de1`. One discovery pass, focused failure checks,
one final pass. Original source imagery, cameras, masks and scenes are immutable.

| ID | Check | State | Evidence |
|---|---|---|---|
| C1 | Full registered-frame inventory and source preservation | untested | Earlier component: 78 frames, 408.134389–412.230244 s; later: 235 frames, 414.562967–427.800311 s. |
| C2 | Selective masks preserve ground evidence and exclude visible obstructions | untested | Four-frame earlier pilot ran; source and overlays inspected. Full inventory pending. |
| C3 | Both reconstructed Gaussian scenes and held-out render inspection | untested | Existing blanket-person-mask candidates retained as baselines. |
| C4 | LAN editor renders real splats and adjusts only selected section | untested | Implementation underway in isolated worktree. |
| C5 | Save/reload, next section, original bytes unchanged, LAN access | untested | Pending editor runtime. |

Counts: 0 passed, 0 failed, 0 blocked, 5 untested.

The selected spans are complete retained camera components, not complete physical
areas or every raw video frame in those intervals. Registered-frame holes and the
inter-component gap remain explicit. The earlier delivered preview used only
one-second depth clouds; this campaign trains actual Gaussian splats.
