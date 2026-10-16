# Veritas research backlog

The Mission 2 queue below reflects expected information value, possible
economic impact, current evidence, and compute cost. Work remains on
`project/veritas`; the frozen Reality campaign is a protected reference. The
earlier Mission 1 handoff backlog is retained below for provenance.

## Current Mission 2 queue (updated 2026-10-16T05:22:16Z)

| Rank | Question | Evidence today | Next experiment | Promotion rule |
| --- | --- | --- | --- | --- |
| 1 | Does the fixed coverage pilot improve usable market coverage? | The immutable v1 pilot is 20/48 scans: 652/800 valid slots across 492 IDs. One scheduled sequence was missed after the scan-45 code-hash mismatch. Rotating selections yield 629/742 valid slots; frozen controls yield 23/58. The comparison is descriptive and nonrandomized. | Preserve the pilot through its 19:00:55 UTC stop, then report strata, control availability, missed scans, storage and compute cost. | Do not treat repeated observations as independent or infer venue-wide availability. |
| 2 | Which source gaps coincide with frozen follow-up censoring? | The primary analyzer covers 5,324/5,324 segments, with 361,068 valid states across 91 markets and zero positives. The gap index is partial at 3,019/5,344 replayable segments; it records 735 campaign-window gap events, with 2,323 segments / 633,802,218 bytes pending. H109 attribution 002 verified 339 gap-censored outcomes among 40,075 scanned; 100 exact references are indexed, 79 await indexing, and 63 same-market links are temporal only. | Continue bounded gap-detail batches and refresh attribution only when the prefix materially advances; preserve frozen labels. | Keep beyond-prefix outcomes unresolved; a temporal link is not causal attribution. |
| 3 | Does independent raw replay agree through the latest saved scan, and what does the reported timestamp track? | Independent audit 005 covers 51 scans / 2,040 observations, reproducing all 1,755 v4 validity/top-edge decisions with zero mismatches. Strict reported-age sensitivity admits 379; all economic gates remain zero. Timestamp audit 001 also covers 51 snapshots / 4,080 book observations: all 2,197 content-changing endpoint transitions have an advancing reported timestamp, while 77 unchanged-content transitions have an advanced or unchanged timestamp. | Preserve the bounded audits. Seek documented venue timestamp semantics or independent sequence evidence before changing freshness gates. | Require source identity and independent arithmetic. Endpoint timestamp/content association is not sequence freshness, continuous update history, or quote persistence. |
| 4 | Which eligible segments remain under-covered? | Coverage artifact 004 verifies 50 scans: 6,059 Gamma IDs, 2,166 eligible at least once, 887 selected IDs, 1,727/2,000 current-replay-valid pairs. The latest saved scan 51 has a bounded union of 299 IDs / 191 eligible; it is not a venue denominator. | Use the fixed pilot's final stratum/control results to decide a versioned successor; retain the 40-market cap until evidence supports a change. | Preserve conditional selection probabilities and exclusions; label snapshots as intermittent. |
| 5 | Can the Research Director qualify and reconcile each new scan durably? | The 05:15 UTC cycle reconciled scan 50 and admitted scan 51. Its Arena child completed 51/51 events; the manifest records scan 50 as last qualified and still projects scan 51's completed child as `QUEUED`. | Let the scheduled 05:45 UTC cycle reconcile scan 51; then exercise idempotent recovery in isolated fixtures. | Require pinned revisions, idempotent admission, complete replay, bounded resources, and read-only behavior. |
| 6 | Does the improved economic qualification change the baseline decision? | The completed 48–51-scan v4 runs compare the unchanged top-ask baseline with depth/minimum/fee-aware qualification. Scan 51 has 1,755 quality-valid states and zero positives at all five gates, with complete empty candidate evidence/replay. This qualifies the discovery pipeline, not strategy P&L. | Keep no-trade; compare execution/strategy policies only when a genuine gross candidate and valid target exist. | Do not interpret qualification as performance or fills. |
| 7 | Is the research dashboard current and fully verified? | Coverage projection now resolves the newest existing ledger-receipted artifact and the direct source projection reads artifact 006/H116 through scan 52. The current API change has not had automated test or browser verification and remains undeployed. | After the scheduled scan-52 reconciliation, run the focused API/browser checks for the updated projection, then complete remaining research-readiness views and isolated Gate H verification. | Every displayed source value must resolve to a validated artifact and show sample limits. |

## Archived checkpoint notes

At 00:12 UTC, the live observer was at scan 41 (`scan-20261016T000215Z-e6ff8b97e045`): 33/40 quality-valid pairs and zero positive gross or economic states. Across 41 saved snapshots the current-v4 replay had 1,438/1,640 valid pairs. Scan 40's Arena qualification completed all 40 events with zero candidates at all five gates, and the scheduled Director reconciliation was due at 00:15:04 UTC. The A1 report was a separately versioned 40-scan audit with 5,319 distinct bounded IDs, 2,077 eligible at least once, and 1,405/1,600 current-v4 valid pairs; it did not include scan 41 or estimate the venue denominator. Its dashboard projection was pinned to the H084 ledger digest and remained source-only. The fixed pilot had 11/48 scans, 368/440 valid slots across 282 IDs, and no skipped sequences. See [Gate A checkpoint 038](VERITAS_MISSION2_GATE_A_CHECKPOINT_038.md), [Gate F checkpoint 024](VERITAS_MISSION2_GATE_F_CHECKPOINT_024.md), [Gate G checkpoint 011](VERITAS_MISSION2_GATE_G_CHECKPOINT_011.md), and [inventory 047](VERITAS_MISSION2_RESEARCH_INVENTORY_047.json).

