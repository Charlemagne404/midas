# Gate A checkpoint 017 — scan 19 and source-window replay

**Captured:** 2026-10-15 13:17 UTC

**Branch:** `project/veritas`

**Checkpoint base:** `a7840db`

## Correction to checkpoint 016

The finalized-source analyzer's `period_frame_records` counter counts frames
inside the frozen campaign window. Checkpoint 016 incorrectly said that the
12:43 processed prefix contained no campaign-window frames. It contained
4,078, with 2,779 touched market-frame states and 2,739 quality-valid states.
The positive top-ask and full-depth counts were still zero, and the replay
prefix was still incomplete. The earlier source and finding digests remain
unchanged; the interpretation is corrected here and in the linked operations
records.

## Prospective discovery and economics

The scheduled 13:01:14 UTC scan,
`scan-20261015T130114Z-f5e32eaf445c`, is the 19th finalized v4 snapshot. Six
bounded Gamma frames returned 300 records, 298 unique IDs, 138 supported
same-condition V1 pairs, and 160 explicit exclusions (93 augmented NegRisk
records and 67 unsupported outcome relationships). Two records overlapped
across frames; there were no identity conflicts. The 40-market sample retained
all three available frozen controls and selected 37 rotating markets. It
overlaps scan 18 on seven IDs; 33 rotating selections changed. Selection counts
were 15 high / 13 medium / 12 low liquidity, 19 near / 14 medium / 7 long
expiry, and 18 tight / 16 medium / 6 wide spreads.

Thirty-six pairs passed the current request/receipt quality gate; four had
empty ask sides (one Yes and three No). Seven of 40 passed the older reported
age/skew gate. No top-ask, full-depth, per-leg minimum, single-match fee, or
fragmentation-safe fee gate was positive.

Across 19 scans, the cumulative sample has 760 selected observations, 681
quality-valid pairs, 79 invalid pairs, and 326 distinct markets. The previous
reported-age/skew gate accepts 160 pairs. The paired recovery is 521/760
(68.55 percentage points). The top-edge range remains -$0.984 to -$0.001 per
share, with a nearest-rank median of -$0.024. These are selected intermittent
observations, not independent opportunity counts or a venue-wide census.

Snapshot evidence SHA256 is
`f5e32eaf445c35205c6a601f3122279add8cf4a611b521d415abeffa99efe8e4`; the
compressed snapshot file SHA256 is
`9dae1bbb7dedf502776040a7f8c1923b0f2933a44fdf7b6ff334188799109de9`. The v4
analysis event SHA256 is
`5955d3405c02cd42c98521c6ac7b12da53c1b0ccf9464cf8c91e9365ebad0189`; its
file SHA256 is
`7a8fbd22d1cbbe42d7ed6eb2ddd13a8d216975c9b3fa26f07f5ae1dead844c29`. The
19-snapshot research summary digest is
`4e90c788b2124caf6663ee3ee80762c29e44b62cf6c4c87bba2476a3584edc9c`.

## Finalized-source replay entered the campaign window

The 13:10:44 UTC scheduled replay completed successfully at 13:13:51 UTC. It
processed 128 finalized segments / 31,714,730 source bytes in 187 seconds,
using 9.34 CPU seconds and 141,037,568 bytes peak memory. The prefix now covers
1,676 of 3,432 cataloged segments (383,377,554 bytes), through ordinal
198,650; 1,756 finalized segments / 470,661,304 bytes remain pending.

The cumulative summary counts 15,469 campaign-window frame records, 11,367
touched market-frame states, and 11,000 quality-valid states. It still reports
zero positive top-ask and full-depth states. The replay is partial and reads
only finalized `.seg` files. Its sealed summary digest is
`03ace2c3d6761fdb92d6ed81df1e731ad3ed5cf3acda04d609b4b40f6fe27c4d`; the
summary file SHA256 is
`d5733cfdfd61e2fe702b79f6e4d894c9023761be7bd68168b3bb32725f6a8cb4`. The
state file SHA256 is
`e6911b540a07d54edd1e79db450ff80a855ac46c21a06ce24f4329d35970222a`.

## Director qualification

The 13:15 UTC Director cycle consumed the scan 19 v4 event and the 13:13
finalized-source summary, then admitted job
`job-a7320b92c7f0453ea32b1b79`. Arena completed all 19 events at 13:16:07 UTC
in 1.019 seconds. Finding `veritas-qualification-v1-6e262fb7c4325c0c` covers
760 selected pairs, 681 quality-valid pairs, 79 invalid pairs, and 326 unique
markets. It reports zero positive states at each of the five qualification
gates and retains the no-trade recommendation. The dataset SHA256 is
`a4319521f316e7e136d84d35cd26eea1864d4c404f4be2aaed8881c78c7c5675`; the
experiment SHA256 is
`896e16915e4fe43d065ce99b3b0da639e1ea332d8c6b4ad0b02d93c13ed00e27`; the
finding manifest SHA256 is
`e8f46a929377593b12c42e2a4ee9b6948bf390400383b16c43e399b22bf9a2d7`.

At checkpoint time the Arena job and finding were complete, but the Director
manifest still showed the admission as queued and scan 18 as the last
qualified scan. The 13:45 UTC scheduled cycle is the next reconciliation
point. No manual poll or retry was started.

The observer, source-analysis, and Director timers remain active. Their next
scheduled UTC runs are 13:31:21, 13:40:19, and 13:45:16. Mission 2 remains
active. Preserve the corrected source-window interpretation, the bounded
sampling limitations, and the unchanged zero-exposure baseline. Current state
is in [research inventory 020](VERITAS_MISSION2_RESEARCH_INVENTORY_020.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md).
