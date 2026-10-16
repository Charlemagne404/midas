# Gate F checkpoint 002 — source summary in Research Director

**Captured:** 2026-10-15 10:59 UTC  
**Branch:** `project/veritas`  
**Checkpoint base:** `d1d6681`

## Change

The Veritas Research Director now reads the separately scheduled finalized
Reality source-analysis summary on every cycle. It verifies the sealed summary
digest, analysis version, campaign identity and hash, code hash, progress and
economic counters, campaign window, and the `active_segment_read=false`
boundary. The Director stores the validated digest and a compact set of replay
and opportunity counters beside public-scan qualification state.

Source replay readiness remains its own field. A missing or invalid source
summary is reported without blocking an otherwise valid public-scan
qualification, and public-scan readiness cannot imply that the independent
source replay has reached the campaign window. The Director does not run or
restart the replay. Its read-only API exposes the validated counters, and the
Veritas activity panel now shows source readiness, processed/cataloged
segments, quality-valid campaign states, and positive full-depth pre-fee
states.

## Live evidence

A no-launch Director poll at 10:56 UTC returned `CURRENT`, reused the existing
completed qualification for
`scan-20261015T103110Z-b077f9c3d7be`, and admitted no job. The API projection
reported zero active jobs and zero invalid activity artifacts. The persisted
Director manifest records source summary digest
`42c477ea02173bd2ed52b16248d2cca0e5b3e7e154edfcc273a8553331a1e4cb` and
validated source readiness `catching_up_finalized_source`.
A second no-launch poll at 10:59 UTC, after the final path-safety edit, returned
the same current scan and completed job without admitting work; its manifest
records source revision `1b4a1db450cdae1d5c5969f2148f857aa5b2dd71d6627ed4c2cc0dab7b1a31fe`.

At that poll, 1,072/3,136 finalized segments had been processed, with 2,064
segments / 557,814,406 bytes pending through ordinal 122,759. The processed
prefix still contains zero campaign-window frames, zero quality-valid states,
and zero positive top-pair or full-depth pre-fee states. This is insufficient
for source-based opportunity inference. The existing no-trade recommendation,
strategy-not-ready state, and model-not-ready state remain in force.

The observer, source-analysis, and Director timers were active at capture. The
next scheduled runs were 13:01:31, 13:10:21, and 13:15:00 CEST, respectively.
No Reality service, campaign, source-analysis state, or replay input was
changed.

## Verification

- Focused Director and Arena API tests: 22 passed; one existing Starlette/httpx
  deprecation warning.
- The targeted Veritas dashboard test passed and asserts source readiness is
  displayed.
- Frontend TypeScript check, Prettier, and production build passed; Vite emitted
  its existing large-chunk advisory.
- Ruff checks, Ruff formatting, and strict Mypy passed on changed Python code.
- A no-launch poll confirmed the current manifest and API projection without
  creating another qualification job.

Mission 2 remains active. Replay completion, independent source coverage,
sequence freshness, the separate follow-up study gates, economic confirmation,
strategy/model experiments, and broader dashboard scope remain open. See
[operations](VERITAS_MISSION2_OPERATIONS.md) and [research inventory
014](VERITAS_MISSION2_RESEARCH_INVENTORY_014.json).
