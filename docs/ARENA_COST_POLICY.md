# First-position cost policy comparisons

`TournamentSpec.cost_gates` accepts a corrected cost-model ID, a virtual-USD
friction preference cap and a fixed research buffer. Each binding creates three
matched policies:

- Forecast: admit a full mathematical proposal when predicted mean friction plus
  the buffer is within the cap.
- Quoted: use the observed quoted full-fill control with the same cap/buffer.
- Scope: apply the same first-position, cost-regime and support restrictions,
  without a friction cap. This isolates restrictions from forecast value.

All policies require mathematical eligibility, empty position history, matching
explicit training costs and inputs within training ranges. They request only full
size; the original broker independently applies its hard risk rules. The cap
never changes mathematical edge or subtracts fees again. It is not an actual-cost
limit; the buffer is a research preference, not a calibrated confidence bound.
Low predicted friction may accompany failed fills, so numerical prediction quality
cannot establish policy value.

The ordinary no-trade, arbitrage, conservative and random controls remain in the
same tournament. Source-group comparisons include forecast versus quoted and
scope controls. Saved replays retain predicted/quoted costs, bounds, support,
rejection reasons, original financial ledgers and all actual outcomes. Scenario
costs come from the declared dataset/challenge before any economic perturbation.

The UI offers a fresh cost-policy challenge with fixed inputs exposed for review.
Automatic champion designation can be disabled by setting the minimum source
count above the study size. Research findings must report both mean P&L and
sampled downside, not equate low friction with high return.
