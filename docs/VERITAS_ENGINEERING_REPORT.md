# Project Veritas — engineering report

**As of:** 2026-10-15

**Branch:** `project/veritas`

**Result:** Gate G/H verification passed within the limits below; the read-only dashboard and research artifacts are ready for review.

## Delivered

### Evidence dashboard

The native Veritas page reads a bounded overview and a small allowlist of
versioned JSON artifacts. The API rejects unknown identities, symlinked files,
invalid object shapes, and artifacts larger than 512 KiB. It returns artifact
hashes and summary evidence without exposing raw market records or campaign
controls. The dashboard displays observed and derived measurements separately
from synthetic economics. Implementation and initial checks are recorded in
[dashboard checkpoint 001](VERITAS_DASHBOARD_CHECKPOINT_001.md).

### Replay and research support

The Veritas research code replays only finalized `.seg` catalog entries for the
latest aggregate funnel, verifies reconstruction checkpoints, and writes a
raw-free summary artifact. The new snapshot has a manifest hash and fixed
source-prefix bounds. The follow-up power tool is deterministic and reads the
committed research baseline; it does not read Reality runtime stores or alter a
campaign. The underlying evidence is linked from [Gate A checkpoint
012](VERITAS_GATE_A_CHECKPOINT_012.md) and [follow-up design draft
002](VERITAS_GATE_A_FOLLOWUP_DESIGN_002.md).

### Test portability and typing fixes

- Reality deployment fixtures now select a path inside the current Veritas
  worktree and keep write/restart calls mocked.
- The discovery test supplies a fixed clock value through the optional `now_ns`
  parameter, while normal callers continue to use the current clock.
- Playwright uses the configured or available Python interpreter consistently
  across worktrees. The Reality browser configuration uses isolated temporary
  storage and intercepts service operations and raw-record requests.
- The research-follow-up JSON reader validates object shape, and its completed
  job path narrows the optional tournament spec before use.
- Formatting and strict typing issues found during the broad check were fixed
  in the Veritas worktree.

These changes are scoped to reproducibility and test portability; the
protected Reality worktree and campaign were not changed.

## Verification results

| Check | Result |
| --- | --- |
| Full backend suite | 785 passed, 1 optional PostgreSQL skip, 0 failed; 19:07. The skip requires `MIDAS_TEST_POSTGRES_URL`. |
| Post-suite follow-up guards | 10 focused tests passed after the final `scripts/research_followup.py` guards. |
| Veritas dashboard API | 3 passed. |
| Frontend unit tests | 29 passed across 5 files. |
| Browser | 5 demo tests passed in the temporary app environment; 1 Reality UI test passed separately with operation and raw-record routes intercepted. |
| Python static checks | Ruff passed; Ruff format passed for 323 files; strict Mypy passed for 120 files. |
| Frontend static checks | ESLint, Prettier, and TypeScript typecheck passed. |
| Production build | Passed; existing advisory reports a 501.84 kB main chunk and 544.41 kB chart chunk after minification. |

Detailed logs are linked from [Gate G checkpoint 001](VERITAS_GATE_G_CHECKPOINT_001.md)
and [Gate H checkpoint 001](VERITAS_GATE_H_CHECKPOINT_001.md). The full backend
suite ran before the last two type-driven guards; their focused tests and the
full Mypy check ran after those edits. The Reality browser check validates the
read-only view with intercepted requests; it does not validate the real
operation or raw-record route end to end. A temporary-segment backend test
covers source-record lookup separately.

## Protected-state boundary

The protected Reality campaign remains
`adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46` and its
`campaign.json` SHA256 remains
`aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`. No
protected Reality service was restarted or sent an operation. The latest raw
funnel did not read an `.open` payload, and no order was submitted.

The original browser failure's API response is unavailable. The release-fixed
segment-rotation lookup is a plausible explanation, but remains unconfirmed.
The optional PostgreSQL integration path also remains unverified in this
environment. Those limits and the retained first-failure logs are disclosed
in the checkpoint documents.
