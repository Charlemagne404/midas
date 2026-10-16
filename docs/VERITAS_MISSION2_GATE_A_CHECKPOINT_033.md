# Gate A checkpoint 033 — scan 37 and coverage-pilot progress

**Updated through:** 2026-10-15T22:26:02Z  
**Mission status:** active; the scheduled observer and fixed prospective pilot continue.

## Scan 37 and cumulative discovery panel

Scan `scan-20261015T220039Z-1bcb8753082e` was captured at 22:00:39 UTC.
Six bounded discovery queries returned 300 unique market IDs. Of those, 233
met the supported same-condition V1 binary relationship rule; 67 were
excluded (37 augmented negative-risk relationships without verified semantics
and 30 unsupported outcome relationships). Forty markets were selected, 35
passed the request/receipt quality checks, and five had an empty ask side.
The scan recorded no positive top-gross state.

The cumulative panel now contains 37 snapshots, 1,480 selected market
observations, 1,307 quality-valid pairs, 173 invalid pairs, and 689 selected
market IDs. On the same observations, the legacy reported-age rule accepts
290 states while the request/receipt gate accepts 1,307: 1,017 additional
classifications, or 68.72 percentage points of all selected slots. This is a
measurement-yield comparison and does not prove venue-time freshness.

Across the 1,307 quality-valid paired states, the maximum top-pair edge is
-$0.001 per share and the median nearest-rank edge is -$0.020. Positive counts
remain zero at unchanged top-ask gross, full displayed-depth gross, both
per-leg minimums, single-match fee sensitivity, and fragmentation-safe fee
sensitivity, at each tested size from 5 to 100 shares per leg. The full panel
is intermittent and correlated; it is not continuous market coverage or
independent confirmation.

## Fixed prospective coverage pilot

The read-only pilot has completed seven of at most 48 scans in its fixed
24-hour window, ending at 2026-10-16T19:00:55.062293Z. Its current summary
contains 280 selected pair slots, 237 quality-valid pairs (84.64%), 43
invalid pairs, 207 distinct selected IDs, and zero skipped scan sequences.
The rotating cohort contributes 228/257 valid (88.72%); the frozen stable
controls contribute 9/23 (39.13%). Those controls are not randomized and
role/phase differences are descriptive only. All seven scans report zero
positive top-gross pairs. No orders were submitted and no authenticated
requests were used.

## Freshness evidence review

The current [Polymarket Real-Time Data documentation](https://docs.polymarket.com/market-data/realtime-data)
shows the public book event with optional timestamp and hash fields but no
sequence counter in its documented schema. The [Prices and Order Books
documentation](https://docs.polymarket.com/market-data/prices-order-books)
describes the REST book hash as a way to tell whether the state changed
between reads; the page does not define the timestamp as a monotonic venue
sequence or a freshness guarantee. This supports retaining hash changes as
state fingerprints and keeping the reported age as a diagnostic. It does not
establish cross-outcome atomicity or independent feed continuity.

## Verification and remaining work

The scheduled v3 economic qualification consumed all 37 finalized snapshot
events and produced zero positive candidates. Its detailed source-linked
result is in [Gate F checkpoint 022](VERITAS_MISSION2_GATE_F_CHECKPOINT_022.md).
The improved request/receipt gate recovers many measurable pairs, but the
expanded observation panel still shows no positive gross state. Keep no-trade,
continue the fixed pilot, and retain the bounded discovery and evidence limits.
Gate A remains in progress.
