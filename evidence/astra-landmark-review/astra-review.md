# Independent Astra correspondence review

There is convincing **regional overlap**, but this review does **not** establish a geometric bridge between components `cbc3a19f69fce48a` and `0bc7a95fc61b9c4c`.

I inspected all 38 supplied original frames, plus five unenhanced native crops. I did not inspect previous matching overlays. Review was limited to scene objects and floor features; no facial matching or biometric landmarks were used.

The strongest shared feature is the combination of a **rectangular reflective tape patch, a green strip below/left of it, and a thin white cord hanging immediately to its left on the near wall of a black bag**. BEFORE `frame_006454.jpg` shows this between occluding trouser legs. It appears larger but more blurred in `006489` and `006491`. AFTER `006548` and `006549` show the patch clearly. This distinctive configuration supports overlap much more strongly than generic bag shapes or the tiled floor.

The best point-proposal pair is **006454 → 006548**, with **006454 → 006549** as an adjacent-frame check. Three approximate physical patch corners are recorded in `astra-candidates.json`:

| ID | Feature | BEFORE 006454 (x,y) | AFTER 006548 (x,y) | Confidence |
|---|---|---|---|---|
| A01 | Patch lower-left corner at green strip | (211,621), ±15 px | (944,1008), ±12 px | Medium |
| A02 | Patch lower-right corner | (276,626), ±16 px | (1008,990), ±12 px | Medium |
| A03 | Patch upper-left corner at bag rim | (205,562), ±14 px | (914,894), ±12 px | Medium |

These are **three points on one small, potentially deformable patch**, not three independent distributed scene landmarks. The physical patch appears attached and no handling is visible, but motion or deformation during the missing interval cannot be excluded. Its reflections change markedly with view. The intended features are material boundaries, not the bright streaks inside the patch. `usable_for_geometric_test: true` means suitable as tentative hypotheses for refinement or rejection, not accepted camera-recovery evidence.

The white cord reinforces regional identity but is deliberately **not** supplied as an exact point: its apparent bottom in the before images may be where it bends or disappears against the bag. A silhouette extremum or occlusion endpoint need not be the same material point in another view.

I found **no confident cross-gap floor correspondence**. Before `006466/006476/006477` contain a distinctive floor smear near an irregular seam, but I could not locate its after counterpart. Regular tile intersections cannot safely be paired without establishing the tile index. Shadows are not fixed floor texture. Later after frames mostly move into close views of neighboring bags and add no defensible distributed before/after points. Repeating white coverings, black bag outlines, purple fabric, and trolley wheel fragments are not enough to invent further matches.

The useful next boundary is a narrowly scoped refinement/check of these patch proposals against existing geometry and original pixels, while retaining a separate search for independently anchored floor or other rigid features. A fit using only this patch must not be called a reconstructed connection. This review performed no geometric solve, inference, GPU work, installation, public repository edit, or commit.

Crop mapping (coordinates unchanged inside each crop; add its upper-left offset):

| Crop | Source | Native bounds (left,top,right,bottom) |
|---|---|---|
| analytical-crop-0.png | 006454 | (100,400,380,700) |
| analytical-crop-1.png | 006489 | (100,0,440,360) |
| analytical-crop-2.png | 006491 | (150,0,460,350) |
| analytical-crop-3.png | 006548 | (650,570,1080,1050) |
| analytical-crop-4.png | 006477 | (0,0,1080,500) |
