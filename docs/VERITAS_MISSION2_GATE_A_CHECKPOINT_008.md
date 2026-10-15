# Veritas Mission 2 Gate A Checkpoint 008 — Per-Market Coverage and Paired Gate Reclassification

- **Captured:** 2026-10-15 08:33 UTC
- **Branch:** `project/veritas`
- **Analysis:** `veritas-finalized-snapshot-analysis-v4`
- **Status:** v4 measurement and coverage outputs implemented; periodic observation continues.

## Changes

The incremental snapshot analyzer now preserves separate v1–v3 state and event histories and writes v4 events. For every selected market it accumulates selected and valid observations, first/last observation time, the sampled YES/NO book-state fingerprint, fingerprint transitions, and results under the previous reported-age/skew gate. The summary explicitly limits these transition counts to sampled snapshots; they are not venue update rates.

The same saved pairs are assessed under two gates: the prior 5-second reported-update-age and 250 ms cross-outcome-skew requirements, and the current request-to-receipt requirement with the existing pair and book checks. This comparison isolates measurement yield on common evidence. It does not establish batch atomicity, venue sequence, or upstream queue age.

## Evidence at capture

- Eleven finalized snapshots cover 05:59:28–08:31:53 UTC (about 152 minutes), with 440 selected market observations and 156 distinct market IDs.
- The corrected gate accepts 396/440 pairs (90.0%); the previous gate accepts 98/440 (22.3%). The paired difference is +298 pairs / +67.7 percentage points.
- Previous-gate failures are 298 pairs with reported age above 5 seconds, 42 empty NO ask sides, and two empty YES ask sides. The corrected gate retains those 44 empty-ask invalid pairs.
- The 156 markets have 284 consecutive sampled state comparisons; 271 fingerprints differ. 54 markets are in the `higher_sampled_change` band, eight in `lower_sampled_change`, and 94 remain unclassified under the minimum sample/span rule. These bands describe this sparse snapshot schedule only.
- The detector recorded zero positive top-ask gross states. The separate qualification run over the same 359 valid states also found zero positive states at full displayed depth, per-leg minimums, single-match fees, and the fragmentation-safe fee sensitivity.
- The latest scan (`scan-20261015T083153Z-1d45d1808d34`) has 37/40 current-gate-valid pairs and zero positive top-ask gross pairs. Latest strata: liquidity high 9 / medium 14 / low 17; expiry near 7d 17 / medium 90d 22 / long 1; spread tight 9 / medium 15 / wide 16.
- Latest bounded discovery union: 300 unique IDs, 167 supported same-condition V1 binary pairs, 133 explicit exclusions (83 unverified augmented negative-risk semantics; 50 unsupported outcome relationships). The selected panel remains 40 markets: 34 rotating and six available frozen controls.

## Interpretation and next step

The gate repair materially increases usable-pair measurement in these saved batches. It is not evidence of more opportunity, independent validation, executable quotes, fills, or profitability. The rolling v4 analyzer now applies the paired classification to every newly finalized snapshot. Keep collection running and require an independent freshness/sequence source before treating request-receipt timing as a venue-time guarantee.

Artifacts: `data/veritas-observatory/research-summary.json` (analysis summary digest `4be7df782c5acbbc57f7c1c3d9491219eaf4161aace4089b1d3183e2bd040970` at this capture) and experiment `VERITAS-M2-ECO-QUAL-001-RUN-95f8752f5291` (dataset SHA256 `95f8752f52913461a03c20f020c5ca0f56add927584823f7da673c458b570beb`). The 11-snapshot experiment has zero positive states at every gate; its top-edge median is -0.028 and maximum is -0.001 per share. These runtime artifacts are ignored by Git; a versioned inventory records their hashes.

The finalized Reality source replay remains separate, read-only, and behind its 128-segment-per-run catch-up. No Reality data or service was changed. No orders, wallet, authenticated API, or real-money activity occurred.
