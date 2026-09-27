# Independent marked-image review — 2026-09-27

All eight supplied marked screenshots, the three original JPEGs, and both unenhanced analytical crops were opened and inspected. The image observations preceded reading the candidate descriptions. This review uses original scene pixels; there was no image generation, enhancement, inference run, geometry solve, or write to the public repository.

The same local assembly is visually well supported: pale curved region above a black side wall, descending pale cord, gray rectangular patch to the right, and green material at its lower left. This is stronger than a generic bag resemblance. It does **not** make every marked corner correct. “Reflective tape” is a proposed material description, not something established here.

| Candidate | Verdict | What the marked images show |
|---|---|---|
| A01 original: before (211,621), after (944,1008)/(946,1020) | **Unresolved** | The before center lies in the gray/green transition toward the left of the patch's lower portion. The after centers are at or just below the patch's bottom-left vicinity near the dark lower edge. The before boundary is irregular and poorly separated; these are not unambiguously the same material corner. Recognition of the region is supported; precise correspondence is not. |
| A01 adjusted: before (226,636), same after points | **Rejected as a correction** | The before center now falls in the green area below the visible gray patch, without a distinctive corner at the center. The after centers remain in the gray patch's lower-left/bottom-edge vicinity. The rightward part of the move is superficially plausible, but the downward displacement is unsupported. The arbitrary 15/15 change should not be promoted as a fixed match. |
| A02: before (276,626), after (1008,990)/(1014,1003) | **Supported as an approximate hypothesis** | The centers select the lower-right termination of the gray patch against black material in all three views. The patch shape supports the same coarse feature. Blur prevents an exact material-corner measurement. |
| A03: before (205,562), after (914,894)/(917,907) | **Supported as an approximate hypothesis** | The centers select the upper-left start of the gray patch at the sloping top of the black wall; the patch extends right and down in each view. The bright, folded/reflected top edge makes the exact material junction ambiguous. A highlight by itself is not a stable point. |

All coordinates above are native 1080×1920 pixels with top-left origin. The verdicts apply to both supplied after frames. A02/A03 support is visual and approximate, not acceptance for alignment. The stated 12–16 px uncertainties remain uncalibrated annotation estimates.

There is no confidently visible replacement coordinate for A01's intended lower-left material corner. Inventing another precise displacement would exceed the evidence. No change to A02/A03 coordinates is justified by this inspection.

Recommended disposition: retain original A01 as a historical unresolved proposal, reject the unverified 15/15 adjustment, and retain A02/A03 only as tentative visual hypotheses. This is a localization problem within a plausibly shared region, not evidence that the entire object is different. The two adjacent after images give repeatability within that view; they do not settle the before-to-after corner ambiguity. No stationarity, rigid support, pose, or reconstruction alignment is established. No faces, identities, or biometric features were used as correspondence evidence.
