# Gate A checkpoint 021 — scan 23 and source replay progress

**Captured:** 2026-10-15 15:16 UTC

**Branch:** `project/veritas`

**Checkpoint base:** `48688f1`

## Prospective discovery and economics

The scheduled 15:00:26 UTC scan,
`scan-20261015T150026Z-56e1e44d7837`, is the 23rd finalized v4 snapshot.
Six bounded Gamma frames returned 300 records and 300 unique IDs. The union
contains 190 supported same-condition V1 pairs and 110 explicit exclusions
(84 augmented NegRisk records and 26 unsupported outcome relationships); no
duplicates or identity conflicts were recorded.

The 40-market selection retained four available frozen controls and selected
36 rotating markets. It overlaps scan 22 on five IDs, one rotating and four
controls, so 35 rotating selections changed. Liquidity counts were 15 high /
11 medium / 14 low; expiry counts were 19 near / 14 medium / 7 long; spread
counts were 21 tight / 14 medium / 5 wide. Selection used the `expiry` phase.
All selection probabilities remain conditional on the bounded response union
and frozen controls.

Thirty-six pairs passed the current request/receipt quality gate; four had
empty No ask sides. Six of 40 passed the older reported age/skew gate. The
valid top-edge range was -$0.310 to -$0.001 per share, with a nearest-rank
median of -$0.010. No top-ask, full-depth, per-leg minimum, single-match fee,
or fragmentation-safe fee gate was positive.

Across 23 scans, the cumulative sample has 920 selected observations, 825
quality-valid pairs, 95 invalid pairs, and 418 distinct markets. The prior
reported-age/skew gate accepts 189 pairs. Paired recovery is 636/920 (69.13
percentage points). The cumulative edge range remains -$0.984 to -$0.001 per
share, with a nearest-rank median of -$0.023. The 502 sampled state
comparisons differ in 486 cases (96.81%); current activity bands are 39
higher-change, 55 lower-change, and 324 unclassified markets. These remain
selected, intermittent observations, not independent opportunity counts or
a venue-wide census.

Snapshot evidence SHA256 is
`56e1e44d7837c5c30efc7dd9e42b74eed9331da69db83f7d6113b4a4acb7146f`; the
compressed snapshot file SHA256 is
`4a6484174e60e520b3a13c03cc40f402edd1fb5469bb021db1b5d8127ae4264e`. The v4
analysis event SHA256 is
`46b517caa69aa87b5b8a1a0449cffbfeae30e552e06f7ba1ca892716cd0e991c`; its
file SHA256 is
`e1de02400a3b772286c49b84f78dd6c6f1ff874ee15e346be26f2233534c18c6`. The
23-snapshot research summary digest is
`010cbf63f0b6af45ab5a12a02174a3a8ff8011bf430dda487001c8575a15be30`; its
file SHA256 is
`581de46473c4fe099e21bf7203c02e1eb33879d5ad492b1e7770db2441933fa9`.

## Finalized-source replay

The 15:10:44 UTC scheduled replay completed at 15:14:31 UTC. It processed 124
finalized segments / 33,163,975 source bytes in 227 seconds, using 11.36 CPU
seconds and 155,504,640 bytes peak memory. The prefix now covers 2,161 of 3,668
cataloged segments (516,420,246 bytes), through ordinal 269,843; 1,507
finalized segments / 396,434,833 bytes remain pending.

The cumulative campaign-window summary counts 70,950 frame records, 59,343
touched market-frame states, and 57,798 quality-valid states. Positive
top-ask and full-depth states remain zero. The replay remains partial and
reads only finalized `.seg` files. Its sealed summary digest is
`37715a41a176feb08db23867b5f2c7b9e39647a3f9df43a770df049c497dd6e3`; the
summary file SHA256 is
`08bd70741083b0d689c8df5d3bdf9b3fbee7683670261fea5932dbaccba6199a`. The
state file SHA256 is
`4a0736936816d797f09cfef588ee04d9fcac4c05e05f52bd4983c1df492a282c`.

## Director qualification

The 15:15:07 UTC Director cycle recorded scan 22 qualification completion at
15:15:32, admitted scan 23 at 15:15:35, and consumed the 15:14 finalized-
source summary. Arena completed all 23 events at 15:15:47 UTC in 1.320
seconds. Finding `veritas-qualification-v1-a695104c7dcbb82a` reports no
positive gross candidate. Its finding manifest SHA256 is
`6d6abd9ad8834370998d7124f1cec7d0e91f3d83674b0e8a41b1d6aa20c7fc0c`; the
dataset SHA256 is
`92c7548c9dd97a669673a5243eeb83abaf646273a93957c843a712f0a723844a`; the
experiment SHA256 is
`131e29f8052f30ebf34a1768a5cb52c68dd3be82585426a3fba1a38c2a9c8d12`.

The Director manifest last updated at 15:15:32 UTC names scan 23 and projects
its job as `QUEUED`, while its latest finding remains the completed scan 22
finding. Arena's scan 23 job is complete; the next scheduled Director cycle
at 15:45:00 UTC is the reconciliation point. No manual poll or retry was
started.

The observer, source-analysis, and Director timers remain active. Their next
scheduled UTC runs are 15:30:10, 15:40:45, and 15:45:00. Mission 2 remains
active. Preserve the bounded sampling limits, corrected source-window
interpretation, and unchanged zero-exposure baseline. Current state is in
[research inventory 024](VERITAS_MISSION2_RESEARCH_INVENTORY_024.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and
[engineering](VERITAS_MISSION2_ENGINEERING.md).
