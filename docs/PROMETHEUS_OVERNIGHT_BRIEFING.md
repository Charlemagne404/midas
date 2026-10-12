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
