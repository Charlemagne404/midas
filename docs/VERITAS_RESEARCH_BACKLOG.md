# Veritas research backlog

The Mission 2 queue below reflects expected information value, possible
economic impact, current evidence, and compute cost. Work remains on
`project/veritas`; the frozen Reality campaign is a protected reference. The
earlier Mission 1 handoff backlog is retained below for provenance.

## Current Mission 2 queue (updated 2026-10-16T11:31:12Z)

The protected shadow worker remains lagged. Both frozen-source analysis jobs
now load Reality modules from the campaign's pinned snapshot through a durable
per-user import overlay; bounded source and gap runs have succeeded without
changing the campaign or resetting either cursor. Confirm the next scheduled
runs before treating this as durable operation. The separate decode-reuse
change remains in the Veritas worktree, passed focused tests, and has no
measured CPU effect; profile it only in an isolated successor and do not
deploy it to the frozen worker.

Scan 64 completed at 11:30:53 UTC. The cumulative panel now has 2,560 selected
pair observations, 2,150 quality-valid pairs, and zero top-gross candidates;
the independent opportunity audit remains through scan 62. The source replay
last completed at 11:26:34 with 6,055 segments and zero pending at that run;
gap detail last completed at 11:28:49 with 5,885/6,064 segments and 177
pending. See [Gate D checkpoint 003](VERITAS_MISSION2_GATE_D_CHECKPOINT_003.md).

| Rank | Question | Evidence today | Next experiment | Promotion rule |
| --- | --- | --- | --- | --- |
| 1 | Has any credible gross or economically qualified opportunity appeared? | Independent audit 013 covers 62 saved snapshots through `scan-20261016T103050Z-bc8cf9bc331e`: 2,480 selected observations, 2,095 quality-valid pairs, zero v4/v3 validity or top-edge mismatches, and zero positive top, depth, minimum, single-match-fee, or fragmentation-safe-fee states. The independent Decimal cross-check agrees on 2,609 fee evaluations. Newer scan 64 brings the stored panel to 2,560 observations / 2,150 valid pairs, still with zero top-gross candidates; it is not yet independently audited. See [Gate B checkpoint 014](VERITAS_MISSION2_GATE_B_CHECKPOINT_014.md). | Preserve no-trade. Extend the immutable independent replay through scan 64; do not count repeated states as independent opportunities. Define candidate-specific replay only after a positive gross observation survives source-quality review. | Require an observed gross candidate, depth and per-leg minimums, current fee-model checks, independent replay, and evidence of executable conditions; qualification is not P&L. |
| 2 | Does the current fee model correctly account for both taker legs and entry capital? | Fee model v3 follows current published collateral-denominated fees and charges both purchased legs at entry. Independent source replay found zero formula mismatches. The 100-share synthetic full-depth case is +1.624 USDC under single-match rounding and -0.370 USDC under the fragmentation-safe bound; the assumed unrecovered unmatched-leg loss is 52.200 USDC. These are controlled sensitivities only. Previous v2 share-deduction outputs are superseded. | Keep the corrected synthetic artifact as the dashboard source after a safe code rollout. Recompute any future observed candidate with its reported schedule and supported venue semantics. | Never treat synthetic P&L or sensitivity rates as observed profitability, fills, or execution likelihood. |
| 3 | Does the fixed coverage pilot improve usable market coverage? | Pilot 001 remains 28/48 scans: 912/1,120 valid slots across 657 selected markets, with one skipped sequence; its latest summary flags current-source code drift. Pilot 002 is 3/48 scans: 75/120 valid pairs across 98 IDs; 17 pass the strict reported-age sensitivity, with zero verified atomicity or sequence pairs. | Let pilot 002 proceed under its own bound. Re-audit inclusion support after the new cohort completes; do not edit either protocol while active. | Do not treat repeated observations as independent or infer causal or venue-wide improvement. |
| 4 | What do reported timestamps and intermittent coverage establish about freshness? | Audit 013 covers 62 scans / 2,480 observations and reproduces v4 validity and top-edge decisions with zero mismatches. Strict reported-age sensitivity admits 438 states; 1,657 pairs exceed five seconds; none exceeds the 250 ms timestamp-skew threshold. Pilot 002 separately records its first scan's age bands and no verified batch atomicity or sequence counts. | Preserve quality and freshness gates. Seek documented venue sequence semantics or an independent continuity signal before changing them. | Request-to-receipt and returned timestamps do not prove venue sequence freshness, batch atomicity, quote persistence, order arrival, or fills. |
| 5 | Which source gaps coincide with frozen follow-up censoring? | The 11:28:49 UTC gap summary covers 5,885/6,064 segments / 1,509,016,852 processed bytes, with 177 segments / 44,891,642 bytes pending and 2,142 campaign-window events (2,138 resynchronizations, 4 connection failures). Attribution 003 remains partial and noncausal. | Continue scheduled bounded gap-detail batches; refresh attribution when the sealed prefix materially advances and preserve frozen labels. | Keep beyond-prefix outcomes unresolved; temporal association is not causal attribution. |
| 6 | Can the Research Director qualify and reconcile each new scan durably? | The 11:15 UTC cycle admitted scan 63; its Arena child completed all 63 events with no positive gross candidate. Scan 64 is the latest public snapshot and is awaiting the next Director reconciliation. | Preserve the Arena source revision through the scheduled 11:45 UTC reconciliation; then extend the independent audit through scan 64. | Require pinned revisions, idempotent admission, complete replay, bounded resources, and read-only behavior. |
| 7 | Is the research dashboard current and fully verified? | The API validates v1's stored event chain and labels current-source pin drift; pilot 002 is exposed with its first scan and verified snapshot/analysis lineage. API tests (33), pilot/observer tests (12), component test (1), and TypeScript build pass. The hosted main checkout is not deployed from this branch. | Keep displayed values tied to receipted artifacts and sample limits; run the isolated browser workflow after the next material UI change and use a safe deployment path when authorized. | Every displayed source value must resolve to a validated artifact and show sample limits. |
| 8 | Do machine learning or strategy comparisons have candidate-relevant evidence? | No gross candidate or public outcome labels support training or a strategy tournament. The available economic runs qualify a read-only discovery pipeline, not expected returns or fills. | Do not train or compare execution policies yet; revisit when eligible gross candidates and suitable labels exist. | Do not infer improvement from synthetic inputs, hypothetical execution, or infrastructure completion. |

