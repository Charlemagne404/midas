# Gate A checkpoint 022 — scan 24 and source replay progress

**Captured:** 2026-10-15 15:53 UTC  
**Branch:** project/veritas  
**Checkpoint base:** 9146100

## Prospective discovery and economics

The scheduled 15:30:20 UTC scan, scan-20261015T153020Z-4edb94c649e6, is the 24th finalized v4 snapshot. Six bounded Gamma frames returned 300 records and 300 unique IDs. The query union contained 176 supported same-condition V1 pairs and 124 explicit exclusions (73 augmented NegRisk records with unverified semantics and 51 unsupported outcome relationships). There were no duplicate records or identity conflicts.

The 40-market selection retained three available frozen controls and selected 37 rotating markets. Five of the eight frozen control IDs were unavailable in this query union. The scan overlaps scan 23 on five IDs: two rotating markets and three controls; 35 rotating selections changed. Liquidity counts were 15 high, 14 medium, and 11 low; expiry counts were 17 near, 19 medium, and four long; spread counts were 18 tight, 17 medium, and five wide. Selection used the category phase. Selection probabilities are conditional on the bounded response union and the frozen control cohort.

Thirty-four pairs passed the request/receipt quality gate; six had empty No ask sides. Seven of 40 passed the older reported-age/skew gate. The valid top-edge range was -$0.403 to -$0.001 per share, with a nearest-rank median of -$0.016. No top-ask, full-depth, per-leg minimum, single-match fee, or fragmentation-safe fee gate was positive.

Across 24 scans, the cumulative panel has 960 selected observations, 859 quality-valid pairs, 101 invalid pairs (96 empty No asks and five empty Yes asks), and 441 distinct markets. The prior reported-age/skew gate accepts 196 pairs. Paired recovery is 663/960 (69.06 percentage points). The 519 sampled state comparisons differ in 502 cases (96.72%); current activity bands are 39 higher-change, 55 lower-change, and 347 unclassified markets. These are selected, intermittent observations and correlated sample states, not independent opportunity counts or a venue-wide census.

Snapshot evidence SHA256 is 4edb94c649e629ce96f5e2fbd5419198a447c4e6e3de0534b57aa23d06dace7f; the compressed snapshot file SHA256 is 05557a0ea35b86be1372c2844fd9cb9b310859bf5407f08cde778918f0ac7f48 (629,296 bytes). The v4 analysis event SHA256 is dde94dde1d840c6f447fcb8c2ba2939b7facc0d9080ecd91ffeaf7e0aa312ab9; its file SHA256 is bed0f6c091a7ce055147d4059dfe6f3a357e84327c8bb1a5c520d344ded6772c (18,660 bytes). The 24-snapshot research summary digest is d33a2ecb71ab018b016dbf00724ebafd33fcdb442c239b573f9fb7e5b9745740; its file SHA256 is 335e5ce36838913a7d475b29231b481471c5f026d1cf7c941fc696729b93e575 (269,980 bytes).

## Finalized-source replay

The scheduled 15:40:45 UTC replay completed at 15:44:45 UTC. It processed 128 finalized segments / 32,016,580 source bytes in 225 seconds, using 11.290 CPU seconds. The peak memory value was not retained by systemd for this invocation. The prefix covers 2,289 of 3,727 cataloged finalized segments (548,436,826 bytes), through ordinal 287,107; 1,438 segments / 377,450,510 bytes remain pending. The batch stayed within the 128-segment and 32 MiB read bounds.

The cumulative campaign-window summary counts 84,112 frame records, 72,406 touched market-frame states, and 70,508 quality-valid states. Positive top-ask and full-depth states remain zero. The replay remains partial and reads finalized .seg files only. Its sealed summary digest is ed887a5443ff3348e5d39a1755ca75d2f8f1c615a545c18a4a2ffa3594a4a51a; summary file SHA256 is 799aa953db5a519e7cf9df7221ec103f5449830b7fbbced24e2b7a656e9528a8. State digest is f7b096d60949bd38bac2790fa8d4124bb8c9c77b867adfe134f00f9016a18723; state file SHA256 is 4780c76d45a3ae9553e3502de5726272ebfb0c2030ec2236da8a7e30e7537023. Prefix catalog digest is 7a3725f03f468e6e291b9e6fd9688647165f37c5cb88e78d43d61ea0bd9086fe. The final processed event was 00000000000000002289.json with internal event digest ca4584db5f8e44722d55a3e2913d257c653d67205f5d170ddd7405b0c31aa875 and file digest e785518bfcf1b35051f19846bfaea866f671ec6f14766e9d4adf8f479782c5e3.

## Director qualification

The 15:45:04 UTC Director cycle recorded scan 23 completion at 15:45:29, then admitted scan 24 at 15:45:31 using the 15:44:43 finalized-source summary. Arena completed all 24 events at 15:45:44 UTC in 1.418 seconds. Finding veritas-qualification-v1-564af5dc8f4b12eb reports no positive gross candidate. Its manifest file SHA256 is c1b52f5e8084892c84e77c604ba87fecf0eeac7cbe5d8afa4972461388d17c46; dataset SHA256 is df28b65d20ccec295e69163b5f1a5b1ca62de4685f9cc9b8d10440759e490872; experiment SHA256 is a88ba12f729b2e27b210021a3e51ea3716e093383b01afbd417ede9c9826e6d6.

The Director manifest was updated at 15:45:28 UTC and projects scan 24's job as QUEUED while its last qualified scan and latest finding remain scan 23. Arena's scan 24 job is complete; the next scheduled Director cycle at 16:15:11 UTC is the reconciliation point. No manual poll or retry was started.

The observer, source-analysis, and Director timers remain active. At inventory capture their next scheduled UTC runs were 16:00:04, 16:10:39, and 16:15:11. The observer store measured 22,696,673 bytes. Mission 2 remains active. See [Gate F checkpoint 012](VERITAS_MISSION2_GATE_F_CHECKPOINT_012.md), [research inventory 025](VERITAS_MISSION2_RESEARCH_INVENTORY_025.json), [operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md).
