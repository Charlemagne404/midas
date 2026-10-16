# Gate A checkpoint 018 — scan 20 and source replay progress

**Captured:** 2026-10-15 13:47 UTC

**Branch:** `project/veritas`

**Checkpoint base:** `644e509`

## Prospective discovery and economics

The scheduled 13:31:42 UTC scan,
`scan-20261015T133142Z-dfa1ef9bb7fe`, is the 20th finalized v4 snapshot. Six
bounded Gamma frames returned 300 records, 297 unique IDs, 153 supported
same-condition V1 pairs, and 144 explicit exclusions (126 augmented NegRisk
records and 18 unsupported outcome relationships). Three records overlapped
across frames; there were no identity conflicts. The 40-market sample retained
all three available frozen controls and selected 37 rotating markets. It
overlaps scan 19 on nine IDs, six of them rotating; 31 rotating selections
changed. Selection counts were 10 high / 6 medium / 24 low liquidity, 26 near
/ 14 medium expiry, and 15 tight / 13 medium / 12 wide spreads.

Thirty-three pairs passed the current request/receipt quality gate; seven had
empty No ask sides. Seven of 40 passed the older reported age/skew gate. No
top-ask, full-depth, per-leg minimum, single-match fee, or fragmentation-safe
fee gate was positive.

Across 20 scans, the cumulative sample has 800 selected observations, 714
quality-valid pairs, 86 invalid pairs, and 349 distinct markets. The previous
reported-age/skew gate accepts 167 pairs. The paired recovery is 547/800
(68.38 percentage points). The top-edge range remains -$0.984 to -$0.001 per
share, with a nearest-rank median of -$0.024. These are selected intermittent
observations, not independent opportunity counts or a venue-wide census.

Snapshot evidence SHA256 is
`dfa1ef9bb7fe36e644aec1f8e83f739d329836d115006d385ed6527d0f1d7de0`; the
compressed snapshot file SHA256 is
`b40cc00818aa512846d23cad5ca8fa2a8246be6575a7bcd79346324bfa0e2893`. The v4
analysis event SHA256 is
`d39e6f509b6894f817d8ef9026f5f618bf34b9464bc1ad008b10d5c022f79cb0`; its
file SHA256 is
`6cb48c4b6e1613cfe0be590c8368f8108ff5b7b040dda931bd8256cc7b5be324`. The
20-snapshot research summary digest is
`78053dfe0687afa9b79f5efd5f4c21d9f50aac08ff50dd50298c905ed2cf75f4`.

## Finalized-source replay

The 13:40:34 UTC scheduled replay completed successfully at 13:43:59 UTC. It
processed 115 finalized segments / 33,465,203 source bytes in 205 seconds,
using 10.25 CPU seconds and 148,406,272 bytes peak memory. The prefix now
covers 1,791 of 3,490 cataloged segments (416,842,757 bytes), through ordinal
216,185; 1,699 finalized segments / 450,044,085 bytes remain pending.

The cumulative summary counts 29,198 campaign-window frame records, 21,747
touched market-frame states, and 21,041 quality-valid states. Positive
top-ask and full-depth states remain zero. The replay is partial and reads
only finalized `.seg` files. Its sealed summary digest is
`220fef285637e9a676796227336b78e8bca9222dc13f7ec8132990174a140623`; the
summary file SHA256 is
`844e97b8a1589336f92e84eb5cdbb1c2aa5357d9a45bcdc808a44ee6576e0c79`. The
state file SHA256 is
`f0276de6681a75a5f9afa31c6ba1ea3efa0973f6f4d24ba669165e94d30ba390`.

## Director qualification

The 13:45 UTC Director cycle consumed the scan 20 v4 event and the 13:43
finalized-source summary, then admitted job
`job-0f98c874c60e4b46b0466150`. Arena completed all 20 events at 13:46:06 UTC
in 1.210 seconds. Finding `veritas-qualification-v1-053febadd6978cbf` covers
800 selected pairs, 714 quality-valid pairs, 86 invalid pairs, and 349 unique
markets. It reports zero positive states at each of the five qualification
gates and retains the no-trade recommendation. The dataset SHA256 is
`209795d17e57b628afcca6007b73caf5c58ab7cdab31156b81c942979f97f23b`; the
experiment SHA256 is
`0fc522149e95d3e79612abe6c916b7ccd2d3b3f97998d2b166930f03f59dee60`; the
finding manifest SHA256 is
`278cb4328766932421189ac88b0ea3d0aee8cb6a2ef054e354691bfa38e3d383`.

At checkpoint time the Arena job and finding were complete, but the Director
manifest still showed the admission as queued and scan 19 as the last
qualified scan. The 14:15 UTC scheduled cycle is the next reconciliation
point. No manual poll or retry was started.

The observer, source-analysis, and Director timers remain active. Their next
scheduled UTC runs are 14:01:36, 14:10:17, and 14:15:29. Mission 2 remains
active. Preserve the bounded sampling limits, corrected source-window
interpretation, and unchanged zero-exposure baseline. Current state is in
[research inventory 021](VERITAS_MISSION2_RESEARCH_INVENTORY_021.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and
[engineering](VERITAS_MISSION2_ENGINEERING.md).
