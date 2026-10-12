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

The all-artifact comparison is now supervised as
`job-df4f313087794f65a01968a7` (3000 variants, 100 matched groups). Its inspected
handle was active at 2380/3000 and 356 MiB. `PROMETHEUS_ACTIVE_JOB.json` records
the exact observation. A per-job execution lease now prevents duplicate runners
from updating the same job; all four job reliability tests pass. Remaining
source changes after the last full gate are targeted by the relevant focused
checks. The original goal remains active and the continuation queue is in the
morning briefing.

Terminal audit: the all-artifact job completed as
`tournament-f65083253fc7440d83f66bf0`. All 3000 financial core hashes, journal
hashes, passing results and complete 100-group coverage were verified. Tree,
logistic and MLP policies tie exactly in ordinary policy outcomes. Across three
studies there are 7200 variants over the same 100 held-out identities, not 300
independent samples. No research worker remains running. Further neural
complexity is not supported by a demonstrated decision benefit in this sample.
The continuation priorities remain active.

## Evolution and director implementation checkpoint

New comparisons preserve ties and require complete matched episode/execution
coverage. Paired differences use actual control outcomes. Existing tournament
manifests are immutable. New ranking version `episode-objective-ties-2` reports
joint leaders and leaves the unique champion unset when scores tie.

Predictors now expose training-only feature envelopes. Legacy weights stay
unchanged; their envelopes are derived from verified frozen training rows. New
evaluations explicitly choose warning-only or abstention behavior outside those
ranges. Support coverage does not establish joint calibration. Every affected
replay records the support result and reason.

`evolution.py` preregisters two or more training seeds and bounded candidates.
Selection uses mean validation Brier, a fixed practical tolerance and a declared
simplicity preference. Test metrics are neither read by selection nor opened for
new candidate classification. Trials, including unselected models, remain saved.
Completed trials and a completed sweep are reused on recovery.

`director.py` runs exactly three predefined stages: validation-only selection,
fresh-seed/reordered-family warning evaluation, and matched support-abstention
evaluation. Challenge seeds cannot overlap the original dataset, even under a
changed family name. Final challenge outcomes cannot change fitted parameters
or thresholds. A durable plan links each real artifact, with user-visible stage
progress and the existing supervised CPU/memory/wall budgets.

Validation at this checkpoint: 11 focused evolution/selection/job tests passed
(including a real four-fit sweep and two 30-case challenge studies); 14 focused
foundations/selection/tournament tests passed; the Arena browser workflow passed.
Full regression validation and the first bounded real director campaign are the
next gates. The protected Laboratory archive remains outside all new writers.

## Completed fresh-scenario director and scientific bundle

Director `director-84332caaae9c280e078a799b`, supervised job
`job-605cdb0175c34a34bca7feff`, completed in 1028.93 seconds with exit status 0.
Its four validation-only fits used two seeds each for logistic and MLP. Neural
mean validation Brier was 0.02922065 versus logistic 0.03153976; the difference
exceeded the preregistered 0.002 practical tolerance. Representative neural model
`model-fe2d275e53ae4295adf5ab1f` was selected. New classification test metrics
remain unopened; selection never used them.

The two matched fresh challenges saved 2400 variants each over the SAME 100 new
base identities. These identities do not overlap the original training dataset.
The family order was changed to investigate the generator's seed/settlement
shortcut. Warning tournament `tournament-6bfc67591b6d437085ded3b9` and abstention
tournament `tournament-5ec7656a30614fd49d78f1cd` both found no downside-objective
advantage over no-trade. Three classifier gates tied exactly: mean virtual P&L
1.35026333, 5% tail loss 1.36586667, score -0.01560333. PPO scored -1.95621567.
The neural validation gain did not improve policy P&L in this challenge.

Warning versus abstention produced zero P&L differences for every paired policy
variant. Each classifier encountered 19 unsupported decisions. Warning-mode
logistic requested 19 trades, incumbent MLP 7, selected MLP 8 on those inputs;
EVERY request was independently rejected by production risk admission, including
existing-position/reconciliation rules. The unchanged outcomes are therefore
not evidence that unsupported inference is harmless. Legitimate classifier
losses originated from in-range initial features. Range support alone cannot
establish calibrated completion risk. `PROMETHEUS_SUPPORT_COMPARISON.json` and
`PROMETHEUS_FRESH_CHALLENGE_ANALYSIS.json` preserve the comparisons and loss cases.

Read-only full audit verified one frozen dataset, ten model weight artifacts and
all 12,000 completed replay variants across five tournaments. The first three
reuse 100 original held-out identities; the last two reuse 100 fresh identities.
Do not count these studies as 500 independent episode groups. Accounting and
journal hashes and matched coverage passed. The recovered Laboratory logical
hash remains `70d446f0a3833011bb150b0212c4cad3f2751c7f1c210d4c6989816d249fe4ec`;
SQLite quick_check is OK and the API still owns its exclusive writer lease.

`scripts/arena_bundle.py` exported the completed plan, four fitted candidates,
three incumbent models, frozen dataset, both challenge replays and captured job
source to `/home/charlie/midas-prometheus-bundles/director-84332caaae9c280e078a799b.tar.gz`.
All 4887 manifest entries passed byte-hash verification. The bundle SHA256 is
`25bdb83c8bd8778839e6e99b683dabde46ae079f9c66ddd9c2102d84355e4adb`.
This is an evidence export, not a claim of clean-machine training reproduction.
Legacy incumbent training source snapshots remain unavailable. Export refuses
replacement, including concurrent publication. Two utility regressions pass.
The prior complete code gate at `17e3adb` was 266 passed / one PostgreSQL skip;
frontend four tests, typecheck, lint and build passed.

## Validation diagnostics implementation

A supervised diagnostic job now computes ten repeated feature permutations with
consistent donor episodes across execution variants. It averages losses within
base episodes before bootstrap confidence estimates. Only validation rows enter
calculations; final test labels are excluded. Saved reports bind frozen dataset
and model hashes and source version, preserve false-completion/missed-completion
cases and a fixed descriptive threshold table, and are reused without rewriting
when provenance matches. Different provenance is rejected. Permutations may
create impossible states among correlated features; predictive dependence does
not prove causality or economic decision value. The model page shows actual
saved reports and exposes their download. New full-suite/browser gates and real
registered-model diagnostic jobs are pending below.

Diagnostics gate: full Python regression **272 passed / one PostgreSQL skip**,
214.22 seconds, one Starlette deprecation warning; four frontend unit tests pass;
TypeScript, ESLint, build, Ruff and strict mypy (59 source files) pass. The updated
browser workflow passed in 53.8 seconds, including a genuine supervised fit,
diagnostic job, model evidence display, independent evaluation and replay.
The lazy ECharts chunk remains 544 KiB and triggers the existing build advisory.
An extracted director bundle's captured source independently replayed the
preserved partial-leg case with exactly matching financial/journal hashes.

Registered-model execution: logistic diagnostic
`job-68d9ecc1d8934a789cb56985` completed in 4.22 seconds; selected-neural diagnostic
`job-e0a34b52cb934607a16d0609` completed in 8.72 seconds. Both exited 0 and reached
19/19 feature stages. The model endpoint displays their hash-bound persisted
reports. Each uses the same 69 validation groups / 207 execution variants and
has six false-completion predictions plus one missed completion at threshold
0.5. The three depth features dominate permutation sensitivity. Some volatile,
disappearing and one-sided failures receive completion scores near 0.89–0.91;
no confidence threshold is selected from this observation. Constant age/latency
coverage prevents inference about broader latency regimes. Saved evidence is in
`PROMETHEUS_VALIDATION_DIAGNOSTICS.json`; full lineage is in each job source
snapshot and `PROMETHEUS_DIAGNOSTIC_JOBS.json`.

Deployment after `0cfc9e2`: API verified READY after snapshot startup over 20,704
paper journal events; web service active. No research jobs remain running.
Runtime/model inventory evidence has been refreshed. The full goal is active.
Next implement validation-only matched policy sizing/rejection selection or
unmatched-exposure targets, then evaluate on a preregistered genuinely new seed
set. Do not tune against the opened fresh challenge. Recovery actions and wider
economic sensitivity remain higher-value unfinished research branches.

## Residual unmatched-inventory target

The next target uses the initial proposal's exchange ledger to sum acquired
shares on each leg. A positive label means unequal acquired quantities after
all initial fills, before settlement. Zero fills and equally sized partial fills
are negative labels even when full completion is false. Residual quantity is
saved in shares as outcome metadata, never fed back into decision-time features.
It is not a predicted dollar-loss severity or a guarantee about settlement.

Dataset specifications and manifests record the target and label version.
Model parameters/manifests record the target and reject inconsistent metadata.
Legacy artifacts default to completion without modification. Unmatched-risk
predictors accept a proposal only when predicted risk is <= the configured
maximum; completion predictors retain their >= minimum-completion rule. Every
proposal still passes independent production risk admission. The fixed completion
heuristic is rejected for unmatched labels rather than given an invented meaning.
Replay explanations explicitly distinguish completion scores and unmatched risk.

