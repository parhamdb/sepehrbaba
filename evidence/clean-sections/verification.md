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
| C1 | Full registered-frame inventory and source preservation | passed | Earlier: 78 frames, 408.134389–412.230244 s; later: 235 frames, 414.562967–427.800311 s. All source and mask hashes checked; static initialization filter preserved camera poses and copied images/masks byte-identically. |
| C2 | Selective masks preserve ground evidence and exclude visible obstructions | passed | All 313 proposal overlays inspected. Six earlier frames corrected; independent later review added 134 polygons across 129 frames. Final corrected examples inspected. Some blurred hand edges and tiny visitor remnants remain uncertain; this passes provisional training review, not perfect-cleanup certification. |
| C3 | Both reconstructed Gaussian scenes and held-out render inspection | passed | Both 8,000-step trainings completed. All 8 earlier and 24 later held-out views inspected; bodies remain visible and targeted obstructions substantially removed. Source blur and residual artifacts remain documented. Original baseline PLY hashes unchanged. |
| C4 | LAN editor renders real splats and adjusts only selected section | passed | Editor focused inventory passed 9/9 with real Gaussian PLY rendering, independent transforms, camera navigation, locking and source hashes. Cleaned-section rendering remains C3/C5. |
| C5 | Save/reload, next section, original bytes unchanged, LAN access | passed | Final live browser pass used both actual cleaned Gaussian assets, exercised placement and save/reload/reset, inspected individual/combined/orbit screenshots, checked mobile width and no runtime errors. HTTP access passed from a second LAN machine. Server restart/append checks retained from the editor campaign; original source/mask hashes rechecked after training. |

Final counts: **5 passed, 0 failed, 0 blocked, 0 untested** for this two-section/editor delivery. This is not acceptance of a verified physical join or a complete recording reconstruction.

The selected spans are complete retained camera components, not complete physical
areas or every raw video frame in those intervals. Registered-frame holes and the
inter-component gap remain explicit. The earlier delivered preview used only
one-second depth clouds; this campaign trains actual Gaussian splats.

Discovery: sitting-person prompt mislabeled ground clothing and was dropped.
The reviewed correction validator rejected four out-of-image polygon vertices;
the failed partial dataset was retained, polygons geometrically clipped to image
bounds, and the focused preparation completed. No input data were overwritten.

Final regression reused unchanged mask-review evidence and verified matching
source/mask hashes after training. The actual cleaned-scene LAN pass completed
against the committed editor including the save-race correction. No additional
full reconstruction or broad repository test run was needed. LAN service remains
active for the user; training services and test processes have completed.
