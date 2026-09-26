# Full-recording processing evidence

[Window plan](plan.json) covers the complete 737.301333-second recording with
37 overlapping windows and accounts for all 12,793 native frames. The retained
feature database contains every source frame; 12,780 have detectable keypoints.
The 13 without keypoints are not silently removed from the coverage denominator.

[Batch method and reproduction](../../docs/full-recording-batch.md).

The batch runs retained-component training first, followed by shorter-window gap
recovery. Processing the recording does not guarantee reconstruction of every
surface. New splats remain provisional until visual review. The published
18-second pilot overlaps the existing 71-second scene and adds no unique duration.
