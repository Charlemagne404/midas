# Gate B checkpoint 006 — independent scan-51 economic replay

- **Captured:** 2026-10-16T05:22:16Z
- **Experiment:** `VERITAS-M2-INDEPENDENT-SOURCE-AUDIT-001`
- **Mission status:** active; no gross candidate has qualified.

The independent raw-source evaluator now covers 51 saved snapshots / 2,040
selected market-pair observations over 33,318,338 compressed source bytes. It
verified the saved source lineage and independently reproduced all 1,755
quality-valid states and top-edge decisions from v4 with zero mismatches.

| Check | Result |
| --- | ---: |
| Independent valid / v4 stored valid | 1,755 / 1,755 |
| Validity / top-edge mismatches | 0 / 0 |
| Strict reported-age sensitivity | 379 states |
| At least one reported age over 5 seconds | 1,376 pairs |
| Pair timestamp skew over 250 ms | 0 pairs |
| Positive top-pair gross states | 0 |
| Positive full-depth gross states | 0 at quantities 5, 10, 20, 50, 100 |
| Positive full-depth and both minimums | 0 at quantities 5, 10, 20, 50, 100 |
| Positive single-match fee sensitivity | 0 at quantities 5, 10, 20, 50, 100 |
| Positive fragmentation-safe fee sensitivity | 0 at quantities 5, 10, 20, 50, 100 |
| Positive under both fee sensitivities | 0 at quantities 5, 10, 20, 50, 100 |

The strict reported-age rule admits five more states than in the prior 50-scan
audit. It is a conservative sensitivity using the returned timestamp, a
250-ms pair-skew bound, and same-batch receipt. It does not prove sequence
freshness, continuous quote persistence, atomicity, order arrival, fills, or
profitability. The 1,376 age exceedances are not independently labeled as
stale quotes. Keep the current no-trade decision and keep reported age
separate from sequence freshness.

Artifact and provenance:

- [Independent opportunity audit 005](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_005.json)
- Artifact file SHA-256: `60b1f2a204970f504f97e4096fa4bb45d8a139175b19e79d1796ae18baa045b9`
- Result SHA-256: `5d1b667a72bdd8d444d956fcd266e56e8e137fd4dcf35fdabfae4f71a6c9773a`
- Source-manifest SHA-256: `236754ef937101fd9348dd67bff0f461a1d28cc4c2fb0b5d5e60ae0b7d500dc4`
- Research ledger: H114.

This audit used only saved local public-response data. It made no authenticated
requests and submitted no orders. It is an independent qualification replay,
not a strategy-P&L experiment or evidence of executable liquidity. The source
code path shares the versioned fee evaluator only after its own price, depth,
minimum, and quality calculations. See [inventory
068](VERITAS_MISSION2_RESEARCH_INVENTORY_068.json).
