# Project Prometheus — final engineering report

**Status: controlled finalization in progress, 2026-10-14. This document is not
yet a completion declaration.** Pending acceptance evidence is identified below.
The owner ended open-ended stretch expansion and authorized a verified handoff
of mandatory functionality with explicit, justified exceptions.

## 1. Executive summary

Prometheus turns Midas into a working synthetic strategy-research platform:
versioned grouped datasets, genuine supervised and PPO training, saved models,
matched competitions, risk-admitted learned policies, durable bounded workers,
replays, independent accounting checks, research findings and an integrated Arena.
It also implements bounded search, stress research, missing-leg BUY and
inventory-backed SELL recovery, finite research scheduling, checkpoint continuation,
portable evidence, replay packing, cold storage and compatible dataset migration.

The platform has useful positive predictive results and important negative
decision-policy findings. None establishes real-market profitability. Synthetic
fills and public quote observations remain explicitly distinct. No wallet,
private key, real-money order submission or live execution is introduced.

Before final verification, estimates against the original full directive were
95% mandatory functionality, 55–65% stretch goals and 70% overall engineering.
These estimates are judgment, not measured task counts. Final acceptance will
follow the owner's revised completion criteria; deferred stretch work will not
be represented as implemented.

## 2. Original requirements and implementation status

| Original requirement | Implementation status | Final acceptance / exception |
|---|---|---|
| Existing infrastructure and protected campaign | Implemented | Current integrity/counts/owner checks pass; final health recheck pending |
| Training architecture and versioned provenance | Implemented | Dataset/feature/training/evaluation/registry boundaries; final full audit pending |
| Grouped splits, leakage controls, training-only transforms | Implemented | Grouped identities, frozen tests, timestamp guards, validation-only selection; current regression pending |
| Constant/logistic/tree/heuristic and PyTorch models | Implemented and trained | Actual artifacts, calibration/error diagnostics and policy evaluation |
| Persistence, unmatched severity and cost research | Implemented and evaluated | Mixed/negative results preserved; empirical targets absent |
| Learned-policy integration and hard admission rules | Implemented | Deterministic/no-trade controls; no bypass or hard post-fill loss guarantee |
| Midas-compatible RL environment and PPO | Implemented and trained | Real simulator/accounting; checkpoint reload and continuation verified |
| Matched tournaments, rankings, uncertainty and replay | Implemented | Episode-group uncertainty; explicit downside objective and ties |
| Arena dashboard and actual research data | Implemented | Final major-browser-workflow verification pending |
| Durable bounded research jobs | Implemented | Source capture, logs, resource caps, cancellation and terminal records |
| Crash recovery / checkpoint continuation | Implemented with limits | Interrupted jobs require explicit recovery; no arbitrary automatic replay of partial jobs |
| Native worker pause/resume states | Partially implemented | Schedule admission pause/resume and model checkpoint continuation exist; arbitrary running-worker pause/resume deferred |
| Data Foundry and public observations | Partially implemented | Catalog, audits and chronological public windows; representative empirical history deferred |
| Evolution / search / ablation | Implemented bounded subset | Validation selection and saved trials; broad search deferred |
| Adversarial stress and counterexamples | Implemented bounded subset | Saved failures, minimization and generator revision audit; broad robust optimization deferred |
| Recovery research | Implemented bounded subset | One-intervention missing-leg BUY/SELL/hold controls; broad recovery optimization deferred |
| Research Director | Implemented bounded subset | Configured sequences, rule-based follow-ups, finite timer and one evidence-selected template; production campaign deferred after prerequisite gate failure |
| Explainability | Partially implemented | Supervised validation diagnostics and policy traces; richer RL attribution deferred |
| Economic sensitivity | Partially implemented | Synthetic execution/cost/latency/settlement analyses; empirical calibration and broad frontiers deferred |
| Mandatory training/evaluation/report campaigns | Implemented and executed | Initial baselines, neural model, PPO, competition and stress evidence exist |
| Operational handoff and complete final evidence | In progress | This report, final regression/audit/UI/service checks and terminal jobs required |

Existing transient workers are not claimed to resume automatically after reboot.
Actual API-restart scheduling evidence exists; actual reboot/multi-day unattended
operation remains deferred. These exceptions are visible operating limits.

## 3. Architecture

The FastAPI API integrates Arena endpoints from `apps/api/arena.py`. Research
components live in `packages/midas/arena`; React views live in
`apps/web/src/Arena.tsx`. The existing Laboratory simulator, broker and accounting
are reused, with explicitly versioned research adaptations where required.

The main flow is:

