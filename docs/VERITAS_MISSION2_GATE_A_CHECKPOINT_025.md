# Gate A checkpoint 025 — scan 27 and source replay progress

**Captured:** 2026-10-15 17:16 UTC  
**Branch:** `project/veritas`  
**Checkpoint base:** `0cedcad`

## Prospective discovery and economics

The scheduled 17:01:12 UTC scan, `scan-20261015T170112Z-de5e990dcdf5`, is the 27th finalized v4 snapshot. Six bounded Gamma frames returned 300 records and 298 unique IDs. Two repeated records were identical and there were no identity conflicts. The deduplicated union contained 123 supported same-condition V1 binary pairs and 175 explicit exclusions: 121 augmented NegRisk records with unverified semantics and 54 unsupported outcome relationships.

The 40-market selection retained four available frozen controls and selected 36 rotating markets in the liquidity phase. It overlaps scan 26 on seven IDs (four rotating and three controls); 32 of 36 rotating selections changed. Liquidity counts were 12 high, nine medium, and 19 low; expiry counts were 22 near, 17 medium, and one long; spread counts were 19 tight, 11 medium, and 10 wide. Selection probabilities remain conditional on the bounded response union and frozen controls.

Thirty-three pairs passed the request/receipt quality gate; seven had empty No ask sides. Ten of 40 passed the older reported-age/skew gate. Valid top-edge values ranged from -$0.848 to -$0.001 per share, with nearest-rank median -$0.020. No top-ask, full-depth, per-leg minimum, single-match fee, or fragmentation-safe fee gate was positive.

Across 27 scans, the cumulative panel has 1,080 selected observations, 961 quality-valid pairs, 119 invalid pairs (113 empty No asks and six empty Yes asks), and 494 distinct markets. The older reported-age/skew gate accepts 223 pairs. Paired recovery is 738/1,080 (68.33 percentage points). Of 586 sampled state comparisons, 568 differ (96.93%). These are intermittent selected observations and correlated states, not independent opportunity counts or a venue-wide census.

Snapshot evidence SHA256 is `de5e990dcdf55a1bff57cb7d4941ade8663ea35d4e4bd29d69bde86d548517fd`; compressed snapshot file SHA256 is `64f1d21d402e2bf6a86c38d0fcda8a0f755624b3fb382b054409c1089183382a` (691,952 bytes). The v4 analysis event SHA256 is `66b1a65f12d2f659338c244f4c80396817936dc67818e64a87b1499a216f1f4b`; its file SHA256 is `b8fe328d92b130ab62218aaa9842eecb01bad5809f8e54eec615924dc71ad3e3` (18,373 bytes). The 27-snapshot research summary digest is `558248150c48eaca9cf2d09193354b1ea3833c3a8457d2a95dd0e3d905a064ff`; its file SHA256 is `5ca097e9688564d386d58a8e70785ea090a9c8fd0bb59a4395f2205269f3b822`.

## Finalized-source replay

The scheduled 17:10:17 UTC replay completed at 17:14:19 UTC. It processed 116 finalized segments / 33,217,726 source bytes in 242 seconds, using 12.138 CPU seconds and 122.3 MiB peak memory. The prefix covers 2,661 of 3,903 cataloged finalized segments (647,027,196 bytes), through ordinal 340,035; 1,242 segments / 344,457,128 bytes remain pending. The batch stayed within the 128-segment and 32 MiB read bounds.

The campaign-window summary counts 124,922 frame records, 110,158 touched market-frame states, and 107,340 quality-valid states. Invalid reasons include 2,226 empty ask sides, 339 independent-book divergences, 140 reported expiries, 82 source-timing uncertainties, and 31 top-divergence book issues. Positive top-ask, full-depth, and per-leg minimum states remain zero. Replay remains partial and reads finalized `.seg` files only. Sealed summary digest is `46d3ed07c0bb8a519d0053fcffe7dfb975fabf6adc5ba1d8a9ea737c8cc18899`; summary file SHA256 is `c009c625140c311d53f334a08e5a52dcfaaa914cca6ca628688135591af3eabe`. State digest is `2f14a6f8157f6c8425b3ddac22d802e5e75cd60c1e79c7b76c4ebc3c2579015d`; state file SHA256 is `cc8cceb0af5a01fb4986647074e9ca83a4ceccf426b5ec98fe2a2a5a08ea9d4c`. Prefix catalog digest is `38c36f9192b1799ee7f5074b11a36b4dca45136b02b5446d24c8503df2215828`.

## Director qualification

The 17:15:09 UTC Director cycle admitted a scan-pinned qualification for scan 27 using the 17:14:16 UTC sealed source summary. Arena completed all 27 events at 17:15:51 UTC in 1.619 seconds. Finding `veritas-qualification-v1-b595559921e55264` reports no positive gross candidate at any of the five qualification gates. Finding manifest SHA256 is `bd6f00e2d3423c8284e13f61828926c2e101f5226b0271a425246275e91b934a`; dataset SHA256 is `08363598d19c509dcbf48ff77d83197e24cdc58032a801d61f3bb85d2e08b8b7`; experiment SHA256 is `554b2180964ef796f3f891901307e5829d7fcb7aa737516595cba070284c9464`.

The Director manifest was updated at 17:15:34 UTC and still projects scan 27's job as `QUEUED` while scan 26 remains its last qualified scan. Arena's scan 27 job is complete; the 17:45:25 UTC scheduled Director cycle is the reconciliation point. No manual poll or retry was started.

The observer, source-analysis, and Director timers remain active. At capture their next scheduled UTC runs were 17:31:45, 17:40:03, and 17:45:25. The observatory store was about 32 MB, below the 1 GiB cap. Mission 2 remains active. See [Gate F checkpoint 015](VERITAS_MISSION2_GATE_F_CHECKPOINT_015.md), [research inventory 028](VERITAS_MISSION2_RESEARCH_INVENTORY_028.json), [operations](VERITAS_MISSION2_OPERATIONS.md), and [engineering](VERITAS_MISSION2_ENGINEERING.md).
