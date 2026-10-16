# Gate F checkpoint 010 — scan 22 qualification and source replay

**Captured:** 2026-10-15 14:48 UTC

**Branch:** `project/veritas`

**Director cycle:** 2026-10-15 14:45 UTC

The 14:45 Director cycle admitted a bounded qualification for
`scan-20261015T143154Z-8c0fa0040695`:

| Field | Value |
| --- | --- |
| Job | `job-2998418c4bec44529ec4c012` |
| Admission key | `veritas-qualification-v1-scan-20261015T143154Z-8c0fa0040695` |
| State | `COMPLETED`, exit status 0 |
| Progress | 22/22 finalized analysis events |
| Pinned source | 22 events / 404,034 bytes |
| Completed | 2026-10-15 14:46:23 UTC |
| Elapsed | 1.221 seconds |
| Job source artifact | 13,644,413 bytes |
| Job record SHA256 | `2e4f44758c8ebad11a717f1cbde247ee9c5b358927d62fb3520f6686e9c3de16` |
| Finding | `veritas-qualification-v1-d6e6f2a3574075a0` |
| Finding manifest SHA256 | `d53dfdb1e3e5276ae272753f397f8a5e3bdfb1f93f89530b462e6d3668475842` |
| Dataset SHA256 | `15aaefd674764f99b3ed3fe083870db265700dc4eda7c996c1e235ab0b3806ed` |
| Experiment SHA256 | `6b65c513c8cc7d67e757a0ea6af361b8d366e6ea5887ae3c362dfa37e948f6f9` |
| Source revision | `e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd` |

The finding covers 22 snapshots, 880 selected pairs, 789 quality-valid pairs,
91 invalid pairs, and 392 unique markets. All five economic qualification
gates report zero positive states. The 22-scan valid top-edge range is -$0.984
to -$0.001 per share, with a nearest-rank median of -$0.024. The recommendation
keeps the hypothetical no-trade policy. No order or authenticated request was
made.

The source summary consumed by this cycle was generated at 14:44:34 UTC. It
records 56,771 campaign-window frame records, 46,152 touched market-frame
states, and 44,837 quality-valid states, with zero positive top-ask and
full-depth states. The replay is partial: 2,037/3,608 finalized segments are
processed, with 1,571 / 413,665,338 bytes pending. Summary digest:
`0f5e98355d6ef4be02d3987cb2546a14455e252f55abbf35d0cf117a10bb38db`.

The Director manifest last updated at 14:46:07 UTC projects the scan 22 job
`QUEUED` and retains the completed scan 21 finding. The append-only event log
records scan 21 completion at 14:46:08 UTC and scan 22 admission at 14:46:10
UTC. Arena completed scan 22 at 14:46:23 UTC; the 15:15:07 UTC scheduled
Director cycle is the reconciliation point. No manual poll or retry was
started.

See [Gate A checkpoint 020](VERITAS_MISSION2_GATE_A_CHECKPOINT_020.md),
[research inventory 023](VERITAS_MISSION2_RESEARCH_INVENTORY_023.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and
[engineering](VERITAS_MISSION2_ENGINEERING.md). Mission 2 remains active.
