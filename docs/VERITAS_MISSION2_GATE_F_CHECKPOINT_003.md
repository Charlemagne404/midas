# Gate F checkpoint 003 — scheduled qualification source drift

**Captured:** 2026-10-15 11:18 UTC  
**Branch:** `project/veritas`  
**Checkpoint base:** `16b5660`

## Scheduled run

At 11:15 UTC the Research Director observed the finalized scan
`scan-20261015T110153Z-93de340dd5ce` and admitted one bounded Arena job,
`job-8cf39368af21426ea3127501`. Its pinned admission key was
`veritas-qualification-v1-scan-20261015T110153Z-93de340dd5ce`.

The worker started at 11:15:43 UTC and failed before processing an event with
`ValueError: Research source changed while queued; submit a new job against
the current revision`. The job remains `FAILED` at progress 0/1 and has no
finding. The source revision changed while this checkpoint's code work was
still in progress; the worker's source pin correctly prevented a result from
being attributed to the moving checkout. The Director's no-auto-retry policy
remains intact, and no second job was submitted for the same scan. A no-launch
reconciliation at 11:20 UTC updated the Director to `FAILED` with current
stage `Reviewing a failed qualification` and a status note that automatic
retry is disabled; it admitted no job.

The prior completed qualification for the 10:31 scan remains preserved. The
Director timer remains active at :15 and :45 UTC. The next observer scan is
scheduled for 11:31 UTC, followed by the next Director cycle at 11:45 UTC.
That new scan is the next valid chance to qualify against the committed source
revision. The 11:15 attempt does not change the existing no-trade decision.

## Independent source replay

The scheduled 11:10 UTC source-analysis recurrence completed successfully at
11:13:27 UTC. It processed 116 finalized segments / 33,071,280 bytes in 163
seconds, used 8.149 CPU seconds, and peaked at 121.7 MiB. The prefix now has
1,188 of 3,195 cataloged segments processed, 2,007 pending (538,721,685
bytes), through ordinal 139,550. It still contains zero campaign-window
frames. The sealed summary digest is
`c54728b7aa6b2a68a742f5ba5304b11eddeec498aa5b94664a155e961595b7e0`.

The observer, source-analysis, and Director timers were active at capture. The
source analyzer still reads finalized `.seg` files only and reports
`active_segment_read=false`. No Reality service or source record was changed.

## Follow-up

Commit the stable research source before the next observation cycle, then let
the already configured observer and Director timers process a newly finalized
scan. Preserve the failed job and its error; do not retry its scan key. See
[operations](VERITAS_MISSION2_OPERATIONS.md), [Gate A checkpoint
012](VERITAS_MISSION2_GATE_A_CHECKPOINT_012.md), and [research inventory
015](VERITAS_MISSION2_RESEARCH_INVENTORY_015.json).
