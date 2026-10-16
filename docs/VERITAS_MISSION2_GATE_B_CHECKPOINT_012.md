# Gate B checkpoint 012 — collateral fee correction and replay of 59 saved snapshots

**Captured:** 2026-10-16 09:06 UTC

**Mission status:** active; no positive gross opportunity observed.
**Scope:** read-only replay of already saved public snapshots plus a synthetic
fee-sensitivity recalculation. No service was restarted, no order was sent, and
the protected Reality campaign and raw source records were not changed.

## Independent public-snapshot replay

The independent audit replayed all 59 saved, selected snapshots available at
capture time, including latest scan
`scan-20261016T090043Z-957608af59ae` (2,360 selected market observations;
38,387,196 compressed source bytes). It
reproduced all stored quality decisions and top-edge results under the corrected
v3 economics with no mismatches. It is a replay of intermittent, selected, and
correlated snapshots; the row count is not an independent opportunity count or
a venue-wide denominator.

| Check | Result |
| --- | ---: |
| Independent / stored quality-valid observations | 2,015 / 2,015 |
| Quality-validity / top-edge mismatches | 0 / 0 |
| Strict reported-freshness observations | 426 |
| Pairs with reported age over 5 seconds | 1,589 |
| Pair timestamp skew over 250 ms | 0 |
| Independent fee arithmetic checks / disagreements | 2,523 / 0 |
| Positive top-pair gross states | 0 |
| Positive full-depth gross states at quantities 5, 10, 20, 50, 100 | 0 at each quantity |
| Positive states after both minimums, single-match fees, or fragmentation-safe fees | 0 at each quantity |

The age sensitivity uses returned timestamps, same-batch receipt, and a 250 ms
cross-outcome skew threshold. It does not establish venue-sequence freshness,
quote persistence, batch atomicity, order arrival, or fillability. The 1,589
reported-age exceedances are not independently proven stale quotes.

## Fee model correction

The former v2 model converted buy fees into outcome-share deductions and applied
them at resolution. Current fee guidance describes taker fees in USDC, and the
current exchange settlement source charges buy fees from collateral. The v3
model therefore books both bought-leg fees as entry costs, reserves collateral
for fees, and keeps share-equivalent values diagnostic only. Sources:
[Polymarket trading-fee guidance](https://help.polymarket.com/en/articles/13364478-trading-fees)
and [CTF Exchange V2 settlement implementation](https://github.com/Polymarket/ctf-exchange-v2/blob/main/src/exchange/mixins/Trading.sol).

The source replay checked a separate Decimal implementation of the documented
fee arithmetic for 2,523 quantities and found no disagreements. This verifies
internal arithmetic agreement against the documented schedule; it is not an
observed fee charge. Fee rounding on a hypothetical fragmented order, actual
queue position, and fills remain unobserved.

## Synthetic sensitivity only

The revised 100-share-per-leg synthetic case has a full-depth completed-pair
P&L of **+1.62399 USDC** under single-match rounding and **-0.36982 USDC** under
the fragmentation-safe fee bound. The unmatched-leg loss assumption is
**52.19973 USDC**. At half displayed depth, the single-match completed pair is
**-0.88421 USDC**. These are controlled hypothetical inputs, not observed
markets, candidates, fills, strategy performance, or a profitability estimate.
The positive single-match corner depends on an unverified rounding assumption;
the conservative full-depth bound remains negative, and empirical completion
and unmatched-event rates are unknown.

## Artifacts and verification

- Independent source audit: [audit 011](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_011.json)
- Audit file SHA-256: `f8538a523f2cc092939de7755e4697e1a5fb0ad52c48ecc16657162dbf8fb069`
- Result SHA-256: `208ff1828969e8e49baf414345d7100b3d01680048b951036796af5bfcaa521c`
- Source manifest SHA-256: `c6de53f929bc35faba2abd989227c332af528ce4868f9394aa57988aa98e4879`
- Synthetic sensitivity: [break-even report 002](VERITAS_GATE_B_EXECUTION_BREAK_EVEN_002.json)
- Synthetic report SHA-256: `662ec9cc4be0923fdf03a0270daf49c68d3ffefbb5eb3c4d6c16c9839b9cdea0`
- Research ledger receipts: H130 (source replay), H131 (synthetic model correction)
- Focused backend Veritas suite: 104 passed; one upstream Starlette/httpx deprecation warning.
- Dashboard API and frontend checks: passed, including the focused Veritas UI test, TypeScript typecheck, and Prettier check. Ruff check/format and `git diff --check` passed.

The local API and dashboard now select the ledger-receipted, hash-verified v3
synthetic report and expose its fee-model version and collateral collection
medium. The long-running API process has not been reloaded, so this repository
change is not evidence that the hosted dashboard has already loaded the new
artifact.

## Decision and next work

Keep the no-trade decision. The corrected accounting does not change the public
finding: no positive gross state appeared in these snapshots, and no state
survived the displayed-depth, minimum, and fee checks. Use v3 for new
calculations; retain the old v2 artifact as immutable historical evidence.

Next, perform the normal safe code rollout when it can be done without
disturbing the collector or Reality worker; verify that the API serves the
hash-receipted v3 artifact after that rollout. Continue bounded source capture
and replay, and keep the fee-rounding and execution-rate uncertainties explicit.
Do not start strategy training until there are candidate-relevant observations
and independent outcome labels.