The UI exposes the prediction target during dataset creation, identifies model
and dataset targets, and explains the reversed probability gate. Diagnostics now
use target-specific errors and generic positive/negative counts while preserving
old saved report display. New unit cases cover zero fills, matched partial fills,
one-leg fills, unequal partial fills, unchanged observations across target choice,
gate direction, a real unmatched logistic fit and a matched tournament.

Focused validation: **17 passed** in 42.55 seconds. An earlier concurrent source
edit invalidated the source-derived dataset identity during its reuse test
(16 passed / one failed); the frozen-source rerun passed. This was a test-run
coordination failure, not weakened artifact identity logic. Source remains frozen
through the full gates and upcoming supervised campaign.

`PROMETHEUS_UNMATCHED_PREREGISTRATION.json` fixes the next experiment before
execution: 1001 fresh generated episodes starting seed 62070, seven scenario
families (rotating seed parity), two-seed logistic/MLP selection on validation,
then warning and abstention challenges on the same 100 new identities starting
73071. The threshold stays 0.5; no final-challenge retuning is permitted. Low
unmatched risk is not evidence of profitable execution. Comparing risk targets
against legacy completion models trained on a different frozen dataset remains
separate unfinished work.

Target gate: full Python regression **278 passed / one PostgreSQL skip** in
223.01 seconds (one Starlette deprecation warning). Four frontend tests, build,
Ruff and strict mypy (59 files) pass. The browser target workflow initially
failed to resolve the new selector's label; explicit `aria-label` fixed it.
The rerun passed in 50.8 seconds, exercising unmatched dataset generation, real
neural training, target-aware diagnostics, independent evaluation and replay.
The final UI source also passes TypeScript/ESLint. Legacy frozen dataset/model
and all five tournament row hashes still verify under the new readers.

Bundle v2 exports now reject changed referenced dataset rows, model weights,
tournament rows and captured source; they include the core package specification,
verification/comparison tools and reproducibility instructions. Existing external
bundles remain immutable. Two utility regression tests pass after this change.

### Sampling-scope correction before training

Attribution of the three earlier fresh-challenge classifier losses reproduced
20.4, 14 and 19 unmatched YES shares. The latter two volatile cases began at the
SECOND decision. The existing initial-decision sampler returned no row for them.
This was a documented coverage limitation, but retaining it for the new risk
question would exclude relevant states. No final test was used to fit parameters.

Stopped dataset job `job-76d27de1b74f4ccd9d6b278d` at 384/1001. The supervised
handle is terminal (MainPID 0); persisted state is CANCELLED / exit status 130.
Partial episode checkpoints remain retained and no complete manifest was
published. The original preregistration and terminal cancellation record are
preserved separately.

New `decision_scope=first_admitted` advances the actual event simulator through
rejected/ineligible decisions until the first proposal admitted by production
risk rules. It extracts observations before that proposal, with no preceding
acquired inventory, and labels only that proposal's fills. Decision ordinals and
scope are persisted; scope and target must match frozen manifest/spec/rows.
Legacy initial-decision datasets remain readable and unchanged. The UI uses this
scope for newly requested unmatched datasets and explains it. Later portfolio
states still require separate data; the correction does not claim comprehensive
state coverage.

Seven focused target tests pass, including the later volatile loss case and
zero prior capital lockup. The revised campaign preregistration is recorded
before training or new challenge execution; its amendment documents why the
initial build was cancelled. Full source remains frozen through validation and
subsequent jobs.

The amended first-admitted browser workflow passed (53.7 seconds); frontend
build/lint pass. Protected archive digest, SQLite quick_check and exclusive writer
ownership were reverified unchanged. Bundle v2 was exported independently at
`/home/charlie/midas-prometheus-bundles/director-84332caaae9c280e078a799b-v2.tar.gz`;
all 4893 entries verify, SHA256
`652bcffa65beb1e94a0c0d4a7fa5f81d01a6d3f09ac2ae4687e2b1e2d3f19bde`.
The original bundle is preserved. Full regression evidence for the scope
correction is pending below; no new training or challenge result is claimed yet.

Scope-correction gate: full Python regression **279 passed / one PostgreSQL skip**,
222.58 seconds, one existing Starlette warning. Source Ruff/mypy and frontend
build/lint pass; updated browser workflow passed. The first-admitted sampler is
ready for the amended bounded campaign. Source will remain frozen until its
supervised jobs finish.

## Active amended risk campaign — resumable handoff

Source `4cf3079` is frozen for supervised execution. Dataset job
`job-95a47ccd32b246a982cc722f` is producing
`dataset-f53981b7dd24c1521ce749b1`; the inspected systemd handle was ACTIVE with
MainPID 2986562, 174/1001 episodes, about 112 MiB memory. It stops at 1001 episodes
or a 900-second wall budget, cancellation, pressure failure or artifact cap.

Director job `job-a9f4533b62e14baf8b8bbb1c` has a verified ACTIVE queued handle
(MainPID 2987310, about 108 MiB), waiting for the same worker lease. It refers to
the deterministic planned dataset ID. If dataset publication fails, the director
must fail visibly; it cannot manufacture completed data. Its 3600-second wall
budget includes queue time. Once admitted it runs four validation-only fits and
two 100-group/three-execution challenges, fixed threshold 0.5, then terminates.
The two challenges share the same new identities and must not be counted as
200 independent groups. No final outcome can alter parameters or thresholds.

Both jobs use one serialized compute worker, CPUQuota 100%, per-unit MemoryMax
4 GiB, host available-memory floor 2 GiB and Arena artifact cap 1 GiB. Both
processes were confirmed live; no observation timeout was treated as completion.
API remains READY after snapshot verification and web remains active. Protected
archive logical digest and ownership were reverified unchanged earlier this turn.

Inspect progress in the Arena or these JSON artifacts:
`PROMETHEUS_UNMATCHED_DATASET_JOB.json`, `PROMETHEUS_UNMATCHED_DIRECTOR_JOB.json`.
Authoritative current records are in `data/arena/jobs/<job-id>/job.json`; logs are
`journalctl --user -u midas-arena-<job-id>.service`. Safe cancellation is available
in the Arena or POST `/api/arena/jobs/<job-id>/cancel`. If cancelling the upstream
build, also cancel the queued downstream plan. Partial checkpoints remain under
`data/arena/datasets`; supervised job source snapshots remain in each job folder.

Next turn: inspect BOTH exact supervisor handles and read authoritative records.
Do not change Arena Python source while the plan runs. After completion, verify
new dataset partitions/outcomes, all four weight artifacts, the selected model
and both complete tournament replays. Interpret risk-gate policy P&L and tails
against matched deterministic/no-trade controls; preserve negative findings.
Then export the completed plan and investigate supported next hypotheses.
Cross-target comparisons on the same frozen observations, severity/cost labels,
bounded recovery actions and broader economic sensitivity remain unfinished.
The full Prometheus goal is ACTIVE; this is not a completion claim.

## Fixed-path economic sensitivity and first risk results

Added `scripts/arena_economics.py`: verifies frozen row/replay financial and journal
hashes, reproduces the original nonzero-cost Laboratory accounting formula, then
applies 20 one-factor hypothetical cost points to unchanged actions/fills/capital
paths. Axes are extra virtual USD per fill, virtual USD per settled position,
annual financing fraction (365-day year), and retained collateral value.
Exchange fees remain embedded in original gross P&L. These additional charges
are not empirically observed fee schedules. No policy, risk admission, sizing,
execution delay or future model training changes in this analysis.

Confidence intervals group execution variants inside base episodes. The report
preserves tail loss, downside scores and a mean break-even extra cost per fill.
Mean break-even is not a downside margin or profitability guarantee. Financing
uses retained reserved-plus-locked capital time; short synthetic episodes cannot
represent prolonged real resolution delays. Source bytes are retained alongside
the saved report, and report/input digests are checked by its API endpoint.

The earlier warning challenge's classifier gate had mean P&L 1.35026333 but score
-0.01560333 with zero extra costs. An extra 0.25 virtual USD per fill reduces mean
to 1.15526333 and score to -0.39847; at 1.0 it reduces mean to 0.57026333 and score
to -2.99360333. Its fixed-path mean break-even charge is about 1.73111 USD/fill.
There was already no positive downside margin at zero. The interactive tournament
view shows the actual saved curves, assumptions and full report/interval link.

New gates: **283 Python tests passed / one PostgreSQL skip**, 220.49 seconds,
one existing Starlette warning. Seven focused economic/API tests passed, including
nonzero financing agreement, grouped uncertainty and tamper rejection. Strict
mypy covers 60 source files; Ruff, frontend build/lint and four frontend tests
pass. The updated browser workflow passed in 54.3 seconds, calculating a report
from real isolated tournament replays, displaying its chart and switching axes.
Arena Python source remains unchanged during the active director.

