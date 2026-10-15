# Gate F checkpoint 011 — scan 23 qualification and source replay

**Captured:** 2026-10-15 15:16 UTC

**Branch:** `project/veritas`

**Director cycle:** 2026-10-15 15:15 UTC

The 15:15 Director cycle admitted a bounded qualification for
`scan-20261015T150026Z-56e1e44d7837`:

| Field | Value |
| --- | --- |
| Job | `job-bf0dbe4c773f4cfe9832fd8d` |
| Admission key | `veritas-qualification-v1-scan-20261015T150026Z-56e1e44d7837` |
| State | `COMPLETED`, exit status 0 |
| Progress | 23/23 finalized analysis events |
| Pinned source | 23 events / 422,748 bytes |
| Completed | 2026-10-15 15:15:47 UTC |
| Elapsed | 1.320 seconds |
| Job source artifact | 15,019,645 bytes |
| Job record SHA256 | `cf2bda800f4795e93122f9a84e779aedfb4607432ccb80dc7860b3853960dc03` |
| Finding | `veritas-qualification-v1-a695104c7dcbb82a` |
| Finding manifest SHA256 | `6d6abd9ad8834370998d7124f1cec7d0e91f3d83674b0e8a41b1d6aa20c7fc0c` |
| Dataset SHA256 | `92c7548c9dd97a669673a5243eeb83abaf646273a93957c843a712f0a723844a` |
| Experiment SHA256 | `131e29f8052f30ebf34a1768a5cb52c68dd3be82585426a3fba1a38c2a9c8d12` |
| Source revision | `e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd` |

The finding covers 23 snapshots, 920 selected pairs, 825 quality-valid pairs,
95 invalid pairs, and 418 unique markets. All five economic qualification
gates report zero positive states. The 23-scan valid top-edge range is -$0.984
to -$0.001 per share, with a nearest-rank median of -$0.023. The recommendation
keeps the hypothetical no-trade policy. No order or authenticated request was
made.

The source summary consumed by this cycle was generated at 15:14:28 UTC. It
records 70,950 campaign-window frame records, 59,343 touched market-frame
states, and 57,798 quality-valid states, with zero positive top-ask and
full-depth states. The replay is partial: 2,161/3,668 finalized segments are
processed, with 1,507 / 396,434,833 bytes pending. Summary digest:
`37715a41a176feb08db23867b5f2c7b9e39647a3f9df43a770df049c497dd6e3`.

The Director manifest last updated at 15:15:32 UTC projects the scan 23 job
`QUEUED` and retains the completed scan 22 finding. The append-only event log
records scan 22 completion at 15:15:32 UTC and scan 23 admission at 15:15:35
UTC. Arena completed scan 23 at 15:15:47 UTC; the 15:45:00 UTC scheduled
Director cycle is the reconciliation point. No manual poll or retry was
started.

See [Gate A checkpoint 021](VERITAS_MISSION2_GATE_A_CHECKPOINT_021.md),
[research inventory 024](VERITAS_MISSION2_RESEARCH_INVENTORY_024.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and
[engineering](VERITAS_MISSION2_ENGINEERING.md). Mission 2 remains active.
