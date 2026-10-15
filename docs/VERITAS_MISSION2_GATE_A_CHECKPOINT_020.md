# Gate A checkpoint 020 — scan 22 and source replay progress

**Captured:** 2026-10-15 14:48 UTC

**Branch:** `project/veritas`

**Checkpoint base:** `4248b04`

## Prospective discovery and economics

The scheduled 14:31:54 UTC scan,
`scan-20261015T143154Z-8c0fa0040695`, is the 22nd finalized v4 snapshot.
Six bounded Gamma frames returned 300 records and 300 unique IDs. The union
contains 217 supported same-condition V1 pairs and 83 explicit exclusions
(33 augmented NegRisk records and 50 unsupported outcome relationships); no
duplicates or identity conflicts were recorded.

The 40-market selection retained four available frozen controls and selected
36 rotating markets. It overlaps scan 21 on three IDs, all controls; none of
the rotating selections overlap. Liquidity counts were 10 high / 16 medium /
14 low; expiry counts were 12 near / 24 medium / 4 long; spread counts were
12 tight / 18 medium / 10 wide. Selection used the `liquidity` phase. All
selection probabilities remain conditional on the bounded response union and
frozen controls.

Thirty-eight pairs passed the current request/receipt quality gate; two had
empty No ask sides. Seven of 40 passed the older reported age/skew gate. The
valid top-edge range was -$0.570 to -$0.002 per share, with a nearest-rank
median of -$0.023. No top-ask, full-depth, per-leg minimum, single-match fee,
or fragmentation-safe fee gate was positive.

Across 22 scans, the cumulative sample has 880 selected observations, 789
quality-valid pairs, 91 invalid pairs, and 392 distinct markets. The prior
reported-age/skew gate accepts 183 pairs. Paired recovery is 606/880 (68.86
percentage points). The cumulative edge range remains -$0.984 to -$0.001 per
share, with a nearest-rank median of -$0.024. The 488 sampled state
comparisons differ in 472 cases (96.72%); current activity bands are 39
higher-change, 55 lower-change, and 298 unclassified markets. These remain
selected, intermittent observations, not independent opportunity counts or
a venue-wide census.

Snapshot evidence SHA256 is
`8c0fa0040695851e11b14798dd71245bfd136b169616eb6ebe6746142e67c5bd`; the
compressed snapshot file SHA256 is
`e9b1eb0dd93fd928eede95018f6668500f9606731c15e24cd250537baa1c6368`. The v4
analysis event SHA256 is
`29654481899825e10b6af8dde0c6509f47779cf73a97fcc2b4d375f59b9c1001`; its
file SHA256 is
`c54a7a166ecc6ef31e2e7d9e7d9b6d33ea595b8afa4813318e77435e2e127b2b`. The
22-snapshot research summary digest is
`ec0aa3bcb735877d9205b7c2999561603d6bb9a270de4504467e204e722bd4a1`; its
file SHA256 is
`6648260eebd410af1d47d39aa2223ae5c94e578b059bb8e47dccfade09e8980e`.

## Finalized-source replay

The 14:40:34 UTC scheduled replay completed at 14:44:37 UTC. It processed 118
finalized segments / 33,526,838 source bytes in 243 seconds, using 12.14 CPU
seconds and 155,471,872 bytes peak memory. The prefix now covers 2,037 of 3,608
cataloged segments (483,256,271 bytes), through ordinal 251,691; 1,571
finalized segments / 413,665,338 bytes remain pending.

The cumulative campaign-window summary counts 56,771 frame records, 46,152
touched market-frame states, and 44,837 quality-valid states. Positive
top-ask and full-depth states remain zero. The replay remains partial and
reads only finalized `.seg` files. Its sealed summary digest is
`0f5e98355d6ef4be02d3987cb2546a14455e252f55abbf35d0cf117a10bb38db`; the
summary file SHA256 is
`705a3e13a37dfc1bd5fe4054f2320629aec93de38d947960335bad69bc0ef0d5`. The
state file SHA256 is
`f2ba97d384b7e78cf7877da7c1bfad89d7dde2a1bfc076b7d9ef2020f34a9539`.

## Director qualification

The 14:45:43 UTC Director cycle recorded scan 21 qualification completion at
14:46:08, admitted scan 22 at 14:46:10, and consumed the 14:44 finalized-
source summary. Arena completed all 22 events at 14:46:23 UTC in 1.221
seconds. Finding `veritas-qualification-v1-d6e6f2a3574075a0` reports no
positive gross candidate. Its finding manifest SHA256 is
`d53dfdb1e3e5276ae272753f397f8a5e3bdfb1f93f89530b462e6d3668475842`; the
dataset SHA256 is
`15aaefd674764f99b3ed3fe083870db265700dc4eda7c996c1e235ab0b3806ed`; the
experiment SHA256 is
`6b65c513c8cc7d67e757a0ea6af361b8d366e6ea5887ae3c362dfa37e948f6f9`.

The Director manifest last updated at 14:46:07 UTC, before the completion and
admission event records. It now names scan 22 and projects its job as
`QUEUED`, while its latest finding remains the completed scan 21 finding.
Arena's scan 22 job is complete; the next scheduled Director cycle at
15:15:07 UTC is the reconciliation point. No manual poll or retry was
started.

The observer, source-analysis, and Director timers remain active. Their next
scheduled UTC runs are 15:00:10, 15:10:12, and 15:15:07. Mission 2 remains
active. Preserve the bounded sampling limits, corrected source-window
interpretation, and unchanged zero-exposure baseline. Current state is in
[research inventory 023](VERITAS_MISSION2_RESEARCH_INVENTORY_023.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and
[engineering](VERITAS_MISSION2_ENGINEERING.md).
