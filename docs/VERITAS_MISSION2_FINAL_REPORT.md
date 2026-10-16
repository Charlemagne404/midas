# Project Veritas Mission 2 — Current Engineering Report

## Latest update — 2026-10-16T05:22:16Z

The independent raw-source audit now covers 51 snapshots / 2,040 observations.
It reproduces all 1,755 v4 quality-valid decisions and top edges with zero
mismatches. Strict reported-age sensitivity admits 379 states; every top-gross,
depth, minimum, and fee gate remains zero. Reported age still does not prove
sequence freshness or executable liquidity. See [Gate B checkpoint
006](VERITAS_MISSION2_GATE_B_CHECKPOINT_006.md), [audit
005](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_005.json), and ledger
H114.

The gap-detail prefix advanced to 3,019/5,344 replayable segments, with 735
campaign-window gap events and 2,323 segments / 633,802,218 bytes pending.
The source analyzer remains current at 5,324/5,324 cataloged segments and
361,068 quality-valid states across 91 markets, with no positive gross or
economic states. The scan-51 Director projection is due for scheduled
reconciliation at 05:45:02 UTC. Mission 2 remains active; the archive timeout
is unresolved. See [operations](VERITAS_MISSION2_OPERATIONS.md) and [inventory
068](VERITAS_MISSION2_RESEARCH_INVENTORY_068.json).

## Previous update — 2026-10-16T05:17:20Z

Scan 51 completed its scheduled v4 Arena qualification: 1,755/2,040 pairs
were quality-valid across 903 selected markets; the maximum top-pair edge was
-$0.001/share, and all five gross, depth, minimum, and fee gates remained
zero-positive. Candidate evidence and independent replay are complete with
zero rows. The Director reconciled scan 50 and admits scan 51, whose completed
child remains projected as `QUEUED` until the 05:45:02 UTC scheduled cycle.
See [Gate F checkpoint 032](VERITAS_MISSION2_GATE_F_CHECKPOINT_032.md) and
ledger H113.

The finalized-source analyzer now covers 5,324/5,324 cataloged segments / 1.376
GB, with 361,068 quality-valid states across 91 markets and no positive
top-ask, full-depth, or minimum-notional state. Its campaign-window readiness
remains collecting. See [Gate C checkpoint
017](VERITAS_MISSION2_GATE_C_CHECKPOINT_017.md).

The 51-snapshot timestamp/content association audit remains bounded and does
not prove freshness semantics; see [Gate B checkpoint
005](VERITAS_MISSION2_GATE_B_CHECKPOINT_005.md). Midas and Reality APIs
returned READY in demo mode, while the archive service remains failed after
timeout. Mission 2 remains active; no full regression was run. See
[operations](VERITAS_MISSION2_OPERATIONS.md) and [inventory
067](VERITAS_MISSION2_RESEARCH_INVENTORY_067.json).

## Previous update — 2026-10-16T05:06:29Z

The new bounded reported timestamp audit verifies 51 saved snapshots / 4,080
book observations. All 2,197 content-changing repeated-asset endpoints had an
advancing reported timestamp; timestamp advancement also appeared in 37
unchanged-content transitions. Endpoint ages over five seconds are not proof
of stale quotes, and the result does not establish timestamp semantics or
sequence freshness. See [Gate B checkpoint
005](VERITAS_MISSION2_GATE_B_CHECKPOINT_005.md), [artifact
001](VERITAS_MISSION2_REPORTED_BOOK_TIMESTAMP_AUDIT_001.json), and ledger
H112.

Scan 51 completed with 28/40 quality-valid pairs and zero positive top-gross
pairs. The fixed pilot is at 20/48 scans, 652/800 valid slots, and one missed
sequence. The scan-50 Director child completed with no positive candidate;
scheduled manifest reconciliation remains pending. The 05:05 gap-detail batch
is running, and the 30-minute archive service remains failed after timeout.
Midas and Reality APIs returned READY in demo mode with live execution
disabled. Mission 2 remains active. See [operations](VERITAS_MISSION2_OPERATIONS.md)
and [inventory 066](VERITAS_MISSION2_RESEARCH_INVENTORY_066.json).

The timestamp audit's four focused tests passed; Ruff, formatting, strict
Mypy, and the artifact digest check passed. No full mission regression was
run. The analysis used saved source data only and made no network requests or
orders.

## Previous update — 2026-10-16T04:42:06Z

The offline market-universe replay and independent opportunity audit now both
cover 50 snapshots / 2,000 selected pair observations. Coverage artifact 004
verified 32,683,291 compressed bytes, 6,059 Gamma IDs, 2,166 eligible IDs,
887 selected IDs, and 1,727 quality-valid pairs. The independent audit matched
all 1,727 stored validity and top-edge results with zero mismatches. Its
reported-age sensitivity admits 374 states. No top-gross, depth, minimum, or
fee-qualified positive appears. These are selected intermittent observations,
not continuous or venue-wide evidence. See [Gate A checkpoint
046](VERITAS_MISSION2_GATE_A_CHECKPOINT_046.md), [Gate B checkpoint
004](VERITAS_MISSION2_GATE_B_CHECKPOINT_004.md), and artifacts [coverage
004](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_004.json) and [audit
004](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_004.json).

The dashboard coverage route now targets artifact 004 and ledger H110; H111
records the independent audit. The dashboard API and coverage tests passed
28 cases; Ruff, formatting, strict Mypy, and diff checks passed. The
in-process overview and artifact routes returned HTTP 200 with the matching
artifact digest. The scheduled Director cycle is due at 04:45 UTC. Mission 2
remains active.

The 04:40 finalized-source run has also completed: 5,264/5,264 segments /
1,358,762,036 bytes, 354,898 quality-valid states across 87 markets, zero
positive gross/depth/minimum states, and no active segment reads. See [Gate C
checkpoint 016](VERITAS_MISSION2_GATE_C_CHECKPOINT_016.md). The scheduled
Director cycle is due at 04:45 UTC. Mission 2 remains active.

The 04:40 finalized-source run has also completed: 5,264/5,264 segments /
1,358,762,036 bytes, 354,898 quality-valid states across 87 markets, zero
positive gross/depth/minimum states, and no active segment reads. See [Gate C
checkpoint 016](VERITAS_MISSION2_GATE_C_CHECKPOINT_016.md). The scheduled
Director cycle is due at 04:45 UTC. Mission 2 remains active.

## Previous update — 2026-10-16T04:29:03Z

The scheduled gap-detail run completed without restart and advanced the
finalized replay prefix to 2,545/5,224 replayable segments. The partial prefix
contains 500 campaign-window resynchronization events across 20 markets, with
2,679 segments / 736,206,152 bytes pending. The new read-only attribution
artifact scanned 40,075 censored outcomes, verified 339 gap-related rows, and
reduced terminations beyond the indexed prefix from 86 to 25. It found 63
same-market temporal candidate links (nine unique gaps); those are not causal
proof. See [Gate C checkpoint
015](VERITAS_MISSION2_GATE_C_CHECKPOINT_015.md).

The dashboard API now serves the versioned attribution artifact 002 and
validates the H109 ledger receipt. Its focused API/coverage tests passed 28
cases, with Ruff, formatting, strict Mypy, and diff checks passing. The update
is source-only and undeployed. Mission 2 remains active; strategy P&L, fill
evidence, and model training remain unsupported without positive candidates
and suitable labels. See [Gate G checkpoint
014](VERITAS_MISSION2_GATE_G_CHECKPOINT_014.md) and [operations
checkpoint](VERITAS_MISSION2_OPERATIONS.md).

**Status:** Mission 2 remains active. Discovery, independent binary-pair arithmetic, bounded public observation, continuous finalized-snapshot analysis, candidate qualification, paired measurement comparison, market/time censoring analysis, and the read-only dashboard are implemented. The recurring scan-pinned Veritas Research Director consumes the independently maintained finalized-source summary alongside public-scan qualification. A new bounded audit confirms public markout measurements exist in the frozen campaign, but they do not provide a usable opportunity target or execution/P&L labels. Strategy/model experiments, broader dashboard scope, and longer independent validation remain open.