1. Construct a source-bound dataset with grouped partition identities and labels.
2. Fit transforms on training observations, then train bounded eligible models.
3. Serialize parameters/checkpoints and retain validation metrics and curves.
4. Select candidates on validation only; do not tune on opened final tests.
5. Evaluate frozen policies over matched synthetic scenario/execution grids.
6. Store rows, decisions, broker journals, uncertainty and findings.
7. Inspect the evidence through API, registry, tournaments and replay views.

Native jobs use process supervision, CPU/memory/wall limits, immutable source
capture and atomic durable states. Stable admission keys prevent duplicate plan
execution. A finite user timer dispatches eligible schedules; it is not an
unbounded research loop. The API retains exclusive Laboratory archive ownership.

Storage uses content-addressed manifests and exact parameter/row hashes.
Replay packing stores checksummed compressed payloads in SQLite. The optional
cold tier preserves exact stores outside the active Arena cap. Storage migration
creates a new dataset identity while preserving canonical observations/labels.

## 4. Verified training and research inventory

**Pre-final-study inventory:**45 registered artifacts; 44 fitted plus one heuristic.

| Family | Artifacts | Interpretation |
|---|---:|---|
| Logistic regression | 15 | Repeated tasks/seeds, not independent strategies |
| Classification MLP | 15 | Completion/persistence/unmatched classifiers |
| Execution-cost MLP | 4 | Synthetic target forecasts |
| Ridge regression | 3 | Cost/severity tasks |
| Severity MLP | 2 | Synthetic exposure severity |
| Tree | 1 | Interpretable classification baseline |
| Fitted constant | 1 | Fitted base-rate baseline |
| PPO | 3 | Older proof plus same-seed parent/child lineage |
| Deterministic heuristic | 1 | Not counted as fitted |

The machine-readable [final research inventory](PROMETHEUS_FINAL_RESEARCH_INVENTORY.json)
contains model IDs, configurations, datasets, curves, metrics and limitations.
A readable [per-model table](PROMETHEUS_FINAL_MODEL_INVENTORY.md) records every artifact. Temporary browser/test roots are excluded; the production capacity campaign was never admitted.
Unopened test metrics remain unopened; lack of a final-test metric is explicit.

Seven synthetic dataset identities represent five source collections, a target
derivative and a storage migration.27 tournament artifacts include one performance
study and52,323 correlated variants.70 native jobs: 66 completed, two cancelled and two failed.

Dataset/tournament manifests contain4,185distinct synthetic episode identities:
2,986 dataset identities,1,359 tournament identities,160 overlap. This excludes
separate recovery/unwind collections and the protected Laboratory campaign.
Identity uniqueness does not establish independent realistic samples; generator
shortcuts, repeated shapes and repeated cohorts are documented limitations.
The protected Laboratory retains162,000 variants over 18,000 underlying groups.
Recovery adds 540 variants over 60 identities; three unwind studies contain4,320 variants
over 360 identities. The union across Arena datasets,tournaments,recovery and unwind
is 4,605 distinct synthetic identities,still not 4,605 independent real-market samples.

The production capacity plan was cancelled before native admission during
controlled finalization. Its coordinator failed the prerequisite regression gate.
Genuine fixture fits and verification remain preserved; no production models
or studies were added by this campaign.

## 5. Research findings

All P&L is virtual synthetic P&L. Confidence intervals use episode groups rather
than correlated variant rows. Separate verifier implementations and source-bound
reruns are independent engineering checks, not external scientific replication.

### Positive evidence and its boundaries

- Cost-v2 MLP held-out RMSE0.08688 versus quote baseline0.17186 across92groups;
  paired RMSE-change95%CI[-0.10743,-0.06166]. This is prediction improvement on
  a synthetic target, not empirically calibrated cost forecasting.
- A preregistered fixed classifier gate on100fresh stress groups achieved
  downside score0.569284 versus arbitrage0.050455. Mean virtual return was lower
  by0.232504,paired95%CI[-0.596131,-0.001942]. This restricted risk/return trade-off
  does not prove broad superiority or a statistically established score difference.
- A bounded two-seed Director found MLP validation Brier0.02922065 versus
  logistic0.03153976,exceeding its0.002practical tolerance. On fresh policy
  challenges, classifier policies tied; the validation gain did not improve P&L.

### Negative findings

- Cost forecast gating lost0.23340mean versus quote gating,
  CI[-0.36920,-0.11210]; joint cost/completion gating added no measured benefit.
- Persistence is not trade completion:456incomplete executions despite
  persistence; gating lost0.57769versus arbitrage,CI[-0.84472,-0.31905].
- Severity ridge improved RMSE3.485→3.186but worsened MAE0.874→1.509.
- Missing-leg hedge mean versus hold−0.0261,CI[-0.1094,0.0433]; benefit unproven.
- SELL-minus-hold means+0.03216and+0.02263on two fresh150-group cohorts had
  intervals touching/including zero. Eight conservative requests had zero fills.
