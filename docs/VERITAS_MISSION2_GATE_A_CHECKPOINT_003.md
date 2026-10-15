# Veritas Mission 2 Gate A Checkpoint 003 — Finalized Source Replay

**Captured:** 2026-10-15 06:51 UTC  
**Branch:** `project/veritas`  
**Protected Reality commit:** `714f824`  
**Status:** Initial bounded source batch passed; catch-up continues.

## Scope and safeguards

This checkpoint adds incremental analysis of the frozen Mission 2 Reality
recording. The reader is pinned to campaign
`adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46` and
campaign-file SHA256
`aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`. It reads
numeric finalized sidecar catalogs and their `.seg` files only. It never opens
the active `.open` file, writes to the Reality source root, or controls the
Reality recorder.

Every run revalidates the pinned campaign and code identity, scans a bounded
catalog set, verifies the processed sidecar prefix and source ordinal, and
handles only a bounded suffix. New segments are hash-checked and replayed
record-by-record against their catalog count, kind histogram, and ordinal
range. Empty finalized headers are validated but skipped as no-record inputs;
this prevents a later empty segment from changing the replay cursor or
reordering a same-ordinal nonempty segment.

The analyzer restores `Context` from an atomic state snapshot and retains
campaign-window counts across runs. Each segment gets a versioned immutable
event with campaign, code, source-catalog, prefix, and post-state hashes. The
event is exclusively created before the state cursor advances. A crash between
those writes causes the segment to be replayed and compared with its existing
event before state advances, without applying it twice. A changed processed
catalog prefix or analysis code hash fails closed.

The user service caps each run at 128 replayable segments or 32 MiB, each
segment at 16 MiB, source catalog metadata at 32 MiB/100,000 entries, state at
24 MiB, and source-analysis artifacts at 256 MiB. Systemd applies a 5% CPU
quota, 256 MiB memory limit, idle IO, `Nice=19`, a 10-minute timeout, no new
privileges, read-only home access, and write access only to
`data/veritas-observatory/`.

## Initial live batch

The first systemd run started at 06:49:51 UTC and completed at 06:51:03 UTC
with exit status 0. It processed 128 replayable segments totaling 5,646,827
bytes through source ordinal 7,048. At the run's catalog snapshot there were
2,681 replayable segments, two empty finalized headers, and 2,553 replayable
segments (648,266,578 bytes) pending. Systemd recorded 3.63 seconds of CPU,
110.6 MiB peak memory, and no swap.

This initial source prefix contained zero campaign-window frame records,
quality-valid paired states, or positive states. It is a replay-bootstrap
result, not an economic observation. Readiness is
`catching_up_finalized_source`.

The source-analysis identities are:

- Analysis code SHA256: `9f9e2249b49dd1cb10c11713aa2683567aa9cf0914c3ed2b08cf8e3fea25ebf8`
- Processed catalog-prefix SHA256: `8620e6a909ddf0a10e024056de6fe965709d507a83378f96b1e38ea1e04ca8d6`
- Last immutable event SHA256: `a5e7aa9e45a64f3c8cd0ad8acd9b1846b233ee518c87fbfdbbad3d229f358b71`
- Last event file SHA256: `564f16ae93ca9f1c0706b7b70be4c8037d55cca92edc4bfbcbf9667a7a094575`
- Summary digest: `6022714ccd6505bcbf5de5ddd8e9f3cac2564d2d1f2a79a091cb96d6c8011cc6`
- Summary file SHA256: `28bdd45ed73396e28e801a005cb2093f0a5818de63ff3c9d5da68250ce88404e`

The summary is at
`data/veritas-observatory/source-research-summary.json`; events are under
`data/veritas-observatory/source-analysis-events/v1/`. The separate API panel
reports source-segment progress and readiness without including the local
Reality source path.

## Recurrence and preservation

`midas-veritas-source-analysis.timer` is active on an offset 30-minute UTC
schedule at minutes 10 and 40, with up to 60 seconds of randomized delay. It
runs separately from the public snapshot timer. The source service was
inactive after its successful oneshot; the source timer is active. The
observatory data root used 4,959,490 bytes after this run, below its 1 GiB cap.

The sibling Reality checkout remained clean at `714f824`; its recorder service
remained active. No Reality unit was restarted, no active or finalized source
record was changed, and the existing public snapshot timer continued to be
active.

## Verification

- Synthetic segmented-source tests: prefix resume, finalized-empty handling,
  one-pass metric agreement, idempotence, crash recovery, catalog tampering,
  and per-run segment/byte bounds all passed.
- Full Veritas backend suite: 83 passed; one existing Starlette/httpx
  deprecation warning.
- Ruff and Mypy: passed for the source analyzer, API, and CLI script.
- Frontend suite: 29 passed; typecheck, lint, and production build passed. The
  build retains its existing large-chunk advisory.
- `systemd-analyze --user verify` passed for both new units; installed user
  unit files match the repository definitions.

The source replay remains in bootstrap. Continue bounded batches and retain the
separate intermittent-snapshot evidence and its readiness gate.
