# Gap recovery experiment results

Completed 47 gaps; 912 PnP screens and 1248 image-pair/matcher trials.
**0 new-pose screens passed; 16 / 208 in-map control screens passed.** No new poses or component joins were accepted.

A screen is a method/window/direction/query combination, not a distinct recovered frame. Related screens share features and are not independent evidence. Unsupported anchor directions are recorded separately in report.json.

[Full report](report.json) · [All missing-frame runs and component transitions](inventory.json) · [Method list and limitations](../../docs/gap-recovery.md)

| Matcher | Search | Direction | New-pose screens | New-pose passes | Control passes / screens |
|---|---:|---|---:|---:|---:|
| sift | 10 s | lookback | 92 | 0 | 2 / 23 |
| sift | 10 s | lookahead | 84 | 0 | 4 / 29 |
| sift | 30 s | lookback | 92 | 0 | 2 / 23 |
| sift | 30 s | lookahead | 84 | 0 | 4 / 29 |
| lightglue | 10 s | lookback | 92 | 0 | 0 / 23 |
| lightglue | 10 s | lookahead | 84 | 0 | 3 / 29 |
| lightglue | 30 s | lookback | 92 | 0 | 0 / 23 |
| lightglue | 30 s | lookahead | 84 | 0 | 1 / 29 |

## Per-gap next attempt

These are evidence-based next experiments, **not running jobs**. A maximum match count is not a correctness score. Reference selection currently favors the component with the most views in the search interval; that can omit closer small components. Low-feature failures therefore justify checking alternate reference maps before expensive full-video inference.

| Gap | Missing timestamps (s) | Frames | Maximum midpoint matches | Proposed next test |
|---|---:|---:|---:|---|
| gap-007 | 97.38–98.69 | 22 | 5 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-009 | 110.20–113.69 | 54 | 17 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-011 | 115.19–117.34 | 34 | 6 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-021 | 161.20–162.75 | 25 | 19 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-031 | 271.87–273.03 | 19 | 14 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-033 | 274.49–276.23 | 30 | 5 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-034 | 278.78–290.01 | 181 | 9 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-044 | 299.76–306.22 | 94 | 6 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-047 | 307.95–309.02 | 18 | 9 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-050 | 310.62–313.42 | 48 | 5 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-051 | 320.36–321.46 | 22 | 8 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-059 | 328.21–329.46 | 26 | 9 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-067 | 341.52–346.12 | 85 | 0 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-071 | 355.39–358.19 | 50 | 0 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-081 | 365.89–371.53 | 82 | 11 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-084 | 374.33–380.50 | 89 | 37 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-085 | 382.32–401.41 | 276 | 0 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-098 | 412.29–414.51 | 38 | 34 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-101 | 429.28–432.24 | 58 | 28 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-103 | 438.63–446.57 | 136 | 47 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-111 | 452.70–455.75 | 52 | 24 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-117 | 468.84–470.12 | 22 | 6 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-118 | 473.00–477.91 | 75 | 5 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-125 | 485.34–486.46 | 17 | 8 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-128 | 488.21–496.35 | 125 | 26 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-131 | 498.71–507.90 | 153 | 9 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-135 | 512.26–513.59 | 30 | 17 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-137 | 516.99–521.11 | 103 | 3 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-144 | 552.98–554.63 | 38 | 26 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-150 | 560.11–562.30 | 36 | 2 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-151 | 564.68–566.10 | 24 | 6 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-153 | 568.24–569.85 | 24 | 4 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-154 | 572.37–573.44 | 27 | 18 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-157 | 574.80–575.86 | 19 | 22 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-159 | 580.33–581.69 | 30 | 23 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-169 | 611.30–620.35 | 147 | 3 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-177 | 632.59–640.21 | 124 | 11 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-183 | 643.49–645.17 | 36 | 6 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-188 | 646.46–648.10 | 34 | 2 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-191 | 649.48–650.48 | 26 | 4 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-204 | 686.03–687.77 | 43 | 18 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-215 | 708.32–709.71 | 32 | 33 | Static mask + stronger descriptors; inspect PnP inconsistency |
| gap-217 | 713.46–714.70 | 24 | 10 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-220 | 716.93–719.07 | 32 | 11 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-221 | 721.08–723.08 | 43 | 15 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-228 | 731.09–733.52 | 47 | 3 | Closer alternative maps + denser clear anchors; then learned descriptors |
| gap-229 | 734.95–737.25 | 43 | 10 | Earlier-map retrieval; tail has no later anchor |

## Source-image inspection

Six source triptychs were inspected. At 98.02 s the image is heavily occluded and overexposed; at 283.71 s the view is obstructed near a doorway; at 512.96 s there is strong motion blur. The larger-match cases at 377.41, 413.47 and 442.27 s still contain foreground people, repeated floor patterns and substantial viewpoint/blur changes. These observations suggest follow-up tests; they do not establish which matches caused each PnP failure.

- [gap-007: authentic reference / midpoint / return](review/gap-007.jpg)
- [gap-034: authentic reference / midpoint / return](review/gap-034.jpg)
- [gap-135: authentic reference / midpoint / return](review/gap-135.jpg)
- [gap-084: authentic reference / midpoint / return](review/gap-084.jpg)
- [gap-098: authentic reference / midpoint / return](review/gap-098.jpg)
- [gap-103: authentic reference / midpoint / return](review/gap-103.jpg)

The six synthetic tests passed, including shuffled held-out correspondence rejection and resume rejection when a reference model changes. Passing these implementation checks does not mean camera recovery succeeded. All source models remain separate.