- Settlement revision held2,100pre-settlement pairs identical, changed payouts
  in48groups,raised classifier tail loss0→0.476and reduced score1.3530→0.8237.
- PPO parent2,048transitions→child4,096cumulative;Adamsteps320→640and12tensors
  changed. All300paired outcomes and702decision checks were unchanged.
  Downside score−2.1682was below no-trade0. More optimization was not a benefit.

No learned policy establishes a general advantage across conservative execution,
scenario distributions and generator revisions. Positive mean P&L alone does
not defeat no-trade under the declared downside objective.

## 6. Recovery, execution and risk semantics

Missing-leg BUY uses known inventory/latest admissible books, terminal acknowledged
orders, unused allocated capital and bounded price/quantity constraints.
Inventory-backed SELL cannot sell more than owned inventory, supplies no new
capital, and follows modeled latency/liquidity/fees/settlement constraints.
Hold and no-trade remain controls. Requests may be rejected or never filled.

One recovery convention corrects consumed-depth bookkeeping for repeat orders
inside the isolated research runner. It is explicitly versioned and is not
claimed to reproduce historical Laboratory bytes. The historical campaign is
not rewritten.

Admission cutoffs prevented new admissions after stops, yet later fills caused
drawdown/daily/unmatched-exposure exceedances. Admission semantics are not a
hard guaranteed loss bound. Recovery studies show mechanics and accounting,
not guaranteed liquidation or general economic superiority.

## 7. Reproducibility and independent verification

The audit verifies dataset/weight/row hashes, matched coverage, replay result
cores and journal checksums. Additional studies use Decimal and rational ledger
checks, frozen-policy inference reruns and grouped paired uncertainty.

Recent examples:

- PPO study:2,100replays,25,128journal states,captured-source inference checks.
- Generator audit:4,200replays,45,696journal states,24exact inference reruns.
- Unwind robustness:3,600replays and28frozen-policy reruns.
- Dataset migration:1,593canonical rows preserved;4,779existing predictor outputs
  identical;95export payloads and isolated reconstruction verified.
- Completed planning fixture:1,375export payloads;1,260replay variants;
  13,104journal states;26inference reruns under66captured source files.

Fixture checks do not add production research samples. Some portable artifact
checks invoke workspace verifier scripts; a fresh dependency installation is
not claimed. Modern missing source snapshots fail export; explicitly reported
legacy incumbent source gaps remain a limitation rather than invented provenance.

## 8. Final tests and operational evidence

**Pending:** the final full backend regression and deployed UI/service/archive
checks. The production inventory is complete. No production capacity campaign
is required for wrap-up.

Completed checks:

- **Frontend:** 22 tests passed; TypeScript, ESLint and production build passed.
- **Current Python source:** Ruff passed for packages, API, scripts and tests.
  A broader scan found three import-order issues in immutable historical source
  captures. Their original evidence bytes are preserved.
- **Previous full backend gate:** 582 passed and one skipped. The subsequent
  gate finished with 599 passed, one failed and one skipped in 1,154.11 seconds.
  The failure was a transient SQLite SHM file disappearing during archive disk
  accounting. That failed gate is retained and never counted as passing.
- **Stabilization:** 19 tests passed in 16.03 seconds, including API shutdown and
  restart recovery. The Laboratory execution identity is unchanged. Corrections
  were committed as `89d0132`; a complete regression is now running.
- **Planning verification:** four tests passed; three inference refusal tests
  passed separately. Fixture inference and export checks are described above.
- **Full artifact audit:** seven datasets, 45 model artifacts, 27 completed
  tournaments and all 52,323 replay variants passed. Two historical partial
  tournaments were identified separately and preserved.
- **Recovery audit:** all 4,860 variants passed verification: 540 missing-leg BUY
  variants and 4,320 unwind variants. Each study's verification scope is recorded
  in `PROMETHEUS_FINAL_RECOVERY_AUDIT.json`.
- **Browser suite:** the initial run had four passes and one failure caused by
  temporary APIs sharing capped production recordings. After recording isolation
  was corrected, **all five workflows passed in 4.0 minutes**, including genuine
  Arena generation, training, evaluation, search and replay.
- **Protected archive:** SQLite quick_check passed; counts remained 162,000
  variants, 18,000 indices and 162,000 unique result IDs. The original exclusive
  owner lock was held and API health was READY in paper-only mode.

Final screenshots are preserved under `PROMETHEUS_FINAL_BROWSER_IMAGES`; prior
published documentation images were restored. RoadReach and Vanguard remain
active with their original processes. Neither service was restarted or modified.

