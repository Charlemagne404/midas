# Market quality selection experiment 001

**Status:** preregistered exploratory evaluation; no model deployment authorized.

## Question

Can Gamma metadata available before the public CLOB book request rank markets
by whether the requested YES/NO pair will pass Veritas's frozen snapshot
quality gate? This targets measurement efficiency and market selection. It is
not a prediction of positive gross edges, fills, or profitability.

## Frozen data and split

- Read only immutable compressed snapshots from `data/veritas-observatory`.
- Freeze the source at scan `scan-20261016T213038Z-498756c46b83`; later scans
  are excluded even if available when the script is rerun. This yields 23
  same-revision scans in the captured archive.
- Include only `veritas-public-observatory-v2` snapshots with source code SHA-256
  `4ab2fa35be8d568a6e65a833f26f3c32e5b20f821bfb6e6c3ddcb9474bd6f060` and the
  `stratified-gamma-page-rotation-v2` frame protocol.
- Include only the rotating stratified cohort in the primary analysis. The
  stable random control is reported separately because its currently observed
  sample is too small and its IDs are periodically absent from discovery.
- Sort eligible scans by captured time. Use the first 70% of scans for training
  and the remaining 30% for evaluation. For training, retain each market's
  first selected observation. For evaluation, retain only the first
  post-cutoff observation for each market ID that never appeared in training.
- Use the recorded selection probability as an inverse-probability weight. This
  only represents sampling within the recorded bounded query-response frame;
  it does not make the result representative of the venue.

## Fixed comparison

The target is the existing boolean `audit.valid` label. Features are limited to
pre-book Gamma market metadata: log liquidity, log 24-hour volume, days to
expiry, spread, primary category, category source, liquidity band, expiry band,
and spread band. No book prices, outcomes, market IDs, later scans, or economic
edge values enter the model.

Compare one L2-regularized logistic regression (`C=1`, `lbfgs`, fixed seed) to:

1. A constant weighted training-prevalence predictor.
2. A deterministic random top-quartile selection.
3. A fixed metadata heuristic ranking higher liquidity first, then narrower
   spread.

Primary metric: inverse-probability-weighted Brier score on the held-out,
previously unseen markets. Secondary metrics: weighted ROC AUC, weighted
average precision, and quality-valid yield in the top quartile versus the
random and fixed-heuristic selections. No threshold or model is tuned on the
evaluation data.

## Interpretation and promotion rule

This is one short, selected, time-correlated validation window. Even favorable
results would justify only a separately preregistered prospective replication;
they would not establish market-wide performance or economic value. The model
will not change the frozen pilot, live selection, collector, campaign, or any
trading behavior. If held-out predictive performance does not beat the
constant baseline and the top-quartile yield does not beat random selection,
reject the model and do not integrate it.

The versioned result will report all included scan IDs and compressed-file
hashes, the train/test boundary, unseen-market counts, sampling weights,
metrics, fitted model details, limitations, and the fact that no orders were
submitted.
