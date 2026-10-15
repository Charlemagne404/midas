# Gate G one-shot test failure forensics 001

## Backend timeout finding

The operational Gate G backend regression log reports 737 passed, 1 skipped,
and 2 errors in 1,443.80 seconds. Both errors are setup failures from the same
module-scoped `completed_plan` fixture. Its nested Arena job was killed by
`subprocess.run(timeout=180)` while the fixture's `JobSpec` declared
`max_wall_seconds=300`.

The relevant test files have the same SHA256 in the protected Reality and
Veritas worktrees before this correction:

- `tests/arena/test_evidence_study_verification.py`:
  `262511537f0f7fdb8944b1c118f3eb138b9473af93a25dd4c93bd8851146064e`
- `tests/arena/test_research_planning.py`:
  `8762349a1722892c031a767a7770f96850b72cc024886e8ff622f688d1eaf1d9`

An isolated run from the Veritas checkout completed the same fixture and its
verification tests after the timeout correction: 4 passed in 162.80 seconds,
including 142.59 seconds in the nested plan job. The job completed all four
sweep trials and both 630-row challenge stages. The earlier 180-second wrapper
left little margin for CPU contention during the longer Gate G suite; the
reproduction does not identify an Arena logic failure.

The Veritas test now sets the process timeout to the job's declared wall budget
plus 30 seconds for process startup and shutdown. That gives the worker its
full 300-second budget to report its own timeout. The production Arena code and
the protected Reality checkout were not changed. The full Gate G backend suite
has not been rerun after this test-only correction.

## Browser failure finding

The first operational Gate G browser run reports 5 passed and 1 failed. The
Reality replay test did not find the exact text `Checksum-verified raw input
record` within its five-second assertion window after requesting the source
record. Before the same-worktree recheck, commit `c96a031` changed the API
reader to try both `.seg` and `.open` for the referenced segment. A shadow
record can retain its eventual `.seg` name while the recorder still owns the
matching `.open` file; the previous reader handled the reverse transition but
did not find `.open` when the reference named a missing `.seg` file. The new
reader is covered by `tests/test_reality_dashboard.py`, which renames the
referenced `.seg` file to `.open` and verifies that the source-record request
succeeds. That focused test passed 5 cases in 0.73 seconds. The subsequent
same-worktree browser recheck passed in 26.8 seconds, and `c96a031` is an
ancestor of the Veritas release baseline.

The segment-rotation lookup bug is the likely cause and is fixed in the release
baseline. The failed run's error-context artifact was not available, so the
original API response cannot confirm that attribution. No additional Veritas
browser code change is indicated. Keep the browser part of Gate G provisional
until it is checked in isolated staging with the Reality operations endpoint
disconnected from the protected user services.

## Scope and remaining work

All inspection of the operational service logs and test sources was read-only.
The backend reproduction used a temporary `/tmp` artifact root from the Veritas
checkout. No Reality campaign, raw source, journal, or service was modified or
restarted. No orders were submitted.

This does not make Gate G green. Re-run the backend fixture after the timeout
correction as part of a bounded Veritas verification pass. Separately classify
the failed shadow-canary service, which reported
`Final source segment integrity/continuity mismatch`; do not repair it by
writing to the protected Reality store.
