# MIDAS — PROJECT PROMETHEUS engineering log

Started 2026-10-12. This is a living report, not a declaration that the full
directive is complete. All research is generated, hypothetical, economically
unverified and paper only.

## Safety gate

- Clean initial worktree at `ebbb39c`; both existing user services active.
- API health READY, verified paper checkpoint startup, exclusive Laboratory lease
  held by the API. No competing Laboratory writer was created.
- Read-only SQLite quick_check returned `ok`. Protected campaign
  `07edb15a09a541dcb090a3b566e209d7`: 162000 passing variants, 18000 episode
  groups, nine variants per group, zero incomplete groups.
- Initial logical SHA256 over ordered `(idx,variant,id,result)` JSON rows:
  `70d446f0a3833011bb150b0212c4cad3f2751c7f1c210d4c6989816d249fe4ec`.
- Recovery backups were not modified. Campaign results were not rerun.
- Measured host: six logical CPUs, 15893 MiB RAM, approximately 10885 MiB
  available, zero swap used, 212 GiB free disk. Arena workers use CPU only,
  one heavy job at a time, CPUQuota 100%, MemoryMax 4 GiB, Nice 10, explicit
  wall budgets and a 2 GiB available-memory floor. User lingering is enabled.

## Implemented core

- Isolated `data/arena` artifact tree; atomic writes and content checksums.
- Decision-time allowlisted features, generator provenance, frozen hash-based
  episode partitions, first risk-admitted proposal completion labels, resumable
  per-episode dataset construction. IDs, family names, seeds, future venue books,
  future events and settlement answers never enter the feature vector.
- Training-only standardization; constant, documented assumption heuristic,
  logistic regression, depth-limited tree and genuine two-hidden-layer PyTorch
  MLP. Validation selection, early stopping, JSON weights, actual loss curves,
  reliability bins, Brier/log loss/precision/recall/PR-AUC, episode-grouped
  bootstrap intervals and scenario/execution breakdowns.
- MLP checkpoints now preserve optimizer and RNG state. Controlled interruption
  and exact resumption are regression-tested. Older initial checkpoints lack the
  new optimizer metadata and are not advertised as exactly resumable.
- Gymnasium environment controls production broker decisions while retaining
  the existing Laboratory event clock, matching, fees, settlement and independent
  accounting. Abstain, full-size and half-size actions; independent hard risk
  admission. No hedge/unwind action yet.
- Stable-Baselines3 PPO on CPU; atomic zip checkpoints, real episode curves and
  CSV entropy/value/loss diagnostics. Deterministic serialization verified.
  Exact mid-rollout PPO continuation is not implemented.
- Frozen-test tournaments with deterministic/conservative/no-trade/random
  controls and learned policies. All strategies share scenario inputs, capital,
  risk and execution assumptions. Bootstrap groups all execution variants by
  base episode. Ranking penalizes 5% tail loss; no champion is manufactured.
- Saved full event replays with observations, decisions, orders, ledger and
  portfolio evolution. Lossless gzip compression preserves evidence.
- Supervised systemd job processes, cancellation, persisted progress, resource
  limits, supervisor-based interruption detection and source-bound admission.
  New jobs preserve a source snapshot. Source changes while queued require a new
  job; a stale process cannot be described as executing the current revision.
- Arena API and React views: overview, training console, model registry,
  competitions/replay and persisted findings. Optional ML libraries are not
  imported during API startup. Original application workflows remain intact.

Laboratory hashes now exclude Arena modules, whose code cannot affect a
Laboratory run. Arena has its own research hash. The protected campaign was
already recorded under an older source hash than the clean starting revision;
this change does not claim to reconstruct that historical source automatically.

## Executed research checkpoint

Dataset `dataset-38ec6e9776097d8e36693372`: 1000 generated base episodes,
three execution variants, seed 42070, six families, observation latency 100 ms.
Only mathematically eligible, risk-admitted first proposals receive labels.
The dataset manifest records exact eligible counts and frozen partitions.

| Family | Model | Validation Brier | Frozen-test Brier |
| --- | --- | ---: | ---: |
| Constant | model-ff1c8c8a580944778d3eb7c0 | 0.23730 | 0.24754 |
| Assumption heuristic | model-3b9a496d6fad468ba791c1b4 | 0.09889 | 0.12566 |
| Logistic | model-3141334b301947499b59913d | 0.03154 | 0.01946 |
| Tree | model-f51ed0dcc4094f2d9cbae2f2 | 0.03207 | 0.01831 |
| PyTorch MLP | model-f587b98d06f34441bb040877 | 0.02896 | 0.01915 |
| PPO | model-33cddb0d92024c2bb0a3b34a | Policy evaluated in tournament | Policy evaluated in tournament |