At 23:34 UTC, scan 40 had completed with 30/40 quality-valid pairs from 291
unique discovery IDs (77 V1-eligible) and zero positive top-gross pairs. The
coverage pilot has 10/48 scans, 335/400 valid slots over 271 selected IDs, and
no skipped scan sequences. The scan-39 Arena qualification completed 39/39
events with zero candidates; the Director manifest still awaits its scheduled
reconciliation, and scan 40 remains unqualified. A scan-keyed durable-child
recovery path now has isolated tests for pointer adoption and no-retry behavior
when admission evidence is absent. See [Gate A checkpoint
037](VERITAS_MISSION2_GATE_A_CHECKPOINT_037.md), [Gate F checkpoint
023](VERITAS_MISSION2_GATE_F_CHECKPOINT_023.md), and [recovery artifact
001](VERITAS_MISSION2_DIRECTOR_RECOVERY_001.json).

The latest censoring and source-attribution work is documented in [Gate C checkpoint 004](VERITAS_MISSION2_GATE_C_CHECKPOINT_004.md) and [checkpoint 005](VERITAS_MISSION2_GATE_C_CHECKPOINT_005.md). The control-availability projection is in [Gate G checkpoint 010](VERITAS_MISSION2_GATE_G_CHECKPOINT_010.md) and is not deployed to the running host. Current discovery evidence is in [Gate A checkpoint 036](VERITAS_MISSION2_GATE_A_CHECKPOINT_036.md), including the [frame-marginal artifact](VERITAS_MISSION2_DISCOVERY_FRAME_MARGINAL_001.json), the direct-control lookup in [research ledger H081](VERITAS_RESEARCH_LEDGER.json), and the frame-budget result in H082. The latest inventory is [044](VERITAS_MISSION2_RESEARCH_INVENTORY_044.json). The official [Gamma OpenAPI schema](https://gamma-api.polymarket.com/openapi.json) supports the bounded ID lookup used in that diagnostic. The official [Real-Time Data](https://docs.polymarket.com/market-data/realtime-data) and [Prices and Order Books](https://docs.polymarket.com/market-data/prices-order-books) pages remain relevant to freshness; their documented schemas do not provide an independent sequence guarantee.


## Archived Mission 2 queue (checkpoint 036; retained for provenance)

| Rank | Question | Evidence today | Next experiment | Promotion rule |
| --- | --- | --- | --- | --- |
| 1 | What freshness assurance does request-to-receipt timing provide when book timestamp semantics are unclear? | Across 31 scans, 256/1,240 pairs pass the five-second reported-update-age rule and 1,102/1,240 pass the request/receipt quality rule (+846; +68.23 percentage points). The timestamp/hash audit still found 248/250 sampled stable-control transitions advancing together and two unchanged; continuity, batch atomicity, and upstream queue age remain unverified. | Keep paired classification on every finalized scan. Seek documented sequence or equivalent independent continuity evidence before changing the gate. | Do not treat receipt duration as venue-time freshness. Require source identity, complete asset coverage, bounded receipt timing, and an independent freshness signal before candidate promotion. |
| 2 | Does a wider repeated market panel change the gross-opportunity result? | The 31-snapshot panel spans 575 distinct selected market IDs and 1,102 request/receipt-valid pairs. It has no positive top-ask, full-depth, minimum, or fee state; the maximum top-pair edge remains -0.001/share. | Continue the 24-hour coverage pilot and review its fixed-window result; preserve the original 48-hour coverage and dependence gates for confirmation. | Treat repeated samples as correlated. Do not treat the bounded six-frame union as a venue census. |
| 3 | Which eligible segments remain under-covered by discovery? | Scan 31 returned 300 unique IDs; 122 passed same-condition V1 eligibility and 178 were excluded (128 with unverified augmented NegRisk semantics, 50 unsupported outcome relationships). The 40-market scan spans category, liquidity, expiry, and spread strata; only three of eight frozen controls were available. | Compare eligibility and inclusion by category, liquidity, lifecycle, and payoff structure across the pilot. Add frames only after reviewing request, byte, and selection-probability bounds. | Verify payout identity and counterexamples before including any additional structure; do not infer venue-wide probabilities from the query offsets. |
| 4 | Does economic qualification find and replay a genuine candidate? | The persisted scan-31 v3 run completed all 31 events with 1,102 valid pairs across 575 markets and zero positives at all five gross/depth/minimum/fee gates. Candidate evidence is complete with zero rows. The Arena job completed, while the Director manifest still projects `QUEUED` pending its next scheduled reconciliation. | Let the next scheduled Director cycle reconcile scan 31. Keep no-trade and do not compare execution policies or models without an eligible gross candidate. | Require same-condition identity, immutable-source replay, full requested depth, per-leg minimums, fees, and independent freshness before strategy work. |
| 5 | Can broader complete-outcome structures produce fresh positive net economics? | The pinned Strava nine-outcome basket is structure-verified but failed age/skew quality and its YES basket gross edge was -1.213 USDC/set. The OpenAI IPO REST and WebSocket captures, including an 18:25 recapture, failed the configured timestamp age/skew checks (timestamp semantics remain unresolved); its latest Yes/No top gross edges were -$0.012/-$0.021 per set and all 5/20/100-share fee-safe edges were negative. No candidate qualified. | Wait for a public source with sequence or equivalent independent freshness evidence; do not spend more cycles on REST-only recaptures while timestamp semantics remain unresolved. Keep no-trade. | Do not promote an age/skew gate failure without timestamp semantics or independent freshness evidence; require complete payoff identity and per-leg net economics. |
| 6 | Can prediction or strategy policies improve an economically useful decision? | No genuine positive gross state or suitable forward outcome labels exist. Model and strategy readiness remain not ready. | Keep the no-trade control. Reassess only after candidate discovery and label/coverage gates are met. | No training or tournament on repeated price states without valid chronological targets and independent evaluation. |
| 7 | Does the rotating discovery cohort improve usable observation coverage under the current request budget? | Pilot scan 1 of up to 48 selected 40 pairs: 32 valid (80%), including 31/37 rotating and 1/3 available stable controls. Eight invalid pairs had an empty ask side. One scan is descriptive only. | Let the scheduled observer continue through the fixed 24-hour window; review source lineage, missed scans, per-role yield, and stratum coverage at its stop. | Treat repeated scans as dependent and the bounded Gamma union as selected; make no causal or venue-wide claim. |

## Archived Mission 2 queue (checkpoint 028; retained for provenance)



| Rank | Question | Evidence today | Next experiment | Promotion rule |
| --- | --- | --- | --- | --- |
| 1 | Does request-to-receipt freshness improve usable pair measurement without accepting stale or queued books? | The v4 panel now covers 28 snapshots: 230/1,120 pass the legacy age/skew gate and 996/1,120 pass the request/receipt gate (+766, +68.39 pp). The complete 14-token WebSocket cross-check agrees with REST top prices but has no sequence field and fails source age/skew. Batch atomicity and upstream queue age remain unverified. | Keep paired classification on every new scan and seek a source with documented sequence or equivalent freshness guarantees. Keep reported age/skew diagnostics. | Do not call request-to-receipt a venue-time guarantee. Require source identity, a complete asset set, bounded receipt time, and independent freshness evidence before candidate promotion. |
| 2 | Does a wider repeated market panel change the gross-opportunity result? | Twenty-eight snapshots cover 693 minutes, 513 distinct IDs, 996 valid pairs, and zero positive top/depth/minimum/fee candidates. The latest rotating-frame union has 190 eligible pairs; sampled state changes are not true update rates. | Keep the 30-minute pilot running, then review market/time dependence after at least 24 hours. Keep the specific follow-up design's 48-hour coverage and dependence gates intact. | Never treat repeated snapshots as independent events or the six-frame union as a venue census. |
| 3 | Which segments remain under-covered by the current discovery frames? | The v2 query union uses six capped frames and rotating half-hour offsets; scan 28 returned 300 unique IDs, 190 supported pairs, and 110 explicit exclusions. The selected 40-market cohort spans the current liquidity, expiry, spread, and category strata, conditional on that union. | Compare eligible market coverage by protocol, category, liquidity, and lifecycle. Add query frames only after observing rate use, response bounds, and resource/storage cost. | New payoff structures require verified settlement/payoff identity and adversarial counterexamples; offsets do not establish venue-wide inclusion probabilities. |
| 4 | Does economic qualification find any candidate as the pilot accumulates data? | Scan 28 has 35/40 quality-valid pairs and no positive gross state. The 17:15 Director admission completed scan 27 in Arena with zero positives across all five gates; the Director manifest awaits its 17:45 UTC scheduled reconciliation. The earlier source-drift failure remains preserved without retry. See [Gate F checkpoint 015](VERITAS_MISSION2_GATE_F_CHECKPOINT_015.md). | Keep qualifying each new finalized scan under a stable revision. The economic-comparison v2 now emits bounded hash-linked pointers for each positive top-ask row; its next scheduled job should persist that schema. | Any candidate must pass same-condition semantics, independent replay, freshness, complete depth, both minimums, and fees before hypothetical strategy research. |
| 5 | Does incremental snapshot analysis remain complete and idempotent under interruption or backlog? | Twenty-eight v4 events have verified hashes, zero pending work, per-market coverage, and legacy/current gate outcomes. A read-only v2 qualification comparison reconciled positive-row counts against market rows and found no candidate pointers; the previous 15-event Arena job remains failed at 0/1 after source revision drift. | Keep event/state lineage checks in each release and freeze the source revision before the next timed qualification. | No source record rewrite, duplicate event application, unbounded snapshot read, or silent event repair. |
| 6 | Is there evidence for a strategy or predictor tournament? | There are no positive gross candidates or realized/public fill labels in the new panel. The comparison tests qualification, not PnL. | Keep no-trade. Reassess only after quality-valid positive gross evidence and suitable chronological outcome labels exist. | No model training or strategy promotion from synthetic cases or a repeated selected holdout. |
| 7 | Can the Research Director coordinate recurring Veritas work without duplicating the collector? | The Director runs at :15 and :45 UTC. Its 17:15 cycle admitted scan 27 and Arena completed 27/27; the manifest still projects `QUEUED` and scan 26 as latest qualified. The 17:45 cycle is the scheduled reconciliation point and should evaluate scan 28 under the committed v2 code. The prior source-drift failure remains preserved and was not retried. See [Gate F checkpoint 015](VERITAS_MISSION2_GATE_F_CHECKPOINT_015.md) and [Gate G checkpoint 004](VERITAS_MISSION2_GATE_G_CHECKPOINT_004.md). | Let the active observer publish new scans and check each scheduled Director cycle. Keep source code stable between admission and worker verification. | Each cycle must remain finite, idempotent, interruptible, resource-bounded, and unable to modify campaign inputs. Failed scans must not be retried without a new scan or explicit operator action. |
| 8 | Does incremental Reality source replay remain bounded and resumable while it catches up? | The 17:10 UTC recurrence processed 116 finalized segments / 33.22 MB; cumulative progress is 2,661/3,903 segments with 1,242 pending (344.46 MB) through ordinal 340,035. The processed prefix contains 124,922 campaign-window frames and 107,340 quality-valid states, with zero positive top-ask/full-depth states. See [Gate F checkpoint 015](VERITAS_MISSION2_GATE_F_CHECKPOINT_015.md). | Keep the offset timer active; inspect source hashes, processed/pending counts, resource use, and campaign-window coverage as it advances. | Never open the active `.open` source, change Reality records, silently continue after prefix/code drift, or report bootstrap counts as economic evidence. |
| 9 | Can independent coverage evidence separate unavailable future observations from venue inactivity and feed gaps? | The v1.3 audit records 10,184 `future_observation_unavailable` labels across valid starts, but the frozen worker does not distinguish quiet venues, feed selection, and every missing-source cause. It also records explicit stale, timeout, gap, reconstruction, and ordering labels. | Compare the frozen journal with an independent sequence or feed-coverage source, if one is available, while leaving campaign labels unchanged. | Do not recode historical outcomes without source-grounded evidence; keep unresolved mixtures explicit. |
| 10 | Can verified multi-outcome groups add economically useful discovery beyond binary pairs? | Two complete groups are verified: the nine-outcome Strava set and a seven-market OpenAI IPO set whose sequential Gamma question indices match the Polygon adapter count at block 95,574,561. A second REST capture and a market WebSocket capture returned all 14 books, but both failed age/skew. Best bid/ask and last-trade prices matched across channels for 14/14 tokens; the stream exposed no sequence field and full depth changed. Both groups show non-positive gross basket edges. See [Gate A checkpoint 016](VERITAS_MISSION2_GATE_A_CHECKPOINT_016.md). | Use the replayable runner for bounded recaptures and compare source timestamps with independent sequence or equivalent source evidence; keep the no-position baseline. | Never treat bounded query counts as a venue census. Require complete books, disjoint outcome coverage, protocol/event payoff evidence, fresh source timestamps, and positive quality-valid full-depth net economics before candidate promotion. |

The operating study protocol is
[`VERITAS_MISSION2_MEASUREMENT_PILOT_001.md`](VERITAS_MISSION2_MEASUREMENT_PILOT_001.md).
The v4 paired gate comparison is specified in
[`VERITAS_MISSION2_MEASUREMENT_COMPARISON_002.md`](VERITAS_MISSION2_MEASUREMENT_COMPARISON_002.md).
Its early evidence is summarized in
[`Mission 2 Gate A checkpoint 001`](VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md)
and [`checkpoint 002`](VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md).

## Earlier Mission 1 handoff backlog (retained)

| Rank | Question | Evidence today | Next experiment | Promotion rule |
| --- | --- | --- | --- | --- |
| 1 | Which separate activity-aware sampling and future horizons improve synchronized public follow-ups while retaining the current quality gate? | The v7 replay found 1,895/2,945 decisions over the 5-second freshness gate. The refined protocol uses the 1,408-slot baseline's 1.92% all-scheduled one-second yield as its primary planning rate. Its 50% relative-lift sensitivity fits the 14-day slot count only through a simple design effect of about 2.47; crossed market/time dependence is unmeasured. | Validate the two-day subscription-coverage gate and estimate/bound market and time dependence from finalized multi-day evidence. Run the exact assignment simulation in [follow-up design draft 002](VERITAS_GATE_A_FOLLOWUP_DESIGN_002.md) before freezing any separate campaign. | The draft is not campaign-ready. Never alter Reality's horizons, sampling, or labels. A higher public-measurement yield does not establish fills or profitability. |
| 2 | Does a longer and broader observed panel contain a positive gross complementary opportunity? | The 004 snapshot covers about 4 h 16 m, 44,981 quality-valid states, and 16 market IDs. All positive top, quantity-depth, full-depth pre-fee, and per-leg minimum-notional counts remain zero; maximum top edge is -0.001. See [Gate A checkpoint 012](VERITAS_GATE_A_CHECKPOINT_012.md). | Wait for a materially larger finalized interval or a new approved observation cohort before another replay. Stratify by market family, activity, lifetime, and liquidity if the prefix reveals a candidate. | A candidate must pass source quality, same-condition payoff, per-leg USDC minimums, and full-depth costs before fees or execution assumptions are considered. |
| 3 | Does the v2 economic model correctly bound a real, positive gross candidate across size and cost assumptions? | Official fee fields include rate and exponent; taker buy fees are collected in shares. The v2 engine covers exponent, fee rounding sensitivities, share deductions, and USDC minimums. The synthetic 100-share full-depth example has +1.42 USDC worst-resolution P&L under single-match rounding, about 50.20 USDC of adverse unmatched-leg loss, and negative P&L under the fragmentation-safe fee bound. | Independently recalculate any observed candidate if one appears; evaluate per-leg schedules, depth, partial positions, capital lockup, settlement, and break-even completion assumptions. | Do not promote synthetic thresholds or capacity as empirical performance. Unknown fills stay unknown. |
| 4 | Does ML improve an economically useful decision over heuristics? | Reality reports no eligible learned model; prior depth heuristics beat learned alternatives and held-out risk-tree gains did not survive. The current raw funnel has no gross candidate. | Reassess label count and target support after the source-quality and prospective-horizon work. Train only if real chronological labels support a useful target. | Prediction gains must improve a predeclared hypothetical decision metric on independent data. |
| 5 | Can the Research Director schedule bounded Veritas work without duplicating existing controls? | Arena already provides typed supervised jobs, finite schedules, durable progress, and local failure alerts. The native `research_followup.py` Director is a synthetic latency study; Veritas source replay has no Arena job type and remains a bounded command. See [Gate E scheduling review 001](VERITAS_GATE_E_SCHEDULING_REVIEW_001.md). | Reuse existing Arena control for eligible simulator studies. Defer a source-reading adapter until multi-day coverage or another repeated analysis has enough information value to justify it. | Any adapter must pin source/code, bound finalized-segment reads and artifacts, handle idempotent admission/interruption, and keep protected campaign controls out of the job. |
| 6 | What Veritas evidence should the native dashboard expose? | Implemented in [dashboard checkpoint 001](VERITAS_DASHBOARD_CHECKPOINT_001.md): native navigation, bounded overview, selected raw-funnel and follow-up measures, synthetic execution sensitivity, hypotheses, and versioned artifact links. | Keep the summary aligned with versioned source artifacts; add metrics only after their evidence contract and interpretation are explicit. | Keep observed, derived, assumed, simulated, and unknown values visibly separate. The API remains read-only, allowlisted, and size-bounded. |
| 7 | Can a selected strategy reduce incomplete-leg loss under realistic public evidence? | Prometheus and Reality document unmatched-position risk, but no current positive gross candidate supports a meaningful strategy tournament. | Preserve the no-trade control; revisit matched risk-policy and recovery studies after a quality-valid gross candidate appears. | Never assume a hedge, recovery order, or displayed depth would fill. |

## Current controls

- No order, wallet, credential, deposit, or live-execution integration is in
  scope.
- Do not restart, pause, or take ownership of Reality service writers.
- Keep confirmation data untouched and report all unsuccessful experiments.
- The first baseline and original v1 economics are recorded in the
  [research ledger](VERITAS_RESEARCH_LEDGER.json) and
  [Gate A checkpoint 001](VERITAS_GATE_A_CHECKPOINT_001.md). Source replay
  evidence is in checkpoints 002–007; the per-outcome gap audit and event-age
  analysis are in [Gate A checkpoint 009](VERITAS_GATE_A_CHECKPOINT_009.md)
  and [010](VERITAS_GATE_A_CHECKPOINT_010.md); the updated raw-funnel snapshot
  is [Gate A checkpoint 012](VERITAS_GATE_A_CHECKPOINT_012.md). Gate G and H
  verification are recorded in [Gate G checkpoint 001](VERITAS_GATE_G_CHECKPOINT_001.md)
  and [Gate H checkpoint 001](VERITAS_GATE_H_CHECKPOINT_001.md). The corrected
  v2 economics are in
  [Gate A checkpoint 008](VERITAS_GATE_A_CHECKPOINT_008.md).
- The current decision is no strategy promotion and no new Reality follow-up
  campaign; the bounded snapshot coverage pilot is documented separately
  above. Read the [final report](VERITAS_FINAL_REPORT.md), [economic
  verdict](VERITAS_ECONOMIC_VERDICT.md), and [Gate J closeout](VERITAS_GATE_J_CHECKPOINT_001.md)
  before starting another study.
- The bounded controlled capacity sensitivity is
  [VERITAS_GATE_B_CAPACITY_001.json](VERITAS_GATE_B_CAPACITY_001.json); it uses
  synthetic inputs and does not promote a strategy.

## Mission 2 current evidence — scan 24

The bounded observatory has completed 24 scheduled snapshots: 859/960 pairs pass quality checks across 441 markets, with zero positive gross or qualified states. Scan 24 covered 40 markets drawn from a 300-ID response union; 176 markets in that union passed the current same-condition V1 eligibility gate. Keep the read-only observation and qualification pipeline running while the finalized source prefix catches up; do not train or compare execution policies without a qualified gross candidate and suitable outcome labels. Current checkpoint: [Gate A 022](VERITAS_MISSION2_GATE_A_CHECKPOINT_022.md), [Gate F 012](VERITAS_MISSION2_GATE_F_CHECKPOINT_012.md), [inventory 025](VERITAS_MISSION2_RESEARCH_INVENTORY_025.json).

## Mission 2 current evidence — scan 25

The 25-snapshot observatory panel has 894/1,000 quality-valid pairs across 460 markets and zero positive gross or qualified states. Scan 25 recorded three duplicate records across discovery frames, zero identity conflicts, and 121 eligible same-condition V1 pairs in the deduplicated query union. Keep the read-only observation and qualification pipeline running while the finalized source prefix catches up; model and execution-policy experiments remain unready without a candidate and suitable outcome labels. Current checkpoint: [Gate A 023](VERITAS_MISSION2_GATE_A_CHECKPOINT_023.md), [Gate F 013](VERITAS_MISSION2_GATE_F_CHECKPOINT_013.md), [inventory 026](VERITAS_MISSION2_RESEARCH_INVENTORY_026.json).

## Mission 2 current evidence — scan 26

The 26-snapshot observatory panel has 928/1,040 quality-valid pairs across 480 markets and zero positive gross or qualified states. Scan 26 recorded 11 identical duplicates across query frames, zero identity conflicts, and 169 eligible same-condition V1 pairs in the deduplicated query union. Keep the read-only observation and qualification pipeline running while the finalized source prefix catches up; model and execution-policy experiments remain unready without a candidate and suitable outcome labels. Current checkpoint: [Gate A 024](VERITAS_MISSION2_GATE_A_CHECKPOINT_024.md), [Gate F 014](VERITAS_MISSION2_GATE_F_CHECKPOINT_014.md), [inventory 027](VERITAS_MISSION2_RESEARCH_INVENTORY_027.json).

## Mission 2 current evidence — scan 28 and Gate D provenance

The 28-snapshot observatory panel has 996/1,120 quality-valid pairs across 513 markets and zero positive gross or qualified states in the read-only v2 comparison. Scan 28 recorded 300 unique discovery IDs, 190 eligible same-condition V1 pairs, 110 explicit exclusions, and 35/40 quality-valid books; its scheduled Arena qualification is due at the 17:45 UTC Director cycle. The 17:15 qualification completed scan 27 with zero positive states at all five gates. The v2 economic comparison now preserves bounded snapshot/event pointers for every positive top-ask row and rejects count/row mismatches. Twenty-one relevant tests, Ruff, formatting, and strict Mypy passed; a synthetic positive fixture exercised the pointer path. No real positive candidate has appeared, and candidate pointers still require independent replay before any hypothetical strategy comparison. Keep bounded collection running while the finalized source prefix catches up. See [Gate D checkpoint 001](VERITAS_MISSION2_GATE_D_CHECKPOINT_001.md), [Gate A checkpoint 025](VERITAS_MISSION2_GATE_A_CHECKPOINT_025.md), [Gate F checkpoint 015](VERITAS_MISSION2_GATE_F_CHECKPOINT_015.md), and [inventory 028](VERITAS_MISSION2_RESEARCH_INVENTORY_028.json).

## Mission 2 current evidence — scan 28 and candidate source replay

The v3 read-only qualification over 29 finalized snapshots contains 1,034
quality-valid pairs across 536 markets and no positive gross or economic gate.
Its maximum observed top-pair gross edge is -0.001 per share. Candidate source
replay is implemented and verified on synthetic positive and tampered-source
fixtures; the scan-28 persisted finding remains v2. Keep the no-trade policy,
allow the scheduled collector and source-prefix replay to continue, and let a
later scheduled Director run persist v3 before considering further strategy
work. Outcome labels, independent venue sequence, order arrival, and fills
remain unavailable. Current checkpoint: [Gate D 002](VERITAS_MISSION2_GATE_D_CHECKPOINT_002.md),
[inventory 030](VERITAS_MISSION2_RESEARCH_INVENTORY_030.json).

## Mission 2 current evidence — scan 29 and Director compatibility

The 29-scan v3 comparison remains negative: 1,034 quality-valid pairs across
536 markets, maximum top-pair edge -0.001/share, and zero positive states at
every gross or economic gate. The 18:15 Director cycle marked its manifest
`UNVERIFIED` because it could not reconcile the prior scan-28 v2 finding.
Commit `9379985` fixes legacy v2 handling; the actual finding now passes a
read-only validation. Wait for the next scheduled cycle to reconcile the old
finding and qualify the newest scan. The isolated browser suite still has a
Reality test-fixture limitation; the targeted Veritas browser workflow passes.
Current evidence: [Gate F 016](VERITAS_MISSION2_GATE_F_CHECKPOINT_016.md),
[inventory 031](VERITAS_MISSION2_RESEARCH_INVENTORY_031.json).

## Mission 2 continuation — scan 35 / checkpoint 039

Scan 35 is durably qualified with no positive gross candidates and a complete
empty candidate replay. The Director manifest reconciliation is due at 21:45
UTC. The five-scan coverage pilot remains active and ends at its fixed stop,
2026-10-16 19:00:55 UTC.

The scheduled finalized-source analyzer now covers 3,641/4,377 segments, with
204,052 quality-valid states across 57 markets and 736 segments pending. The
new gap-detail analyzer has only reached ordinal 13,113 / 2026-10-14 10:15 UTC,
before the frozen campaign began. Its 466 all-period gap records are
independently reconciled to finalized source, but campaign-time gap detail is
still pending. Preserve its code and pinned cursor while it catches up.

Next work: let the 21:45 Director cycle reconcile scan 35; keep the scheduled
observer, source replay, and gap-detail batches running; check whether source
analysis reaches its current catalog before increasing bounds; then continue
Gate C censoring diagnosis with the latest detailed gap prefix and frozen
label-feasibility evidence. Do not spend model-training time while every
observed gross gate remains zero and candidate-relevant labels remain
unavailable. Do not alter the coverage pilot's hashed code or fixed protocol.
Current evidence is in [Gate A checkpoint 032](VERITAS_MISSION2_GATE_A_CHECKPOINT_032.md),
[Gate F checkpoint 021](VERITAS_MISSION2_GATE_F_CHECKPOINT_021.md), and
[inventory 039](VERITAS_MISSION2_RESEARCH_INVENTORY_039.json).

## Mission 2 continuation — scan 47 / Gate G checkpoint 012

The latest pinned 47-snapshot qualification and independent source audit still
show zero positive gross or economic candidates: 1,880 selected observations,
1,628 quality-valid, with no v4/v2 validity or top-edge mismatches. The A1
market-universe artifact remains the 46-scan report and should not be described
as scan-47 coverage. The campaign gap-censor artifact scanned 40,075 censored
follow-ups and found 339 gap-labeled rows. Its partial gap index has processed
1,919/5,079 segments, leaving 3,158 segments / 862,240,407 bytes pending; 45
same-market preceding-gap outcome links are temporal candidates, not causal
proof.

Gate G now exposes that frozen attribution through a digest- and
campaign-validated overview summary and an artifact inspection route. The UI
keeps the incomplete prefix, recorder receiver-time basis, source checks, and
causality limitation visible. The focused API, browser, typing, lint,
formatting, and production-build checks passed. The code is source-only and
not deployed. No collector, campaign, or research job was touched; the latest
runtime evidence remains in inventory 058 and should be refreshed at a later
safe checkpoint. See [Gate B checkpoint 002](VERITAS_MISSION2_GATE_B_CHECKPOINT_002.md),
[Gate C checkpoint 011](VERITAS_MISSION2_GATE_C_CHECKPOINT_011.md), [Gate G
checkpoint 012](VERITAS_MISSION2_GATE_G_CHECKPOINT_012.md), and [inventory
059](VERITAS_MISSION2_RESEARCH_INVENTORY_059.json).

Next: commit this coherent Gate G checkpoint, then continue Gate G review for
remaining discovery/readiness views and preserve the scheduled research
pipeline. At the next operational checkpoint, inspect only persisted outputs
from completed scheduled runs and refresh host/service telemetry read-only; do
not manually trigger jobs or alter the fixed coverage pilot.

## Mission 2 continuation — scheduled gap-detail batch 03:20 UTC

The completed 03:20 gap-detail run advanced the finalized-only prefix from
1,919 to 2,037 processed segments and from 194 to 251 campaign-window gap
events. The current prefix has 3,069 replayable segments / 836,081,401 bytes
pending; the 251 indexed events affect 11 markets, with no missing reported
assets or unmapped affected assets. The primary source analyzer remains at
4,997/5,089 segments, 331,241 quality-valid states over 77 markets, and zero
positive gross states. These summaries passed their read-only digest and
progress checks after the one-shot services exited successfully.

The scheduled observer had just started at 03:31:44 UTC during the limited
systemd check; its scan output was left untouched. The Director's next cycle is
scheduled for 03:45:19 UTC. The attribution artifact 001 remains explicitly
pinned to the 03:10, 1,919-segment gap prefix. If refreshed later, write a new
version and preserve 001. Current operational evidence is in [Gate C
checkpoint 012](VERITAS_MISSION2_GATE_C_CHECKPOINT_012.md), [operations
checkpoint 060](VERITAS_MISSION2_OPERATIONS.md), and [inventory
060](VERITAS_MISSION2_RESEARCH_INVENTORY_060.json).

Next: let scheduled collection and analysis continue. At the next safe review,
read only sealed outputs after their services exit, refresh the Director
projection after its scheduled cycle, and decide whether an attribution
artifact 002 adds enough new classified outcomes to justify a bounded rerun.
Do not read the observer's in-progress scan or manually trigger a job.

## Mission 2 continuation — 03:35 gap-detail batch and Gate H browser check

The 03:35 finalized-only gap-detail batch completed successfully. Its sealed
prefix is 2,161/5,137 cataloged segments, with 2,974 segments / 810,593,712
bytes pending and 311 campaign-window book-resynchronization events across 11
markets. The primary source analyzer's last completed summary remains
4,997/5,089 segments and 331,241 quality-valid states across 77 markets, with
zero positive gross states. The current gap attribution artifact 001 is still
pinned to the earlier 1,919-segment prefix; preserve it if a new bounded
attribution version is produced.

The isolated Veritas Playwright workflow now verifies the attribution card,
link, and artifact endpoint, including the 339-row count and explicit
non-causality flag. It passed 1 test; its temporary API and Vite servers were
closed and their ports were free afterward. This is a local source-checkout
workflow, not a hosted deployment check. Gate H remains active. See [Gate C
checkpoint 013](VERITAS_MISSION2_GATE_C_CHECKPOINT_013.md), [Gate H checkpoint
001](VERITAS_MISSION2_GATE_H_CHECKPOINT_001.md), and [inventory
061](VERITAS_MISSION2_RESEARCH_INVENTORY_061.json).

Next: allow source analysis and the 03:45 Director cycle to finish, then read
only their sealed outputs and reconcile the scan-47 projection after its
scheduled cycle. Continue the gap-detail prefix under its existing bounds;
do not manually launch an overlapping analyzer or inspect an in-progress
observer output.


## Mission 2 continuation — scan-51 coverage and scheduled reconciliation

The A1 replay is verified through scan 51. Keep the 5-versus-32 first-scan capture/replay valid-pair discrepancy visible while using the 1,755/2,040 current-replay valid states for the explicitly versioned replay. The bounded six-frame discovery union still yields zero positive top-gross pairs; do not infer a venue-wide zero-opportunity rate.

Next actions:

1. Let the scheduled 05:45 UTC Director cycle reconcile the completed scan-51 child; do not poll, retry, or manually admit it.
2. Preserve the existing bounded observation schedule and compare later scans against the same source-pinned coverage and independent economic panels.
3. Review whether a predeclared future query-frame design should retain the tagged near-expiry and low-liquidity frames; frame-removal values overlap and do not justify changing the active campaign.
4. Keep the dashboard projection and browser verification scoped to the artifact version actually exposed; artifact 005 has not been checked against the current API projection.
5. Continue the fixed pilot, finalized-source catch-up, and separate gap-detail prefix under their existing bounds; do not use the active recording segment.

See [Gate A checkpoint 047](VERITAS_MISSION2_GATE_A_CHECKPOINT_047.md), [coverage artifact 005](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_005.json), and [inventory 069](VERITAS_MISSION2_RESEARCH_INVENTORY_069.json).


## Mission 2 continuation — scan-52 evidence and manifest reconciliation

The A1 universe replay and independent raw-source audit now cover scan 52. Preserve the first-scan capture/replay quality discrepancy. The Arena child is complete with zero economic candidates, but the Director manifest has not yet reconciled it.

1. Allow the scheduled 06:15:10 UTC Director cycle to reconcile scan 52; do not poll or retry the child.
2. Keep the Arena research package unchanged until that manifest reconciliation completes, because queued jobs pin their source revision. The dashboard-only `apps/api` change is outside the Arena source hash.
3. The source dashboard now resolves the newest existing hash-receipted coverage artifact; an in-process check reads artifact 006 through scan 52. Focused API tests and browser verification remain open, and the change has not been deployed.
4. Continue the fixed pilot and scheduled source/gap-detail batches; use only finalized source segments.
5. Do not change the frozen campaign, active scan cadence, or no-trade threshold in response to this selected panel.

See [Gate A checkpoint 048](VERITAS_MISSION2_GATE_A_CHECKPOINT_048.md), [Gate B checkpoint 007](VERITAS_MISSION2_GATE_B_CHECKPOINT_007.md), and [inventory 070](VERITAS_MISSION2_RESEARCH_INVENTORY_070.json).


## Mission 2 continuation — Gate G coverage projection

The source API now selects the newest existing A1 coverage artifact with a matching ledger receipt instead of pinning artifact 004/H110. A direct in-process projection reports scan 52 / 1,788 valid pairs / zero positive top-gross pairs and the expected artifact hash. Automated tests, browser verification, and deployment remain open. The change is in `apps/api`, outside the Arena source hash; the scan-52 child source revision is unchanged. Continue to leave the Director manifest for the scheduled 06:15:10 UTC reconciliation. See [Gate G checkpoint 015](VERITAS_MISSION2_GATE_G_CHECKPOINT_015.md).


## Mission 2 continuation — scan 53 coverage and source audit

Coverage artifact 007 and independent audit 007 now cover 53 saved scans / 2,120 selected pair observations. Current replay finds 1,818 quality-valid states and zero positive top-gross candidates; the independent evaluator matches v4 validity and edge decisions with no mismatches. Keep the first-scan 5-versus-32 capture/replay discrepancy visible. All depth, minimum, and fee gates remain zero. The scan-53 Arena child is complete, but the Director manifest is still `QUEUED` pending its 06:45 UTC scheduled reconciliation.

1. Let the scheduled 06:45 UTC Director cycle reconcile scan 53; do not poll, retry, or manually admit the completed child.
2. Keep the Arena research package pinned until that reconciliation completes; the API-only projection change remains outside the Arena source hash.
3. Continue the fixed coverage pilot and finalized-source/gap-detail schedules under their existing bounds. Read only sealed summaries and never open the active recording segment.
4. Keep the no-trade policy and frozen campaign unchanged. Do not start model training or a strategy tournament without an eligible gross candidate and candidate-relevant labels.
5. Complete the source API's focused/browser verification at a suitable point; the direct in-process projection of artifact 007 is verified, but tests, browser checks, and deployment remain open.

See [Gate A checkpoint 049](VERITAS_MISSION2_GATE_A_CHECKPOINT_049.md), [Gate B checkpoint 008](VERITAS_MISSION2_GATE_B_CHECKPOINT_008.md), [Gate G checkpoint 016](VERITAS_MISSION2_GATE_G_CHECKPOINT_016.md), and [inventory 071](VERITAS_MISSION2_RESEARCH_INVENTORY_071.json).


## Mission 2 continuation — A1 counter-semantics review

The first-scan 5-versus-32 A1 flag compares unlike saved counters: snapshot `counts.valid_quality_pairs=5` versus v4 event `valid_quality_pairs=32`; that same event reports `legacy_freshness_valid_pairs=5` and 27 reported-age exceedances. The independent evaluator matches the v4 value and the retained source hashes verify. This points to a counter-semantics mismatch rather than missing payloads, while the snapshot producer semantics still need documentation.

After the scheduled 06:45 UTC Director reconciliation, update the A1 analyzer to report snapshot-stored and v4 event counters separately, then write a versioned successor artifact. Preserve coverage artifact 007 and the original records. Keep the Arena research source pinned until the completed scan-53 child is reconciled.

See [Gate A counter-semantics note 001](VERITAS_MISSION2_GATE_A_COUNTER_SEMANTICS_NOTE_001.md) and [inventory 072](VERITAS_MISSION2_RESEARCH_INVENTORY_072.json).
