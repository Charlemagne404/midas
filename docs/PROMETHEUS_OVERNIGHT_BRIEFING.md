# MIDAS — PROMETHEUS OVERNIGHT BRIEFING

This briefing records an ongoing development checkpoint. The full Prometheus
directive remains active; completion of the initial Arena is not completion of
the whole research backlog.

Open **Arena** in Midas. The deployed interface contains real dataset provenance,
model weights and curves, supervised systemd jobs, classifier calibration,
matched competitions, risk-aware rankings, saved event replays and findings.

## What is available

- One frozen generated dataset: 1000 generated episodes, 531 eligible base
  identities and 1593 correlated execution variants, with episode-safe splits.
- Five fitted predictors/policies: base-rate constant, logistic regression,
  decision tree, PyTorch MLP and PPO. A separate fixed assumption heuristic is
  retained as a control, not presented as learned intelligence.
- The MLP ran 80 real epochs. PPO ran 4096 transitions across 1780 completed
  episodes. Model IDs, settings, durations, hashes and evaluations are in
  `PROMETHEUS_RESEARCH_INVENTORY.json` and `data/arena/models/`.
- The first independent competition evaluated seven policies under three
  execution assumptions over 100 matched base episodes: 2100 correlated results.
  All passed independent accounting/invariant checks.
- Replays preserve observations, decisions, orders, fills, portfolio balances,
  realized/unrealized virtual P&L and terminal outcomes. Lossless gzip reduces
  artifact size without discarding evidence.

## What the evidence says

The neural classifier's frozen-test Brier score is 0.0192, compared with 0.2475
for the base-rate predictor. Tree and logistic models are similarly competitive.
These predict completion under the simulator's assumptions; this is not evidence
about real fill probabilities.

PPO had the highest mean virtual P&L in the first tournament. The classifier
gates reduced sampled tail losses compared with full-size arbitrage. **No trading
candidate cleared the configured mean-minus-tail-loss objective against no-trade.**
The Arena therefore declared no research champion.

Dataset quality analysis found 81 groups of identical observable vectors crossing
partitions and 11 ambiguous vectors with different completion labels. Grouped
partitioning works, but repeated synthetic quote grids and family/settlement
seed-parity shortcuts limit generalization claims. Shifted distributions and
validation-only model selection should be investigated next.

Two public datasets are available, each containing three events at one receipt
time. These are bounded REST captures, not chronological training history. There
are no empirically observed execution labels, so no model is called calibrated
to real execution.

## Operational evidence

The existing API was restarted through its original systemd service and reports
READY. Paper recovery verified 7836 journal events at that checkpoint. Dashboard
HTTP status is 200, and direct browser inspection found no page errors. The
protected 18000-episode/162000-variant campaign retained its original logical
hash, valid SQLite state and exclusive API writer lease. Protected backups were
not changed.

Latest full Python gate: **258 passed, zero failed, one PostgreSQL skip**, 99.36
seconds. Frontend unit gate: four passed. Full browser checkpoint: five passed;
the Arena workflow was subsequently rerun after interface updates and passed.
Strict Python typing, lint, TypeScript and production build pass. Existing
Starlette deprecation and ECharts chunk-size advisories remain.

## Active research and failures

The first stress attempt stopped after 315 variants when an adversarial mutation
delivered a future timestamp. It is a failed, incomplete job, with preserved
partial replays and source evidence. No partial leaderboard was published.

The feature guard now abstains on such evidence, supplies zero sentinel features
and logs the reason. A regression proves that no future price enters a policy
vector and no order is submitted. This guard is shared by all Arena policies.

Replacement stress job (COMPLETED; no research worker remains active):

- ID: `job-6b59348cd5af4d948dc13a6b`.
- Unit: `midas-arena-job-6b59348cd5af4d948dc13a6b.service`.
- Purpose: 100 held-out base episodes, seven policies, three execution assumptions
  with timing, liquidity, cancellation and acknowledgment stress mutations.
- Budget: one CPU core, MemoryMax 4 GiB, 1800 seconds, 1 GiB Arena artifact budget,
  stop under less than 2 GiB available host memory. All new replays are compressed.
- Progress: `data/arena/jobs/job-6b59348cd5af4d948dc13a6b/job.json` or Training console.
- Logs: `journalctl --user -u midas-arena-job-6b59348cd5af4d948dc13a6b.service -f`.
- Checkpoints: existing immutable model directories; evaluation replays go under
  `data/arena/tournaments/`. The result reference is published on completion.
