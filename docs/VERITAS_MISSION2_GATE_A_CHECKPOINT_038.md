# Gate A checkpoint 038 — measured discovery coverage audit

**Captured:** 2026-10-15 23:57 UTC

**Mission status:** active; the existing Reality collector, frozen campaign,
and fixed coverage pilot remain unchanged.

## A1 market-universe coverage

Added a bounded offline analyzer for finalized public observatory snapshots.
It verifies each retained Gamma page, CLOB response, metadata digest, and
snapshot evidence digest, then reports Gamma market IDs, condition IDs, and
outcome asset IDs separately. It also summarizes the six query frames,
current V1 eligibility, exclusions, metadata dimensions, selection
probabilities, and sampled activity. The versioned output is
[market-universe coverage 001](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_001.json).

The analyzer verified all 40 finalized snapshots from 05:59:28 UTC through
23:32:05 UTC on 2026-10-15: 240 Gamma responses, 40 CLOB responses, 40
snapshot-evidence digests, and 26,226,564 compressed snapshot bytes. The six
bounded pages average 298.85 unique Gamma market IDs and 162.07 currently
eligible same-condition V1 pairs per scan. Across the window, the pages
contained 5,319 distinct market IDs, 5,319 condition IDs, and 10,638 outcome
asset IDs; 2,077 market IDs were eligible at least once. No market-to-contract
or market-to-asset identity conflicts appeared in this retained sample.

This is a count of the observed bounded query unions, not an estimate of the
venue-wide denominator. The Reality recorder still has its separate eight
market-ID cohort; the public snapshot screen does not change that continuous
cohort.

## Composition and sampling

The latest six-frame union has 291 market IDs: 77 eligible and 214 excluded
(156 augmented NegRisk structures with unverified semantics and 58
unsupported outcome relationships). Among eligible markets, the observed
liquidity bands are 22 high, 14 medium, and 41 low; expiry bands are 50 within
seven days, 12 within 90 days, and 15 longer; displayed spread bands are 35
tight, 27 medium, and 15 wide. These are the 40 markets selected for books,
not venue-wide category shares.

The six discovery frames each contribute about 49–50 unique IDs on average.
Removing the low-liquidity or medium-liquidity frame would remove an average
of 38.83 or 32.60 eligible IDs from the bounded union. The stable random
control frame contributes 23.62 eligible IDs on average; the tagged near-
expiry frame contributes 49.90. These marginals support retaining all six
frames while the fixed pilot runs. Across 40 scans, 1,435 selected slots were
rotating-stratified and 165 were stable controls. Numeric selection
probabilities are conditional on the bounded query union and frozen controls.

The latest scan has 40 selected markets, 40 condition IDs, and 80 selected
outcome asset IDs. Only 60 selected assets appear in payoff-verified rows,
matching the 30 pairs that passed current request/receipt quality checks.
This distinction is now explicit in the report.

## Quality and economic screen

Current v4 replay accepts 1,405 of 1,600 selected pair observations (87.81%).
The 195 invalid pairs have missing asks on the No leg in 185 cases and the Yes
leg in 10. There are zero positive top-gross pairs and zero candidate events
in these 40 snapshots. This result is limited to selected intermittent
public books; it provides no order-arrival, fill, or profitability evidence.

There is one capture-counter difference: scan 1 stores five
`valid_quality_pairs`, while current v4 replay gives 32. The earlier v1 event
for that scan also reports five valid pairs, while its v4 event reports 32
request/receipt-quality pairs and five legacy freshness-valid pairs. The 27
pair difference is therefore consistent with the quality-gate revision. The
audit retains both capture-time and current-replay totals rather than mixing
them. Its 1,405 current-replay total is the comparable v4 measure.

Across repeated selected samples, 174 markets had at least one comparable
repeat, with 335 of 677 adjacent top-of-book comparisons changing (49.48%).
This is an intermittent activity proxy, not a venue update-rate estimate.
Reported source update age exceeded five seconds on 1,095 valid pairs per
leg, while all 1,405 valid pairs had reported cross-outcome timestamp skew at
or below 250 ms. Request/receipt quality does not imply fresh upstream quote
timestamps.

## Verification and next work

The focused analyzer tests pass (2 passed); Ruff, formatting, and strict
Mypy pass for the changed analysis files. The full regression suite was not
run. The analyzer and tests operate on saved fixtures and snapshots; no
service, collector, pilot, frozen campaign, or research job was restarted or
altered.

A1 now has a measurable, digest-verified report for the saved public
discovery sample. Gate A remains in progress: the bounded screen still has no
venue-wide denominator, the continuous Reality cohort remains small, and the
fixed pilot has not finished. The versioned eight-call successor remains
deferred until the v1 pilot reaches its fixed stop. See [research ledger
H084](VERITAS_RESEARCH_LEDGER.json), [inventory
046](VERITAS_MISSION2_RESEARCH_INVENTORY_046.json), and the [engineering
checkpoint](VERITAS_MISSION2_ENGINEERING.md).
