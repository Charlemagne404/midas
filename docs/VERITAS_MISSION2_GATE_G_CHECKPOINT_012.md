# Gate G checkpoint 012 — expose verified censor-gap attribution

**Captured:** 2026-10-16 03:29 UTC
**Mission status:** active; dashboard change verified in source, not deployed.

## Implemented

The read-only Veritas API now allowlists
`VERITAS_MISSION2_CENSOR_GAP_ATTRIBUTION_001.json`, verifies its result digest,
frozen campaign identity, source-check flags, prefix state and bounded counters,
and reconciles the per-outcome reason and link-status totals with the artifact
rows. It rejects a campaign mismatch, digest tampering, counter mismatches,
unsupported link labels, and any assertion that a preceding same-market gap
proves causality. It serves the validated full artifact through
`/api/veritas/artifacts/censor-gap-attribution` and exposes a compact summary
in the overview. The existing 512 KiB artifact limit contains the current
414,687-byte file.

The Opportunity Observatory now shows examined and gap-labeled follow-ups,
preceding same-market temporal candidates, the processed gap-index prefix,
exact references that are indexed or still ahead of the prefix, outcomes with
no matching prior gap in the indexed prefix, and terminations beyond it. The
copy labels temporal matches as candidates, describes the recorder receiver
time basis, and surfaces the source verification and unverified SQLite event
hash chain.

## Evidence displayed from the current saved artifact

The audit scanned 40,075 censored follow-up outcomes and found 339 gap-labeled
rows: 160 `book_issue` and 179 explicit `recorded_gap` labels. Link statuses
reconcile to 45 preceding same-market temporal candidates, 38 exact recorded
gap references verified and indexed, 141 verified references not yet indexed,
29 with no matching earlier gap in the indexed prefix, and 86 terminations
beyond that prefix. The 45 temporal candidates point to six unique indexed gap
events; 30 candidate gaps were over one hour before termination on the
recorder receiver-time clock. These counts do not establish direct causality,
continuous book impairment, order arrival, fills, or profitability.

The gap-detail prefix remains partial: 1,919 of 5,079 cataloged segments are
processed, with 3,158 segments and 862,240,407 source bytes pending. The
attribution source check verified 157 exact source references across 133
finalized segments, hashing 58,443,329 bytes. It read no active segment. The
SQLite event hash chain and full database integrity were not reverified.

## Verification

- `tests/test_veritas_dashboard_api.py`: **23 passed**, including overview and
  artifact-route coverage, campaign mismatch, bad digest, causal-claim
  rejection, and row-to-summary reconciliation. One existing Starlette/httpx
  deprecation warning was emitted by the test environment.
- `apps/web/src/Veritas.test.tsx`: **1 passed**.
- Ruff check and formatting, strict Mypy for `apps/api/veritas.py`, TypeScript
  build-mode typecheck, ESLint, Prettier, and `git diff --check`: passed.
- Production frontend build: passed. Vite reports the existing large-chunk
  advisory (the main JS bundle is 501.86 kB and the chart bundle is 544.41 kB
  before gzip).
- The real saved attribution artifact passes the API validator. Its file SHA-256
  is `332258b51f72c058cf945742ff29f0d26abcb1da0d5865ebcfd5419fb94e45a5`; its
  result digest is
  `2c81d4ad8852b2feaae7a7b5f7bf6948a5f85c514ac9d6bfd0f3bff3935dcab2`.

The running dashboard was not restarted or changed. No service, recorder,
shadow campaign, scheduled collector, research job, or pilot-pinned source was
interrupted. No real orders or authenticated requests were used. The last
recorded operations checkpoint remains inventory 058; this implementation
checkpoint did not refresh host or service telemetry.
