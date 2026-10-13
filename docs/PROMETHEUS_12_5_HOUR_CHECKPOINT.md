# Project Prometheus — requested 12.5-hour checkpoint

Status-only checkpoint, checked 2026-10-13. Prometheus remains active. The
12.5-hour label is the user's cumulative-development checkpoint; it is not an
independently reconstructed measurement of active engineering time.

## Completion and scope

Estimated **70% complete / 30% remaining**, with a plausible uncertainty of
65–75% complete. This is engineering judgment against the entire original scope,
including stretch goals, rather than a measured task-count percentage.
The earlier 55–65% assessment is superseded. Progress since that assessment
includes deeper recovery/unwind research, generator-outcome audits, chronological
public observations, replay packing, and finite persistent scheduling. The
minimum Arena success criteria are satisfied; the full goal is not complete.

## Major milestones

| Milestone | Status | Evidence or unfinished work |
|---|---|---|
| Safety, existing services and protected campaign | Completed | API READY, ownership lock held, SQLite quick_check OK; 162,000 variants / 18,000 groups preserved |
| Arena architecture, provenance, grouped splits, registry | Completed for current synthetic schemas | Six datasets, serialized models, immutable source hashes, training-only transforms and frozen evaluations |
| Supervised completion, persistence, severity and cost research | Completed initial implementation and bounded campaigns | Genuine fits and policy evaluations; scientific performance varies and no broad superiority is established |
| Learned policy integration | Completed initial implementation | Risk admission, confidence/support gates, matched deterministic and no-trade controls |
| RL environment and first PPO training | Completed minimum milestone | Genuine simulator/accounting integration and saved PPO; larger, repeated-seed training remains |
| Tournament comparison, grouped uncertainty and replays | Completed core | 26 tournaments including one performance study; 50,223 correlated variants |
| Arena dashboard, console, registry and findings | Completed core | Persisted backend data and real browser workflows; future stretch interfaces remain |
| Durable workers and resource supervision | Partially completed | Native CPU/memory/wall bounds, cancellation, source capture, terminal records; arbitrary optimizer resumption remains |
| Data Foundry | Partially completed | Synthetic catalog/quality audits plus real observation-only chronology; longer/multiple-market data and migrations remain |
| Evolution Laboratory | Partially completed | Multi-seed selection, bounded sweeps, ablations and policy search; broader search and model families remain |
| Adversarial Arena | Partially completed | Stress evaluation, saved counterexamples and loss minimization; broader distributions and robust optimization remain |
| Recovery research | Partially completed | BUY hedge and inventory-backed SELL unwind evaluated; narrow one-intervention policies and weak conservative fill coverage |
| Research Director | Partially completed | Real bounded training/evaluation plans, rule-based follow-up experiments and persisted journals; general question-to-experiment planning remains |
| Explainability | Partially completed | Observable features, model/policy explanations, decision/replay evidence; richer RL attribution remains |
| Economics and realism | Partially completed | Cost/latency sensitivity and explicit assumptions; empirical execution and economic verification absent |
| Mandatory training/evaluation campaigns and reporting | Completed initial requirements | Baselines, neural fits, PPO checkpoint, competitions, stress studies and living reports exist |

### Every stretch category

All nine categories have at least some work, so none is wholly untouched.
Untouched or not yet demonstrated objectives within them are identified below.

| Stretch level | Status | Remaining / untouched objectives |
|---|---|---|
| 1 Model quality | Partial | More calibration, broader independent families, repeated RL seeds and stronger selection evidence |
| 2 Efficiency | Partial | Replay packing and profiling implemented; reusable feature caches, safe batching and full optimizer checkpoint resumption remain |
| 3 Better experiments | Partial | Stress, quality checks and minimization exist; wider systematic attribution and coverage remain |
| 4 Model families | Partial | Logistic/tree/ridge/MLPs/PPO exist; sequence models, alternative RL and validated ensembles untouched |
| 5 Tournament sophistication | Partial | Cross-execution scoring and uncertainty exist; seasonal leagues and model genealogy/promotion history untouched |
| 6 Autonomous research | Partial | Finite plans, adaptive rule-based follow-ups, journals and resource scheduling exist; general planning and automatic regression generation remain |
| 7 Advanced robustness | Partial | Confidence gates, recovery, latency and settlement revision audits exist; robust optimization and defensible broad break-even frontiers remain |
| 8 Platform maturity | Partial | Bundles, specifications, reproduction, verification and scheduling exist; dataset/model schema migrations, cold retention and wider monitoring remain; actual multi-day/reboot validation absent |
| 9 Ultimate research loop | Partial | Configured bounded workflows run end to end; arbitrary user questions do not yet become independently justified experiments automatically |