PPO trained for 4096 transitions across 1780 completed training episodes in
113.9 seconds, with independent policy evaluation afterward.
All classifiers were configured before their frozen tests were opened; test
numbers do not drive automatic hyperparameter selection.

First tournament `tournament-8129ac44cebf4c198b5e3a97`: 100 held-out base
episodes, 2100 correlated variants, seven policies, three execution assumptions,
zero invariant failures.

| Policy | Mean virtual P&L | 5% tail loss | Mean minus tail loss |
| --- | ---: | ---: | ---: |
| No trade | 0 | 0 | 0 |
| Logistic gate | 1.2801 | 1.4664 | -0.1863 |
| Neural gate | 1.2801 | 1.4664 | -0.1863 |
| PPO | 1.6838 | 2.5824 | -0.8986 |
| Random control | 0.9938 | 2.2088 | -1.2150 |
| Conservative sizing | 1.2882 | 3.0063 | -1.7182 |
| Full-size arbitrage | 1.5341 | 4.4363 | -2.9022 |

No candidate clears the configured downside objective. PPO has the highest
synthetic mean, and classifier gates reduce sampled tail loss, but neither
finding establishes real execution quality or profitability. The generator's
seed-parity settlement and fixed family ordering are potential shortcuts that
need distribution-shift investigation.

## Validation checkpoints

- Before changes: 233 Python passed, one PostgreSQL skip.
- Latest full integration gate: 258 Python passed, zero failed, one PostgreSQL
  skip, existing Starlette deprecation warning (99.36 seconds). Compression and
  exact optimizer/RNG resumption are included in this count.
- Frontend: four unit tests passed; TypeScript, ESLint and production build pass.
- Browser: all five workflows passed, including actual dataset generation,
  neural training, frozen-test evaluation, competition and replay in a separate
  temporary artifact root. Earlier selector timeout was corrected and rerun.
- Python lint passes; strict mypy passes for 51 source files. Startup verifier
  locals were clarified and malformed identity/checksum types explicitly reject.
- Build retains an ECharts chunk-size advisory; charts load on demand.

## Current limitations and next acceptance gates

1. API routes deployed via the existing service. Health READY, paper checkpoint
   verified with 7836 journal events, six models and one tournament served, Vite
   HTTP 200. Protected campaign logical hash is unchanged; SQLite and writer lease
   rechecks pass. See PROMETHEUS_RUNTIME_EVIDENCE.json and PROMETHEUS_SAFETY_GATE.json.
2. Run the adversarial tournament against the finalized committed source. An earlier queued
   stress job was intentionally cancelled during development; partial artifacts
   remain and do not count as a completed campaign.
3. Live checkpoint curves, bounded admission (eight outstanding jobs), source
   snapshots and worker-log links are now implemented. PPO evaluation status,
   distribution/drawdown charts, human-readable balances and paired confidence
   tables are implemented. Dedicated pause/reboot resumption needs further work.
4. Add dataset-quality and recovered-campaign grouping audits, recorded-data
   catalog limitations, permutation/threshold analysis and distribution shifts.
5. Add bounded validation-only multi-seed search and an auditable research
   director. No autonomous model-selection loop has been implemented yet.
6. Investigate opportunity persistence, unmatched-risk severity, execution cost,
   recovery sizing, hedge/unwind research and economic sensitivity. Completion
   prediction alone does not fulfill all these scientific tasks.
7. Produce the morning briefing, final artifact inventory and reproducible
   experiment bundle. Initial runs retain hashes/configuration/weights/data;
   source snapshots were added after those first runs, so older dirty-source
   reconstruction is a stated limitation.

## Operations

Install CPU dependencies with:

```bash
.venv/bin/pip install torch==2.8.0+cpu --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements-arena.txt
```

Job state: `data/arena/jobs/JOB_ID/job.json`. Checkpoints:
`data/arena/models/MODEL_ID/`. All budgets and result references are in the job
record. View progress at `/api/arena/jobs/JOB_ID` or in Training console.

```bash
journalctl --user -u midas-arena-JOB_ID.service -f
curl -X POST http://127.0.0.1:8000/api/arena/jobs/JOB_ID/cancel
systemctl --user stop midas-arena-JOB_ID.service
```

Cancellation is cooperative at episode/epoch/checkpoint boundaries. A SIGKILL,
reboot or supervisor wall expiry is reported as interrupted rather than complete.
Job supervision is independent of API restarts. Existing `midas-api.service` and
`midas-web.service` retain their ownership and logging arrangements.

