# Gate A checkpoint 028 — scan 30 and book timestamp/hash audit

**Captured:** 2026-10-15T18:31:00.171496Z  
**Mission status:** active; no candidate qualified.

## Scheduled scan 30

Scan `scan-20261015T183100Z-3e11a6dc87d4` completed on its scheduled
collector cycle. The bounded six-frame discovery returned 300 records and 300
unique IDs; 161 passed same-condition V1 eligibility and 139 were excluded (77
with unverified augmented NegRisk semantics and 62 unsupported outcome
relationships). Forty pairs were selected, 36 passed the request/receipt
completeness gate, and four had an empty ask side. The older five-second
reported-update-age rule accepts six of the 36; pair timestamp skew exceeded
250 ms for zero pairs. All gross/depth/minimum/fee gates remain zero-positive.
The best quality-valid top edge was -$0.001/share.

The 30-snapshot panel now contains 1,200 selected observations, 1,070 passing
the request/receipt gate, 130 invalid observations, and 558 distinct market
IDs. The five-second reported-update-age rule accepts 246/1,200, while the
request/receipt completeness rule accepts 1,070/1,200. This is a gate-yield
comparison, not a venue freshness guarantee. No positive gross state has
appeared.

- Scan analysis-event SHA-256: `91d34e0fce5802d479545f127fb2574dff04de69b109c8013867e0bee003bc25`
- Snapshot evidence SHA-256: `3e11a6dc87d449a65e6a7446d114530b70d21fa8cb7f20bb2656e86e29982fe3`
- Compressed snapshot file SHA-256: `66a7973e24a330ba970df67abce17a4582b1f7ff5351c075c45c962402ba561f`

## Timestamp and state-hash evidence

A read-only comparison of the 30 finalized snapshot files followed the raw CLOB
book hash and timestamp for role-labelled stable-control outcomes. Among 250
transitions between sampled appearances across eight market IDs and 16 token
books, the hash and timestamp both advanced 248 times and both remained
unchanged twice. There were no mismatches. Of 133 paired market appearances,
132 had exactly equal outcome timestamps and the maximum pair skew was 1 ms.
Across 266 book observations, reported timestamp age ranged from 207 ms to
1,009,288 ms, with nearest-rank median 38,003 ms. The input file manifest SHA-256
is `7a4a1deb3e481f39edfe070058d94fedb6e4cbe8decd5778bc22c2d4086c539a`; the
result SHA-256 is
`e34131d5645d8581f12150ef799dbcfd765ddaa5fa93334e00bf0b9e7c7c0f17`.

This pattern is consistent with the CLOB timestamp marking when book state
changed. It does not prove that interpretation, uninterrupted delivery, or
freshness of an unchanged snapshot. Polymarket's [book documentation](https://docs.polymarket.com/market-data/prices-order-books)
describes the hash as a way to detect state changes between reads; its published
[market-book event schema](https://docs.polymarket.com/market-data/realtime-data)
contains no sequence field. Keep the five-second age measure as a reported
update-recency diagnostic and preserve independent freshness/continuity checks
for promotion.

The scheduled source-analysis and Director timers remain in control; no manual
poll, retry, or service restart was used. See [research ledger H068](VERITAS_RESEARCH_LEDGER.json)
and [inventory 035](VERITAS_MISSION2_RESEARCH_INVENTORY_035.json) for the complete
input lineage. Mission 2 remains active.

## Scheduled qualification and source-analysis follow-up

The 18:45 UTC Director cycle reconciled the legacy scan-28 v2 finding and
admitted the scan-30 v3 qualification. Job
`job-0aa6327f9d734da6b7be9dc3` completed 30/30 in 1.90 seconds. Its persisted
finding reports 1,070 request/receipt-valid pairs across 30 snapshots and zero
positive candidates at each of the five economic gates. The job record is
complete, while the Director manifest still projects it as queued; leave that
projection for the scheduled 19:15:13 UTC cycle.
The qualification result is recorded as [research ledger H069](VERITAS_RESEARCH_LEDGER.json).

The 18:44:49 UTC finalized-source replay completed normally, processing 112
segments (33.29 MB). Its catalog prefix is 3,019/4,081 segments, with 1,062
segments and 312.43 MB pending. The campaign window contains 151,539
quality-valid states and remains zero-positive. The recurrence used 13.1 CPU
seconds, peaked at 137.5 MiB, and used no swap.
