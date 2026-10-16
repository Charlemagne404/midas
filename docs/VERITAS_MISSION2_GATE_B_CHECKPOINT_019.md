# Gate B checkpoint 019 — independent audit through scan 85

**Captured:** 2026-10-16 22:13:55 UTC  
**Experiment:** `VERITAS-M2-INDEPENDENT-SOURCE-AUDIT-002`  
**Status:** Independent v3 replay agrees with the stored v4 analysis through all 85 saved scans. No positive gross candidate was observed.

## Reproduction

The bounded audit replayed every immutable public snapshot and its associated
v4 analysis event from `data/veritas-observatory`. The versioned result is
[audit 021](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_021.json). It covers
85 scans and 3,400 selected market-pair observations. The source-manifest
digest is
`8e5d053a4865b5d0877a57be36a9d082fba7dc82cd7568ade2826fc2ffb5c8aa`; the
independent audit code digest is
`ff0d89ef437a051b27002ca9a5f6deb5b1f7dca52e87883894a48ccc726f98e2`; and the
result digest is
`5e95a18df8ea9a513b43c32adcd0c1219fadaec11e7e76837fcb3590d040b3c5`.

## Results

| Check | Through scan 84 | Through scan 85 |
| --- | ---: | ---: |
| Selected observations | 3,360 | 3,400 |
| Stored v4 / independent v3 quality-valid states | 2,845 / 2,845 | 2,874 / 2,874 |
| Validity mismatches | 0 | 0 |
| Top-edge mismatches | 0 | 0 |
| Independent fee calculations / disagreements | 3,768 / 0 | 3,826 / 0 |
| Strict reported-timestamp sensitivity states | 622 | 627 |
| Pairs over the five-second reported-age bound | 2,222 | 2,246 |
| Pairs over the 250 ms timestamp-skew bound | 1 | 1 |
| Positive top-pair gross candidates | 0 | 0 |
| Positive full-depth, minimum, or fee-qualified candidates | 0 | 0 |

All tested quantities (5, 10, 20, 50, and 100 shares) remain zero-positive
under the gross, displayed-depth, per-leg minimum, and fee sensitivity gates.
Repeated scan states are correlated and are not independent opportunity
trials.

## Historical capture-label difference

The capture-time `audit.valid` labels sum to 2,847 across these 85 snapshots,
while the v4 analysis events and independent v3 replay each count 2,874. The
27-state difference is confined to the first scan: 5 capture-time states
versus 32 under the later replay. That scan uses the earlier source revision
`1c25a275c6ee39930b3da499a1c4cdfce41a204ad64a9d014cd534d2d4cb2c45`; its
capture-time audit labels the affected books `yes_book_stale`. The later
request-to-receipt gate records those states as valid while separately marking
the old reported-age condition false. The subsequent 84 scans, from source
revision
`4ab2fa35be8d568a6e65a833f26f3c32e5b20f821bfb6e6c3ddcb9474bd6f060`, have no
capture-time versus v4 label differences. The original snapshot and labels
were not altered.

This resolves the provenance of the previously noted first-scan difference;
it does not weaken the current gate or establish venue sequence freshness.

## Interpretation and limits

The supported same-condition binary arithmetic and the v4 implementation
agree over the current saved panel. No positive gross discrepancy appeared,
so no depth, minimum, fee, strategy-return, or fill claim follows. Returned
timestamps and request-to-receipt timing do not prove upstream sequence
freshness, atomic books, quote persistence, order arrival, or execution. The
sample is intermittent and selected, not a venue-wide denominator. No
authenticated requests or orders were used.
