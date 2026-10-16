# Gate F checkpoint 008 — scan 20 qualification and source replay

**Captured:** 2026-10-15 13:47 UTC

**Branch:** `project/veritas`

**Director cycle:** 2026-10-15 13:45 UTC

The 13:45 Director cycle admitted a bounded qualification for
`scan-20261015T133142Z-dfa1ef9bb7fe`:

| Field | Value |
| --- | --- |
| Job | `job-0f98c874c60e4b46b0466150` |
| Admission key | `veritas-qualification-v1-scan-20261015T133142Z-dfa1ef9bb7fe` |
| State | `COMPLETED`, exit status 0 |
| Progress | 20/20 finalized analysis events |
| Completed | 2026-10-15 13:46:06 UTC |
| Elapsed | 1.210 seconds |
| Finding | `veritas-qualification-v1-053febadd6978cbf` |
| Finding manifest SHA256 | `278cb4328766932421189ac88b0ea3d0aee8cb6a2ef054e354691bfa38e3d383` |
| Dataset SHA256 | `209795d17e57b628afcca6007b73caf5c58ab7cdab31156b81c942979f97f23b` |
| Experiment SHA256 | `0fc522149e95d3e79612abe6c916b7ccd2d3b3f97998d2b166930f03f59dee60` |
| Source revision | `e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd` |

The finding covers 20 snapshots, 800 selected pairs, 714 quality-valid pairs,
86 invalid pairs, and 349 unique markets. All five economic qualification
gates report zero positive states. The quality-valid edge range is -$0.984 to
-$0.001 per share, with a nearest-rank median of -$0.024. The recommendation
keeps the hypothetical no-trade policy. No order or authenticated request was
made.

The source summary consumed by this cycle was generated at 13:43:56 UTC. It
records 29,198 campaign-window frame records, 21,747 touched market-frame
states, and 21,041 quality-valid states, with zero positive top-ask and
full-depth states. The replay is partial: 1,791/3,490 finalized segments are
processed, with 1,699 / 450,044,085 bytes pending. Summary digest:
`220fef285637e9a676796227336b78e8bca9222dc13f7ec8132990174a140623`.

The Arena job record and finding show completion, while the Director manifest
still says `QUEUED` and retains scan 19 as last qualified. The next scheduled
Director cycle at 14:15:29 UTC is the reconciliation point. No manual poll or
retry was started.

See [Gate A checkpoint 018](VERITAS_MISSION2_GATE_A_CHECKPOINT_018.md),
[research inventory 021](VERITAS_MISSION2_RESEARCH_INVENTORY_021.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and
[engineering](VERITAS_MISSION2_ENGINEERING.md). Mission 2 remains active.
