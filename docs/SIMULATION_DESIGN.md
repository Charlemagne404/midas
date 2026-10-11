# Discrete-event simulation

The scheduler orders `(virtual milliseconds, insertion sequence)`. Scheduling into the past is forbidden. There are no wall-clock sleeps or clock reads inside a simulation. A fixed synthetic epoch establishes model timestamps; seed-selected 0–2 ms jitter changes leg arrival times reproducibly.

The runner creates input market/book contracts, executes `BinaryStrategy.evaluate` and the independent `risk.assess`, schedules independent virtual submissions/acknowledgments/matches/faults/settlement, and audits the final exchange. An experiment includes initial conditions, risk state, limits, full timeline snapshots, orders, ledger, versions, seed and a SHA-256 of the canonical result. Storage IDs and application run times are outside that deterministic artifact.

## Matching assumptions

- Internal BUY limit orders, price priority, quantity precision 0.01 shares, supported positive tick prices and instrument minimum sizes.
- IOC consumes currently observed eligible asks and expires the unfilled remainder. GTC preserves a remainder that can be matched again explicitly; there is no queue rank or passive matching model.
- Orders reserve worst-case price/fee collateral before matching. Unspent reservations are released. Fill fees independently use nearest five-decimal rounding; notional uses a six-decimal upward bound.
- Liquidity is consumed, so repeated matching does not refill a price level. Legs are never atomic.
- Venue receipt, user acknowledgment and fills are separate events. A lost acknowledgment never triggers a blind duplicate submission. Cancellation takes effect when its event arrives; a prior fill remains valid.
- An emergency event cancels queued matching and releases reservations. Settlement cancels outstanding orders and prohibits future submissions.
- A complete payout vector must be supplied, nonnegative and summing to the contract's backing. Settlement is idempotent.

These are explicitly **simulated execution estimates**, not verified Polymarket fill mechanics. No queue probability, competing participants, endogenous impact, real network distribution, maker matching, sell orders or real collateral operation is modeled.

## Portfolio and audit

Available collateral, reserved collateral and position cost basis (locked collateral) are distinct. The ledger records every reserve, fill, release and settlement movement, including asset, order ID, quantity, execution price, fee and virtual timestamp. Inventory includes matched complete sets and unmatched shares. Realized P&L is credited at settlement; unrealized P&L uses best bid marks with zero when no bid exists. Maximum drawdown is measured at event marks from starting equity, not from a fabricated smoothed curve.

The independent auditor replays the journal, recomputes fill charges, checks each prefix for negative balances/inventory, rebuilds positions and P&L, verifies collateral conservation and reconciles open-order quantities/reservations. It does not call strategy pricing helpers. It shares only the explicitly documented simulator rounding convention. Corrupted-price tests demonstrate detection. This is accounting independence, not a second external implementation of exchange economics.

## Scenario library

43 executable scenarios span mathematics, execution, infrastructure and risk. The API catalog exposes description, initial expected behavior and category. Result artifacts preserve precise initial states and injected timeline events. Named cases cover fees/rounding, liquidity, depth/ticks, missing proof, V2 recognition, unhedged losses, partial fills, disappearing books, venue rejection, delayed/lost acknowledgment, duplicates, pending cancellation, stale/disconnected/untrusted data, persistence failure, checkpoint restore, stop/exposure/capital/drawdown/slippage/position constraints and split/early settlement.

Infrastructure fault scenarios establish deterministic invalid/untrusted starting states or inject a persistence/stop event. They do not emulate a real PostgreSQL process crash or physically disconnect the public endpoint. Separate adapter tests execute timestamp regression, delta reconstruction, snapshots and recording failures; integration tests cover actual SQL write failure. Exchange checkpoint cases serialize and reconstruct ledger and orders inside the same process. Full running-service/process recovery is deferred.

An expected virtual trading loss can pass invariants. A failed invariant creates a persisted result, incident and JSON failure artifact. Seed and full input/configuration permit reproduction without external market access.

## Replay

`market_data.recording.replay` processes JSONL in local receipt order through the same strategy engine. It rejects regressing receipt times and malformed/truncated tails, suppresses duplicate event IDs and exposes only already observed snapshots. Raw deltas invalidate affected books until the next normalized snapshot. It produces opportunity observations, not inferred historical fills. The bundled replay CLI demonstrates both a positive and rejected synthetic observation. Original source provenance is retained; the output explicitly states historical context.

## Milestone 2 fault laboratory and persistent execution

The original 43 scenarios remain. A separate `midas.paper.experiments` runner now uses
the production shared-account state machine with 15 selectable modes: no fault,
withdrawal, pause, lost/delayed acknowledgment, out-of-order delivery, changed fees,
invalidated payout, restart serialization, duplicate event, conflicting metadata,
settlement delay, corrupt ledger, malformed input and staleness. Each mode has a distinct
input/timing/invariant; fee/rule changes alter the actual market passed to the runner.
Malformed inputs are rejected before transition and retained in the timeline.

Seeded fixed/uniform latency, availability fractions and adverse tick movement are
explicit presets/parameters. Differential runs use identical data/strategy/seed and
compare hypothetical fills, theoretical profit, realized virtual P&L, fees, drawdown
and modeled lockup. Results are deterministic artifacts with configuration and input
commands. They never infer real fills or profits. Physical before/after-commit process
termination is tested separately against actual SQL, not represented by an in-process
serialization scenario. Independent integer reference checks cover terminal rounding
and fees; original independent ledger reconstruction remains in use.
