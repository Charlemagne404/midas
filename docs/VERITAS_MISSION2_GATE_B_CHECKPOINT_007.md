# Gate B checkpoint 007 — independent scan-52 economic replay

- **Captured:** 2026-10-16T05:46:57.429788+00:00
- **Experiment:** `VERITAS-M2-INDEPENDENT-SOURCE-AUDIT-001`
- **Mission status:** active; no gross candidate has qualified.

The independent raw-source evaluator covers 52 saved snapshots / 2,080 selected market-pair observations across 33,957,407 compressed source bytes. It independently reproduces v4 quality and top-edge decisions.

| Check | Result |
| --- | ---: |
| Independent valid / v4 stored valid | 1,788 / 1,788 |
| Validity / top-edge mismatches | 0 / 0 |
| Strict reported-age sensitivity | 383 states |
| Pairs with at least one reported age over 5 seconds | 1,405 |
| Pair timestamp skew over 250 ms | 0 pairs |
| Positive top-pair gross states | 0 |
| Positive full-depth gross states | 0 at quantities 5, 10, 20, 50, 100 |
| Positive full-depth and both minimums | 0 at quantities 5, 10, 20, 50, 100 |
| Positive single-match fee sensitivity | 0 at quantities 5, 10, 20, 50, 100 |
| Positive fragmentation-safe fee sensitivity | 0 at quantities 5, 10, 20, 50, 100 |
| Positive under both fee sensitivities | 0 at quantities 5, 10, 20, 50, 100 |

The strict reported-age rule admits 383/1788 states. It uses returned timestamps, a 250-ms pair-skew limit, and same-batch receipt; it does not prove venue sequence freshness, quote persistence, atomicity, order arrival, fills, or profitability. The 1,405 age exceedances are not independently labeled stale quotes.

The scheduled 05:45 Director cycle reconciled scan 51 and admitted scan 52 as one job. Arena child `job-6c0fa56b47034494a10ccaa1` completed 52/52 events in 3.73 seconds with exit 0. The 52-scan result has 1,788 quality-valid pairs from 2,080, a maximum top edge of -$0.001/share, median -$0.020, and minimum -$0.996. All five qualification gates are zero; candidate evidence and independent candidate replay are complete and empty. The Director manifest still shows the completed child as QUEUED with scan 51 as last qualified until the scheduled 06:15:10 UTC reconciliation.

| Evidence | Value |
| --- | --- |
| Independent audit | `docs/VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_006.json` |
| File SHA-256 | `bd1c6d52fa7a75028a6992c9e1ede537a6e2a215e0d5cf417f964a5aa9c467a8` |
| Result SHA-256 | `96cd40e1b7ab3a27024560878fdd73772dd96f57db9f459b96df335727760854` |
| Source-manifest SHA-256 | `4860b0c90d701b49df2d70613070e60da74bae5c2a2ff8992598bd63fcd0fad0` |
| Research ledger | H117 |

This is an independent qualification replay, not a strategy-P&L experiment or evidence of executable liquidity. All source reads used saved public responses; no authenticated request or order was made. Keep the no-trade policy and reported age separate from sequence freshness.
