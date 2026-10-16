# Gate A checkpoint 048 — scan-52 universe coverage replay

**Captured:** 2026-10-16T05:46:50.551042+00:00
**Mission status:** active; the bounded A1 discovery replay is verified through scan 52.

The offline replay verified all 52 saved snapshots, 312 Gamma responses, and retained CLOB books across 33,957,407 compressed snapshot bytes. Snapshot, Gamma, and CLOB response hashes verified; no live requests were made. The current eligibility classifier matches stored eligible counts in all 52 scans.

| Measure | Result |
| --- | ---: |
| Distinct Gamma market IDs in bounded query unions | 6,195 |
| Eligible at least once | 2,180 |
| Selected market IDs over the panel | 926 |
| Selected outcome asset IDs | 1,852 |
| Attempted market-pair observations | 2,080 |
| Current-replay quality-valid pairs | 1,788 (85.96%) |
| Invalid pairs | 292 |
| Positive top-gross pairs / candidate events | 0 / 0 |
| Scans matching stored eligible counts | 52/52 |

The latest scan, `scan-20261016T053106Z-17b5d754b6c2`, has a 299-ID bounded union: 154 eligible, 145 excluded, and 40 selected. Across all 52 snapshots, the mean six-frame union is 298.8 IDs, including 159.33 eligible IDs. Among 897 repeated comparable samples, 427 top-of-book fingerprints changed (47.60%); this is an intermittent activity proxy, not an update-rate or continuous-coverage estimate.

The first-scan capture discrepancy remains preserved: 5 captured-valid pairs versus 32 current-replay-valid pairs, a 27-pair difference. The replay reports 1,761 captured-valid pairs overall versus 1,788 current-replay-valid pairs; the other 51 scans have no capture/replay valid-count discrepancy. The independently implemented audit 006 reproduces all 1,788 current-replay valid states with zero v4 validity or top-edge mismatches.

| Evidence | Value |
| --- | --- |
| Artifact | `docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_006.json` |
| File SHA-256 | `a16d024aaadd8334fee1692a3b1e6767f412a7b587731bc3ce5a46b9f11e5f49` |
| Snapshot-manifest SHA-256 | `e856c5476696dd4e797609a96f6f5358c4780fff4b8031cfe5f666b6acd48cd9` |
| Gamma-response-manifest SHA-256 | `2abe41637ef2242d9702532c194a83bbe40581545fff85f8dd0d70d71da2bbd4` |

The six query frames are bounded and upstream-filtered, not a venue-wide denominator. Intermittent observations do not establish continuous book coverage, quote lifetime, sequence freshness, order arrival, fills, or profitability. No authenticated requests or orders were used. The capture mismatch is unresolved. The API still pins coverage artifact 004 / ledger H110; the current artifact 006 has not yet been projected or browser-verified. The scan-52 Director manifest reconciliation is due at 06:15 UTC.
