# Gate A checkpoint 047 — scan-51 universe coverage replay

**Captured:** 2026-10-16T05:25:46.019207+00:00
**Mission status:** active; the bounded A1 discovery replay is verified through scan 51.

The offline replay verified all 51 saved snapshots and retained Gamma/CLOB response hashes across 33,318,338 compressed snapshot bytes. It made no live requests. Current eligibility classification matches the stored eligible count in all 51 scans.

| Measure | Result |
| --- | ---: |
| Distinct Gamma market IDs in bounded query unions | 6,118 |
| Eligible at least once | 2,168 |
| Selected market IDs over the panel | 903 |
| Selected outcome asset IDs | 1,806 |
| Attempted market-pair observations | 2,040 |
| Current-replay quality-valid pairs | 1,755 (86.03%) |
| Invalid pairs | 285 |
| Positive top-gross pairs / candidate events | 0 / 0 |
| Scans matching stored eligible counts | 51/51 |

The latest scan, `scan-20261016T050020Z-5729ddc65f43`, has a 299-ID bounded union: 191 eligible, 108 excluded, and 40 selected. Across the panel, the mean six-frame union is 298.8 IDs, including 159.43 eligible IDs. The descriptive frame-removal replay assigns the largest average eligible marginal to tagged near-expiry (49.92 IDs) and low-liquidity (38.51); the ordinary near-expiry frame has a 4.84 mean and removes zero eligible IDs in 33/51 scans. These frame values overlap and apply only within the bounded query union.

The artifact reports 1,853 numeric conditional selection probabilities (median 0.24; range 0.0415–1.00). Among 885 repeated comparable samples, 421 top-of-book fingerprints changed (47.57%); this is an intermittent sampled-change proxy, not a venue update-rate or continuous-coverage estimate.

The prior first-scan capture discrepancy is preserved: the capture recorded 5 valid pairs while the current replay finds 32, a 27-pair difference. The other 50 scans match the stored eligibility counts; this does not erase or explain the first scan's valid-pair mismatch. The independent source economic audit 005 separately reproduces all 1,755 current-replay quality-valid pairs with zero validity or top-edge mismatches.

| Evidence | Value |
| --- | --- |
| Artifact | `docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_005.json` |
| File SHA-256 | `0def0f2f926657ca50ca305bd5d5626520c4da9036b1743b7528f240844b3a47` |
| Snapshot-manifest SHA-256 | `26aad8db8aec10d80163397b8b7ed5394e57669a6f8291b5f4cf13d6d061becb` |
| Gamma-response-manifest SHA-256 | `eb4404c468a87f830a5df1096d835a37f02580168121b080ea1467265b7db05d` |

The panel is bounded by six upstream query frames and is not venue-wide. Intermittent snapshots do not establish continuous book coverage, quote lifetime, sequence freshness, order arrival, fills, or profitability. No authenticated requests or orders were used. The capture-versus-replay discrepancy remains an open data-quality issue. The dashboard projection of artifact 005 and full Mission 2 regression were not checked in this checkpoint.
