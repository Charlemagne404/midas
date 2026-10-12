# Bounded missing-leg recovery research

The first recovery runner compares one ordinary risk-admitted initial position
followed by holding or one missing-leg buy. It also retains a no-trade control.
It supports generated synthetic binary scenarios only. Selling and unwind
ledger entries are not implemented by this runner.

A recovery decision uses the latest observed books and known own inventory.
Initial submit/match/ack actions must finish; existing orders must be acknowledged
and terminal. Unknown acknowledgments, stale quotes, changed market identity,
emergency stop, drawdown/daily/cumulative-loss cutoffs, or insufficient remaining
capital force holding. Live broker limits are used, including exposure and
slippage limits. The unmatched-quantity admission stop has a documented recovery
exception: the requested missing-side quantity cannot exceed the residual.
No new position or external capital is granted.

Recovery spends only unused capital already allocated to the original exchange
portfolio. Default additional reservation is at most five virtual units and the
observed price ceiling is 0.75. Quantity, original allocation, exchange minimum
order size, tick rules and the existing fee reserve constrain the request.
The order follows the broker's existing submit, match and acknowledgment events,
including submission/processing latency, jitter, capacity fraction, adverse
ticks, faults, market changes and settlement. Future fills are not assumed.

The isolated research runner normalizes used liquidity to unadjusted venue
prices after adverse fills. The legacy broker indexes those fills by adjusted
prices; retaining that mapping for a second buy could reuse consumed depth.
Both hold and recovery runners apply the same bookkeeping convention. The
production broker code, financial ledger schema and historical archives are
unchanged. This convention is explicit in the recovery runner version and
experiment limitations; it is not claimed as a replay of old archive bytes.

The unused allocation and residual-size restrictions bound collateral and
inventory expansion. They do not guarantee realized profit or maximum net loss.
Buying the missing leg can reduce profit when the already held leg would win.
Partial fills, rejected or delayed recovery, financing, operational costs and
remaining unmatched inventory are retained in actual simulated outcomes.

## Supervised studies

`JobSpec(kind="recovery", recovery=RecoveryStudySpec(...))` uses existing Arena
worker supervision, cancellation, pressure monitoring, source snapshots and
artifact caps. The default study uses 60 source groups, seven families, three
execution assumptions and three policies: 540 correlated variants. Variants are
grouped by underlying family/seed for paired confidence intervals. Recovery
budgets remain fixed; results never automatically refit a model or widen them.

Artifacts are at `data/arena/recoveries/RECOVERY_ID`: preparing record, rows,
compressed complete replays and completed manifest. API:
`GET /api/arena/recoveries/RECOVERY_ID`. The Research Director view offers a
bounded comparison and displays persisted mean, downside score, worst outcome,
actual recovery requests, filled shares and grouped uncertainty. Findings keep
execution caveats visible. Overlap with registered datasets or opened studies
is rejected.

## Saved evidence verification and export

Run `.venv/bin/python scripts/verify_recovery.py RECOVERY_ID --output report.json`
to check every saved core and journal hash, complete matched coverage, actual
orders against residual/price/reservation bounds, equal initial order ledgers,
leaderboard arithmetic and the source-group bootstrap interval. This audits saved
evidence; it does not independently reexecute every broker transition.

Export a completed study with `.venv/bin/python scripts/arena_bundle.py --recovery
RECOVERY_ID --output /path/to/new-bundle.tar.gz`. The exporter first verifies the
study, then includes replays, findings, captured worker source and checksummed
payloads. It refuses to overwrite an existing bundle.