Risk dataset `dataset-f53981b7dd24c1521ce749b1` completed in 288.45 seconds:
1935 variants / 645 admitted base groups, including 87 groups admitted after the
first decision. Train/validation/test rows are 1392/297/246 (464/99/82 groups).
Labels and frozen partitions load with checksums; source remains matched to the
submitted snapshot. Four actual fits completed. MLP mean validation Brier
0.08931322 versus logistic 0.09132488 exceeds the 0.002 selection tolerance by
only 0.00001166. This selection-rule result does not establish scientific
superiority. Selected model is `model-131794f0434945a286163323`; new classification
final test metrics remain unopened.

Warning challenge `tournament-1543d15e04054c4eb4eab2e2` completed 1500 variants
on 100 new groups. The selected risk gate exactly ties deterministic arbitrage:
mean P&L 1.217566, tail loss 5.116, score -3.898434, worst loss -8.6. Conservative
score is -2.04887167; no-trade remains 0. No candidate demonstrates the declared
downside advantage. The matched abstention stage is still running; its results
must be verified separately before the plan is called complete.

## Terminal unmatched-risk campaign audit

Director `director-9e54849454cbf86fd4b85db0` completed all three stages under
`job-a9f4533b62e14baf8b8bbb1c`, exit status 0, recorded elapsed 1108.81 seconds
including worker-lease queue wait. Both supervisor handles are now terminal.
No research worker remains active. All four risk candidate weight hashes and
both frozen datasets load correctly. The read-only audit verified **all 15,000
completed replay variants across seven tournaments**, matching core hashes,
journals, stored rows, complete group coverage and valid accounting. Three
sets of 100 disjoint evaluation identities are reused within their respective
studies: do not count these as 700 independent episode groups.

Independently regenerated 50 source episode indices / 150 candidate execution
configurations from simulator inputs. All 102 retained labels and excluded cases
matched their saved per-episode checkpoints. Complete grouping/outcome metadata
was checked by dataset loading. This is a sampled regeneration, not a second
full 1001-episode run. `PROMETHEUS_UNMATCHED_LABEL_VERIFICATION.json` preserves
the exact selected indices and admitted counts.

The abstention challenge `tournament-c3ded1b0589d4beab52a9eba` also fails the
specified downside objective: risk gate mean 1.21749933, tail loss 5.116, score
-3.89850067; conservative score -2.04887167; no-trade score 0. Range abstention
changes just one of the risk gate's 300 matched variants, missing a +0.02 virtual
USD outcome. Group mean difference is -0.00006667, bootstrap interval
[-0.0002, 0]. Warning mode made 50 unsupported requests; 47 were rejected by
risk admission. The three allowed requests had conditional-edge values outside
training ranges in one thin episode; only its optimistic execution variant had
nonzero P&L. This bounded observation neither proves range guards unnecessary
nor demonstrates a universal adverse effect. `PROMETHEUS_UNMATCHED_SUPPORT_CASES.json`
and the paired comparison retain the evidence. No threshold or weights were
adapted after these challenges.

Exported the completed plan at
`/home/charlie/midas-prometheus-bundles/director-9e54849454cbf86fd4b85db0.tar.gz`.
All 3084 manifest entries verify; bundle SHA256
`42ca8b567410868a06348ff78e72a15430328af7f086fd9e5c73bc1062416c35`.
Both challenge directories include verified fixed-path economics reports and
producer source snapshots. This is an evidence export, not clean-machine
retraining. Existing external bundles remain unchanged.

Economic-overlay memory now retains five accounting totals per result instead
of full journals after verification. Publication captures producer source bytes
and uses an exclusive atomic link, refusing replacement even with concurrent
exporters. Seven focused economic/API tests pass after these utility changes;
Ruff/mypy pass. The full 283-test gate preceded this utility-only optimization.
The deployed API returns the saved economic report, and the actual dashboard
cost chart was inspected. Legend placement was adjusted to prevent overlap with
the numeric axis; final frontend build/lint pass. Runtime/model inventory and
terminal job records are refreshed. API is READY with snapshot verification;
protected archive digest, quick_check and exclusive ownership were reverified.

### Exact next work

1. Preregister a bounded validation-only comparison of risk thresholds and
   full/half sizing against no-trade, with explicit target direction and matched
   episode-group uncertainty. Optimize the declared economic objective on
   validation; no new decisions based on the opened seed-73071 challenge.
2. Evaluate the selected policy once on a genuinely new seed block after source
   gates. Preserve unsuccessful candidates and ties; a no-trade selection is
   a valid negative result. Record that full-size risk scores do not calibrate
   reduced-size execution unless that training data is generated separately.
3. Add severity/cost targets only from valid proposal-level accounting. Compare
   targets on the SAME frozen observations; legacy completion models currently
   use different datasets and cannot support a fair target comparison.
4. Recovery still requires execution/accounting support: the current simulated
   exchange implements buys/cancels and settlement, not bid-side sales. Do not
   fabricate unwind capability or assume a hedge completes. Extend the broker
   with separate invariants/ledger proofs before policy research.
5. Extend economic analysis from fixed paths to actually rerun fee/latency/depth/
   lockup variations, keeping market-specific unverified schedules explicit.
   The full Prometheus goal remains ACTIVE with these unfinished branches.

The verified negative result is also published in Arena Research Findings as
`finding-d2d512b111782b1a18173562`, with input row hashes, both tournament links,
plan lineage, uncertainty and the preregistered follow-up recommendation.
This synthesis does not promote or refit a model. The final deployed risk-plan
cost chart and terminal dashboard are captured in `arena-economic-sensitivity.png`.

## Validation-only threshold and sizing search implementation

Tournament specifications now accept up to twelve distinct hash-identified
supervised gates. Each gate binds one immutable model to a probability threshold
and full/half sizing. Weights are loaded once and remain unchanged. Gate IDs,
configs, underlying weight hashes, target direction and requested sizing are
preserved in rows/manifests/replay explanations. Half-size proposals use the
existing SizedStrategy and production risk admission. Scores still refer to
full proposals; reduced-size execution is not separately calibrated.

`policy_search.py` runs exactly two stages: a matched validation league, then a
single new-seed evaluation of the frozen selected policy. It permits one to
twelve predefined gates. Candidate eligibility requires no invariants, at least
30 validation groups, positive downside score versus no-trade and paired mean
bootstrap CI lower bound >0. Selection maximizes score; score ties prefer half
size then lower maximum risk. If none qualifies, it selects no-trade. Final test
outcomes cannot alter the gate or weights. Fresh seeds cannot overlap any frozen
dataset or registered completed/partial challenge range. Completed stages are
reused by recovery with config/source checks. Interrupted partial results cannot
be treated as completed tournaments.

Validation tournaments retain rankings/metrics but cannot designate an independent
research champion. API/model detail counts distinguish validation policy
comparisons from independent evaluations; a focused regression checks this.
Supervised search jobs retain owner identity, phase progress, source snapshots,
existing one-CPU worker lease, pressure/cancellation checks and wall/memory/disk
budgets. API catalogues and `/api/arena/searches/{id}` expose real artifacts.
The Research director tab can launch searches, show selected/no-trade decisions,
link both stages and open frozen specifications. Gate leaderboard rows identify
threshold/size and link the underlying model.

Focused engine/search/job gate: nine passed in 89.10 seconds, including a genuine
risk fit, four-gate validation league and fresh evaluation with immutable weights.
Additional tests cover source-seed exclusion and deterministic tie/uncertainty
selection. Full gate: **288 passed / one PostgreSQL skip** in 295.36 seconds, one
existing Starlette warning. Five API tests pass after the evaluation-count
projection change, including the newly added independence regression. Strict
mypy (61 source files) and Ruff pass. Frontend build/lint and four unit tests pass;
the prior Arena workflow passed. The expanded real-search browser test is still
running and remains an explicit gate.

`PROMETHEUS_POLICY_SEARCH_PREREGISTRATION.json` fixes the next production question
before execution: current risk dataset/model, thresholds 0.05/0.1/0.25/0.5, full
and half sizes, all 139 source-generator validation groups under the 160-group
cap, then 100 fresh identities beginning seed 93071. No final-challenge tuning.
Validation selection is optimistic and does not establish generalization.

Expanded browser gate passed in 3.8 minutes, including a real eight-gate search,
frozen no-trade selection on a deliberately small validation set and 1200 fresh
control variants. Its systemd worker is verified terminal. A subsequent recovery
fix transfers search owner identity to a resumed worker while reusing completed
stages; **14 focused search/API/job tests passed** in 82.09 seconds after this
change. The earlier full gate remains 288 passed / one skip; it preceded the
ownership fix and the additional API-count regression. Final Ruff/mypy and
frontend build/lint pass. Source and weights are ready for the preregistered
production comparison; no production search result is claimed yet.

### Legacy provenance preflight correction

The first production search job `job-39b5b0c0eac945d298b5c666` failed before any
simulation, with `KeyError: evaluation_generator`. Its supervised handle is
terminal and its full error/source record is retained. The earliest completed
tournament manifests predate that field. The novelty checker now derives their
seed ranges from the referenced frozen dataset (or explicit challenge config),
rather than skipping them or modifying historical results. A regression covers
this legacy format and confirms reused seeds still reject. Direct preflight
against the actual archive confirms seed block 93071–93170 remains unused.
`PROMETHEUS_POLICY_SEARCH_FAILED_JOB.json` preserves the failure; replacement
source gates and the new supervised job are pending below.

