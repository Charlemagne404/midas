# Gate C checkpoint 029 — frozen shadow lag and quota pressure

**Captured:** 2026-10-16T19:19:10Z

**Mission status:** active; the frozen campaign and worker remain unchanged.

## Current shadow and recorder state

The Reality recorder is active with restart count 0 and status
`RECORDING_UNSEQUENCED`. At 19:19:09 UTC it had ordinal 986,000, 730,984
frames, 8 markets / 16 expected books, 4,761 gaps, four failures, and latest
reported error `ConnectionClosedError`. Recording continued after that error.

The frozen shadow is active with restart count 1 and state
`WARMING_OR_LAGGED_SOURCE`. Its cursor is 535,359, leaving an ordinal gap of
450,641 to the recorder. Its last source receipt is 2026-10-15T17:30:13Z
(about 25h49m old); its last decision remains 2026-10-15T08:58:06Z (about
34h22m old). It has 10,253 decisions, 47,911 observations, 113,376 journal
events, and zero submitted orders. Public-measurement follow-ups remain 937
observed / 40,075 censored.

Against the 18:40 UTC checkpoint, the shadow cursor advanced by 1,212
ordinals and the recorder by 8,325, widening the gap by 7,113. By 19:19 the
shadow cursor had advanced 1,460 while the recorder advanced 10,288; the gap
had widened by 8,828. Lagged frames increased from 207,871 to 209,056.
Decisions and follow-up counts did not change. The source receipt advanced
only 4m49s across this interval and is still more than a day old.

## Resource evidence and likely cause

The shadow's cgroup remains limited to 10% CPU (`cpu.max` 10000/100000). At
19:19, 1,422,680 of 1,450,279 periods were throttled (98.10%). Memory was
315,604,992 / 536,870,912 bytes, peak 323,477,504 bytes, with 15,126,528
bytes of swap and no cgroup OOM events. Host load was 0.56 / 0.96 / 1.06,
available RAM 10.1 GB, swap 4.28 / 4.29 GB used, and disk 57% used / 195 GB
free. This is strong evidence that the CPU quota is binding; it does not
establish that quota is the only cost in the large live journal.

Code comparison identifies a likely source-side cost: the frozen
`Tail.refresh()` re-enumerates and sorts the segment directory at least every
0.5 seconds as records are read, while the current branch keeps the open
segment handle and refreshes the inventory at sealed-segment boundaries. The
branch also reuses decoded frame events and cached top-of-book values. Its
four-segment isolated canary reduced process CPU by 81.32% while preserving
the tested business-event results, but that short run does not establish
catch-up throughput against the live journal's full accumulated state.

The live campaign pins `shadow_worker.py` to hash
`0b745947399dc33898bdba41df4f0b183ba87477f5dcddecb7ae2d26f29e3c6d`; the
current Veritas branch version is
`903a5cd900678a6b89c1e7bf6efb1fa58a131c8d0b2d5e7ef82d2a6dd46b0005`. The
live worker's producer hash remains on its single allowed campaign value.
Therefore the branch's isolated reader improvements are not running in the
frozen campaign. Applying them would violate the campaign's pinned identity;
no live code, quota, cursor, or campaign change was made.

The last saved integrity result is from 03:01:41Z: SQLite integrity was `ok`
and 113,162 events were verified. The live status now reports 113,376 events,
so 214 events are outside that completed check. No full integrity scan was
run against the active writer.

## Safe next step

Treat forward shadow data as non-current until source receipts and decisions
resume. Evaluate a separately versioned successor with verified continuity
and a bounded throughput check; keep the original campaign, worker, and quota
unchanged. The higher CPU throttle fraction and growing gap justify that
investigation, but do not authorize a live restart or quota change.
