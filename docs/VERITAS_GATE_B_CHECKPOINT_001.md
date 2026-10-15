# Veritas Gate B checkpoint 001 — execution break-even thresholds

Captured 2026-10-15 00:40 UTC. This checkpoint adds a versioned threshold
analysis to the controlled synthetic capacity study. It uses no Reality quote
data and does not change any campaign.

## Protected-state and runtime check

- The release checkout and `origin/main` remain at
  `f968095feb9c591de38fe12d7493224425f62f3a`; the release tag resolves to that
  commit.
- The protected Reality campaign remains
  `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`, with
  `campaign.json` SHA256
  `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`.
- The recorder, shadow worker, Reality API, Reality web, and development web
  were active with `NRestarts=0` in the read-only service check. No Reality
  process was started, stopped, or restarted.
- This experiment used controlled inputs only; it did not read a Reality
  recording or campaign database. No `.open` segment was read, no campaign
  data was written, and no order was submitted.

## Method

The reproducible artifact is
[VERITAS_GATE_B_EXECUTION_BREAK_EVEN_001.json](VERITAS_GATE_B_EXECUTION_BREAK_EVEN_001.json),
analysis version `veritas-execution-break-even-v1`. It adds a per-attempt model
with three mutually exclusive outcomes:

- A completed pair with probability `p` and explicit hypothetical net P&L `G`.
- One unmatched leg with probability `q` and explicit loss `L`.
- No fill with probability `1 - p - q` and zero P&L.

The break-even relation is `p × G = q × L`. It reports the minimum matched
completion rate for candidate unmatched-event rates and the converse maximum
unmatched-event rate for candidate completion rates. These are algebraic
sensitivities, not probabilities estimated from data.

The completed-pair calculation compares a single-match rounding case with a
fragmentation-safe fee upper bound. The unmatched case assumes one leg fills,
loses at binary settlement, and cannot be recovered. It includes that leg's
financing and operating cost, with zero recovery value. The source book, fee,
settlement, and cost inputs are synthetic and remain those of the parent
[controlled capacity study](VERITAS_GATE_B_CAPACITY_001.json).

## Results

Across the size grid, four of seven full-depth sizes had positive worst-outcome
P&L under the single-match rounding case; none of seven had positive P&L under
the fragmentation-safe fee bound. Under half displayed depth, three of six
eligible sizes were positive in the single-match case and none of six were
positive under the fragmentation-safe fee bound.

For the 100-share-per-leg, full-depth sensitivity:

| Fee case | Completed-pair worst-resolution P&L | Adverse unmatched-leg loss | Break-even result |
| --- | ---: | ---: | --- |
| Single-match rounding | +1.4178 USDC | 50.1959 USDC | 35.4039 matched completions per unmatched event |
| Fragmentation-safe upper bound | -0.7822 USDC | 50.1959 USDC | No positive completion threshold |

Under the single-match case, an assumed 1% unmatched-event rate requires a
35.40% matched-completion rate and leaves probability mass for no fills. An
assumed 5% unmatched-event rate requires a 177.02% matched-completion rate and
is infeasible because the two outcome rates cannot sum above 100%. These rates
are examples from the declared sensitivity grid; no real rate is known.

At half depth and the same 100-share quantity, the completed-pair P&L is
negative under both fee cases. No positive break-even threshold is available.

## Decision and limitations

The favorable single-match result is fragile: one adverse unmatched event
requires about 35.4 completed pairs to break even at this synthetic size. The
more conservative fee-fragmentation bound is already negative before adding
any incomplete-position loss. This does not establish that the real venue
offers the synthetic quotes, that either leg would fill, or that any
completion rate is achievable.

Do not promote the scenario to a policy or strategy. The next useful use of
this analysis is candidate-specific sensitivity if a quality-valid positive
gross observation appears; until then, continue improving prospective public
measurement design and market coverage.

## Verification

- Focused Veritas tests: **40 passed**.
- Ruff lint and formatting checks: passed.
- Strict mypy for `packages/midas/veritas`: passed.
- The generator completed synchronously in about 0.2 seconds; the focused
  suite completed in 1.68 seconds. The aggregate JSON artifact is 158,875 bytes
  and contains no raw observations.
- No long-running research job or service change was made for this experiment.
