# Gate B checkpoint 014 — independent replay through the 10:30 snapshot

**Captured:** 2026-10-16T10:31:51Z

**Mission status:** active; no gross or economically qualified candidate
observed.

## Independent source replay

The normal 10:30 UTC observer run saved
`scan-20261016T103050Z-bc8cf9bc331e`. Independent audit 013 replayed all 62
saved snapshots using the separated v3 collateral-fee model.

| Check | Result |
| --- | ---: |
| Selected market observations | 2,480 |
| Quality-valid in v4 / independent v3 replay | 2,095 / 2,095 |
| Validity / top-edge mismatches | 0 / 0 |
| Strict reported-age freshness states | 438 |
| Pairs with one or more reported ages over 5 seconds | 1,657 |
| Pair timestamp skew over 250 ms | 0 |
| Independent fee checks / disagreements | 2,609 / 0 |
| Positive top-pair gross states | 0 |
| Positive full-depth gross states at quantities 5, 10, 20, 50, 100 | 0 at each quantity |
| Positive states after both per-leg minimums, single-match fees, or fragmentation-safe fees | 0 at each quantity |

The audit covers selected, intermittent, repeatedly observed market states.
These are not independent opportunity trials and do not estimate the
venue-wide opportunity rate. Public timestamp age and skew do not establish
sequence freshness, atomicity, quote persistence, arrival, or fills.

## Prospective measurement pilot 002

The same scheduled observer run enrolled the isolated 24-hour pilot on its
first scan, without backfill. It recorded 20 quality-valid pairs from 40
selected pair slots and zero positive top-gross pairs. Four pairs passed its
strict reported-age sensitivity; 16 YES and 16 NO update legs exceeded five
seconds. No batch atomicity or venue sequence counts were verified. The event,
snapshot, finalized v4 analysis, and summary digests all verify. These are
first-scan measurement diagnostics, not an improvement estimate or economic
result.

Pilot 001 remains at 28/48 scans, with 912/1,120 quality-valid slots across 657
selected markets and one skipped sequence. Its current-source pin is stale; the
read-only API now preserves the internally verified historical chain and
labels that source drift. Neither pilot nor the frozen Reality campaign was
reset or edited.

## Evidence and next action

- Independent replay: [audit 013](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_013.json)
- Audit file SHA-256: `4d5c3d97fceeaf6cad8b81306dae9a187498955b2f6b21e3c89057d1cd8c5bd0`
- Result SHA-256: `530ad108fa4fe467f002f7119875777d7c0d638fce70d53db257b1e163617e4`
- Source manifest SHA-256: `e00b5c6f13f31070a97ac098268318d078befe1b539d620329b72bcd7f892e1f`
- Pilot 002: `data/veritas-observatory/measurement-pilots/VERITAS-M2-COVERAGE-PILOT-002/summary.json`
- Ledger receipt: H135

Preserve the no-trade decision and continue the pilots only on their normal
schedule. No model training or strategy promotion is justified by these data.
Revisit candidate-specific research only if a quality-valid positive gross
state appears.