### Fee-model correction (2026-10-16)

The prior v2 P&L evaluator translated buy fees into outcome-share deductions and
charged the winning leg at resolution. Current public fee guidance specifies
USDC-denominated taker fees, while current CTF Exchange V2 settlement code
charges buy fees from collateral. Model v3 subtracts both leg fees at entry,
keeps P&L resolution-independent, and includes the conservative fee reserve in
entry capital. The [current-fee source audit
011](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_011.json) independently
reproduces 2,523 fee calculations with zero disagreements. The corrected
[synthetic break-even report
002](VERITAS_GATE_B_EXECUTION_BREAK_EVEN_002.json) supersedes v2 synthetic
figures for current economics; observed gross-candidate counts are unchanged.
The project has not reloaded running services, so the dashboard update remains
pending a safe code rollout.

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
| 6 | Can the Research Director coordinate recurring Veritas work without duplicating the collector? | The Director runs at :15 and :45 UTC. Its 17:15 cycle admitted scan 27 and Arena completed 27/27; the manifest still projects `QUEUED` and scan 26 as latest qualified. The 17:45 cycle is the scheduled reconciliation point and should evaluate scan 28 under the committed v2 code. The prior source-drift failure remains preserved and was not retried. See [Gate F checkpoint 015](VERITAS_MISSION2_GATE_F_CHECKPOINT_015.md) and [Gate G checkpoint 004](VERITAS_MISSION2_GATE_G_CHECKPOINT_004.md). | Let the active observer publish new scans and check each scheduled Director cycle. Keep source code stable between admission and worker verification. | Each cycle must remain finite, idempotent, interruptible, resource-bounded, and unable to modify campaign inputs. Failed scans must not be retried without a new scan or explicit operator action. |
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
| 3 | Does the v2 economic model correctly bound a real, positive gross candidate across size and cost assumptions? | Historical v2 results used an outcome-share deduction for taker buys. That treatment is superseded for current economics by v3 collateral costs charged at entry on both legs. The synthetic 100-share v3 case is recorded in break-even report 002. | Independently recalculate any observed candidate if one appears; evaluate per-leg schedules, depth, partial positions, capital lockup, settlement, and break-even completion assumptions. | Do not promote synthetic thresholds or capacity as empirical performance. Unknown fills stay unknown. |
| 4 | Does ML improve an economically useful decision over heuristics? | Reality reports no eligible learned model; prior depth heuristics beat learned alternatives and held-out risk-tree gains did not survive. The current raw funnel has no gross candidate. | Reassess label count and target support after the source-quality and prospective-horizon work. Train only if real chronological labels support a useful target. | Prediction gains must improve a predeclared hypothetical decision metric on independent data. |
| 6 | Can the Research Director schedule bounded Veritas work without duplicating existing controls? | Arena already provides typed supervised jobs, finite schedules, durable progress, and local failure alerts. The native `research_followup.py` Director is a synthetic latency study; Veritas source replay has no Arena job type and remains a bounded command. See [Gate E scheduling review 001](VERITAS_GATE_E_SCHEDULING_REVIEW_001.md). | Reuse existing Arena control for eligible simulator studies. Defer a source-reading adapter until multi-day coverage or another repeated analysis has enough information value to justify it. | Any adapter must pin source/code, bound finalized-segment reads and artifacts, handle idempotent admission/interruption, and keep protected campaign controls out of the job. |
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

