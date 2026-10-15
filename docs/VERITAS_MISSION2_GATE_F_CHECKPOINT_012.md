# Gate F checkpoint 012 — scan 24 qualification and source replay

**Captured:** 2026-10-15 15:53 UTC  
**Branch:** project/veritas  
**Director cycle:** 2026-10-15 15:45 UTC

The 15:45 Director cycle reconciled scan 23 and admitted a bounded qualification for scan-20261015T153020Z-4edb94c649e6. It validated the sealed source summary generated at 15:44:43 UTC (digest ed887a5443ff3348e5d39a1755ca75d2f8f1c615a545c18a4a2ffa3594a4a51a) before admission.

| Field | Value |
| --- | --- |
| Job | job-a6806df19f4d4d67bfcc83b5 |
| Admission key | veritas-qualification-v1-scan-20261015T153020Z-4edb94c649e6 |
| State | COMPLETED, exit status 0 |
| Progress | 24/24 finalized analysis events |
| Pinned source | 24 events / 441,408 bytes |
| Completed | 2026-10-15 15:45:44 UTC |
| Elapsed | 1.418 seconds |
| Job source artifact | 16,395,379 bytes |
| Job record SHA256 | 35933c02af7d1201cff8a5bb4aa0de5d51af448f60420f1072a9d532b0af7eec |
| Finding | veritas-qualification-v1-564af5dc8f4b12eb |
| Finding manifest SHA256 | c1b52f5e8084892c84e77c604ba87fecf0eeac7cbe5d8afa4972461388d17c46 |
| Dataset SHA256 | df28b65d20ccec295e69163b5f1a5b1ca62de4685f9cc9b8d10440759e490872 |
| Experiment SHA256 | a88ba12f729b2e27b210021a3e51ea3716e093383b01afbd417ede9c9826e6d6 |
| Source revision | e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd |

The finding covers 24 snapshots, 960 selected pairs, 859 quality-valid pairs, 101 invalid pairs, and 441 unique markets. All five economic qualification gates report zero positive states. The cumulative top-edge range is -$0.984 to -$0.001 per share, with nearest-rank median -$0.023. The recommendation keeps the hypothetical no-trade policy. No order or authenticated request was made.

The source replay generated 84,112 campaign-window frame records, 72,406 touched market-frame states, and 70,508 quality-valid states, with zero positive top-ask and full-depth states. It processed 128 finalized segments / 32,016,580 bytes in 225 seconds; cumulative progress is 2,289/3,727 segments, with 1,438 / 377,450,510 bytes pending through ordinal 287,107. Readiness remains catching_up_finalized_source.

The Director manifest last updated at 15:45:28 UTC and still projects the scan 24 job as QUEUED and scan 23 as last qualified. The append-only event log records scan 23 completion at 15:45:29 and scan 24 admission at 15:45:31. Arena completed scan 24 at 15:45:44; the 16:15:11 UTC scheduled Director cycle is the next reconciliation point. No manual poll or retry was started.

See [Gate A checkpoint 022](VERITAS_MISSION2_GATE_A_CHECKPOINT_022.md), [research inventory 025](VERITAS_MISSION2_RESEARCH_INVENTORY_025.json), [operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md). Mission 2 remains active.
