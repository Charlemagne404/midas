# Gate F checkpoint 007 — scan 19 qualification and source-window progress

**Captured:** 2026-10-15 13:17 UTC

**Branch:** `project/veritas`

**Director cycle:** 2026-10-15 13:15 UTC

The 13:15 Director cycle admitted a bounded qualification for
`scan-20261015T130114Z-f5e32eaf445c`:

| Field | Value |
| --- | --- |
| Job | `job-a7320b92c7f0453ea32b1b79` |
| Admission key | `veritas-qualification-v1-scan-20261015T130114Z-f5e32eaf445c` |
| State | `COMPLETED`, exit status 0 |
| Progress | 19/19 finalized analysis events |
| Completed | 2026-10-15 13:16:07 UTC |
| Elapsed | 1.019 seconds |
| Finding | `veritas-qualification-v1-6e262fb7c4325c0c` |
| Finding manifest SHA256 | `e8f46a929377593b12c42e2a4ee9b6948bf390400383b16c43e399b22bf9a2d7` |
| Dataset SHA256 | `a4319521f316e7e136d84d35cd26eea1864d4c404f4be2aaed8881c78c7c5675` |
| Experiment SHA256 | `896e16915e4fe43d065ce99b3b0da639e1ea332d8c6b4ad0b02d93c13ed00e27` |
| Source revision | `e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd` |

The finding covers 19 snapshots, 760 selected pairs, 681 quality-valid pairs,
79 invalid pairs, and 326 unique markets. All five economic qualification
gates report zero positive states. The quality-valid edge range is -$0.984 to
-$0.001 per share, with a nearest-rank median of -$0.024. The recommendation
keeps the hypothetical no-trade policy. No order or authenticated request was
made.

The source summary consumed by this cycle was generated at 13:13:48 UTC. It
records 15,469 campaign-window frame records, 11,367 touched market-frame
states, and 11,000 quality-valid states, with zero positive top-ask and
full-depth states. The source replay is partial: 1,676/3,432 finalized
segments are processed and 1,756 / 470,661,304 bytes remain pending. Summary
digest: `03ace2c3d6761fdb92d6ed81df1e731ad3ed5cf3acda04d609b4b40f6fe27c4d`.

The Arena job record and finding show completion, while the Director manifest
still says `QUEUED` and retains scan 18 as last qualified. The next scheduled
Director cycle at 13:45:16 UTC is the reconciliation point. No manual poll or
retry was started.

**Correction to checkpoint 006:** the 12:43 summary's 4,078
`period_frame_records` were campaign-window frames. The earlier statement
that the prefix contained none was an interpretation error. Those frames had
2,739 quality-valid states and zero positive top-ask or full-depth states.

See [Gate A checkpoint 017](VERITAS_MISSION2_GATE_A_CHECKPOINT_017.md),
[research inventory 020](VERITAS_MISSION2_RESEARCH_INVENTORY_020.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md).
Mission 2 remains active.
