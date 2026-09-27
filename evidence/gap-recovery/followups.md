# Targeted recovery follow-ups

Three distinct hypotheses were tested on the same three pilot gaps. No new camera pose passed. The original full-run report remains unchanged. These are alternative experiments on failed cases, not certified reconstructions.

| Gap | Largest-map SIFT maximum midpoint matches | Nearest-map SIFT maximum | Nearest-map ALIKED maximum | New-pose passes |
|---|---:|---:|---:|---:|
| gap-007 | 5 | 9 | 5 | 0 |
| gap-034 | 9 | 0 | 2 | 0 |
| gap-135 | 17 | 9 | 4 | 0 |

The maxima combine ratio and LightGlue matching, search directions and window lengths; they are not unique validated landmarks. More raw correspondences did not produce a reliable camera. ALIKED here describes existing SIFT locations, so this does not test an independent ALIKED detector.

Runtime evidence:

- [nearest report](nearest-report.json): 3 gaps, 72 screens, 66 pair/matcher trials; 4 control passes; zero new-pose passes.
- [aliked report](aliked-report.json): 3 gaps, 72 screens, 66 pair/matcher trials; 4 control passes; zero new-pose passes.

All three focused attempts are now closed. The remaining next steps are in the [ranked method list](../../docs/gap-recovery.md): inspect clearer anchors and mask static landmarks at recoverable gap boundaries, then use learned-camera proposals only where independent geometric evidence can check them. Mid-gap blind motion may remain unknown. No additional jobs are running for these attempts.
