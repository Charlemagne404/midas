# Gate F checkpoint 009 — scan 21 qualification and source replay

**Captured:** 2026-10-15 14:21 UTC

**Branch:** `project/veritas`

**Director cycle:** 2026-10-15 14:15 UTC

The 14:15 Director cycle admitted a bounded qualification for
`scan-20261015T140150Z-b4ba652d6e9c`:

| Field | Value |
| --- | --- |
| Job | `job-979f118b02764225b23ad87b` |
| Admission key | `veritas-qualification-v1-scan-20261015T140150Z-b4ba652d6e9c` |
| State | `COMPLETED`, exit status 0 |
| Progress | 21/21 finalized analysis events |
| Pinned source | 21 events / 385,567 bytes |
| Completed | 2026-10-15 14:16:20 UTC |
| Elapsed | 1.214 seconds |
| Job source artifact | 12,269,678 bytes |
| Job record SHA256 | `8157bd23984495d5e7d9461ea2cd84e81fd0e983bde3042d3d518b2adc7c4943` |
| Finding | `veritas-qualification-v1-e46e192a082956ab` |
| Finding manifest SHA256 | `a96e0e029ce83e2c181aebcaa2b38ef1fc5b816d45fb4a510d5bdbd7f6f8847c` |
| Dataset SHA256 | `fe9b2295cd75246167ad23e6fff017c424f74581036afed3f23f90ee103f6ab6` |
| Experiment SHA256 | `9047457176fb94a8ff5afddc0949b568f47d5ad3ee08b45f5cf8a29e1bef1ae3` |
| Source revision | `e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd` |

The finding covers 21 snapshots, 840 selected pairs, 751 quality-valid pairs,
89 invalid pairs, and 367 unique markets. All five economic qualification
gates report zero positive states. Scan 21's valid top-edge range is -$0.368
to -$0.001 per share, with a nearest-rank median of -$0.032. The recommendation
keeps the hypothetical no-trade policy. No order or authenticated request was
made.

The source summary consumed by this cycle was generated at 14:13:53 UTC. It
records 40,459 campaign-window frame records, 30,809 touched market-frame
states, and 29,749 quality-valid states, with zero positive top-ask and
full-depth states. The replay is partial: 1,919/3,549 finalized segments are
processed, with 1,630 / 430,839,649 bytes pending. Summary digest:
`ed121aceb771923c0070d648c18794e6b1ff378bce7a17afcba4e8f827614495`.

The Director manifest last updated at 14:16:04 UTC marked the scan 21 job
`QUEUED` and scan 20 as last qualified. Arena completed scan 21 at 14:16:20
UTC; the append-only event log records scan 20 completion before scan 21
admission. The 14:45:16 UTC scheduled Director cycle is the reconciliation
point. No manual poll or retry was started.

See [Gate A checkpoint 019](VERITAS_MISSION2_GATE_A_CHECKPOINT_019.md),
[research inventory 022](VERITAS_MISSION2_RESEARCH_INVENTORY_022.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and
[engineering](VERITAS_MISSION2_ENGINEERING.md). Mission 2 remains active.
