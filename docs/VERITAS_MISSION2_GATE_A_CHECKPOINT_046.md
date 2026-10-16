# Gate A checkpoint 046 — scan-50 universe coverage replay

**Captured:** 2026-10-16T04:38:43Z
**Mission status:** active; the expanded intermittent discovery panel is verified through scan 50.

The bounded offline A1 replay verified all 50 saved snapshots, Gamma responses,
and CLOB book payloads across 32,683,291 compressed bytes. It used no live HTTP
calls. Current eligibility classification matches the stored eligible count in
all 50 scans.

| Measure | Result |
| --- | ---: |
| Distinct Gamma market IDs | 6,059 |
| Eligible at least once | 2,166 |
| Selected market IDs | 887 |
| Selected outcome asset IDs | 1,774 |
| Attempted market-pair observations | 2,000 |
| Current-replay quality-valid pairs | 1,727 (86.35%) |
| Invalid pairs | 273 |
| Positive top-gross pairs / candidate events | 0 / 0 |
| Scans matching stored eligibility | 50/50 |

The latest scan, `scan-20261016T043140Z-6dbd91418e78`, has a 300-ID bounded
union: 190 eligible, 110 excluded, and 40 sampled. The 50-scan replay records
1,815 numeric conditional selection probabilities, scoped to the bounded
query-response union and frozen controls. Across 870 repeated-market
comparisons, 413 top-of-book fingerprints changed (47.47%); this is an
intermittent sampled-change proxy, not a venue update-rate estimate.

Artifact: `docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_004.json`
File SHA-256: `631e336e0d9023558a5f7a1ea8203e5ebc336aec7441dde53612d817acb24a3c`
Snapshot-manifest SHA-256: `80e22e4937a14341bb9eac4dc75e90caf1c227f687e45d740a13b9d4ce1486b4`

The earlier first-scan capture-versus-replay quality counter discrepancy
remains in the aggregate as one mismatch; it is preserved rather than
rewritten. The observed union is not a venue-wide denominator, and the
intermittent panel does not show continuous book coverage, quote lifetime,
sequence freshness, order arrival, or fills. The fixed coverage pilot remains
separate and nonrandomized.