Scan 53 has now been reconciled. Update the A1 analyzer to report snapshot-stored and v4 event counters separately, then write a versioned successor artifact after scan 54's scheduled 07:15 UTC Director reconciliation. Preserve artifacts 007 and 008 and the original records. Keep the Arena research source pinned until the completed scan-54 child is reconciled.

See [Gate A counter-semantics note 001](VERITAS_MISSION2_GATE_A_COUNTER_SEMANTICS_NOTE_001.md) and [inventory 072](VERITAS_MISSION2_RESEARCH_INVENTORY_072.json).


## Mission 2 continuation — scan 54 coverage and qualification

Coverage artifact 008 and independent audit 008 now cover 54 snapshots / 2,160 selected pair observations. Current replay finds 1,853 quality-valid pairs; the independent evaluator matches v4 validity and edge decisions with no mismatches. All gross, depth, minimum, and fee gates remain zero. The first-scan 5-versus-32 A1 flag is clarified as a comparison of snapshot and v4/legacy-freshness counters; keep note 001 linked and preserve artifact 008.

The 06:45 UTC Director cycle reconciled scan 53 and admitted scan 54. Its Arena child is complete with zero positives, but the Director manifest remains `QUEUED` until 07:15 UTC.

1. Let the scheduled 07:15 UTC Director cycle reconcile scan 54; do not poll, retry, or manually admit the completed child.
2. Keep the Arena research package pinned until that reconciliation completes.
3. Continue the fixed coverage pilot and finalized-source/gap-detail schedules under their existing bounds; read only sealed summaries and never open the active recording segment.
4. Preserve the no-trade policy and frozen campaign. Do not start model training or a strategy tournament without an eligible gross candidate and candidate-relevant labels.
5. Automated API tests, browser checks, and deployment remain open; the in-process projection of artifact 008 is verified.

