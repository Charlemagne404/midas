# Gate A checkpoint 012 — verified multi-outcome set audit

**Captured:** 2026-10-15 11:16 UTC  
**Branch:** `project/veritas`  
**Checkpoint base:** `16b5660`

## Discovery extension

The bounded 11:01:53 UTC observer union contained 300 unique market IDs, 207
eligible same-condition V1 binary markets, and 93 exclusions. Six Gamma frames
also exposed 106 records with a NegRisk group ID across 39 groups. The Strava
IPO market-cap group appeared complete in that union with nine members, so it
was selected for a pinned, read-only event-level check rather than being
admitted generally by the binary-pair scanner.

Gamma event `164439` (`strava-ipo-closing-market-cap`) returned exactly markets
`1185108`–`1185116`. The event was active, open, `negRisk=true`, and
`negRiskAugmented=false`; all nine V1 conditions shared the same group ID. The
event rules divide IPO-day market capitalization into a continuous set of
non-overlapping ranges, assign exact bracket ties to the higher range, and add
a “no IPO by December 31, 2027” outcome. The verifier fails closed if the
event identity, exact member IDs, group, lifecycle, V1 Yes/No shape, fees, or
range partition changes.

The official adapter description says NegRisk prevents more than one Yes
outcome, while the contract does not enforce that at least one outcome resolves
Yes. The complete Yes basket therefore pays one dollar per share only under
the event-rule assumption that exactly one outcome resolves Yes. The complete
No basket has a protocol payoff floor of eight shares per nine-outcome set:
at most one Yes can resolve, leaving at least eight No outcomes. See the
official [NegRisk adapter documentation](https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/docs/NegRiskAdapter.md),
[adapter README](https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/README.md),
and [Gamma API documentation](https://gamma-api.polymarket.com/docs).

## Public book capture and economics

The v3 collector fetched the pinned Gamma event, waited one second, and
submitted one unauthenticated CLOB `/books` request for all 18 Yes and No token
IDs. Each response was capped at 2,000,000 bytes. Both requests returned HTTP
200; the CLOB batch took 98 ms and included all 18 expected assets. No
credentials or orders were used. Raw source bodies, request/response hashes,
timings, and the versioned result are retained in the ignored runtime artifact
`data/veritas-observatory/structure-studies/1792062993453561861-event-164439.json`.

All 18 ask books had displayed depth for the 5-, 20-, and 100-share cases, and
each leg met the five-share minimum. Both displayed baskets were expensive
relative to their payout basis:

| Basket / shares per outcome | Ask cost | Payout basis | Gross edge | Conservative taker-fee upper bound | Net edge |
| --- | ---: | ---: | ---: | ---: | ---: |
| Yes / 1 (top ask) | $2.213 | $1.000 conditional | -$1.213 | — | — |
| Yes / 5 | $11.065 | $5.000 conditional | -$6.065 | $0.51538 | -$6.58038 |
| Yes / 20 | $55.98744 | $20.000 conditional | -$35.98744 | $2.20502 | -$38.19246 |
| Yes / 100 | $386.31895 | $100.000 conditional | -$286.31895 | $13.35163 | -$299.67058 |
| No / 1 (top ask) | $8.595 | $8.000 minimum | -$0.595 | — | — |
| No / 5 | $42.975 | $40.000 minimum | -$2.975 | $0.14226 | -$3.11726 |
| No / 20 | $172.21832 | $160.000 minimum | -$12.21832 | $0.54636 | -$12.76468 |
| No / 100 | $864.57300 | $800.000 minimum | -$64.57300 | $2.48442 | -$67.05742 |

The markets expose a 4% taker rate with exponent 1. Fee results use the
existing fee-envelope code, including a fragmentation-safe upper bound; no
maker rebate is assumed. The quote snapshot fails the unchanged quality gate:
maximum source timestamp age was 350,713 ms against a 5,000 ms bound, and
cross-market timestamp skew was 349,801 ms against a 250 ms bound. The
computed costs remain descriptive only. Neither basket has positive displayed
gross or after-fee economics, and stale displayed depth does not prove
executable fills.

The earlier v1 and v2 Yes-only captures remain intact and replay under their
original analysis versions. Study v3 requests both outcomes, keeps stale but
structurally valid quotes for descriptive arithmetic, and leaves candidate
flags behind the freshness gate.

## Verification and limits

- Focused audit tests: 9 passed, covering exact range partition, missing or
  changed members, same-group verification, fee/depth arithmetic, timestamp
  failure, No-basket payout floor, and descriptive-only stale-book handling.
- Ruff checks and formatting passed; strict Mypy passed for the audit and
  collector.
- The v1 and v2 stored captures replay against their original rules. The v3
  capture retains both outcome sides and replays to result digest
  `e7007fdae2d28e6eb59c06605788a247aa58371ec780476b5a204fb1727af50d`.
- The current bounded discovery union is conditional on six rotated query
  frames. This single event does not estimate venue-wide NegRisk coverage or
  prevalence. Dynamic event membership, conditional settlement rules, source
  timestamp age, settlement delay, and no-fill uncertainty remain material.

The next useful extension is to scan additional complete event groups under
the same bounded rules. Do not add every NegRisk record to binary-pair
qualification or infer a profitability result from this one snapshot. Mission
2 remains active; see [operations](VERITAS_MISSION2_OPERATIONS.md), [research
backlog](VERITAS_RESEARCH_BACKLOG.md), and [research inventory
015](VERITAS_MISSION2_RESEARCH_INVENTORY_015.json).