**Date:** 2026-10-16
**Branch:** `project/veritas`
**Original checkpoint base commit:** `48688f1`; **latest follow-up base commit:** `54cf9dd`.

## Latest checkpoint addendum — 2026-10-15 19:58 UTC

The 32-snapshot panel contains 1,136/1,280 quality-valid pairs across 598
selected market IDs. Scan-32 Arena qualification completed 32/32 events at
19:46:25 UTC and found zero positive states at all five economic gates; the
Director manifest awaits its scheduled reconciliation.

The separate frozen-campaign v1.4 forensic audit found 937 public markout
measurements across 41,012 follow-up slots, with 40,075 censored. At five
seconds, 473/3,503 valid initial decisions were observed; all 473 had no
initial discrepancy, null opportunity persistence, and
`unknown_counterfactual` execution ground truth. The strongest supported
conclusion is that these marks do not support a strategy/model comparison;
they are not evidence of fills or P&L. See [Gate C checkpoint
003](VERITAS_MISSION2_GATE_C_CHECKPOINT_003.md) and the
[summary artifact](VERITAS_MISSION2_LABEL_FEASIBILITY_001.json).

Finalized-source replay remains partial at 3,260/4,200 segments, with 940
pending and zero positive top-ask/full-depth states. The eight-market Reality
recorder is active but its latest logged state is degraded after a name
resolution failure, with last observation at 04:57 UTC. The frozen shadow
service remains active after one automatic restart for source
integrity/continuity mismatch. No Reality service or campaign was changed for
this checkpoint. Mission 2 remains active.

## Changes in this checkpoint

- Analyzer v4 preserves v1–v3 artifacts and adds per-market selection/validity coverage, sampled state fingerprints/transitions, and the prior reported-age/skew classification paired on each saved payload.
- The dashboard and read-only API expose category/liquidity/expiry/spread strata, old/current gate yield, sampled state-change bands, and least-covered markets.
- The economic experiment now follows the current snapshot analysis version when loading immutable events, so qualification reads v4 evidence.
- A stale source-integrity fixture now mutates a nonempty processed segment rather than the intentionally skipped empty catalog header.

## Earlier evidence at the twelve-snapshot checkpoint

The panel covers 05:59:28–09:00:47 UTC: 12 snapshots, 480 selected observations, 161 distinct market IDs, and 431 request/receipt-valid pairs. The prior 5-second reported-age plus 250 ms cross-outcome-skew gate accepts 107/480. The paired yield difference is +324 pairs, or +67.5 percentage points. The corrected gate has 49 empty-ask invalid pairs remaining.

Across 319 sampled consecutive book-state comparisons, 304 fingerprints differ. These intermittent observations do not estimate WebSocket activity or true quote update rates. The latest bounded discovery union is 300 IDs, with 167 supported same-condition V1 binary pairs and 133 exclusions. The selected cohort remains 40 markets, 34 rotating and six available frozen controls.

The deterministic qualification run `VERITAS-M2-ECO-QUAL-001-RUN-b401cd384481` used v4 data (480 attempted pairs, 431 valid, 161 distinct markets). It found zero positive states at the unchanged top-ask gross-sign baseline, full 20-share displayed depth, per-leg minimum notional, single-match fee, and fragmentation-safe fee gates. This is not a profitability or fill result and does not prove venue-wide absence.

The 08:44 UTC forensic snapshot covers 10,165 frozen-campaign decisions across 42 markets and 36 connected families. It records 930 public follow-up measurements, 39,730 censor labels, and zero pending outcome rows across 40,660 horizon slots. Valid-start yield rises from 0.83% at 100 ms to 13.50% at 5 seconds. The largest censor bucket, `future_observation_unavailable`, remains an unresolved mixture of venue inactivity, cohort selection, and feed coverage. See [Gate C checkpoint 001](VERITAS_MISSION2_GATE_C_CHECKPOINT_001.md) and [Gate G checkpoint 003](VERITAS_MISSION2_GATE_G_CHECKPOINT_003.md).

At the twelve-snapshot checkpoint, the latest scan was `scan-20261015T090047Z-6f98ffeaecab`; its qualification run had zero positive states. The Reality source replay remains bounded and read-only at 786/2,959 replayable finalized segments, with 2,173 pending and no campaign-window frames in the processed prefix. The live public observer and source-replay timers remain active. See [operations](VERITAS_MISSION2_OPERATIONS.md) and [Gate A checkpoint 010](VERITAS_MISSION2_GATE_A_CHECKPOINT_010.md).

## Earlier checkpoint verification

- Veritas backend regression suite: 88 passed; one Starlette/httpx deprecation warning.
- Ruff and strict Mypy on changed Python sources: passed.
- Frontend unit tests: 29 passed; typecheck, lint, formatting check, and production build passed. The existing Vite large-chunk advisory remains.
- Earlier Veritas Playwright workflow passed. A broader browser set had six passes and one unrelated Reality exact-heading assertion failure; no Reality source was changed.
- `git diff --check` and documentation/inventory validation are run before this checkpoint commit.

## Scientific limits and remaining work

Request-to-receipt duration does not prove venue sequence or batch atomicity. Snapshots and campaign decisions are selected, intermittent, and correlated. The v4 reclassification is retrospective for the ten initial snapshots; thirteen later scheduled snapshots were captured under v4. The censoring audit is a bounded read-only SQL snapshot; it did not replay the complete event hash chain or run a full SQLite integrity scan. `future_observation_unavailable` does not establish whether a venue was quiet or the feed failed to expose a quote. There is no positive gross candidate, so strategy PnL testing, model training, or promotion is unsupported. The original follow-up study's readiness gates remain intact.

Mission 2 is not complete. Continue safe observation; seek independent source coverage or sequence evidence to separate unavailable future observations from feed gaps; review the recurring Director after longer operation; coordinate source replay only if its information value justifies another bounded workflow; expand dashboard research/readiness surfaces; and gather independent temporal evidence before any economic claim.

## Preserved systems

No Reality campaign rule, observation, historical result, or service writer was changed. Existing Veritas, Prometheus, Arena, and Laboratory evidence remains preserved. No orders, wallets, deposits, credentials, authenticated trading APIs, or real-money activity were used.

Detailed implementation and evidence: [engineering checkpoint](VERITAS_MISSION2_ENGINEERING.md), [Gate A 008](VERITAS_MISSION2_GATE_A_CHECKPOINT_008.md), [Gate A 009](VERITAS_MISSION2_GATE_A_CHECKPOINT_009.md), [Gate A 010](VERITAS_MISSION2_GATE_A_CHECKPOINT_010.md), [Gate C 001](VERITAS_MISSION2_GATE_C_CHECKPOINT_001.md), [Gate G 002](VERITAS_MISSION2_GATE_G_CHECKPOINT_002.md), [Gate G 003](VERITAS_MISSION2_GATE_G_CHECKPOINT_003.md), [measurement comparison 002](VERITAS_MISSION2_MEASUREMENT_COMPARISON_002.md), [research inventory 010](VERITAS_MISSION2_RESEARCH_INVENTORY_010.json), and [current research inventory 011](VERITAS_MISSION2_RESEARCH_INVENTORY_011.json).

## Checkpoint addendum — 2026-10-15

The next scheduled discovery cycle completed with the v2 rotating query-frame
protocol. Scan `scan-20261015T100116Z-7d135306c470` returned 300 bounded query
IDs, 132 supported binary pairs, and 168 explicit exclusions; 40 markets were
selected and 38 pairs passed the common quality checks. It found zero positive
gross candidates. The v4 analyzer indexed all 13 snapshots (469 valid pairs,
186 distinct IDs), with 347 more valid pairs than the prior reported-age/skew
gate. This remains selected intermittent coverage, not a venue census or
independent sequence-freshness result.

