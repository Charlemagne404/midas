# Synthetic replay dataset v1

Every market and event in this directory is synthetic. No fixture represents an observed real arbitrage. Complete sets in `profitable` cost 9.5 virtual USD and pay 10 under the supplied scenario contract. `unprofitable` costs 10.3 for ten sets and is rejected. Receipt-ordered replay sees one instrument at a time and cannot evaluate a complete position before both snapshots exist.

Run `uv run python scripts/replay.py` from the repository root. Scenario execution is available through `/api/scenarios/{id}/run` and the Simulation Lab. Original fixtures use a fixed synthetic UTC epoch; demo dashboard observations explicitly regenerate those synthetic snapshots with current clocks.
