# Gate A checkpoint 043 — scan 46 and pilot continuity

**Captured:** 2026-10-16 02:48 UTC

**Mission status:** active; bounded discovery continues.

## Scan 46

The scheduled observer completed scan 46 at 02:30:17 UTC. Six public Gamma
queries returned 300 unique IDs. Of these, 178 met the supported same-condition
V1 binary-pair rule; 122 were excluded, with 72 excluded for unverified
augmented NegRisk semantics and 50 for unsupported outcome relationships.
The observer selected 40 markets; 33 passed the request/receipt quality gate
and seven had an empty ask side. The scan recorded zero positive top-gross
pairs and zero positive full-depth, minimum-notional, or fee-sensitive states
at the tested quantities. It used seven public HTTP attempts, no authenticated
requests, and no orders.

The cumulative v4 panel now contains 46 scans, 1,840 selected pair
observations, 1,600 quality-valid and 240 invalid states, 820 distinct
selected IDs, and zero candidate events. The maximum quality-valid top edge
remains -$0.001 per share. Repeated snapshots are correlated; the six-query
union and selected panel do not represent the venue-wide market universe.

## Fixed measurement pilot

The frozen v1 pilot has processed 15/48 scans: 497/600 selected slots are
quality-valid (82.8%), 103 are invalid, and 367 distinct selected IDs have
appeared. Its summary records one skipped scan sequence associated with a
scan-45 code-hash mismatch. The pilot has not been modified; its plan,
implementation, and control-cohort hashes remain pinned. The fixed stop is
2026-10-16 19:00:55 UTC. The rotating-versus-control comparison remains
descriptive and nonrandomized.

## Next action and limits

Let the pilot finish at its predeclared stop, then review missed scans,
selection strata, quality yield, control availability, and source hashes. The
separate eight-read discovery successor remains unrun live. Any decision to
replace the existing observer should follow a same-budget comparison; do not
run two collectors concurrently or reinterpret the bounded query union as a
venue census.

The immutable panel replay, independent source audit, and raw constraint
comparison are documented in [Gate B checkpoint
001](VERITAS_MISSION2_GATE_B_CHECKPOINT_001.md). No pilot rule or frozen
Reality campaign was changed for this checkpoint. See [inventory
054](VERITAS_MISSION2_RESEARCH_INVENTORY_054.json).
