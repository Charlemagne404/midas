# Gate A checkpoint 044 — 46-scan market-universe coverage

**Captured:** 2026-10-16 02:59 UTC

**Mission status:** active; the discovery union remains bounded and selected.

## Refreshed A1 coverage report

The offline A1 analyzer replayed all 46 saved snapshots spanning the first
scan at 05:59:28 UTC on October 15 through scan 46 at 02:30:17 UTC on October
16. It verified every snapshot evidence digest and retained Gamma and CLOB
response hash. The report covers 30,058,744 compressed snapshot bytes and
makes no public HTTP requests.

| Measure | 40-scan report 001 | 46-scan report 002 |
| --- | ---: | ---: |
| Distinct Gamma market IDs in bounded query unions | 5,319 | 5,784 |
| IDs eligible for the supported V1 pair rule at least once | 2,077 | 2,115 |
| Distinct IDs selected for paired observation | 741 | 820 |
| Selected pair observations | 1,600 | 1,840 |
| Quality-valid pairs under current replay | 1,405 | 1,600 |
| Positive top-gross pairs | 0 | 0 |

The six additional scans added 465 distinct Gamma IDs to the observed bounded
union, including 38 more IDs that met the supported V1 eligibility rule. The
selected panel added 79 IDs. Across all 46 scans the mean six-frame union was
298.98 unique IDs / 160.39 eligible IDs per scan; scan 46 itself returned
300 / 178. These values describe the retained query frames, not the venue
denominator.

All six query frames contributed eligible IDs conditional on the other five
frames. Mean unique / eligible IDs lost if a frame is removed were:

| Discovery frame | Mean unique IDs lost | Mean eligible IDs lost |
| --- | ---: | ---: |
| High liquidity | 49.17 | 11.02 |
| Low liquidity | 49.96 | 38.37 |
| Medium liquidity | 49.87 | 31.59 |
| Near expiry | 49.72 | 5.00 |
| Rotating ID control | 49.33 | 24.00 |
| Tagged near expiry | 49.91 | 49.91 |

Keep all six frames for now. The rotating ID control frame also preserves a
randomly sampled bounded-union control; its inclusion probability is
conditional on that union and is not a venue-wide probability.

## Data-quality qualifications

The source-verification and current-classifier replay matched the stored
eligible count for all 46 scans. A separate legacy capture-counter comparison
has one discrepancy on the first scan: its stored capture counter reports 5
valid pairs, while the current replay reports 32. This old scan predates the
current quality schema, so the mismatch is retained and disclosed rather than
folded into the v4 panel count. Across the full current replay there are
1,600/1,840 quality-valid pairs, 820 selected IDs, and zero positive gross
candidate events.

The 46-scan artifact is
[VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_002.json](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_002.json).
Its file SHA-256 is
`a85a34c6878e27f06666c2f8cf88b8aba28f1258ec48c0b818873c315af87a83`; the
snapshot manifest digest is
`a2350a9cafba373e9b6704f6f25984fc8fa36f4d83a3c6b43d8d55b3d0e82a1f`. The
dedicated coverage suite passed **2 tests**. See [Gate A checkpoint
043](VERITAS_MISSION2_GATE_A_CHECKPOINT_043.md) and [inventory
056](VERITAS_MISSION2_RESEARCH_INVENTORY_056.json).
