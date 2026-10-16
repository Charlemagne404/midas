# Gate G checkpoint 011 — market-universe coverage projection

**Captured:** 2026-10-16 00:12 UTC
**Mission status:** active; projection code is not deployed.

## Implemented

The read-only Veritas overview now exposes the versioned A1 bounded market-
universe report through an explicit artifact allowlist. Before returning a
summary or downloadable report, the API compares the exact report bytes with
the digest recorded in research-ledger H084, then checks the schema and
analysis version, source-verification flags, identity totals, pair-count
reconciliation, metadata-band totals, selection totals, and bounded
limitations. Missing, oversized, symlinked, receipt-mismatched, or internally
inconsistent artifacts are not projected as valid coverage.

The Market Discovery panel displays the saved scan count, distinct and
eligible IDs, latest audited union composition, market/condition/asset
identities, current-v4 quality-pair totals, latest eligible metadata bands,
and the scan-1 capture-versus-replay discrepancy. It links to the hashed
artifact and states that intermittent bounded queries do not establish a
venue-wide denominator, continuous quotes, order arrival, fills, or
profitability.

## Evidence and verification

The projected source is
`docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_001.json`, SHA-256
`db330e63bc541321a8a0167bf21ff64895bf655ffd00ac7729d78f04ff906aef`. It
covers the 40 hash-verified snapshots through scan 40; it does not yet include
the newer scan 41. The live observer has since recorded scan
`scan-20261016T000215Z-e6ff8b97e045` at 00:02:15 UTC: 33/40 pairs passed the
current request/receipt quality check, with zero top-gross or economic
positive counts. Across 41 snapshots, the current-v4 replay contains
1,438/1,640 quality-valid pairs and no positive candidates.

- `tests/test_veritas_dashboard_api.py`: **21 passed**, including valid
  H084-pinned projection, rejection of a tampered ledger receipt, and
  rejection of inconsistent counts. One existing Starlette/httpx deprecation
  warning remains.
- `tests/test_veritas_universe_coverage.py`: **2 passed**.
- `apps/web/src/Veritas.test.tsx`: **1 passed**.
- Ruff lint and format, strict Mypy for `apps/api/veritas.py`, ESLint,
  Prettier, TypeScript `--noEmit`, and `git diff --check`: passed.
- No full regression suite, production build, live HTTP probe, service
  restart, deployment, collector change, campaign change, or manual research
  job was performed for this projection.

The source tree contains the change on `project/veritas` at base commit
`122da17`; it remains pending commit and is not running on the hosted Midas
API/dashboard. The fixed measurement pilot is unchanged and continues toward
its 19:00:55 UTC stop. Gate G and Mission 2 remain active.
