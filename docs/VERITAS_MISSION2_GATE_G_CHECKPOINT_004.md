# Veritas Mission 2 Gate G Checkpoint 004 — Director history and experiment lineage

- **Captured:** 2026-10-15
- **Branch:** `project/veritas`
- **Status:** implemented in the existing read-only Veritas dashboard.

## Dashboard changes

The Arena research-activity projection now includes up to eight recent events
for each of the five displayed Director manifests. It scans no more than 128
event files per Director, accepts payloads up to 64 KiB, verifies each
event's immutable filename digest and Director identity, and exposes only
bounded status, stage, timestamp, scan/job/finding IDs, experiment and dataset
hashes, source revision, gate counts, readiness, and recommendation fields.
Symlinks, malformed files, and digest mismatches are omitted and counted.
The complete event archive remains unchanged.

The Veritas Director panel can now show the sequence of attempts rather than
only the current state. It distinguishes the 11:15 scan-pinned admission,
source-revision failure at 11:20 (no automatic retry), and the later stable
11:31 scan qualification at 11:45, including its experiment run and zero
positive counts at all five qualification gates. A live read-only projection
returned eight verified events and zero invalid activity artifacts. The
history surface does not change strategy or model readiness.

## Verification

- Arena API tests: 16 passed, including digest-name verification, tampered
  event rejection, bounds, and existing job/Director/schedule coverage.
- Frontend unit suite: 29 passed.
- TypeScript typecheck, ESLint, Prettier, and production build passed. Vite
  emitted the existing large-chunk advisory.
- Strict Mypy and Ruff check/format passed for the changed Arena API module and
  tests.
- The Veritas Playwright workflow passed with a simulated Director history
  fixture, verifying that the failure note and completed experiment lineage
  are visible in the browser.
- The live persisted Arena event projection returned the current Director's
  eight most recent verified events, including the preserved source-drift
  failure and stable-revision completion; it reported zero invalid artifacts.

## Limits

This adds research traceability, not new economic evidence. The current
qualification still has zero positive states at all five gates. There are no
candidate labels to support a strategy tournament or model training, and the
dashboard does not report an economic strategy comparison. History is bounded
to eight returned events and 128 inspected event files per Director; the
immutable Arena event archive remains the complete record.

Mission 2 remains active. Multi-day market coverage, independent freshness,
source replay through the frozen campaign window, additional verified
multi-outcome groups, and an evidence-supported strategy comparison remain
open.
