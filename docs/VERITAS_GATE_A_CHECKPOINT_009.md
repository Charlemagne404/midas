# Veritas Gate A checkpoint 009 — outcome-level source gaps and startup config

Captured 2026-10-15 00:07:43 UTC. This checkpoint completes the per-outcome
resynchronization issue map and inspects configuration carried by finalized
process-start records. It does not accept Gate A or change the Reality campaign.

## Protected-state check

- The protected campaign remains
  `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`.
  Its campaign configuration SHA256 remains
  `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`.
- The Reality recorder (`midas-reality.service`) and shadow worker
  (`midas-reality-shadow.service`) remained active, each with
  `NRestarts=0`, after the replay.
- The replay read finalized cataloged `.seg` files only. It did not read the
  active `.open` segment or write to the Reality worktree. No order was
  submitted, and no wallet or trading credential was used.

## Finalized-source replay

The reproducible aggregate is
[VERITAS_GATE_A_GAP_OUTCOME_001.json](VERITAS_GATE_A_GAP_OUTCOME_001.json),
analysis version `veritas-source-replay-v6`. It covers 1,886 finalized
segments (442,295,829 bytes) through ordinal 228,329 and verified 1,882 source
checkpoints. The source manifest SHA256 is
`960fa420cb69c5d9dad8d5d4738cc16ef0db5b86823b8fc54f85a3402dddb542`.
All 2,729 sampled decisions reproduced, with zero mismatches and none beyond
the finalized prefix.

## YES/NO issue mapping and source activity

The replay found 178 resynchronization gap records and 1,026 mapped issue
entries across eight campaign markets: 980 stale, 39 top-divergence, six
advertised-top-pending, and one timestamp-regression entry. No issue entry was
unmapped. Across the market-gap appearances, 509 affected both outcomes and
eight affected one outcome. These are overlapping market appearances across
gap records, not unique reconnects or unique source assets. The 980 stale
entries split evenly between YES and NO, and every stale market-gap appearance
affected both outcomes. The smaller divergence, pending, and timestamp issue
counts account for the observed one-sided cases.

The table uses S=stale, D=top divergence, P=advertised top pending, and
R=timestamp regression. Issue counts are entries, not unique events.

| Market | YES issues | NO issues | Gap appearances: both / one outcome | YES/NO interval p95 bucket | Freshness violations |
| --- | --- | --- | --- | --- | --- |
| 559687 | S79 | S79 | 79 / 0 | 30–60 s | 267 / 341 |
| 561251 | S80 | S80 | 80 / 0 | 30–60 s | 258 / 341 |
| 562828 | R1 | — | 0 / 1 | 2–5 s | 22 / 227 |
| 5674900 | S101, D3, P1 | S101, D3 | 104 / 1 | 30–60 s | 265 / 341 |
| 5674902 | S14, D1 | S14, D1 | 15 / 0 | 30–60 s | 33 / 45 |
| 5674915 | S77, D4 | S77, D5 | 81 / 1 | 10–30 s | 222 / 286 |
| 5675021 | S10, D11, P5 | S10, D11 | 21 / 5 | 2–5 s | 156 / 341 |
| 665205 | S129 | S129 | 129 / 0 | 30–60 s | 275 / 341 |

For every issue-bearing market, the recorded YES and NO update-interval
distributions had the same p50 and p95 buckets. In these eight markets the
source recorded 25,945 frames updating both outcomes and 52 updating one
outcome. Intervals spanning source discontinuities are censored; the p95
bucket summaries therefore do not measure the full distribution. Across all
markets, 1,730 of 2,729 scheduled decisions (63.4%) violated the frozen
freshness limit.

The pattern is consistent with pair-wide inactivity contributing to many
stale observations: markets 559687, 561251, 5674900, 5674902, and 665205 had
p95 update intervals in the 30–60 second bucket and 73–81% scheduled
freshness violations. The high-update market 562828 had 2–5 second p95
intervals and a 9.7% violation rate, while 5675021 also had 2–5 second p95
intervals but a 45.7% violation rate. This is descriptive association only;
activity does not explain every stale decision. Gap issue maps do not identify
which issue triggered a reconnect, and source receiver times do not establish
upstream venue timing or prove preventability.

## Finalized process-start configuration

The replay inspected 15 captured process-start epochs. Nine carried the
allowlisted configuration fields; none fell inside the campaign window. The
latest configured start before the campaign was ordinal 52,466 at
2026-10-14 14:34:56 UTC, about 6 hours 33 minutes before the campaign began.
Its recorded configuration was:

- Eight markets, discovery limit 50, stratified selection seed 20261014.
- Refresh 600 seconds, resynchronization 300 seconds, and stale threshold
  60 seconds.
- Queue size 32, segment duration 300 seconds, and near-expiry tag 2.
- Comparison window 15 seconds and timeout 5 seconds.
- Reconstruction version 4 and implementation SHA256
  `9231e11c969cc95af607d847c7d5aa32418a91c21152b214cf9f170d517c0c9f`.

This captured configuration is consistent with the campaign's eight-market
selection and recorded freshness/resync thresholds. It is context from the
last preceding process start, not proof that these settings caused any
individual gap or that they fully describe every live process state.

## Verification and decision

- Focused source replay tests: **5 passed**.
- Ruff check and format: passed.
- Strict mypy for `packages/midas/veritas`: passed.
- The v6 artifact contains aggregate market and outcome labels only; it does
  not export outcome asset identifiers or startup storage paths.
- No campaign or collector setting was changed. No future campaign, training
  job, or long-running Veritas process was started.

Current classification remains **insufficient independent evidence**. The
observed stale issue entries were overwhelmingly pair-wide, and source
freshness covaries with market update activity in this snapshot. There is no
demonstrated collector defect or causal trigger to repair.

## Next work

1. Align each finalized stale issue and scheduled decision to the preceding
   per-outcome source update; measure elapsed time against the recorded
   60-second threshold before considering any separate cadence experiment.
2. Design a separate, predeclared future-horizon and sampling study without
   changing Reality's labels, schedule, or campaign identity.
3. Revisit economics only if a positive quality-valid gross candidate appears
   in a broader finalized panel.
