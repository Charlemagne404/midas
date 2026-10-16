# Veritas Gate E review 001 — bounded research orchestration

Captured 2026-10-15 on `project/veritas`. This is a read-only architecture
review; it did not create or launch an Arena job, enable a timer, or change a
campaign.

## Existing capability

Arena already provides durable research jobs and finite schedules. The native
Arena page exposes persisted job progress and a bounded Research Director.
`POST /api/arena/jobs` validates a typed `JobSpec` and launches a worker through
the existing user supervisor. Jobs are limited to one CPU core, 4 GiB of
memory, a declared wall budget of at most two hours, and a 1 GiB artifact
budget. Admission is capped at eight active or queued jobs.

The finite schedule API accepts up to 32 ordered steps within an admission
window of at most seven days. It writes idempotent child-admission keys, checks
source identity, and waits for idle Arena jobs, at least 2 GiB of available
memory and free disk, and artifact storage below its bound. The dispatcher is
bounded to 100 schedules per pass. Its optional installer writes and enables a
user systemd timer; the installer was not run for this review.

`scripts/research_followup.py` is a specialized, preregistered latency study
over synthetic Arena tournaments. It uses existing supervised Arena jobs,
disjoint seed ranges, frozen model/source identities, at most two cycles and
four child jobs, and does not promote a strategy from challenge outcomes. It
does not consume Reality public-market segments or produce public follow-up
measurements.

## Veritas integration gap

The `JobSpec` kinds do not currently include a Veritas raw-funnel, source-replay,
or follow-up-power job. Those Veritas tools remain bounded command-line
programs, and a recurring Veritas schedule is not registered in the Arena
dispatcher. This review found no reason to add a parallel job controller.

The next ranked source-coverage and follow-up questions still depend on a
materially longer finalized interval and a verified pre-period. No gross
candidate exists in the latest snapshot. Adding a new source-reading worker now
would automate repeated analysis without resolving the existing sample or
study-readiness limits, so that adapter is deferred.

## Decision

Reuse Arena's typed jobs, resource gates, finite schedules, persisted status,
and UI/API for eligible simulator research. Keep Veritas source replay as an
explicit bounded command until a preregistered multi-day analysis or other
recurring job has sufficient information value. Any future adapter must pin
source and code identities, use an explicit source byte bound, read only
finalized `.seg` inputs, write aggregates only to its own artifact root, and
include tests for idempotence, interruption, and source-bound enforcement.

Source references: `packages/midas/arena/jobs.py`,
`packages/midas/arena/scheduling.py`, `apps/api/arena.py`,
`scripts/dispatch_schedules.py`, `scripts/install_schedule_timer.py`, and
`scripts/research_followup.py`.