See [Gate A checkpoint 050](VERITAS_MISSION2_GATE_A_CHECKPOINT_050.md), [Gate B checkpoint 009](VERITAS_MISSION2_GATE_B_CHECKPOINT_009.md), [Gate F checkpoint 033](VERITAS_MISSION2_GATE_F_CHECKPOINT_033.md), [Gate G checkpoint 017](VERITAS_MISSION2_GATE_G_CHECKPOINT_017.md), and [inventory 073](VERITAS_MISSION2_RESEARCH_INVENTORY_073.json).


## Mission 2 continuation — scan-58 independent coverage and opportunity replay

The saved public snapshot panel now has 58 scans / 2,320 selected pair observations. Versioned A1 replay 010 verifies snapshot, Gamma, and stored eligibility lineage for all 58 scans: 6,565 bounded-union IDs, 2,204 eligible at least once, and 998 selected market/condition IDs. Independent audit 010 reproduces all 1,981 valid states and top-edge decisions with zero mismatches; no positive top, depth, minimum, or fee-qualified state appears. These are selected intermittent observations, not a venue census or execution result.

The scheduled observer is at scan 58 and the fixed measurement pilot is at 27/48 scans, 878/1,080 valid slots, 630 distinct selected market IDs, and one skipped sequence. Keep audit 002 immutable; it covers 25 pilot scans and is stale. The latest finalized-source pass remains current at 5,677 segments / 386,158 valid states / 101 markets. Gap detail completed at 08:36:30 UTC and advanced to 4,485/5,724 replayable segments, with 1,239 / 302,415,732 bytes pending and 1,442 campaign-window gaps indexed.

Next actions:

1. Allow the scheduled 08:45:23 UTC Director cycle to reconcile scan 57; do not manually poll, retry, or admit a child.
2. Keep the Arena research package pinned through that reconciliation. Scan 58 is not yet admitted.
3. Continue the fixed pilot to its existing end or cap, then run a new versioned inclusion-support audit against the completed prefix.
4. Continue source/gap-detail analysis only on finalized segments; investigate the failed archive service and shadow lag without changing the frozen campaign.
5. Complete the isolated Mission 2 regression, preservation, scheduler-recovery, and dashboard checks. Do not train a model without candidate-relevant labels.

See [Gate A checkpoint 053](VERITAS_MISSION2_GATE_A_CHECKPOINT_053.md), [Gate B checkpoint 011](VERITAS_MISSION2_GATE_B_CHECKPOINT_011.md), [inventory 076](VERITAS_MISSION2_RESEARCH_INVENTORY_076.json), and ledgers H128–H129.

## Mission 2 continuation — v3 fee isolation and source-analysis recovery

The v3 collateral-fee engine is isolated in `economic_feasibility_v3.py`; the
historical `economics.py` depth helper was restored to the exact fingerprint
required by the finalized-source cursor. One 09:10 UTC source-analysis run
failed on that code mismatch without advancing or rewriting state. The bounded
recovery run then processed 81 segments and completed at 09:23:41 UTC: 5,815
processed of 5,815 cataloged segments, 394,313 quality-valid states across 102
markets, and no pending source. The pinned campaign digest still matches. See
[Gate B checkpoint 012](VERITAS_MISSION2_GATE_B_CHECKPOINT_012.md),
[Gate F checkpoint 035](VERITAS_MISSION2_GATE_F_CHECKPOINT_035.md), and ledger
H132. The next scheduled source-analysis and Director cycles remain to be
verified; the hosted API and dashboard are still on the main checkout.

## Mission 2 continuation — scan 60 and independent audit 012

The scheduled 09:30 UTC observer cycle completed with zero restarts and saved
scan `scan-20261016T093021Z-b20cf6a3b852` (32/40 quality-valid pairs; zero
positive top-gross pairs). Independent audit 012 covers 60 saved snapshots /
2,400 selected observations / 2,047 quality-valid pairs, reproduces stored
quality and top-edge results with zero mismatches, and agrees on 2,548 fee
calculations. Gross, depth, minimum and both fee-sensitivity gates remain zero.
The next scheduled source-analysis and Director cycles are 09:40 and 09:45 UTC.
See [Gate B checkpoint 013](VERITAS_MISSION2_GATE_B_CHECKPOINT_013.md),
[audit 012](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_012.json), and
ledger H133.

