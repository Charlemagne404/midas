# Veritas follow-up sampling and horizon design — draft 002

**Status:** refined design only. No campaign was created or started.

**Supersedes:** draft 001's conditional primary estimand and market-hour arm
assignment.

## Research question

Does activity-stratified selection produce more qualifying one-second public
follow-up measurements per scheduled decision slot than uniform selection from
the same eligible market universe, while keeping all existing source-quality
rules and the no-trade control?

This is a measurement-efficiency question. The outcome is not a fill, queue
position, execution probability, or profitability label.

## Baseline and planning sensitivity

The selected baseline recorded 1,408 scheduled decisions, 381 valid initial
states, and 27 qualifying one-second public measurements. Therefore:

- **Primary planning rate:** 27 / 1,408 = 1.92% per scheduled slot. Invalid
  initial states remain in this denominator and count as primary-outcome
  non-successes.
- **Secondary descriptive rate:** 27 / 381 = 7.09% conditional on an initial
  state passing the quality gate. This is not the primary causal estimand,
  because the sampling policy can change which markets yield valid starts.
- **Initial-state failures:** 1,027 / 1,408. Keep these distinct from later
  follow-up censoring.

The planning sensitivity targets a 50% relative improvement in the primary
rate, from 1.92% to 2.88%. This is a measurement-yield planning target, not an
economic or profitability threshold. A normal approximation for a two-sided
two-proportion test at 5% significance and 80% power requires 3,994 independent
scheduled slots per arm. A simple design-effect sensitivity gives:

| Assumed design effect | Slots per arm | Total slots | Days at 1,408 slots/day | Fits 14-day slot count? |
| ---: | ---: | ---: | ---: | --- |
| 1.0 | 3,994 | 7,988 | 5.67 | Yes |
| 1.5 | 5,991 | 11,982 | 8.51 | Yes |
| 2.0 | 7,988 | 15,976 | 11.35 | Yes |
| 3.0 | 11,982 | 23,964 | 17.02 | No |

The one-day baseline volume projects to 19,712 slots in 14 days and supports a
design effect of at most 2.47 under this approximation. This is not a powered
study claim: no market, time-block, family, or repeated-measure correlation was
estimated, and the baseline rate may not persist. The machine-readable
calculation is [follow-up power sensitivity 001](VERITAS_GATE_A_FOLLOWUP_POWER_001.json).

Cluster dependence must be represented in both planning and analysis. The
usual cluster design effect depends on cluster size and intracluster
correlation; repeated cross-sections also require time autocorrelation in the
calculation ([CONSORT extension for cluster randomized trials](https://www.bmj.com/content/345/bmj.e5661),
[cluster trials with repeated cross-sections](https://www.bmj.com/content/350/bmj.h2925)).
The single design-effect grid above is only a sensitivity illustration.

## Candidate protocol

### Eligible universe and activity strata

1. Freeze the market identifiers and paired-outcome mapping from a finalized
   pre-period before the randomized observation window. Do not add markets
   after looking at arm outcomes.
2. Require two complete UTC days of pre-period evidence. A market is eligible
   only if subscription and finalized-source continuity metadata establish
   coverage for at least 95% of its planned pre-period slots and its paired
   outcome mapping is unambiguous. This coverage rule must use subscription
   and recording metadata, not market update counts, initial-book validity,
   edge, labels, or future outcomes. If the source cannot distinguish a quiet
   market from an unobserved one, do not classify that market or start the
   study.
3. Require at least nine eligible markets. Compute each market's pre-period
   activity as finalized source frames updating either outcome per covered
   subscription hour. Split eligible markets into equal-count low, medium, and
   high tertiles. Resolve boundary ties by ascending stable market identifier.
   If any tertile would contain fewer than three markets, defer instead of
   changing the number of strata after inspecting outcomes.
4. The activity-stratified arm allocates equal scheduled-slot exposure to each
   tertile, then selects a market uniformly within the selected tertile. The
   control selects uniformly from the full eligible universe. Use replacement
   so each scheduled slot is assigned without outcome-dependent exclusions.

The 95% coverage, two-day pre-period, and nine-market minimum are candidate
protocol thresholds, not established properties of the current data. Verify
that existing subscription and source metadata can support them before a plan
is frozen.

### Assignment and measurement

- Keep the existing scheduled decision cadence and quality gates: the 250 ms
  input-lag limit, 5-second paired-book freshness limit, initial-state checks,
  synchronization tolerance, follow-up matching rules, and every source
  quality filter.
- Assign each scheduled slot 1:1 to an arm within UTC five-minute blocks. For
  odd block sizes, use a pre-generated seeded assignment that keeps cumulative
  arm exposure balanced within each UTC day. Save the complete slot-to-arm and
  slot-to-market schedule, seed, and hashes before outcomes are inspected.
- Apply the same one-second primary horizon to both arms. Keep 5 seconds as a
  bridge; treat 100 ms and 300 ms as short diagnostics and 15 seconds and 30
  seconds as exploratory longer diagnostics. Do not loosen synchronization,
  freshness, input-lag, or quality rules to raise observed yield.
- Keep the no-trade policy in place for every slot. No order path is part of
  the campaign.

### Outcomes and analysis

The primary outcome for a scheduled slot is 1 only if the initial state passes
the existing quality gate and a qualifying synchronized public measurement is
available at one second. Invalid initial states, unavailable follow-ups, and
other non-qualifying outcomes are 0 for this **all-scheduled-slot** estimand;
retain their separate censor and invalidity reasons for diagnosis.

Report the arm-specific numerator and scheduled-slot denominator, absolute risk
difference, risk ratio, and a predeclared uncertainty interval. Preserve the
exact randomized block schedule for a randomization-based primary analysis.
Report conditional follow-up yield among valid initial states only as a
secondary descriptive measure, beside each arm's valid-initial-state fraction.
Also report every censor reason, activity stratum, market, and UTC time block.

Before freezing the plan, validate the randomization analysis against the
crossed market and time dependence in multi-day finalized data. If the number
of market or family clusters is too small for the proposed interval method,
report that limit and rely on the predeclared randomization distribution; do
not treat scheduled slots as independent replicates.

### Stop rule and interpretation

Use a fixed 14-calendar-day randomized window. Do not stop early based on arm
differences or apparent success, and do not extend after inspecting outcomes.
If the observed scheduled-slot volume or the cluster-aware power simulation
shows that the target effect cannot be detected inside that cap, report the
study as insufficient or revise the design before freezing a new version.

The estimand applies to the frozen eligible universe and its activity-stratum
mix, not venue-wide prevalence. Even a higher qualifying public measurement
yield would establish neither executable fills nor profitability.

## Readiness decision

**Do not freeze or start a prospective campaign yet.** The current evidence
supports the one-day slot-yield baseline, but it does not establish the two-day
per-market coverage rule or the crossed market/time dependence needed for a
cluster-aware power calculation. At the proposed 50% relative lift, the
14-day slot count only accommodates a simple design effect up to about 2.47;
the current data do not show whether the actual dependence is below that
threshold.

Before any separate campaign plan is frozen:

1. verify per-market subscription and finalized-source coverage for a complete
   48-hour pre-period without reading the active `.open` segment;
2. estimate or bound time-block and market/family dependence from finalized
   multi-day outcomes, then simulate the exact assignment and analysis;
3. confirm that the frozen eligible universe has at least nine markets and
   three markets per activity tertile;
4. freeze the complete assignment schedule, code, primary outcome, interval
   method, sample cap, censor handling, and no-trade policy; and
5. obtain an independent review of the protocol and power simulation.

No campaign, Reality setting, service, or source record was changed for this
design refinement.
