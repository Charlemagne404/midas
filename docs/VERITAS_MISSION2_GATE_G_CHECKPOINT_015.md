# Gate G checkpoint 015 — select the latest receipted coverage artifact

**Captured:** 2026-10-16 05:53:56 UTC
**Mission status:** active; the source API resolves the latest receipted market-coverage report.

The API previously hardcoded coverage artifact 004 and ledger receipt H110. A1 coverage now reaches scan 52, so the source projection could remain behind the research evidence. `apps/api/veritas.py` now selects the highest numbered existing coverage artifact with a matching versioned path and analysis receipt in the ledger, then validates the exact file digest and analysis version. The artifact endpoint uses the same selection path. Older ledger fixtures with artifact 004/H110 remain supported through their matching receipt.

A direct in-process projection using the repository's Python environment returned `available`, 52 snapshots, latest scan `scan-20261016T053106Z-17b5d754b6c2`, 1,788 current-replay valid pairs, and zero positive top-gross pairs. The projected artifact file hash matches coverage artifact 006 (`a16d024aaadd8334fee1692a3b1e6767f412a7b587731bc3ce5a46b9f11e5f49`).

The Arena research source hash is formed from `packages/midas` and Arena modules; `apps/api` is outside that source set, so this dashboard-only edit does not change the source revision pinned by the completed scan-52 child. No code in the active Arena research package changed.

Automated API tests, browser checks, and a full Mission 2 regression were not run. The change remains in the `project/veritas` source checkout and is not deployed; no service or campaign was restarted. The scheduled 06:15:10 UTC Director reconciliation of scan 52 remains pending.

See [Gate A checkpoint 048](VERITAS_MISSION2_GATE_A_CHECKPOINT_048.md), [coverage artifact 006](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_006.json), and [inventory 070](VERITAS_MISSION2_RESEARCH_INVENTORY_070.json).
