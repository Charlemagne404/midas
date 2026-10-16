# Gate F checkpoint 028 — scan 46 scheduled qualification

**Captured:** 2026-10-16 02:48 UTC

**Mission status:** active; the Director has not yet reconciled its manifest.

## Scan-pinned Arena child

The scheduled Research Director admitted scan 46 to Arena at 02:45 UTC. Child
`job-4618a298410143789631af10` completed 46/46 source events with exit status
0 in 2.92 seconds. Its submitted source revision matches the source manifest.
The read-only finding validator accepted finding
`veritas-qualification-v1-f36de5fff01de75a`, including its experiment digest,
scan identity, complete candidate evidence, and complete empty source replay.

| Evidence | SHA-256 / value |
| --- | --- |
| Job record | `d868987fd9a521f42b9f33afdee09677713b377627285dc952b0dd50fca72939` |
| Source manifest file | `79e2f367bf18ed6425043f2bac0dac0979085ea7bd25ea402f30b12018f5e970` |
| Finding manifest file | `4355d5b2b263a28280effa222c2d8cd47802224582294cd409d658fb75745c41` |
| Experiment | `VERITAS-M2-ECO-QUAL-001-V4-RUN-fc7e37ab22c2` |
| Experiment digest | `12fb0d4947adba8a815595982ddd269de7f4aa74f35273be88381d94cc784356` |
| Dataset digest | `fc7e37ab22c274dfe98718ca33e5c375234d6161f5ae42efd5d9fab70f87165c` |

The finding covers 46 snapshots, 1,840 selected pair states, 1,600
quality-valid states, and 820 selected IDs. The unchanged top-ask gross rule,
full-depth gross, both-minimum, single-match-fee, and fragmentation-safe-fee
gates each have zero positive states. The maximum edge remains -$0.001/share;
the median is -$0.020/share. Candidate evidence is complete with zero rows,
and empty source replay is complete. Orders and authenticated requests remain
false. The decision stays no-trade; this is qualification evidence, not
strategy P&L or independent venue confirmation.

## Director and source-analysis state

At capture, the Director manifest still projects the completed child as
`QUEUED`, with scan 44 as last qualified. Its next scheduled reconciliation
is at 03:15 UTC. No manual poll, retry, or duplicate admission was made.

The 02:44:41 UTC finalized-source summary covers 4,869/5,029 segments and
1,261,406,393 processed bytes, with 160 segments / 39,330,180 bytes pending.
It reports 318,568 quality-valid states across 77 markets and zero positive
top-ask or full-depth states. The source analyzer reads finalized segments
only and does not read the active `.open` segment. The gap-detail index remains
incomplete at 1,676/5,020 segments and has found 73 campaign-window
resynchronization gaps; see [Gate C checkpoint
009](VERITAS_MISSION2_GATE_C_CHECKPOINT_009.md).

The persisted source artifacts and validation are in
`data/arena/jobs/job-4618a298410143789631af10/` and
`data/arena/findings/veritas-qualification-v1-f36de5fff01de75a/`. See the
[independent panel audit](VERITAS_MISSION2_GATE_B_CHECKPOINT_001.md) and
[inventory 054](VERITAS_MISSION2_RESEARCH_INVENTORY_054.json).