Upstream interfaces: [Gymnasium environment contract](https://gymnasium.farama.org/api/env/),
[Stable-Baselines3 PPO](https://stable-baselines3.readthedocs.io/en/v2.7.0/modules/ppo.html).

## Data Foundry and adversarial follow-up

The initial dataset has **1593 labeled variants from 531 eligible independent base
identities**, out of 1000 generated episodes. Six features are constant in these
initial states. Identical observable vectors cross partitions, and fixed family
order ties some families to one seed parity. Partition identities are correctly
grouped, but this does not establish realistic covariate diversity or generalization.
`PROMETHEUS_DATA_FOUNDRY_AUDIT.json` saves feature distributions, correlations,
label balance, duplicate/ambiguity diagnostics, shift checks and a read-only audit
of all 162000 protected records. All deterministic variant identities, seeds,
group coverage and the original logical hash pass. Compact old outcomes lack
safe decision features and are not imported as training features.

Stress job `job-2c71ea452f7c46cfae0ba7aa` stopped after 315 of 2100 variants because
an adversarial timing mutation delivered a snapshot with an exchange timestamp
later than the decision. This is an incomplete, failed research job; it does not
count as a completed stress evaluation. Its partial replays and source snapshot
are retained. The original extractor rejected the evidence, protecting leakage.

The Arena decision boundary now deterministically abstains on that evidence,
provides zero sentinel features and logs the validation reason. Regression
coverage proves it submits no orders and grants no future prices to the policy.
This strict policy observation guard is stronger than the legacy Laboratory's
one-second source-clock tolerance; all Arena competitors receive the same guard.
Laboratory fill, fee, settlement and accounting logic remains unchanged. A new
stress study must complete before robustness claims are made.

The replacement stress job `job-6b59348cd5af4d948dc13a6b` completed as
`tournament-6b260f31fe474f50821308c3`: 100 base identities, 2100 variants,
zero invariant failures. All replay/result links, complete group coverage and
frozen row hashes passed verification. Logistic and MLP gates tied at mean P&L
0.8632 with zero sampled 5% tail loss. Their advantage is confined to this
synthetic stress suite; the ordinary held-out study still rejects all trading
candidates under the downside objective. No broad or real-market champion is
supported. Future ranking should explicitly preserve ties instead of choosing a
representative model by ID. No Arena research unit remained running at this
checkpoint.

## Reproducibility and visibility checkpoint

The saved-action replay verifier reproduced the ordinary tournament's worst
outcome, -10.106200 virtual USD, with exactly matching financial result and
journal hashes. `PROMETHEUS_REPLAY_VERIFICATION.json` records this bounded
verification. It replays saved actions and accounting; it does not claim to
retrain models or rerun policy inference.

```bash
.venv/bin/python scripts/arena_reproduce.py \
  --tournament tournament-8129ac44cebf4c198b5e3a97 \
  --row 109-optimistic-arbitrage
```

New replays now retain actual classifier scores, thresholds and policy-specific
explanations. New worker processes return OS exit codes matching their persisted
outcomes. Orphaned/interrupted model checkpoints are not presented as active
training. Model weights, quality diagnostics and verified public-source coverage
are accessible through the interface. Focused environment/tournament/job checks
passed 13 tests after the last full 258-pass gate; the replay verifier's two
focused tests also passed.

The supervised dataset labels only initial proposals. Constant portfolio features
in this dataset do not establish calibration in later portfolio states. Future
work must add support warnings or broaden state coverage before making claims
about those predictions. The paper ledger exposes fills immediately on matching;
delayed private fill notifications are not separately modeled. See RISK_MODEL.md
for admission limits, stop thresholds and the absence of guaranteed loss bounds.

| Milestone | Current status |
| --- | --- |
| Safety/reliability preservation | Verified; protected archive unchanged |
| Core datasets and supervised prediction | Working and trained; completion target only |
| Gymnasium/PPO | Working and trained; limited actions/observation assumptions |
| Matched and adversarial comparisons | Two completed studies with preserved evidence |
| Arena interface and durable jobs | Working; cancellation/interruption/CPU budgets verified |
| Data Foundry | Quality/grouping audits and public-source catalog; broader ingestion partial |
| Evolution Laboratory | Not started |
| Research Director | Not started |
| Interpretability | Calibration/traces/diagnostics partial; permutation/threshold studies pending |
| Recovery policies and sensitivity suite | Not started in Arena |

Next priorities are explicit tie handling, supported inference/state coverage,
seed/family shifts, validation-only multi-seed search, and bounded auditable
research orchestration. The full goal remains active.
