# Gate A checkpoint 053 — bounded market-universe replay through scan 58

**Captured:** 2026-10-16T08:33:22Z  
**Mission status:** active; the public observer and measurement pilot remain scheduled.

## Audit result

The offline A1 replay verified 58 saved public snapshots, all snapshot-evidence
hashes, Gamma response hashes, and stored eligible-count classifications. It
made no public requests and submitted no orders.

| Measure | Result |
| --- | ---: |
| Gamma responses / bounded distinct market IDs | 348 / 6,565 |
| Eligible at least once / excluded by latest metadata | 2,204 / 4,361 |
| Distinct selected market / condition IDs | 998 |
| Selected outcome asset IDs | 1,996 |
| Quality-valid pair observations / all selected observations | 1,981 / 2,320 |
| Scans matching stored eligible counts | 58 / 58 |
| Selected markets in latest scan | 40 of 167 eligible |
| Latest-scan bounded union | 288 IDs; 167 eligible; 121 excluded |
| Source identity conflicts / multiple conditions per Gamma ID | 0 / 0 |

Across the sampled window, the latest metadata classifies 1,600 IDs as
augmented-negative-risk structures with semantics not yet verified and 2,761
as unsupported outcome relationships. The six query frames each contributed
information to the eligible union. The replay records 304 markets with at
least one comparable repeat sample; the top of book changed in 495/1,021
sampled comparisons (48.48%). That is a snapshot-change proxy, not an update-
frequency or continuous-coverage measure.

## Interpretation and limits

Selection and inclusion probabilities remain conditional on bounded Gamma
query-response unions and frozen controls. The replay does not estimate the
full venue universe, establish continuous coverage, or prove that excluded
multi-outcome structures are arbitrage-free. Repeated observations are
dependent. Scan 58 adds three snapshots beyond the prior A1 artifact 009;
artifacts 009 and earlier remain unchanged.

## Evidence

- Artifact: [coverage replay 010](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_010.json)
- Artifact file SHA-256: `ab15c7de9d8611e2107ad074786754e8d92d1487e4d2358d189f0e55f3d0e6f3`
- Analysis module SHA-256: `3512586bfd7d63b0238abed2a7330556a10466c40f1624366b7bac5fc5138826`
- Runner SHA-256: `486712f5729f8a11d105d4bfe12649807ff52f6637d3d163cfd5420ec8d5d379`
- Ledger receipt: H128

The replay used saved local snapshots only. It did not modify the observer,
pilot, Arena package, Reality collector, or frozen campaign.