Legacy correction gate: **14 focused search/API/job tests passed** in 82.30 seconds;
Ruff/mypy pass, and final TypeScript/ESLint pass. The failed job has no completed
research output and consumed no validation/test scenario. Source is ready for
replacement submission without changing the preregistered parameters or seed
block. Historical tournament/model bytes remain unchanged.

## Active production policy search — exact continuation

Source `7ec440f` is frozen. Replacement job
`job-659ad7466d8d41f7b5a7f360` is RUNNING under
`midas-arena-job-659ad7466d8d41f7b5a7f360.service`, verified ACTIVE with MainPID
3045736, approximately 266 MiB memory and 223/5004 validation variants at the
last observation. Search artifact is `search-948c67bb4c90175f0b1e0294`.
The 5004 variants are 139 matched validation groups × three execution modes ×
eight gates plus four controls. They are not independent samples. The subsequent
fresh test has 100 groups, four controls and at most one selected gate, so
1200–1500 variants. A no-trade selection is valid.

Budget: one serialized CPU worker, MemoryMax 4 GiB, 5400-second wall limit,
minimum 2 GiB host available memory and 1 GiB Arena artifact cap. It stops after
both stages, cancellation, timeout or pressure failure. Source/weights/validation
inputs and all completed candidates remain retained. API is READY; dashboard
is active. Job and search are visible in the Arena. Logs:
`journalctl --user -u midas-arena-job-659ad7466d8d41f7b5a7f360.service`.
Cancel from the job panel or POST
`/api/arena/jobs/job-659ad7466d8d41f7b5a7f360/cancel`.

Next turn must poll this exact live handle and its authoritative
`data/arena/jobs/job-659ad7466d8d41f7b5a7f360/job.json`. Do not modify Arena Python
source until terminal; observation timeouts do not justify restarting it.
After completion, verify all new replays/configs, selected policy lineage and
novel seed/group coverage; compare final downside results with no-trade and
controls without changing the selected gate. Publish a supported finding and
preserve all unsuccessful/tied validation candidates. Extend bundle export for
search artifacts, then proceed to fair cross-target severity/cost comparisons
and correctly accounted recovery actions. The overall Prometheus goal is ACTIVE.

## Independent search evidence verification and export

The live source remains frozen. Added standalone `verify_policy_search.py` to
recompute policy selection directly from frozen validation row outcomes, using
an independent implementation of the fixed score, grouped paired bootstrap,
minimum sample rule and tie preference. It checks preregistered gate configs,
weights/dataset/stage hashes, control coverage, finite outcomes, final selection
bindings and disjoint source seeds. `--full-replays` verifies every retained
core/journal hash and replay-row identity. It does not repeat policy inference
or establish real fill probabilities.

Bundle exporter v3 accepts completed searches as well as directors. It refuses
incomplete searches and invokes full replay verification before search export.
It includes both stages, model weights, frozen dataset, captured job source,
associated findings and verification tools. Each archived payload is hashed
from the exact bytes written, with one payload held in RAM, preventing later
model annotations from invalidating the bundle manifest. Existing output still
uses exclusive publication and cannot be overwritten.

Five focused export/evidence tests pass, including independently recomputed
selection, altered final bindings and missing replay rejection. The completed
browser search was audited against its actual 180 validation / 1200 final
variants and exported as a clearly labelled smoke artifact. All 1452 exported
file digests verify (SHA256
`ada5461da53f11b11a95f849e68ff7d5fd460dfd9b2fa830a94574d2d9192614`).
This smoke bundle is not the production campaign. Source Ruff/mypy pass; full
regression **292 passed / one PostgreSQL skip** in 298.05 seconds, one existing
Starlette warning. `ARENA_REPRODUCIBILITY.md` documents the new commands.

Production validation completed as `tournament-74386f79d51b4f68b4fd2020`:
5004 variants / 139 matched source groups. Independent selection recomputation
agrees with the frozen decision: `gate-f12a4e29a05e5a4ce18f`, maximum predicted
unmatched risk 0.10, full sizing. Validation mean P&L 1.52829305, 5% tail loss
0.68976190, score +0.83853114; arbitrage score +0.67038863; no-trade 0. Worst
validation loss is -4.48. This is selection evidence subject to optimism, not
an independent champion designation. The final new-seed stage is running.

Runtime accounting also identifies a performance question: validation wall
1491.85 seconds versus 398.91 seconds summed episode-reported runtime. The
1092.94-second residual includes artifact/progress I/O, setup and repeated budget
checks; it cannot be attributed to one cause without instrumentation. Profile
these costs after the source-frozen campaign finishes before changing throughput
or safety check behavior. `PROMETHEUS_POLICY_VALIDATION_SELECTION_AUDIT.json`
preserves this observation and the independent decision check.

## Completed policy search — independently audited fresh result

Production search `search-948c67bb4c90175f0b1e0294` completed under
`job-659ad7466d8d41f7b5a7f360`, exit 0, recorded elapsed 1983.41 seconds.
The supervisor is terminal (MainPID 0). Independent auditing confirms the exact
validation-selected 0.10/full gate and verifies all **6504** search-stage replays
(5004 validation + 1500 final variants), including financial/journal hashes,
preregistered candidates, final bindings and unused test seeds.

Fresh final tournament `tournament-be94f3ab8512499ab68db300` contains 100 generated
base groups / three execution variants for each of five matched policies.
The frozen gate's mean virtual P&L is 1.17716567, mean bootstrap interval
[0.86014168, 1.54643986], tail loss 0, worst final loss 0, downside score
+1.17716567. No-trade scores 0; arbitrage -0.27071933; conservative -0.64717067;
random -0.27137667. The gate abstains in 55.33% of variants. Its mean by execution
is optimistic 2.439206, standard 1.000991, conservative 0.0913.

The paired mean difference versus arbitrage is -0.20238167 with interval
[-0.45172317, 0.02642033], so this is not a demonstrated mean-return improvement.
It clears the declared downside objective in this bounded synthetic sample.
Zero observed losses do not imply zero loss probability. Maximum mark-to-market
drawdown was 13.27%, despite zero final losses; pre-trade thresholds do not
provide a drawdown guarantee. Synthetic fills, zero base extra costs and generator
structure remain material limitations. No live promotion or weight update occurs.

A supported finding is published as `finding-d6fceea037935d437cd31128`, with paired
uncertainty and these caveats. The final tournament now has a verified fixed-path
cost report. Export tooling also collects findings attached to either stage, so
an additional immutable bundle preserves the completed plan plus its final
interpretation. Original smoke and production bundles remain untouched.

The promising fixed policy warrants a LIMITED preregistered follow-up:
`PROMETHEUS_FROZEN_GATE_STRESS_PREREGISTRATION.json` uses the same model, 0.10
threshold and full size on 100 new groups beginning seed 113071. It applies the
existing event-sequence timing/withdrawal/lost-ack/cancellation/duplicate/pause
mutations across three execution assumptions, plus matched controls, with no
ledger corruption, refit or threshold tuning. Proposed wall budget is 1800
seconds. This is independent robustness evaluation, not adaptation to the opened
93071 test. Submission status and exact handle follow below.

## Active fixed-gate robustness follow-up

The preregistered adversarial job is
`job-65fcccb2fd5340c783923279`, unit
`midas-arena-job-65fcccb2fd5340c783923279.service`. Its exact handle was verified
ACTIVE, MainPID 3077457, about 274 MiB memory, 156/1500 variants. It uses the same
0.10/full gate and immutable model on new seed block 113071–113170, with existing
adverse event mutations and matched controls. No gate or weights were adapted
from the final test. No stress result is claimed yet.

Budget: one CPU worker, 4 GiB per-unit memory ceiling, 1800-second wall bound,
2 GiB available-host-memory floor and 1 GiB Arena artifact cap. It terminates at
1500 variants or on cancellation, timeout or pressure failure. Inspect/cancel
in the Arena, or POST
`/api/arena/jobs/job-65fcccb2fd5340c783923279/cancel`. Logs:
`journalctl --user -u midas-arena-job-65fcccb2fd5340c783923279.service`.
Authoritative job record is
`data/arena/jobs/job-65fcccb2fd5340c783923279/job.json`; observed snapshot is
`PROMETHEUS_FROZEN_GATE_STRESS_JOB.json`.

Next turn: read the original objective, inspect the current worktree and poll
this exact handle. Keep Arena Python/financial source frozen while it runs.
After completion, verify every stress replay and compare its declared objective,
loss/exposure distribution and grouped uncertainty with the fixed controls.
Losses are legitimate unless invariant evidence shows otherwise. Publish a
bounded finding, preserve the initial positive result and all failures, and
export the stress evidence without replacing earlier bundles. Then instrument
budget/progress I/O overhead and develop correctly accounted proposal-severity/
recovery experiments. No broader profitability or guaranteed safety claim follows
from these synthetic studies. The full Prometheus goal remains ACTIVE.

