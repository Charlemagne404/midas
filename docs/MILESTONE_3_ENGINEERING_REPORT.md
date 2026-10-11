# Milestone 3 engineering report — The Laboratory

Implemented and verified on 2026-10-11. This delivers a coherent working Laboratory
core and research dashboard, with explicit remaining scope. It does **not** claim every
advanced feature in Directive 003 is complete. All trading remains internal simulation.
The original integrations, strategy, risk gate, broker, ledger, scenario catalog and UI
remain operational. No wallet, signing credential or live-order submission was added.

## Completed implementation

- A stable priority event heap with virtual time, frozen inputs, delayed events,
  cancellation/replacement, checksummed checkpoints and exact environment resumption.
- Production broker/strategy/risk reuse; separate observed and venue states; seeded
  latency, liquidity and adverse-price assumptions; FOK/FAK semantics, independent
  legs, asynchronous acknowledgment, cancellation races and expiration.
- Validated content-addressed dataset manifests, receipt-time windows, related binary
  instrument replay, original raw public data, observation latency, late snapshot
  protection, duplicate/conflict handling and unsequenced-delta invalidation.
- Frozen declarative scenarios, 19 parameterized families, strategy/model sweeps,
  fault combinations, timing-boundary mutation and stateful/property testing.
- Independent rational/integer fee, acquisition, reservation, payout, inventory and
  conservation checks alongside existing ledger/risk validation. Losses pass when
  behavior is valid; accounting failures invalidate financial aggregation.
- Active adversarial search, bounded delta debugging, single-deletion minimality,
  original/minimized incident artifacts and a permanent executable regression fixture.
- Local SQLite campaign orchestration, bounded spawned workers with memory caps,
  writer ownership, admission/resource budgets, active pause/cancel, interruption,
  atomic episode checkpoints, safe resumption and compact successful-run persistence.
- Versioned experiment manifests, source and dataset/manifest hashes, exact result and
  journal integrity checks, one-command reconstruction/reproduction, and explicit
  irreproducibility when source/data changed.
- Paired strategy/model comparisons, distributions, synthetic bootstrap estimates,
  drawdown, partial execution, hypothetical slippage, capital utilization/time lockup,
  losses, rejection metrics and failure counts. No-trade and conservative controls
  receive the same scenario inputs, capital ceiling, risk and cost assumptions.
- Seven functioning dashboard tabs: overview, builder, monitor, replay, adversarial
  incidents, strategy comparison and scenario explorer. Real controls, pagination,
  persisted histories, before/after inspection, observed books, scrub/step/playback,
  source/settings visibility, exports and actual re-execution are browser-tested.
- Explicit per-fill/redemption cost, financing and collateral-value sensitivity.
  Acquiring a complete pair does not release cash. Unresolved positions stay locked.
  Every Laboratory output remains economically unverified.

Implementation maps and reproduction commands:
[Architecture](LABORATORY_ARCHITECTURE.md), [market simulation](MARKET_SIMULATION.md),
[historical replay](HISTORICAL_REPLAY.md), [scenario generation](SCENARIO_GENERATION.md),
[adversarial testing](ADVERSARIAL_TESTING.md),
[reproducibility](EXPERIMENT_REPRODUCIBILITY.md),
[validation](SIMULATION_VALIDATION.md), [baseline](MILESTONE_3_BASELINE.md).

## Executed evidence and findings

[Tests and demonstrations](MILESTONE_3_TEST_REPORT.md) record **228 Python passes,
one PostgreSQL skip, four frontend passes and four browser passes**, plus successful
lint, formatting, strict type checks and frontend build. No original regression
scenario/test was removed.

The final randomized campaign executed **1000 episodes / 12336 events** with zero
invariant failures and a worst valid virtual outcome of **−10.40**. A separate 100-trial
fault-combination search found zero failures, which is a bounded result. The deliberately
corrupted ledger produced a detected, minimized and exactly reproduced failure; it
is clearly labeled as controlled, not a discovered production accounting bug.

The unchanged evaluation sample compared three strategies and three models over
12 paired episodes (**108 runs**). More conservative strategy configuration did not
improve those outcomes. Optimistic-versus-standard performance was inconclusive under
the synthetic bootstrap. No-trade produced zero. No evaluation dataset was tuned to
make a preferred strategy look better. Confidence statements describe generated episode
variation and do not establish independent observations of market reality.

