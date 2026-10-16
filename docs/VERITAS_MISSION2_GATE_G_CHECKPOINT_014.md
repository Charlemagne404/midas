# Gate G checkpoint 014 — pin dashboard to updated gap attribution

**Captured:** 2026-10-16T04:27:21Z
**Mission status:** active; source-only API change is verified and undeployed.

The read-only API now serves gap-censor attribution artifact 002 and requires
the H109 ledger receipt to match the artifact path, file hash, embedded result
digest, and analysis version. The new 447,316-byte artifact is below the
existing 512 KiB response bound. Tests reject a stale artifact path and a
ledger file-digest mismatch. The dashboard continues to label same-market gap
links as temporal associations rather than causal findings.

Verification after the change:

- Dashboard API and market-coverage tests: **28 passed**.
- Ruff lint and formatting: passed.
- Strict Mypy for `apps/api/veritas.py`: passed.
- `git diff --check`: passed.
- An in-process read-only API check against the saved repository returned
  HTTP 200 for the overview and artifact routes; the projected file hash
  matched artifact 002 and all 339 rows were returned.

The change was not deployed and no hosted API or dashboard was restarted. The
Reality recorder, frozen campaign, gap-detail scheduler, and observer were
not changed. Existing artifact 001 and earlier ledger evidence remain
preserved.