The chart chunk remains 544 kB and produces a build-size warning; the build
passes. Final evidence files use the `PROMETHEUS_FINAL_*` prefix.

## 9. Known limitations and historical failures

- No empirical execution calibration, observed fill labels or real profitability.
- Public coverage is four short recordings; longest241events/~598seconds,
  103usable paired windows and17stale exclusions. Reused artifact identities are
  not independent public samples.
- Generator seed/settlement shortcuts and duplicated quote shapes limit realism.
- Watch quota fallback preserves correctness but can substantially slow research.
- Recording retention is manual under an explicit cap; automatic rotation deferred.
- Native interrupted jobs require explicit recovery; actual multi-day/reboot
  validation deferred. Schedule pause does not cancel an admitted child.
- Legacy model source gaps are explicit. Source/model compatibility cannot be
  assumed across arbitrary revisions.
- A planning promotion-threshold defect was found and corrected; the stopped
  pre-fix gate and stale proposal are retained. Deployment/final verification pending.
- Historical failed/cancelled/partial studies remain visible and do not count as
  completed experiments. Legitimate simulated losses are not software defects.

## 10. Deferred and intentionally excluded work

Valuable deferred work:more independent seeds/calibration,conservative recovery
coverage,broader monitoring,feature caching,richer RL explanations,more planning
templates and longer unattended operation. These are not silently declared done.

Future initiatives:new RL/sequence families,validated ensembles,seasonal leagues,
general question-to-experiment planning,broad robust optimization and extensive
empirical economics. They would materially expand this project's scope.

Intentionally excluded:live trading,wallets/private keys,real deposits/orders,
privileged host changes and unrelated infrastructure rewrites.

## 11. Operating and extending Midas

From `/home/charlie/midas`,inspect local service health:

```bash
systemctl --user status midas-api.service midas-web.service
curl --fail http://127.0.0.1:8000/api/health
```

Dashboard:`http://127.0.0.1:5173`;API docs:`http://127.0.0.1:8000/docs`.
Use the Arena tabs for dataset provenance,training/models,competitions/replays,
Director schedules and findings. Inspect job configuration/budget before starting.
Cancel native jobs through the existing Arena job controls; cancellation retains
partial evidence. Do not blindly resubmit interrupted or failed jobs.

```bash
.venv/bin/python -m scripts.verify_arena --full-replays --progress
systemctl --user status midas-arena-scheduler.timer
journalctl --user -u midas-api.service -n 50 --no-pager
```

Stop schedule polling if desired with `systemctl --user disable --now
midas-arena-scheduler.timer`;cancel an admitted child separately. The timer admits
only finite plans,under resource/source guards. Never start a competing Laboratory
writer while the API owns `data/laboratory-final`.

Preserve `data/arena`, `data/arena-cold`, `data/exports`,public captures/datasets,
the Laboratory archive,and the protected pre/post-recovery backups. Large research
data is intentionally outside Git;source commits are not a backup of that data.
Do not remove SQLite WAL/SHM files manually or regenerate data under old identities.

Further instructions:
[service operations](RELIABILITY_OPERATIONS.md),
[reproduction](ARENA_REPRODUCIBILITY.md),
[scheduling](ARENA_RESEARCH_SCHEDULING.md),
[planning](ARENA_EVIDENCE_PLANNING.md),
[PPO continuation](ARENA_PPO_RESUMPTION.md),
[cold storage](ARENA_COLD_RETENTION.md),
[migration](ARENA_DATASET_MIGRATIONS.md),
[unwind reproduction](ARENA_UNWIND_REPRODUCIBILITY.md).

Extend schemas with new identities and compatibility tests;keep train/validation/
test boundaries and grouped pairing intact. Do not promote models from exploratory
challenge tuning. Report null/negative outcomes and economic assumptions explicitly.

## 12. Next projects: Reality and Atlas

**Reality:**establish representative chronological public observations,verified
market-specific economic assumptions and defensible execution calibration where
lawful observable evidence permits. Separate hypothetical execution from empirical
labels. Start with measurement/provenance;software readiness is not profitability.

**Atlas:**define a separately bounded roadmap for broader research navigation,
experiment catalogs,question templates,comparative evidence and coordination.
Reuse Prometheus's artifact/worker contracts rather than restarting completed work.
Its precise scope should be agreed as a new project,not silently added here.

## Final acceptance record

Not yet signed off. Remaining essentials are tracked in
[controlled finalization plan](PROMETHEUS_FINALIZATION_PLAN.md). All running
research must finish or be safely preserved in documented terminal states before
the goal is marked complete. This section will record exact final tests,inventory,
service/archive evidence,repository commit/state and justified exceptions.
