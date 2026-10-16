# Veritas Mission 2 Measurement Coverage Pilot 001

**Identity:** `VERITAS-M2-MEASURE-PILOT-001`
**Protocol version:** `veritas-bounded-snapshot-coverage-v1`
**Status:** Active, read-only engineering pilot
**Started:** 2026-10-15 UTC
**Evidence cutoff:** 2026-10-15 06:22:59 UTC

## Question

Can a bounded, price-blind public snapshot panel measure more eligible market
conditions and recover paired books that the previous reported-update-age gate
classified as stale, while keeping quality limits, source lineage, and resource
use explicit?

This is a market-discovery and measurement pilot. It is not the separate
prospective follow-up study described in
[`VERITAS_GATE_A_FOLLOWUP_DESIGN_002.md`](VERITAS_GATE_A_FOLLOWUP_DESIGN_002.md).
That study's 48-hour subscription-coverage, nine-market, and dependence-analysis
gates remain in force. The snapshot pilot gathers broader intermittent public
observations while those gates remain unmet; it does not claim to satisfy them.

## Frozen protocol

- Discover a bounded union from six public Gamma query frames covering high,
  medium, and low displayed liquidity; near expiry; tagged near expiry; and a
  rotating ID frame.
- Preserve all returned market records, duplicate and identity checks, explicit
  exclusions, query parameters, response hashes, and the discovery source hash.
- Restrict pair economics to verified same-condition V1 binary YES/NO markets.
  Unsupported outcome relations and unverified augmented negative-risk
  semantics are retained with exclusion reasons.
- Select up to 40 markets without conditioning on price edge: a frozen random
  control cohort plus deterministic rotating strata over liquidity, expiry,
  category, spread, and sampled-snapshot change. Probabilities are conditional
  on the bounded query union and frozen controls.
- Target eight stable controls. If a frozen ID is absent from the current
  eligible union, report it as unavailable and do not replace it based on
  outcomes. The current scan had six available controls and 34 rotating
  markets.
- Make one bounded unauthenticated CLOB `/books` batch read for selected token
  IDs. Require a complete, unique response asset set and exact market/book
  identity. Retain source timestamps and batch request/receipt timestamps
  separately.
- For the repaired freshness gate, use request-to-receipt duration (maximum
  five seconds) and reject future source-clock values. Keep reported update age
  and cross-outcome skew as diagnostics. A batch response does not establish
  atomicity, venue sequence, or upstream queue age.
- Store each completed scan as an immutable, compressed, hashed snapshot; then
  idempotently analyze each finalized snapshot once. Do not overwrite prior
  snapshots or analysis events.
- Run every 30 minutes with bounded host and API use. The timer does not create
  continuous quote coverage; each sample is intermittent.

## Prespecified measures

1. Discovery union size, eligible pair count, exclusion reasons, and response
   duplicates or conflicts.
2. Selected markets by stable-control/rotating role and by liquidity, expiry,
   category, and spread strata.
3. Selected, quality-valid, and invalid pair counts with invalid reasons.
4. Reported update-age and YES/NO timestamp-skew distributions.
5. Top-ask gross sign, full displayed depth, per-leg minimum notionals, and
   single-match and fragmentation-safe fee sensitivities at 5, 10, 20, 50, and
   100 shares per leg.
6. Unique market IDs, concentration, elapsed observation window, and analyzer
   backlog.
7. Service duration, configured CPU/memory limits, request pacing, and stored
   data size.

No confidence interval or independent-event rate is inferred from repeated
market snapshots. Future comparisons must account for market and time
dependence. A public snapshot is not a follow-up fill or execution label.

## Early measurement comparison

The old and repaired freshness rules were applied to the exact same saved first
scan, selected markets, Gamma metadata, and CLOB books. This is a paired
reclassification, not a new sample.

| Rule | Quality-valid pairs | Rate | Main exclusions |
| --- | ---: | ---: | --- |
| Original reported-timestamp age/skew gate | 5 / 40 | 12.5% | 34 reported-stale; 1 empty ask |
| Repaired batch-receipt gate | 32 / 40 | 80.0% | 6 NO empty asks; 2 YES empty asks |

The repaired rule recovers 27 pairs (+67.5 percentage points) from the same
payloads. The CLOB request-to-receipt batch duration was 70 ms. For 27 accepted
pairs, both reported update ages still exceeded five seconds; the oldest was
7,209,108 ms. This establishes that the old gate conflated a last-update time
with the freshness of a just-returned batch. It does **not** prove that returned
books are atomic, current at venue sequence time, free of upstream queue age, or
executable. Both comparison artifacts preserve their own hashes and limitations:

- `data/veritas-observatory/comparisons/measurement-gate-correction-001.json`
- `data/veritas-observatory/comparisons/measurement-gate-correction-002.json`

The versioned comparison implementation is
[`measurement_comparison.py`](../packages/midas/veritas/measurement_comparison.py).

## Current pilot result

Six snapshots were finalized between 05:59:28 and 06:22:59 UTC. The bounded
query union in the latest scan contained 300 unique Gamma market IDs, of which
167 were eligible for the supported pair audit and 133 were excluded (81
unverified augmented negative-risk semantics and 52 unsupported outcome
relationships). The latest selected panel had 40 markets: six available stable
controls and 34 rotating markets. It covered high/medium/low liquidity, three
expiry bands, and tight/medium/wide spread bands.

Across the six scans, the analyzer processed 240 selected pair observations;
211 passed the repaired quality gate (87.9%), 29 failed on an empty ask side,
and 121 distinct market IDs were observed. The 87.9% is a descriptive yield
across repeated, selected public snapshots, not an independent rate estimate.

The 20-share economic qualification experiment found zero positive top-ask,
full-depth, minimum-notional, single-match-fee, or fragmentation-safe-fee
states. Keep no-trade as the current hypothetical policy and continue measuring.

## Stopping and review rules

- Stop a scan on request failure, incomplete or duplicate book assets, failed
  identity checks, analyzer failure, or the configured storage bound. Retain
  the error and do not turn a partial scan into a valid observation.
- Do not promote a candidate from a single scanner result. Preserve its exact
  immutable snapshot and require independent replay, payoff, depth, minimum,
  timestamp, and fee review first.
- Revisit cohort size or request cadence only after checking host, venue rate,
  storage, and source-quality measurements. Never change the frozen Reality
  campaign or its historical records.
- Review dependence and descriptive readiness only after at least 24 hours,
  repeated scans, and sufficient market diversity. The current interval is far
  shorter and does not meet that bar.
