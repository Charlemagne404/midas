# Gate F checkpoint 004 — stable-revision qualification completed

**Captured:** 2026-10-15 11:48 UTC  
**Branch:** `project/veritas`  
**Checkpoint base:** `6cc4061`

## Scheduled Research Director cycle

At 11:45 UTC, the Director admitted one bounded Arena job for the new 11:31
scan, `scan-20261015T113126Z-bf24f3a0706b`. The job,
`job-b7c66151c4c34b3ca60cd376`, was pinned to source revision
`e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd`, matching
the committed checkout. It completed all 16 finalized v4 events in 0.82
seconds and read 293,197 source bytes.

The reproducible finding is
`veritas-qualification-v1-0e39c79c039a76cf`; its experiment run is
`VERITAS-M2-ECO-QUAL-001-RUN-b3fc19f69680`. All five qualification gates have
zero positive states. The result remains `no_positive_gross_candidate_observed`;
the recommendation is no-trade. No orders or authenticated requests occurred.

A 11:46 UTC no-launch poll verified the finding, set the Director state to
`CURRENT`, and admitted no job. There are no active or queued Arena jobs and no
invalid activity artifacts. The earlier 11:15 job for the 11:01 scan remains
failed at 0/1 because its source changed while queued; it was not retried.

## Finalized-source replay

The 11:40 UTC recurrence completed at 11:43:13 UTC. It processed 128 finalized
segments / 27,931,474 bytes in 149 seconds, using 7.443 CPU seconds and
116.0 MiB peak memory. The prefix now covers 1,316 of 3,254 cataloged
segments, with 1,938 pending (524,228,737 bytes) through ordinal 151,428. It
still has zero campaign-window frames and `active_segment_read=false`. The
sealed summary digest is
`6f959acc6978fc2e4eb2fbf7e07ee41112a286d0e844daa25d31f43c515fc9cf`.

The observer, source-analysis, and Director timers remain active. Their next
runs are scheduled for 12:01:17, 12:10:14, and 12:15:15 UTC. No Reality
service or protected source record was changed. Current lineage and resource
details are in [research inventory 016](VERITAS_MISSION2_RESEARCH_INVENTORY_016.json)
and [operations](VERITAS_MISSION2_OPERATIONS.md). Mission 2 remains active.
