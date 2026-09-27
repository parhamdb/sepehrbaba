# Independent clearer-frame review

Verdict: **unresolved**. No supported A01 seed is available from this inspection.

Inspected all eight contact sheets spanning the supplied 159-frame sequence, followed by 15 native originals: 006423, 006434, 006441, 006442, 006449, 006453, 006454, 006457, 006459, 006463, 006464, 006466, 006468, 006477, and 006548. Also inspected native-resolution, unenhanced pixel crops of 006449, 006453, 006454, and 006548. Crop files are inspection aids only; no interpolation, sharpening, generation, or model inference was used.

The relevant patch is in the background-left of target 006454, next to the pale hanging cord. The pre-gap 006453/006454 views are among the clearest inspected views with the patch exposed. Earlier views are smaller, blurred, cropped, or partly obstructed. In 006463 onward the patch approaches the left edge; by 006477 it is substantially cropped out. Moving people and the pan interrupt the later correspondence, so 006548 is not a continuous directly observed tracking bridge.

The gray patch's upper-left and lower-right boundaries are substantially more readable than its lower-left. At the lower-left, green material overlaps or visually merges with the gray surface; the images do not establish whether a visible gray/green junction is the actual corner or an occluding boundary. This ambiguity persists in the larger later 006548 view. Therefore neither an offset from the previous tentative target nor an intersection extrapolated from the other corners is a defensible A01 measurement.

For a bounded tracker control experiment only, 006453 is immediately adjacent to target 006454 and offers approximate control seeds in native 1080x1920 coordinates: A02 lower-right approximately (279, 619), uncertainty about 6 px; A03 upper-left approximately (209, 554), uncertainty about 6 px. These are visual estimates, not independently verified tracked results, and do not resolve A01. They are deliberately excluded from the A01 seed JSON to avoid suggesting a supported A01 seed exists.

A tracker can test whether a selected visible texture moves consistently. It cannot independently establish that an ambiguous seed is the requested physical lower-left corner. Keep A01 unresolved unless independent source evidence exposes that corner or the landmark definition is explicitly changed to a visible junction.
