# Gate B checkpoint 010 — independent scan-55 economic replay

- **Captured:** 2026-10-16T07:18:03.478813+00:00
- **Experiment:** `VERITAS-M2-INDEPENDENT-SOURCE-AUDIT-001`
- **Mission status:** active; no gross candidate has qualified.

The independent raw-source evaluator covers 55 saved snapshots / 2,200 selected market-pair observations across 35,726,316 compressed source bytes. It independently reproduces the v4 validity and top-edge decisions.

| Check | Result |
| --- | ---: |
| Independent v2 valid / v4 stored valid | 1,882 / 1,882 |
| Validity / top-edge mismatches | 0 / 0 |
| Strict reported-age sensitivity | 399 states |
| Pairs with at least one reported age over 5 seconds | 1,483 |
| Pair timestamp skew over 250 ms | 0 pairs |
| Positive top-pair gross states | 0 |
| Positive full-depth gross | 0 at quantities 5, 10, 20, 50, 100 |
| Positive full-depth and both minimums | 0 at quantities 5, 10, 20, 50, 100 |
| Positive single-match fee sensitivity | 0 at quantities 5, 10, 20, 50, 100 |
| Positive fragmentation-safe fee sensitivity | 0 at quantities 5, 10, 20, 50, 100 |

The conservative reported-age rule admits 399/1,882 states. It uses returned timestamps, a 250-ms pair-skew limit, and same-batch receipt; it does not prove venue sequence freshness, quote persistence, atomicity, order arrival, fills, or profitability. The 1,483 age exceedances are not independently labeled stale quotes.

| Evidence | Value |
| --- | --- |
| Independent audit | `docs/VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_009.json` |
| File SHA-256 | `4b9ea5e001c794d7015e52eb664f01ff1f923d729cb422faae22c95f04bdfd10` |
| Result SHA-256 | `62fc0bf208535d48a6d2411062becda39e2610eb9ee287f8a6fd6a2c10018aca` |
| Source-manifest SHA-256 | `fc0adc6e28c49c20cec85e57f964b70fb852e070bc35b59e955437a73ca52259` |
| Research ledger | H124 |

This independent replay is a qualification check, not a strategy-P&L experiment or evidence of executable liquidity. No authenticated request or order was made.
