# Project Veritas Mission 2 — Engineering Checkpoint Report

**Status:** The discovery, measurement-repair, continuous-analysis, experiment,
and dashboard checkpoint is implemented and running. Mission 2 remains open
while the observation window and dependence evidence accumulate.
**Date:** 2026-10-15
**Branch:** `project/veritas`
**Starting commit:** `9a857cc56804bec6b7129171ba090d338e263aa3`

## What changed

Veritas now has a bounded public market-discovery and snapshot service, a
stratified 40-market panel with frozen random controls, an independently tested
same-condition YES/NO audit, and an idempotent analyzer over immutable finalized
snapshots. The old timestamp-only freshness gate was repaired after the pilot
showed it rejecting books whose reported update was old even though the book
payload had just returned in a short batch. The dashboard and read-only API
surface discovery strata, source-quality counts, candidate gates, research
readiness, and snapshot evidence.

An active 30-minute timer runs the bounded scanner and incremental analyzer
without changing Reality. It is limited to 40 markets, one second between
public requests, seven planned requests per scan, 5% CPU, 256 MiB memory, and a
1 GiB data root.

## Evidence at this checkpoint

- Latest bounded union: 300 unique market IDs; 167 supported V1 binary pairs;
  133 excluded with explicit reasons (81 unverified augmented negative-risk
  semantics, 52 unsupported outcome relationships).
- Latest selection: 40 markets, six available frozen controls, 34 rotating;
  liquidity, expiry, category, and spread strata are present.
- Six immutable snapshots from 05:59:28 to 06:22:59 UTC: 240 selected market
  observations, 211 quality-valid pairs, 29 empty-ask invalids, 121 distinct
  market IDs, zero analyzer backlog.
- Current descriptive readiness: `collecting_repeated_temporal_coverage`.
  This 23-minute window does not meet the 24-hour dependence-review readiness
  threshold or the earlier specific study's 48-hour gate.
- The paired same-snapshot freshness reclassification changed valid yield from
  5/40 (12.5%) to 32/40 (80.0%): +27 pairs and +67.5 percentage points on the
  exact same saved payload. Batch atomicity and upstream queue age remain
  unverified.
- `VERITAS-M2-ECO-QUAL-001`, using 211 quality-valid pairs, found zero positive
  top-ask gross, 20-share depth, minimum-notional, single-match-fee, or
  fragmentation-safe-fee states. Top-edge range was -0.60 to -0.001 per share;
  median nearest-rank edge was -0.022. The result supports no-trade today; it
  does not establish absence across the venue or profitability.

## Measurement yield and limits

The freshness change materially reduces timestamp-based false exclusions in a
paired replay. Because it reclassifies one saved scan, the yield change is an
instrumentation result, not an independent prospective economic result. The
active periodic panel will collect future observations under the repaired
protocol. Public book timestamps remain diagnostics and do not prove quote
availability, matching sequence, order arrival, or fills.

The original prospective follow-up design remains gated on sufficient coverage
and dependence analysis. This separate public snapshot pilot does not bypass
those gates. It provides a safe, recurring alternative for market-discovery and
measurement coverage while the required window grows.

## Experiment and readiness decision

The end-to-end comparison is deliberately a candidate-qualification experiment:
the unchanged baseline uses same-condition top asks; the improvement requires
complete displayed depth at 20 shares and both per-leg USDC minimums, then
reports two fee sensitivities. Every gate remained at zero in real public
observations. There are no real candidate labels to justify model training or a
strategy tournament. No strategy or model was promoted.

The recurring pipeline detects new finalized snapshots, verifies source and
event digests, updates coverage and opportunity counts idempotently, and exposes
a readiness state. It does not autonomously rewrite code, campaign policies,
models, or historical results.

## Verification and preservation

- Targeted Veritas Python/API tests: 34 passed.
- Ruff and Mypy on the new observation, analysis, experiment, and test code:
  passed.
- Frontend tests: 29 passed; typecheck, lint, and production build passed. The
  build retains a large-chunk advisory.
- Veritas Playwright workflow passed. The broad seven-workflow browser run had
  six passes and one Reality UI assertion failure: its exact `Yes` heading was
  absent. No Reality source code was changed.
- The separate Reality checkout remained clean at `714f824`; active Reality
  services and timers were not restarted or modified. Oct 14 exit-code statuses
  from three unrelated Reality test/canary units were observed and left alone.
- No orders, wallets, deposits, credentials, or authenticated requests were
  used. Historical Reality, Prometheus, Arena, Laboratory, and existing Veritas
  evidence remains outside the write set.

Detailed implementation and commands are in
[`VERITAS_MISSION2_ENGINEERING.md`](VERITAS_MISSION2_ENGINEERING.md),
[`VERITAS_MISSION2_OPERATIONS.md`](VERITAS_MISSION2_OPERATIONS.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md),
and [`VERITAS_MISSION2_RESEARCH_INVENTORY.json`](VERITAS_MISSION2_RESEARCH_INVENTORY.json).

## Next evidence gates

1. Keep the recurring observer active and accumulate a longer window.
2. Review dependence only after at least 24 hours and adequate market diversity;
   do not claim the specific 48-hour follow-up design is ready until its stated
   gates pass.
3. Validate request-receipt freshness against a source with sequence or
   equivalent freshness guarantees.
4. Expand discovery only after measuring rate, coverage, host resources, and
   storage on the current frame.
5. Continue no-trade and no-model status until a quality-valid positive gross
   candidate supplies appropriate real labels for further economic research.
