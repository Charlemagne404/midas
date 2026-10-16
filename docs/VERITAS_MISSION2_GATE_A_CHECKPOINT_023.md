# Gate A checkpoint 023 — scan 25 and source replay progress

**Captured:** 2026-10-15 16:18 UTC  
**Branch:** project/veritas  
**Checkpoint base:** 6c8f08e

## Prospective discovery and economics

The scheduled 16:00:14 UTC scan, scan-20261015T160014Z-63b12b6b8d54, is the 25th finalized v4 snapshot. Six bounded Gamma query frames returned 300 records, 297 unique IDs, three cross-query duplicates, and zero identity conflicts. The deduplicated union contained 121 supported same-condition V1 pairs and 176 explicit exclusions (110 augmented NegRisk records with unverified semantics and 66 unsupported outcome relationships).

The 40-market selection retained three available frozen controls and selected 37 rotating markets in the spread phase. It overlaps scan 24 on five IDs (two rotating and three controls); 35 rotating selections changed. Liquidity counts were six high, 13 medium, and 21 low; expiry counts were 21 near, 14 medium, and five long; spread counts were 16 tight, 13 medium, and 11 wide. Selection probabilities remain conditional on the bounded query-response union and frozen controls.

Thirty-five pairs passed the request/receipt quality gate; four had empty No asks and one had an empty Yes ask. Seven of 40 passed the older reported-age/skew gate. The valid top-edge range was -$0.996 to -$0.001 per share, with a nearest-rank median of -$0.020. No top-ask, full-depth, per-leg minimum, single-match fee, or fragmentation-safe fee gate was positive.

Across 25 scans, the cumulative panel has 1,000 selected observations, 894 quality-valid pairs, 106 invalid pairs (100 empty No asks and six empty Yes asks), and 460 distinct markets. The older reported-age/skew gate accepts 203 pairs. Paired recovery is 691/1,000 (69.10 percentage points). Of 540 sampled state comparisons, 522 differ (96.67%); current activity bands are 37 higher-change, 59 lower-change, and 364 unclassified markets. The observations are intermittent, selected, and correlated; they are not independent opportunity counts or a venue-wide census.

Snapshot evidence SHA256 is 63b12b6b8d54502847627a8a98526769fd7c4e759eda6ee3d4c1083dd3059ba2; compressed snapshot file SHA256 is 39bf8d9dc7cef0f6a08f5867c024f35d5b7674dd5b98ffda50267e75c35eb821 (668,623 bytes). The v4 analysis event SHA256 is 4fe4cc75380d6fda27e218a8cd4ade830d50a730909e151956be17f6f5d6658f; its file SHA256 is 9dab8bff2820de7629f2be758a6f5c3d21f24d1382690912b5101afdcb92b45f (18,177 bytes). The 25-snapshot research summary digest is 77c455394927f969c9355761ce858cc06cbf907c1a144bc49c830daa65a37bd5; its file SHA256 is eec7e77f3d26502c80562a9be1a8d7c3a989e78eae76b6848681e0fbf728c9c9 (281,269 bytes).

## Finalized-source replay

The scheduled 16:10:39 UTC replay completed at 16:14:31 UTC. It processed 128 finalized segments / 32,329,769 source bytes in 227 seconds, using 11.347 CPU seconds. The peak memory value was not retained by systemd. The prefix covers 2,417 of 3,786 cataloged finalized segments (580,766,595 bytes), through ordinal 303,638; 1,369 segments / 372,776,598 bytes remain pending. The batch stayed within the 128-segment and 32 MiB read bounds.

The campaign-window summary counts 96,535 frame records, 84,138 touched market-frame states, and 81,994 quality-valid states. Positive top-ask and full-depth states remain zero. Replay remains partial and reads finalized .seg files only. Sealed summary digest is 4e8f84ea69ba9ad1970495b3981feb3136b086367edef693a07be2a4e4351b9a; summary file SHA256 is af1523f3e1c3b60c75d1ae0eb6f29a9d3351a83c013cee2565a68a480341c335. State digest is bcd5ceb3ca89c6af5bb3b3c9d22b279f1931ef42cc8ba7eaa24b978f48aa5c6c; state file SHA256 is d37d5acdd9a17c57eae5cc19e28750277709f25f50bd22413102412ad9066a40. Prefix catalog digest is 44390757bd69b3d3d80991ea77ee88835887176d58cf64091e10f94f4cf0015d. The latest processed event is 00000000000000002417.json, with internal digest ea81f6c44be2f47e7141bae399a9051f53f58bb01e74e51d1e8ff4fcfd6f036b and file digest e06891ab0c68ed63addd266ef9307e957e6ad99f74f1090325432f2680c92946.

## Director qualification

The 16:15:14 UTC Director cycle recorded scan 24 completion at 16:15:40 and admitted scan 25 at 16:15:42 using the 16:14:28 finalized-source summary. Arena completed all 25 events at 16:15:55 UTC in 1.514 seconds. Finding veritas-qualification-v1-454c6e2d83426f98 reports no positive gross candidate. Finding manifest SHA256 is d4723d6f505af2bbbc04dd671d66a1008964abce0378b3e8e35899ed396406d7; dataset SHA256 is f8e91d98d0c251402c82d8ddc51ae6bb26fbf98022d76cca9ae959aaf5e89ddd; experiment SHA256 is 82fbcb05fc28a10bd5321e713e17df6f46edcb6f8637bf380e9c6af85ce0793f.

The Director manifest was updated at 16:15:39 UTC and still projects scan 25's job as QUEUED while its last qualified scan and latest finding remain scan 24. Arena's scan 25 job is complete; the 16:45:03 UTC scheduled Director cycle is the reconciliation point. No manual poll or retry was started.

The observer, source-analysis, and Director timers remain active. At inventory capture their next scheduled UTC runs were 16:30:42, 16:40:08, and 16:45:03. The observer store measured 23,646,132 bytes. Mission 2 remains active. See [Gate F checkpoint 013](VERITAS_MISSION2_GATE_F_CHECKPOINT_013.md), [research inventory 026](VERITAS_MISSION2_RESEARCH_INVENTORY_026.json), [operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md).