## Actual models and evaluations

**43 registered model artifacts; 42 fitted artifacts plus one deterministic
heuristic.** The fitted count includes a fitted constant baseline; it is not
42 neural networks or 42 independently validated strategies.

| Family | Artifacts |
|---|---:|
| Logistic regression | 15 |
| Classification MLP | 15 |
| Execution-cost MLP | 4 |
| Ridge cost/severity regression | 3 |
| Severity MLP | 2 |
| Tree | 1 |
| Fitted constant | 1 |
| PPO | 1 |
| Deterministic heuristic | 1 |

PPO trained for 4,096 transitions across 1,780 episodes: genuine proof of
training, not a mature RL campaign. Seven final model tests have been opened.
Multi-seed supervised fitting, validation selection, held-out prediction tests,
fresh paired policy challenges and source-bound inference reproduction have run.
There are six synthetic datasets (five independently constructed sources plus
one derivative). No production models were added by the recent scheduling work.
Superseded cost-v1 evidence is preserved and marked TARGET_REVISION_REQUIRED.

## Five important scientific findings

All P&L figures below are virtual synthetic outcomes. Confidence intervals are
95% intervals using underlying episode groups, not individual correlated variants.
Independent validation means additional verifier implementations/reexecutions;
it does not mean external scientific replication.

1. **Better cost prediction does not imply a better policy.** Cost-v2 MLP
   held-out RMSE was 0.08688 versus quote baseline 0.17186 over 92 groups;
   paired RMSE-change CI [-0.10743, -0.06166]. On 100 fresh policy groups,
   forecast gating reduced mean P&L relative to quote gating by 0.23340
   (CI [-0.36920, -0.11210]); residual losses were unchanged. Joint
   completion/cost gating added no measured benefit over completion gating.
   No-trade won the cost-policy downside score. Prediction and decision tests
   are separate persisted artifacts; this is improvement in a synthetic target,
   not observed execution forecasting.
2. **Persistence is not completion, and severity targets have trade-offs.**
   There were 456 incomplete executions despite predicted/labelled persistence.
   Fresh persistence gating lost 0.57769 versus arbitrage
   (CI [-0.84472, -0.31905]). Severity ridge improved RMSE 3.485 to 3.186,
   but worsened MAE 0.874 to 1.509 over 82 held-out groups. Target and policy
   audits therefore reject a blanket claim that these predictors improve risk.
3. **SELL unwind works mechanically; robust benefit remains unproven.**
   Initial 60-group results improved mean versus hold by 0.03173, but each
   policy filled only once. Two fresh 150-group cohorts produced SELL-minus-hold
   means +0.03216 and +0.02263; intervals touched/included zero. Only two of
   five requested standard-execution groups filled, and eight conservative
   requests produced zero fills. Verification covered 3,600 fresh replays,
   independent accounting and 28 frozen-policy reruns. The policy is narrowly
   bounded; no general recovery superiority or forced-liquidation guarantee.
4. **Settlement assumptions materially change sampled downside.**
   Fixed-model generator comparisons kept 2,100 pre-settlement pairs identical
   and changed payout in 48 groups. Classifier tail loss rose 0 to 0.476 and
   score fell 1.3530 to 0.8237. Mean-change CI [-0.13667, 0] and all other
   policy intervals included zero. Verification covered 4,200 replays, 45,696
   journal states, 4,391 bundle payloads and 24 exact inference reruns. This
   isolates settlement dependence, not general market-path robustness.
