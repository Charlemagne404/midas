# Gate G checkpoint 013 — pin coverage dashboard to artifact 003

**Captured:** 2026-10-16 03:58 UTC
**Mission status:** active; the source change is verified and not deployed.

## Change

The market-universe coverage route previously allowlisted artifact 001 and validated the H084 receipt. The saved 48-snapshot coverage result is artifact 003 with ledger receipt H105. The read-only API now allowlists coverage 003 and validates H105's artifact path, analysis version, and artifact_file_sha256 against the saved file.

The dashboard API tests now use the artifact 003/H105 schema and reject both digest tampering and a receipt that points to stale coverage 002. The real saved artifact digest is aa9e59a360324d6480a27b63447868ccc5519c905eb02002b37277485a249634. It is 104,197 bytes, within the existing 512 KiB artifact bound.

## Verification

- tests/test_veritas_dashboard_api.py and tests/test_veritas_universe_coverage.py: 26 passed total (24 API and 2 coverage tests).
- Ruff check and format check passed.
- Strict Mypy for apps/api/veritas.py passed.
- git diff --check passed.
- The real H105 receipt and artifact file hash agree.

The change is in the project/veritas source checkout only. The hosted dashboard was not deployed or restarted, and no collector, pilot, campaign, or research job was altered. The dashboard remains read-only.