A bounded Arena worker consumed the 13 finalized v4 events, processed 237,821
source bytes, and completed in about 2.11 seconds. Its 20-share qualification
found no positive states across the gross, depth, minimum-notional, and fee
gates. The result is stored as
`veritas-qualification-v1-f56acbc2267455d2`; repeat admission for the same
scan returned the existing job. The new browser workflow passed with the live
v2 and v4 artifacts.

The Veritas and Arena backend regression group passed 132 tests; the frontend
passed 29 tests, with Ruff, strict Mypy, formatting, lint, typecheck, build,
and browser verification also passing. The frozen control record kept its
original hash. No Reality, campaign, Laboratory, Prometheus, or historical
Arena evidence was altered, and no orders or authenticated requests were
made. The observer and source-analysis timers remain active.

The 10:10 UTC source replay completed within bounds at 944/3,077 finalized
segments, with 2,133 pending and zero campaign-window frames. All 944 event
hashes and the rolling chain were reverified against sealed state.

Mission 2 remains active. Independent freshness evidence, the 24-hour pilot
review, the 48-hour follow-up and dependence gates, continued source replay,
the full Director workflow, and any strategy/model comparison remain open.
See [Gate A checkpoint 011](VERITAS_MISSION2_GATE_A_CHECKPOINT_011.md) and
[research inventory 012](VERITAS_MISSION2_RESEARCH_INVENTORY_012.json).

## Gate F checkpoint addendum — 2026-10-15

The 10:31:10 UTC observer scan
`scan-20261015T103110Z-b077f9c3d7be` brought the v4 panel to 14 finalized
snapshots, 560 selected observations, 507 request/receipt-valid pairs, 210
distinct observed markets, and zero pending snapshots. The current bounded
discovery union contains 300 IDs, 184 eligible same-condition binary pairs,
and 116 explicit exclusions; the selected 40-market frame had 38 valid pairs.
Across the cumulative panel the prior reported-age/skew gate accepts 128 of
560, compared with 507 under the current gate, a paired gain of 379 states
(67.68 percentage points). This remains intermittent selected coverage and
does not verify venue sequence or quote lifetime.

The enabled Research Director timer runs at :15 and :45 UTC. Its first
operational cycle admitted one scan-pinned Arena job for the new v4 evidence,
processed 14 events / 256,411 source bytes, and persisted
`veritas-qualification-v1-115a375a2bd16454`. Every top-ask, full-depth,
minimum-notional, single-match-fee, and fragmentation-safe-fee count is zero.
The maximum observed top-pair edge is -0.001 per share. The Director keeps
no-trade, marks strategy review not ready without an eligible gross candidate,
and marks model work not ready without outcome labels. It does not promote
models or change source code. The read-only Arena API and dashboard show the
scan IDs, sample counts, readiness, and recommendation.

The Director service is bounded at CPU 5% and 512 MiB. Its qualification jobs
are bounded at CPU 10%, 512 MiB, 300 seconds, 64 MiB of source, and 512 events.
The service and future workers restrict address families to `AF_UNIX`. The
timer is active, the latest finding is complete, the Arena root has no active
jobs, and the API activity projection reports zero invalid artifacts.

The separate 10:40 UTC source-replay recurrence processed 128 finalized
segments / 30,283,274 bytes in 155 seconds, using 7.737 CPU seconds and 132.1
MiB peak memory. The prefix now covers 1,072/3,136 replayable segments, with
2,064 pending and no campaign-window frames. The service continues to read
only finalized `.seg` files; current sealed state and summary digests are in
[research inventory 013](VERITAS_MISSION2_RESEARCH_INVENTORY_013.json).

The focused backend regression set passed 133 tests; frontend tests passed 29,
and lint, formatting, strict typing, production build, and the Veritas browser
workflow passed. The broad all-Arena suite was stopped early while it was
running unrelated simulator/stress cases under the active collector; the
affected Veritas and Arena groups completed. The production build retains its
existing Vite large-chunk advisory. One 11:30 CEST observer run failed on the
legacy control-cohort version check; its frozen file hash was unchanged, and
the next two scheduled observations succeeded.

Mission 2 remains active. The 24-hour measurement-pilot review, original
48-hour follow-up and dependence gates, independent sequence freshness, source
replay continuation, full strategy/model readiness workflow, and broader
dashboard work remain open. Details are in [Gate F checkpoint
002](VERITAS_MISSION2_GATE_F_CHECKPOINT_002.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 014](VERITAS_MISSION2_RESEARCH_INVENTORY_014.json).

## Gate A checkpoint addendum — 2026-10-15

The 11:01:53 UTC scheduled scan
`scan-20261015T110153Z-93de340dd5ce` expanded the bounded union to 207
eligible binary markets among 300 unique IDs, with 93 explicit exclusions.
Continuous v4 analysis now contains 15 finalized snapshots / 600 selected
observations / 543 quality-valid pairs across 235 distinct markets. It retains
zero positive top-ask, full-depth, minimum, or fee-qualified states. This
remains intermittent selected coverage and does not give a venue-wide
inclusion estimate or an independent freshness guarantee.

The new [Gate A checkpoint 012](VERITAS_MISSION2_GATE_A_CHECKPOINT_012.md)
records an event-level NegRisk study of a complete nine-outcome Strava IPO
market group. The 18-token CLOB batch returned all Yes and No books in 98 ms,
but source timestamps were up to 350,713 ms old and spanned 349,801 ms, so the
capture fails the freshness gate. The Yes ask sum was $2.213 against a
conditional $1 payout. The No ask sum was $8.595 against the protocol minimum
payout of $8. Both baskets had negative gross edges at 5, 20, and 100 shares,
before fees. No candidate qualifies. The v3 artifact preserves raw responses
and replayable calculations; the earlier v1 and v2 captures also replay.
NegRisk's at-most-one-Yes rule does not guarantee a Yes outcome, so the Yes
basket remains conditional on the event rules.

The next research step is to extend the bounded audit to additional complete
event groups with both Yes and No payoff baskets under explicit settlement
bounds. Continue excluding them from binary-pair qualification until full
event membership, payoff relationships, and current book quality are
independently verified.
Mission 2 remains active; current lineage is in [research inventory
015](VERITAS_MISSION2_RESEARCH_INVENTORY_015.json).

## Gate F checkpoint addendum — 2026-10-15

The 11:10 UTC finalized-source recurrence processed 116 segments / 33.07 MB
and advanced the read-only prefix to 1,188/3,195 segments, with 2,007 pending
and no campaign-window frames. Its sealed summary digest is
`c54728b7aa6b2a68a742f5ba5304b11eddeec498aa5b94664a155e961595b7e0`.

At 11:15 UTC the Director admitted the scan-pinned job for the 11:01 scan, but
the worker rejected it before reading events because the source revision
changed while it was queued. The failure remains recorded at progress 0/1 with
no finding. A no-launch reconciliation at 11:20 UTC recorded the Director's
state as `FAILED` without admitting another job. The Director does not
automatically retry the same scan. The next scheduled observer and Director
runs can qualify a new finalized scan against
the stable committed source. See [Gate F checkpoint
003](VERITAS_MISSION2_GATE_F_CHECKPOINT_003.md) and [operations](VERITAS_MISSION2_OPERATIONS.md).

## Gate A checkpoint addendum — 2026-10-15, 11:31 UTC

The scheduled 11:31 scan
`scan-20261015T113126Z-bf24f3a0706b` found 164 supported same-condition V1
binary pairs in its bounded 300-ID union, with 136 explicit exclusions. The
40-market sample contained 37 rotating markets and three available controls;
35 pairs passed the request/receipt quality gate. Cumulative v4 analysis now
contains 16 snapshots, 640 selected observations, 578 valid pairs, and 256
distinct markets. The legacy timestamp gate accepts 140/640; the paired
increase is 438 observations (+68.44 percentage points). All top, depth,
minimum-size, and fee qualification counts remain zero-positive.

