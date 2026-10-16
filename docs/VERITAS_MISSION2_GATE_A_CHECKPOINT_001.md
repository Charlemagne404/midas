# Veritas Mission 2 Gate A Checkpoint 001

**Captured:** 2026-10-15 06:22:59 UTC
**Branch:** `project/veritas`
**Starting commit:** `9a857cc56804bec6b7129171ba090d338e263aa3`
**Evidence status:** Early operating checkpoint; observation continues

## Implementation

- Added a bounded six-frame public market discovery union and deterministic
  stratified cohort selection with a frozen random control cohort.
- Added immutable public snapshot capture for 40 same-condition V1 binary
  markets, complete token-book batch checks, exact source/code hashes, and
  exclusion records.
- Added an independent pair detector with adversarial tests for payoff identity,
  orientation, book identity, invalid asks, depth, minimums, tick rules, and fee
  sensitivities.
- Replaced the misleading use of old reported update timestamps as the sole
  freshness clock with request-to-receipt duration, preserving reported ages
  and cross-leg skew as diagnostics.
- Added idempotent finalized-snapshot analysis, a 20-share baseline-versus-
  qualification experiment, a read-only API, and Veritas dashboard panels.
- Started the bounded systemd user timer and service; live units match the
  checked-in deployment definitions.

## Discovery and observation evidence

The latest bounded Gamma union returned 300 unique market IDs. 167 markets were
eligible for the supported V1 binary pair audit; 133 were excluded, including
81 with unverified augmented negative-risk semantics and 52 with unsupported
outcome relationships. This query union is not the venue-wide market universe.

The current panel targeted 40 markets and selected all 40. Six of the intended
eight stable control IDs were present in the current eligible union; the other
34 selected markets were rotating. Latest strata contained eight high, 14
medium, and 18 low-liquidity markets; 21 near-seven-day, 17 medium-horizon, and
two longer-duration markets; and 13 tight, 12 medium, and 15 wide displayed
spreads. Category selection was price-blind and covered multiple event classes.

Six finalized snapshots span 23 minutes 31 seconds. Across 240 selected pair
observations, 211 were quality-valid, 29 were invalid because at least one ask
side was empty, and 121 distinct market IDs were seen. The latest scan was
`scan-20261015T062259Z-f060bd25dec4`:

- Snapshot: `data/veritas-observatory/snapshots/scan-20261015T062259Z-f060bd25dec4.json.gz`
- Snapshot evidence SHA-256: `f060bd25dec45ce5688fa8efbd7918b27c3e35e3173c90f403ca2bc13da7c4f0`
- Scanner source SHA-256: `712d65a8698e3b6a3d9ec5362c12322559cf7359d874ea281eab0740569f08e1`
- Latest observation: 40 attempted, 35 quality-valid, five empty-ask exclusions,
  zero positive gross candidates.
- 31 of 35 valid pairs had reported update age above five seconds on each leg;
  all 35 had reported cross-outcome timestamp skew at or below 250 ms.

## Measurement repair

Reclassifying the exact first saved scan changed quality validity from 5/40
(12.5%) under the old gate to 32/40 (80.0%) under the request-to-receipt gate.
That is 27 additional pairs and a 67.5 percentage-point increase on the same
payloads. The 70 ms response duration does not establish batch atomicity or
upstream freshness; the comparison is not an independent prospective sample.
Details and hashes are in
[`VERITAS_MISSION2_MEASUREMENT_PILOT_001.md`](VERITAS_MISSION2_MEASUREMENT_PILOT_001.md).

## Economic result

Experiment `VERITAS-M2-ECO-QUAL-001` compares the unchanged top-ask gross-sign
baseline with complete displayed depth at 20 shares per leg and both per-leg
minimum-notional checks. Single-match and fragmentation-safe fee sensitivities
are reported separately. Across 211 valid states:

- Top-ask positive gross: 0
- Positive full displayed depth: 0
- Positive depth with both minimums: 0
- Positive under either fee sensitivity: 0
- Observed top-edge range: -0.60 to -0.001; median nearest rank -0.022 per
  share

The comparison qualifies candidates; it is not a strategy PnL or fill
experiment. Keep no-trade. The hashed artifact is
`data/veritas-observatory/experiments/VERITAS-M2-ECO-QUAL-001.json`.

## Remaining Gate A/C work

- Keep sampling until the temporal window is long enough for a separate
  dependence review; the 24-hour descriptive-readiness and the prior study's
  48-hour coverage gates have not been met.
- Validate source freshness semantics against a sequence-bearing source or
  another independent observation mechanism. Keep the batch limitation visible.
- Expand the query frame only after rate, discovery coverage, and host costs are
  measured; six capped pages do not represent the venue.
- Report rotating-panel concentration and market/time dependence before making
  inferential claims.
