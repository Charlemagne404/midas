# Gate A checkpoint 051 — scan-55 universe coverage replay

**Captured:** 2026-10-16T07:18:19.709216+00:00
**Mission status:** active; bounded A1 replay is verified through scan 55.

The offline replay verified all 55 saved snapshots, 330 Gamma responses, and retained CLOB books across 35,726,316 compressed snapshot bytes. Snapshot, Gamma, and CLOB response hashes verified; the current eligibility classifier matches stored eligible counts on 55/55 scans.

| Measure | Result |
| --- | ---: |
| Distinct Gamma market IDs in bounded query unions | 6,371 |
| Eligible at least once | 2,187 |
| Selected market IDs over the panel | 967 |
| Selected outcome asset IDs | 1,934 |
| Attempted market-pair observations | 2,200 |
| Current-replay quality-valid pairs | 1,882 (85.55%) |
| Invalid pairs | 318 |
| Positive top-gross pairs / candidate events | 0 / 0 |
| Scans matching stored eligible counts | 55/55 |

Latest scan `scan-20261016T070124Z-97345c9106e0` has a 300-ID bounded union: 106 eligible, 194 excluded, and 40 selected. This is a bounded intermittent sample, not a venue-wide denominator.

The snapshot-recorded valid-pair counter sum is 1,855 versus 1,882 on current replay. The 27-count difference is isolated to the first scan: its snapshot stores 5, while the paired v4 event records 32 current-quality pairs and 5 legacy-freshness pairs. See [Gate A counter-semantics note 001](VERITAS_MISSION2_GATE_A_COUNTER_SEMANTICS_NOTE_001.md); this comparison is not evidence of missing payloads.

| Evidence | Value |
| --- | --- |
| Artifact | `docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_009.json` |
| File SHA-256 | `ae99ddf9b53f68efc5c1fb67fcfbd65d5d33f34bd1aa48a7024ec222def8ae55` |
| Snapshot-manifest SHA-256 | `ca629a1572a6a8a0466de2d2baac3c1317c2c7c0e4089ac832d81699f9ed9102` |
| Gamma-response-manifest SHA-256 | `59e1a73e006c83c61cf4fb5403dd607b69d1b2f5160e4e9363d00aa857a4e628` |
| Research ledger | H123 |

The six query frames remain bounded and upstream-filtered. Intermittent observations do not establish continuous book coverage, quote lifetime, sequence freshness, order arrival, fills, or profitability. No authenticated requests or orders were used.
