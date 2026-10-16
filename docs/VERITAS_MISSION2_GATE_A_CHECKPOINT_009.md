# Veritas Mission 2 Gate A Checkpoint 009 — Twelfth Prospective Snapshot

- **Captured:** 2026-10-15 09:00:47 UTC
- **Indexed:** 2026-10-15 09:00:52 UTC
- **Branch base:** `48fcfc27f42b4ae68a06182cfeb1ff936260de67`
- **Analysis:** `veritas-finalized-snapshot-analysis-v4`
- **Status:** the bounded paired measurement panel and no-candidate economic qualification continue prospectively.

## Latest observation

The scheduled public observer captured `scan-20261015T090047Z-6f98ffeaecab` for 40 selected markets. It found 35 request/receipt-valid pairs and five empty-NO-ask invalids. The observation used six bounded Gamma frames over 300 IDs; 167 same-condition V1 binary pairs were eligible and 133 were excluded (83 with unverified augmented negative-risk semantics and 50 with unsupported outcome relationships). The panel uses 34 rotating selections and six available frozen controls. The selected strata were liquidity high/medium/low 9/16/15, expiry near/medium/long 18/21/1, and spread tight/medium/wide 16/12/12.

The cumulative panel now contains 12 snapshots from 05:59:28 to 09:00:47 UTC (181.31 minutes), 480 selected market observations, 431 valid pairs, 49 invalid pairs, and 161 distinct market IDs. The previous reported-age/skew gate accepts 107/480, while the current request/receipt gate accepts 431/480. This paired measurement difference is +324 observations, or +67.50 percentage points. The valid-yield rates are 89.79% and 22.29%, respectively.

Across the sampled market fingerprints, 319 adjacent comparisons differ in 304 cases. The API bands 54 markets as higher sampled change, 15 as lower, and 92 as unclassified under the minimum sample/span rule. The remaining markets have no qualifying classified interval. This is intermittent snapshot-to-snapshot evidence; it is not a venue update rate.

## Economic qualification

The refreshed deterministic run is `VERITAS-M2-ECO-QUAL-001-RUN-b401cd384481`, dataset SHA256 `b401cd38448145e0d384d5c58bfa6e16251b85d28d5febe20d65e30ef6880300`. It compares the unchanged top-ask gross-sign baseline with 20-share full displayed depth, per-leg minimum notionals, and single-match and fragmentation-safe fee sensitivities on 431 valid states across 161 markets. All five positive-state counts remain zero. The nearest-rank median top edge is -0.028 per share and the maximum is -0.001. The run measures qualification, not strategy PnL, execution or fills. No authenticated request or order was made.

Artifact `data/veritas-observatory/experiments/VERITAS-M2-ECO-QUAL-001-RUN-b401cd384481.json` has file SHA256 `56342c6734ec6a6af267553204a49ed918e3a30e38c33888c501ccbd76bb7501`. Latest analysis summary SHA256 is `970c44e0bb07d671889bbd3516457931b4f3285f821f58b699d85126214b5731`. The indexed analysis has zero pending snapshots.

## Operations and limits

The observer timer and separate source-analysis timer are active. The observer root uses 9,865,838 bytes against its 1 GiB bound. The Reality source analyzer remains `catching_up_finalized_source` at 658/2,899 replayable finalized segments with 2,241 pending (610,777,450 bytes) through ordinal 39,776; its processed prefix contains zero campaign-window frames. The protected Reality checkout remains clean at `714f824`; no Reality writer was changed or restarted.

The public panel remains bounded, selected and correlated. The 181-minute interval is short of the 24-hour pilot review and the original prospective study's 48-hour coverage and dependence requirements. Request/receipt time is not venue sequence or batch-atomicity proof. No positive gross candidate exists, so strategy comparison, training, and promotion remain unsupported.

The immutable 12-snapshot lineage, v4 cumulative coverage, current timer state and 08:44 UTC Gate C snapshot are recorded in [research inventory 010](VERITAS_MISSION2_RESEARCH_INVENTORY_010.json). The previous 11-snapshot inventory 009 and Gate A checkpoint 008 remain preserved.