## Worker overhead profiling checkpoint

During the frozen stress campaign, a read-only artifact-size benchmark compared
existing `Path.rglob`/per-file stat checks with an iterative `os.scandir` walk.
Five alternating-order measurements gave medians 0.21838 seconds versus 0.07287
seconds on the current tree. Active writes can change totals between scans;
correctness parity was tested on a quiescent fixture including regular files,
file symlinks, skipped directory symlinks and broken links. The fixture test
passes, as do Ruff/mypy. `PROMETHEUS_BUDGET_SCAN_PROFILE.json` preserves actual
measurements. This does not yet establish a whole-job speedup or assign the
previous runtime residual to a single cause. The active worker remains unchanged.

## Audited stress result and measured scan optimization

Stress `tournament-aa1e3d4241f044daa4eaff30` completed 1500 matched variants over
100 new groups in 503.995 seconds, exit 0, no invariant failures. The fixed
0.10/full gate scored +0.569284, with mean interval [0.33078328, 0.80912803],
no final losing variants and marked drawdown 12.62%. Arbitrage scored +0.050455;
conservative -1.814215. The gate's paired mean difference versus arbitrage was
-0.23250433 with interval [-0.59613125, -0.00194214], so the lower mean return
must not be described as an improvement. It retains the declared downside
advantage in this sample, with all synthetic/uncalibrated limitations intact.

The full read-only audit verified 23,004 replay variants, 14 model artifacts and
two datasets. The standalone stress bundle's 1570 file entries verify, SHA256
`717568d07e451d0271280e6e0a0f55e28e101066416888f9f58a6d7fb78dc39d`.
A linked finding and fixed-path cost report preserve the conclusion and caveats.

After the stress worker became terminal, artifact budget scans switched to the
benchmarked iterative scandir walk. There is no cached byte total or reduced
check cadence: every progress callback still checks cancellation/signals, wall
budget, available memory and the complete logical artifact-byte total. Job records
now retain cumulative artifact-scan/progress-publication timing counters. Tests
prove scanner parity and that a sparse over-budget artifact still stops a real
worker with FAILED state and retained timing evidence. Full regression passed
294 tests / one PostgreSQL skip in 303.14 seconds, one existing Starlette warning.
Subsequent focused gates cover explicit performance-replay metadata and direct
standalone tournament export.

A saved-specification performance replay will compare end-to-end time and all
financial/journal hashes with the original stress run. Its design is explicitly
PERFORMANCE_REPLAY: it cannot count as new independent evidence or designate a
champion. Scanner measurements alone do not establish whole-job speedup; the
new worker counters and repeat will provide that evidence.

Final optimization source is committed as `4650bd9`. Focused worker/tournament
and scanner gates passed nine tests after explicit PERFORMANCE_REPLAY handling;
six export/evidence tests and a comparator test pass. The full 294-test gate
preceded the purpose annotation; that annotation is separately tested and does
not alter financial transitions. Added direct tournament bundle export with
replay validation for standalone stress evidence. No champion or independent
research evidence can be designated from a performance replay.

Benchmark replay job `job-6104eea7028e4f04b7233121` is supervised with the original
stress specification, fixed gate and seed block unchanged. It was observed
RUNNING at 1240/1500, elapsed 230.35 seconds, with 102.13 scan seconds and 8.93
progress-publication seconds. Source remains frozen until terminal. The
original stress run completed in 503.995 seconds. End-to-end speed and exact
accounting equality are not claimed until the completed comparator verifies
all 1500 financial and journal hashes. Shared-host single-run limitations apply.

## Completed performance replay and paired outcome audit

Replay job `job-6104eea7028e4f04b7233121` completed, exit 0, in 281.149
supervised-job seconds. The comparator verified identical financial metrics,
result/scenario/policy identities and actual journal hashes across all 1500
variants. Tournament time changed from 501.999 to 279.450 seconds: observed
1.79638× speed ratio. This is one shared-host comparison, not a repeated
controlled benchmark or new independent strategy evidence. Worker counters
record 124.192 seconds of full artifact scans and 10.855 seconds publishing
progress; artifact safety checks retain their original cadence and budgets.

A development-only audit now compares saved completion and residual unmatched
outcomes on exactly the same first-admitted observations. Among 1689 variants
from 563 train/validation groups, 1077 were incomplete, of which 915 had matched
inventory and 162 had unmatched inventory. Only 15.04% of incomplete proposals
were unmatched. Positive residual shares had median 8 and maximum 24.39.
Residual shares are not dollar losses or recovery costs. The frozen final test
partition is excluded from all reported statistics. The audit checks exact
Decimal agreement between saved leg quantities, residual and binary risk label.
Seven focused audit/comparator tests pass; the full regression gate is running.

A separately hashed derivation utility freezes alternative binary labels from
saved initial outcomes while preserving every observation, episode identity and
partition. Parent records remain unchanged; the transform source is stored next
to its artifact. Such derivatives are correlated views of the same data, never
new independent samples. No classifier final-test evaluation is authorized by
this derivation. Next: bounded completion fits on the risk dataset's identical
observations, validation-only comparisons and explicitly paired target analysis.

## Paired target training completed

Derived completion dataset `dataset-d8c1593a2d281e1c9e430952` preserves exactly
1935 observations / 645 eligible groups from unmatched dataset
`dataset-f53981b7dd24c1521ce749b1`; it contributes no new independent observations.
Both dataset identities and the transformation source are retained. The target
frequency of the final test partition is not published by the derivation.

Supervised job `job-2eb81a9086e34a8899c5e409` completed four real fits, exit 0,
21.961 seconds, under one CPU / 4 GiB / 600-second limits. Sweep
`sweep-7add7afb907a5801568ad8e6` used logistic and MLP with seeds 11 and 29.
Mean validation Brier was 0.03640857 logistic and 0.03460778 MLP. The 0.00180079
MLP improvement fell inside the preregistered 0.002 simplicity tolerance,
so logistic `model-e8ea85c7e7fe49f7a0a2a7b9` was selected. Other artifacts:
`model-4058f9dcf60a4dd39ef3b8ac`, `model-0994f52d25424bfeb5c91a81`,
`model-cfe981f8ce0e48408fdf7866`. All four classifier tests remain unopened.

On paired validation observations, inverse completion probability had Brier
0.52414196 against unmatched labels, versus 0.08924986 for frozen direct-risk
`model-131794f0434945a286163323`. Mean paired group Brier difference was
+0.43489214, exploratory bootstrap interval [0.36536208, 0.49484375]. These
models were selected on this validation set; the interval is not independent
selection-adjusted evidence. Separate target Brier scores cannot rank the
underlying tasks. The finding is target mismatch, not a new policy or profitability
claim. Saved report and Arena finding `finding-40999cbcecf28d5f75f17df0` preserve
this distinction. Existing 0.10/full gate and prior final results remain fixed.

The full regression gate passed 297 tests / one PostgreSQL skip / one existing
Starlette warning in 305.79 seconds before the new paired-target tests were
collected. The final focused gate passed ten tests (including the nine new target
audit/derivation/comparison tests), and Ruff plus strict mypy pass across the
changed scripts and 62 source files. A comparison fixture initially lacked
family metadata required by the metrics evaluator; it was corrected and rerun.
No Python financial/Arena source changed during the suite or production job.

Current inventory: 18 registered model artifacts (17 fitted, one fixed control),
three dataset artifacts representing two source datasets, ten research tournaments
plus one explicitly repeated performance tournament. No research workers remain
active. The full Prometheus objective remains ACTIVE.

### Next continuation queue

1. Compare completion/direct-risk policy behavior on these matched validation
   observations without using prior final tests for selection. Any new selected
   policy requires a preregistered fresh seed block and retained no-trade controls.
2. Add residual-share severity regression, with zero-inflated labels and proper
   group metrics. Residual shares cannot substitute for dollar loss or recovery
   cost; keep future outcomes out of observable features.
3. Use the new recursive dataset bundle support for future derived-dataset
   tournaments. It preserves parent lineage and transform source; both exporter
   and read-only verifier check exact paired rows and producer hashes.
4. Perform genuine frozen-policy fee/latency/depth stress reruns; fixed-path cost
   overlays alone do not represent changed fill behavior.
5. Expand Data Foundry with actual public observation capture, without inventing
   fills or settlements. Recovery hedges/unwinds require new financial accounting
   and hard-risk invariants before policy experiments.

Bundle export now includes derived dataset parents and stored transformer source,
with lineage/hash/row verification and cycle rejection. This was added while the
read-only replay audit ran; financial/Arena source stayed unchanged.

Final export/target/evidence gate: 14 passed in 10.12 seconds. Existing export
fixtures exposed an unnecessary feature-schema requirement for non-derived
archives; export retains its original hash checks for those archives, while
new derived lineage requires full observation/partition/producer verification.
The rerun passes. API catalog directly confirms 3 datasets, 18 model artifacts,
and the new linked finding; all four new classifier tests are still null.

