# Project Veritas Mission 2 — Engineering Checkpoint Report

**Status:** Discovery, measurement repair, snapshot and source-segment analysis,
the qualification experiment, and dashboard checkpoint are implemented and
running. Mission 2 remains open while source catch-up, observation, and
dependence evidence accumulate.
**Date:** 2026-10-15
**Branch:** `project/veritas`
**Starting commit:** `9a857cc56804bec6b7129171ba090d338e263aa3`

## What changed

Veritas now has a bounded public market-discovery and snapshot service, a
stratified 40-market panel with frozen random controls, an independently tested
same-condition YES/NO audit, and separate idempotent analyzers for finalized
public snapshots and finalized Reality source segments. The old timestamp-only
freshness gate was repaired after the pilot showed it rejecting books whose
reported update was old even though the book
payload had just returned within a short batch. The dashboard and read-only API
surface discovery strata, source-quality counts, candidate gates, research
readiness, and snapshot evidence.

The first finalized-source batch processed 128 of 2,681 replayable segments
through ordinal 7,048. The analyzer has 2,553 segments (648,266,578 bytes)
pending and remains in `catching_up_finalized_source`; this initial source
prefix contains no campaign-window frames. See [checkpoint 003](VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md)
for campaign, code, event, summary, and runtime hashes.

An active 30-minute timer runs the bounded scanner and snapshot analyzer. A
second offset 30-minute timer advances a read-only, resumable Reality source
replay. The source reader is pinned to the frozen campaign hash and source root,
ignores `.open` files, and processes at most 128 finalized segments or 32 MiB
per run under 5% CPU and 256 MiB memory. Neither service changes Reality.

## Evidence at this checkpoint

- Latest bounded union: 300 unique market IDs; 167 supported V1 binary pairs;
  133 excluded with explicit reasons (81 unverified augmented negative-risk
  semantics, 52 unsupported outcome relationships).
- Latest selection: 40 markets, six available frozen controls, 34 rotating;
  liquidity, expiry, category, and spread strata are present.
- Seven immutable snapshots from 05:59:28 to 06:31:03 UTC: 280 selected market
  observations, 248 quality-valid pairs, 32 empty-ask invalids, 133 distinct
  market IDs, zero analyzer backlog.
- Current descriptive readiness: `collecting_repeated_temporal_coverage`.
  This 31-minute window does not meet the 24-hour dependence-review readiness
  threshold or the earlier specific study's 48-hour gate.
- The paired same-snapshot freshness reclassification changed valid yield from
  5/40 (12.5%) to 32/40 (80.0%): +27 pairs and +67.5 percentage points on the
  exact same saved payload. Batch atomicity and upstream queue age remain
  unverified.
- `VERITAS-M2-ECO-QUAL-001` run
  `VERITAS-M2-ECO-QUAL-001-RUN-7878566d1ffb`, using 248 quality-valid pairs,
  found zero positive
  top-ask gross, 20-share depth, minimum-notional, single-match-fee, or
  fragmentation-safe-fee states. Top-edge range was -0.984 to -0.001 per share;
  median nearest-rank edge was -0.028. The result supports no-trade today; it
  does not establish absence across the venue or profitability.

The post-commit timer scan succeeded and analysis v2 indexed exactly one new
snapshot. The seven-snapshot run has a deterministic ID derived from its input
manifest; the first economic result remains preserved separately.
The refreshed result is [economic run 002](../data/veritas-observatory/experiments/VERITAS-M2-ECO-QUAL-001-RUN-002.json).

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

The snapshot pipeline detects newly finalized public scans; the source pipeline
replays bounded finalized Reality segments and resumes from its serialized
reconstruction context. Each verifies source and event digests, updates its
own summary idempotently, and exposes separate readiness. Neither rewrites
campaign policies, models, source records, or historical results.

## Verification and preservation

- Full Veritas backend test selection: 83 passed; one Starlette/httpx
  deprecation warning.
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
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md),
[`VERITAS_MISSION2_RESEARCH_INVENTORY.json`](VERITAS_MISSION2_RESEARCH_INVENTORY.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_002.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_002.json),
and [`VERITAS_MISSION2_RESEARCH_INVENTORY_003.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_003.json).

## Next evidence gates

1. Keep both read-only timers active, let the source analyzer catch up in
   bounded batches, and accumulate a longer public observation window.
2. Review dependence only after at least 24 hours and adequate market diversity;
   do not claim the specific 48-hour follow-up design is ready until its stated
   gates pass.
3. Validate request-receipt freshness against a source with sequence or
   equivalent freshness guarantees.
4. Expand discovery only after measuring rate, coverage, host resources, and
   storage on the current frame.
5. Continue no-trade and no-model status until a quality-valid positive gross
   candidate supplies appropriate real labels for further economic research.
