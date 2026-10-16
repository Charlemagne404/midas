# Gate A checkpoint 050 — scan-54 universe coverage replay

**Captured:** 2026-10-16T06:47:15.691518+00:00
**Mission status:** active; the bounded A1 discovery replay is verified through scan 54.

The offline replay verified all 54 saved snapshots, 324 Gamma responses, and retained CLOB books across 35,111,892 compressed snapshot bytes. Snapshot, Gamma, and CLOB response hashes verified. The current eligibility classifier matches stored eligible counts in all 54 scans.

| Measure | Result |
| --- | ---: |
| Distinct Gamma market IDs in bounded query unions | 6,303 |
| Eligible at least once | 2,185 |
| Selected market IDs over the panel | 960 |
| Selected outcome asset IDs | 1,920 |
| Attempted market-pair observations | 2,160 |
| Current-replay quality-valid pairs | 1,853 (85.79%) |
| Invalid pairs | 307 |
| Positive top-gross pairs / candidate events | 0 / 0 |
| Scans matching stored eligible counts | 54/54 |

The latest scan, `scan-20261016T063125Z-a83f9f475d62`, has a 296-ID bounded union: 122 eligible, 174 excluded, and 40 selected. Across the panel, 441 of 930 repeated comparable samples changed top-of-book fingerprints (47.42%). This is an intermittent activity proxy, not an update-rate or continuous-coverage estimate.

The A1 artifact still records the first-scan snapshot counter comparison of 5 versus 32. The paired v4 event reports 32 current quality-valid pairs and 5 legacy-freshness-valid pairs; see [Gate A counter-semantics note 001](VERITAS_MISSION2_GATE_A_COUNTER_SEMANTICS_NOTE_001.md). Keep the snapshot counter and replay values explicit; this is not evidence of missing payloads.

| Evidence | Value |
| --- | --- |
| Artifact | `docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_008.json` |
| File SHA-256 | `85a5e630621329463ee205470ce88b2655758b6e6039fc3bbc81a6db2f9b3e30` |
| Snapshot-manifest SHA-256 | `955d1932b5a06431418243ab893071e72dd14d265d9ad5cc75ec984aa977c967` |
| Gamma-response-manifest SHA-256 | `f63adc3d1abf13532a92a031bb7de152e6a05c1f075afc8301268bae1f8ed964` |
| Research ledger | H121 |

The six query frames are bounded and upstream-filtered, not a venue-wide denominator. Intermittent observations do not establish continuous book coverage, quote lifetime, sequence freshness, order arrival, fills, or profitability. No authenticated requests or orders were used.