Two genuinely captured public datasets validate and replay their original negative-edge
outcomes. They do not establish profitable historical opportunities, long-term feed
completeness, live fill probability, live V2 economics or successful real redemption.
Recorded and synthetic provenance remain distinct in inputs, results and the UI.

Measured performance distinguishes **83512 heap events/second**, **201 fully audited
events/second**, and **13.999 durable campaign runs/second**. The final compact
1000-episode benchmark archive used about **1.49 MiB**. Worker memory measurement is a
sampled lifetime peak, not a claim of total concurrent system usage. Profiling identified
portfolio reconstruction/deep copying/serialization as bottlenecks; discarded replay
construction was removed while preserving both accounting checks. Raw profiles and
configurations are checked in. No million-episode workload was executed.

Development tests discovered mutable replay journal aliases and a result-monitor cache
refresh defect; both were fixed with regression coverage. Conflicting financial identities
now reject, and a paused venue independently prevents matching after submission.
Existing local paper history recovered from an integrity-checked read-only backup,
retaining two fills, available 92.40 and locked 7.60 virtual collateral. No financial
history was reset to make the upgrade appear successful. The existing local API was
restarted after an integrity-checked backup and reports READY with the same balances
and two fills, zero live orders, both validated datasets and all four final campaigns.
[Runtime evidence](MILESTONE_3_LOCAL_RUNTIME.json) and the
[actual running overview](laboratory-overview.png) retain that verification.

## Acceptance status and remaining scope

| Directive criterion | Evidence/status |
| --- | --- |
| Existing functionality operational | Original suites plus legacy account backup replay |
| Deterministic large-scale execution | 1000-run campaigns, heap benchmark, one/two worker and hash-seed tests; million-scale unmeasured |
| Validated historical manifests / look-ahead protection | Real capture fixtures, clock/integrity and future-observation tests |
| Random generation / adversarial injection / minimization | Implemented and demonstrated; bounded search, controlled fixture |
| Independent math/accounting checks | Automatic production reconciliation plus independent rational oracle |
| Campaign execution / monitoring / cancellation / recovery | Backend, active control, durable episode and browser tests |
| Fair execution/strategy comparisons | Identical paired seeds/data/configs; no-trade controls and visible settings |
| Versioning/reproduction | Exact hashes; original dirty source restoration still external |
| Functional dashboard / real replay | Four browser workflows, saved screenshot and real persisted/reconstructed journals |
| Performance measurement | Actual profiles, throughput, storage and scoped RSS figures |
| Economic assumptions / simulated-only boundary | Explicit costs, lockup and verification flags; original read-only transport tests |
| Automated checks / backed claims | Passed with PostgreSQL skip and stated warnings; broader requested scope remains partial |

Deferred or reduced features are substantial and explicit:

- Full multi-market/correlated portfolio episodes; empirically calibrated queue
  competition, matching/chain settlement uncertainty, unmatched-leg rescue, complete-set
  merge/conversion state machines and pUSD adapter/operational-cost verification.
- Long continuous historical datasets, streaming gap repair and accurate hypothetical
  fill reconstruction. Current real-data demonstrations are bounded REST captures.
- Comprehensive distributed/infrastructure emulation, simulated SQL/process-failure
  orchestration inside campaigns and automatic incomplete-recovery mutation. Existing
  physical broker/database crash regressions remain; PostgreSQL runtime remains skipped.
- Automated multi-value fee/latency/liquidity sweeps, specialized sensitivity plots,
  market-type/lifetime analytics and a full continuous portfolio equity benchmark.
  Current distributions and replay equity are real outputs; episode curves do not compound.
- Automatic strategy-versus-simulator causal triage, code-generated regression tests,
  manual incident resolution/before-after fix management and source snapshot archiving.
  Original/minimized artifacts remain available and are never auto-resolved on a pass.
- Automatic mid-episode campaign persistence, journal compaction/cross-version migration,
  million-episode empirical resource evidence and Windows/distributed execution support.
- Costs affect analytical episode results rather than ongoing broker admission or ledger
  cash. Collateral/fiat parity and model uncertainty therefore block economic verification.
- Formal Gymnasium/custom order-action adapters; observations/transitions/reset/reward
  boundaries are prepared, but no neural-network training was implemented.

These limits prevent a claim of complete fulfillment of all Directive 003 breadth or
real-world strategy feasibility. The delivered system can now execute, compare, interrupt,
inspect, minimize and reproducibly explain substantial simulated research campaigns
using the actual Midas strategy/risk/accounting implementation.
