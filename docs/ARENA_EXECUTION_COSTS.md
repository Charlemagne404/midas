# Execution-cost research

Datasets may opt into `retain_execution_costs` and an explicit `costs` configuration.
The original binary target remains available; the auxiliary continuous target is
`initial_position_friction_usd`, version `initial-position-friction-1`.

For the first risk-admitted position, the target sums:

- Positive fill-price slippage against each asset's observed best ask at admission,
  multiplied by its actual filled quantity. Favorable price changes do not offset
  adverse slippage in this definition.
- Actual simulated exchange fees in its fill ledger, counted once.
- Operating estimate per fill and redemption estimate per settled position,
  following the current analytical cost convention, including an empty settled
  position when the simulator charges one.
- Financing estimate from the position's integral of reserved plus locked capital
  over ledger timestamps through terminal simulation time, at the declared annual
  rate on a 365-day millisecond basis. Fees included in financed capital are not
  principal added to the target; financing is a distinct estimated expense.

The principal purchase cost, settlement gains/losses, collateral haircut, missed
opportunities and recovery actions are excluded. Zero fills can have low friction
while missing profit. These labels cannot substitute for a profit or tail-loss
objective.

Rows retain the observed price benchmarks, first-position ledger, declared costs,
label horizon and exact Decimal components. Loading verifies component arithmetic.
The feature schema remains the same 19 decision-time inputs: labels, future fills
and settlement do not enter it. Capturing cost evidence without changing costs
preserves financial result hashes. Other positions' expenses are excluded.

Typed `cost` jobs fit ridge or PyTorch `cost_mlp` regressors using the shared
checkpointed regression trainer, train-only scaling, grouped evaluation and
validation stopping. Predictions are nonnegative virtual USD, not probabilities;
classifier gates reject these model artifacts. Existing severity models retain
shares as their task and unit.

Controls include zero, training mean, and a quoted full-fill estimate: two fills
at the observed best asks under the documented exponent-one simulator fee curve,
plus operating/redemption estimates. It excludes future slippage and financing
and is neither an expected cost nor a loss bound. Cost assumptions are fixed
within the training dataset; inference under other regimes remains unvalidated.

The UI's cost dataset preset uses 0.01 virtual USD per fill, 0.02 per settled
position and annual financing rate 0.05. These are explicit synthetic estimates,
not claims about actual market charges. Real cost calibration, conditional cost
quantiles and policy integration remain further research.

## Version-one financing scope audit

An audit against the broker analytical cost calculation verified a missing scope
in 20 single-position development cases: broker reservation includes available
allocated capital while any action is pending, in addition to venue reservations
and locked capital. The version-one venue ledger does not record that envelope.
Amounts were small under this study's short horizons, but the target does not
fully reproduce broker financing. Existing artifacts are preserved and annotated
`TARGET_REVISION_REQUIRED`; final tests remain unopened.

The next version must record per-position exposure intervals, including pending
allocation reserves, and validate them against the broker formula before rebuilding
the dataset and retraining. Do not silently rewrite version-one data or present its
cost-model scores as complete broker friction estimates.