- Stop: use Training console's Cancel action, or POST
  `/api/arena/jobs/job-6b59348cd5af4d948dc13a6b/cancel`.

The replacement completed all 2100 variants over 100 independent base identities,
with zero invariant failures. Every compressed replay, result link and frozen row
hash was verified. Artifact: `tournament-6b260f31fe474f50821308c3`.

The logistic and neural gates tied at mean virtual P&L 0.8632 with zero sampled
5% tail loss in this stress suite. PPO scored -0.0270 and full-size arbitrage
-0.0358 under the same downside objective. The gate advantage is confined to
this synthetic stress sample, and the classifiers tied; this does not establish
a unique best model, a broad champion or real profitability.

## Continuation queue

1. Stress coverage and replay verification are complete. Preserve both completed
   tournaments and the failed prerequisite study. Add explicit tie handling to
   future champion selection; the two learned gates have identical stress scores.
2. Data Foundry diagnostics and verified recorded-source limitations are now
   surfaced. Add supported-inference warnings for constant portfolio features and
   investigate seed/family shifts before blindly increasing model size.
3. Implement bounded multi-seed, validation-only model search with preserved
   lineage and unsuccessful trials. Protect final tests from adaptive selection.
4. Add a rule-based, resource-bounded research director with durable plans and
   meaningful follow-up criteria. Preserve every negative result.
5. Investigate shifted family order/settlement rules, execution-risk sizing,
   unmatched recovery, permutation/threshold diagnostics and economic sensitivity.
6. Expand chronological public observations only through the existing read-only,
   bounded infrastructure. Do not invent execution or historical labels.

Source checkpoints: `ea7c8e5` (working Arena), `9fb7525` (Data Foundry audit and
strict timestamp guard). The living engineering report describes remaining
features, source reconstruction limits and reproduction/operations commands.

## Latest active job and exact resume point

A third comparison is running after the two completed studies:
`job-df4f313087794f65a01968a7`, supervised by
`midas-arena-job-df4f313087794f65a01968a7.service`.
It includes all six registered model artifacts plus four deterministic/diagnostic
controls over 100 frozen test groups and three execution assumptions: 3000
correlated variants. Its limits are one CPU core, 4 GiB, 1800 seconds and the
existing disk/memory-pressure controls. Latest verified snapshot was 2380/3000,
PID 2647514, approximately 356 MiB current cgroup memory. This is an observation
snapshot, not a promise that the job remains active later.

Progress and supervisor evidence are in `PROMETHEUS_ACTIVE_JOB.json` and
`data/arena/jobs/job-df4f313087794f65a01968a7/job.json`. Logs:

```bash
journalctl --user -u midas-arena-job-df4f313087794f65a01968a7.service -f
```

Stop through Training console or POST
`/api/arena/jobs/job-df4f313087794f65a01968a7/cancel`.
The job stops after 3000 results, its wall budget, a resource gate, or cancellation.
Its replay files are durable; its tournament manifest is published only when the
whole comparison finishes. Existing trained weights are reused, not retrained.

On continuation, inspect this exact unit and job before initiating more research.
Verify terminal coverage and the result reference when complete; preserve any
interruption/failed partial artifacts. Then implement tie-aware rankings and
supported-input warnings, followed by fresh seed/family-shift challenges,
validation-only multi-seed search and an auditable research director.

Source `83aaa54` adds the quality/source interface and saved-action accounting
reproducer. Subsequent source work also prevents duplicate runners from writing
the same job and ensures OS exit status matches the persisted outcome. No
coordinator has been given permission to modify the protected Laboratory archive.

## Latest terminal audit

The all-artifact job completed as `tournament-f65083253fc7440d83f66bf0`.
All 3000 core-result hashes, journal hashes, passing invariants and 100 complete
groups were verified. The tree, logistic and neural gates produced identical
policy outcomes. The fixed base-rate filter abstained; no-trade remained best
under the ordinary downside objective. There is no supported neural decision
advantage over the simpler classifiers in this sample.

There are now **three completed tournaments / 7200 correlated variant results**.
All reuse the same 100 underlying held-out identities; this is not 300 independent
market samples. The stress suite has altered event conditions. No research worker
remains active; the formerly active job section above is historical and its JSON
record now reports COMPLETED. The ordinary suite still supports no broad champion.

The next turn should read the current worktree and engineering report, then
implement tie-aware selection and supported-input diagnostics. Preserve existing
results. Use fresh episode identities and family/seed shifts for the next
independent challenge, then implement validation-only multi-seed selection and a
bounded research director. The full goal is still active.
