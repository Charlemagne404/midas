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
- Latest full integration gate: 255 Python passed, zero failed, one PostgreSQL
  skip, existing Starlette deprecation warning (94.14 seconds). Compression and
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