The completed read-only audit verifies all 24504 replay variants, 18 model
weight artifacts and 3 datasets, including derivative parent/transform provenance.
Of these variants, 23004 belong to research tournaments and 1500 to the explicit
performance repeat. This audit verifies bytes and matched coverage, not retraining
or every numerical leaderboard statistic.

## Paired-target tournament support and validation plan

Tournament admission now accepts models from verified target-only derivatives
of the same frozen observations. Shared source identity, exact observation and
partition content, generator specification, saved source/feature provenance,
parent rows and stored transformation bytes must agree. Altered or unrelated
observations are rejected even if their row hash is resigned. Every model's own
training dataset hash is checked and persisted separately in the tournament.
PPO retains its original single-dataset contract. No simulator or broker financial
semantics changed; risk admission and support abstention remain intact.

Bundles now include each model's training dataset and derivative ancestry, even
when the tournament's primary dataset is the unmatched parent. The UI identifies
completion versus exposure prediction alongside gate thresholds; its new rendered
component test checks both target labels. Full Python regression passed 308 tests,
one PostgreSQL skip, one existing Starlette warning in 326.48 seconds. Four
additional comparator tests pass after full-suite collection. Frontend: five
unit tests, typecheck, lint and production build pass (existing chunk-size warning).
Strict mypy/Ruff pass. Earlier focused integration/export gate passed ten tests.

`PROMETHEUS_PAIRED_POLICY_PREREGISTRATION.json` freezes an exploratory validation
league: the established direct-risk 0.10/full gate versus completion 0.90/full
(primary) and completion 0.50/full (secondary), plus all four controls and all
three execution presets. It covers all 139 raw generator validation groups,
including 40 without an admitted labelled proposal, for 2919 correlated variants.
No thresholds or policies will be selected/promoted from this comparison, and no
classifier/fresh challenge final tests are opened. Validation reuse means that
any observed difference remains exploratory. The full goal remains ACTIVE.

Source checkpoint `0c13722` is committed. Paired validation job `job-83cb1633e674433b8bb6e6c8`
was confirmed RUNNING with systemd MainPID 3280929, progress
{'done': 830, 'total': 2919}, elapsed 150.47 seconds.
Its unit is `midas-arena-job-83cb1633e674433b8bb6e6c8.service`; budget 1800 seconds, one CPU, 4 GiB,
1 GiB artifact cap. Inspect/cancel in Arena or call
`POST /api/arena/jobs/job-83cb1633e674433b8bb6e6c8/cancel`; logs use
`journalctl --user -u midas-arena-job-83cb1633e674433b8bb6e6c8.service`. Keep Arena/financial Python
source frozen until this worker is terminal. No result or winner is claimed.
After completion, run `scripts/compare_policies.py` using the primary and
secondary gate IDs from the preregistration; export the verified tournament
bundle and preserve the exploratory validation caveat. Then implement
residual-share severity regression and actual economic scenario reruns.

## Completed paired policy and chronological public capture checkpoint

The paired league completed 2919 variants in 542.241 seconds,
exit 0: `tournament-3060d836ebe14825a985e59c`, VALIDATION with no champion.
Completion 0.50/full scored 1.01501213 versus direct risk 0.10/full 0.83853114
and completion 0.90/full 0.70177842. Risk had higher mean P&L, but larger tail
loss. Better unmatched-label Brier than inverse completion did not establish
policy dominance. The gate and all final tests remain unchanged. The paired
mean differences/intervals are in the primary and secondary comparison reports;
139 reused validation groups make these exploratory, not independent evidence.
Finding `finding-d9df6beceec1042a0b2cddc4` preserves this qualification. All 2994
bundle payload hashes verify; archive SHA256
`d4950a53d8b5479b85a0cb49e37e2a51224fe65acfbe3d15f6109b6120529c85`.

The public series `public-series-2d5f0b5f86f64f21a8156acc` completed 25 events
from 12 sequential two-leg polls over 55.509 seconds, with 9 and 11 distinct
quote books. Original responses, normalized events, both clocks, state and source
are retained; hash/schema/clock/provenance validation passes. The API exposes the
series as RECORDED_PUBLIC. This is one short market history, not independent
training episodes, empirical fills, settlement or onchain payout attestation.

The GET-only utility has bounded requests, a minimum five-second poll interval,
16 MiB observation/discovery response caps, wall limits, fsynced retained partials
and exclusive no-overwrite publication. Four tests pass, covering wire/clocks,
no fabricated attestation, interrupted/unsupported capture and immutable publish;
Ruff/strict mypy pass. CPUQuota 25%, MemoryMax 256 MiB, internal wall 180 seconds
and supervisor wall 240 seconds were applied. The first startup failed because
resolving the venv interpreter symlink selected system Python; its failed unit is
retained, and the corrected launch completed. No Arena Python source changed
while either worker was active. Both processes are terminal; API is READY.

Next: residual-share severity regression, with explicit units and probability-gate
exclusion, followed by actual economic scenario reruns. The full goal is ACTIVE.

## Severity regression implementation checkpoint

Added `severity` jobs for deterministic ridge and genuine PyTorch Softplus MLP
regression of exact initial-proposal residual shares. The frozen dataset remains
unchanged; only retained train/validation outcomes enter fitting. Features and
RMS target scale are fit on training only. Positive-outcome MAE/RMSE, aggregate
errors, grouped RMSE intervals, family/execution breakdowns, zero and train-mean
controls are persisted. Shares are not probabilities, dollar losses or recovery
costs. Probability loaders reject these models, and the tournament UI excludes
them from probability policies. No existing gate or hard risk rule changes.

MLP checkpoints retain current/best weights, optimizer, RNG, epoch, early-stop
state and actual curves, with atomic fsync and hash metadata. Tests verify exact
resume equivalence, training-only feature means, no probability admission,
reload and bounded worker/evaluation dispatch. Final tests remain unopened by
training; explicit evaluation dispatch uses continuous metrics. The UI supports
both architectures, shares-based metrics and validation controls, with a rendered
regression test preventing probability diagnostics from appearing.

Full regression: 321 passed / one PostgreSQL skip / one existing Starlette warning
in 368.53 seconds. Focused integration previously passed 15 tests; a later five-test
severity gate passed after making unchanged optimizer defaults explicit and
correcting loss descriptions (ridge uses raw squared shares plus L2; neural loss
uses train-RMS-normalized shares). Strict mypy/Ruff pass. Frontend: six tests,
typecheck/lint and production build pass, with the existing chunk-size warning.

Three production fits are preregistered: one ridge and two MLP seeds, selected
on validation group RMSE with 0.10 shares practical tolerance and positive-error
controls. This is fit selection, not policy promotion or independent evidence.
The final classifier and regression test partitions are excluded from this plan.

## Severity production fits completed

All three preregistered supervised jobs are terminal, exit 0:
- `job-b0e81322ee0d40cbb443b275`: ridge `model-38a8da8c0d7a481d8d2d9771`.
- `job-b66615ae3dae44b3a05a42f0`: neural seed 11 `model-5a0f86eceb8c4c689e85d285`, 55 real epochs (early stopped).
- `job-f59802c1add140c8828513bf`: neural seed 29 `model-265cbcc71f6847828c959882`, 50 real epochs (early stopped).

Validation RMSE: ridge 3.72768645 shares, neural 3.66792487 / 3.66050721,
zero control 4.08255668, train-mean 3.91222962. Neural mean improvement over
ridge was only 0.06347041 shares, below the preregistered 0.10 tolerance:
ridge is selected. The verifier independently reloads each candidate, recomputes
all validation metrics, and binds source/data/job specifications to the plan.
No final test was opened. Aggregate MAE (ridge 1.80005, neural about 1.68) was
worse than zero-control MAE 1.21391; positive-outcome errors remained about nine
shares. Modest squared-error gains do not establish reliable tail forecasts or
policy benefit. Finding `finding-8d31175172eab2d986a9cbf3` preserves those limits.

A read-only live Chromium inspection of the actual selected model confirms
shares-based target/metrics/controls, no probability diagnostics, and no page
errors. The API restart restored a verified 32859-event paper snapshot and
returned READY with the exclusive Laboratory archive still healthy. Fresh archive
logical hash, 162000 variant / 18000 group coverage and SQLite quick_check pass.
All model-weight and tournament-row/coverage hashes pass a fresh read-only audit;
this coverage audit does not reread old replay journals. The new validation
league's entire replay bundle was separately verified earlier in this checkpoint.

Current registry: 21 artifacts, 20 fitted (16 supervised probability predictors,
three severity regressors, one PPO), plus one fixed heuristic control. No research
or public-capture workers remain running. The full Prometheus goal is ACTIVE.
Next: freeze and evaluate the selected severity fit independently without tuning,
then build actual fee/latency/depth economic reruns and broader data collection.

## Frozen severity holdout and actual economic-regime implementation

