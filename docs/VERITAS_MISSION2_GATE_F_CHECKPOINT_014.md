# Gate F checkpoint 014 — scan 26 qualification and source replay

**Captured:** 2026-10-15 16:48 UTC  
**Branch:** project/veritas  
**Director cycle:** 2026-10-15 16:45 UTC

The 16:45 Director cycle reconciled scan 25 and admitted a bounded qualification for scan-20261015T163054Z-7f7265f6f8fe. It validated the sealed source summary generated at 16:43:46 UTC (digest c28e4f92547264dfa8d41ba28101357b8e498ddd2816a96af73c103f0f05ca74).

| Field | Value |
| --- | --- |
| Job | job-bf79fe6aaf2444738b7d024e |
| Admission key | veritas-qualification-v1-scan-20261015T163054Z-7f7265f6f8fe |
| State | COMPLETED, exit status 0 |
| Progress | 26/26 finalized analysis events |
| Pinned source | 26 events / 478,069 bytes |
| Completed | 2026-10-15 16:45:44 UTC |
| Elapsed | 1.525 seconds |
| Job source artifact | 19,148,342 bytes |
| Job record SHA256 | c1a50e2b92ec3dc5ec17072b03575ea854bc39d67f590d3ec3c96867e728739a |
| Finding | veritas-qualification-v1-0d41b647a6d03623 |
| Finding manifest SHA256 | 9987fabed0366789ba0c94a329820f20d6d552e5e97e19f0687663ef0febb307 |
| Dataset SHA256 | 08cfdaad91bdaaa42eb94225947ee0c2760eee0cc3bd9b89fd2db2309446c86e |
| Experiment SHA256 | 3046c819243807fad858750a47825c3fa0e85930f3f94c23fb72f855a82c79a3 |
| Source revision | e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd |

The finding covers 26 snapshots, 1,040 selected pairs, 928 quality-valid pairs, 112 invalid pairs, and 480 unique markets. All five economic qualification gates report zero positive states. The cumulative top-edge range is -$0.996 to -$0.001 per share, with nearest-rank median -$0.022. The recommendation keeps the hypothetical no-trade policy. No order or authenticated request was made.

The source replay counts 108,912 campaign-window frame records, 95,468 touched market-frame states, and 93,007 quality-valid states; positive top-ask and full-depth states remain zero. It processed 128 finalized segments / 33,042,875 bytes in 221 seconds; cumulative progress is 2,545/3,844 segments, with 1,299 / 356,461,487 bytes pending through ordinal 320,213. Readiness remains catching_up_finalized_source.

The Director manifest last updated at 16:45:28 UTC and still projects the scan 26 job as QUEUED and scan 25 as last qualified. The append-only event log records scan 25 completion at 16:45:29 and scan 26 admission at 16:45:31. Arena completed scan 26 at 16:45:44; the 17:15:09 UTC scheduled Director cycle is the next reconciliation point. No manual poll or retry was started.

See [Gate A checkpoint 024](VERITAS_MISSION2_GATE_A_CHECKPOINT_024.md), [research inventory 027](VERITAS_MISSION2_RESEARCH_INVENTORY_027.json), [operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md). Mission 2 remains active.
