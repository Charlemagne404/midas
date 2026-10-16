# Gate G checkpoint 017 — project the scan-54 coverage receipt

**Captured:** 2026-10-16 06:48 UTC
**Mission status:** active; the source API projects the latest receipted A1 coverage artifact.

After ledger receipt H121 was added for coverage artifact 008, an in-process call to `market_universe_coverage_overview` selected that artifact and returned `available`. The projection reports 54 snapshots, latest scan `scan-20261016T063125Z-a83f9f475d62`, 1,853 current-replay valid pairs, zero positive top-gross pairs, and verified source hashes. Its file digest matches artifact 008 (`85a5e630621329463ee205470ce88b2655758b6e6039fc3bbc81a6db2f9b3e30`).

This verifies the repository projection against the ledger and saved artifact. Automated API tests, browser checks, and deployment remain outstanding. No running service was restarted and no Arena research package changed.

See [Gate A checkpoint 050](VERITAS_MISSION2_GATE_A_CHECKPOINT_050.md), [coverage artifact 008](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_008.json), and [inventory 073](VERITAS_MISSION2_RESEARCH_INVENTORY_073.json).