5. **Risk admission is not a post-fill loss guarantee.** Across 60 groups and
   432 decisions, no admission occurred after a cutoff, yet there were two
   drawdown, one daily-loss and 48 unmatched-exposure exceedances following
   fills. Replay/accounting checks support enforcement at admission; execution
   outcomes can move exposure beyond thresholds after admission.

Real-market evidence is much narrower: four public recordings, the longest
241 events across approximately 598 seconds. Its 120 polls produce 103 usable
paired windows, 17 stale exclusions, 72 training/13 validation/14 test/four
embargo windows, 60 unique quote shapes and two cross-partition repeats.
Independent receipt/metadata/embargo checks and full recomputation pass.
The two observation artifact identities reuse the same recording under different
code identities; they are not independent new samples. **Zero empirical fill
labels, payout attestations or real profitability evidence.**

## What autonomy genuinely works

Given an eligible configured dataset and a bounded plan, Midas can train
candidates, select using validation, evaluate frozen candidates on fresh matched
challenges, retain sources/checkpoints/results, and generate a persisted findings
journal without manual steps. A separate adaptive latency study chose 400ms
after a preregistered positive-score rule at 200ms and ran the new disjoint cohort:
the new score was -0.079, showing that the follow-up ran without manufacturing
a positive finding. This is rule-based autonomy, not unrestricted scientific reasoning.

The deployed persistent minute timer completed a two-child ingestion plan across
an actual API restart. A separate genuinely paused plan expired with no child
and a durable local alert. Source drift stops admission; stable keys prevent
duplicate admission. Failed/interrupted children require explicit recovery.
No actual reboot or multi-day elapsed execution has been demonstrated.

## Health, risks and current work

Live checks: API READY, checkpoint verified at 83,495 journal events; dashboard
HTTP 200; protected archive quick_check OK and ownership lock held. Registry
contains the counts above. **66 native jobs: 62 completed, two cancelled, two
failed; none queued/running.** Historical failed systemd units remain visible;
they are not running jobs or evidence that every past experiment succeeded.

Latest full backend gate: **529 passed, one skipped, one existing Starlette
deprecation warning** in 632.38 seconds. Latest frontend gate: **19 tests
passed**, type checking/lint/build passed; existing chart bundle warning remains.
After that full gate, the installer correction and schedule verifier focused
gate passed **nine tests**. The entire backend suite has not yet been rerun
for this installer-only correction.

Current engineering: complete scheduler deployment/parser reliability and
independent plan/browser verification, then preserve fresh evidence and advance
storage/retention work. Two installer defects were found in actual deployment:
quoted WorkingDirectory was rejected, and RuntimeMaxSec was ineffective for
oneshot services. Both have now been corrected; real systemd parser validation,
idempotent installation and active-timer checking pass. Effective start timeout
is one minute. Scheduler timer is active; no research campaign is running.

Arena occupies approximately 937 MB under the 1 GiB cap, leaving only about
130 MiB of headroom. Packing removed 2,098 files but added 1.9 MB: it reduced
watch pressure, not storage consumption. Watch-limit fallback is correct but
can be slow. Cold retention is still needed. Recording growth, broader alerts,
optimizer resumption, migration compatibility and long unattended operation
remain reliability risks.

## Remaining effort and assessment

Highest priorities: verified cold retention/storage budgeting; broader failure
monitoring and recovery; checkpoint/migration compatibility; stronger multi-seed
model and conservative-execution evidence. Then leagues/genealogy, justified
additional model families, richer explanation and general question-driven
planning. Preserve existing experiments and avoid reusing opened tests for tuning.

Best planning estimate: **30% engineering remains, roughly 15–30 focused
engineering hours**, with substantial uncertainty. Repeated training, real
multi-day operation and representative public-data collection require additional
elapsed time. This is an effort estimate, not a completion deadline or a promise
that empirical calibration can be produced inside that budget.

Midas is a substantial working synthetic research platform with the minimum
Arena milestone complete and useful negative findings. It is not yet mature
across the full original scope. Credible real-market economic evidence remains
far away: execution calibration, representative chronology and verifiable
settlement/economic assumptions are absent. No profitable live strategy is claimed.
