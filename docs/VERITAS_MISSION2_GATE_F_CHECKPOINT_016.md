# Gate F checkpoint 016 — legacy finding recovery

**Captured:** 2026-10-15 18:20 UTC
**Mission status:** active; no strategy is promoted.

## Scheduled source and Director cycle

The 18:10 finalized-source replay completed at 18:14:33 UTC. It processed 127
segments / 33,535,604 bytes in the bounded batch; cumulative progress is
2,907/4,023 finalized segments, with 1,116 / 316,707,896 bytes pending through
ordinal 378,514. The summary digest is
`15430b315fbab8ffb534534ba8ee6209114537cbf4142510cf5aaa8d81151280`; the
summary file digest is
`f952ea84a90c84f84cb06bcfdcbaf4c635bf76363f1e41ff91e2802277f1d90e`. It did
not read the active `.open` segment. The source prefix still reports zero
positive top-ask and full-depth states.

The scheduled Director service ran 18:15:21–18:15:49 UTC and exited with OS
status 0. It validated scan 29's snapshot and v4 event as `READY`, then failed
to reconcile the completed scan-28 Arena finding because the finding is
version 2 and predates source replay. The new validator incorrectly required a
v3 replay object, leaving the manifest `UNVERIFIED` with
`Finding validation failed: Qualification result has invalid gross-candidate
replay evidence`. No scan-29 Arena job was admitted and no new finding was
written. The manifest still refers to the already completed scan-28 job as
`QUEUED`; the underlying job record remains `COMPLETED`. There are no running
or queued Arena jobs in the Veritas Arena root.

## Corrective change and verification

Commit `9379985` makes the Research Director version-aware. A v2 finding with
complete candidate-pointer counts is accepted and explicitly projected as
`REPLAY_NOT_AVAILABLE_LEGACY_V2`, with replay completeness false. V3 findings
still require complete replay evidence and reconciled counts. The same commit
makes the dashboard tolerate historical hypothesis rows missing top-level
`status`, `decision`, or `result.status`, without editing historical ledger
records.

The persisted scan-28 v2 finding now passes the Director's read-only
`_finding_summary` validation: zero candidate rows, replay unavailable for
legacy v2, incomplete. The changed Director and dashboard API suites pass **18
tests**; strict Mypy, Ruff, formatting, and the targeted Veritas browser test
pass. The full frontend suite passed **29 tests**; TypeScript, production build,
ESLint, and Prettier passed. Vite retained its existing large-chunk advisory
for the 501.86 kB main and 544.41 kB chart bundles.

The first full browser run passed five tests and failed two. The Veritas
workflow now passes in a targeted rerun after the fix. The remaining Reality
browser test expects a monitored market while its isolated demo setup exposes
zero; it does not use frozen production campaign data. No full browser rerun
was performed. All E2E database and Arena files were isolated under `/tmp`.

## Current state and next cycle

The current genuine panel remains 29 scans / 1,160 selected pairs / 1,034
quality-valid pairs / 536 market IDs, with maximum top-pair edge -0.001 per
share and zero positive gross, depth, minimum, or fee states. The v3 comparison
is read-only and unpersisted; the scan-28 finding remains v2. The fix is
committed before the next scheduled Director cycle. Timers remain active; the
next observer, source-analysis, and Director runs are scheduled for 18:30:45,
18:40:08, and 18:45:20 UTC. No manual Director tick, retry, service restart,
or campaign modification was performed.

See [inventory 031](VERITAS_MISSION2_RESEARCH_INVENTORY_031.json) and the
[stable current inventory](VERITAS_MISSION2_RESEARCH_INVENTORY.json).

## 2026-10-15 18:22 UTC post-fix regression

The combined affected backend set passed **43 tests** across candidate replay,
economic qualification, Arena qualification and API, Research Director, and
dashboard API. Strict Mypy, Ruff, and formatting checks also pass for the
changed backend modules. The targeted Veritas browser test passes after the
legacy-ledger projection correction. One existing Starlette/httpx
TestClient deprecation warning remains. See [inventory
032](VERITAS_MISSION2_RESEARCH_INVENTORY_032.json).
