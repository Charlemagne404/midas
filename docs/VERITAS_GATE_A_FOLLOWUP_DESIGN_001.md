# Veritas follow-up sampling and horizon design — draft 001

**Status:** design draft only. No campaign was created or started.

This note proposes a prospective, no-trade comparison of uniform market
sampling with activity-stratified sampling. It uses the frozen Reality
campaign only as a protected reference. Any future study would require its own
campaign identity and a separately frozen plan, source window, code version,
market universe, seed, and analysis rules.

## Research question

Can activity-stratified market selection increase the rate of synchronized
public follow-up measurements at a one-second horizon, compared with uniform
random market selection, while retaining the existing initial-state and
follow-up quality rules?

The outcome is a qualifying public measurement. It is not a fill, queue
position, execution probability, or profitability label.

## Evidence motivating the design

The initial Reality snapshot had 1,408 scheduled decisions across 10 markets;
381 had a valid initial state. The selected cohort covered one UTC day and six
connected market families. Follow-up counts below use the same 381 valid
initial decisions as the denominator. The remaining scheduled decisions were
invalid at the initial state and are excluded from this conditional rate.

| Horizon | Observed public measurements | Fraction of valid initial states | Future unavailable | Source timeout | Stale | Pending / gap / issue |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 ms | 3 | 0.8% | 309 | 65 | 0 | 4 |
| 300 ms | 10 | 2.6% | 309 | 54 | 2 | 6 |
| 1 s | 27 | 7.1% | 252 | 59 | 19 | 24 |
| 5 s | 22 | 5.8% | 98 | 37 | 154 | 70 |

The combined pending/gap/issue column groups advertised-top-pending,
book-issue gap, and recorded-gap censor reasons. Counts in each row plus the
observed count sum to 381. At 1 second, the 24 grouped censors comprise 7
pending, 14 issue-gap, and 3 recorded-gap outcomes. At 5 seconds, the 70
comprise 29 pending, 14 issue-gap, and 27 recorded-gap outcomes.

Across all horizons, valid-initial-state follow-ups had 968
future-observation-unavailable and 215 source-availability-timeout censors.
These are distinct from the 1,027 invalid initial decisions. The finalized
source replay also found that 1,895 of 2,945 scheduled decisions exceeded the
frozen 5-second freshness gate; all such failures were pair-wide. Most failing
legs remained below the source's separate 60-second stale threshold. These
source-age findings describe the protected campaign snapshot and do not show
that changing either threshold would improve measurement quality.

Sources: [Gate A baseline](VERITAS_GATE_A_BASELINE.json), [Gate A checkpoint
010](VERITAS_GATE_A_CHECKPOINT_010.md), and [Gate A checkpoint
011](VERITAS_GATE_A_CHECKPOINT_011.md).

## Candidate protocol

This is a proposal to refine before any future campaign is frozen.

### Arms and assignment

- **Uniform control:** select eligible markets uniformly at random from a
  frozen eligible universe.
- **Activity-stratified arm:** classify the same eligible universe into low,
  medium, and high paired-book update-activity strata using finalized public
  observations from a fixed pre-period. Randomly allocate equal sampling
  exposure to each stratum, then select markets uniformly within each stratum.
- Define activity only from pre-period update counts or rates and coverage.
  Do not use edge, labels, future outcomes, policy decisions, or profitability
  in stratum construction. Freeze the eligible universe, pre-period, coverage
  rule, stratum boundaries, and random seed before assignment.
- Use equal scheduled-slot exposure per arm. Assign each market-by-UTC-hour
  block to at most one arm; allow a market to appear in both arms only in
  different UTC-hour blocks. Generate and retain the assignment schedule and
  selection seed before outcomes are inspected.
- Require enough pre-period finalized coverage to assign activity strata
  without outcome-dependent exclusions. If the coverage rule fails, defer the
  study or redesign the universe before freezing it.

### Horizons and quality rules

- **Primary candidate horizon:** 1 second.
- **Bridge horizon:** 5 seconds.
- **Short continuity diagnostics:** 100 ms and 300 ms.
- **Longer candidate diagnostics:** 15 seconds and 30 seconds.

The 1-second horizon is a candidate primary endpoint because it had the
largest observed count in the initial snapshot. That selected, small baseline
does not guarantee that it is optimal in a new cohort. The 15- and 30-second
checks are exploratory candidates; they must use the same frozen
synchronization tolerance, decision freshness gate, input-lag limit, and
quality checks. Do not extend either tolerance to obtain more observations.

Keep the existing decision cadence, 5-second freshness gate, 250 ms input-lag
limit, initial-state eligibility checks, follow-up matching rules, and all
source-quality filters unchanged in both arms. Preserve censor reasons and
pending outcomes by horizon. Keep the no-trade policy in place for the full
study.

### Outcomes and estimands

The candidate primary comparison is the difference between arms in the
proportion of valid initial decisions with a qualifying synchronized public
measurement at 1 second. Report the arm-specific numerator and denominator,
risk difference, risk ratio, and a cluster-aware uncertainty interval.

Also report, by arm and activity stratum:

- qualifying measurements per all scheduled decisions, alongside the
  conditional rate among valid initial states;
- the valid-initial-state fraction and every horizon-specific censor reason;
- paired-book age, cross-outcome skew, input lag, and quality failures;
- counts by market family and market-by-UTC-hour assignment block.

The conditional primary comparison applies to the states each sampling policy
produces. Because activity stratification changes the sampled population,
also show the all-scheduled-decision yield and stratum-specific results. Do not
describe either arm as venue-wide prevalence.

### Sample size and stopping

Before freezing a future plan, calculate power using the proposed assignment
unit and a cluster-aware method. Use baseline outcome rates only as planning
inputs; freeze the target effect, confidence level, power target, and required
number of independent market-by-hour blocks before observing study outcomes.
If the target cannot be reached by a proposed maximum 14-day observation
window, stop at that limit and report the study as insufficient rather than
extending it after inspecting results. Do not peek at arm differences or stop
early for apparent success.

## Interpretation limits and controls

Repeated decisions within a market, family, and hour are correlated. Analyze
at the randomized market-by-UTC-hour block level and account for market-family
clustering; do not treat individual decisions as independent replicates.
Predeclare the exact uncertainty procedure and handling of any sparse family
before a future plan is frozen.

The study tests public measurement yield under two sampling policies. It does
not train a model, alter Reality, relax quality rules, infer fills, or test
profitability. No campaign, collector setting, service, or order flow was
changed for this design draft.

## Decision before any prospective run

Refine and independently review the eligible-universe rule, pre-period
coverage threshold, randomization schedule, cluster-power calculation, and
analysis code. If later approved and frozen, run only under a new campaign ID
and retain the no-trade control. This document alone authorizes no campaign
creation or start.
