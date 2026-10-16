# Gate C checkpoint 006 — bounded gap-detail catch-up

Captured 2026-10-16 01:21:56 UTC, after the scheduled gap-detail service exited.
The one-shot started at 01:20:00 and completed at 01:21:14 UTC with exit status
0. It processed 128 finalized segments / 30,283,274 source bytes under its
existing 128-segment / 32-MiB batch limits.

## Current prefix

| Measure | Result |
| --- | ---: |
| Cataloged segments | 4,871 |
| Replayable catalog segments | 4,869 |
| Processed segments / bytes | 1,072 / 224,233,275 |
| Pending segments / bytes | 3,797 / 1,037,173,118 |
| All-period gap events | 1,855 |
| Campaign-window gap events in processed prefix | 0 |
| Status | `catching_up` |

The processed prefix ends at ordinal 122,759. It has not reached the frozen
campaign window, which starts at 2026-10-14 21:07:58 UTC. Therefore the empty
campaign-window gap count is incomplete and is not evidence that the campaign
had no feed gaps. The active `.open` segment was not read. The next bounded
batch remains scheduled for 01:50 UTC; no manual run or restart was made.

At roughly 30 MB per 30-minute batch, many more scheduled batches will be
needed to traverse the remaining ~1.04 GB, while new finalized segments
continue to arrive. This is a throughput observation, not a completion-time
forecast; segment sizes and future recording growth vary.

No campaign, service, timer, or recorder state was changed. Keep censor
categories separate and wait for the finalized prefix to enter campaign time
before reconciling gap reasons or affected markets against frozen follow-ups.
