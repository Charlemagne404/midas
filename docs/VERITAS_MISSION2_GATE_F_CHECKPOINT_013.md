# Gate F checkpoint 013 — scan 25 qualification and source replay

**Captured:** 2026-10-15 16:18 UTC  
**Branch:** project/veritas  
**Director cycle:** 2026-10-15 16:15 UTC

The 16:15 Director cycle reconciled scan 24 and admitted a bounded qualification for scan-20261015T160014Z-63b12b6b8d54. Before admission it validated the sealed source summary generated at 16:14:28 UTC (digest 4e8f84ea69ba9ad1970495b3981feb3136b086367edef693a07be2a4e4351b9a).

| Field | Value |
| --- | --- |
| Job | job-717cf7803fd746809d073d46 |
| Admission key | veritas-qualification-v1-scan-20261015T160014Z-63b12b6b8d54 |
| State | COMPLETED, exit status 0 |
| Progress | 25/25 finalized analysis events |
| Pinned source | 25 events / 459,585 bytes |
| Completed | 2026-10-15 16:15:55 UTC |
| Elapsed | 1.514 seconds |
| Job source artifact | 17,771,610 bytes |
| Job record SHA256 | dbf24e2b5cdcb84791bc9cd5674aece3be0ff34c9f66ee6bc960d46c10a09173 |
| Finding | veritas-qualification-v1-454c6e2d83426f98 |
| Finding manifest SHA256 | d4723d6f505af2bbbc04dd671d66a1008964abce0378b3e8e35899ed396406d7 |
| Dataset SHA256 | f8e91d98d0c251402c82d8ddc51ae6bb26fbf98022d76cca9ae959aaf5e89ddd |
| Experiment SHA256 | 82fbcb05fc28a10bd5321e713e17df6f46edcb6f8637bf380e9c6af85ce0793f |
| Source revision | e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd |

The finding covers 25 snapshots, 1,000 selected pairs, 894 quality-valid pairs, 106 invalid pairs, and 460 unique markets. All five economic qualification gates report zero positive states. The cumulative top-edge range is -$0.996 to -$0.001 per share, with nearest-rank median -$0.023. The recommendation keeps the hypothetical no-trade policy. No order or authenticated request was made.

The source replay counts 96,535 campaign-window frame records, 84,138 touched market-frame states, and 81,994 quality-valid states; positive top-ask and full-depth states remain zero. It processed 128 finalized segments / 32,329,769 bytes in 227 seconds; cumulative progress is 2,417/3,786 segments, with 1,369 / 372,776,598 bytes pending through ordinal 303,638. Readiness remains catching_up_finalized_source.

The Director manifest last updated at 16:15:39 UTC and still projects the scan 25 job as QUEUED and scan 24 as last qualified. The append-only event log records scan 24 completion at 16:15:40 and scan 25 admission at 16:15:42. Arena completed scan 25 at 16:15:55; the 16:45:03 UTC scheduled Director cycle is the next reconciliation point. No manual poll or retry was started.

See [Gate A checkpoint 023](VERITAS_MISSION2_GATE_A_CHECKPOINT_023.md), [research inventory 026](VERITAS_MISSION2_RESEARCH_INVENTORY_026.json), [operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md). Mission 2 remains active.
