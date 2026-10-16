# Gate D checkpoint 002 — bounded candidate source replay

**Captured:** 2026-10-15 18:02 UTC
**Mission status:** active; no strategy is promoted.

## Implemented

The economic qualification comparison is now version 3. When a quality-valid
positive top-ask row appears, it carries the snapshot's source-code digest and
is passed to a bounded source replay. The replay verifies the immutable
snapshot and analysis-event lineage, checks the embedded Gamma and CLOB source
payloads and their digests, re-derives the same-condition market identity,
reconstructs the saved books, and independently recomputes the best-ask pair
and sorted displayed-depth walk for the requested quantity. It compares that
arithmetic with the saved audit and records per-leg minimum and fee
sensitivities. Invalid, changed, oversized, or inconsistent source evidence
fails closed; candidate evidence is capped at 256 rows.

The replay explicitly records that request/receipt timing does not prove
independent sequence freshness, batch atomicity, order arrival, or fills. Fee
sensitivity still uses the shared versioned fee model. A replayed gross edge
therefore remains hypothetical and cannot promote a strategy.

The Arena qualification output is validated by the Research Director and
exposed through a bounded, digest-checked read-only finding endpoint. The
Veritas dashboard shows the gross-evidence and replay state and links to that
finding.

## Evidence and verification

The read-only v3 comparison over the current 29 finalized snapshots processed
1,160 selected market pairs / 1,034 quality-valid pairs / 536 distinct market
IDs. The greatest observed top-pair gross edge was -0.001 per share; there
were zero positive top-ask, full-depth, minimum-notional, single-match-fee, or
fragmentation-safe-fee states. It returned zero candidate rows and a complete
`NO_POSITIVE_CANDIDATES_TO_REPLAY` result. This comparison was not persisted as
a finding. Run `VERITAS-M2-ECO-QUAL-001-V3-RUN-fd9b0c1cdc06` has result digest
`e927ea7eecf94823b098d51746021f0e1915c55006de0de7118b51a6d6528e0b` and dataset
digest `fd9b0c1cdc0624555237fb7fe891bbe43ab2bef5e20fd343e24f4bdf69e4f777`.

The scheduled scan-28 Arena finding is separately persisted from v2:
`VERITAS-M2-ECO-QUAL-001-V2-RUN-c3decafe98ba`, result digest
`d51904d042634f961908fcb23c0ec9789ef0a82f840fb54a41a9a4382283f6c6`, finding
`veritas-qualification-v1-7fd5970007ea7a95`. It also has zero positive
candidates. The v3 result will first be eligible for scheduled persistence
after the new code has been committed and observed by a later Director cycle.

Targeted backend verification passed **40 tests** across candidate replay,
economic qualification, Arena qualification, Research Director, dashboard API,
and affected Arena API tests. The targeted Veritas frontend test passed (**1
test**). Ruff, Ruff formatting, strict Mypy for the changed Python modules,
Prettier, and `git diff --check` passed. Synthetic positive and tampered-source
fixtures exercise the replay path; no genuine positive market candidate has
exercised it.

No live orders, authenticated requests, or research findings were created by
the read-only comparison. The scheduled collector and source-analysis jobs
were not restarted or manually invoked.

Scan 29 and the current v3 comparison are documented in [Gate A checkpoint
026](VERITAS_MISSION2_GATE_A_CHECKPOINT_026.md) and [inventory
030](VERITAS_MISSION2_RESEARCH_INVENTORY_030.json).

## Operational follow-up — scheduled compatibility failure and recovery

The 18:15 Director cycle initially rejected the completed v2 scan-28 finding
because it lacked a replay object. Commit `9379985` now treats v2 results as
legacy and unreplayed while retaining strict replay validation for v3. The
persisted v2 finding passes the read-only validator after the fix. No v3
finding has yet been persisted; the next scheduled Director cycle is due at
18:45:20 UTC. See [Gate F checkpoint
016](VERITAS_MISSION2_GATE_F_CHECKPOINT_016.md) and [inventory
031](VERITAS_MISSION2_RESEARCH_INVENTORY_031.json).
