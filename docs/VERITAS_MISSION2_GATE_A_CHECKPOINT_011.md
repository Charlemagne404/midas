# Veritas Mission 2 Gate A Checkpoint 011 — Rotating Discovery and Arena Qualification

- **Captured:** 2026-10-15 10:14 UTC
- **Branch:** `project/veritas`
- **Base commit:** `0c9e35c` (`docs(veritas): checkpoint fifth source replay`)
- **Status:** The scheduled v2 discovery scan, v4 indexing, dashboard browser workflow, and a bounded Arena qualification job all completed. Mission 2 remains active.

## Scheduled public discovery

The scheduled observer ran at 10:01:06 UTC and exited successfully at
10:01:22 UTC. The scan captured at 10:01:16 UTC as
`scan-20261015T100116Z-7d135306c470`. Systemd recorded 624 ms of CPU time and a
28.4 MiB memory peak; the timer remains active and the next scheduled event is
12:31 CEST. No manual scan was run.

This is the first live scan under `veritas-public-observatory-v2` and
`stratified-gamma-page-rotation-v2`. Six Gamma frames each returned up to 50
rows. The high-, medium-, and low-liquidity frames used offsets 571, 842, and
113; the rotating ID frame used offset 384. Near-expiry frames remained
unoffset. The frames yielded 300 unique IDs, 132 supported same-condition V1
binary pairs, and 168 explicit exclusions (109 augmented negative-risk
markets and 59 unsupported outcome relationships).

The selected cohort contained 40 markets: three of the eight frozen control
IDs were present, with the other five reported missing and not replaced; 37
markets rotated through expiry strata. Selection probabilities are recorded
per market and remain conditional on this bounded query union and frozen
controls. Category labels now prefer market/event category metadata before
tags, and the selected record states which metadata source supplied the
primary label.

All seven logical reads succeeded on their first attempt: six discovery reads
and one CLOB books batch. The scan made seven HTTP attempts, below the 14
attempt ceiling. The response, pacing, request, and storage limits remain:

- 40 target markets, 50-market hard maximum, six pages capped at 50 rows;
- at most seven logical reads and 14 HTTP attempts per scan, with one retry
  maximum per logical read and a 15-second timeout;
- 48 MiB maximum per response, one-second request pacing, five book quantities
  (5, 10, 20, 50, 100 shares), and a 1 GiB observatory-root cap.

The pre-existing frozen control file was not rewritten; its SHA256 remains
`9578217e20dcc7d1c65fa110f0ed7c689b55483b61191f1aae8d30c9b7300d9a`. Its
original v1 record version is accepted by the new scanner. The compressed
snapshot SHA256 is
`a12fb9906c04c7a7cf697dbb46484d732a02d5c423ecaf8378137b2d4d1276d7`; the
snapshot evidence digest is
`7d135306c470b7d95f1e83025263b2968d8b17265d29a4b54a0cc0ad3ff9539a`.

The latest scan had 38 valid pairs out of 40, two empty-ask invalid pairs, and
zero positive top, full-depth, minimum-notional, single-match-fee, or
fragmentation-safe-fee candidates. It submitted no orders and used no
authenticated request path.

## Continuous panel and Arena research

The v4 analyzer indexed the new snapshot without pending work. The 13-snapshot
panel now spans 05:59:28–10:01:16 UTC (241.80 minutes), with 520 attempted
market pairs, 469 quality-valid pairs, 51 invalid pairs, and 186 distinct
market IDs. The previous reported-age/skew gate accepts 122 pairs; the paired
yield difference is 347 pairs (+66.73 percentage points). This request/receipt
measurement does not establish venue sequence freshness or atomicity.
Across 334 sampled consecutive state comparisons, 319 fingerprints changed;
the classification remains an intermittent snapshot comparison, not a venue
update-rate estimate.

The new Arena job kind reads only the pinned finalized v4 analysis-event
prefix. It accepts at most 512 events and 64 MiB of source events, uses a fixed
20-share comparison, has a 300-second wall limit, and writes an idempotent
Arena finding. It makes no network requests and does not write to snapshot or
Reality data. The real run completed as
`job-13280ea8cb2d427c938f0a3e` in about 2.11 seconds, processing 13 events /
237,821 bytes. Its deterministic finding is
`veritas-qualification-v1-f56acbc2267455d2`, with manifest SHA256
`794de33531287125dfee52de9d87f7c7c04ce4f05bade69c8d3673025267f7ee`.

The Arena comparison found zero positive states across all gates: 469 valid
states, 186 markets, and a top-edge median of -0.028 per share with maximum
-0.001. The result remains candidate qualification, not strategy PnL,
execution, or profitability. Repeating admission for the same scan returned
the same job ID. The read-only activity projection reports one completed job,
zero active jobs, and zero invalid artifacts.

## Dashboard and verification

The Veritas view now shows the frame protocol, per-market conditional
selection probabilities and category source, actual HTTP attempts, collector
bounds, and Arena job/Director/schedule/alert activity. Its qualification
button is enabled only when a v2 scan and finalized v4 event are present. The
bounded discovery Playwright workflow passed against the live finalized
snapshot and analysis artifacts.

Verification for this checkpoint:

| Check | Result |
| --- | --- |
| Related Veritas and Arena backend regression group | 132 passed; one existing Starlette/httpx deprecation warning |
| Frontend unit tests | 29 passed |
| Ruff, Python formatting, strict Mypy | Passed |
| Frontend lint, typecheck, Prettier check, production build | Passed; Vite retains its large-chunk advisory |
| Playwright bounded-discovery workflow | 1 passed; v2 frame and finalized evidence verified |
| Arena job execution and idempotent re-admission | Completed; 13/13 events; same job returned |
| Frozen control identity | Original v1 control file hash unchanged |

## Open requirements and preservation

The bounded union is not a venue census and the rotating offsets do not imply
venue-wide inclusion probabilities. Observations remain intermittent,
selected, and dependent. Independent sequence/freshness evidence, the 24-hour
pilot review, the original 48-hour follow-up and dependence gates, a complete
Research Director cycle, strategy comparison, model training, and campaign
window source replay remain open. With no positive gross candidates, the
unchanged no-trade policy remains in force.

The observer and source-analysis timers remain active. The 10:10 UTC scheduled
source-analysis recurrence completed at 10:13:32 UTC, processing 36 segments /
33,314,216 bytes in 179 seconds. It used 8.962 CPU seconds, peaked at 149.7 MiB
RAM, and used no swap. The replay now covers 944/3,077 finalized segments, with
2,133 segments / 571,624,064 bytes pending through ordinal 108,963. No
campaign-window frames were found and no active segment was read. All 944
sealed event files were reverified; their rolling chain matches the sealed
state, and the summary/state digests validate.

Reality remains clean at `714f824`, and its API, collector, and shadow services
were active. No Reality, Laboratory, Prometheus, historical Arena, or campaign
evidence was rewritten. No live service was restarted, and no real-money action
occurred.

The current evidence lineage is recorded in [research inventory 012](VERITAS_MISSION2_RESEARCH_INVENTORY_012.json); inventory 011 and checkpoint 010 remain preserved.
