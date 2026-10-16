# Gate E checkpoint 002 — market-quality prediction experiment

**Captured:** 2026-10-16 21:50 UTC  
**Gate status:** In progress; one bounded predictive experiment completed.  
**Branch base:** `1f8f1df9648d9ad78bac51421881d8009962abcd` (`project/veritas`)

## Question and method

Experiment `VERITAS-M2-MARKET-QUALITY-PREDICTION-001` tests whether pre-book
Gamma market metadata can rank selected markets by the same-snapshot
YES/NO-pair quality gate. It predicts measurement usability only. It does not
predict a positive price discrepancy, a fill, P&L, or profitability.

The question, source revision, chronological split, unseen-market rule,
inverse-inclusion weighting, model, and baselines were preregistered in
[experiment 001](VERITAS_MISSION2_MARKET_QUALITY_EXPERIMENT_001.md). The runner
and explicit bounded CLI are in
[`market_quality_experiment.py`](../packages/midas/veritas/market_quality_experiment.py)
and [`veritas_market_quality_experiment.py`](../scripts/veritas_market_quality_experiment.py).
It reads immutable compressed public snapshots and writes one standalone
result artifact; it makes no network calls and does not change collector
selection or the active pilot.

The pinned dataset contains 23 scans under one observatory source revision.
The first 16 scans supplied 470 first-seen training markets. The final seven
scans formed an out-of-time evaluation set of 175 first-seen markets not
present in training. Market IDs are disjoint across the split. The source
manifest records every compressed snapshot SHA-256 in
[the result artifact](VERITAS_MISSION2_MARKET_QUALITY_EXPERIMENT_001.json).

## Results

| Evaluation | Result |
|---|---:|
| Held-out markets | 175; 166 quality-valid and 9 invalid |
| Weighted base quality yield | 94.96% |
| Logistic model weighted Brier score | 0.03998 |
| Constant-prevalence baseline weighted Brier score | 0.05087 |
| Weighted ROC AUC / average precision | 0.894 / 0.993 |
| Model-ranked top quartile | 44/44 quality-valid (100.0% weighted yield) |
| Deterministic random top quartile | 40/44 quality-valid (90.53% weighted yield) |
| Fixed liquidity-then-spread heuristic | 39/44 quality-valid (86.56% weighted yield) |
| Positive gross candidates in the held-out markets | 0 |

The weighted Brier score fell by 0.01089 (about 21.4%) against the
constant-prevalence baseline, and the model's top quartile had higher observed
quality yield than either fixed comparison in this holdout. The inverse
selection weights apply only within the bounded Gamma query-response frame.
The Kish effective sample size before dependence adjustment is about 148;
this is not an independence correction.

## Interpretation and limits

This is a promising internal measurement-selection result, not evidence that
Midas is better at finding economic opportunities. The 175-market holdout
covers seven scans over a few hours, and market-category, selection-phase, and
time dependence remain. One short window does not justify a production filter.
Using the model to select only high-scoring markets could hide unusual or
low-liquidity opportunities. The model remains undeployed; future selection
must retain explicit randomized/stratified exploration and an independent
prospective replication.

There were no positive gross candidates in the evaluation data and no usable
candidate-specific execution labels. Economic strategy performance therefore
remains untestable on this panel. No model training process remains active.
No orders were submitted, and no live service, pilot, campaign, or recording
was modified.

## Verification

- Full Veritas backend suite: **232 passed** (one existing Starlette/httpx
  deprecation warning).
- Frontend suite: **29 passed**; isolated browser workflow: **1 passed**,
  including the prediction panel and hash-checked artifact endpoint.
- TypeScript typecheck, ESLint, Prettier, Ruff, production build, and strict
  Mypy for the new experiment module and CLI passed. The production build
  still warns that the main and chart chunks exceed 500 kB.
- Strict Mypy on the whole API module remains red on five unrelated existing
  issues at lines 90, 126, 160, 3141, and 3143. The complete repository
  backend suite was not run.
- The experiment artifact records a pinned data cutoff, preregistration hash,
  current analysis code hash, source file hashes, split, fitted coefficients,
  metrics, and non-deployment / no-orders attestations. After adding strict
  NumPy array types and fixing coefficient-ranking types, the analysis was
  rerun against the same immutable snapshots; metrics were identical. The
  current artifact SHA-256 is
  `dfe9bd6589071b4f43c79e39bfb2cda4896c189534a616453040b158cd8a2c02`; current
  analysis-module SHA-256 is
  `b9bbeeed3408ff9c668ef62066a2beba69338c9fd9483b9e3b8d822687a2c63d`.

## Next evidence gate

Keep the existing measurement pilot and broad stratified discovery active. If
the quality selector is reconsidered, evaluate it as a fixed shadow ranker on
future observations while retaining random controls; do not change the frozen
pilot or discard low-score markets. Require an independent prospective window
before integrating it into live selection. Keep economic strategy and
profitability claims deferred until genuine positive candidates and
execution-relevant outcomes exist.
