# Independent section filters — acceptance ledger

Scope: per-section visibility and reversible opacity/size/ray filtering in the
LAN editor, saved with project settings. Retraining, permanent source changes,
filtered PLY export, voxel-floater processing and semantic ghost identification
are outside this delivery. Browser emulation is not a physical-phone test.

Fixed inventory: the five filter integration checks, four mobile checks, existing
desktop integration and save-race regression, followed by read-only live deploy
inspection. Budget: discovery, focused failed/blocked checks, one final pass on
committed product source. Tests use isolated state and real Gaussian PLY files.

| Check | Current result | Evidence |
| --- | --- | --- |
| Independent visibility / Only; alignment unchanged | passed | filter integration |
| All three filters render; other section unaffected; Original/reset restore image | passed | image hashes excluding overlays |
| Separate settings persist through save/reload, JSON import/export, server restart | passed | filter integration |
| Invalid thresholds rejected; legacy settings default off | passed | filter API and validator |
| Phone inspection controls; source hashes unchanged | passed | focused phone check |
| Existing mobile placement/save and touch/layout checks | pending | queued sequential rerun |
| Existing desktop integration | pending | queued sequential rerun |
| Pending-save regression | passed | discovery |
| Live deployed scene and saved-state preservation | pending | after deployment |

Discovery encountered a test-harness failure while constructing a huge binary
image assertion diff, alongside browser crashes during concurrent runs. Tests
now compare bounded image hashes and run sequentially. The image-isolation setup
was corrected to actually exit solo mode before selecting the hidden section.
A phone test selector matched both the selected panel and its button; it now
selects the navigation button explicitly. These were test changes, not product
fixes. The focused filter/image checks passed after these corrections.

Independent read-only code review found no medium/high scoped issues. Both
original and filtered actual-scene images were inspected. Aggressive combinations
remove substantial real surface detail as well as some streaks. No filter preset
is promoted as an accurate cleaned reconstruction; all filters default off.
