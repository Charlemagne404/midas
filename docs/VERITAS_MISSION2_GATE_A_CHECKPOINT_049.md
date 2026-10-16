# Gate A checkpoint 049 — scan-53 universe coverage replay

**Captured:** 2026-10-16T06:17:19.193058+00:00
**Mission status:** active; the bounded A1 discovery replay is verified through scan 53.

The offline replay verified all 53 saved snapshots, 318 Gamma responses, and retained CLOB books across 34,505,902 compressed snapshot bytes. Snapshot, Gamma, and CLOB response hashes verified. The current eligibility classifier matches stored eligible counts in all 53 scans. The replay uses only saved public responses.

| Measure | Result |
| --- | ---: |
| Distinct Gamma market IDs in bounded query unions | 6,248 |
| Eligible at least once | 2,183 |
| Selected market IDs over the panel | 942 |
| Selected outcome asset IDs | 1,884 |
| Attempted market-pair observations | 2,120 |
| Current-replay quality-valid pairs | 1,818 (85.75%) |
| Invalid pairs | 302 |
| Positive top-gross pairs / candidate events | 0 / 0 |
| Scans matching stored eligible counts | 53/53 |

The latest scan, `scan-20261016T060051Z-340d33b97461`, has a 300-ID bounded union: 147 eligible, 153 excluded, and 40 selected. Across the panel, 434 of 912 repeated comparable samples changed top-of-book fingerprints (47.59%). This is an intermittent activity proxy, not an update-rate or continuous-coverage estimate.

The first-scan capture discrepancy remains preserved: 5 captured-valid pairs versus 32 current-replay-valid pairs, a 27-pair aggregate difference. The replay reports 1,791 capture-recorded valid pairs versus 1,818 current-replay valid pairs. The independent audit 007 reproduces all 1,818 current-replay valid states with zero v4 validity or top-edge mismatches.

| Evidence | Value |
| --- | --- |
| Artifact | `docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_007.json` |
| File SHA-256 | `e7dd080c64564fb67c4ae2ac9fd9740fdbb2499894238b1758b0d99158fc6151` |
| Snapshot-manifest SHA-256 | `d2a5c700da54965f2d2bcdd0fd8af4fa0819f5ea10bd97e85e897016d981b953` |
| Gamma-response-manifest SHA-256 | `af2b1854d9f8d8cd456f6943d406e7ab3aae517e3afc81c86862caa3843b9976` |
| Research ledger | H118 |

The six query frames are bounded and upstream-filtered, not a venue-wide denominator. Intermittent observations do not establish continuous book coverage, quote lifetime, sequence freshness, order arrival, fills, or profitability. No authenticated requests or orders were used. The capture mismatch is unresolved.
