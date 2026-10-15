# Veritas Gate G checkpoint 001 — bounded backend and browser verification

Captured 2026-10-15 02:22 UTC. The original Gate G one-shot failures have been
rechecked in the Veritas worktree without operating the protected Reality
services or writing to its campaign.

## Backend suite

The earlier full run had 737 passes, 1 skip, and 2 setup errors. Both errors
came from the same planning fixture: the test wrapper stopped the nested job
after 180 seconds even though its declared wall budget was 300 seconds. The
wrapper was changed to the declared budget plus a 30-second shutdown margin.
The four-test fixture module then passed in 167.58 seconds.

The first full Veritas recheck is retained in
[backend recheck 001](VERITAS_GATE_G_BACKEND_RECHECK_001.log): 778 passed,
1 skipped, and 7 failed. The failures were test-environment assumptions:

- Five deployment tests inherited the Reality worktree's absolute storage
  path. Veritas' storage guard correctly rejected that path outside the
  current worktree. The fixture now uses a non-created path under the Veritas
  worktree and keeps its write and restart calls mocked.
- The discovery fixture used an expiry date that had passed. `discover` now
  accepts an optional clock value, defaulting to the current clock in normal
  use, and the test supplies its fixed fixture time.
- The migration coordinator test changed its working directory before a child
  process resolved relative `PYTHONPATH` entries. The full rerun now uses an
  absolute Veritas import path so the worker loads the same checkout.

The corrected full suite passed 785 tests with 1 optional PostgreSQL test
skipped in 19:07. See
[backend recheck 002](VERITAS_GATE_G_BACKEND_RECHECK_002.log). The three
failure groups also passed in focused checks before the full rerun.

## Browser checks

The original browser failure was an absent source-record label within five
seconds. Its original API response was not captured; the released `.seg` / `.open`
lookup fix remains the likely cause. The isolated Reality browser run passed
1 test in 7.8 seconds. Its API used temporary demo storage; the Reality views
read their evidence from the protected workspace, while Playwright intercepted
the operations GET/POST routes and raw-record request. It could not start a
service or read a recording segment. See
[isolated Reality browser run](VERITAS_GATE_G_BROWSER_ISOLATED_001.log).

The other five demo browser tests passed in 3.8 minutes in the default
temporary app environment; see
[browser suite recheck 002](VERITAS_GATE_H_BROWSER_002.log). The Arena browser
test now chooses the same configured Python interpreter as its test server,
which works across worktrees.

The backend source-record test uses temporary `.seg` / `.open` fixtures and
passed as part of the full backend suite. It exercises the segment rotation
lookup without reading protected source payloads.

## Protected-state check

- Protected campaign ID:
  `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`.
- `campaign.json` SHA256 remained
  `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`.
- No protected Reality service was restarted or sent an operation. No
  `.open` payload was read and no order was submitted.

## Decision

Gate G backend and isolated browser verification passed. The original browser
failure remains classified as likely caused by the release-fixed segment
rotation lookup, not confirmed from the missing response. Keep its failed log
and campaign evidence intact; no production campaign repair is warranted.