Before opening any severity final test, the verified pre-test selection, all
three candidate manifests/weights/checkpoints, frozen data and captured training
sources were exported. All 177 payload hashes verify; restoring the bundle
reproduces the original selection exactly after current registry evaluation.
`job-b53452014bb5434d9e8da6b6` then evaluated only the selected ridge on 82
held-out source groups / 246 correlated variants. RMSE was 3.18595732 shares
versus 3.48544593 zero and 3.37398888 frozen train-mean controls. MAE was
1.50882216 versus zero's 0.87439024. Weights/selection were unchanged. This
qualifies a modest squared-error gain; it establishes no tail guarantee or policy
advantage. Neural severity tests remain unopened, and no classifier tests changed.

New bounded economic regimes modify generated scenarios before execution:
initial and future bid/ask depth, synthetic fee coefficients, submission latency,
and optional existing cost assumptions. Recorded observations cannot be rewritten.
Risk admission/support abstention remain active. Each row retains its pre-regime
scenario hash. Comparisons verify common origin/policy/configuration, both actual
replay cores/journals, and exact declared transformation of the replay scenario.
The native UI exposes declared coefficients and latency with explicit units.

Focused economic/integration gates passed six tests; legacy comparison tests
found one missing optional configuration-field assumption in a full run (323
passed, one failed, one skip). That comparison-only regression was fixed, and
five focused research/economic tests pass. A full rerun is in progress. Seven
frontend tests, typecheck/lint/build pass. A subsequent unused fixture argument
was corrected and frontend typecheck/lint rerun. Ruff/strict mypy pass.

`PROMETHEUS_ECONOMIC_RERUN_PREREGISTRATION.json` freezes four conditions over
100 fresh source groups beginning seed 133071: baseline, half depth, +200 ms
submission delay, and fee coefficient 0.01. They share all source identities:
6000 variants do not provide 6000 independent samples. The old risk 0.10/full
policy and weights stay fixed; this experiment performs no tuning or promotion.

Final full rerun passed 324 tests / one PostgreSQL skip / one existing warning
in 374.68 seconds. All current economic source is frozen for launch.

Economic source committed as `c9d2341`. API restored a verified 34686-event
paper snapshot and is READY. Four bounded jobs are admitted and inspected under
user systemd; one serialized research worker is active at a time.
- additional_200ms: `job-750f79877bd943fea3feccfc`, RUNNING, {'done': 671, 'total': 1500}, unit `midas-arena-job-750f79877bd943fea3feccfc.service`.
- baseline: `job-881058f3ba194aaf89780a6b`, QUEUED, {'done': 0, 'total': 1}, unit `midas-arena-job-881058f3ba194aaf89780a6b.service`.
- fee_coefficient_001: `job-b239042b57814feb95a04563`, QUEUED, {'done': 0, 'total': 1}, unit `midas-arena-job-b239042b57814feb95a04563.service`.
- half_depth: `job-85004834f3a746ec941d4401`, QUEUED, {'done': 0, 'total': 1}, unit `midas-arena-job-85004834f3a746ec941d4401.service`.
Each has CPUQuota 100%, MemoryMax 4 GiB and 1800-second wall bound, plus
1 GiB artifact and host-memory pressure guards. View/cancel in Arena or POST
`/api/arena/jobs/ID/cancel`; logs use `journalctl --user -u UNIT`. Keep all Arena
Python source frozen until terminal. After baseline and each condition complete,
run `scripts/compare_arena.py --control BASELINE --candidate CONDITION`, export
verified replay bundles, and interpret all four conditions as the same 100
source groups. No results or economic robustness are claimed while they run.

## Economic condition verification checkpoint

Added a completed-study summarizer that reads authoritative job records, binds
all configurations/source/weights to the preregistration, verifies each declared
scenario transformation through paired replay comparison, and keeps the common
100-group denominator. Four focused tests pass, including stale documentation
state, incomplete jobs and changed source/weights; Ruff/strict mypy pass. The
read-only live browser shows editable economic controls without page errors or
submitting additional jobs. Financial/Arena Python source remains frozen.

Added-delay condition `tournament-c2726108b16543a796b9f202` completed all 1500
variants. Frozen gate mean +0.81887267, 5% tail loss 1.46186667, downside score
-0.642994; no-trade wins at zero. There were 137 unsupported gate decisions.
Its bundle verifies 1570 payload entries. Finding
`finding-8e9cb4f1a5a3006200204520` records the failed downside objective.
Fee coefficient 0.01 condition `tournament-6eabcc71619c4f2989cd072d` also
completed 1500 variants: gate mean/score zero, 366 unsupported decisions.
This is abstention under unseen fee inputs, not demonstrated profitable fee
robustness. All trading controls scored negative. Its full bundle hashes verify.

The unperturbed baseline and half-depth condition remain active/queued as recorded
in `PROMETHEUS_ECONOMIC_RERUN_JOBS.json`; no paired economic effects are claimed
before baseline completion. Keep Arena source frozen. After all four finish, run
`scripts/summarize_economic_reruns.py --output docs/PROMETHEUS_ECONOMIC_STUDY.json`
and export the remaining verified bundles. The full goal remains ACTIVE.

## Completed economic publication, loss attribution and failure regressions

All four preregistered economic reruns completed, giving 6,000 correlated variants
over 100 shared source groups. The native Arena serves the frozen study on all
four condition endpoints. Baseline and half-depth bundles each passed all 1,570
payload hashes; prior delay/fee checks remain recorded. Runtime inventory now
contains 21 registered artifacts (20 fitted), 16 tournaments, and 37 terminal jobs
(33 completed, two cancelled, two failed). The tournaments contain 33,423 variants,
including 1,500 performance-replay variants; these are not independent samples.

`attribute_arena_losses.py` verifies saved rows and replay hashes, reconstructs
binary fill quantities from ledgers, and allocates terminal cash flows between
matched and residual shares in proportion to each asset's filled quantity. Fill
costs include ledger fees. It reconciles position realized P&L and explicit
operating/financing/collateral costs to episode net P&L. It rejects incomplete
positions and inconsistent order quantities. Saved reports cover all 300 gate
variants in baseline and delay conditions. All six delay losses have residual
shares (five source groups, total loss 21.928 virtual USD), versus five baseline
losses (four groups, total loss 11.258). This is descriptive accounting, not a
causal estimate or proof that an executable hedge would avoid the loss.

`replay_failure_cases.py` freezes up to 100 observed losing cases with original
scenarios, saved actions/explanations, and expected financial/journal hashes. The
actual six delay failures were frozen to a separate compressed corpus and rerun
through ArenaEnv. All financial hashes, journal hashes and decision traces match
exactly. This implements failure-driven accounting regression generation; it
does not rerun model inference or convert failures into independent evaluation
data. The corpus and verification report retain explicit limitations.

Commands:

```bash
.venv/bin/python -m scripts.attribute_arena_losses --tournament tournament-c2726108b16543a796b9f202 --policy gate-f12a4e29a05e5a4ce18f --output /tmp/delay-attribution.json
.venv/bin/python -m scripts.replay_failure_cases verify --corpus /home/charlie/midas-prometheus-bundles/economic-delay-failure-corpus.json.gz --output /tmp/delay-regressions.json
```

Existing destinations are not overwritten. The aggregate finding is published in
Arena and linked to the supporting latency tournament. The full goal stays active.
Next priorities: adaptive follow-up planning with independent challenge identities;
uncertainty-aware severity before policy integration; economically sound recovery
hedge/unwind semantics. No policy was retuned on the opened economic study.

Validation for the new attribution and regression tools: 13 tests passed in
10.43 seconds; Ruff checks passed. The published finding was read back from the
production Arena API. No source package or financial engine changed in this
checkpoint.

Production browser verification passed: the baseline tournament displays the
frozen four-condition study, 100 shared source groups / 6,000 correlated variants,
and the downside chart. The published aggregate finding is visible in Research
Findings. No page errors were recorded; the screenshot and browser evidence are
linked in PROMETHEUS_ECONOMIC_STUDY_BROWSER.json. An initial browser inspection
used an overly strict label selector and timed out before reading the tournament;
the corrected selector passed without changing application code.

The three-minute full-replay audit reached its wall limit without completing.
The verifier now logs completed tournaments and can atomically publish its report
with `--output`; interrupted/failed runs preserve the previous valid report. A
ten-minute bounded rerun is in progress. Focused attribution, failure-corpus and
derived-lineage tests: 16 passed in 11.38 seconds. Tests exercise CLI publication
and verify a failed audit leaves its previous published report unchanged.

Protected-campaign read-only verification passed again: SQLite quick_check OK,
162,000 unique variant IDs, 18,000 groups, unchanged ordered logical hash
70d446f0a3833011bb150b0212c4cad3f2751c7f1c210d4c6989816d249fe4ec.
The API exclusive owner lease remains held. Evidence is recorded in
PROMETHEUS_ECONOMIC_CHECKPOINT_ARCHIVE_VERIFICATION.json.

The bounded full-replay audit completed successfully and atomically published
PROMETHEUS_ARTIFACT_AUDIT.json: all three datasets, 21 model weight artifacts,
16 completed tournaments and 33,423 saved variants passed immutable-byte,
coverage, financial-core and saved-journal hash verification. This checks saved
replays; the six failure-corpus cases were separately re-executed and matched
exactly. It does not claim all 33,423 variants were simulated again. Older
source-reconstruction limitations remain documented. No research job is active.

