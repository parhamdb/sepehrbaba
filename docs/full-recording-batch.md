# Processing the complete 12:17 recording

The September 26 batch processes the complete **737.301333-second source and
12,793 native frames**. This is a processing scope, not a claim that every frame
can already be reconstructed. The previously published 48- and 71-second scenes
remain separate; the pilot overlaps them.

`scripts/process_recording.py` first reuses published models, then processes all
retained window and bootstrap components, largest first. It avoids training a
component only when all its registered views occur in one already trained
component; that reuse is recorded. Every other candidate receives the existing geometry check,
1920-pixel image preparation, person masks, mask inventory checks, 8,000 Brush
training steps, up to 500,000 splats, and every tenth image held out. Rejected
geometry and failed stages remain recorded; failures do not stop independent
sections.

Then **37 overlapping 30-second windows, advancing 20 seconds**, cover the video
from zero through its last frame. Windows with uncovered frames receive matching
at native-frame offsets 1, 2, 4, 8, 16 and 32, followed by independent multi-model
mapping. Unlike the previous largest-model recovery, **every returned model**
is considered for training. The initial triangulation-angle threshold is 8°;
the subsequent existing reprojection and coverage gates are unchanged. Narrower
windows and denser local matching are an attempt to recover through local camera
motion; they cannot recover surfaces hidden by people or absent from the video.

## Why this approach

- Reusing retained geometry provides additional inspectable scenes without
  repeating successful camera reconstruction.
- Short independent windows retain more disconnected components and limit the
  influence of occlusion and long-range drift. They cost additional mapping and
  training time and do not establish spatial connections between scenes.
- Repeating the same 90-second largest-component search would retain the same
  limitation. Joining without verified landmarks would invent spatial evidence.

## Run and inspect

Use the pinned COLMAP 3.12.6 CUDA and Brush 0.3.0 environment from this project.
Paths are supplied at runtime; private server addresses, users and logs do not
belong in the repository.

```sh
python3 scripts/process_recording.py \
  --source-run "$NATIVE" --windows "$WINDOWS" --database "$WINDOWS/database.db" \
  --work "$FRESH_CAMPAIGN" --colmap "$COLMAP" --brush "$BRUSH" \
  --published-model "$PUBLISHED_48_MODEL" --published-model "$PUBLISHED_71_MODEL"
```

Run under a persistent supervisor with no runtime cutoff and an appropriate
memory limit. There is one sequential writer and one campaign lock. SQLite's
backup API creates a private database including committed WAL content. The source
video, native frames and existing reconstructions are not modified. The batch
checks for at least 20 GiB disk and 8 GiB available memory before each subprocess.
The supervisor must enforce the memory ceiling while a subprocess is running.

`state.json` and `logs/` are private runtime evidence. `summary.json` deliberately
contains no runtime paths and reports each component, attempted window and
ten-second coverage bin. Frame counts are separate from temporal spans and
publication. No automatic upload or publication occurs.

Successful stages are reused with unchanged configuration and script hashes.
Failed or interrupted stages are preserved and are **not automatically retried**.
The identical command can continue after observed failures. An interrupted stage
or missing previously accepted output instead stops with an actionable error;
inspect its retained log and recover in a fresh campaign.
An interrupted process cannot be declared complete just because a directory
exists.

The batch permits provisional training after automated mask checks so it can run
unattended. **This does not replace visual mask review.** Each candidate retains
`mask-review.jpg`, source/render `held-out-contact.jpg`, measured held-out results,
and camera references. Before publication inspect those artifacts, choose and
verify an entry camera, establish display orientation, inspect navigation and
record limitations. A high PSNR alone does not validate geometry. An automatic
person mask can remove static human details; the original recording remains the
primary source for those details.

## Frozen acceptance inventory

The minimum delivery is the complete batch running on the reconstruction host,
with a real additional trained candidate and inspectable progress. The broader
goal remains pending until the batch finishes and usable results are reviewed
and published. No unverified alignment is in scope.

1. All native frames, including first and last, appear in the 37-window plan.
2. Independent work continues after a failed stage; completed/failed stages are
   not silently rerun; public progress excludes private paths.
3. The live batch reuses published scenes and trains/evaluates an additional
   actual component at the existing settings.
4. Every remaining interval receives processing or a precise preserved failure.
5. New scene masks, held-out renders, entry view and navigation are reviewed
   before web publication; missing intervals remain visible in coverage reports.
6. Scripts, method, sanitized progress and verification evidence are committed.

Validation budget: one discovery pass, focused failed/blocked checks, one final
pass after required checks are resolved. Existing unchanged viewer evidence is
reused until viewer assets or behavior change. Long-running GPU processing has
no elapsed-time cutoff; an active batch is not a completed reconstruction.
