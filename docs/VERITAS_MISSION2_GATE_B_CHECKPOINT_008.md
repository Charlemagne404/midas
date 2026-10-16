# Gate B checkpoint 008 — independent scan-53 economic replay

- **Captured:** 2026-10-16T06:17:16.166538+00:00
- **Experiment:** `VERITAS-M2-INDEPENDENT-SOURCE-AUDIT-001`
- **Mission status:** active; no gross candidate has qualified.

The independent raw-source evaluator covers 53 saved snapshots / 2,120 selected market-pair observations across 34,505,902 compressed source bytes. It independently reproduces v4 quality and top-edge decisions.

| Check | Result |
| --- | ---: |
| Independent valid / v4 stored valid | 1,818 / 1,818 |
| Validity / top-edge mismatches | 0 / 0 |
| Strict reported-age sensitivity | 388 states |
| Pairs with at least one reported age over 5 seconds | 1,430 |
| Pair timestamp skew over 250 ms | 0 pairs |
| Positive top-pair gross states | 0 |
| Positive full-depth gross states | 0 at quantities 5, 10, 20, 50, 100 |
| Positive full-depth and both minimums | 0 at quantities 5, 10, 20, 50, 100 |
| Positive single-match fee sensitivity | 0 at quantities 5, 10, 20, 50, 100 |
| Positive fragmentation-safe fee sensitivity | 0 at quantities 5, 10, 20, 50, 100 |
| Positive under both fee sensitivities | 0 at quantities 5, 10, 20, 50, 100 |

The conservative reported-age rule admits 388/1,818 states. It uses returned timestamps, a 250-ms pair-skew limit, and same-batch receipt; it does not prove venue sequence freshness, quote persistence, atomicity, order arrival, fills, or profitability. The 1,430 age exceedances are not independently labeled stale quotes.

The scheduled 06:15 UTC Director cycle admitted scan 53. Arena child `job-6be536ab59a143ec964f46b1` completed 53/53 events with exit 0 in 3.91 seconds. Its finding has 1,818 quality-valid pairs from 2,120, maximum top edge -$0.001/share, median -$0.020, and minimum -$0.996. All five qualification gates are zero; candidate evidence and independent candidate replay are complete and empty. The Director manifest still shows the child as `QUEUED` and scan 52 as last qualified until the scheduled 06:45 UTC reconciliation.

| Evidence | Value |
| --- | --- |
| Independent audit | `docs/VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_007.json` |
| File SHA-256 | `f18cab1f69b2634c142911602e3872694c5a342996f0c42c5027e88e33cd7bcd` |
| Result SHA-256 | `9749ef015a9c1ab18d857a1e4e52ae485c92689d6c2b866ee37174686269e134` |
| Source-manifest SHA-256 | `45a7fca0ac76721c862f78a6589444080f63c8bd09ee26019e2297863e666717` |
| Research ledger | H119 |

This is an independent qualification replay, not a strategy-P&L experiment or evidence of executable liquidity. All source reads used saved public responses; no authenticated request or order was made. Keep the no-trade policy and reported age separate from sequence freshness.

The first-scan v4 event itself stores 32 quality-valid pairs and 5 legacy-freshness-valid pairs; the independent evaluator reproduces the v4 count. The A1 5-versus-32 flag compares the snapshot's legacy counter with the v4 event counter. See [Gate A counter-semantics note 001](VERITAS_MISSION2_GATE_A_COUNTER_SEMANTICS_NOTE_001.md).
