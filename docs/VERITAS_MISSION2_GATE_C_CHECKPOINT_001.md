# Gate C checkpoint 001 — preregistered coverage pilot

**Status:** implemented and scheduled to activate on the first observer scan
completed after this checkpoint's source revision is committed.

## Protocol

`VERITAS-M2-COVERAGE-PILOT-001` is a 24-hour, measurement-only pilot with a
48-scan cap. It reuses the existing scheduled observer's six bounded Gamma
queries and one batched public CLOB books read; it adds no network requests,
does not select by price edge, and does not modify the frozen Reality campaign.
The first post-deployment scan enrolls as scan one. Historical snapshots are
not backfilled.

The primary measure is request/receipt-valid paired-book states divided by all
selected pair slots, with invalid observations retained in the denominator.
The pilot also records validity by the existing stable-control and
stratified-rotation roles, discovery exclusions, phase and stratum, distinct
market IDs, missed scan sequences, and immutable snapshot/analysis hashes.
The same-scan control/rotation comparison is descriptive: controls are not
randomized against rotating markets, and no causal or venue-wide claim is
allowed. Full protocol: [coverage pilot plan
001](VERITAS_MISSION2_COVERAGE_PILOT_001.json).

## Implementation and verification

The observer now writes a bounded, digest-checked event chain and summary under
`data/veritas-observatory/measurement-pilots/VERITAS-M2-COVERAGE-PILOT-001/`.
It verifies each event against the finalized snapshot and finalized v4
analysis event. Repeated scans are idempotent, the 24-hour window and 48-scan
cap are fixed, and pilot errors are surfaced in the latest summary without
stopping public observation.

Focused verification: **10 tests passed** across the new pilot and the mocked
observer flow. Ruff checks and formatting passed. No live service was started,
restarted, or manually invoked; the active timer will begin the pilot at its
next scheduled scan after commit. No study outcomes exist yet.

The pilot measures observation coverage and quality only. It does not measure
continuous quote availability, execution, fills, or strategy profitability.
