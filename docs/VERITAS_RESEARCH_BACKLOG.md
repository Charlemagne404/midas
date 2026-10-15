# Veritas research backlog

The ranks reflect expected information value, possible economic impact, current
evidence, and compute cost. Work remains on `project/veritas`; the frozen
Reality campaign is a protected reference.

| Rank | Question | Evidence today | Next experiment | Promotion rule |
| --- | --- | --- | --- | --- |
| 1 | Which separate activity-aware sampling and future horizons improve synchronized public follow-ups while retaining the current quality gate? | The v7 replay found 1,895/2,945 decisions over the 5-second freshness gate. The refined protocol uses the 1,408-slot baseline's 1.92% all-scheduled one-second yield as its primary planning rate. Its 50% relative-lift sensitivity fits the 14-day slot count only through a simple design effect of about 2.47; crossed market/time dependence is unmeasured. | Validate the two-day subscription-coverage gate and estimate/bound market and time dependence from finalized multi-day evidence. Run the exact assignment simulation in [follow-up design draft 002](VERITAS_GATE_A_FOLLOWUP_DESIGN_002.md) before freezing any separate campaign. | The draft is not campaign-ready. Never alter Reality's horizons, sampling, or labels. A higher public-measurement yield does not establish fills or profitability. |
| 2 | Does a longer and broader observed panel contain a positive gross complementary opportunity? | The v3 snapshot covered about 3 h 18 m and 29,932 quality-valid states across 15 market IDs. Every five-share state had full depth, but top and full-depth pre-fee positive counts remained zero; maximum top edge was -0.001. | Rerun the versioned funnel on later finalized prefixes and any new approved observation cohort. Stratify by market family, activity, lifetime, and liquidity. | A candidate must pass source quality, same-condition payoff, per-leg USDC minimums, and full-depth costs before fees or execution assumptions are considered. |
| 3 | Does the v2 economic model correctly bound a real, positive gross candidate across size and cost assumptions? | Official fee fields include rate and exponent; taker buy fees are collected in shares. The v2 engine covers exponent, fee rounding sensitivities, share deductions, and USDC minimums. The synthetic 100-share full-depth example has +1.42 USDC worst-resolution P&L under single-match rounding, about 50.20 USDC of adverse unmatched-leg loss, and negative P&L under the fragmentation-safe fee bound. | Independently recalculate any observed candidate if one appears; evaluate per-leg schedules, depth, partial positions, capital lockup, settlement, and break-even completion assumptions. | Do not promote synthetic thresholds or capacity as empirical performance. Unknown fills stay unknown. |
| 4 | Does ML improve an economically useful decision over heuristics? | Reality reports no eligible learned model; prior depth heuristics beat learned alternatives and held-out risk-tree gains did not survive. The current raw funnel has no gross candidate. | Reassess label count and target support after the source-quality and prospective-horizon work. Train only if real chronological labels support a useful target. | Prediction gains must improve a predeclared hypothetical decision metric on independent data. |
| 5 | Can the Research Director schedule bounded Veritas work without duplicating existing controls? | The pre-release policy-search failure was fixed before release. Gate G's backend plan fixture had a 180-second subprocess timeout around a 300-second job budget; after raising the wrapper to 330 seconds, the isolated fixture passed 4 tests in 162.80 seconds, with a 142.59-second nested job. The browser source-record failure likely came from a `.seg`/`.open` rotation lookup gap fixed by release commit `c96a031`; the focused regression and same-worktree browser recheck passed, though the original response was not captured. The separate canary failure came from a frozen reader comparing an empty segment's `last=0` with cursor 847; release commit `8775bda` added the zero-count guard and regression. See [Gate G failure forensics 001](VERITAS_GATE_G_TEST_FAILURE_FORENSICS_001.md) and [shadow-canary forensics 001](VERITAS_SHADOW_CANARY_FAILURE_FORENSICS_001.md). | Run the full backend suite only in a bounded Veritas verification pass. Isolate the browser operations endpoint before repeating that test, and classify remaining one-shot failures without writing to Reality. | No unrestricted code changes, campaign mutation, or compute feedback loop. |
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
  is [Gate A checkpoint 011](VERITAS_GATE_A_CHECKPOINT_011.md). The corrected
  v2 economics are in
  [Gate A checkpoint 008](VERITAS_GATE_A_CHECKPOINT_008.md).
- The bounded controlled capacity sensitivity is
  [VERITAS_GATE_B_CAPACITY_001.json](VERITAS_GATE_B_CAPACITY_001.json); it uses
  synthetic inputs and does not promote a strategy.
