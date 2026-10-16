# Gate B checkpoint 009 — independent scan-54 economic replay

- **Captured:** 2026-10-16T06:47:12+00:00
- **Experiment:** `VERITAS-M2-INDEPENDENT-SOURCE-AUDIT-001`
- **Mission status:** active; no gross candidate has qualified.

The independent raw-source evaluator covers 54 saved snapshots / 2,160 selected market-pair observations across 35,111,892 compressed source bytes. It independently reproduces v4 quality and top-edge decisions.

| Check | Result |
| --- | ---: |
| Independent valid / v4 stored valid | 1,853 / 1,853 |
| Validity / top-edge mismatches | 0 / 0 |
| Strict reported-age sensitivity | 391 states |
| Pairs with at least one reported age over 5 seconds | 1,462 |
| Pair timestamp skew over 250 ms | 0 pairs |
| Positive top-pair gross states | 0 |
| Positive full-depth gross states | 0 at quantities 5, 10, 20, 50, 100 |
| Positive full-depth and both minimums | 0 at quantities 5, 10, 20, 50, 100 |
| Positive single-match fee sensitivity | 0 at quantities 5, 10, 20, 50, 100 |
| Positive fragmentation-safe fee sensitivity | 0 at quantities 5, 10, 20, 50, 100 |
| Positive under both fee sensitivities | 0 at quantities 5, 10, 20, 50, 100 |

The strict reported-age rule admits 391/1,853 states. It uses returned timestamps, a 250-ms pair-skew limit, and same-batch receipt; it does not prove venue sequence freshness, quote persistence, atomicity, order arrival, fills, or profitability. The 1,462 age exceedances are not independently labeled stale quotes.

The scheduled 06:45 UTC Director cycle reconciled scan 53 and admitted scan 54. Arena child `job-f8035f4c4d534e7082246684` completed 54/54 events with exit 0 in 3.91 seconds. Its finding has 1,853 quality-valid pairs from 2,160, maximum top edge -$0.001/share, median -$0.020, and minimum -$0.996. All five qualification gates are zero; candidate evidence and independent candidate replay are complete and empty. The Director manifest still projects the child as `QUEUED` until the scheduled 07:15 UTC reconciliation.

| Evidence | Value |
| --- | --- |
| Independent audit | `docs/VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_008.json` |
| File SHA-256 | `994ed09161d31b7e571cd99fe047599dd8e08987020d3acdf5c2f891f786e7fe` |
| Result SHA-256 | `895c0aae38b2196fcf429416f90ce018a3fe0b5fc34713d80217bbb0746c5808` |
| Source-manifest SHA-256 | `1558e96013bdb6fc6baad546b02ee3a09d656697e082ac45a00e454e2d70ab37` |
| Research ledger | H122 |

The first-scan snapshot counter difference remains explained in [Gate A counter-semantics note 001](VERITAS_MISSION2_GATE_A_COUNTER_SEMANTICS_NOTE_001.md). This is an independent qualification replay, not a strategy-P&L experiment or evidence of executable liquidity. No authenticated request or order was made.