## Gate A checkpoint addendum — 2026-10-15, 12:01 UTC

The scheduled 12:01 scan
`scan-20261015T120127Z-af0847c75aeb` found 200 supported same-condition
binary pairs in its bounded 300-ID union, with 100 explicit exclusions. The
40-market sample contained 37 rotating markets and three available controls;
35 pairs passed the request/receipt quality gate. Cumulative v4 analysis now
contains 17 snapshots, 680 selected observations, 613 quality-valid pairs,
and 284 distinct markets. The legacy timestamp gate accepts 148/680; the
paired increase is 465 observations (+68.38 percentage points). All top,
depth, minimum-size, and fee qualification counts remain zero-positive. See
[Gate A checkpoint 014](VERITAS_MISSION2_GATE_A_CHECKPOINT_014.md) and
[research inventory 017](VERITAS_MISSION2_RESEARCH_INVENTORY_017.json).

## Gate F checkpoint addendum — 2026-10-15, 11:45 UTC

The Director admitted and completed a 16-event Arena qualification for the
11:31 scan using the committed source revision. Finding
`veritas-qualification-v1-0e39c79c039a76cf` reports no positive gross
candidate at any of five gates. The 11:46 no-launch poll verified the finding,
set the Director to `CURRENT`, and admitted no job. The earlier 11:15 failure
for scan 110153 remains preserved and unretried.

The 11:40 finalized-source replay advanced the bounded prefix to 1,316/3,254
cataloged segments, with 1,938 pending and no campaign-window frames. Its
sealed summary digest is
`6f959acc6978fc2e4eb2fbf7e07ee41112a286d0e844daa25d31f43c515fc9cf`.
Mission 2 remains active. The current evidence and scheduled run state are in
[Gate A checkpoint 013](VERITAS_MISSION2_GATE_A_CHECKPOINT_013.md), [Gate F
checkpoint 004](VERITAS_MISSION2_GATE_F_CHECKPOINT_004.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 016](VERITAS_MISSION2_RESEARCH_INVENTORY_016.json).

## Gate F checkpoint addendum — 2026-10-15, 12:15 UTC

The scheduled Director admitted and completed a 17-event Arena qualification
for scan `scan-20261015T120127Z-af0847c75aeb` using committed source revision
`e78a95e2`. Finding `veritas-qualification-v1-4158e04dd04c8f4f` reports no
positive states at any of five gates across 613 quality-valid pairs. A 12:16
no-launch poll verified the finding and source summary, set the Director to
`CURRENT`, and admitted no second job.

The 12:10 finalized-source replay advanced to 1,438/3,313 cataloged segments,
with 1,875 pending / 504,775,332 bytes and no campaign-window frames. Its
sealed summary digest is
`12ae77298aaca26f5b402ac9548983a6b34e4e0d7414d1d1a1b8ac858800bf0d`.
Mission 2 remains active. Details are in [Gate A checkpoint
014](VERITAS_MISSION2_GATE_A_CHECKPOINT_014.md), [Gate F checkpoint
005](VERITAS_MISSION2_GATE_F_CHECKPOINT_005.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 017](VERITAS_MISSION2_RESEARCH_INVENTORY_017.json).

## Gate G checkpoint addendum — Director history

The Veritas research interface now exposes a bounded history of durable
Research Director events, including failures, no-retry decisions, later
completion, and experiment/dataset lineage. The Arena API verifies each
event's filename digest and Director identity, inspects at most 128 event
files per Director, and returns at most eight events. The last read-only
projection check at 12:55 UTC returned eight verified events from the
Director's then-19-file archive and zero invalid artifacts. The 11:15
source-drift failure remains visible next to the 11:45 stable-revision
qualification; this improves auditability but does not alter economics or
readiness.

The Arena API suite passed 16 tests; the frontend suite passed 29. Strict
Mypy, Ruff, typecheck, lint, Prettier, production build, and the Veritas
Playwright workflow passed. The build retains its existing chunk-size
advisory. Details are in [Gate G checkpoint
004](VERITAS_MISSION2_GATE_G_CHECKPOINT_004.md), [engineering](VERITAS_MISSION2_ENGINEERING.md),
and [research inventory 017](VERITAS_MISSION2_RESEARCH_INVENTORY_017.json).

Mission 2 remains active. Current market evidence still contains no qualifying
positive gross candidate. Multi-day independent coverage, source replay
through the frozen campaign window, more verified multi-outcome sets, and a
meaningful strategy comparison remain open.

## Gate A checkpoint addendum — 2026-10-15, 12:31 UTC

The 12:31 scan (`scan-20261015T123114Z-ded26b5ea023`) is the 18th finalized
snapshot. It adds 32 quality-valid pairs and eight empty-ask invalid pairs. The
cumulative panel has 645/720 valid observations across 304 markets; 153/720
pass the earlier reported-age/skew rule, leaving a paired difference of 492
(68.33 percentage points). All five economic qualification counts remain
zero-positive. The Director is scheduled to qualify scan 18 at 12:45 UTC.

A second complete NegRisk group is verified: seven OpenAI IPO market-cap
outcomes with sequential question indices 0–6 match the Polygon adapter's
on-chain question count at block 95,574,561. Their six numeric ranges are
contiguous, exact boundaries resolve upward, and the seventh outcome covers no
IPO by the end of 2026. The Gamma group-filter endpoint returned 20 unrelated
records, so completeness rests on the direct member reads and adapter count.

All 14 Yes/No books returned with depth at 5/20/100 shares, but the oldest
source timestamp was 33.546 seconds old and cross-book skew was 20.962 seconds.
The Yes top ask equals its conditional $1 payout; the No top ask costs $6.035
against the $6 protocol minimum. Every tested full-depth basket is gross
non-positive, before fees. The capture failed the configured timestamp checks and does not
qualify a candidate. No orders or authenticated requests were made. See
[Gate A checkpoint 015](VERITAS_MISSION2_GATE_A_CHECKPOINT_015.md), [inventory
018](VERITAS_MISSION2_RESEARCH_INVENTORY_018.json), and the [replayable study
runner](../scripts/veritas_openai_ipo_basket_study.py).

Mission 2 remains active. The next evidence gate is a fresh complete book
capture with independently supported source freshness, while the scheduled
scan and source-replay workflows continue.

## Gate A checkpoint 016 addendum — stream cross-check and scan 18

A second bounded REST capture still failed freshness at 95.353 seconds maximum
source age and 90.247 seconds of skew. The official Polymarket market WebSocket
returned the complete 14-token book set in 84 ms, but the source data remained
17.781 seconds old at worst with 11.977 seconds of cross-book skew. The stream
schema has no sequence field. REST and WebSocket best bids, best asks, and
last-trade prices matched for all 14 tokens; the full displayed depth changed
for eight tokens on each side. Basket gross and fee-safe edges remain
non-positive at 5, 20, and 100 shares per outcome. The no-position baseline
remains $0 exposure and $0 P&L.

