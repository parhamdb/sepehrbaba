# Human selection delivery checks

Acceptance: record the six user choices exactly, preserve the blind Luna record,
evaluate the existing local geometric gate, expose both reviews on the live page.
No camera joining, new matcher run, or changed thresholds. Validation budget: one
local discovery pass, focused failed checks if needed, one final live pass.

| ID | Status | Evidence |
|---|---|---|
| H1 exact mapping and retained source | passed | Human JSON, original Luna result and source hashes |
| H2 geometry and repeatability | passed | Actual Thor OpenCV 4.11.0 run plus independent reprojection/repeat check |
| H3 local page | passed | Both reviews, six choices, selected markers, geometry text, toggles, mobile, hashes |
| H4 independent review | passed | Scoped source/artifact review |
| H5 live page | untested | Final deployed artifact and user paths |

Initial inventory: 0 passed, 0 failed, 0 blocked, 5 untested.
The scientific result is a failed planar-fit check, separately from delivery status.

Discovery: **4 passed, 0 failed, 0 blocked, 1 untested**. Re-evaluation on Thor
exactly reproduced the retained human JSON. Independent homogeneous-coordinate
reprojection reproduced the all-point errors. Original Luna evaluation recomputed
unchanged. Local Chromium checked both reviews, every selection, controls, all
four JPEG hashes, three JSON payloads, mobile width and absence of runtime errors.
Mobile screenshot visually inspected. Independent source/UI review reported no
medium/high findings; it specifically checked Q5 uses human option 1.
