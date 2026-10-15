# Gate F checkpoint 015 — scan 27 qualification and source replay

**Captured:** 2026-10-15 17:16 UTC  
**Branch:** `project/veritas`  
**Director cycle:** 2026-10-15 17:15 UTC

The 17:15 Director cycle admitted a bounded qualification for `scan-20261015T170112Z-de5e990dcdf5`. It validated the sealed source summary generated at 17:14:16 UTC (digest `46d3ed07c0bb8a519d0053fcffe7dfb975fabf6adc5ba1d8a9ea737c8cc18899`).

| Field | Value |
| --- | --- |
| Job | `job-6458cea269bc460db671e75e` |
| Admission key | `veritas-qualification-v1-scan-20261015T170112Z-de5e990dcdf5` |
| State | COMPLETED, exit status 0 |
| Progress | 27/27 finalized analysis events |
| Completed | 2026-10-15 17:15:51 UTC |
| Elapsed | 1.619 seconds |
| Job source artifact | 20,525,574 bytes |
| Finding | `veritas-qualification-v1-b595559921e55264` |
| Finding manifest SHA256 | `bd6f00e2d3423c8284e13f61828926c2e101f5226b0271a425246275e91b934a` |
| Dataset SHA256 | `08363598d19c509dcbf48ff77d83197e24cdc58032a801d61f3bb85d2e08b8b7` |
| Experiment SHA256 | `554b2180964ef796f3f891901307e5829d7fcb7aa737516595cba070284c9464` |
| Source revision | `e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd` |

The finding covers 27 snapshots, 1,080 selected pairs, 961 quality-valid pairs, 119 invalid pairs, and 494 unique markets. The unchanged top-ask baseline and all four depth, minimum, and fee qualification gates report zero positive states. The cumulative top-edge range is -$0.996 to -$0.001 per share, with nearest-rank median -$0.022. The recommendation keeps the hypothetical no-trade policy. The experiment tests candidate qualification, not strategy P&L. No order or authenticated request was made.

The source replay counts 124,922 campaign-window frame records, 110,158 touched market-frame states, and 107,340 quality-valid states; positive top-ask and full-depth states remain zero. It processed 116 finalized segments / 33,217,726 bytes in 242 seconds; cumulative progress is 2,661/3,903 segments, with 1,242 / 344,457,128 bytes pending through ordinal 340,035. Readiness remains `catching_up_finalized_source`.

The Director manifest last updated at 17:15:34 UTC and still projects the scan 27 job as `QUEUED` and scan 26 as last qualified. The append-only event log records the scan 27 admission; Arena completed the job at 17:15:51. The 17:45:25 UTC scheduled Director cycle is the next reconciliation point. No manual poll or retry was started.

See [Gate A checkpoint 025](VERITAS_MISSION2_GATE_A_CHECKPOINT_025.md), [research inventory 028](VERITAS_MISSION2_RESEARCH_INVENTORY_028.json), [operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md). Mission 2 remains active.