The saved WebSocket frame and its REST reference now replay through the study
runner's `--replay-market-stream` path. Replay verifies the digests, group
token set, source book fields, age/skew gate, and basket arithmetic. This
cross-channel match does not establish sequence continuity, upstream queue
age, or executable fills. The [official stream documentation](https://docs.polymarket.com/market-data/realtime-data)
describes the book event fields used here.

The 12:45 Director admission completed its 18-event Arena qualification with
zero positive states at all five economic gates. The Arena finding is
completed, although the Director manifest still showed the admission as queued
at checkpoint time; the 13:15 UTC scheduled cycle is the next reconciliation
point. Finalized-source replay advanced to 1,548/3,373 segments with 1,825
segments / 487.08 MB pending. Its processed prefix included 4,078
campaign-window frame records and 2,739 quality-valid states, with zero
positive top-ask and full-depth states. Mission 2 remains active. See [Gate A checkpoint
016](VERITAS_MISSION2_GATE_A_CHECKPOINT_016.md), [Gate F checkpoint
006](VERITAS_MISSION2_GATE_F_CHECKPOINT_006.md), and [research inventory
019](VERITAS_MISSION2_RESEARCH_INVENTORY_019.json).

## Gate A checkpoint 017 addendum — scan 19 and source-window progress

The 13:01 scan (`scan-20261015T130114Z-f5e32eaf445c`) is the nineteenth
finalized v4 snapshot. The panel now has 760 selected observations, 681
quality-valid pairs, 79 invalid pairs, and 326 distinct markets. The previous
reported-age/skew gate accepts 160/760; the paired recovery is 521 pairs
(68.55 percentage points). The latest 40-market selection includes 37
rotating markets and all three available frozen controls. All five economic
gates remain zero-positive.

The 13:10 source replay advanced to 1,676/3,432 finalized segments, with
1,756 segments / 470,661,304 bytes pending. Its campaign-window summary counts
15,469 frames, 11,367 touched states, and 11,000 quality-valid states, with
zero positive top-ask and full-depth states. The replay remains partial and
reads finalized segments only.

**Correction to checkpoint 016:** the 12:43 source summary's 4,078
`period_frame_records` were inside the frozen campaign window, with 2,779
touched states and 2,739 quality-valid states. The earlier “no campaign-window
frames” interpretation was incorrect; the positive top-ask and full-depth
counts were correctly zero.

The 13:15 Director admission completed the scan 19 Arena qualification at
13:16:07 UTC. Its finding covers all 19 events and remains zero-positive at all
five gates. The Director manifest still showed `QUEUED` and scan 18 as last
qualified at checkpoint time; the scheduled 13:45:16 UTC cycle is the next
reconciliation point. No manual poll or retry was run. See [Gate A checkpoint
017](VERITAS_MISSION2_GATE_A_CHECKPOINT_017.md), [Gate F checkpoint
007](VERITAS_MISSION2_GATE_F_CHECKPOINT_007.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 020](VERITAS_MISSION2_RESEARCH_INVENTORY_020.json).
## Previous Gate A checkpoint 018 addendum — scan 20 and source replay progress

The 13:31 scan (`scan-20261015T133142Z-dfa1ef9bb7fe`) is the twentieth
finalized v4 snapshot. The panel has 800 selected observations, 714
quality-valid pairs, 86 invalid pairs, and 349 distinct markets. The previous
reported-age/skew gate accepts 167/800; the paired recovery is 547 pairs
(68.38 percentage points). All five economic gates remain zero-positive.

The 13:40 source replay advanced to 1,791/3,490 finalized segments, with
1,699 segments / 450,044,085 bytes pending. Its campaign-window summary counts
29,198 frames, 21,747 touched states, and 21,041 quality-valid states, with
zero positive top-ask and full-depth states. The replay remains partial and
reads finalized segments only.

The 13:45 Director admission completed the scan 20 Arena qualification at
13:46:06 UTC. Its finding covers all 20 events and remains zero-positive at all
five gates. The Director manifest still showed `QUEUED` and scan 19 as last
qualified at checkpoint time; the scheduled 14:15:29 UTC cycle is the next
reconciliation point. No manual poll or retry was run. See [Gate A checkpoint
018](VERITAS_MISSION2_GATE_A_CHECKPOINT_018.md), [Gate F checkpoint
008](VERITAS_MISSION2_GATE_F_CHECKPOINT_008.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 021](VERITAS_MISSION2_RESEARCH_INVENTORY_021.json).

## Gate A checkpoint 019 addendum — scan 21 and source replay progress

The 14:01 scan (`scan-20261015T140150Z-b4ba652d6e9c`) is the 21st finalized
v4 snapshot. The panel has 840 selected observations, 751 quality-valid pairs,
89 invalid pairs, and 367 distinct markets. The previous reported-age/skew
gate accepts 176/840; the paired recovery is 575 pairs (68.45 percentage
points). All five economic gates remain zero-positive.

The 14:10 source replay advanced to 1,919/3,549 finalized segments, with
1,630 segments / 430,839,649 bytes pending. Its campaign-window summary counts
40,459 frames, 30,809 touched states, and 29,749 quality-valid states, with
zero positive top-ask and full-depth states. The replay remains partial and
reads finalized segments only.

The 14:15 Director cycle recorded scan 20 completion and admitted scan 21.
Arena completed all 21 events at 14:16:20 UTC, with zero positive states at all
five gates. The Director manifest last updated at 14:16:04 UTC still showed
`QUEUED` for scan 21 and scan 20 as last qualified; the scheduled
14:45:16 UTC cycle is the next reconciliation point. No manual poll or retry was run.
See [Gate A checkpoint 019](VERITAS_MISSION2_GATE_A_CHECKPOINT_019.md), [Gate F checkpoint
009](VERITAS_MISSION2_GATE_F_CHECKPOINT_009.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 022](VERITAS_MISSION2_RESEARCH_INVENTORY_022.json).

## Gate A checkpoint 020 addendum — scan 22 and source replay progress

The 14:31 scan (`scan-20261015T143154Z-8c0fa0040695`) is the 22nd finalized
v4 snapshot. The panel has 880 selected observations, 789 quality-valid pairs,
91 invalid pairs, and 392 distinct markets. The prior reported-age/skew gate
accepts 183/880; paired recovery is 606 pairs (68.86 percentage points). All
five economic gates remain zero-positive.

The 14:40 source replay advanced to 2,037/3,608 finalized segments, with 1,571
segments / 413,665,338 bytes pending. Its campaign-window summary counts
56,771 frames, 46,152 touched states, and 44,837 quality-valid states, with
zero positive top-ask and full-depth states. The replay remains partial and
reads finalized segments only.

The 14:45 Director cycle reconciled scan 21 and admitted scan 22 at 14:46:10
UTC. Arena completed all 22 events at 14:46:23 UTC with zero positive states at
all five gates. The manifest last updated at 14:46:07 UTC projects `QUEUED`
for scan 22 and retains scan 21's finding; the scheduled 15:15:07 UTC cycle is
the reconciliation point. No manual poll or retry was run. See [Gate A
checkpoint 020](VERITAS_MISSION2_GATE_A_CHECKPOINT_020.md), [Gate F checkpoint
010](VERITAS_MISSION2_GATE_F_CHECKPOINT_010.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 023](VERITAS_MISSION2_RESEARCH_INVENTORY_023.json).

## Gate A checkpoint 021 addendum — scan 23 and source replay progress

The 15:00 scan (`scan-20261015T150026Z-56e1e44d7837`) is the 23rd finalized
v4 snapshot. The panel has 920 selected observations, 825 quality-valid pairs,
95 invalid pairs, and 418 distinct markets. The prior reported-age/skew gate
accepts 189/920; paired recovery is 636 pairs (69.13 percentage points). All
five economic gates remain zero-positive.

The 15:10 source replay advanced to 2,161/3,668 finalized segments, with 1,507
segments / 396,434,833 bytes pending. Its campaign-window summary counts
70,950 frames, 59,343 touched states, and 57,798 quality-valid states, with
zero positive top-ask and full-depth states. The replay remains partial and
reads finalized segments only.

The 15:15 Director cycle reconciled scan 22 and admitted scan 23 at 15:15:35
UTC. Arena completed all 23 events at 15:15:47 UTC with zero positive states
at all five gates. The manifest last updated at 15:15:32 UTC projects `QUEUED`
for scan 23 and retains scan 22's finding; the scheduled 15:45:00 UTC cycle
is the reconciliation point. No manual poll or retry was run. See [Gate A
checkpoint 021](VERITAS_MISSION2_GATE_A_CHECKPOINT_021.md), [Gate F checkpoint
011](VERITAS_MISSION2_GATE_F_CHECKPOINT_011.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 024](VERITAS_MISSION2_RESEARCH_INVENTORY_024.json).

## Latest operating evidence — 2026-10-15 scan 24

The operating discovery system now has 24 scheduled snapshots spanning 05:59–15:30 UTC, with 960 selected observations, 859 quality-valid pairs, and 441 observed market IDs. The latest bounded query union contains 300 IDs, of which 176 were eligible same-condition V1 pairs; the 40 selected markets included three available frozen controls and 37 rotating markets. No positive gross, depth, per-leg-minimum, or fee-sensitive candidate has been observed in this panel. The result remains limited to intermittent selected observations and does not establish venue-wide absence or executability.

The finalized-source replay has processed 2,289/3,727 segments and remains bounded and incomplete; the scheduled Arena and Director qualification completed scan 24 with zero-positive gates. The no-trade baseline remains. See [Gate A checkpoint 022](VERITAS_MISSION2_GATE_A_CHECKPOINT_022.md), [Gate F checkpoint 012](VERITAS_MISSION2_GATE_F_CHECKPOINT_012.md), and [inventory 025](VERITAS_MISSION2_RESEARCH_INVENTORY_025.json). Mission 2 remains active.

## Latest operating evidence — 2026-10-15 scan 25

The bounded observatory has completed 25 scheduled snapshots: 894/1,000 pairs pass the current quality gate across 460 observed market IDs. Scan 25 found three duplicate records across its six public query frames, then selected 40 markets from a deduplicated 297-ID union; 121 markets passed the current same-condition V1 eligibility gate. No positive gross, depth, per-leg-minimum, or fee-sensitive candidate has appeared. This remains intermittent selected evidence, not a venue-wide absence claim.

The finalized-source replay has processed 2,417/3,786 segments and remains bounded and incomplete. The scheduled Arena qualification completed scan 25 with zero-positive gates; the no-trade baseline remains. See [Gate A checkpoint 023](VERITAS_MISSION2_GATE_A_CHECKPOINT_023.md), [Gate F checkpoint 013](VERITAS_MISSION2_GATE_F_CHECKPOINT_013.md), and [inventory 026](VERITAS_MISSION2_RESEARCH_INVENTORY_026.json). Mission 2 remains active.

## Latest operating evidence — 2026-10-15 scan 26

The bounded observatory has completed 26 scheduled snapshots: 928/1,040 pairs pass the current quality gate across 480 observed market IDs. Scan 26 retained 289 unique IDs from 300 query records after removing 11 identical duplicates, with zero identity conflicts; 169 markets passed the current same-condition V1 eligibility gate. No positive gross, depth, per-leg-minimum, or fee-sensitive candidate has appeared. This remains intermittent selected evidence, not a venue-wide absence claim.

The finalized-source replay has processed 2,545/3,844 segments and remains bounded and incomplete. The scheduled Arena qualification completed scan 26 with zero-positive gates; the no-trade baseline remains. See [Gate A checkpoint 024](VERITAS_MISSION2_GATE_A_CHECKPOINT_024.md), [Gate F checkpoint 014](VERITAS_MISSION2_GATE_F_CHECKPOINT_014.md), and [inventory 027](VERITAS_MISSION2_RESEARCH_INVENTORY_027.json). Mission 2 remains active.

## Latest operating evidence — 2026-10-15 scan 27

The observatory has completed 27 scheduled snapshots: 961/1,080 pairs pass the current quality gate across 494 observed market IDs. Scan 27 returned 300 query records and 298 unique IDs after two identical duplicates were removed; 123 markets passed the supported same-condition V1 eligibility gate. No positive gross, depth, per-leg-minimum, or fee-sensitive candidate has appeared. This remains intermittent selected evidence and does not establish venue-wide absence or executability.

The finalized-source replay has processed 2,661/3,903 segments and remains bounded and incomplete. Its campaign-window prefix contains 124,922 frame records, 110,158 touched states, and 107,340 quality-valid states, with zero positive top-ask and full-depth states. The scheduled Arena qualification completed scan 27 with zero-positive gates. The Director manifest awaits its scheduled 17:45:25 UTC reconciliation. The no-trade baseline remains. See [Gate A checkpoint 025](VERITAS_MISSION2_GATE_A_CHECKPOINT_025.md), [Gate F checkpoint 015](VERITAS_MISSION2_GATE_F_CHECKPOINT_015.md), and [inventory 028](VERITAS_MISSION2_RESEARCH_INVENTORY_028.json). Mission 2 remains active.

## Gate D engineering addendum — 2026-10-15

The v2 economic qualification now preserves bounded source pointers for every
quality-valid positive top-ask row, verifies row/counter reconciliation, and
labels pointers as not independently replayed. This closes a provenance gap
without treating a candidate as verified or executable. A read-only comparison
of the 28 finalized snapshots through scan 28 found 996 valid pairs and zero
positive top-ask rows; no result artifact was written by this check. The
scheduled Arena qualification remains responsible for persisting the next
versioned result. See [Gate D checkpoint
001](VERITAS_MISSION2_GATE_D_CHECKPOINT_001.md).

## Gate D checkpoint 002 addendum — independent source replay

The v3 economic comparison now performs bounded source verification and
independent gross/depth arithmetic for every positive gross candidate, with
fail-closed handling and explicit execution-evidence limitations. A read-only
run over the current 29-snapshot panel found 1,034 quality-valid pairs across 536
markets and no positive top-ask, depth, minimum, or fee state. The scheduled
scan-28 finding remains v2; v3 has passed focused backend, frontend, lint,
format, and strict type checks and awaits a later scheduled persisted run.
Mission 2 remains active. See [Gate D checkpoint
002](VERITAS_MISSION2_GATE_D_CHECKPOINT_002.md) and [inventory
029](VERITAS_MISSION2_RESEARCH_INVENTORY_030.json).

## Gate F checkpoint 016 addendum — Director compatibility recovery

The scheduled 18:15 Director cycle rejected the completed scan-28 v2 finding
under the new v3 replay validator and did not admit scan 29. Commit `9379985`
adds version-aware reconciliation: the v2 artifact is accepted as legacy and
unreplayed, while v3 replay checks remain strict. The actual persisted v2
finding passes the read-only validator after the fix. Mission 2 remains active;
the next scheduled Director run is due at 18:45:20 UTC. The v3 panel comparison
remains read-only and has no positive candidates. See [Gate F checkpoint
016](VERITAS_MISSION2_GATE_F_CHECKPOINT_016.md) and [inventory
031](VERITAS_MISSION2_RESEARCH_INVENTORY_031.json).

## Gate A measurement update — scan-29 panel

Across the 29-snapshot, 1,160-observation panel, the prior reported-age/skew
gate accepts 240 observations and the request-to-receipt quality gate accepts
1,034. The paired increase is 794 observations (+68.45 percentage points).
This improves usable measurement yield; it does not establish venue sequence,
batch atomicity, or upstream queue age. The panel remains selected, repeated,
and correlated, with zero positive gross candidates. See [Gate A checkpoint
026](VERITAS_MISSION2_GATE_A_CHECKPOINT_026.md) and [inventory
033](VERITAS_MISSION2_RESEARCH_INVENTORY_033.json).


## Gate A checkpoint 027 addendum — OpenAI IPO REST recapture

A bounded 18:25 UTC REST recapture returned all fourteen books for the pinned
seven-market OpenAI IPO group in 91 ms, but the source timestamps were 31.404
seconds old at worst with 24.598 seconds of cross-market skew. It failed the
5-second age and 250-millisecond skew limits. The complete Yes/No top baskets
were -$0.012 and -$0.021 gross per set; full-depth 5/20/100-share scenarios
were all negative after fees. The sealed result replays, but no candidate
qualified. This is a single observation that fails the configured timestamp
checks. The official book schema exposes a timestamp and state hash, but does not define
timestamp age as proof of stale contents; the published market-book event has
no sequence field. Keep no-trade and prioritize independent freshness or
continuity evidence.
See [Gate A checkpoint 027](VERITAS_MISSION2_GATE_A_CHECKPOINT_027.md) and
[inventory 034](VERITAS_MISSION2_RESEARCH_INVENTORY_034.json).


## Gate A checkpoint 028 addendum — scan 30 and timestamp/hash audit

Scheduled scan 30 brings the panel to 1,200 selected pairs, 1,070 passing the
request/receipt completeness gate, and 558 distinct markets. There are still no
positive gross or fee-qualified states. A read-only audit across 30 snapshots
found that raw book hashes and timestamps advanced together in 248 of 250
sampled stable-control transitions and both remained unchanged in two. This is
consistent with timestamp marking a book-state update, not proof of response
freshness. Keep the five-second age rule as a recency diagnostic and retain the
independent freshness/continuity requirement. See [Gate A checkpoint 028](VERITAS_MISSION2_GATE_A_CHECKPOINT_028.md)
and [research ledger H068](VERITAS_RESEARCH_LEDGER.json).

## Scheduled qualification and source-analysis checkpoint 035

The scheduled 18:45 UTC Research Director cycle reconciled the legacy scan-28
v2 finding and admitted scan 30 under economic qualification v3. The bounded
Arena job completed 30/30 in 1.90 seconds over 30 snapshots (1,200 selected
pairs; 1,070 request/receipt-valid; 558 distinct markets). The persisted finding
reports zero candidates at all five gross, depth, minimum-notional, and fee
gates, with complete zero-candidate replay evidence. No model or execution
policy was promoted. The Director manifest still shows its job as queued while
the local job record is completed; the next scheduled cycle at 19:15:13 UTC is
expected to reconcile that projection. No manual poll or retry was used.
The result is recorded in [research ledger H069](VERITAS_RESEARCH_LEDGER.json).

The scheduled finalized-source replay processed 112 segments (33.29 MB),
bringing the catalog prefix to 3,019/4,081 segments with 1,062 segments and
312.43 MB pending. Its campaign window contains 173,498 frame records and
151,539 quality-valid states, with zero positive top-ask or full-depth states.
The recurrence exited normally, used 13.1 CPU seconds, peaked at 137.5 MiB,
and used no swap. Mission 2 remains active; see [inventory 035](VERITAS_MISSION2_RESEARCH_INVENTORY_035.json).

## Gate C checkpoint 001 — coverage pilot registered

Implemented and preregistered `VERITAS-M2-COVERAGE-PILOT-001`, a 24-hour
measurement-only study capped at 48 scheduled scans. It reuses the observer's
existing bounded public reads and adds no market requests. It measures
quality-valid paired-book yield per selected slot, with descriptive stable
control/rotating comparisons, stratum coverage, missed scans, and immutable
source lineage. At registration, the first scheduled scan after the source revision was
committed had not yet occurred. Its outcome is recorded below and in [Gate C
checkpoint 002](VERITAS_MISSION2_GATE_C_CHECKPOINT_002.md). The fixed window,
no-backfill rule, resource cap, and limitations are in [Gate C checkpoint
001](VERITAS_MISSION2_GATE_C_CHECKPOINT_001.md) and the [versioned pilot
plan](VERITAS_MISSION2_COVERAGE_PILOT_001.json).

## Coverage pilot first scan — 2026-10-15 19:00 UTC

The first post-commit scheduled scan started the fixed 24-hour
`VERITAS-M2-COVERAGE-PILOT-001` window without additional public requests.
Scan `scan-20261015T190055Z-7799523b9d87` selected 40 pairs, of which 32 were
quality-valid (80%) and eight had an empty ask side. The current bounded union
contained 300 IDs and 122 eligible pairs. The small same-scan comparison was
31/37 valid rotating pairs versus 1/3 available stable controls; it is
descriptive and non-causal. There were zero positive states at the top gross,
full-depth, minimum-notional, single-match-fee, and fragmentation-safe-fee
gates. The pilot remains active with one completed scan; its 24-hour stop is
2026-10-16 19:00:55 UTC. See [Gate C checkpoint 002](VERITAS_MISSION2_GATE_C_CHECKPOINT_002.md)
and [research inventory 036](VERITAS_MISSION2_RESEARCH_INVENTORY_036.json).

## Scheduled source and Director cycle — 2026-10-15 19:15 UTC

The 19:10 source-analysis recurrence completed normally at 19:14:38 UTC. It
processed 113 finalized segments / 33,445,857 bytes, advancing the prefix to
3,132/4,140 segments (780,800,513 processed source bytes; 1,008 segments /
298,406,538 bytes pending). The cumulative campaign window now contains
192,072 frame records and 169,253 quality-valid states across 43 markets;
positive top-ask and full-depth counts remain zero. The batch used 13.619 CPU
seconds, peaked at 146.7 MiB, and used no swap.

The scheduled 19:15 Director cycle admitted and completed a scan-31 v3 Arena
qualification, job `job-c2b34af59d624f2ea3081b54`. It processed all 31 scan
events in 1.914 seconds and wrote finding
`veritas-qualification-v1-b3744235647f846e`. The finding covers 1,240 selected
pairs, 1,102 valid pairs, and 575 markets, with zero positives across all five
gross/depth/minimum/fee gates and complete zero-candidate replay evidence. The
job record is complete, but the manifest still reports it queued; the next
scheduled Director cycle is the reconciliation point. No manual poll or retry
was used. See [Gate F checkpoint 017](VERITAS_MISSION2_GATE_F_CHECKPOINT_017.md)
and [research inventory 036](VERITAS_MISSION2_RESEARCH_INVENTORY_036.json).


## Checkpoint addendum — Gate G dashboard and scan 32 (2026-10-15 19:41 UTC)

Mission 2 remains active and this addendum does not change final acceptance
status. The read-only dashboard now exposes the prospective coverage pilot
through a verified API projection and a dedicated panel. Commit `a03a10c`
passed 12 dashboard API tests, one targeted UI test, Python lint/format/type
checks, frontend type/lint/format checks, and a production build. The dashboard
was not deployed to the running host.

The live 24-hour pilot has two scans: 66/80 selected pair slots are
quality-valid (82.5%), with zero missed scan sequences. The scan-32 v4 panel
contains 1,136 valid pairs out of 1,280 selected observations across 598
distinct market IDs. No positive gross, depth, per-leg minimum, or fee-safe
candidate has appeared; the maximum top edge remains -$0.001/share. The latest
persisted Arena qualification is scan 31; scan 32 awaits its scheduled
Director cycle.

Finalized Reality source analysis remains partial at 3,132/4,140 segments,
with 1,008 pending. Its campaign window has 169,253 quality-valid states
across 43 markets and zero positive top-ask or full-depth states. The recorder,
frozen shadow, and Veritas timers were active at capture; the scheduled source
analysis was running. Freshness/continuity evidence, source catch-up, Gate E
experimentation, broader dashboard coverage, and full regression verification
remain open. See [Gate G checkpoint
005](VERITAS_MISSION2_GATE_G_CHECKPOINT_005.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [inventory 037](VERITAS_MISSION2_RESEARCH_INVENTORY_037.json).

## Checkpoint addendum — 2026-10-16 03:58 UTC

Mission 2 remains active. The offline A1 replay verified 48 saved snapshots / 31,353,007 compressed bytes. The bounded union contains 5,903 Gamma IDs, 2,135 eligible IDs, and 849 selected IDs. Current replay yields 1,660 quality-valid pairs from 1,920 selected observations, with zero positive top-gross pairs. The first-scan stored-versus-current-replay mismatch remains disclosed. See [Gate A checkpoint 045](VERITAS_MISSION2_GATE_A_CHECKPOINT_045.md) and [coverage artifact 003](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_003.json).

The scheduled scan-48 Arena qualification completed 48/48 events. Its top-ask, full-depth, minimum, single-match-fee, and fragmentation-safe-fee positive counts are all zero; candidate evidence and replay are complete and empty. The independent raw opportunity audit remains at scan 47, so the Arena result is not described as an extension of that audit. See [Gate F checkpoint 030](VERITAS_MISSION2_GATE_F_CHECKPOINT_030.md).

The fixed 24-hour pilot remains at 17/48 scans with 557/680 valid slots across 408 IDs and one skipped sequence following a scan-45 code-hash mismatch. The latest source analyzer prefix is 5,125/5,147 segments with 342,943 valid states across 81 markets. The separate gap-detail index is 2,289/5,165 replayable segments with 373 campaign-window resynchronization events and 2,876 segments pending. Both remain partial where indicated.

The source-only dashboard now validates coverage artifact 003 against ledger receipt H105. The focused dashboard API and universe-coverage tests passed 26 tests; Ruff, formatting, strict Mypy for the changed API module, and git diff checks passed. The dashboard was not deployed. The pilot, Reality collector, shadow campaign, and frozen campaign remained untouched. Mission acceptance criteria remain open.


## Mission 2 checkpoint addendum — scan 49, Gate E experiment, and current source prefixes (2026-10-16T04:12:21Z)

Mission 2 remains active. The 48-scan Arena run provides an end-to-end economic qualification comparison against the unchanged top-ask gross-sign baseline. Its implemented depth/minimum/fee-aware research rule leaves the zero-candidate decision unchanged: 1,660 of 1,920 pairs are quality-valid; the baseline and all four downstream economic gates contain zero positives; candidate evidence and independent empty replay are complete. This is an economic qualification experiment, not strategy P&L or fills. See [Gate E checkpoint 001](VERITAS_MISSION2_GATE_E_CHECKPOINT_001.md), [Gate F checkpoint 030](VERITAS_MISSION2_GATE_F_CHECKPOINT_030.md), and [ledger H106](VERITAS_RESEARCH_LEDGER.json).

The observer separately finalized scan 49, scan-20261016T040030Z-56b893816f32, at 04:00:30 UTC. It selected 40 markets from a 298-ID bounded union (127 eligible, 171 excluded), with 31 quality-valid pairs and zero gross, depth, minimum, or fee-positive states. Scan 49 is outside coverage artifact 003 and awaits the scheduled Director qualification; it is not added to the completed 48-scan qualification or independent raw audit.

The scheduled gap-detail analysis advanced to 2417/5196 catalog segments. Its partial prefix contains 435 campaign-window book-resynchronization gaps across 15 affected market IDs, with 2777 segments / 762,500,134 bytes pending. It read no active segment and does not establish causal censor attribution. The latest finalized-source analyzer summary remains from 2026-10-16T03:44:33+00:00: 5125/5147 segments and 342,943 quality-valid states across 81 markets, with zero positive top-ask or full-depth states.

The fixed measurement pilot remains at 18/48 scans and 588/720 valid slots across 434 selected IDs. Rotating selections are 567/666 valid and frozen controls 21/54; the comparison remains descriptive and nonrandomized. The scan-49 Director reconciliation, completed pilot analysis, independent scan-49 replay, full Gate H regression and preservation audit remain open. Current inventory: [062](VERITAS_MISSION2_RESEARCH_INVENTORY_062.json). No service, collector, pilot, or frozen campaign was changed.


## Mission 2 checkpoint addendum — scan 49 audit, qualification, and source catch-up (2026-10-16T04:18:16Z)

The independent raw-source audit now covers 49 scans / 1,960 selected pair observations and 32,003,727 compressed bytes. It reproduces all 1,691 v4 quality decisions and top edges with zero mismatches. The conservative reported-timestamp sensitivity accepts 364/1,691 states; 1,327 have a reported age above five seconds. This sensitivity does not prove sequence freshness, atomicity, persistence, or executable quotes. All top, depth, minimum, and fee gates remain zero. See [Gate B checkpoint 003](VERITAS_MISSION2_GATE_B_CHECKPOINT_003.md) and audit artifact 003.

The 04:15 UTC Director cycle admitted scan 49. Arena completed all 49/49 events with zero positives and complete empty candidate evidence/replay. The child job record is complete; the Director manifest still projects QUEUED, with scan 48 recorded as last qualified. Leave the next scheduled 04:45 UTC cycle to reconcile scan 49. See [Gate F checkpoint 031](VERITAS_MISSION2_GATE_F_CHECKPOINT_031.md).

The finalized-source analyzer is now current at 5,206/5,206 segments with no pending bytes. It reports 351,524 quality-valid states across 87 markets and zero positive top-ask/full-depth states. The separate gap index remains partial at 2,417/5,194 replayable segments, with 435 campaign-window resynchronization events across 15 market IDs and 2,777 segments / 762,500,134 bytes pending. See [Gate C checkpoint 014](VERITAS_MISSION2_GATE_C_CHECKPOINT_014.md).

The fixed measurement pilot remains at 18/48 scans with 588/720 valid slots; its rotating/control comparison is descriptive and nonrandomized. Mission 2 remains active. Full Gate H regression and preservation checks, final pilot analysis, and the next Director reconciliation remain open.


## Mission 2 checkpoint addendum — scan 49 audit, qualification, and source catch-up (2026-10-16T04:18:16Z)

The independent raw-source audit now covers 49 scans / 1,960 selected pair observations and 32,003,727 compressed bytes. It reproduces all 1,691 v4 quality decisions and top edges with zero mismatches. The conservative reported-timestamp sensitivity accepts 364/1,691 states; 1,327 have a reported age above five seconds. This sensitivity does not prove sequence freshness, atomicity, persistence, or executable quotes. All top, depth, minimum, and fee gates remain zero. See [Gate B checkpoint 003](VERITAS_MISSION2_GATE_B_CHECKPOINT_003.md) and audit artifact 003.

The 04:15 UTC Director cycle admitted scan 49. Arena completed all 49/49 events with zero positives and complete empty candidate evidence/replay. The child job record is complete; the Director manifest still projects QUEUED, with scan 48 recorded as last qualified. Leave the next scheduled 04:45 UTC cycle to reconcile scan 49. See [Gate F checkpoint 031](VERITAS_MISSION2_GATE_F_CHECKPOINT_031.md).

The finalized-source analyzer is now current at 5,206/5,206 segments with no pending bytes. It reports 351,524 quality-valid states across 87 markets and zero positive top-ask/full-depth states. The separate gap index remains partial at 2,417/5,194 replayable segments, with 435 campaign-window resynchronization events across 15 market IDs and 2,777 segments / 762,500,134 bytes pending. See [Gate C checkpoint 014](VERITAS_MISSION2_GATE_C_CHECKPOINT_014.md).

The fixed measurement pilot remains at 18/48 scans with 588/720 valid slots; its rotating/control comparison is descriptive and nonrandomized. Mission 2 remains active. Full Gate H regression and preservation checks, final pilot analysis, and the next Director reconciliation remain open.


## Mission 2 checkpoint addendum — Gate A scan-51 coverage replay (2026-10-16T05:27:54Z)

The A1 replay verified 51 saved snapshots / 33,318,338 compressed bytes and matches the stored eligibility count on 51/51 scans. The six-frame bounded union contains 6,118 distinct Gamma market IDs; 2,168 were eligible at least once and 903 were selected. Current replay found 1,755 valid pairs from 2,040 observations, with zero positive top-gross pairs. One first-scan discrepancy remains explicit (5 captured-valid versus 32 current-replay-valid). Repeated sampled top-of-book content changed in 421/885 comparable transitions, an intermittent activity proxy only. See [Gate A checkpoint 047](VERITAS_MISSION2_GATE_A_CHECKPOINT_047.md), [artifact 005](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_005.json), and [ledger H115](VERITAS_RESEARCH_LEDGER.json). The bounded panel does not establish venue-wide opportunity prevalence or executable fills.

At 05:27 UTC, the Reality recorder, shadow, Midas/Reality APIs and web services were active; the shadow retained one historical restart and its lag was not refreshed. The archive unit remained failed after its 04:33:35 timeout. The completed scan-51 Arena child awaited its scheduled Director reconciliation at 05:45:02 UTC. The 20/48 measurement pilot and partial gap-detail prefix remain open. No job was manually triggered, retried, or restarted.