## Mission 2 continuation — prospective measurement pilot v2 and first scheduled scan

Implemented an isolated, bounded pilot 002 after pilot 001's protocol pin
proved too broad: v1 hashed observer, analysis, opportunity, and fee code, so
unrelated engineering changes stopped its recording. V2 pins only its protocol
module and the shared event/summary helper, while recording snapshot and v4
analysis hashes plus source-code lineage per scan. It reports the strict
reported-age sensitivity, per-leg age bands, timestamp skew, and separate
atomicity/sequence verification counts. This is a measurement instrument, not
an economic strategy.

The observer enrolls pilot 002 only on its next normal scan, without backfill;
pilot 001 state and the frozen Reality campaign remain untouched. The dashboard
has a separate v2 status and hash-verified artifact route. Focused pilot and
observer tests pass (12), all dashboard API tests pass (33), and the frontend
component test and TypeScript build pass. The API keeps v1's internally
verified event chain visible while explicitly flagging drift from its old
current-source pin. The first scheduled v2 scan recorded 20/40 quality-valid
pairs and zero positive top-gross candidates. Its event, summary, snapshot, and
finalized-analysis digests verify. Four states pass the strict reported-age
sensitivity; 16 legs on each side exceed five seconds; no batch atomicity or
sequence claims are verified. These single-scan measurements are descriptive.
The independent source audit 013 now covers 62 snapshots / 2,480 selected
observations / 2,095 quality-valid states and still has zero positive gross or
post-cost candidates. See the frozen
[pilot 002 protocol](VERITAS_MISSION2_COVERAGE_PILOT_002.json) and the
[operations note](VERITAS_OPERATIONS.md#prospective-measurement-pilot-v2).

The independent follow-up replay is recorded in
[Gate B checkpoint 014](VERITAS_MISSION2_GATE_B_CHECKPOINT_014.md) and
[audit 013](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_013.json).

## Mission 2 continuation — profile the complete shadow consume path

Profiling found that frozen `Tail.refresh()` repeatedly scans and symlink-
checks approximately 6,134 segment files every 0.5 seconds. The measured
68–91 ms CPU per scan can exceed the worker's 100 ms/s quota before record
processing. The Veritas branch now caches the path list behind directory
device/inode/mtime/ctime and retains the existing symlink check on rescans.
Reusing frame decodes plus the directory cache reduced bounded `Tail` plus
`Context` replay CPU by 16.16%, with an identical state digest. This replay
does not include the policy, journal, follow-up or status-save path.

The full consume path was profiled in an isolated temporary journal in
[Gate C checkpoint 020](VERITAS_MISSION2_GATE_C_CHECKPOINT_020.md). The branch
matched the pinned implementation's engine/context digests and all 768
normalized research rows on 2,774 records / 2,247 frames. A single bounded
pass used 79.8% less CPU under the same quota. This does not show live catch-up;
the next reader check is a second independent finalized-source window with
exact evidence-row comparison before any successor deployment decision. Keep
the original worker and campaign untouched. See [benchmark
002](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_002.json) and ledger H139.

## Active Mission 2 queue — 2026-10-16 15:07 UTC

1. **Recover useful forward evidence safely.** The frozen Reality shadow is
   still roughly 22 hours behind its source, has skipped about 200,483 lagged
   frames, and has not made a decision for about 30 hours. Its single
   historical restart count is unchanged. Keep the campaign and worker
   untouched. The branch shows equivalent decisions with materially lower
   CPU on two bounded source windows, but the 5% 32-segment canary timed out;
   only an eight-segment, 10% synthetic-clock canary completed. Any successor
   needs resumable, journal-preserving checkpoints and continuity checks
   before it can safely contribute prospective evidence.
2. **Keep the independent discovery and measurement streams operating.** The
   71-scan audit and the scheduled Arena v4 qualification still have zero
   positive gross candidates. Coverage pilot 002
   is 10/48 scans with 286/400 request-to-receipt-valid slots and no skipped
   scan sequence. Complete its fixed protocol and interpret repeated markets
   as dependent; do not change eligibility based on the economic result.
3. **Keep verifying incremental finalized-source throughput.** The scheduled
   15:10 UTC replay processed 57 segments / 16.6 MB and reached 6,498/6,498
   with zero pending bytes at 15:13 UTC; that matched the incoming count for
   this interval. Gap-detail had reached 6,487/6,489 at 15:06 UTC. Continue
   checking the normal timer because one successful interval does not prove
   long-run capacity margin.
4. **Do not train a predictor yet.** The readiness endpoint remains
   `WAITING_FOR_COVERAGE` at 1.77 recorded days versus a seven-day minimum.
   The audited panel still has no observed positive gross state or
   candidate-relevant labels. Keep model work blocked on evidence, not on
   engineering availability.

See Gate C checkpoint 022, Gate F checkpoint 036, independent audit 015,
coverage 012, the operations log, and inventory 082 for the evidence and
limitations.

## Active Mission 2 queue — 2026-10-16 16:38 UTC

1. **Resolve the frozen shadow's lag without changing its campaign.** The
   worker remains at a 10% CPU quota, has skipped 203,883 lagged frames, and
   has no decision newer than about 31.7 hours. The maintained-top branch
   canary now covers two sequential segments with exact state/journal
   equivalence and a modest 4.82% aggregate CPU reduction in one paired pass.
   This is not evidence of live recovery. Continue profiling the actual
   consume path and keep any prospective implementation in a versioned
   successor; do not restart or retune the frozen worker.
2. **Complete coverage pilot 002 under its fixed protocol.** It is at 13/48
   scans and 398/520 quality-valid slots across 390 markets. Only 84 slots
   meet strict reported freshness; sequence and atomicity verification remain
   zero. Do not equate the 76.5% main gate yield with synchronized evidence.
3. **Keep the incremental source analysis current.** The 16:12 UTC
   opportunity replay is at 6,614/6,614 segments with zero pending and still
   has zero positive economic gates. Gap-detail is at 6,663/6,665 catalog
   entries with zero pending finalized bytes. Check the next scheduled run
   for sustained headroom rather than assuming one current prefix proves it.
4. **Keep model and strategy work gated on evidence.** There is still no
   candidate-relevant target or independent strategy comparison. Continue
   the read-only observation and qualification cycle; do not train a model to
   compensate for missing synchronized outcomes.

See Gate C checkpoint 023, benchmark 004, inventory 083, and the operations
log for the current evidence and limitations.


## Active Mission 2 queue — 2026-10-16 17:39 UTC

1. **Validate the durable reader gain on a longer sequential window.** The
   matched one-segment 5% canary reduced process CPU by 76.48% with exact
   state and journal parity. Repeat on several sealed segments and at a
   segment rotation boundary before considering any versioned successor. The
   frozen campaign and worker remain protected.
2. **Keep the measurement and economic evidence streams running.** The canary
   reused finalized observations and yielded no new market evidence. Continue
   the fixed prospective coverage protocol and independent candidate
   qualification; repeated states remain dependent.
3. **Do not train models or select a new strategy without eligible targets.**
   The current engineering result concerns reader CPU only. It neither
   supplies candidate-relevant labels nor changes the zero-candidate economic
   evidence.

See Gate C checkpoint 024 and benchmark 005.


## Active Mission 2 queue — 2026-10-16 17:47 UTC

1. **Check resumable multi-segment continuity.** The committed branch now has
   exact parity on a four-segment replay and an 81.32% process CPU reduction
   versus the frozen implementation on this window. Validate a split/resume
   sequence with persistent isolated journal and source cursor before planning
   any versioned successor.
2. **Preserve the frozen live campaign while assessing recovery criteria.**
   The shadow service remains active but still has one historical restart;
   no canary has changed its cursor or journal. Any future recovery mechanism
   must preserve source continuity and journal integrity.
3. **Continue evidence-gated economic work.** This replay produced no new
   market states or independent opportunities and no execution ground truth.
   Keep the no-trade posture and defer model training until candidate-relevant
   targets exist.

See Gate C checkpoint 025 and benchmark 006.


## Active Mission 2 queue — 2026-10-16 17:54 UTC

1. **Test recovery from a bounded interruption.** The clean two-process split
   resumed without lost or duplicated business events and reproduced the
   one-shot runtime and research state. A second `worker_start` and reordered
   same-time observations make the journal tail hash differ; decide whether
   stable append order is an acceptance need, then exercise a controlled stop
   at a durable checkpoint in an isolated work directory.
2. **Keep any production recovery separate from the frozen campaign.** The
   current shadow remains untouched. A versioned successor still needs a
   bounded run and a documented continuity plan before prospective evidence
   can be used.
3. **Continue collecting and auditing economic observations.** This replay
   used historical recordings and created no new market states, candidate,
   fill evidence, or strategy/model evaluation.

See Gate C checkpoint 026 and benchmark 007.


## Active Mission 2 queue — 2026-10-16 17:58 UTC

1. **Assess event-order reproducibility across process resumes.** The clean
   segment split and the forced SIGTERM both preserved state and normalized
   business-event content, but only the SIGTERM replay preserved normalized
   event order. Decide whether byte-stable append order is an acceptance
   requirement before adding more ordering machinery.
2. **Keep the frozen live shadow and campaign unchanged.** The current shadow
   remains untouched. A versioned successor still needs a bounded forward
   run and a documented continuity plan before prospective evidence can be
   used.
3. **Keep economics evidence-gated.** These historical source replays add no
   new market observations, candidates, actual fills, or model targets. The
   decision-to-commit recovery path already has focused fault-injection
   coverage in `test_missing_decision_commit_marker_is_repaired_before_followup`.

See Gate C checkpoint 027 and benchmark 008.


## Active Mission 2 queue — 2026-10-16 18:47 UTC

1. **Keep the frozen campaign and live writer untouched.** The current shadow
   is still about 441,813 recorder ordinals behind, with a 25-hour-old source
   receipt and 33-hour-old decision. The current branch canary verifies
   isolated resume ordering but is not permission or evidence to restart the
   protected worker. The 18:40 source replay caught up through 6,905 finalized
   segments with no pending source segments; keep watching live shadow lag and
   preserve campaign identity.
2. **Continue the economic observation, not model training.** Independent
   replay now covers 78 snapshots / 3,120 selected observations and still has
   zero positive gross or qualified states. Keep the no-trade baseline. The
   states are selected and correlated; do not convert the count into
   independent-trial evidence. The scheduled scan-78 Arena child also
   completed 78/78 events with zero positives at all five gates and complete
   empty candidate evidence and source replay. The next Director reconciliation
   is due at 19:15 UTC.
3. **Let pilot 002 reach its predeclared completion before judging its
   measurement yield.** It is at 17/48 scans and 553/680 quality-valid slots.
   Its age and synchronization diagnostics remain distinct from atomicity or
   sequence verification. Gap detail last covered 6,894 replayable segments;
   review the scheduled 18:50 batch after the source analyzer caught up to
   6,905 segments, then compare the two prefixes without assuming their
   timestamp difference is an exact pending count.

See [Gate B checkpoint 015](VERITAS_MISSION2_GATE_B_CHECKPOINT_015.md), [Gate C
checkpoint 028](VERITAS_MISSION2_GATE_C_CHECKPOINT_028.md), [inventory
088](VERITAS_MISSION2_RESEARCH_INVENTORY_088.json), and benchmark 009. The
four-segment canary used historical input;
it added no market observations, fills, or model targets.
