# Project Veritas Mission 2 — Current Engineering Report

**Status:** Mission 2 remains active. Discovery, independent binary-pair arithmetic, bounded public observation, continuous finalized-snapshot analysis, candidate qualification, paired measurement comparison, market/time censoring analysis, and the read-only dashboard are implemented. The recurring scan-pinned Veritas Research Director now consumes the independently maintained finalized-source summary alongside public-scan qualification. Strategy/model experiments, broader dashboard scope, and longer independent validation remain open.

**Date:** 2026-10-15
**Branch:** `project/veritas`
**Checkpoint base commit:** `40f04c8`

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

The latest scan is `scan-20261015T090047Z-6f98ffeaecab`; its 12-snapshot qualification run still has zero positive states. The Reality source replay remains bounded and read-only at 786/2,959 replayable finalized segments, with 2,173 pending and no campaign-window frames in the processed prefix. The live public observer and source-replay timers remain active. See [operations](VERITAS_MISSION2_OPERATIONS.md) and [Gate A checkpoint 010](VERITAS_MISSION2_GATE_A_CHECKPOINT_010.md).

## Earlier checkpoint verification

- Veritas backend regression suite: 88 passed; one Starlette/httpx deprecation warning.
- Ruff and strict Mypy on changed Python sources: passed.
- Frontend unit tests: 29 passed; typecheck, lint, formatting check, and production build passed. The existing Vite large-chunk advisory remains.
- Earlier Veritas Playwright workflow passed. A broader browser set had six passes and one unrelated Reality exact-heading assertion failure; no Reality source was changed.
- `git diff --check` and documentation/inventory validation are run before this checkpoint commit.

## Scientific limits and remaining work

Request-to-receipt duration does not prove venue sequence or batch atomicity. Snapshots and campaign decisions are selected, intermittent, and correlated. The v4 reclassification is retrospective on ten saved scans, with two later scheduled scans captured prospectively. The censoring audit is a bounded read-only SQL snapshot; it did not replay the complete event hash chain or run a full SQLite integrity scan. `future_observation_unavailable` does not establish whether a venue was quiet or the feed failed to expose a quote. There is no positive gross candidate, so strategy PnL testing, model training, or promotion is unsupported. The original follow-up study's readiness gates remain intact.

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
