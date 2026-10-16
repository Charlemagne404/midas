# Veritas Mission 2 Gate G Checkpoint 003 — Censoring Dashboard

- **Captured:** 2026-10-15
- **Status:** current read-only campaign censoring is linked to market, time, horizon, and observation quality.

## Changes

The overview API now selects the versioned censoring report only when its campaign identity matches the protected baseline and its per-horizon counts reconcile. It uses the current report for follow-up yield, exposes compact market and UTC-hour rows at the longest frozen horizon, and links the full bounded report. The endpoint rejects a mismatched campaign, malformed dimensions, unbalanced counts, oversized artifacts, and symlinked artifact paths.

The dashboard shows the current read-only snapshot size, valid and invalid initial counts, observed and censored follow-up counts by horizon, market coverage, UTC-hour coverage, and censoring mechanism bands. It explains that an unavailable future observation does not prove there was no venue quote and that pending rows are different from censor labels.

## Verification

- Dashboard API regression tests cover valid versioned censoring evidence, count reconciliation, campaign mismatch, and artifact access.
- Frontend tests cover the market/hour table and the full artifact link.
- The Veritas Playwright workflow fetched the analyzer, the censoring report, and the latest public snapshot successfully.
- Full Veritas backend suite: 88 passed; frontend suite: 29 passed. Strict Mypy, Ruff, lint, format, typecheck, and production build passed.

## Limits

The dashboard table shows 20 of 42 markets at the longest horizon and up to 24 UTC hours; the full JSON artifact contains every bounded group. It reports public observation censoring, not execution fills. The campaign remains prospective and its current counts are selected and correlated.
