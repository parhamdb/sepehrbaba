# Provisional alignment delivery ledger

Acceptance: preserve six exact human matches, produce reversible local 3D
placement, expose both windows and comparison modes, inspect surrounding geometry,
publish a navigable preview and reproducible methods. No original-scene merge,
new model training, generated surfaces or claim of accepted camera recovery.
Budget: one local discovery pass, focused failure checks, one final deployed pass.

| ID | Status | Evidence |
|---|---|---|
| P1 transform/data integrity | passed | Known-transform controls, proper rotations/positive scales, all candidate residuals and floor offsets independently recomputed; all cloud hashes, frame tags and counts verified. |
| P2 independent review | passed | Read-only review checked local gauges, coordinate transforms, floor constraints, privacy and exact source preservation; no medium/high findings. Follow-up checked render/layout fixes. |
| P3 local browser | passed | Both clouds rendered and passed browser SHA-256 checks; three modes, hide/show, photo colors, all-frame/floor selection, frame selector, pointer/keyboard orbit, reset/top, mobile width and zero runtime/shader errors. |
| P4 visual inspection | passed | Actual rendered geometry, photo-color view and floor comparison inspected. Approximate shared region and large surrounding depth conflict remain visible. |
| P5 live publication | passed | GitHub Pages run [36305036586](https://github.com/parhamdb/sepehrbaba/actions/runs/36305036586) deployed product commit `bc55f21835f4b88a980d73ad75205941c52ed139`. Final live browser pass exercised the complete P3 controls, checked both cloud hashes, recorded 150,802 visible geometry pixels and zero runtime/shader errors. Live photo-color screenshot inspected. |

Final delivery count: **5 passed, 0 failed, 0 blocked, 0 untested**.
Scientific verification of a camera/scene connection remains unresolved.

Discovery exposed unstable canvas sizing and heavy unnecessary rendering under
software WebGL. A diagnostic screenshot bypass did not solve the stall; that
browser and its child processes were stopped. The focused product fix set explicit
container-sized rendering, limited the mesh draw range to the selected frame,
and rendered static geometry only after interaction. The next local pass completed
all required controls and screenshots. Previously passed numerical evidence was
retained because geometry did not change.

Initial local full build succeeded. The focused viewer bundle was rebuilt once
for those runtime fixes; final deployment built the frozen committed source successfully.
No inference, reconstruction or source-video processing job remains running.
The final browser process exited successfully; no delivery jobs remain active.
