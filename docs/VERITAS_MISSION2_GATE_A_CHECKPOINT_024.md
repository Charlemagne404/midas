# Gate A checkpoint 024 — scan 26 and source replay progress

**Captured:** 2026-10-15 16:48 UTC  
**Branch:** project/veritas  
**Checkpoint base:** 3e993fe

## Prospective discovery and economics

The scheduled 16:30:54 UTC scan, scan-20261015T163054Z-7f7265f6f8fe, is the 26th finalized v4 snapshot. Six bounded Gamma frames returned 300 records and 289 unique IDs; 11 records were repeated across frames and zero identity conflicts were found. The 11 repeated records were identical payloads: ten appeared in the high-liquidity and near-expiry frames, and one in the high-liquidity and rotating-ID frames. The deduplicated union contained 169 supported same-condition V1 pairs and 120 explicit exclusions (90 augmented NegRisk records with unverified semantics and 30 unsupported outcome relationships).

The 40-market selection retained three available frozen controls and selected 37 rotating markets in the snapshot-change phase. It overlaps scan 25 on seven IDs (four rotating and three controls); 33 rotating selections changed. Liquidity counts were 21 high, seven medium, and 12 low; expiry counts were 24 near, 12 medium, and four long; spread counts were 24 tight, 12 medium, and four wide. Selection probabilities remain conditional on the bounded response union and frozen controls.

Thirty-four pairs passed the request/receipt quality gate; six had empty No ask sides. Ten of 40 passed the older reported-age/skew gate. The valid top-edge range was -$0.400 to -$0.001 per share, with a nearest-rank median of -$0.010. No top-ask, full-depth, per-leg minimum, single-match fee, or fragmentation-safe fee gate was positive.

Across 26 scans, the cumulative panel has 1,040 selected observations, 928 quality-valid pairs, 112 invalid pairs (106 empty No asks and six empty Yes asks), and 480 distinct markets. The older reported-age/skew gate accepts 213 pairs. Paired recovery is 715/1,040 (68.75 percentage points). Of 560 sampled state comparisons, 542 differ (96.79%); current activity bands are 36 higher-change, 60 lower-change, and 384 unclassified markets. These remain intermittent selected observations and correlated states, not independent opportunity counts or a venue-wide census.

Snapshot evidence SHA256 is 7f7265f6f8fe588da1d10548d3bac7db7dac322d9480349045e416d003b189ef; compressed snapshot file SHA256 is 4a27811f714fa462be48c24e6abf0ee088886b1daf2a960ae917df97619f4fa5 (641,131 bytes). The v4 analysis event SHA256 is af1855d877e1485d7781c81cab089bd359a7764616670ca36ffae5509ca196d3; its file SHA256 is 9535004ce7eb064cb5138dfc0fd97164e4152fe5be494c9e868fa534b21f51d9 (18,484 bytes). The 26-snapshot research summary digest is 1f114aef2ac3d1cbb569426e88632baa1675c028cd073837c600150ad801acfa; its file SHA256 is 4e87240e845e33f7725598373e2f6ed21ecdeaf4e5aa7c9df923152fc0711d1b (293,176 bytes).

## Finalized-source replay

The scheduled 16:40:08 UTC replay completed at 16:43:49 UTC. It processed 128 finalized segments / 33,042,875 source bytes in 221 seconds, using 11.037 CPU seconds. Systemd did not retain a peak memory value. The prefix covers 2,545 of 3,844 cataloged finalized segments (613,809,470 bytes), through ordinal 320,213; 1,299 segments / 356,461,487 bytes remain pending. The batch stayed within the 128-segment and 32 MiB read bounds.

The campaign-window summary counts 108,912 frame records, 95,468 touched market-frame states, and 93,007 quality-valid states. Positive top-ask and full-depth states remain zero. Replay remains partial and reads finalized .seg files only. Sealed summary digest is c28e4f92547264dfa8d41ba28101357b8e498ddd2816a96af73c103f0f05ca74; summary file SHA256 is 614f4a13f8508b80b9c180a255f08d971548b0c707c8a7acad78160b3cbe3e45. State digest is cbbffcf77c1ed5fbd44cff1b37345d8485f16785e88bb623a7660e95fef60070; state file SHA256 is 3d416c9d81107dfaf1c3d74e157d92a070f00c4eb6cbf4dc69cea09d678bb0ac. Prefix catalog digest is e12ef61bbf5dd36475631e20907a77fb85d1936428d60c8698f62c16fba4d5f4. Latest processed event 00000000000000002545.json has internal digest db5c7684e4fd6a9c3e87c3d3cbba14c12132e2bd67bd0efb7c726e7c5cd14340 and file digest bb9529f82dedf5ad770dd0d4ff52aa0d22b3ea392f84d9124a0468d72a6c78bb.

## Director qualification

The 16:45:04 UTC Director cycle recorded scan 25 completion at 16:45:29 and admitted scan 26 at 16:45:31 using the 16:43:46 finalized-source summary. Arena completed all 26 events at 16:45:44 UTC in 1.525 seconds. Finding veritas-qualification-v1-0d41b647a6d03623 reports no positive gross candidate. Finding manifest SHA256 is 9987fabed0366789ba0c94a329820f20d6d552e5e97e19f0687663ef0febb307; dataset SHA256 is 08cfdaad91bdaaa42eb94225947ee0c2760eee0cc3bd9b89fd2db2309446c86e; experiment SHA256 is 3046c819243807fad858750a47825c3fa0e85930f3f94c23fb72f855a82c79a3.

The Director manifest was updated at 16:45:28 UTC and still projects scan 26's job as QUEUED while its last qualified scan and latest finding remain scan 25. Arena's scan 26 job is complete; the 17:15:09 UTC scheduled Director cycle is the reconciliation point. No manual poll or retry was started.

The observer, source-analysis, and Director timers remain active. At inventory capture their next scheduled UTC runs were 17:00:53, 17:10:13, and 17:15:09. The observer store measured 24,568,313 bytes. Mission 2 remains active. See [Gate F checkpoint 014](VERITAS_MISSION2_GATE_F_CHECKPOINT_014.md), [research inventory 027](VERITAS_MISSION2_RESEARCH_INVENTORY_027.json), [operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md).
