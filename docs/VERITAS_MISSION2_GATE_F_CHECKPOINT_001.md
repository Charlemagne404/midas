# Gate F checkpoint 001 — recurring Veritas qualification

- **Captured:** 2026-10-15 10:36 UTC
- **Branch:** `project/veritas`
- **Base commit:** `40f04c8`
- **Mission status:** active; this checkpoint delivers a bounded recurring
  qualification cycle, not the full autonomous research plan.

## Implementation

The Veritas Research Director now runs from a persistent user timer at 15 and
45 minutes past each UTC hour. It reads the latest v2 scan summary and matching
finalized v4 event, verifies the event digest and snapshot lineage, and skips
missing, invalid, or more than two-hour-old evidence. The input is pinned to a
scan ID and an Arena admission key. Repeated polls reuse the same job and do
not repeat completed analysis.

The Director writes a current manifest and append-only state/result events to
this checkout's `data/arena/directors/director-veritas-opportunity-v1/`. It
records scan, snapshot, analysis, experiment, dataset, and source-code hashes;
the job result and readiness states; and a recommendation. It admits at most
one active Veritas qualification job. A durable admission intent and the
Arena admission key recover the crash window between job creation and Director
manifest publication. Failed admissions create one local alert and are not
retried automatically for that scan.

Resource gates use Arena's idle-job, available-memory, free-disk, and artifact
limits. The Director service is capped at 5% CPU and 512 MiB; qualification
workers are capped at 10% CPU, 512 MiB, 300 seconds, 64 MiB of source input,
and 512 finalized events. The Director and future qualification jobs restrict
socket families to `AF_UNIX`; a transient systemd check confirmed that this
still permits the local user manager. The code path reads finalized local
artifacts only and has no public or authenticated network client.

The read-only Arena activity API now projects the Director's scan, readiness,
recommendation, and finding summary. The Veritas panel displays the latest and
qualified scan IDs, strategy/model/independent-confirmation readiness, sample
counts, and the current recommendation. The existing manual qualification
action remains scan-idempotent.

## Operating result

The 10:31:10 UTC observer cycle produced
`scan-20261015T103110Z-b077f9c3d7be`. Its rotating six-frame query union had
300 IDs, 184 supported same-condition binary pairs, and 116 explicit
exclusions. The selected 40-market panel had 38 quality-valid pairs. The v4
index now contains 14 finalized snapshots, 560 attempted market pairs, 507
quality-valid pairs, 210 distinct market IDs, and no pending snapshot events.

The Director admitted one job,
`job-1bb0f47d56374e1385503362`, for that scan. It processed 14 events / 256,411
source bytes and completed in about 14 seconds, using 1.404 CPU seconds and
102.3 MiB peak memory. Finding
`veritas-qualification-v1-115a375a2bd16454` records 507 valid states across
210 markets. The maximum top-pair edge remains -0.001 per share; all five
gross, depth, minimum, and fee qualification counts are zero. The Director
keeps no-trade, marks strategy review not ready without a qualifying gross
candidate, and marks model work not ready without public outcome labels.
No orders or authenticated requests occurred.

The initial Director service run took about 30 seconds under its 5% CPU cap
(1.511 CPU seconds, 109.8 MiB peak). A second poll published the completed
finding without admitting another job (1.435 CPU seconds, 72.4 MiB peak).
The user timer is enabled and active; its next tick is 10:45 UTC. The existing
observer and finalized-source replay timers remain active. The Arena root has
no active jobs and reports zero invalid activity artifacts.

One earlier observer run at 11:30 CEST failed with `Invalid frozen control
cohort`. The failure was the legacy cohort-version compatibility check. The
frozen `control-cohort.json` still has its original eight IDs and SHA256
`9578217e20dcc7d1c65fa110f0ed7c689b55483b61191f1aae8d30c9b7300d9a`; it was
not rewritten. The current code accepts that legacy version, and the 12:01
and 12:31 CEST scheduled observations both succeeded.

The first qualification worker logged that the host could not enforce
`PrivateNetwork`; it made no network calls and completed using local files.
The worker launcher and Director unit were then changed to `AF_UNIX`-only
socket families, which the host supports. The next new-scan job will exercise
that setting. No active worker was restarted.

## Verification

- Veritas backend plus the affected Arena job, API, and scheduling tests:
  133 passed; one existing Starlette/httpx deprecation warning.
- Ruff, formatting, and strict Mypy on the changed Python modules: passed.
- Frontend: 29 unit tests, lint, typecheck, formatting, and production build
  passed. Vite retains its existing large-chunk advisory.
- Veritas Playwright workflow: 1 passed.
- `systemd-analyze --user verify` passed for the new service and timer.
- A broader sweep of all 369 collected Arena and Veritas cases was stopped at
  about 15% because it was spending a CPU core on unrelated simulator/stress
  coverage while the collector timer was active. The affected Veritas and
  Arena regression set above completed.

## Remaining work

This Director handles new finalized-snapshot detection, repeatable economic
qualification, persisted readiness, and evidence-backed recommendations. It
does not coordinate the independent Reality-source replay, run strategy/model
experiments, promote models, or autonomously change code. The measurement
pilot still needs its 24-hour review, and the original 48-hour follow-up and
dependence gates remain open. Independent venue-sequence freshness evidence
is still absent. The dashboard remains broader than this Director panel in
the Market Discovery, censoring, and strategy-comparison areas.

Reality, Prometheus, Arena, and Laboratory protected evidence remains
unchanged. No Reality service was restarted, no control cohort was replaced,
and no financial action occurred.
