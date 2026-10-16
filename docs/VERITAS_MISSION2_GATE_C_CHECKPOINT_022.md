# Gate C checkpoint 022 — cursor-safe shadow snapshot and bounded canaries

Captured 2026-10-16. All canaries used an isolated temporary journal; the
Reality worker and its frozen campaign were not restarted or modified.

## Resume-boundary validation

Added `packages/midas/veritas/shadow_runtime_snapshot.py` and the read-only
export command `scripts/export_veritas_shadow_runtime_snapshot.py`. Snapshot
capture verifies the campaign identity and plan digest, journal checkpoint
digest, finalized segment and catalog hashes, framing/checksums, and that the
source ordinal matches an exact record boundary at the stored byte offset.
The last check was added after review found that a range-only ordinal check
could accept a cursor in the middle of a record.

The exporter captured the live frozen campaign's committed SQLite runtime in
read-only mode. Its campaign ID and plan hash match the protected campaign;
the snapshot's cursor is ordinal 524953 at offset 83447 in finalized segment
`00000000000000524898-39d15b1877bc459887f4083483d3f177.seg`. No campaign or
journal write occurred. Five dedicated boundary and read-only tests passed.

## Bounded reader canaries

Canary 002 attempted 32 finalized segments under a 5% CPU quota, 384 MiB
memory cap, and 20-minute wall bound. systemd terminated it at the configured
limit after 76 CPU seconds; no final result or after-runtime snapshot was
written. This is a failed bounded attempt, not a throughput measurement.

Canary 003 processed the next eight-segment window under a 10% CPU quota,
384 MiB memory cap, and 10-minute bound. It consumed ordinals 529093–530747
(1,655 records; 1,393 frames) in 84.69 seconds of process wall time and 8.47
seconds of process CPU. It recorded 56 decisions, 336 observations, and 3
observed versus 221 censored follow-ups in its isolated journal. systemd
reported success, 12.9 CPU seconds, and a 131.4 MiB memory peak.

The canary replay advanced its decision clock with recorded timestamps. It
measures bounded full-consume replay work; it does not reproduce real-time
lag, prove live catch-up, provide fresh observations, or establish prospective
follow-up yield. It used Veritas branch code against the campaign definition
(`--allow-current-code`), verified the campaign-pinned source files, and did
not verify that the branch implementation matches the campaign code hashes.
Do not use this result to justify a frozen-worker restart or deployment.

Artifacts: private run manifests and results under
`data/veritas-canaries/shadow-reader-catchup-002/` and
`data/veritas-canaries/shadow-reader-catchup-003/`; read-only live snapshot at
`data/veritas-canaries/shadow-runtime-readonly-003/live-runtime.json`.

## Verification and decision

The focused snapshot and Reality shadow tests passed (21 total), as did Ruff,
Ruff formatting, and strict Mypy. Keep the cursor-boundary validation and
bounded replay tooling in the branch. Continue investigating source lag under
isolated limits; live recovery still needs an approved successor lifecycle,
continuity checks, and a safe method to retain complete progress across
interruptions. The frozen campaign remains untouched.
