# Gate G checkpoint 007 — finalized-source gap evidence

**Captured:** 2026-10-15 22:08 UTC
**Mission status:** active; the dashboard update is read-only and the existing collectors remain on their schedules.

## Implemented

The Veritas API now exposes two bounded, campaign-matched gap evidence views.
The frozen campaign audit is available as `gap_censor_audit` in
`/api/veritas/overview` and as the allowlisted
`/api/veritas/artifacts/censor-gap-audit` artifact. The API verifies its
canonical artifact digest, audit identity, campaign ID, outcome reconciliation,
and finalized-record counts before returning it.

The incremental finalized-source gap summary is exposed as
`finalized_gap_detail` and at
`/api/veritas/artifacts/gap-detail-current`. Its canonical self-digest,
campaign ID, bounded counters, count maps, replay progress, and
`active_segment_read=false` declaration are checked. The endpoint reads only
the bounded summary JSON; it does not open Reality source segments.

The dashboard now distinguishes explicit `recorded_gap` outcome references
from indirect `book_issue:gap` labels, shows the source record kinds used to
terminate the indirect labels, and reports the incremental prefix's
all-period and campaign-window gap counts separately. It warns that a zero
campaign-window count in an incomplete prefix is not evidence of zero gaps.
Both views link to their hash-verified source artifacts.

## Evidence displayed from the current artifacts

The frozen campaign audit covers 40,075 censored outcome rows. It identifies
339 gap-related outcomes: 179 explicit `recorded_gap` rows verified against
97 unique finalized gap records, and 160 `book_issue:gap` rows terminating on
60 later source records (53 discovery pages, two fee metadata records, and
five market metadata records). The exact later record is not verified as the
cause of the original gap. Record offsets and hashes were verified for 157
source records across 133 finalized segments. No active `.open` segment was
read. The audit did not reverify the SQLite event hash chain or run a full
database integrity check.

The current gap-detail summary was generated at 21:51:20 UTC. It has processed
274 of 4,455 replayable finalized segments, with 4,181 segments / 1,100,463,766
bytes pending. The prefix contains 1,152 all-period gap events and no
campaign-window gap event so far. The latest gap event in the prefix is before
the campaign window; the zero in-window count remains partial while the
analyzer catches up. The summary declares that it did not read an active
segment.

## Verification

- `tests/test_veritas_dashboard_api.py`: **18 passed**, including campaign and digest rejection, reconciliation checks, active-segment rejection, and both artifact endpoints.
- `apps/web/src/Veritas.test.tsx`: **1 passed**, including the explicit/indirect distinction and incomplete-prefix warning.
- `apps/web/e2e/veritas.spec.ts`: **1 passed** with the new artifact links and attribution copy checked in Chromium against an isolated demo API/database. The temporary test servers exited after the run.
- Ruff check and format check passed; strict Mypy for `apps/api/veritas.py` passed.
- Prettier check and TypeScript typecheck passed.
- A read-only TestClient request against the current repository returned **200** for `/api/veritas/overview` and both new artifact routes. The production artifacts produced the same counts recorded above.
- The focused API suite emitted the existing Starlette/httpx deprecation warning. No full regression suite, deployment, or service restart was run.

No campaign, collection process, source segment, or running research job was changed for this dashboard work. Gate G remains in progress; this checkpoint does not close Mission 2.