## Adaptive research coordinator implementation and validation

`scripts/research_followup.py` inspects an attached economic study and chooses a
pure-latency reversal using a transparent rule. It verifies saved condition row
hashes, model weights and producer sources, then selects the two families with
the largest observed losses and retains controls. The five-family schedule in
the actual preflight balances both seed-parity settlements within each family
(six of each parity per family for 60 groups). The previously opened scenarios
are excluded from both follow-up seed ranges.

The coordinator preregisters two cycles, at most four supervised Arena jobs.
Cycle one repeats baseline/200ms added delay on fresh directed scenarios. Cycle
two tests half that delay if the gate score is nonpositive, or double it if
positive, on a disjoint range. It does not refit models or choose thresholds.
Directed-challenge promotion is withheld by requiring more champion groups than
the plan evaluates. Results remain descriptive, and two adaptively assigned
delays cannot establish a population break-even frontier.

The plan has a separate immutable preregistration and captured producer scripts.
Source/configuration changes are rejected. Submission intents recover a child
job created before a coordinator crash without launching a duplicate. Ambiguous
recovery and failed workers stop the plan. The cancellation path also recovers an
unrecorded submitted job. Active jobs and completed tournaments are linked in
the Research Director view; native cancellation is available for these plans.
Each completed cycle publishes actual paired uncertainty and loss attribution
in Research Findings. Existing core job supervision and pressure/disk limits
remain in force; the protected Laboratory archive is outside all new writers.

Validation: full Python suite 353 passed, one skipped, one existing Starlette
warning, 387.93 seconds. Focused backend checks 34 passed; frontend nine tests,
typecheck, lint and build passed. The existing chart-chunk warning remains. The
actual artifact preflight chose gate-f12a4e29a05e5a4ce18f, source seeds 143071..
143130 and 143131..143190, with volatile/disappearing/calm/deep/thin families.
Preflight submitted no jobs. See ARENA_ADAPTIVE_RESEARCH.md and the validation
and preflight JSON reports. Production launch is the next gate.

### Production adaptive plan running

Committed source 9dd2e70; API restarted READY with 41,472 verified paper events
at that restart. The preflight configuration was frozen as director-followup-453650eedd036f130bc81fd8.
Its separate coordinator unit is midas-prometheus-followup-453650eedd036f130bc81fd8.service: CPUQuota 25%,
MemoryMax 512 MiB, RuntimeMax 9,000 seconds, Nice 10, numerical libraries single
thread and CUDA disabled. The first child is job-5d88ff57521f4fc0a13d77e7,
running baseline cycle one with actual 900-variant progress. Child budgets are
one CPU, 4 GiB and 1,800 seconds. The native Arena serves the plan and child job.
No further stage has been submitted yet; subsequent stages are selected and
submitted sequentially by the bounded coordinator. Runtime evidence contains
exact current worker state, source/weight hashes and the stopping commands.

Cancellation: `.venv/bin/python -m scripts.research_followup stop --director director-followup-453650eedd036f130bc81fd8`
or **Cancel follow-up** in Arena's Research Director view. Logs:
`journalctl --user -u midas-prometheus-followup-453650eedd036f130bc81fd8.service -f`.
No research outcome is inferred from launch or partial progress.

Production progression verified: baseline tournament-3e1ee735a43c4f66a5b87b42 completed all
900 variants over 60 groups; frozen gate mean 1.586692, downside
score -0.420242. No paired interpretation is available until the delay
condition completes. The coordinator automatically submitted
job-739176fa2338460ca19c489a for matched 200ms delay. Production browser check
passed for the plan question, active child-job link and cancellation control,
with no page errors. Both source and weights remain frozen.

### First adaptive branch executed from verified results

Cycle one completed both 900-variant studies over the same 60 source groups.
The coordinator verified actual financial/journal hashes and declared scenario
transformations in the paired comparison. Gate mean P&L changed by
-0.210816; grouped 95% interval
[-0.4499100138888889, 0.01437923611111101]. Baseline downside score -0.420242, added
200ms delay +0.372542: lower mean P&L, but lower realized tail loss. Thus the
baseline already fails the downside criterion on these directed families; this
is not replication of the earlier positive-to-negative reversal. Latency does
not have a monotonic policy effect when it also changes actions and support.

The frozen positive-score rule selected 400ms for cycle two. The coordinator
automatically submitted job-5d49c24feb9e4c9d84f740f1 for its fresh baseline
(seeds 143131..143190). The subsequent matched 400ms condition remains pending.
Model weights, threshold, sizing and all producer sources remain unchanged.
Cycle-one paired evidence and attribution are stored in
PROMETHEUS_ADAPTIVE_RESEARCH_CYCLE_ONE.json and the native Research Finding
director-followup-453650eedd036f130bc81fd8-cycle-1. No champion was promoted.

## Completed adaptive research and truthful coordinator observation

The four-stage plan completed, both paired replay/scenario-transformation audits
passed, and all its supervisor/worker PIDs returned to zero. It stopped without
a fifth job. Cycle-two baseline score -0.060561, 400ms score -0.078717; paired
mean change -0.155045, grouped interval [-0.313081, -0.027845]. Cycle-one
positive-score rule selected this second delay on disjoint seeds. The 200ms
positive point score does not establish robustness, and its mean-change interval
contains zero. Cohorts differ between cycles, so this is not a population
break-even frontier. Aggregate finding finding-61263012d4b365eb527e0818
preserves these limitations. Model weights and thresholds were never changed.

The API now checks the adaptive coordinator's authoritative systemd state without
rewriting its owned manifest. Completed child jobs are displayed as VERIFYING
while paired audits finish. Stopped coordinators show INTERRUPTED; transient
observation failures show UNVERIFIED and never request a restart. Cancellation
remains available in these observed states. Large cycle/attribution payloads are
excluded from overview polling and remain on the detailed plan endpoint.

The experiment exporter supports the adaptive schema, verifies preregistration
and captured producer hashes, requires four distinct completed child jobs, checks
stage source/weight/configuration lineage, and includes each child source snapshot.
It also includes the frozen original study and its four source condition artifacts.
Tests: 19 focused backend/export tests passed in 2.72 seconds; nine frontend
tests, typecheck, lint and build passed. Earlier full Python suite: 353 passed,
one PostgreSQL skip; these later observation/export changes have focused coverage.
The existing Starlette warning and chart chunk warning remain.

Current completed inventory is 20 tournaments and 37,023 correlated variants,
including one 1,500-variant performance replay. Fitted model count remains 20;
there are 21 registered artifacts including the untrained heuristic. The older
full saved-replay audit covers 33,423 variants; the new coordinator separately
verified all 3,600 follow-up variants. No broad rerun of all 37,023 is claimed.

The completed bundle verified all 9,870 payload hashes, including the four
owned child source manifests and all four input-study condition artifacts.
Production browser verification passed for the completed plan state, absence of
active cancellation on the terminal plan, and the aggregate Research Finding,
with no page errors. Completion browser evidence and screenshot hash are saved
in PROMETHEUS_ADAPTIVE_RESEARCH_COMPLETION_BROWSER.json.

## Opportunity-persistence labeling and integrated training support

Added `persistence.py` and target `persistence` to the versioned dataset pipeline.
The label evaluates the original admitted quantity within its allocated capital
and original leg-price limits at the earliest actual scheduled submission arrival.
All earlier venue events are advanced through the unchanged simulator; both
original submits must still be pending. Private venue exchange timestamps are
used rather than delayed observer receipt clocks, on copied label-only books.
Future exchange timestamps invalidate quote eligibility. The raw venue hash and
clock convention are stored with the label. No arrival within the horizon is
negative. A positive label cannot guarantee fills or later second-leg availability.

Features remain the 19 pre-admission observable values. Tests demonstrate equal
features, decision time, initial execution outcomes, scenario hash and final
financial result hash between persistence and completion sampling. A profitable
quote can fail its original order-price limit, and a positive persistence label
can accompany incomplete execution. No broker, execution or accounting semantics
changed. Existing datasets are frozen; new source hashes produce new identities.

The existing baseline/PyTorch trainers, verified predictor loader, probability
gates and native target selector support persistence. The completion heuristic
is excluded. Persistence gates require scores at or above threshold and still
pass independent mathematical eligibility and risk admission. Model details
explain the quote/fill distinction. See ARENA_OPPORTUNITY_PERSISTENCE.md.

Validation: full Python suite 371 passed, one PostgreSQL skip and one existing
Starlette warning, 401.81 seconds. Twenty-nine focused tests passed; nine frontend
tests, typecheck, lint and build passed, with the existing chart chunk warning.
The production plan uses 1,001 fresh groups from seed 183071, seven families and
three execution assumptions; first-admitted scope. A two-seed logistic/MLP sweep
will select on validation Brier with the existing 0.002 simplicity tolerance.
Final classifier tests remain unopened. Seed overlap and artifact-budget checks
passed. The source will be frozen during production generation and training.
