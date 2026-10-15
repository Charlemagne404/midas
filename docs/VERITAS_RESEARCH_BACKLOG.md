# Veritas research backlog

The Mission 2 queue below reflects expected information value, possible
economic impact, current evidence, and compute cost. Work remains on
`project/veritas`; the frozen Reality campaign is a protected reference. The
earlier Mission 1 handoff backlog is retained below for provenance.

## Mission 2 queue (2026-10-15)

| Rank | Question | Evidence today | Next experiment | Promotion rule |
| --- | --- | --- | --- | --- |
| 1 | Does request-to-receipt freshness improve usable pair measurement without accepting stale or queued books? | v4 reclassifies the same twelve finalized snapshots: 107/480 pass the legacy age/skew gate and 431/480 pass the request/receipt gate (+324, +67.5 pp). Batch atomicity and upstream queue age remain unverified. | Keep paired classification on every new scan and validate freshness against a source with sequence or equivalent guarantees. Keep reported age/skew diagnostics. | Do not call request-to-receipt a venue-time guarantee. Require source identity, complete asset set, bounded receipt time, and an independent freshness check before candidate promotion. |
| 2 | Does a wider repeated market panel change the gross-opportunity result? | Twelve snapshots cover about 181 minutes, 161 distinct IDs, 431 valid pairs, and zero positive top/depth/minimum/fee candidates. The latest bounded union has 167 eligible markets; sampled state changes are sparse between requests and are not true update rates. | Keep the 30-minute pilot running, then review market/time dependence after at least 24 hours. Keep the specific follow-up design's 48-hour coverage and dependence gates intact. | Never treat repeated snapshots as independent events or the six-frame union as a venue census. |
| 3 | Which segments remain under-covered by the current discovery frames? | Current query union is six capped frames and 300 IDs; 133 IDs are excluded by unsupported payoff or augmented negative-risk semantics. Selection has liquidity, expiry, category, and spread strata, conditional on that union. | Compare eligible market coverage by protocol, category, liquidity, and lifecycle. Add query frames only after observing rate use, response bounds, and resource/storage cost. | New payoff structures require verified settlement/payoff identity and adversarial counterexamples. |
| 4 | Does economic qualification find any candidate as the pilot accumulates data? | Run `VERITAS-M2-ECO-QUAL-001-RUN-b401cd384481` uses the v4 analysis event directory and compares top asks with 20-share full-depth, per-leg minimum, and two fee gates on 431 valid states across 161 markets; all counts are zero. | Re-run only when new finalized snapshots arrive; preserve each input set under its deterministic run ID. | Any candidate must pass same-condition semantics, independent replay, freshness, complete depth, both minimums, and fees before hypothetical strategy research. |
| 5 | Does incremental snapshot analysis remain complete and idempotent under interruption or backlog? | Twelve v4 events have verified hashes, zero pending work, per-market coverage and legacy/current gate outcomes; tests cover versioned event routing, duplicate processing, digest failure, malformed snapshots, and bounded recovery. | Keep event/state lineage checks in each release; exercise larger backlogs in isolated fixtures before changing the per-run bound. | No source record rewrite, duplicate event application, unbounded snapshot read, or silent event repair. |
| 6 | Is there evidence for a strategy or predictor tournament? | There are no positive gross candidates or realized/public fill labels in the new panel. The comparison tests qualification, not PnL. | Keep no-trade. Reassess only after quality-valid positive gross evidence and suitable chronological outcome labels exist. | No model training or strategy promotion from synthetic cases or a repeated selected holdout. |
| 7 | Should Veritas source analysis become a typed Arena job? | A bounded systemd timer now drives immutable capture and incremental analysis. The existing Arena scheduler has no Veritas source-reading job type; prior review deferred an adapter until repeated analysis justified it. | Keep the one-shot timer simple while coverage is short. Revisit typed Arena integration after a multi-day panel and measured recurring workload. | Any adapter must pin source/code, bound finalized reads and artifacts, recover idempotently, and keep campaign controls out of scope. |
| 8 | Does incremental Reality source replay remain bounded and resumable while it catches up? | The latest scheduled recurrence processed 128 segments / 26.56 MB in 158 seconds (7.937 CPU seconds); cumulative progress is 786/2,959 segments with 2,173 pending. No campaign-window frames occur in the processed prefix. See [Gate A checkpoint 010](VERITAS_MISSION2_GATE_A_CHECKPOINT_010.md) and the current [research inventory 011](VERITAS_MISSION2_RESEARCH_INVENTORY_011.json). | Keep the offset timer active; inspect source hashes, processed/pending counts, resource use, and campaign-window coverage as it advances. | Never open the active `.open` source, change Reality records, silently continue after prefix/code drift, or report bootstrap counts as economic evidence. |
| 9 | Can independent coverage evidence separate unavailable future observations from venue inactivity and feed gaps? | The v1.3 audit records 10,184 `future_observation_unavailable` labels across valid starts, but the frozen worker does not distinguish quiet venues, feed selection, and every missing-source cause. It also records explicit stale, timeout, gap, reconstruction, and ordering labels. | Compare the frozen journal with an independent sequence or feed-coverage source, if one is available, while leaving campaign labels unchanged. | Do not recode historical outcomes without source-grounded evidence; keep unresolved mixtures explicit.

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
