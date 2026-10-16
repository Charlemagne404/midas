# Gate B checkpoint 015 — independent replay through scan 78

**Captured:** 2026-10-16T18:38:29Z
**Mission status:** active; no quality-valid positive gross candidate observed.

## Independent source replay

Audit 016 independently replayed all 78 saved public snapshots, comprising
3,120 selected market observations and 50,119,641 compressed source bytes. It
reproduced all 2,628 stored v4 quality-valid decisions and top-edge results:
validity mismatches 0, top-edge mismatches 0. It checked 3,415 fee
calculations against the v3 collateral-entry fee model with zero disagreements.

| Check | Result |
| --- | ---: |
| Stored v4 / independent v3 quality-valid states | 2,628 / 2,628 |
| Strict reported-timestamp sensitivity states | 569 |
| Pairs with reported age over 5 seconds on a leg | 2,058 |
| Pair timestamp skew over 250 ms | 1 |
| Positive top-pair gross states | 0 |
| Positive full-depth gross states at quantities 5, 10, 20, 50, 100 | 0 at each quantity |
| Positive states after both minimums, single-match fee, or fragmentation-safe fee checks | 0 at each quantity |

All strict-freshness positive counts are also zero. This is a selected,
intermittent, correlated snapshot panel. It does not estimate a venue-wide
opportunity rate, prove atomicity or sequence freshness, or establish
executable fills. Timestamp age is a conservative sensitivity, not proof of
book freshness.

The latest scan (78) sampled 40 pairs, of which 38 passed quality checks. It
had zero positive top-gross pairs and zero positive states at the tested depth
and fee gates.

## Evidence and next action

- Independent replay: [audit 016](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_016.json)
- Artifact file SHA-256: `21259f83037de7f4d96fbf162a5ca8a5e0a6c4b94f41b1e1e42535d9b4852393`
- Result SHA-256: `820ba4a9438511a1c1fcf05b36cdf3d2867231e00d06a3b2203da35501a5c38c`
- Latest snapshot: `scan-20261016T183053Z-5cc3121a6906`

Keep no-trade. Do not train a model or promote a strategy from this panel. A
candidate-specific audit is justified only if a future quality-valid positive
gross state appears.
