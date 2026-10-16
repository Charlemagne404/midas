# Gate A checkpoint 036 — marginal value of discovery frames

**Captured:** 2026-10-15 23:22 UTC  
**Mission status:** active; the six-frame v1 observer, fixed coverage pilot,
and protected Reality campaign remain unchanged.

## Historical frame replay

The new offline analyzer replayed all 39 finalized observatory snapshots and
verified the stored response hash for each of 234 Gamma pages. The snapshots
contain an average of 299.05 unique market IDs and 164.26 markets eligible for
the supported V1 binary pair analysis per scan. These are bounded-query counts,
not an estimate of the venue-wide market total.

Each 50-row query frame contributed almost 50 IDs that none of the other five
frames returned. Its mean exclusive V1-eligible contribution varied:

| Discovery frame | Mean unique IDs lost if removed | Mean V1-eligible IDs lost | Median eligible IDs lost | Scans with zero eligible loss |
| --- | ---: | ---: | ---: | ---: |
| High liquidity | 49.23 | 11.08 | 11 | 0/39 |
| Medium liquidity | 49.85 | 33.44 | 42 | 3/39 |
| Low liquidity | 49.95 | 39.26 | 48 | 1/39 |
| Near expiry | 49.72 | 5.77 | 0 | 24/39 |
| Rotating ID control frame | 49.41 | 24.23 | 16 | 4/39 |
| Tagged near expiry | 49.95 | 49.95 | 50 | 0/39 |

The near-expiry frame often contributes few markets to the current binary-pair
eligibility set, but it still supplies about 50 unique IDs per scan and covers
a distinct lifecycle stratum. Removing it solely to free a request would
weaken the broader discovery scope.

## Control-lookup budget sensitivity

For scan 39, the six-frame baseline returned 300 unique IDs, of which 174 were
V1-eligible. The explicit-ID response captured 10 minutes 50 seconds later
returned all eight controls; six passed V1 metadata checks, two had
`closed=true`, and the raw response was 47,860 bytes. The analyzer modeled
removing each frame and adding those later control rows. This is a design
sensitivity, not an observed scan, because the control response was later
than the snapshot.

| Frame removed | Five-frame union plus controls: eligible IDs | Delta vs. six-frame baseline |
| --- | ---: | ---: |
| High liquidity | 171 | -3 |
| Medium liquidity | 131 | -43 |
| Low liquidity | 155 | -19 |
| Near expiry | 177 | +3 |
| Rotating ID control frame | 127 | -47 |
| Tagged near expiry | 130 | -44 |

The one scan where dropping near-expiry looks favorable does not erase its
24/39 zero-eligible-loss scans, its distinct lifecycle role, or its unique
market IDs. The historical comparison therefore favors testing an eighth,
bounded request in a successor rather than cutting a discovery frame. One
additional request per 30-minute scan is a 14.3% call-count increase over the
current seven-call budget. The control response observed here was about 47 KiB;
at 48 scans per day, that response size would add about 2.3 MB of raw response
payload per day if its size stayed similar, before compression and record
metadata. Future runs still need explicit request, response-size, pacing, and
storage bounds.

## Decision and verification

Keep v1's seven-call plan and pinned code unchanged through its fixed stop.
After the pilot completes, test a separately versioned eight-call successor:
six discovery pages, one direct control lookup, and one batched book request.
Compare its full source hashes, cohort availability, quality yield, and
rotating coverage against the unchanged v1 baseline before adoption. The
existing 1-second request pacing and bounded response handling remain required.

The analyzer is in
[`discovery_frame_analysis.py`](../packages/midas/veritas/discovery_frame_analysis.py)
and [`analyze_veritas_discovery_frame_marginal.py`](../scripts/analyze_veritas_discovery_frame_marginal.py).
Its [versioned result](VERITAS_MISSION2_DISCOVERY_FRAME_MARGINAL_001.json)
contains snapshot and response manifests but no control market IDs. Three
focused analyzer tests and three control-retrieval tests passed; Ruff and
strict Mypy passed. The replay made no network calls, book requests, or orders.
The source ID filter and `closed=any` behavior are documented in Gamma's
[OpenAPI schema](https://gamma-api.polymarket.com/openapi.json).

Gate A remains in progress. See [research ledger H082](VERITAS_RESEARCH_LEDGER.json)
and [inventory 044](VERITAS_MISSION2_RESEARCH_INVENTORY_044.json).
