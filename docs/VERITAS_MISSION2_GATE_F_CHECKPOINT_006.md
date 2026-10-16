# Gate F checkpoint 006 — scan 18 qualification and replay progress

**Captured:** 2026-10-15 12:48 UTC
**Branch:** `project/veritas`
**Director cycle:** 2026-10-15 12:45 UTC

The recurring Director admitted one scan-pinned qualification for
`scan-20261015T123114Z-ded26b5ea023`:

| Field | Value |
| --- | --- |
| Job | `job-3c739889ee5846dd80f284b8` |
| Admission key | `veritas-qualification-v1-scan-20261015T123114Z-ded26b5ea023` |
| State | `COMPLETED`, exit status 0 |
| Progress | 18/18 finalized analysis events |
| Completed | 2026-10-15 12:45:53 UTC |
| Elapsed | 0.929 seconds |
| Finding | `veritas-qualification-v1-c6d40523cb31a232` |
| Finding manifest SHA256 | `e534510529749687e17d2d95b02581fbf77bbb2541e5ac3f5a7034f9470f0996` |
| Dataset SHA256 | `92df11af576a4a0509f45f23a5d6a4c166fae16f4d1e05037af978796d7587c6` |
| Experiment SHA256 | `23b827532087e5e61af04612da616854b4bc2c71faa944ceb5c1dc9b46712738` |
| Source revision | `e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd` |

The qualification dataset covers 18 snapshots, 720 selected pairs, 645
quality-valid pairs, 75 invalid pairs, and 304 unique markets. The unchanged
top-ask gross sign, full displayed-depth gross, depth-plus-minimum, single
match fee sensitivity, and fragmentation-safe fee sensitivity each report
zero positive states. The quality-valid edge range is -$0.984 to -$0.001 per
share, with a nearest-rank median of -$0.024. The finding recommends retaining
the hypothetical no-trade policy. No order or authenticated request was made.

The Arena job record and finding artifact show completion, but the Director
manifest still reports this admission as queued and scan 17 as its last
qualified scan. This is a stale Director projection, not a failed Arena job.
No manual Director run or retry was started. The scheduled 13:15:27 UTC cycle
is the next reconciliation point; preserve any resulting event and state.

The bounded finalized-source replay published at 12:43:27 UTC and advanced to
1,548/3,373 cataloged segments, with 1,825 segments / 487,084,989 bytes
pending. Its summary SHA256 is
`15fb5a0364063e02b14c0bb435cb9538077557bb2125204b144c98cfa63f74d8`; its file
SHA256 is
`71ad639e9241e98721c82ab30ba4dbd9633dbba74f988e43342aab221bfa9e5d`. The
processed prefix contains 4,078 campaign-window frame records, including
2,779 touched market-frame states and 2,739 quality-valid states; positive
top-ask and full-depth states remain zero. The source timer remains active; no
source files were changed.

See [Gate A checkpoint 016](VERITAS_MISSION2_GATE_A_CHECKPOINT_016.md),
[research inventory 019](VERITAS_MISSION2_RESEARCH_INVENTORY_019.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md).
Mission 2 remains active.
