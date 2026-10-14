# Veritas research backlog

The order reflects expected information value, economic impact, current evidence,
and compute cost. Work remains on `project/veritas`; the frozen Reality campaign
is a protected reference.

| Rank | Question | Evidence today | Next experiment | Promotion rule |
| --- | --- | --- | --- | --- |
| 1 | Why are most initial states unusable, and are those states preventable? | In the first consistent journal snapshot, 1,027 of 1,408 decisions failed initial quality checks; 898 were `stale_book`. | Stream the raw source and campaign events by market, pair age, cross-outcome skew, activity stratum, and source lag. Reproduce quality reasons independently. | Repair only a demonstrated pipeline defect. Any sampling change gets a new frozen campaign identity. |
| 2 | Are there complementary opportunities after full displayed depth, fees, and minimums? | All 381 quality-eligible initial decisions had negative top-of-book pre-fee edge; no positive discrepancy was observed in this sample. | Build a full depth-walk funnel by market family, time block, quantity, and capital. Compare to no-trade and preserve unknown execution as unknown. | A candidate must survive cost bounds and independent payoff/accounting review. |
| 3 | Which future public horizons are measurable in this market panel? | Of 1,524 follow-ups with valid initial states, 62 were public measurements and 1,462 were censored. Most valid-state censoring was missing synchronized future data or a source-availability timeout. | Measure pair update intervals and synchronized-book availability by market and activity stratum; predeclare candidate horizons for a separate campaign. | Never alter Reality's horizons or retroactively relabel it. |
| 4 | Is fee rounding materially understated when match fragmentation is unknown? | Legacy Reality `fee_reserve` adds one quantum per leg; the shared economics package already provides a fragmentation upper bound. | Independently verify fee arithmetic against current official market-specific parameters and scenario partitions; integrate only in Veritas versions. | Use the bound as a conservative scenario, not an estimate of actual fees or fills. |
| 5 | How do incomplete legs and capital lockup change capacity? | Existing Prometheus/Reality evidence documents unmatched-position risk; the first Veritas pair engine can calculate terminal payoff bounds for verified binary semantics. | Run matched size grids, 500–50,000 SEK scenarios after explicit collateral/FX inputs, settlement durations, and stress assumptions. | Do not imply displayed capacity guarantees fillable size. |
| 6 | Does ML improve an economically useful decision? | Reality's accepted evidence reports no eligible learned model; the depth heuristic beat learned alternatives and held-out risk-tree gains did not survive. | Recheck the original failure mechanisms and target support before any training; compare chronological grouped models with simple controls. | Train only on sufficient real labels; promote only if prediction gains improve predefined hypothetical decisions. |
| 7 | Can the Research Director schedule useful controlled work durably? | Existing Arena and Reality scheduling systems already provide bounded jobs, provenance, and freeze controls. | Inventory current director interfaces and add only missing hypothesis ranking, matched-result links, and stop rules. | No unrestricted source edits, campaign mutation, or compute feedback loop. |
| 8 | What native Veritas evidence should the dashboard expose? | Reality already has a bounded API and native dark dashboard. | Design a Veritas view over bounded APIs backed by validated economic and funnel artifacts. | Display observed, derived, assumed, simulated, and unknown values separately. |

## Current controls

- No order, wallet, credential, deposit, or live-execution integration is in scope.
- Do not restart, pause, or take ownership of Reality service writers.
- Keep confirmation data untouched and report all unsuccessful experiments.
- The first baseline and economic implementation are recorded in
  [the research ledger](VERITAS_RESEARCH_LEDGER.json) and
  [Gate A checkpoint](VERITAS_GATE_A_CHECKPOINT_001.md).
